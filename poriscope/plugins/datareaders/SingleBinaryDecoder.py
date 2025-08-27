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
import os
from pathlib import Path

import numpy as np
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaReader import MetaReader


@inherit_docstrings
class SingleBinaryDecoder(MetaReader):
    """
    Subclass of MetaReader for reading chimera VC1100 .log files
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
        :type channel: int
        """
        pass

    @log(logger=logger)
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
        if (
            settings["Bitmask"]["Value"] != 0
            and settings["Data Type"]["Value"] == "Floating Point"
        ):
            raise ValueError("Bitmasks are not supported for floating point data.")
        if (
            settings["Data Type"]["Value"] == "Unsigned Integer"
            or settings["Data Type"]["Value"] == "Signed Integer"
        ) and settings["Data Bytes"]["Value"] == 8:
            raise ValueError("64-bit integers not supported as a base data type.")
        if (
            settings["Data Type"]["Value"] == "Floating Point"
            and settings["Data Bytes"]["Value"] == 2
        ):
            raise ValueError(
                "16-bit floats not supported as a base data type, use 32 or 64 bit only."
            )
        if settings["Data Bytes"]["Value"] == 2 and settings["Bitmask"]["Value"] >= (
            1 << 16
        ):
            raise ValueError(f"16-bit bitmasks must be at most {(1<<16)-1}.")
        if settings["Data Bytes"]["Value"] == 4 and settings["Bitmask"]["Value"] >= (
            1 << 32
        ):
            raise ValueError(f"32-bit bitmasks must be at most {(1<<32)-1}.")
        if settings["Data Bytes"]["Value"] == 8 and settings["Bitmask"]["Value"] > 0:
            raise ValueError("64-bit bitmasks are not supported.")

    @log(logger=logger)
    @override
    def _set_file_extension(self):
        """
        Set the expected file extension for files read using this reader subclass
        """
        return ".bin"

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
        fmt = []
        offset = self.settings["Header Bytes"]["Value"]
        for channel, (filename, config) in enumerate(zip(datafiles, configs)):
            fmt.append((f"data_{channel}", self.dtype))

        memmaps = np.memmap(Path(filename), dtype=fmt, offset=offset, mode="r")
        for channel, (filename, config) in enumerate(zip(datafiles, configs)):
            try:
                datamaps.append(memmaps[f"data_{channel}"])
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
    def _set_sample_rate(self):
        """
        Set the sampling rate for the reader.
        """
        self.samplerate = self.settings["Sampling Rate"]["Value"]

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
        return [0] * self.settings["Number of Arrays"]["Value"]

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
        return list(range(self.settings["Number of Arrays"]["Value"]))

    @log(logger=logger)
    def _get_file_names(self, folder, pattern):
        """
        Get a list of file names with data to map

        :param folder: File name to get the base pattern for.
        :type folder: os.PathLike
        :param pattern: pattern to match
        :type pattern: str

        :return: a list of file names
        :rtype: List[os.PathLike]
        """
        # repeat file names with multiplicity equal to the number of channels involved in cases where there are many channels per file
        return [self.settings["Input File"]["Value"]] * self.settings[
            "Number of Arrays"
        ]["Value"]

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
        return file_name

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
        scale = self.settings["Scale"]["Value"]
        offset = self.settings["Offset"]["Value"]
        bitmask = self.settings["Bitmask"]["Value"]

        conv_data = self._scale_data(
            data,
            bitmask=bitmask,
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
        return [{}] * self.settings["Number of Arrays"]["Value"]

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
        endianness = base_type = self.settings["Byte Order"]["Value"]
        base_type = self.settings["Data Type"]["Value"]
        data_size = self.settings["Data Bytes"]["Value"]

        type_string = ""
        if endianness in ["<", ">"]:
            type_string += endianness
        else:
            raise ValueError(
                f"Incompatible endianness symbol. Must be < or >, but received {endianness}."
            )
        type_string = endianness

        if base_type == "Floating Point":
            type_string += "f"
        elif base_type == "Signed Integer":
            type_string += "i"
        elif base_type == "Unsigned Integer":
            type_string += "u"
        else:
            raise ValueError(
                f"Incompatible data type. Data type must be int, uint, or float, but received {base_type}."
            )

        if data_size in [2, 4, 8]:
            type_string += str(int(data_size))
        else:
            raise ValueError(
                f"Incompatible data size. Data size must be one of 2, 4, or 8, but receieved {data_size}."
            )

        return np.dtype(type_string)

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
        settings["Input File"]["Options"] = ["Binary Files (*.*)"]
        settings["Sampling Rate"] = {"Type": float, "Min": 0.0, "Units": "Hz"}
        settings["Header Bytes"] = {"Type": int, "Value": 0, "Min": 0}
        settings["Number of Arrays"] = {"Type": int, "Value": 1, "Min": 1}
        settings["Byte Order"] = {"Type": str, "Value": "<", "Options": ["<", ">"]}
        settings["Data Type"] = {
            "Type": str,
            "Value": "Floating Point",
            "Options": ["Floating Point", "Signed Integer", "Unsigned Integer"],
        }
        settings["Data Bytes"] = {"Type": int, "Value": 8, "Options": [8, 4, 2]}
        settings["Bitmask"] = {"Type": int, "Value": 0}
        settings["Scale"] = {"Type": float, "Value": 1.0}
        settings["Offset"] = {"Type": float, "Value": 0.0}
        return settings
