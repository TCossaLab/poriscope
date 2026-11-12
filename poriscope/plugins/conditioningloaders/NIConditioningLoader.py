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
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, override

import numpy as np
import numpy.typing as npt
import pandas as pd

from poriscope.plugins.datareaders.NIBinaryReader import NIBinaryReader
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaConditioningLoader import MetaConditioningLoader


@inherit_docstrings
class NIConditioningLoader(MetaConditioningLoader):
    """
    Reads a conditioning experiment written by the lab's LabVIEW and NI DAQ acquisition software.

    The experiment is one folder. ``Conditioning`` holds the pore sizes, one CSV row per
    cycle, in three blocks of one column per channel: the measured size, the upper target
    and the lower target. ``Cond PSD Pos`` and ``Cond PSD Neg`` hold one NI binary file per
    PSD recording at positive and negative bias; either may be missing. Each binary file is
    read by an :py:class:`~poriscope.plugins.datareaders.NIBinaryReader.NIBinaryReader` this
    plugin owns, so the binary format, the sample rate in the file name and the conversion
    to pA are implemented once.

    Several CSVs, as when the acquisition was restarted part-way, are read as one: they are
    put in the order of the ``YYYYMMDD_HHMMSS`` stamp in their names and their rows joined.
    The PSD recordings are ordered by the same stamp, and recording ``i`` of a polarity
    (counted from 0) belongs to cycle ``(i + 1) * N``, where ``N`` is the
    ``PSD Every N Cycles`` setting.
    """

    logger = logging.getLogger(__name__)

    #: The subfolder holding the pore-size CSVs.
    CSV_FOLDER = "Conditioning"

    #: The subfolder holding each polarity's PSD recordings.
    PSD_FOLDERS = {"+": "Cond PSD Pos", "-": "Cond PSD Neg"}

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Start with no experiment read, so :py:meth:`close_resources` is safe before settings arrive.
        """
        self.readers: Dict[str, List[NIBinaryReader]] = {}
        self.points: Dict[str, List[int]] = {}
        self.pore_sizes: Dict[str, npt.NDArray[np.float64]] = {}
        self.channel_count = 0

    @log(logger=logger)
    @override
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters required to configure this plugin.
        :type settings: dict
        :raises ValueError: If the folder is not a conditioning experiment, or the sensitivity is not positive.
        """
        folder = Path(settings["Folder"]["Value"])
        if not (folder / self.CSV_FOLDER).is_dir():
            raise ValueError(
                f"{folder} is not a conditioning experiment: it has no "
                f"'{self.CSV_FOLDER}' folder"
            )
        if not list((folder / self.CSV_FOLDER).glob("*.csv")):
            raise ValueError(f"No CSV file found in {folder / self.CSV_FOLDER}")
        if settings["Sensitivity"]["Value"] <= 0:
            raise ValueError("Sensitivity must be greater than 0 pA/V")

    @log(logger=logger)
    @override
    def _finalize_initialization(self) -> None:
        """
        Read the pore sizes and open every PSD recording.

        A CSV without three columns per channel, or several files that cannot be put in
        time order, is refused with ``ValueError`` by the helpers that read them.
        """
        self.close_resources()
        folder = Path(self.settings["Folder"]["Value"])
        self.channel_count = int(self.settings["Number of Channels"]["Value"])
        self.pore_sizes = self._read_pore_sizes(folder / self.CSV_FOLDER)
        for polarity, subfolder in self.PSD_FOLDERS.items():
            files = self._in_time_order(
                list((folder / subfolder).glob("*.bin")), f"'{subfolder}' recordings"
            )
            if files:
                self.readers[polarity] = [self._open_recording(f) for f in files]
                self.points[polarity] = [
                    self._points_per_average(reader)
                    for reader in self.readers[polarity]
                ]

    # public API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Declare the settings this loader exposes.

        - ``Folder`` - the experiment folder, the one holding ``Conditioning``.
        - ``Number of Channels`` - how many channels the CSVs and the binary files hold.
        - ``PSD Every N Cycles`` - a PSD recording was taken every this many cycles.
        - ``Sensitivity`` (pA/V) - the amplifier gain, converting the recordings' mV to pA.
        - ``Sampling Rate`` (Hz) - 0 reads each recording's rate from its file name;
          any other value is used for every recording.
        - ``Points per Average`` - 0 reads each recording's points per average from its
          file name; any other value is used for every recording.

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the loader
        :rtype: Dict[str, Dict[str, Any]]
        """
        return {
            "Folder": {"Type": str},
            "Number of Channels": {"Type": int, "Value": 16, "Min": 1},
            "PSD Every N Cycles": {"Type": int, "Value": 1, "Min": 1},
            "Sensitivity": {
                "Type": float,
                "Value": 1000.0,
                "Min": 0.0,
                "Units": "pA/V",
            },
            "Sampling Rate": {"Type": float, "Value": 0.0, "Min": 0.0, "Units": "Hz"},
            "Points per Average": {"Type": int, "Value": 0, "Min": 0},
        }

    @log(logger=logger)
    @override
    def report_status(self, channel: Optional[int] = None, init: bool = False) -> str:
        """
        Describe the experiment, and name every PSD recording shorter than one average.

        :param channel: the channel to report on, or None for the whole experiment
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool
        :return: the status report
        :rtype: str
        """
        report = super().report_status(channel, init)
        if channel is not None:
            return report
        for polarity, readers in self.readers.items():
            for index, reader in enumerate(readers):
                length = reader.get_channel_length(0)
                points = self.points[polarity][index]
                if length < points:
                    report += (
                        f"\nPSD{polarity} recording {Path(reader.get_base_file()).name} "
                        f"(cycle {self.get_psd_cycle(polarity, index)}) has {length} "
                        f"samples, fewer than its {points} points per average"
                    )
        return report

    @log(logger=logger)
    @override
    def close_resources(self) -> None:
        """
        Close every recording this loader opened. Safe to call more than once.
        """
        for readers in self.readers.values():
            for reader in readers:
                reader.close_resources()
        self.readers = {}
        self.points = {}

    @log(logger=logger)
    @override
    def get_channels(self) -> List[int]:
        return list(range(self.channel_count))

    @log(logger=logger)
    @override
    def get_cycles(self) -> npt.NDArray[np.int64]:
        return np.arange(1, len(self.pore_sizes["measured"]) + 1, dtype=np.int64)

    @log(logger=logger)
    @override
    def get_pore_sizes(self, channel: int) -> Dict[str, npt.NDArray[np.float64]]:
        return {
            name: block[:, channel].copy() for name, block in self.pore_sizes.items()
        }

    @log(logger=logger)
    @override
    def get_psd_polarities(self) -> List[str]:
        return [polarity for polarity in self.POLARITIES if polarity in self.readers]

    @log(logger=logger)
    @override
    def get_psd_segment_count(self, polarity: str) -> int:
        return len(self.readers.get(polarity, []))

    @log(logger=logger)
    @override
    def get_psd_cycle(self, polarity: str, index: int) -> int:
        return (index + 1) * int(self.settings["PSD Every N Cycles"]["Value"])

    @log(logger=logger)
    @override
    def get_psd_samplerate(self, polarity: str, index: int) -> float:
        return self.readers[polarity][index].get_samplerate()

    @log(logger=logger)
    @override
    def get_psd_points_per_average(self, polarity: str, index: int) -> int:
        return self.points[polarity][index]

    @log(logger=logger)
    @override
    def load_psd_segment(
        self, polarity: str, index: int, channel: int
    ) -> npt.NDArray[np.float64]:
        reader = self.readers[polarity][index]
        samples = reader.get_channel_length(channel)
        return reader.load_data(0.0, samples / reader.get_samplerate(), channel)

    # private API
    @log(logger=logger)
    def _read_pore_sizes(self, folder: Path) -> Dict[str, npt.NDArray[np.float64]]:
        """
        Read every CSV in time order and join their rows.

        Each CSV is read tab-separated first and comma-separated if that does not give
        three columns per channel, as the acquisition software has written both.

        :param folder: the ``Conditioning`` folder
        :type folder: Path
        :raises ValueError: If a CSV does not have three columns per channel.
        :return: the measured size and the band, each of shape (cycles, channels)
        :rtype: Dict[str, npt.NDArray[np.float64]]
        """
        columns = 3 * self.channel_count
        blocks = []
        for path in self._in_time_order(list(folder.glob("*.csv")), "pore-size CSVs"):
            frame = pd.read_csv(path, sep="\t")
            if len(frame.columns) != columns:
                frame = pd.read_csv(path, sep=",")
            if len(frame.columns) != columns:
                raise ValueError(
                    f"{path.name} has {len(frame.columns)} columns, but "
                    f"{self.channel_count} channels need {columns}: the measured size, "
                    f"the upper target and the lower target of each"
                )
            blocks.append(frame.to_numpy(dtype=np.float64))
        rows = np.vstack(blocks)
        n = self.channel_count
        return {
            "measured": rows[:, :n],
            "max_target": rows[:, n : 2 * n],
            "min_target": rows[:, 2 * n :],
        }

    @log(logger=logger)
    def _in_time_order(self, paths: List[Path], what: str) -> List[Path]:
        """
        Put files in the order of the ``YYYYMMDD_HHMMSS`` stamp in their names.

        :param paths: the files
        :type paths: List[Path]
        :param what: what the files are, for the error message
        :type what: str
        :raises ValueError: If there is more than one file and any name has no stamp.
        :return: the files, earliest first
        :rtype: List[Path]
        """
        if len(paths) < 2:
            return paths
        stamped = []
        unstamped = []
        for path in paths:
            stamps = re.findall(r"(\d{8}_\d{6})", path.name)
            if stamps:
                stamped.append((stamps[-1], path.name, path))
            else:
                unstamped.append(path.name)
        if unstamped:
            raise ValueError(
                f"The {what} cannot be put in time order: "
                f"{', '.join(sorted(unstamped))} carry no YYYYMMDD_HHMMSS stamp"
            )
        return [path for _, _, path in sorted(stamped)]

    @log(logger=logger)
    def _open_recording(self, path: Path) -> NIBinaryReader:
        """
        Open one PSD recording with this experiment's channel count, sample rate and sensitivity.

        :param path: the binary file
        :type path: Path
        :return: a reader over it
        :rtype: NIBinaryReader
        """
        reader = NIBinaryReader(key=f"{self.get_key()}:{path.name}")
        settings = reader.get_empty_settings(standalone=True)
        settings["Input File"]["Value"] = str(path)
        settings["Number of Arrays"]["Value"] = self.channel_count
        settings["Sampling Rate"]["Value"] = float(
            self.settings["Sampling Rate"]["Value"]
        )
        settings["Sensitivity"]["Value"] = float(self.settings["Sensitivity"]["Value"])
        reader.apply_settings(settings)
        return reader

    @log(logger=logger)
    def _points_per_average(self, reader: NIBinaryReader) -> int:
        """
        One recording's points per average: the setting if it is not 0, else from the file name.

        :param reader: the recording
        :type reader: NIBinaryReader
        :return: samples per average
        :rtype: int
        """
        points = int(self.settings["Points per Average"]["Value"])
        if points > 0:
            return points
        return reader.get_points_per_average()
