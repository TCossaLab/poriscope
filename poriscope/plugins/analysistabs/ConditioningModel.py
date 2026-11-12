# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs
# Michel Stephan

import json
import logging
from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, override

import numpy as np
import numpy.typing as npt

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class ConditioningModel(MetaModel):
    """
    Holds the Conditioning tab's results: each channel's 1 Hz noise at every PSD recording.

    The 1 Hz value of a recording is found as the conditioning app always found it: Welch's
    PSD of the recording with a Hann window, segments of the recording's own points per
    average and no overlap, then a straight-line fit of log10 PSD against log10 frequency
    over the fit range, read off at 1 Hz. Computing them is the slow part of a plot - every
    recording of every channel is read - so it runs on a worker per channel and the results
    are kept, keyed by the experiment's settings and the fit range. A plot with the same
    experiment and fit range redraws from what is kept; editing the experiment's settings
    drops what was kept for it.
    """

    logger = logging.getLogger(__name__)

    #: The data-plugin family this tab reads experiments from.
    LOADER_FAMILY = "MetaConditioningLoader"

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Start with nothing computed.
        """
        #: loader key -> the settings its kept results were computed with
        self._fingerprints: Dict[str, str] = {}
        #: (loader key, fit start, fit end) -> channel -> polarity -> results
        self._results: Dict[
            Tuple[str, float, float], Dict[int, Dict[str, Dict[str, List[float]]]]
        ] = {}
        #: loader key -> notes about the recordings, said once per plot
        self._notes: Dict[str, List[str]] = {}

    # public API
    @log(logger=logger)
    def forget_stale_results(self, loader: str) -> None:
        """
        Drop what was kept for an experiment whose settings have changed since.

        Whatever the plugin raises on the way propagates, through :py:meth:`call`.

        :param loader: the experiment's plugin key
        :type loader: str
        """
        fingerprint = json.dumps(
            {
                name: setting.get("Value")
                for name, setting in self.call(
                    self.LOADER_FAMILY, loader, "get_raw_settings"
                ).items()
            },
            sort_keys=True,
            default=str,
        )
        if self._fingerprints.get(loader) != fingerprint:
            for kept in [k for k in self._results if k[0] == loader]:
                del self._results[kept]
            self._notes.pop(loader, None)
        self._fingerprints[loader] = fingerprint

    @log(logger=logger)
    def missing_channels(
        self, loader: str, channels: Sequence[int], fit_start: float, fit_end: float
    ) -> List[int]:
        """
        The channels whose 1 Hz values have not been computed for this fit range.

        :param loader: the experiment's plugin key
        :type loader: str
        :param channels: the channels asked for
        :type channels: Sequence[int]
        :param fit_start: lower end of the fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the fit range, Hz
        :type fit_end: float
        :return: the channels with no kept results, in the order asked
        :rtype: List[int]
        """
        kept = self._results.get((loader, fit_start, fit_end), {})
        return [channel for channel in channels if channel not in kept]

    @log(logger=logger)
    def is_running(self, loader: str) -> bool:
        """
        Whether any channel of this experiment is still being computed.

        :param loader: the experiment's plugin key
        :type loader: str
        :return: True while a worker for it runs
        :rtype: bool
        """
        return any(self.thread_running.get(loader, {}).values())

    @log(logger=logger)
    def one_hz_run(
        self, loader: str, channel: int, fit_start: float, fit_end: float
    ) -> Generator[float, Optional[bool], None]:
        """
        Compute one channel's 1 Hz noise at every PSD recording, yielding progress.

        The results are kept only if every recording was analysed, so a channel whose run
        was stopped or failed is computed again by the next plot. A recording with fewer
        than two frequency bins in the fit range ends the run with ``ValueError`` naming it.

        :param loader: the experiment's plugin key
        :type loader: str
        :param channel: the channel
        :type channel: int
        :param fit_start: lower end of the fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the fit range, Hz
        :type fit_end: float
        :return: a generator yielding fractional progress, 0 to 1, that stops early
            when it is sent True
        :rtype: Generator[float, Optional[bool], None]
        """
        polarities = self.call(self.LOADER_FAMILY, loader, "get_psd_polarities")
        counts = {
            polarity: self.call(
                self.LOADER_FAMILY, loader, "get_psd_segment_count", polarity
            )
            for polarity in polarities
        }
        total = max(1, sum(counts.values()))
        done = 0
        results: Dict[str, Dict[str, List[float]]] = {}
        notes: List[str] = []
        stopped = False
        for polarity in polarities:
            cycles: List[float] = []
            values: List[float] = []
            for index in range(counts[polarity]):
                cycle = self.call(
                    self.LOADER_FAMILY, loader, "get_psd_cycle", polarity, index
                )
                value, note = self._one_hz(
                    loader, polarity, index, channel, cycle, fit_start, fit_end
                )
                cycles.append(float(cycle))
                values.append(value)
                if note:
                    notes.append(note)
                done += 1
                sent = yield done / total
                stopped = bool(sent)
                if stopped:
                    break
            if stopped:
                break
            results[polarity] = {"cycles": cycles, "one_hz": values}
        if not stopped:
            self._results.setdefault((loader, fit_start, fit_end), {})[
                channel
            ] = results
            self._notes[loader] = notes

    @log(logger=logger)
    def take_notes(self, loader: str) -> List[str]:
        """
        Hand over, once, what the last run noticed about the recordings - a short one, say.

        :param loader: the experiment's plugin key
        :type loader: str
        :return: the notes, each one sentence
        :rtype: List[str]
        """
        return self._notes.pop(loader, [])

    @log(logger=logger)
    def plot_data(
        self, loader: str, channels: Sequence[int], fit_start: float, fit_end: float
    ) -> List[Dict[str, Any]]:
        """
        Everything the View draws for each channel, from the experiment and the kept results.

        Each entry has ``channel``, ``cycles``, ``measured``, ``max_target``,
        ``min_target``, ``disabled`` (no pore size measured in any cycle) and ``psd``,
        which maps each polarity with kept results to its ``cycles`` and ``one_hz`` values.

        :param loader: the experiment's plugin key
        :type loader: str
        :param channels: the channels to draw
        :type channels: Sequence[int]
        :param fit_start: lower end of the fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the fit range, Hz
        :type fit_end: float
        :return: one entry per channel, in the order asked
        :rtype: List[Dict[str, Any]]
        """
        cycles = self.call(self.LOADER_FAMILY, loader, "get_cycles")
        kept = self._results.get((loader, fit_start, fit_end), {})
        data = []
        for channel in channels:
            sizes = self.call(self.LOADER_FAMILY, loader, "get_pore_sizes", channel)
            measured = np.asarray(sizes["measured"], dtype=np.float64)
            data.append(
                {
                    "channel": channel,
                    "cycles": np.asarray(cycles, dtype=np.float64),
                    "measured": measured,
                    "max_target": np.asarray(sizes["max_target"], dtype=np.float64),
                    "min_target": np.asarray(sizes["min_target"], dtype=np.float64),
                    "disabled": bool(np.all(measured == 0)),
                    "psd": {
                        polarity: {
                            "cycles": np.asarray(result["cycles"], dtype=np.float64),
                            "one_hz": np.asarray(result["one_hz"], dtype=np.float64),
                        }
                        for polarity, result in kept.get(channel, {}).items()
                    },
                }
            )
        return data

    # private API
    @log(logger=logger)
    def _one_hz(
        self,
        loader: str,
        polarity: str,
        index: int,
        channel: int,
        cycle: int,
        fit_start: float,
        fit_end: float,
    ) -> Tuple[float, str]:
        """
        One recording's 1 Hz noise on one channel.

        :param loader: the experiment's plugin key
        :type loader: str
        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :param index: the recording
        :type index: int
        :param channel: the channel
        :type channel: int
        :param cycle: the cycle the recording belongs to, for messages
        :type cycle: int
        :param fit_start: lower end of the fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the fit range, Hz
        :type fit_end: float
        :raises ValueError: If the recording has fewer than two frequency bins in the fit range.
        :return: the 1 Hz value in pA^2/Hz, and a note if the recording is short, else ""
        :rtype: Tuple[float, str]
        """
        # Each channel runs on its own worker; a loader that cannot be read from two
        # threads at once says so, and its own lock then serialises the reads.
        with self.call(self.LOADER_FAMILY, loader, "serialize_channel_operations"):
            segment: npt.NDArray[np.float64] = self.call(
                self.LOADER_FAMILY, loader, "load_psd_segment", polarity, index, channel
            )
        samplerate = self.call(
            self.LOADER_FAMILY, loader, "get_psd_samplerate", polarity, index
        )
        points = self.call(
            self.LOADER_FAMILY, loader, "get_psd_points_per_average", polarity, index
        )
        frequency, psd = self.power_spectral_density(segment, samplerate, points, 0.0)
        try:
            _, intercept = self.fit_power_law(frequency, psd, fit_start, fit_end)
        except ValueError as e:
            raise ValueError(f"PSD{polarity} at cycle {cycle}: {e}") from e
        note = ""
        if len(segment) < points:
            note = (
                f"PSD{polarity} at cycle {cycle} has {len(segment)} samples, fewer than "
                f"its {points} points per average, so its PSD is one shorter segment"
            )
        return float(10**intercept), note
