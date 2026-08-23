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
from typing import Any, Dict, List, Optional, Type, Union

import numpy as np
import numpy.typing as npt
from typing_extensions import override

from poriscope.plugins.eventfitters.CUSUM import CUSUM, Numeric
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
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
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
        :rtype: Dict[str, Dict[str, Any]]
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
        self,
        data: npt.NDArray[np.float64],
        samplerate: float,
        baseline_mean: Optional[float],
        baseline_std: Optional[float],
        sublevel_metadata: Dict[str, List[Numeric]],
    ) -> Dict[str, Union[int, float, str, bool]]:
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
        :rtype: Dict[str, Union[int, float, str, bool]]
        :raises ValueError: if baseline_mean is not provided, since intra-event thresholds cannot be computed without it
        """
        event_metadata = super()._populate_event_metadata(
            data, samplerate, baseline_mean, baseline_std, sublevel_metadata
        )

        if baseline_mean is None:
            raise ValueError(
                "IntraCUSUM requires that baseline_mean be reported and is unable to compute intra-event thresholds without it"
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
    def _define_event_metadata_types(
        self,
    ) -> Dict[str, Type[Union[int, float, str, bool]]]:
        """
        Build a dict of metadata along with associated datatypes for use by the database writer downstream.
        Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting. Options for dtypes are int, float, str, bool

        :return: a dict of metadata keys and associated base dtypes
        :rtype: Dict[str, Type[Union[int, float, str, bool]]]
        """
        metadata_types = super()._define_event_metadata_types()
        metadata_types["threshold_crossings"] = int
        return metadata_types

    @log(logger=logger)
    @override
    def _define_event_metadata_units(self) -> Dict[str, Optional[str]]:
        """
        Build a dict of metadata units, or None if unitless. Keys must match columns defined in _populate_event_metadata()
        All of this metadata must be populated during fitting.

        :return: a dict of metadata keys and associated units
        :rtype: Dict[str, Optional[str]]
        """
        metadata_units = super()._define_event_metadata_units()
        metadata_units["threshold_crossings"] = ""
        return metadata_units
