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
import re

import numpy as np
from typing_extensions import override

from poriscope.plugins.datareaders.helpers.ABF2Header import ABF2Header
from poriscope.plugins.datareaders.TCossaLabABFReader import TCossaLabABFReader
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class LegacyElementsReader(TCossaLabABFReader):
    """
    Subclass of MetaReader for reading ABF2 files
    """

    logger = logging.getLogger(__name__)
    # private API, MUST be implemented by subclasses

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
            pattern = r"_(\d{4})\.abf$"
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
        return [0]

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
        match = re.split(r"_\d{4}\.abf", file_name)
        if len(match) > 1:
            return match[0] + "*" + self.file_extension
        else:
            raise ValueError(
                "Unable to ascertain base naming pattern for {0}".format(file_name)
            )

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
                if header.get_num_channels() != 1:
                    raise ValueError(
                        "Only 1 channel per file is  supported, not {0}".format(
                            header.get_num_channels()
                        )
                    )
            config["samplerate"] = header.get_samplerate()
            config["columntypes"] = np.dtype(
                [
                    ("current", header.get_data_format()),
                ]
            )
            config["scale"] = header.get_scale_factor(
                0
            ) * header.get_rescale_to_pA_factor(header.get_channel_units(0))
            config["header_bytes"] = header.get_header_bytes()
            configs.append(config)
        return configs
