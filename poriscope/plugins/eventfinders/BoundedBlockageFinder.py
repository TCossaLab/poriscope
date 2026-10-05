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
from typing import Any, Dict, List, Optional, override

import numpy as np
import numpy.typing as npt

from poriscope.plugins.eventfinders.ClassicBlockageFinder import ClassicBlockageFinder
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class BoundedBlockageFinder(ClassicBlockageFinder):
    """
    Subclass of ClassicBlockageFinder that adds baseline range constraints for event detection.

    This event finder enforces a user-defined minimum and maximum baseline range
    and refines the Gaussian baseline fitting procedure accordingly. It filters data
    outside the specified baseline window and raises errors if the computed baseline
    falls outside those bounds.
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
        Declare the settings this event finder exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaEventFinder.MetaEventFinder.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The ``super()`` call supplies the mandatory ``"MetaReader"`` key, which is how
        this plugin is wired to its data source, and ``"Threshold"``, which the base
        declares without a unit because the base loop reads it; this plugin sets
        the unit.

        The keys this plugin adds or configures:

        - ``Threshold`` (pA) - how far below the fitted baseline the signal must fall
          for an event to start.
        - ``Min Duration`` / ``Max Duration`` (us) - events outside this range are
          rejected.
        - ``Min Separation`` (us) - two events closer together than this are rejected
          rather than merged.
        - ``Min Baseline`` / ``Max Baseline`` (pA) - the window the baseline fit is
          restricted to. Samples outside it never reach the histogram, and a fit whose
          mean lands outside it is refused rather than reported. This is what separates
          this finder from ``ClassicBlockageFinder``, which takes its range from the
          chunk's own extremes.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Min Baseline"] = {"Type": float, "Value": None, "Units": "pA"}
        settings["Max Baseline"] = {"Type": float, "Value": None, "Units": "pA"}
        return settings

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        super()._validate_settings(settings)
        if settings["Min Baseline"]["Value"] >= settings["Max Baseline"]["Value"]:
            raise ValueError(
                "Min Baseline must be smaller (more negative) than Max Baseline, "
            )

    @log(logger=logger)
    @override
    def _get_baseline_stats(self, data: npt.NDArray[np.float64]) -> tuple[float, float]:
        """
        Get the local mean and standard deviation for a chunk of data.

        Unlike :ref:`ClassicBlockageFinder`, the range is the configured ``Min Baseline``
        to ``Max Baseline`` rather than the chunk's own extremes, so samples outside it
        never reach the fit, and a fit that lands outside it is refused rather than
        reported.

        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Tuple of mean and standard deviation.
        :rtype: tuple[float, float]
        :raises ValueError: if no data is found within the configured baseline range, if a baseline histogram width cannot be estimated, or if the fitted baseline falls outside the configured Min/Max Baseline bounds
        """
        bottom = self.settings["Min Baseline"]["Value"]
        top = self.settings["Max Baseline"]["Value"]
        data = data[(data > bottom) & (data < top)]
        if len(data) == 0:
            raise ValueError("No data found in range")

        mean, std = self._fit_baseline_histogram(data, bottom, top)
        if mean < bottom or mean > top:
            raise ValueError("Baseline out of bounds")
        return mean, std
