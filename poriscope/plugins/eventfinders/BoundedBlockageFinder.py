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
from fast_histogram import histogram1d
from scipy.stats import median_abs_deviation
from typing_extensions import override

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
        settings["Min Baseline"] = {"Type": float, "Value": None, "Units": "pA"}
        settings["Max Baseline"] = {"Type": float, "Value": None, "Units": "pA"}
        return settings

    @log(logger=logger)
    @override
    def _validate_settings(self, settings):
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
    def _get_baseline_stats(self, data):
        """
        Get the local amplitude, mean, and standard deviation for a chunk of data.


        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Tuple of mean and standard deviation.
        :rtype: tuple[float, float]
        """
        top = self.settings["Max Baseline"]["Value"]
        bottom = self.settings["Min Baseline"]["Value"]
        mask = (data > bottom) & (data < top)
        data = data[mask]
        if len(data) == 0:
            raise ValueError("No data found in range")

        median_abs_deviation(data)
        width = 2 * (top - bottom) / len(data) ** (1 / 3)
        bins = int((top - bottom) / width)
        hist = histogram1d(data, range=[bottom, top], bins=bins)
        centers = np.linspace(bottom, top, len(hist))
        max_index = np.argmax(hist)

        maxval = hist[max_index]
        # top_index: the first index where hist[i] <= maxval/5 starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= maxval / 5
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= maxval/5 going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= maxval / 5
            )
        except StopIteration:
            bottom_index = 0

        np.minimum(top_index - max_index, max_index - bottom_index)

        top = centers[top_index]
        bottom = centers[bottom_index]

        mask = (data > bottom) & (data < top)
        data = data[mask]
        if len(data) == 0:
            raise ValueError("No data found in range")

        width = 2 * (top - bottom) / len(data) ** (1 / 3)
        bins = int((top - bottom) / width)
        hist = histogram1d(data, range=[bottom, top], bins=bins)
        centers = np.linspace(bottom, top, len(hist))

        max_index = np.argmax(hist)
        maxval = hist[max_index]

        # top_index: the first index where hist[i] <= 0.6*maxval starting from max_index
        try:
            top_index = next(
                i for i in range(max_index, len(hist)) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            top_index = len(hist) - 1

        # bottom_index: the first index where hist[i] <= 0.6*maxval going backwards from max_index
        try:
            bottom_index = next(
                i for i in range(max_index, -1, -1) if hist[i] <= 0.6 * maxval
            )
        except StopIteration:
            bottom_index = 0

        std_index = (
            bottom_index
            if max_index - bottom_index < top_index - max_index
            else top_index
        )

        try:
            baseline_params = np.array(
                self._gaussian_fit(
                    hist,
                    centers,
                    centers[max_index],
                    np.absolute(centers[std_index] - centers[max_index]),
                )
            )
        except ValueError:
            raise
        mean = baseline_params[1]
        if (
            mean < self.settings["Min Baseline"]["Value"]
            or mean > self.settings["Max Baseline"]["Value"]
        ):
            raise ValueError("Baseline out of bounds")
        return baseline_params
