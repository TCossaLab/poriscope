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
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, override

import numpy as np
import numpy.typing as npt
import pyabf

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaReader import MetaReader

#: Picoamps per unit, for every unit an ABF file can record current in. pyabf spells
#: the micro sign as ``u``.
PA_PER_UNIT = {"fA": 1e-3, "pA": 1.0, "nA": 1e3, "uA": 1e6, "mA": 1e9}

#: The ``Sweep`` value that reads every sweep of a file, back to back.
ALL_SWEEPS = -1

#: ABF ``nOperationMode`` for variable-length event-driven acquisition, whose sweeps
#: differ in length, so a single one cannot be located from the header alone.
VARIABLE_LENGTH_MODE = 1

#: The value each of this reader's own settings takes when a subclass removes it from
#: its settings, which is how a subclass fixes it for the files it reads.
SETTING_DEFAULTS = {"Current Channel": 0, "Sweep": ALL_SWEEPS}


@inherit_docstrings
class ABFReader(MetaReader):
    """
    Reader for any Axon Binary Format file that ``pyabf`` can open: ABF1 or ABF2, int16
    or float32 samples, gap-free or episodic.

    One file is the whole dataset, read as channel 0. The header comes from ``pyabf``;
    the samples are memory-mapped directly rather than loaded through ``pyabf``, which
    would read the whole file into memory as float32. The settings choose which ADC
    channel holds the current and which sweep to read.

    Subclasses for a specific family of ABF recordings remove the settings their files
    do not need from :py:meth:`get_empty_settings`, which fixes them at their defaults
    (ADC channel 0, every sweep), and override the three file-set methods to recognise
    and order a dataset that spans several files.
    """

    logger = logging.getLogger(__name__)

    # public API, must be implemented by subclasses
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

        The keys this plugin adds:

        - ``Input File`` - the ``.abf`` file to read. Its header carries the sample
          rate, the channels and the scaling.
        - ``Current Channel`` - the index of the ADC channel that records current, 0 for
          the first. Its units must be a current.
        - ``Sweep`` - the sweep to read, 0 for the first, or -1 to read every sweep back
          to back. A gap-free recording has one sweep, so -1 and 0 read the same data.

        A subclass that removes ``Current Channel`` or ``Sweep`` reads ADC channel 0, or
        every sweep, respectively.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: True if this is outside the context of a GUI, False otherwise, Default False.
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Input File"]["Options"] = ["ABF Files (*.abf)"]
        settings["Current Channel"] = {
            "Type": int,
            "Value": SETTING_DEFAULTS["Current Channel"],
            "Min": 0,
        }
        settings["Sweep"] = {
            "Type": int,
            "Value": SETTING_DEFAULTS["Sweep"],
            "Min": ALL_SWEEPS,
        }
        return settings

    @log(logger=logger)
    @override
    def reset_channel(self, channel: int) -> None:
        """
        Reset a channel for a new run; this reader keeps no per-channel state, so there is nothing to do.

        :param channel: channel ID
        :type channel: int
        """
        pass

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _convert_data(
        self, data: npt.NDArray[np.int16], config: dict
    ) -> npt.NDArray[np.float64]:
        """
        Convert raw samples into current in pA, as ``pyabf`` does.

        int16 samples are ADC codes: each is multiplied by the channel's gain and the
        channel's offset is added. float32 samples are already in the channel's units and
        are not scaled. Either way the result is then converted from the channel's units
        to pA.

        :param data: Data to convert.
        :type data: npt.NDArray[np.int16]
        :param config: Configuration dictionary for data conversion.
        :type config: dict
        :return: The data, rescaled to pA.
        :rtype: npt.NDArray[np.float64]
        """
        return self._scale_data(
            data,
            scale=config["scale"],
            offset=config["offset"],
            dtype=np.float64,
            copy=False,
        )

    @log(logger=logger)
    @override
    def _get_configs(self, datafiles: List[str]) -> List[dict]:
        """
        Read each file's header with ``pyabf`` and work out how to map and scale it.

        The sample rate comes from the header's own sampling interval, as a float:
        ``pyabf``'s ``dataRate`` rounds it to an integer. An ABF2 header holds the
        interval per channel; an ABF1 header holds it per sample across all channels.

        :param datafiles: List of data files for which to load configurations.
        :type datafiles: List[str]
        :return: List of configuration dictionaries.
        :rtype: List[dict]

        :raises ValueError: If the file has no ADC channel at the ``Current Channel``
            index, if that channel's units are not a current, if the file is shorter
            than its header declares, or if the ``Sweep`` requested does not exist or
            cannot be located.
        """
        current_channel = self._abf_setting("Current Channel")
        sweep = self._abf_setting("Sweep")
        configs = []
        for filename in datafiles:
            abf = pyabf.ABF(filename, loadData=False)
            if current_channel >= abf.channelCount:
                raise ValueError(
                    f"{filename} has {abf.channelCount} ADC channels, so it has no "
                    f"channel {current_channel}"
                )
            units = abf.adcUnits[current_channel]
            if units not in PA_PER_UNIT:
                raise ValueError(
                    f"ADC channel {current_channel} ({abf.adcNames[current_channel]}) of "
                    f"{filename} records {units}, not a current; choose the channel "
                    f"that records current"
                )
            data_bytes = abf.dataPointCount * np.dtype(abf._dtype).itemsize
            if os.path.getsize(filename) < abf.dataByteStart + data_bytes:
                raise ValueError(
                    f"{filename} is shorter than its header declares: it should hold "
                    f"{abf.dataPointCount} samples from byte {abf.dataByteStart}"
                )
            rows = abf.dataPointCount // abf.channelCount
            if sweep == ALL_SWEEPS:
                first_row, last_row = 0, rows
            elif abf.nOperationMode == VARIABLE_LENGTH_MODE:
                raise ValueError(
                    f"{filename} holds variable-length sweeps, which cannot be read "
                    f"one at a time; read every sweep ({ALL_SWEEPS}) instead"
                )
            elif sweep >= abf.sweepCount:
                raise ValueError(
                    f"{filename} has {abf.sweepCount} sweeps, so it has no sweep {sweep}"
                )
            else:
                first_row = sweep * abf.sweepPointCount
                last_row = first_row + abf.sweepPointCount

            if abf.abfVersion["major"] == 1:
                interval_us = (
                    abf._headerV1.fADCSampleInterval * abf._headerV1.nADCNumChannels
                )
            else:
                interval_us = abf._protocolSection.fADCSequenceInterval

            pa_per_unit = PA_PER_UNIT[units]
            if abf._dtype == np.int16:
                gain = abf._dataGain[current_channel]
                offset = abf._dataOffset[current_channel]
            else:
                gain, offset = 1.0, 0.0

            configs.append(
                {
                    "samplerate": 1.0e6 / interval_us,
                    "dtype": np.dtype(abf._dtype).newbyteorder("<"),
                    "header_bytes": abf.dataByteStart,
                    "values": abf.dataPointCount,
                    "channel_count": abf.channelCount,
                    "current_channel": current_channel,
                    "rows": (first_row, last_row),
                    "scale": gain * pa_per_unit,
                    "offset": offset * pa_per_unit,
                }
            )
        return configs

    @log(logger=logger)
    @override
    def _get_file_channel_stamps(
        self, file_names: List[str], configs: List[dict]
    ) -> List[int]:
        """
        Read every file as channel 0; one file is the whole dataset.

        :param file_names: List of file names to get channel stamps for.
        :type file_names: List[str]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of serialization keys for channels
        :rtype: List[int]
        """
        return [0] * len(file_names)

    @log(logger=logger)
    @override
    def _get_file_pattern(self, file_name: str) -> str:
        """
        Match only the chosen file, which is the whole dataset; it is escaped, so
        brackets in its name stay literal.

        :param file_name: File name to get the base pattern for.
        :type file_name: str
        :return: Base pattern for matching other files.
        :rtype: str
        """
        return glob.escape(file_name)

    @log(logger=logger)
    @override
    def _get_file_time_stamps(self, file_names: List[str], configs: List[dict]) -> Any:
        """
        Give every file the same time stamp; one file is the whole dataset.

        :param file_names: List of file names to get time stamps for.
        :type file_names: List[str]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of serialization keys for timestamps, all 0.
        :rtype: Any
        """
        return [0] * len(file_names)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        pass

    @log(logger=logger)
    @override
    def _map_data(self, datafiles: List[str], configs: List[dict]) -> List[np.ndarray]:
        """
        Memory-map each file's samples and take the current channel's column.

        The map covers exactly the number of samples the header declares, so padding
        after the data section is never read as samples, and is then cut to the rows of
        the sweep requested.

        :param datafiles: List of data files to map.
        :type datafiles: List[str]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of memmaps or numpy arrays mapped from data files.
        :rtype: List[np.ndarray]

        :raises FileNotFoundError: If at least one of the input raw data files is missing or renamed.
        :raises OSError: If the file indicated is inaccessible.
        """
        datamaps = []
        for filename, config in zip(datafiles, configs):
            try:
                values = np.memmap(
                    Path(filename),
                    dtype=config["dtype"],
                    mode="r",
                    offset=config["header_bytes"],
                    shape=(config["values"],),
                )
            except FileNotFoundError as e:
                raise FileNotFoundError(
                    "File Not Found : At least one of the input raw data files is missing or renamed"
                ) from e
            except OSError as e:
                raise OSError(
                    "Invalid Argument or Sync Issue : The file indicated is inaccessible. If it is on a remote network location or external media, move it to the local hard drive and try again"
                ) from e
            first_row, last_row = config["rows"]
            datamaps.append(
                values.reshape(-1, config["channel_count"])[
                    first_row:last_row, config["current_channel"]
                ]
            )
        return datamaps

    @log(logger=logger)
    @override
    def _set_file_extension(self) -> str:
        """
        Set the expected file extension for files read using this reader subclass

        :return: the file extension
        :rtype: str
        """
        return ".abf"

    @log(logger=logger)
    @override
    def _validate_file_type(self, filename: os.PathLike) -> None:
        """
        Accept any file here; ``pyabf`` refuses one that is not ABF when its header is read.

        :param filename: the path to one of the files to be opened
        :type filename: os.PathLike
        """
        pass

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Nothing to check beyond the declared minimums; the channel and the sweep can only
        be checked against a file's header, which happens when it is read.

        :param settings: Parameters required to configure this reader.
        :type settings: dict
        """
        pass

    def _abf_setting(self, key: str) -> int:
        """
        The value of one of this reader's own settings, or its default where a subclass
        has removed the setting.

        :param key: ``Current Channel`` or ``Sweep``.
        :type key: str
        :return: the setting's value
        :rtype: int
        """
        if key in self.settings:
            return int(self.settings[key]["Value"])
        return SETTING_DEFAULTS[key]
