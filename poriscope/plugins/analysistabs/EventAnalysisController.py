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
# Alejandra Carolina González González
# Kyle Briggs


import logging
from typing import Any, Callable, List, Optional, Tuple, override

from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.EventAnalysisModel import EventAnalysisModel
from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventTabController import MetaEventTabController


@inherit_docstrings
class EventAnalysisController(MetaEventTabController):
    """
    Subclass of MetaEventTabController for for managing event analysis view-model logic.

    Connects the EventAnalysisModel and EventAnalysisView.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        self.view = EventAnalysisView()
        self.model = EventAnalysisModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        self.view.loader_channels_requested.connect(self.request_loader_channels)
        self.view.write_requested.connect(self.write_events)
        self.view.fitting_statuses_requested.connect(self.request_fitting_statuses)
        self.view.fitting_requested.connect(self.start_fitting)

    @log(logger=logger)
    @Slot(str, list, str)
    def request_fitting_statuses(
        self, eventfitter: str, channels: List[int], data_filter: str
    ) -> None:
        """
        Ask the fitter which channels it has already fitted, for the View to confirm.

        Step 4a's first half of the fitting launch, and the analogue of
        ``RawDataController.request_eventfinding_statuses``. The View used to emit this
        per channel inside its own loop and read the answer back off
        ``self.eventfitting_status``, which nothing cleared - so a dispatch the bus
        swallowed left the *previous* channel's fitted-ness in place and the "start over?"
        prompt was shown, or skipped, for the wrong channel.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param channels: the channels the user asked to fit
        :type channels: List[int]
        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :return: None
        :rtype: None
        """
        statuses: List[Tuple[int, bool]] = []
        for channel in channels:
            try:
                fitted = self.model.call(
                    "MetaEventFitter", eventfitter, "get_eventfitting_status", channel
                )
            except Exception as e:
                self.logger.error(
                    f"Unable to read fitting status for channel {channel}: {repr(e)}"
                )
                self.add_text_to_display.emit(
                    f"Unable to read the state of channel {channel}, so it was skipped: {e}",
                    self.__class__.__name__,
                )
                continue
            statuses.append((channel, bool(fitted)))
        self.view.set_fitting_statuses(eventfitter, statuses, data_filter)

    @log(logger=logger)
    @Slot(str, list, str)
    def start_fitting(
        self, eventfitter: str, channels: List[int], data_filter: str
    ) -> None:
        """
        Fit the approved channels and run the resulting generators.

        ``silent`` and ``indices`` are passed explicitly as False and None because the
        View always did, even though both match their defaults - keeping them makes the
        move visibly behaviour-preserving rather than relying on the defaults not
        changing (rule 42).

        A channel that cannot be launched is reported and skipped, and the ones that did
        register still run, for the same reason as ``write_events``.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param channels: the channels the user approved
        :type channels: List[int]
        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :return: None
        :rtype: None
        """
        callable_filter = self._resolve_callable_filter(data_filter)
        for channel in channels:
            try:
                generator = self.model.call(
                    "MetaEventFitter",
                    eventfitter,
                    "fit_events",
                    channel,
                    False,
                    callable_filter,
                    None,
                )
            except Exception as e:
                self.logger.error(
                    f"Unable to set up event fitter generator {eventfitter} for channel {channel}: {repr(e)}"
                )
                self.add_text_to_display.emit(
                    f"Unable to start fitting on channel {channel}: {e}",
                    self.__class__.__name__,
                )
                continue
            self.model.set_generator(generator, channel, eventfitter, "MetaEventFitter")
        self.model.run_generators(eventfitter)

    @log(logger=logger)
    @Slot(str)
    def request_loader_channels(self, loader: str) -> None:
        """
        Fetch an event loader's channel list and hand it to the View.

        Step 4a, and the direct analogue of ``RawDataController.request_reader_channels``:
        the same conversion against ``MetaEventLoader`` rather than ``MetaReader``. A
        loader that cannot be read leaves the channel combobox alone rather than clearing
        it - an empty combobox reads as "this loader has no channels", which is a
        different and more alarming thing than "this loader could not be read".

        :param loader: the event loader plugin's key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            channels = self.model.call("MetaEventLoader", loader, "get_channels")
        except Exception as e:
            self.logger.error(f"Unable to read channels from {loader}: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to read channels from {loader}: {e}", self.__class__.__name__
            )
            return
        self.view.update_channels(channels)

    @log(logger=logger)
    @Slot(str, list)
    def write_events(self, writer: str, channels: List[int]) -> None:
        """
        Hand each channel's fitted events to a database writer and run the generators.

        The analogue of ``RawDataController.commit_events``, against
        ``MetaDatabaseWriter.write_events``. Like that one it was never an emit-then-read:
        the plugin returns a generator and the bus passed it straight into
        ``set_generator`` as an argument, so there was no attribute to park it on and no
        stale value to inherit.

        The same deliberate behaviour change applies. The View wrapped the whole loop in
        ``except (IndexError, ValueError)`` and skipped ``run_generators`` entirely if it
        fired - a guard that could not catch a plugin failure, because the bus swallowed
        those first. Now that ``call()`` raises, a channel that cannot be written is
        reported and skipped and the rest still run, rather than an arbitrary writer
        exception escaping a Qt slot.

        :param writer: the database writer plugin's key
        :type writer: str
        :param channels: the channels whose events are being written
        :type channels: List[int]
        :return: None
        :rtype: None
        """
        for channel in channels:
            try:
                generator = self.model.call(
                    "MetaDatabaseWriter", writer, "write_events", channel
                )
            except Exception as e:
                self.logger.error(
                    f"Unable to set up database writer {writer} for channel {channel}: {repr(e)}"
                )
                self.add_text_to_display.emit(
                    f"Unable to write channel {channel} with {writer}: {e}",
                    self.__class__.__name__,
                )
                continue
            self.model.set_generator(generator, channel, writer, "MetaDatabaseWriter")
        self.model.run_generators(writer)

    @log(logger=logger)
    def set_event_filter(self, data_filter: Callable) -> None:
        """
        Set the callable function used to filter event data.

        :param data_filter: A function that applies filtering logic to event data.
        :type data_filter: Callable
        """
        self.view.set_data_filter_function(data_filter)

    @log(logger=logger)
    def set_eventfitting_status(self, status: bool) -> None:
        """
        Set the current status of the event fitting process in the view.

        :param status: Boolean indicating if event fitting was successful.
        :type status: bool
        """
        self.view.set_eventfitting_status(status)

    @log(logger=logger)
    def update_plot_data(self, data: Optional[Any] = None) -> None:
        """
        Update the view with new plot data.

        :param data: Optional data to be plotted (e.g., event traces or fitted results).
        :type data: Optional[Any]
        """
        self.view.update_plot_data(data)

    @log(logger=logger)
    def update_features(
        self,
        vertical: Optional[List[float]] = None,
        horizontal: Optional[List[float]] = None,
        points: Optional[List[Tuple[float, float]]] = None,
        vlabels: Optional[List[str]] = None,
        hlabels: Optional[List[str]] = None,
        plabels: Optional[List[str]] = None,
    ) -> None:
        """
        Update the plot with visual annotations including vertical lines, horizontal lines, and point markers.

        Validates that each visual feature has a corresponding label (or explicit None) if labels are provided.

        :param vertical: Vertical line positions for the event being plotted.
        :type vertical: Optional[List[float]]
        :param horizontal: Horizontal line positions for the event being plotted.
        :type horizontal: Optional[List[float]]
        :param points: (x, y) point coordinates for the event being plotted.
        :type points: Optional[List[Tuple[float, float]]]
        :param vlabels: Labels for the vertical lines.
        :type vlabels: Optional[List[str]]
        :param hlabels: Labels for the horizontal lines.
        :type hlabels: Optional[List[str]]
        :param plabels: Labels for the point markers.
        :type plabels: Optional[List[str]]
        :raises ValueError: If a label list is provided and its length does not match the corresponding feature list.
        """
        if (
            vertical is not None
            and vlabels is not None
            and len(vlabels) != len(vertical)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every vertical line feature, or no labels at all"
            )
        if (
            horizontal is not None
            and hlabels is not None
            and len(hlabels) != len(horizontal)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every horizontal line feature, or no labels at all"
            )
        if points is not None and plabels is not None and len(points) != len(plabels):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every point feature, or no labels at all"
            )
        self.view.update_plot_features(
            vertical, horizontal, points, vlabels, hlabels, plabels
        )

    @log(logger=logger)
    @Slot(list)
    def update_channels(self, channels: List[int]) -> None:
        """
        Update the view with the current number of channels available or selected.

        :param channels: List of channel identifiers.
        :type channels: List[int]
        """
        self.view.update_channels(channels)

    @log(logger=logger)
    def set_num_events_allowed(self, num_events: int) -> None:
        """
        Set the maximum number of events allowed for processing or display.

        :param num_events: Maximum number of events to handle.
        :type num_events: int
        """
        self.view.set_num_events_allowed(num_events)

    @log(logger=logger)
    def relay_eventfitting_status(self, status: bool) -> None:
        """
        Relay event fitting status to the view.

        :param status: Boolean indicating the success of event fitting.
        :type status: bool
        """
        self.view.set_eventfitting_status(status)
