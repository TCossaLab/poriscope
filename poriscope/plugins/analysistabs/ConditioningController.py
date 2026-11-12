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

import logging
from typing import Any, Dict, List, override

from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.ConditioningModel import ConditioningModel
from poriscope.plugins.analysistabs.ConditioningView import ConditioningView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class ConditioningController(MetaController):
    """
    The Conditioning tab: each channel's pore size over a conditioning experiment's cycles, with
    the 1 Hz noise of its PSD recordings at positive and negative bias.

    This is its Controller. A plot computes, on a worker per channel, whatever 1 Hz values the
    Model has not kept for the experiment and fit range asked for, and draws once every worker
    has ended; a plot whose values are all kept draws at once.
    """

    logger = logging.getLogger(__name__)

    #: Declared with this tab's own types so the type checker sees
    #: the methods its View and Model add to the bases.
    view: ConditioningView
    model: ConditioningModel

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Build this tab's View and Model.
        """
        self.view = ConditioningView()
        self.model = ConditioningModel()
        #: loader key -> the plot waiting for that experiment's workers to end
        self._waiting: Dict[str, Dict[str, Any]] = {}
        #: why the last plot was not drawn whole, for a replay to ask; "" if it was
        self._failure = ""

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Set up any local connections between the subordinate view and model
        """
        self.view.plot_requested.connect(self.plot_conditioning)
        self.view.channels_requested.connect(self.request_channels)
        self.model.run_finished.connect(self.on_run_finished)

    # public API
    @log(logger=logger)
    @Slot(str, list, float, float, float, float, float, bool)
    @register_action(
        "plot_conditioning",
        kind="view",
        figure="plot",
        skip_on_false=True,
        plugin_args=("loader",),
    )
    def plot_conditioning(
        self,
        loader: str,
        channels: List[int],
        fit_start: float,
        fit_end: float,
        good_noise: float,
        decent_noise: float,
        psd_axis_min: float,
        show_bands: bool,
    ) -> bool:
        """
        Plot pore size and 1 Hz noise against cycle for some channels of an experiment.

        Refused, and not recorded, when the experiment is not available, no channel is
        asked for, the fit range or the thresholds are out of order, or the experiment is
        still being computed for an earlier plot. Otherwise the 1 Hz values not yet kept
        are computed in the background and the plot is drawn when they are done.

        A plot whose 1 Hz noise is not computed for every channel is still drawn, since the
        pore sizes come from the experiment, but is not kept in the tab's history; in a
        replay it fails the step (:py:meth:`background_step_failure`). A plot of values
        already kept that cannot read the experiment is refused.

        :param loader: the experiment's plugin key
        :type loader: str
        :param channels: the channels to draw, numbered from 0
        :type channels: List[int]
        :param fit_start: lower end of the 1/f fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the 1/f fit range, Hz
        :type fit_end: float
        :param good_noise: 1 Hz noise below this is good, pA^2/Hz
        :type good_noise: float
        :param decent_noise: 1 Hz noise below this is decent, pA^2/Hz
        :type decent_noise: float
        :param psd_axis_min: the lower end of the 1 Hz noise axes, pA^2/Hz
        :type psd_axis_min: float
        :param show_bands: colour each PSD's cycle by its noise
        :type show_bands: bool
        :return: True if the plot was drawn or started, False if it was refused or could
            not be drawn
        :rtype: bool
        """
        self._failure = ""
        refusal = self._refusal(
            loader, channels, fit_start, fit_end, good_noise, decent_noise, psd_axis_min
        )
        if refusal:
            self.add_text_to_display.emit(refusal, self.__class__.__name__)
            return False
        try:
            self.model.forget_stale_results(loader)
        except Exception as e:
            self.add_text_to_display.emit(
                f"Unable to read the experiment {loader}: {e}", self.__class__.__name__
            )
            return False
        self._waiting[loader] = {
            "loader": loader,
            "channels": list(channels),
            "fit_start": fit_start,
            "fit_end": fit_end,
            "good_noise": good_noise,
            "decent_noise": decent_noise,
            "psd_axis_min": psd_axis_min,
            "show_bands": show_bands,
        }
        missing = self.model.missing_channels(loader, channels, fit_start, fit_end)
        if not missing:
            # Drawn before this call returns, so before it is recorded: a plot that cannot
            # be drawn is refused here rather than dropped from the history afterwards.
            return self._draw(loader, recorded=False)
        for channel in missing:
            self.model.set_generator(
                self.model.one_hz_run(loader, channel, fit_start, fit_end),
                channel,
                loader,
                "MetaConditioningLoader",
            )
        self.add_text_to_display.emit(
            f"Computing the 1 Hz noise of {len(missing)} channel(s) of {loader}",
            self.__class__.__name__,
        )
        self.model.run_generators(loader)
        return True

    @log(logger=logger)
    @Slot(str)
    def request_channels(self, loader: str) -> None:
        """
        Give the View the chosen experiment's channels for its panel.

        :param loader: the experiment's plugin key
        :type loader: str
        """
        try:
            channels = self.model.call("MetaConditioningLoader", loader, "get_channels")
        except Exception as e:
            self.add_text_to_display.emit(
                f"Unable to read the channels of {loader}: {e}", self.__class__.__name__
            )
            return
        self.view.set_channels(channels)

    @log(logger=logger)
    @Slot(int, str)
    def on_run_finished(self, channel: int, key: str) -> None:
        """
        Draw the waiting plot once the last of its experiment's workers has ended.

        :param channel: the channel whose worker ended
        :type channel: int
        :param key: the experiment's plugin key
        :type key: str
        """
        if key in self._waiting and not self.model.is_running(key):
            self._draw(key, recorded=True)

    @log(logger=logger)
    @override
    def background_step_failure(self) -> str:
        """
        Why the replayed plot was not drawn whole: the experiment could not be read, or a
        channel's 1 Hz noise did not finish.

        :return: the status-panel line that said so, or "" if the plot was drawn whole
        :rtype: str
        """
        return self._failure

    # private API
    @log(logger=logger)
    def _refusal(
        self,
        loader: str,
        channels: List[int],
        fit_start: float,
        fit_end: float,
        good_noise: float,
        decent_noise: float,
        psd_axis_min: float,
    ) -> str:
        """
        Why a plot cannot be drawn, or "" if it can.

        :param loader: the experiment's plugin key
        :type loader: str
        :param channels: the channels asked for
        :type channels: List[int]
        :param fit_start: lower end of the fit range, Hz
        :type fit_start: float
        :param fit_end: upper end of the fit range, Hz
        :type fit_end: float
        :param good_noise: the good threshold
        :type good_noise: float
        :param decent_noise: the decent threshold
        :type decent_noise: float
        :param psd_axis_min: the lower end of the noise axes
        :type psd_axis_min: float
        :return: the reason, or ""
        :rtype: str
        """
        if loader not in self.model.available_plugins.get("MetaConditioningLoader", []):
            return "Add or choose a conditioning experiment to plot"
        if not channels:
            return "Choose at least one channel to plot"
        if not 0 < fit_start < fit_end:
            return "The fit range needs 0 < start < end"
        if not 0 < good_noise < decent_noise:
            return "The noise thresholds need 0 < Good < Decent"
        if psd_axis_min <= 0:
            return "The noise axis minimum must be greater than 0"
        if self.model.is_running(loader):
            return f"{loader} is still being computed; plot again when it finishes"
        return ""

    @log(logger=logger)
    def _draw(self, loader: str, recorded: bool) -> bool:
        """
        Draw the plot waiting on this experiment, from the experiment and the kept results.

        Drawn without the noise of a channel whose computation did not finish.

        :param loader: the experiment's plugin key
        :type loader: str
        :param recorded: the click is already in the history, so one that fails is dropped
        :type recorded: bool
        :return: True if drawn whole
        :rtype: bool
        """
        request = self._waiting.pop(loader)
        for note in self.model.take_notes(loader):
            self.add_text_to_display.emit(note, self.__class__.__name__)
        try:
            data = self.model.plot_data(
                loader, request["channels"], request["fit_start"], request["fit_end"]
            )
        except Exception as e:
            self._not_drawn_whole(
                f"Unable to read the experiment {loader}: {e}", recorded
            )
            return False
        unfinished = self.model.missing_channels(
            loader, request["channels"], request["fit_start"], request["fit_end"]
        )
        if unfinished:
            self._not_drawn_whole(
                f"No 1 Hz noise for channel(s) {', '.join(map(str, unfinished))}: "
                f"their computation did not finish",
                recorded,
            )
        self.view.draw_conditioning(
            data,
            request["good_noise"],
            request["decent_noise"],
            request["psd_axis_min"],
            request["show_bands"],
        )
        return not unfinished

    @log(logger=logger)
    def _not_drawn_whole(self, reason: str, recorded: bool) -> None:
        """
        Say why the plot is not drawn whole: in a replay its step then fails; by hand it is not kept.

        :param reason: what went wrong, for the status panel
        :type reason: str
        :param recorded: the click is already in the history, so it is dropped from it
        :type recorded: bool
        """
        if self.is_replaying():
            self._failure = reason
            self.add_text_to_display.emit(reason, self.__class__.__name__)
            return
        self.add_text_to_display.emit(
            f"{reason}, so this plot is not saved in the tab's history",
            self.__class__.__name__,
        )
        if recorded:
            self.discard_last_tab_action()
