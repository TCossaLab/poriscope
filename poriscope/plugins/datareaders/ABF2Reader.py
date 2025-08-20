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
import re
from pathlib import Path

import numpy as np
from typing_extensions import override

from poriscope.plugins.datareaders.helpers.ABF2Header import ABF2Header
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaReader import MetaReader


@inherit_docstrings
class ABF2Reader(MetaReader):
    """
    Subclass of MetaReader for reading ABF2 files
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
    def _set_file_extension(self):
        """
        Set the expected file extension for files read using this reader subclass
        """
        return ".abf"

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
            fmt = config["columntypes"]
            offset = int(config["header_bytes"])
            try:
                datamaps.append(
                    np.memmap(Path(filename), dtype=fmt, offset=offset, mode="r")[
                        "current"
                    ]
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

        :raises ValueError: If the filename does not match the expected pattern
        """
        time_stamps = []
        for f in file_names:
            pattern = r"\d{3}_(\d{3})\.abf$"
            match = re.search(pattern, f)
            if match:
                time_stamps.append(int(match.group(1)))
            else:
                raise ValueError(
                    "Filename does not conform to expected pattern for the experimental set - unable to extract time stamp from {0}".format(
                        f
                    )
                )
        return time_stamps

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

        :raises ValueError: If the filename does not match the expected pattern
        """
        channel_stamps = []
        for f in file_names:
            pattern = r"_CH(\d{3})_\d{3}\.abf$"
            match = re.search(pattern, f)
            if match:
                channel_stamps.append(int(match.group(1)))
            else:
                raise ValueError(
                    "Filename does not conform to expected pattern for the experimental set - unable to extract channel stamp from {0}".format(
                        f
                    )
                )
        return channel_stamps

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
        match = re.split(r"_\d{12}_CH\d{3}_\d{3}\.abf", file_name)
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
        scale = config["scale"]
        offset = 0
        data = self._scale_data(
            data,
            scale=scale,
            offset=offset,
            dtype=np.float64,
            copy=False,
            raw_data=raw_data,
        )
        if raw_data:
            return data, scale, offset
        else:
            return data

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

        :raises NotImplementedError: If the file type is not ABF2 specifically
        :raises TypeError: If one of the channels does not have an "I" in its header label
        :raises ValueError: If any number of channels other than 2 is found in the data file
        """
        configs = []
        for filename in datafiles:
            config = {}
            with open(filename, mode="rb"):
                header = ABF2Header(filename)
                if header.get_abf_version() != "ABF2":
                    raise NotImplementedError(
                        "Only ABFs files are supported by this reader, not {0}".format(
                            header.get_abf_version()
                        )
                    )
                if "I" not in header.get_channels()[0]:
                    raise TypeError(
                        "Unable to identify current channel in channels named {0}".format(
                            header.get_channels()
                        )
                    )
                if header.get_num_channels() != 2:
                    raise ValueError(
                        "Only 2 channels per file are supported, not {0}".format(
                            header.get_num_channels()
                        )
                    )
            config["samplerate"] = header.get_samplerate()
            config["columntypes"] = np.dtype(
                [
                    ("current", header.get_data_format()),
                    ("voltage", header.get_data_format()),
                ]
            )
            config["scale"] = header.get_scale_factor(
                0
            ) * header.get_rescale_to_pA_factor(header.get_channel_units(0))
            config["header_bytes"] = header.get_header_bytes()
            configs.append(config)
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
        return np.dtype(configs[0]["columntypes"][0])

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
        settings["Input File"]["Options"] = ["ABF2 Files (*.abf)"]
        return settings
