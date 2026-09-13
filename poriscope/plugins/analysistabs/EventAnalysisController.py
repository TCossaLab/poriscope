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
        self.view.event_plot_requested.connect(self.load_event_plot)

    @log(logger=logger)
    @Slot(str, str, int, list, str, bool)
    def load_event_plot(
        self,
        loader: str,
        eventfitter: str,
        channel: int,
        events: List[int],
        data_filter: str,
        raw: bool,
    ) -> None:
        """
        Load the selected events, their raw traces and their fits, ready to plot.

        Step 4a's largest single conversion: eight bus round trips in one 243-line View
        method become eight calls here, and the assembly that turned their answers into
        plot arguments comes with them. It is pure data marshalling - no Qt and no
        matplotlib - so it belongs on this side; ``_update_event_plot`` stays in the View.

        **The alignment this builds is the load-bearing part.** ``event_data`` and
        ``labels`` take one to three entries per event - the data, then optionally the raw
        trace, then optionally the fit - while the six feature lists take exactly *one*
        placeholder per event, and an event's features are written to its own placeholder.
        So ``event_data`` is routinely longer than ``vertical_lines``, and ``num_events``
        counts events rather than traces. Getting that wrong attaches a fit's features to
        another event's subplot, which no gate would notice.

        **Three different unpacking rules, which the bus used to apply implicitly** from
        each callee's declared return type. ``load_event`` returns a dict whose ``data``
        key is the samples; ``get_fitted_event`` returns a bare array and must not be
        unwrapped; ``get_plot_features`` returns a six-tuple in the order
        (vertical, horizontal, points, vlabels, hlabels, plabels). All three are explicit
        here.

        **One call hoisted.** ``get_eventfitting_status`` takes only the channel, so the
        View asking it once per *event* asked the same question N times. It is asked once
        per request now, as the samplerate was on RawData's trace path.

        :param loader: the event loader plugin's key
        :type loader: str
        :param eventfitter: the event fitter plugin's key, or "No Event Fitter"
        :type eventfitter: str
        :param channel: the single channel whose events are being plotted
        :type channel: int
        :param events: the event indices the user selected
        :type events: List[int]
        :param data_filter: the filter plugin's key, or "" for no filtering
        :type data_filter: str
        :param raw: whether to overlay each event's unfiltered trace
        :type raw: bool
        :return: None
        :rtype: None
        """
        try:
            num_available = self.model.call(
                "MetaEventLoader", loader, "get_num_events", channel
            )
        except Exception as e:
            self.logger.error(
                f"Unable to read the event count for channel {channel}: {repr(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to read the event count for channel {channel}: {e}",
                self.__class__.__name__,
            )
            return

        if not events:
            return

        out_of_range = [event for event in events if event >= num_available]
        events = [event for event in events if event < num_available]
        if out_of_range:
            self.logger.info(
                f"Some event indices were out of bounds, truncating indices above {num_available - 1}"
            )
            label = "event" if len(out_of_range) == 1 else "events"
            indices = ", ".join(str(event) for event in out_of_range)
            self.add_text_to_display.emit(
                f"Channel {channel} holds {num_available} events (0-{num_available - 1}), "
                f"so {label} {indices} could not be plotted",
                self.__class__.__name__,
            )
        if not events:
            return

        callable_filter = self._resolve_callable_filter(data_filter)
        self.view.update_plot_samplerate(self._loader_samplerate(loader, channel))

        fitting_done = False
        if eventfitter != "No Event Fitter":
            fitting_done = self._fitting_is_done(eventfitter, channel)

        event_data: List[Any] = []
        labels: List[str] = []
        # One entry per surviving event; each is that event's whole feature list, or
        # None where the fitter supplied none.
        vertical_lines: List[Optional[List[float]]] = []
        horizontal_lines: List[Optional[List[float]]] = []
        points: List[Optional[List[Tuple[float, float]]]] = []
        vlabels: List[Optional[List[str]]] = []
        hlabels: List[Optional[List[str]]] = []
        plabels: List[Optional[List[str]]] = []
        num_events = 0

        for event in events:
            payload = self._load_one_event(loader, channel, event, callable_filter)
            if payload is None:
                self.logger.warning(f"No data loaded for event {event}, skipping")
                continue

            event_data.append(payload)
            labels.append(f"Event {event} Data")
            vertical_lines.append(None)
            horizontal_lines.append(None)
            points.append(None)
            vlabels.append(None)
            hlabels.append(None)
            plabels.append(None)
            num_events += 1

            if raw and callable_filter is not None:
                unfiltered = self._load_one_event(loader, channel, event, None)
                if unfiltered is not None:
                    # Shares this event's subplot, so it takes no new placeholder.
                    event_data.append(unfiltered)
                    labels.append(f"Event {event} Raw")

            if not fitting_done:
                continue

            fit = self._load_one_fit(eventfitter, channel, event)
            if fit is not None:
                event_data.append(fit)
                labels.append(f"Event {event} Fit")

            supplied = self._load_one_feature_set(eventfitter, channel, event)
            if supplied is not None:
                (
                    vertical_lines[-1],
                    horizontal_lines[-1],
                    points[-1],
                    vlabels[-1],
                    hlabels[-1],
                    plabels[-1],
                ) = supplied

        self.view.set_event_plot_data(
            event_data,
            labels,
            num_events,
            vertical_lines,
            horizontal_lines,
            points,
            vlabels,
            hlabels,
            plabels,
            raw,
        )

    @log(logger=logger)
    def _loader_samplerate(self, loader: str, channel: int) -> float:
        """
        The loader's samplerate for a channel, or 1 so the axis falls back to indices.

        Note this takes the channel, unlike the event *finder*'s no-argument version -
        the two are easy to conflate when converting both tabs.

        :param loader: the event loader plugin's key
        :type loader: str
        :param channel: the channel being plotted
        :type channel: int
        :return: the samplerate in Hz, or 1 if it could not be read
        :rtype: float
        """
        try:
            samplerate: float = self.model.call(
                "MetaEventLoader", loader, "get_samplerate", channel
            )
        except Exception:
            self.logger.warning(
                "Unable to get samplerate, time axis will indicate raw data index"
            )
            return 1
        return samplerate

    @log(logger=logger)
    def _fitting_is_done(self, eventfitter: str, channel: int) -> bool:
        """
        Whether this channel has been fitted, which gates the fit and feature overlays.

        Asked once per request rather than once per event: it takes only the channel, so
        the View was asking the same question N times.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param channel: the channel being plotted
        :type channel: int
        :return: True if the channel has been fitted
        :rtype: bool
        """
        try:
            return bool(
                self.model.call(
                    "MetaEventFitter", eventfitter, "get_eventfitting_status", channel
                )
            )
        except Exception as e:
            self.logger.error(
                f"Unable to read fitting status for channel {channel}: {repr(e)}"
            )
            return False

    @log(logger=logger)
    def _load_one_event(
        self,
        loader: str,
        channel: int,
        event: int,
        data_filter: Optional[Callable],
    ) -> Optional[Any]:
        """
        One event's samples, unwrapped from the dict the loader returns.

        ``load_event`` declares ``-> Dict[...]`` and the samples are under ``data``; the
        bus passed the whole dict to ``update_plot_data``, which did the unwrap. It is
        explicit here.

        :param loader: the event loader plugin's key
        :type loader: str
        :param channel: the channel being plotted
        :type channel: int
        :param event: the event index
        :type event: int
        :param data_filter: the callable to filter with, or None for the raw trace
        :type data_filter: Optional[Callable]
        :return: the samples, or None if the event could not be loaded
        :rtype: Optional[Any]
        """
        try:
            payload = self.model.call(
                "MetaEventLoader", loader, "load_event", channel, event, data_filter
            )
        except Exception as e:
            self.logger.error(
                f"Unable to retrieve requested data for event {event}: {repr(e)}"
            )
            return None
        if payload is None:
            return None
        return payload["data"] if isinstance(payload, dict) else payload

    @log(logger=logger)
    def _load_one_fit(
        self, eventfitter: str, channel: int, event: int
    ) -> Optional[Any]:
        """
        One event's fitted trace, or None where there is none to draw.

        ``get_fitted_event`` declares ``-> Optional[NDArray]``, so unlike ``load_event``
        its answer is the samples already and must not be unwrapped.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param channel: the channel being plotted
        :type channel: int
        :param event: the event index
        :type event: int
        :return: the fitted samples, or None
        :rtype: Optional[Any]
        """
        try:
            return self.model.call(
                "MetaEventFitter", eventfitter, "get_fitted_event", channel, event
            )
        except Exception as e:
            self.logger.error(
                f"Fit for event {event} could not be loaded in channel {channel}, skipping: {e}"
            )
            return None

    @log(logger=logger)
    def _load_one_feature_set(
        self, eventfitter: str, channel: int, event: int
    ) -> Optional[Tuple[Any, Any, Any, Any, Any, Any]]:
        """
        One event's feature overlays, in the order the fitter declares them.

        ``get_plot_features`` declares a six-tuple of
        (vertical, horizontal, points, vlabels, hlabels, plabels), which the bus splatted
        across ``update_features``' six parameters. Returned whole here and unpacked by
        the caller into that event's placeholders.

        :param eventfitter: the event fitter plugin's key
        :type eventfitter: str
        :param channel: the channel being plotted
        :type channel: int
        :param event: the event index
        :type event: int
        :return: the six feature values, or None if they could not be read
        :rtype: Optional[Tuple[Any, Any, Any, Any, Any, Any]]
        """
        try:
            supplied = self.model.call(
                "MetaEventFitter", eventfitter, "get_plot_features", channel, event
            )
        except KeyError as e:
            self.logger.info(
                f"Event {event} not found in channel {channel} to get features, skipping: {e}"
            )
            return None
        except Exception as e:
            self.logger.error(
                f"An unexpected error occured while trying to overlay features on the event: {e}"
            )
            return None
        return supplied

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
