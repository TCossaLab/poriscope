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

import logging

import numpy as np
from typing_extensions import override

from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class IntraCUSUM(CUSUM):
    """
    Abstract base class to analyze and flag the start and end times of regions
    of interest in a timeseries for further analysis.
    """

    logger = logging.getLogger(__name__)

    # public API, must be overridden by subclasses:
    @log(logger=logger)
    @override
    def get_empty_settings(self, globally_available_plugins=None, standalone=False):
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.
        EventFinder objects MUST include a MetaReader object in settings

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Mapping[str, List[str]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Mapping[str, Mapping[str, Union[int, float, str, list[Union[int,float,str,None], None]]]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)

        settings["Intraevent Threshold"] = {
            "Type": float,
            "Value": 0,
            "Min": 0,
            "Units": "pA",
        }
        settings["Intraevent Hysteresis"] = {
            "Type": float,
            "Value": 0,
            "Min": 0,
            "Units": "pA",
        }
        return settings

    @log(logger=logger)
    @override
    def _populate_event_metadata(
        self, data, samplerate, baseline_mean, baseline_std, sublevel_metadata
    ):
        """
        Assemble a list of metadata to save in the event database later. Note that keys 'start_time_s' and 'index' are already handled in the base class and should not be touched here.

        :param data: an array of data from which to extract the locations of sublevel transitions
        :type data: npt.NDArray[np.float64]
        :param samplerate: the sampling rate
        :type samplerate: float
        :param baseline_mean: the local mean value of the baseline current
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation of the baseline current
        :type baseline_std: Optional[float]
        :param sublevel_metadata: the dict of sublevel metadata built by self._populate_sublevel_metadata()
        :type sublevel_metadata: Mapping[str, List[Numeric]]

        :return: a dict of event metadata values
        :rtype: Mapping[str, float]
        """
        event_metadata = super()._populate_event_metadata(
            data, samplerate, baseline_mean, baseline_std, sublevel_metadata
        )

        sign = np.sign(baseline_mean)
        down_threshold = (
            sign * sublevel_metadata["sublevel_current"][0]
            - self.settings["Intraevent Threshold"]["Value"]
        )
        up_threshold = sign * sublevel_metadata["sublevel_current"][0] - (
            self.settings["Intraevent Threshold"]["Value"]
            - self.settings["Intraevent Hysteresis"]["Value"]
        )

        below_threshold = False

        event_metadata["threshold_crossings"] = 0
        for d in data:
            if below_threshold is False and sign * d < down_threshold:
                below_threshold = True
                event_metadata["threshold_crossings"] += 1
            elif below_threshold is True and sign * d > up_threshold:
                below_threshold = False
                event_metadata["threshold_crossings"] += 1

        return event_metadata

    @log(logger=logger)
    @override
    def _define_event_metadata_types(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Mapping[str, Union[int, float, str, bool]]
        """
        metadata_types = super()._define_event_metadata_types()
        metadata_types["threshold_crossings"] = int
        return metadata_types

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self):
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Mapping[str, Union[int, float, str, bool]]
        """
        metadata_units = super()._define_event_metadata_units()
        metadata_units["threshold_crossings"] = ""
        return metadata_units
