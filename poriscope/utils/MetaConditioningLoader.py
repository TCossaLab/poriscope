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
# Michel Stephan

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log


@inherit_docstrings
class MetaConditioningLoader(BaseDataPlugin):
    """
    This class, :ref:`MetaConditioningLoader`, is the base class for reading a nanopore conditioning experiment. Conditioning steers each pore towards a target size over many cycles: every cycle records the pore size on each channel and the band it is being steered into, and every so many cycles a short recording is taken at positive bias, at negative bias, or both, from which the noise power spectral density (PSD) is computed. A plugin in this family reads one such experiment and serves both halves through one API, regardless of how the acquisition software laid them out on disk.

    What you get by inheriting from MetaConditioningLoader
    -------------------------------------------------------

    The Conditioning analysis tab reads any experiment through this API: it asks for the cycles and the pore sizes of each channel, and for each PSD recording's cycle, sample rate, points per average and samples, and does the spectral analysis itself. A subclass only has to say where those come from in its format.

    Channels are numbered from 0, as everywhere in Poriscope. PSD recordings are grouped by polarity, ``"+"`` for positive bias and ``"-"`` for negative bias; each polarity's recordings are indexed from 0 in the order they were taken.

    Attributes:
        logger (logging.Logger): Logger instance for logging messages.
    """

    logger = logging.getLogger(__name__)

    #: The polarities a conditioning experiment can have PSD recordings for.
    POLARITIES = ("+", "-")

    def __init__(
        self, settings: Optional[dict] = None, key: Optional[str] = None
    ) -> None:
        """
        Initialize the MetaConditioningLoader instance.

        :param settings: A dict conforming to that which is required by :py:meth:`get_empty_settings`.
        :type settings: Optional[dict]
        :param key: The name this plugin is known by; see :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.__init__`.
        :type key: Optional[str]
        """
        super().__init__(settings, key)

    # public API, should usually be left alone by subclasses
    @log(logger=logger)
    def report_status(self, channel: Optional[int] = None, init: bool = False) -> str:
        """
        Describe the experiment: its cycles and channels, and the PSD recordings at each polarity.

        With a channel, one line for that channel - in how many cycles a pore size was
        measured on it - as the Conditioning tab reports each channel it has finished
        computing; without one, the experiment and then every channel's line. Override
        it, calling ``super()``, to add what only your format knows.

        :param channel: the channel to report on, or None for the whole experiment
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool
        :return: the status report
        :rtype: str
        """
        recordings = ", ".join(
            f"{self.get_psd_segment_count(polarity)} PSD{polarity}"
            for polarity in self.get_psd_polarities()
        )
        cycles = len(self.get_cycles())
        if channel is not None:
            measured = int(np.count_nonzero(self.get_pore_sizes(channel)["measured"]))
            return (
                f"\nChannel {channel}: pore size measured in {measured} of {cycles} "
                f"cycles"
            )
        report = (
            f"\n{cycles} conditioning cycles on {len(self.get_channels())} channels, "
            f"with {recordings or 'no PSD'} recordings"
        )
        for each in self.get_channels():
            report += self.report_status(each, init)
        return report

    @log(logger=logger)
    def reset_channel(self, channel: int) -> None:
        """
        Do nothing: reading an experiment leaves no per-channel state behind.

        :param channel: ignored; accepted so every plugin shares one signature
        :type channel: int
        """

    # public API, must be implemented by subclasses
    @abstractmethod
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaConditioningLoader` subclass.

        Get a dict populated with keys needed to initialize the loader if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.

        .. code-block:: python

           settings = {
                'Parameter 1': {'Type': <int, float, str, bool>,
                                'Value': <value> or None,
                                'Options': [<option_1>, <option_2>, ... ] or None,
                                'Min': <min_value> or None,
                                'Max': <max_value> or None
                               },
                          ...
                }

        Several parameter keywords are reserved: these are

        'Input File'
        'Output File'
        'Folder'
        and all MetaClass names

        These must have Type str and will cause the GUI to generate appropriate widgets to allow selection of these elements when used. An experiment that is a folder, as the NI DAQ setups write one, asks for ``Folder``:

        ..   code:: python

            settings = {
                "Folder": {"Type": str},
                "Sensitivity": {
                    "Type": float,
                    "Value": 1000.0,
                    "Min": 0.0,
                    "Units": "pA/V",
                },
            }
            return settings

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the loader
        :rtype: Dict[str, Dict[str, Any]]
        """
        pass

    @abstractmethod
    def get_channels(self) -> List[int]:
        """
        **Purpose:** Return the channels the experiment recorded, numbered from 0.

        :return: the channel numbers
        :rtype: List[int]
        """
        pass

    @abstractmethod
    def get_cycles(self) -> npt.NDArray[np.int64]:
        """
        **Purpose:** Return the conditioning cycle numbers, counted from 1, one per recorded cycle.

        :return: the cycle numbers, in order
        :rtype: npt.NDArray[np.int64]
        """
        pass

    @abstractmethod
    def get_pore_sizes(self, channel: int) -> Dict[str, npt.NDArray[np.float64]]:
        """
        **Purpose:** Return one channel's pore size in each cycle, and the band it was steered into, in nm.

        The dict has three arrays, each with one value per cycle of :py:meth:`get_cycles`:
        ``"measured"`` (the pore size), ``"max_target"`` and ``"min_target"`` (the band). A
        channel that was not conditioned has a measured size of 0 in every cycle.

        :param channel: the channel, numbered from 0
        :type channel: int
        :return: the measured size and the band, keyed as above
        :rtype: Dict[str, npt.NDArray[np.float64]]
        """
        pass

    @abstractmethod
    def get_psd_polarities(self) -> List[str]:
        """
        **Purpose:** Return the polarities the experiment has PSD recordings for: ``"+"``, ``"-"``, both, or neither.

        :return: the polarities present, from :py:data:`POLARITIES`
        :rtype: List[str]
        """
        pass

    @abstractmethod
    def get_psd_segment_count(self, polarity: str) -> int:
        """
        **Purpose:** Return how many PSD recordings were taken at one polarity.

        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :return: the number of recordings
        :rtype: int
        """
        pass

    @abstractmethod
    def get_psd_cycle(self, polarity: str, index: int) -> int:
        """
        **Purpose:** Return the conditioning cycle a PSD recording was taken after.

        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :param index: the recording, counted from 0 in the order they were taken
        :type index: int
        :return: the cycle number, counted from 1
        :rtype: int
        """
        pass

    @abstractmethod
    def get_psd_samplerate(self, polarity: str, index: int) -> float:
        """
        **Purpose:** Return the sample rate of one PSD recording, in Hz.

        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :param index: the recording, counted from 0 in the order they were taken
        :type index: int
        :return: the sample rate
        :rtype: float
        """
        pass

    @abstractmethod
    def get_psd_points_per_average(self, polarity: str, index: int) -> int:
        """
        **Purpose:** Return the number of samples per PSD average the recording was taken with.

        This is the segment length of the Welch estimate, and sets its frequency
        resolution: one bin is the sample rate divided by this. A recording shorter than
        one segment is analysed as a single shorter segment.

        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :param index: the recording, counted from 0 in the order they were taken
        :type index: int
        :return: samples per average
        :rtype: int
        """
        pass

    @abstractmethod
    def load_psd_segment(
        self, polarity: str, index: int, channel: int
    ) -> npt.NDArray[np.float64]:
        """
        **Purpose:** Return one channel of one PSD recording, in pA.

        :param polarity: ``"+"`` or ``"-"``
        :type polarity: str
        :param index: the recording, counted from 0 in the order they were taken
        :type index: int
        :param channel: the channel, numbered from 0
        :type channel: int
        :return: the samples, in pA
        :rtype: npt.NDArray[np.float64]
        """
        pass

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations before settings are applied.

        This is called immediately at the start of class creation but before settings have been applied. No settings are available yet, so set up only what does not depend on them - typically empty containers that :py:meth:`close_resources` can safely walk before any experiment has been read.
        """
        pass

    @abstractmethod
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Read the experiment once settings are applied.

        Called at the end of :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings`, which also runs when the user edits the plugin's settings, so release whatever an earlier call opened before opening anything new. The settings are in ``self.settings[key]['Value']``.

        Should Raise if initialization fails.
        """
        pass

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters required to configure this loader.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass
