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
import importlib.resources
import logging
import os
import platform
import threading
from typing import Any, Dict, List, Optional

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
    # Process-wide, deliberately: see the comment in _apply_filter.
    _dll_lock = threading.Lock()

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
        # Filters are invoked as plain callables from within other plugins' own channel
        # loops rather than being dispatched through the channel-management system, so
        # force_serial_channel_operations() is never consulted for them; guard the shared
        # DLL handle directly instead.
        #
        # This must stay _dll_lock (class-level, process-wide) rather than self.lock
        # (per-instance): LoadLibrary is called once per WaveletFilter instance but returns
        # a shared module handle, and the wavelet C library's internal state is not
        # reentrant, so two instances filtering at once would corrupt each other. Do not
        # "simplify" this to the per-instance lock.
        with self._dll_lock:
            self.fun(data, len(data), wavelet)
        return data[padlen:-padlen]

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @log(logger=logger)
    @override
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Reset the state of a specific channel for a new operation or run. If channel is not None, handle only that channel, else reset all of them. No-op here, since this filter holds no persistent per-channel state between calls.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

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
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Wavelet": {"Type": str, "Value": "bior1.5", "Options": self.wavelist}
        }
        return settings

    @log(logger=logger)
    @override
    def _finalize_initialization(self) -> None:
        """
        Apply the provided filter paramters and intialize any internal structures needed by self.apply_filter().
        Should Raise if initialization fails, but corner cases should be handled by _validate_settings already
        """
        override_path = os.environ.get("PORISCOPE_WAVELET_PATH")
        if override_path:
            dll_path = os.path.abspath(override_path)
        else:
            system = platform.system()
            ext_map = {"Windows": ".dll", "Linux": ".so", "Darwin": ".dylib"}
            if system not in ext_map:
                raise RuntimeError(f"Unsupported platform: {system}")
            ref = (
                importlib.resources.files("poriscope")
                / "cdlls"
                / "wavelet"
                / "dist"
                / f"wavelet{ext_map[system]}"
            )
            dll_path = os.path.abspath(str(ref))

        if not os.path.isfile(dll_path):
            raise FileNotFoundError(
                f"Wavelet library not found at: {dll_path}\n"
                "Build the binaries or set PORISCOPE_WAVELET_PATH to the exact file."
            )

        if platform.system() == "Windows" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(os.path.dirname(dll_path))

        wavelib = ctypes.cdll.LoadLibrary(dll_path)
        self.fun = wavelib.filter_signal_wt
        self.fun.restype = None
        self.fun.argtypes = [
            ndpointer(ctypes.c_double, flags="C_CONTIGUOUS"),
            ctypes.c_int64,
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
