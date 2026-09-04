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
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class EventAnalysisController(MetaController):
    """
    Subclass of MetaController for for managing event analysis view-model logic.

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
        pass

    @log(logger=logger)
    @Slot(dict)
    def update_available_plugins(self, available_plugins: dict) -> None:
        """
        Relay an updated dict of available plugin keys, keyed by metaclass, to both the model and the view.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: dict
        """
        self.logger.debug(
            f"Controller received available plugins update: {available_plugins}"
        )
        self.model.update_available_plugins(available_plugins)
        self.view.update_available_plugins(available_plugins)

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
    def update_plot_samplerate(self, samplerate: float) -> None:
        """
        Set the sampling rate to be used for time axis conversion in the plot.

        :param samplerate: Sampling rate in Hz.
        :type samplerate: float
        """
        self.view.update_plot_samplerate(samplerate)

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
