"""
Format-agnostic base for generating synthetic recordings.

Building a ground-truth signal (a noisy baseline with blockage events
planted at known positions) is the same job regardless of what file format
it ends up written as. Only "how do physical units become bytes on disk"
differs between formats (everything else here is shared).

BaseSyntheticRecordingWriter captures that split. It implements signal
construction once and calls out to a subclass-defined _write() for the
format-specific encode-and-save step. A new file format is a new subclass
that implements _write() and nothing else.

generate_multichannel_dataset() is likewise format-agnostic: it takes a
writer instance and loops it over channels, so it works for any format
without modification.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Generic, List, Optional, Tuple, TypeVar

import numpy as np


@dataclass
class SyntheticEvent:
    """
    One blockage event placed into a synthetic recording.

    :param start_index: Sample index where the event begins.
    :type start_index: int
    :param length_samples: Event duration in samples.
    :type length_samples: int
    :param amplitude: Signed change during the event, relative to baseline,
        in whatever physical unit the recording format uses. Negative for
        a blockage.
    :type amplitude: float
    """

    start_index: int
    length_samples: int
    amplitude: float

    @property
    def start_time_s(self) -> float:
        """
        Event start, in seconds from the beginning of the recording.

        :return: Start time in seconds.
        :rtype: float
        """
        return self._start_time_s

    @property
    def duration_s(self) -> float:
        """
        Event duration in seconds.

        :return: Duration in seconds.
        :rtype: float
        """
        return self._duration_s

    def with_samplerate(self, samplerate: float) -> "SyntheticEvent":
        """
        Attach a sample rate so start_time_s and duration_s can be reported.

        :param samplerate: Sample rate of the recording this event belongs to.
        :type samplerate: float

        :return: This event, for chaining.
        :rtype: SyntheticEvent
        """
        self._start_time_s = self.start_index / samplerate
        self._duration_s = self.length_samples / samplerate
        return self


@dataclass
class BaseRecordingConfig:
    """
    Recording-shape parameters common to every synthetic format.

    Anything that affects the signal itself (how long it is, how noisy,
    where events go and how big they are) lives here. Anything that
    affects only how that signal gets encoded to disk (gain stacks, ADC
    ranges, header fields, ...) belongs on a format-specific subclass
    instead, e.g. ChimeraRecordingConfig.

    :param base_name: Filename stem shared by every channel.
    :type base_name: str
    :param timestamp: Acquisition timestamp, formatted YYYYmmdd_HHMMSS.
        Defaults to the current local time at the moment a config instance
        is created (not import time), so leaving it unset gives each run
        its own timestamp. Pass an explicit value for reproducible
        filenames, e.g. in tests that assert against a known stem.
    :type timestamp: str
    :param samplerate: Sample rate in Hz.
    :type samplerate: float
    :param duration_s: Recording length in seconds.
    :type duration_s: float
    :param baseline: Mean open-channel signal level, in whatever physical
        unit the writer's format uses (e.g. picoamps).
    :type baseline: float
    :param noise_std: Standard deviation of the Gaussian baseline noise, in
        the same unit as baseline.
    :type noise_std: float
    :param event_amplitude: Signed change during each event, in the same
        unit as baseline. Negative for a blockage.
    :type event_amplitude: float
    :param event_duration_s: Length of each event, in seconds.
    :type event_duration_s: float
    :param edge_margin_s: How far events are kept from either end of the
        recording, in seconds.
    :type edge_margin_s: float
    """

    base_name: str = "synthetic"
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    samplerate: float = 4_000_000.0
    duration_s: float = 2.0
    baseline: float = 0.0
    noise_std: float = 15.0
    event_amplitude: float = -400.0
    event_duration_s: float = 0.0005
    edge_margin_s: float = 0.05


ConfigT = TypeVar("ConfigT", bound=BaseRecordingConfig)
"""
Type variable for a specific format's config subclass (e.g.
ChimeraRecordingConfig). Parameterizing BaseSyntheticRecordingWriter and
generate_multichannel_dataset over this, rather than typing everything as
plain BaseRecordingConfig, is what lets each writer's _write() legitimately
narrow its config parameter to its own subclass (e.g. ChimeraRecordingWriter
requiring ChimeraRecordingConfig specifically) without that being a Liskov
substitution violation: mypy checks each writer against
BaseSyntheticRecordingWriter[ItsOwnConfigType] rather than against a single
shared BaseRecordingConfig that every subclass's _write() would otherwise
have to accept, gain-stack fields and all.
"""


@dataclass
class SyntheticDataset:
    """
    One generated channel and the ground truth about what's in it.

    :param data_path: Path to the file holding the samples.
    :type data_path: Path
    :param channel: Headstage/channel number.
    :type channel: int
    :param config: The configuration used to generate this channel.
    :type config: BaseRecordingConfig
    :param events: Every event planted in the signal, in order.
    :type events: List[SyntheticEvent]
    :param metadata_path: Path to a sidecar metadata file, if the format
        uses one. None for formats that self-describe in one file.
    :type metadata_path: Optional[Path]
    """

    data_path: Path
    channel: int
    config: BaseRecordingConfig
    events: List[SyntheticEvent] = field(default_factory=list)
    metadata_path: Optional[Path] = None

    @property
    def samplerate(self) -> float:
        """
        Sample rate in Hz, from the config.

        :return: Sample rate in Hz.
        :rtype: float
        """
        return self.config.samplerate

    @property
    def duration_s(self) -> float:
        """
        Recording length in seconds, from the config.

        :return: Duration in seconds.
        :rtype: float
        """
        return self.config.duration_s

    @property
    def num_events(self) -> int:
        """
        How many events were planted.

        :return: Event count.
        :rtype: int
        """
        return len(self.events)

    def event_start_times_s(self) -> List[float]:
        """
        Start time of every event, in seconds.

        :return: Start times in seconds, in event order.
        :rtype: List[float]
        """
        return [e.start_time_s for e in self.events]


@dataclass
class MultichannelSyntheticDataset:
    """
    A generated multi-channel recording and the ground truth about it.

    :param config: The configuration shared by every channel.
    :type config: BaseRecordingConfig
    :param channels: Dict mapping channel number to its SyntheticDataset.
    :type channels: Dict[int, SyntheticDataset]
    """

    config: BaseRecordingConfig
    channels: Dict[int, SyntheticDataset] = field(default_factory=dict)

    @property
    def channel_numbers(self) -> List[int]:
        """
        Channel numbers present in this experiment, in insertion order.

        :return: Channel numbers.
        :rtype: List[int]
        """
        return list(self.channels.keys())

    @property
    def total_num_events(self) -> int:
        """
        Events planted across all channels combined.

        :return: Total event count.
        :rtype: int
        """
        return sum(ds.num_events for ds in self.channels.values())

    def __getitem__(self, channel: int) -> SyntheticDataset:
        return self.channels[channel]


def build_noisy_segment(
    rng: np.random.Generator, n_samples: int, baseline: float, noise_std: float
) -> np.ndarray:
    """
    Build a flat baseline segment with Gaussian noise.

    This is the one piece of signal construction shared between continuous
    recordings (many events embedded in one long trace, via
    BaseSyntheticRecordingWriter._build_trace) and per-event databases (one
    short padded snippet per event, via synthetic_events_db). Both need
    "baseline plus noise" as their starting point before an event's
    amplitude gets added over some span of it; pulling it out here means
    that starting point can't drift out of sync between the two.

    :param rng: Random generator to draw noise from.
    :type rng: numpy.random.Generator
    :param n_samples: Length of the segment, in samples.
    :type n_samples: int
    :param baseline: Mean signal level, in physical units.
    :type baseline: float
    :param noise_std: Standard deviation of the Gaussian noise, in the
        same units as baseline.
    :type noise_std: float

    :return: The noisy baseline segment.
    :rtype: numpy.ndarray
    """
    return baseline + rng.normal(0.0, noise_std, n_samples)


class BaseSyntheticRecordingWriter(ABC, Generic[ConfigT]):
    """
    Builds a ground-truth trace and hands it off to a format-specific writer.

    Subclasses implement _write() (how to turn a raw physical-unit trace
    into bytes on disk, and a metadata file if the format needs one) and
    get event planting, noise generation, and edge-margin handling for
    free from generate() and _build_trace().

    Generic over ConfigT, the specific BaseRecordingConfig subclass this
    writer's format needs (e.g. BaseSyntheticRecordingWriter[ChimeraRecordingConfig]
    for Chimera). A format needing no extra fields beyond the base ones
    can parameterize over BaseRecordingConfig itself.
    """

    def generate(
        self,
        out_dir: Path,
        config: ConfigT,
        *,
        channel: int = 0,
        num_events: int = 5,
        seed: int = 42,
    ) -> SyntheticDataset:
        """
        Write one channel's recording with events at known positions.

        Events are spaced evenly across the recording, keeping clear of
        both ends by config.edge_margin_s so that no event is truncated by
        the start or end of the file.

        :param out_dir: Directory to write the channel's file(s) into.
            Created if it does not already exist.
        :type out_dir: Path
        :param config: Recording parameters, of this writer's specific
            ConfigT type.
        :type config: ConfigT
        :param channel: Channel/headstage number for this file.
        :type channel: int
        :param num_events: How many events to plant on this channel.
        :type num_events: int
        :param seed: Random seed, making this channel's noise reproducible.
        :type seed: int

        :return: Dataset describing the file(s) that were written and
            their contents.
        :rtype: SyntheticDataset

        :raises ValueError: If the recording is too short to hold the
            requested events without overlap, or if the duration rounds to
            no samples.
        """
        trace, events = self._build_trace(config, num_events, seed)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        return self._write(out_dir, config, channel, trace, events)

    def _build_trace(
        self, config: ConfigT, num_events: int, seed: int
    ) -> Tuple[np.ndarray, List[SyntheticEvent]]:
        """
        Build the ground-truth signal: baseline, Gaussian noise, and
        planted events, all in physical units. Shared by every format.

        :param config: Recording parameters.
        :type config: ConfigT
        :param num_events: How many events to plant.
        :type num_events: int
        :param seed: Random seed for the noise and, indirectly, event
            spacing reproducibility.
        :type seed: int

        :return: The trace as a float array in the same units as
            config.baseline, and the list of events planted in it.
        :rtype: Tuple[numpy.ndarray, List[SyntheticEvent]]

        :raises ValueError: If the recording is too short to hold the
            requested events without overlap, or if the duration rounds to
            no samples.
        """
        rng = np.random.default_rng(seed)
        n_samples = int(round(config.duration_s * config.samplerate))
        if n_samples <= 0:
            raise ValueError("duration_s * samplerate must be a positive number of samples")

        trace = build_noisy_segment(rng, n_samples, config.baseline, config.noise_std)

        event_len = max(1, int(round(config.event_duration_s * config.samplerate)))
        margin = max(event_len, int(round(config.edge_margin_s * config.samplerate)))
        if n_samples - 2 * margin <= event_len * num_events:
            raise ValueError(
                "duration_s too short for the requested "
                "num_events/event_duration_s/edge_margin_s"
            )

        # Space events evenly across the usable span, then dedupe in case
        # rounding collapsed two positions onto the same sample index.
        positions = np.linspace(margin, n_samples - margin - event_len, num_events, dtype=int)
        positions = np.unique(positions)
        if len(positions) != num_events:
            raise ValueError("Requested events do not fit without overlap; reduce num_events")

        events: List[SyntheticEvent] = []
        for pos in positions:
            pos = int(pos)
            trace[pos : pos + event_len] += config.event_amplitude
            events.append(
                SyntheticEvent(
                    start_index=pos, length_samples=event_len, amplitude=config.event_amplitude
                ).with_samplerate(config.samplerate)
            )

        return trace, events

    @abstractmethod
    def _write(
        self,
        out_dir: Path,
        config: ConfigT,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Encode trace to this format's on-disk representation and write it.

        Must be implemented by subclasses, one per file format. A subclass
        writing e.g. Chimera's format can (and should) narrow config's
        type here to ChimeraRecordingConfig specifically, by declaring
        itself as BaseSyntheticRecordingWriter[ChimeraRecordingConfig] --
        that's what ConfigT is for, rather than every writer needing to
        accept a bare BaseRecordingConfig it can't actually use.

        :param out_dir: Directory to write into. Already created by the
            time this is called.
        :type out_dir: Path
        :param config: The config passed to generate(), of this writer's
            specific ConfigT type.
        :type config: ConfigT
        :param channel: Channel/headstage number for this file.
        :type channel: int
        :param trace: The ground-truth signal, in physical units.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace, for recording in
            the returned dataset.
        :type events: List[SyntheticEvent]

        :return: Dataset describing what was written.
        :rtype: SyntheticDataset
        """
        raise NotImplementedError


def generate_multichannel_dataset(
    writer: BaseSyntheticRecordingWriter[ConfigT],
    out_dir: Path,
    config: ConfigT,
    *,
    channels: List[int],
    num_events_per_channel: Dict[int, int] | int = 5,
    seed_base: int = 100,
) -> MultichannelSyntheticDataset:
    """
    Write one recording per channel into a single directory, for any format.

    Every channel is generated from the same config (and therefore at the
    same sample rate and event shape), but with a distinct random seed, so
    the noise and event placement differ between channels while remaining
    reproducible run to run. Works with any BaseSyntheticRecordingWriter
    subclass; ConfigT ties writer and config to the same format so mypy
    catches a mismatched pair (e.g. a ChimeraRecordingWriter given a
    plain BaseRecordingConfig) rather than it surfacing as an
    AttributeError deep inside _write() at runtime.

    :param writer: The format-specific writer to use for every channel.
    :type writer: BaseSyntheticRecordingWriter[ConfigT]
    :param out_dir: Directory to write all channels into. Readers that
        glob a directory for sibling channel files require this to not be
        split across subdirectories.
    :type out_dir: Path
    :param config: Recording parameters shared by every channel, of the
        same ConfigT type writer expects.
    :type config: ConfigT
    :param channels: Channel numbers to generate, e.g. [1, 2, 3].
    :type channels: List[int]
    :param num_events_per_channel: Either one count used for all channels,
        or a dict mapping channel number to its own count. Channels absent
        from the dict fall back to five events.
    :type num_events_per_channel: Union[Dict[int, int], int]
    :param seed_base: First random seed; each channel uses the next value up.
    :type seed_base: int

    :return: Dataset describing every channel's files and planted events.
    :rtype: MultichannelSyntheticDataset
    """
    result = MultichannelSyntheticDataset(config=config)

    for offset, ch in enumerate(channels):
        n_events = (
            num_events_per_channel
            if isinstance(num_events_per_channel, int)
            else num_events_per_channel.get(ch, 5)
        )
        result.channels[ch] = writer.generate(
            out_dir,
            config,
            channel=ch,
            num_events=n_events,
            seed=seed_base + offset,
        )

    return result