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
# Michelle Stephen

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, override

import numpy as np
import numpy.typing as npt

from poriscope.plugins.datareaders.SingleBinaryDecoder import SingleBinaryDecoder
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class NIBinaryReader(SingleBinaryDecoder):
    """
    Reads one binary file from the lab's NI DAQ acquisition software: 16 channels interleaved,
    big-endian 64-bit floats, no header, in mV.

    A :py:class:`~poriscope.plugins.datareaders.SingleBinaryDecoder.SingleBinaryDecoder` with
    that format fixed. The acquisition software names each file after its settings,
    ``<stem>_PSD-<points>_<averages>_<samplerate>Hz_<date>_<time>.bin``, so the sample rate is
    read from the name unless one is typed in, and the samples are converted from mV to pA
    with the amplifier's sensitivity in pA/V.
    """

    logger = logging.getLogger(__name__)

    #: The NI files' fixed format: the base reader's defaults, big-endian.
    SETTING_DEFAULTS: Dict[str, Any] = {
        **SingleBinaryDecoder.SETTING_DEFAULTS,
        "Byte Order": ">",
    }

    # public API, may be overridden by subclasses
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this reader exposes, on top of the base contract.

        Called by poriscope when the plugin is instantiated or reconfigured, to build
        the settings dialog and to sanity-check whatever the user enters; the accepted
        values are then readable through ``self.settings``. See
        :py:meth:`~poriscope.utils.MetaReader.MetaReader.get_empty_settings`
        for the structure of the dict and what ``Type``, ``Value``, ``Min``, ``Max``, ``Options`` and
        ``Units`` mean in it, and for the reserved keys the GUI builds file pickers
        from.

        The keys this plugin keeps or adds:

        - ``Input File`` - the NI binary file to read.
        - ``Number of Arrays`` - how many interleaved channels the file holds, 16 for the
          NI DAQ setups.
        - ``Sampling Rate`` (Hz) - 0 reads it from the ``<samplerate>Hz`` part of the file
          name; any other value is used instead.
        - ``Sensitivity`` (pA/V) - the amplifier gain; a sample of 1 mV is
          ``sensitivity / 1000`` pA.

        :py:class:`~poriscope.plugins.datareaders.SingleBinaryDecoder.SingleBinaryDecoder`'s
        format settings are removed, which fixes them for these files: no header,
        big-endian, 8-byte floating point, no bitmask.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        for key in self.SETTING_DEFAULTS:
            del settings[key]
        settings["Input File"]["Options"] = ["NI Binary Files (*.bin)"]
        settings["Number of Arrays"]["Value"] = 16
        settings["Sampling Rate"]["Value"] = 0.0
        settings["Sensitivity"] = {
            "Type": float,
            "Value": 1000.0,
            "Min": 0.0,
            "Units": "pA/V",
        }
        return settings

    @log(logger=logger)
    def get_points_per_average(self) -> int:
        """
        The number of samples per PSD average the file was recorded with, from its name.

        A file whose name does not carry its acquisition settings has none to give, and
        ``ValueError`` is raised saying so.

        :return: samples per average
        :rtype: int
        """
        return self._name_settings(str(self.settings["Input File"]["Value"]))[0]

    # private API, may be overridden by subclasses
    @log(logger=logger)
    @override
    def _convert_data(
        self, data: npt.NDArray[np.int16], config: dict
    ) -> npt.NDArray[np.float64]:
        """
        Convert raw data from disk into rescaled current, in pA.

        :param data: Data to convert.
        :type data: npt.NDArray[np.int16]
        :param config: Configuration dictionary for data conversion.
        :type config: dict
        :return: The data, rescaled to pA.
        :rtype: npt.NDArray[np.float64]
        """
        return self._scale_data(
            data,
            bitmask=0,
            scale=self.settings["Sensitivity"]["Value"] / 1000.0,
            offset=0.0,
            dtype=np.float64,
            copy=False,
        )

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the sensitivity is not positive, or no sample rate is typed and the file name does not carry one.
        """
        super()._validate_settings(settings)
        if settings["Sensitivity"]["Value"] <= 0:
            raise ValueError("Sensitivity must be greater than 0 pA/V")
        if settings["Sampling Rate"]["Value"] == 0:
            self._name_settings(str(settings["Input File"]["Value"]))

    @log(logger=logger)
    @override
    def _set_sample_rate(self) -> float:
        """
        The typed sample rate, or the one in the file name when 0 was typed.

        :return: the sampling rate in Hz
        :rtype: float
        """
        typed = float(self.settings["Sampling Rate"]["Value"])
        if typed > 0:
            return typed
        return float(self._name_settings(str(self.settings["Input File"]["Value"]))[1])

    @log(logger=logger)
    def _name_settings(self, path: str) -> Tuple[int, int]:
        """
        Read the points per average and the sample rate out of an NI file name.

        :param path: the file
        :type path: str
        :raises ValueError: If the name has no ``PSD-<points>_<averages>_<samplerate>Hz`` part.
        :return: the points per average and the sample rate
        :rtype: Tuple[int, int]
        """
        name = os.path.basename(path)
        match = re.search(r"PSD-(\d+)_(\d+)_(\d+)Hz", name)
        if match is None:
            raise ValueError(
                f"{name} does not carry its settings as PSD-<points>_<averages>_"
                f"<samplerate>Hz, so its points per average are unknown; type its "
                f"Sampling Rate to read it"
            )
        return int(match.group(1)), int(match.group(3))
