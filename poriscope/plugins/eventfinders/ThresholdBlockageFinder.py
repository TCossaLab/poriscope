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
# Philipp Mensing


import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import numpy.typing as npt
from typing_extensions import override

from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class ThresholdBlockageFinder(ClassicBlockageFinder):
    """
    Subclass of ClassicBlockageFinder that imposes much tighter bounds on the start and end time flagged in the output.

    This event finder calls the start of the event at the first threshold crossing, and the end of the event at the corresponding threshold crossing at the end through backtracking.
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
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.
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
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Threshold"]["Units"] = "σ"
        return settings

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _find_events_in_chunk(
        self,
        data: npt.NDArray[np.float64],
        mean: float,
        std: float,
        offset: int,
        entry_state: bool = False,
        first_chunk: bool = False,
    ) -> Tuple[List[int], List[int], bool]:
        """
        Find the start and end points of events in the provided chunk of data and returns them as separate lists,
        along with a boolean indicating whether or not the chunk ended in the middle of an event.
        Should backtrack data to the baseline, since padding logic will assume that it can use data right up to the start and end found as baseline by default

        :param data: Chunk of timeseries data to analyze. Assume it is rectified so that a blockage will always represent a reduction in absolute value.
        :type data: npt.NDArray[np.float64]
        :param mean: Mean of the baseline on the given chunk. Must be positive.
        :type mean: float
        :param std: Standard deviation of the baseline on the given chunk
        :type std: float
        :param offset: the index of the start of the chunk in the global dataset
        :type offset: int
        :param entry_state: Bool indicating whether we start in the middle of an event (True) or not (False)
        :type entry_state: bool
        :param first_chunk: Bool indicating whether this is the first chunk of data in the series to be analyzed
        :type first_chunk: bool
        :raises ValueError: If event_params are invalid.
        :return: Lists of event start and end indices, and boolean entry state.
        :rtype: Tuple[List[int], List[int], bool]
        """
        if np.sign(mean) < 0:
            raise ValueError("Data must be rectifed for event finding")

        data -= mean
        data /= std

        threshold = -self.settings["Threshold"]["Value"]
        hysteresis = 0
        event_starts = []
        event_ends = []

        if (
            data[0] < threshold and first_chunk and not entry_state
        ):  # do not count an event that straddles the start of the first chunk
            entry_state = True

        index = 0
        len_data = len(data)

        while index < len_data:
            if not entry_state:  # we are not in an event
                pos = int(np.argmax(data[index:] < threshold))
                if pos == 0 and not (data[index] < threshold):
                    break
                index += pos
                event_start = index
                entry_state = True
                event_starts.append(event_start + offset)
            else:
                pos = int(np.argmax(data[index:] > hysteresis))
                if pos == 0 and not (data[index] > hysteresis):
                    break
                index += pos
                event_end = index
                while data[event_end] > threshold and event_end > 0:
                    event_end -= 1
                event_ends.append(event_end + offset)
                entry_state = False
        return event_starts, event_ends, entry_state
