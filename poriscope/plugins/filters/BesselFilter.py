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
from typing import Any, Dict

import numpy as np
import numpy.typing as npt
from scipy.signal import bessel, filtfilt
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaFilter import MetaFilter


@inherit_docstrings
class BesselFilter(MetaFilter):
    """
    Subclass for defining a low-pass Bessel filter to be applied to a dataset
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the filter_params dict contains the correct information for use by the subclass.
        Must be implemented by subclasses.

        :param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information for the given subclass.
        """
        if "Cutoff" not in settings.keys():
            raise ValueError(
                "Bessel filters require the cutoff frequency in Hz to be specified"
            )
        if "Samplerate" not in settings.keys():
            raise ValueError(
                "Bessel filters require the sampling frequency in Hz to be specified"
            )
        if "Poles" not in settings.keys():
            raise ValueError(
                "Bessel filters require the number of poles to be provided as a positive, even integer between 2 and 10"
            )
        if (
            settings["Cutoff"]["Value"] >= settings["Samplerate"]["Value"] / 2.0
            or settings["Cutoff"]["Value"] <= 0
        ):
            raise ValueError(
                "Cutoff must be a positive number less than half the sampling rate"
            )
        if settings["Poles"]["Value"] > 10 or settings["Poles"]["Value"] < 0:
            raise ValueError("Poles must be a positive integer between 1 and 10")
        z, p, k = bessel(
            settings["Poles"]["Value"],
            2.0 * settings["Cutoff"]["Value"] / settings["Samplerate"]["Value"],
            output="zpk",
        )
        if any(np.absolute(p) >= 0.975):
            raise ValueError(
                "This filter is likely to be numerically unstable. Reduce the number of poles and/or increase the cutoff frequency and try again."
            )

    @log(logger=logger)
    @override
    def _apply_filter(self, data: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """
        Apply the specified filter to the data, callable only privately.
        Must be implemented by subclasses.

        :param data: The data to be filtered
        :type data: npt.NDArray[np.float64]
        :return: The filtered data
        :rtype: npt.NDArray[np.float64]
        """

        if len(data) <= 3 * self.order:
            self.logger.info(
                f"Filtering an array with only {len(data)} elements is not possible, this data chunk will not be filtered"
            )
            return data

        padlen = 10 * self.order
        before = np.median(data[: 3 * self.order])
        after = np.median(data[-3 * self.order :])
        data = np.pad(data, padlen, mode="constant", constant_values=(before, after))
        return filtfilt(self.b, self.a, data)[padlen:-padlen]

    # public API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def close_resources(self, channel=None):
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def reset_channel(self, channel=None):
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: int
        """
        pass

    @log(logger=logger)
    @override
    def get_empty_settings(self, globally_available_plugins=None, standalone=False):
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Dict[str, List[str]]
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Union[int, float, str, list[Union[int,float,str,None], None]]]]
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Cutoff": {
                "Type": float,
                "Value": None,
                "Min": 0,
                "Units": "Hz",
            },
            "Samplerate": {
                "Type": float,
                "Value": None,
                "Min": 0,
                "Units": "Hz",
            },
            "Poles": {
                "Type": int,
                "Value": 8,
                "Options": [2, 4, 6, 8, 10],
            },
        }
        return settings

    @log(logger=logger)
    @override
    def _finalize_initialization(self):
        """
        Apply the provided filter paramters and intialize any internal structures needed by self.apply_filter().
        Should Raise if initialization fails, but corner cases should be handled by _validate_settings already

        :raises ValueError: If invalid cutoff frequency or order are provided
        :raises RuntimeError: If calculation of filter coefficients fails
        """
        cutoff = self.settings["Cutoff"]["Value"]
        samplerate = self.settings["Samplerate"]["Value"]
        order = self.settings["Poles"]["Value"]
        Wn = 2 * cutoff / samplerate
        self.order = order
        self.b, self.a = bessel(order, Wn)
