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

import glob
import logging
import re
from typing import Any, Dict, List, Optional, override

from poriscope.plugins.datareaders.ABFReader import ABFReader
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class TCossaLabABFReader(ABFReader):
    """
    Reader for the lab's multi-file ABF2 recordings, one set of files per channel.

    Files are named ``<base>_<12-digit stamp>_CH<channel>_<part>.abf``; every file of a
    recording is found from any one of them, grouped by the ``CH`` number and read in
    ``part`` order as one continuous channel. Each file records current on its first
    ADC channel in one gap-free sweep, so the base reader's channel and sweep settings
    are removed.
    """

    logger = logging.getLogger(__name__)

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

        The one key this plugin keeps:

        - ``Input File`` - one ``.abf`` file of the recording; every file of the same
          recording beside it is found and read with it. The ABF header carries the
          sample rate and scaling.

        :py:class:`~poriscope.plugins.datareaders.ABFReader.ABFReader`'s ``Current
        Channel`` and ``Sweep`` are removed: every file of these recordings records
        current on its first ADC channel in one gap-free sweep, so the current is read
        from ADC channel 0 and every sweep is read.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        del settings["Current Channel"]
        del settings["Sweep"]
        return settings

    @log(logger=logger)
    @override
    def _get_file_time_stamps(
        self, file_names: List[str], configs: List[dict]
    ) -> List[int]:
        """
        Get a list of serialization keys used to sort the list of files associated to the experiment.

        :param file_names: List of file paths.
        :type file_names: List[str]
        :param configs: List of configuration dictionaries.
        :type configs: List[dict]

        :return: List of timestamps parsed from configuration.
        :rtype: List[int]

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
    def _get_file_channel_stamps(
        self, file_names: List[str], configs: List[dict]
    ) -> List[int]:
        """
        Get a list of serialization keys used to sort the list of files associated to the experiment.

        :param file_names: List of file paths.
        :type file_names: List[str]
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
    def _get_file_pattern(self, file_name: str) -> str:
        """
        Get the base name for matching other files to the same dataset as the initial one provided to the constructor.

        :param file_name: File path.
        :type file_name: str

        :return: Base name for matching other files.
        :rtype: str

        :raises ValueError: If the base naming pattern cannot be ascertained.
        """
        # Keep the base name and wildcard the 12-digit stamp, channel and part, spelled
        # out so a recording whose name merely starts with this one's is not globbed
        # into this set; the base is escaped so brackets stay literal.
        match = re.split(r"_\d{12}_CH\d{3}_\d{3}\.abf", file_name)
        if len(match) > 1:
            return (
                glob.escape(match[0])
                + "_"
                + "[0-9]" * 12
                + "_CH"
                + "[0-9]" * 3
                + "_"
                + "[0-9]" * 3
                + self.file_extension
            )
        else:
            raise ValueError(
                "Unable to ascertain base naming pattern for {0}".format(file_name)
            )
