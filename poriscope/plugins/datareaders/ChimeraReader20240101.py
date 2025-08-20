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


import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaReader import MetaReader


@inherit_docstrings
class ChimeraReader20240101(MetaReader):
    """
    Subclass of MetaReader for reading chimera VC400 .log files using the 2024-01 format specification with json string embedded in the file header and multiple files per dataset.

    Attributes:
        datafile (str): Path to the data file.
        logger (logging.Logger): Logger instance for logging messages.
        datafiles (List[List[str]]): List of sorted data files grouped by channel and time.
        configs (List[List[dict]]): List of sorted configuration dictionaries grouped by channel and time.
        datamaps (List[List[numpy.ndarray]]): List of sorted data maps (memmaps or numpy arrays) grouped by channel and time.
        file_start_indices (List[List[int]]): List of starting indices for each data map in each channel.
        total_channel_samples (List[int]): List of total number of samples in each channel.
        samplerate (float): Sampling rate for data acquisition.
    """

    logger = logging.getLogger(__name__)

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self):
        """
        called at the start of base class initialization
        """
        pass

    @log(logger=logger)
    @override
    def close_resources(self, channel=None):
        """
        Perform any actions necessary to gracefully close resources before app exit

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
        :type channel: Optional[int]
        """
        pass

    @override
    def _validate_file_type(self, filename: os.PathLike) -> None:
        """
        Check that the file(s) being opened are of the correct type, and raise IOError if not

        :param filename: the path to one of the files to be opened
        :type filename: os.Pathlike
        :raises IOError: If the wrong type is file is fed to the plugin
        """
        pass

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    @log(logger=logger)
    @override
    def _set_file_extension(self):
        """
        Set the expected file extension for files read using this reader subclass
        """
        return ".log"

    @log(logger=logger)
    @override
    def _map_data(self, datafiles, configs):
        """
        Map data files into a set of memmaps or similarly define a way to access the raw data on disk.
        Returns a list of memmaps corresponding to each datafile/configfile pair.

        :param datafiles: List of data file paths.
        :type datafiles: List[os.PathLike]
        :param configs: List of configuration dictionaries.
        :type configs: List[dict]

        :return: List of memmaps containing raw data.
        :rtype: List[numpy.ndarray]

        :raises FileNotFoundError: If at least one of the input raw data files is missing or renamed.
        :raises OSError: If the file indicated is inaccessible.
        """
        # get formats and offsets for all files
        datamaps = []
        for filename, config in zip(datafiles, configs):
            label = config["label"]
            dtype = config["dtype"]
            fmt = [
                (
                    label,
                    "{0}{1}{2}".format(
                        dtype["data_order"], dtype["data_type"], int(dtype["data_size"])
                    ),
                )
            ]
            offset = int(config["header_bytes"])
            try:
                datamaps.append(
                    np.memmap(Path(filename), dtype=fmt, offset=offset, mode="r")
                )
            except FileNotFoundError:
                raise FileNotFoundError(
                    "File Not Found : At least one of the input raw data files is missing or renamed"
                )
            except OSError:
                raise OSError(
                    "Invalid Argument or Sync Issue : The file indicated is inaccessible. If it is on a remote network location or external media, move it to the local hard drive and try again"
                )
        return datamaps

    # private API, should implemented by subclasses, but has default behavior if it is not needed

    @log(logger=logger)
    @override
    def _get_file_time_stamps(self, file_names, configs):
        """
        Get a list of serialization keys used to sort the list of files associated to the experiment.

        :param file_names: List of file paths.
        :type file_names: List[os.PathLike]
        :param configs: List of configuration dictionaries.
        :type configs: List[dict]

        :return: List of timestamps parsed from configuration.
        :rtype: List[datetime]
        """
        return [
            datetime.strptime(config["timestamp"], "%Y%m%d_%H%M%S")
            for config in configs
        ]

    @log(logger=logger)
    @override
    def _get_file_channel_stamps(self, file_names, configs):
        """
        Get a list of serialization keys used to sort the list of files associated to the experiment.

        :param file_names: List of file paths.
        :type file_names: List[os.PathLike]
        :param configs: List of configuration dictionaries.
        :type configs: List[dict]

        :return: List of channel numbers parsed from configuration.
        :rtype: List[int]
        """
        return [int(config["channel"]) for config in configs]

    @log(logger=logger)
    @override
    def _get_file_pattern(self, file_name):
        """
        Get the base name for matching other files to the same dataset as the initial one provided to the constructor.

        :param file_name: File path.
        :type file_name: os.PathLike

        :return: Base name for matching other files.
        :rtype: str

        :raises ValueError: If the base naming pattern cannot be ascertained.
        """
        # replace date and time in a file name with wildcard, keep id, extension and headstage
        match = re.split(r"_HS\d+_", file_name)
        if len(match) > 0:
            return match[0] + "*" + self.file_extension
        else:
            raise ValueError(
                "Unable to ascertain base naming pattern for {0}".format(file_name)
            )

    @log(logger=logger)
    @override
    def _convert_data(self, data, config, raw_data=False):
        """
        Scale or otherwise transform and return requested data.
        Default behavior assumes data is already scaled when read.
        if raw_data is true, return also scale and offset

        :param data: Data to convert.
        :type data: numpy.ndarray
        :param config: Configuration dictionary for data conversion.
        :type config: dict
        :param raw_data: Decide whether to rescale data or return raw adc codes
        :type raw_data: bool

        :return: Converted data, and scale and offset if and only if raw_data is True
        :rtype: Union[Tuple[np.ndarray, float, float], np.ndarray]
        """
        tia_gain = config["tia_gain"]
        i_offset = config["i_offset"]
        filter_gain = config["filter_gain"]
        # rescale adc data to current (A) to (pA)
        conv_unit = 1e12  # pA/A
        scale = (
            conv_unit * ((2 * 2 * 2.048 / 2**16) / filter_gain) / tia_gain
        )  # adc conversion factor
        offset = -i_offset * conv_unit
        conv_data = self._scale_data(
            data,
            scale=scale,
            offset=offset,
            dtype=np.float64,
            copy=False,
            raw_data=raw_data,
        )
        if raw_data:
            return conv_data, scale, offset
        else:
            return conv_data

    @log(logger=logger)
    @override
    def _get_configs(self, datafiles):
        """
        Load configuration files as dictionaries, corresponding to datamaps as needed.
        Default behavior assumes there are no config files needed.

        :param datafiles: List of data file paths.
        :type datafiles: List[os.PathLike]

        :return: List of configuration dictionaries.
        :rtype: List[dict]
        """
        configs = []
        for filename in datafiles:
            with open(filename, mode="rb") as f:
                header_bytes = 10000
                header = f.read(header_bytes)
                endstring = b"<END HEADER>"
                datastart = header.find(endstring) + len(endstring)
                settings = json.loads(header[: datastart - len(endstring)])
                settings_log = settings["log"]
                settings_global = settings["global"]
                settings_channel = settings["channel"]
            configs.append(
                {
                    "header_bytes": datastart,  # skip header bytes
                    "samplerate": settings_global["f_sampling"],  # sample rate
                    "adc_samplerate": settings_global["f_adc"],  # sample rate
                    "label": "current",  # data labels for all arrays present
                    "units": "pA",
                    "dtype": {
                        "data_order": "",
                        "data_type": "int",
                        "data_size": 16,
                    },  # np dtypes
                    "file_type": "Chimera VC400",
                    "file_ext": ".log",
                    "file_version": settings_log["version"],
                    "channel": settings_log["HS"],
                    "filter_gain": settings_global["filter_gain"],
                    "bandwidth": settings_global["bandwidth"],
                    "decimate": settings_global["decimate"],
                    "tia_gain": settings_channel["tia_gain"],
                    "i_offset": settings_channel["i_offset"],
                    "v_offset": settings_channel["voffset"],
                    "timestamp": settings_log["timestamp"],
                    #'filter_tuning': settings_channel['filtertuning'],
                    #'dac_power': settings_channel['dacpower'],
                    #'dac_divider': settings_channel['dacdivider'],
                    #'dac_rescale': settings_channel['dac_rescale'],
                    #'low_gain': settings_channel['lowgain'],
                    #'boost': settings_channel['boost'],
                    #'internal_T': settings_channel['internalT'],
                    #'tc_T': settings_channel['tcT'],
                    #'tc_fault': settings_channel['tcFault']
                }
            )
        return configs

    @log(logger=logger)
    @override
    def _set_raw_dtype(self, configs):
        """
        Set the data type for the raw data in files of this type

        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]

        :return: the dtype of the raw data in your data files
        :rtype: np.dtype
        """
        return np.int16

    # public API
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
                                           'Max': <max_value> or None,
                                           'Units': <unit str> or None
                                          },
                          ...
                          }


        Several parameter keywords are reserved: these are

        'Input File'
        'Output File'
        'Folder'

        These must have Type str and will cause the GUI to generate widgets to allow selection of these elements when used

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Mapping[str, List[str]]
        :return: the dict that must be filled in to initialize the filter
        :rtype: Mapping[str, Mapping[str, Union[int, float, str, list[Union[int,float,str,None], None]]]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Input File"]["Options"] = ["Chimera Logfiles (*.log)"]
        return settings
