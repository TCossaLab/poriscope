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


import ctypes
import logging
import os
from typing import Any, Dict

import numpy as np
import numpy.typing as npt
from numpy.ctypeslib import ndpointer
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaFilter import MetaFilter


@inherit_docstrings
class WaveletFilter(MetaFilter):
    """
    Subclass for defining a Wavelete filter to be applied to a dataset
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.
        Must be implemented by subclasses.

        :param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information for the given subclass.
        """
        if "Wavelet" not in settings.keys():
            raise ValueError(
                "Wavelet filters require the choice of wavelet to be specified from among {0}.".format(
                    self.wavelist
                )
            )
        wavelet = settings["Wavelet"]["Value"]
        if wavelet not in self.wavelist:
            raise ValueError("Wavelet must be one of {0}".format(self.wavelist))

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
        padlen = 100
        data = np.pad(data, padlen, mode="edge")
        wavelet = self.settings["Wavelet"]["Value"].encode("utf-8")
        self.fun(data, len(data), wavelet)
        return data[padlen:-padlen]

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
            "Wavelet": {"Type": str, "Value": "bior1.5", "Options": self.wavelist}
        }
        return settings

    @log(logger=logger)
    @override
    def _finalize_initialization(self):
        """
        Apply the provided filter paramters and intialize any internal structures needed by self.apply_filter().
        Should Raise if initialization fails, but corner cases should be handled by _validate_settings already
        """
        dll_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "poriscope",
                "cdlls",
                "wavelet",
                "dist",
                "wavelet.dll",
            )
        )

        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(os.path.dirname(dll_path))

        wavelib = ctypes.cdll.LoadLibrary(dll_path)
        self.fun = wavelib.filter_signal_wt
        self.fun.restype = None
        self.fun.argtypes = [
            ndpointer(ctypes.c_double, flags="C_CONTIGUOUS"),
            ctypes.c_int,
            ctypes.c_char_p,
        ]

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called after parent class initialization
        """
        self.wavelist = [
            "bior1.3",
            "bior1.5",
        ]  # list of supported wavelets, these are chosen to be useful to nanopore signals
