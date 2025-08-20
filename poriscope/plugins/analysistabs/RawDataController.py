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

from PySide6.QtCore import Slot
from typing_extensions import override

from poriscope.plugins.analysistabs.RawDataModel import RawDataModel
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class RawDataController(MetaController):
    """
    Subclass of MetaController for managing raw data view-model logic.

    Handles raw data plotting and PSD logic.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self):
        self.view = RawDataView()
        self.model = RawDataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self):
        self.view.calculate_psd.connect(self.calculate_psd)

    @log(logger=logger)
    @Slot(list, float)
    def calculate_psd(self, psd_data, samplerate):
        """
        Calculate the Power Spectral Density (PSD) from the provided signal data and update the view.

        :param psd_data: List of time-domain signal arrays for which PSD will be computed.
        :type psd_data: list
        :param samplerate: Sampling rate of the signal in Hz.
        :type samplerate: float
        """
        Pxx_list, rms_list, frequency = self.model.calculate_psd(psd_data, samplerate)
        self.view.set_psd(Pxx_list, rms_list, frequency)

    @log(logger=logger)
    @Slot(dict)
    def update_available_plugins(self, available_plugins: dict) -> None:
        self.logger.debug(
            f"Controller received available plugins update: {available_plugins}"
        )
        self.model.update_available_plugins(available_plugins)
        self.view.update_available_plugins(available_plugins)

    @log(logger=logger)
    def set_event_filter(self, data_filter):
        """
        Set the data filter function used for processing events.

        :param data_filter: A callable used to filter or preprocess the data.
        :type data_filter: Callable
        """
        self.view.set_data_filter_function(data_filter)

    @log(logger=logger)
    def update_plot_data(self, data):
        self.view.update_plot_data(data)

    @log(logger=logger)
    def update_plot_samplerate(self, samplerate):
        """
        Set the sampling rate to be used for time axis conversion in the plot.

        :param samplerate: Sampling rate in Hz.
        :type samplerate: float
        """
        self.view.update_plot_samplerate(samplerate)

    @log(logger=logger)
    @Slot(dict)
    def update_channels(self, num_channels):
        """
        Update the view with the current number of channels available or selected.

        :param num_channels: Dictionary containing channel information.
        :type num_channels: dict
        """
        self.view.update_channels(num_channels)

    @log(logger=logger)
    def update_timer_channels(self, channels):
        """
        Update the view with the list of channels for timer-based processing.

        :param channels: List or dictionary of channel identifiers.
        :type channels: list or dict
        """
        self.view.update_timer_channels(channels)

    @log(logger=logger)
    def set_num_events_allowed(self, num_events):
        """
        Set the maximum number of events allowed to be processed or visualized.

        :param num_events: Maximum number of events.
        :type num_events: int
        """
        self.view.set_num_events_allowed(num_events)

    @log(logger=logger)
    def set_eventfinding_status(self, status):
        """
        Set the current status of the event finding process in the view.

        :param status: Boolean indicating if event finding was successful.
        :type status: bool
        """
        self.view.set_eventfinding_status(status)

    @log(logger=logger)
    def relay_eventfinding_status(self, status):
        """
        Relay the event finding status to the view for UI updates.

        :param status: Boolean indicating the result of the event finding operation.
        :type status: bool
        """
        self.view.set_eventfinding_status(status)
