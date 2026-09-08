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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, override

from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.RawDataModel import RawDataModel
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventTabController import MetaEventTabController


@inherit_docstrings
class RawDataController(MetaEventTabController):
    """
    Subclass of MetaEventTabController for managing raw data view-model logic.

    Handles raw data plotting and PSD logic.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        self.view = RawDataView()
        self.model = RawDataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        self.view.calculate_psd.connect(self.calculate_psd)
        self.view.baseline_stats_requested.connect(self.compute_baseline_stats)
        self.view.reader_channels_requested.connect(self.request_reader_channels)

    @log(logger=logger)
    def request_reader_channels(self, reader: str) -> None:
        """
        Fetch a reader's channel list and hand it to the View.

        Step 4a: this replaces a ``global_signal`` round trip whose answer arrived seven
        hops later through a return function named by string. A reader that cannot be
        read leaves the channel combobox alone rather than clearing it - an empty
        combobox reads as "this reader has no channels", which is a different and more
        alarming thing than "this reader could not be read".

        :param reader: the reader plugin's key
        :type reader: str
        :return: None
        :rtype: None
        """
        try:
            channels = self.model.call("MetaReader", reader, "get_channels")
        except Exception as e:
            self.logger.error(f"Unable to read channels from {reader}: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to read channels from {reader}: {e}", self.__class__.__name__
            )
            return
        self.view.update_channels(channels)

    @log(logger=logger)
    def compute_baseline_stats(
        self, data: List[Any], channels: List[int], start: Any
    ) -> None:
        """
        Fit each channel's baseline and hand the results back for plotting.

        Decision B's command path, the same shape as calculate_psd below. Step 4c moved
        the fitting to RawDataModel; the View asks for it here and plots on the answer.

        A channel whose fit fails contributes None rather than aborting the plot, which
        is what the View did when it computed these itself - a flat or degenerate trace
        should still be drawn, just without its baseline band.

        The division by 1000 converts pA to nA, matching the scale update_plot draws on.
        It moved here with the call it belongs to.

        :param data: one array of samples per channel
        :type data: List[Any]
        :param channels: the channel identifiers, index-aligned with data
        :type channels: List[int]
        :param start: the start time the View is plotting from, passed straight through
        :type start: Any
        :return: None
        :rtype: None
        """
        stats: List[Optional[Tuple[float, float, float]]] = []
        for channel_data, channel in zip(data, channels, strict=True):
            try:
                stats.append(self.model.get_baseline_stats(channel_data / 1000))
            except ValueError as e:
                self.logger.warning(
                    f"Unable to compute baseline stats for channel {channel}: {e}"
                )
                stats.append(None)
        self.view.update_plot(data, channels, start, stats)

    @log(logger=logger)
    @Slot(list, float)
    def calculate_psd(self, psd_data: list, samplerate: float) -> None:
        """
        Calculate the Power Spectral Density (PSD) from the provided signal data and update the view.

        :param psd_data: List of time-domain signal arrays for which PSD will be computed.
        :type psd_data: list
        :param samplerate: Sampling rate of the signal in Hz.
        :type samplerate: float
        """
        Pxx_list, rms_list, frequency, kept_indices = self.model.calculate_psd(
            psd_data, samplerate
        )
        self.view.set_psd(Pxx_list, rms_list, frequency, kept_indices)

    @log(logger=logger)
    def set_event_filter(self, data_filter: Callable) -> None:
        """
        Set the data filter function used for processing events.

        :param data_filter: A callable used to filter or preprocess the data.
        :type data_filter: Callable
        """
        self.view.set_data_filter_function(data_filter)

    @log(logger=logger)
    def update_plot_data(self, data: Any) -> None:
        """
        Relay processed data to the view for plotting.

        :param data: Structured plot data.
        :type data: Any
        """
        self.view.update_plot_data(data)

    @log(logger=logger)
    @Slot(list)
    def update_channels(self, num_channels: List[int]) -> None:
        """
        Update the view with the current number of channels available or selected.

        :param num_channels: List of channel identifiers.
        :type num_channels: List[int]
        """
        self.view.update_channels(num_channels)

    @log(logger=logger)
    @override
    @Slot(dict)
    def update_available_plugins(self, available_plugins: dict) -> None:
        """
        Resolve every event finder's channels, then push the registry down as usual.

        Step 4a: ``RawDataView.update_available_plugins`` used to make one bus call per
        new event finder from inside this very push, reading the answer back off an
        attribute a callback had set. That is the emit-then-read pattern in its most
        awkward position - a synchronous round trip nested inside a method the Controller
        is already running - so the finders are resolved here and handed down as a
        ready-made map instead.

        **The channels go down before the names, and that ordering is deliberate.**
        Populating a combobox fires a selection change synchronously, which is what made
        the plugin-instance push order load-bearing earlier on this branch. Checked here
        rather than assumed: the event-finder combobox emits the action name
        ``parameter_changed``, which lands in ``_handle_other_actions`` and reaches
        nothing that reads ``analysis_time_limits``, so this order is defensive today
        rather than load-bearing. It costs nothing and it is the order that stays correct
        if a future handler does read that state.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: dict
        :return: None
        :rtype: None
        """
        self.view.register_eventfinder_channels(
            self._resolve_eventfinder_channels(
                available_plugins.get("MetaEventFinder", [])
            )
        )
        super().update_available_plugins(available_plugins)

    @log(logger=logger)
    def _resolve_eventfinder_channels(
        self, eventfinders: Sequence[str]
    ) -> Dict[str, Sequence[int]]:
        """
        Ask each event finder for its channels, skipping any that cannot answer.

        A finder that raises is left out of the returned map rather than mapped to an
        empty list, so the View can tell "no channels" from "did not answer" and leaves
        it unregistered for the next push to retry. Every finder is asked, not only the
        unregistered ones: this runs on plugin lifecycle events rather than per chunk,
        and letting the View own "which finders are new" keeps that state in one place.

        :param eventfinders: keys of the event finder plugins to query
        :type eventfinders: Sequence[str]
        :return: channels per finder, for the finders that answered
        :rtype: Dict[str, Sequence[int]]
        """
        resolved: Dict[str, Sequence[int]] = {}
        for finder in eventfinders:
            try:
                resolved[finder] = self.model.call(
                    "MetaEventFinder", finder, "get_channels"
                )
            except Exception as e:
                self.logger.error(
                    f"Could not get channels for {finder}, not registering it yet: {repr(e)}"
                )
        return resolved

    @log(logger=logger)
    def set_num_events_allowed(self, num_events: int) -> None:
        """
        Set the maximum number of events allowed to be processed or visualized.

        :param num_events: Maximum number of events.
        :type num_events: int
        """
        self.view.set_num_events_allowed(num_events)

    @log(logger=logger)
    def set_eventfinding_status(self, status: bool) -> None:
        """
        Set the current status of the event finding process in the view.

        :param status: Boolean indicating if event finding was successful.
        :type status: bool
        """
        self.view.set_eventfinding_status(status)

    @log(logger=logger)
    def relay_eventfinding_status(self, status: bool) -> None:
        """
        Relay the event finding status to the view for UI updates.

        :param status: Boolean indicating the result of the event finding operation.
        :type status: bool
        """
        self.view.set_eventfinding_status(status)
