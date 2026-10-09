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
class LegacyElementsReader(ABFReader):
    """
    Reader for single-file ABF2 recordings from the older Elements amplifiers, named
    ``<base>_<4-digit index>.abf``.

    Each file is one recording, read as channel 0, holding current alone in one
    gap-free sweep, so the base reader's channel and sweep settings are removed.
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

        - ``Input File`` - the ``.abf`` recording to read. The ABF header carries the
          sample rate and scaling.

        :py:class:`~poriscope.plugins.datareaders.ABFReader.ABFReader`'s ``Current
        Channel`` and ``Sweep`` are removed: these recordings hold current alone, in one
        gap-free sweep, so the current is read from ADC channel 0 and every sweep is
        read.

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
        """
        return [0]

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
        # A Legacy Elements recording is always a single file, so the set is exactly the
        # chosen file - escaped, so brackets in its name stay literal. The naming check
        # is kept so an unrecognised file is still refused.
        match = re.split(r"_\d{4}\.abf", file_name)
        if len(match) > 1:
            return glob.escape(file_name)
        else:
            raise ValueError(
                "Unable to ascertain base naming pattern for {0}".format(file_name)
            )
