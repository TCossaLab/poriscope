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
# Alejandra Carolina González González

import datetime
import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.LogDecorator import log


class MetaReader(BaseDataPlugin):
    """
    :ref:`MetaReader` is the base class for all things related to reading raw nanopore timeseries datafiles. It handles mapping groups of files that belong in the same experiment, separating them by channel in the case of multichannel experimental operations, and time-ordering files within a channel when many data files are written as part of a single experiment. Subsequently, it provides a common API through which to interact with that data, effectively standardizing data reading operations regardless of the source. Given the number of different file formats commonly in use in the nanopore field, this plugin will likely always have the largest number of subclasses.

    What you get by inheriting from MetaReader
    ------------------------------------------

    Regardless of the details of how your data is actually stored, :ref:`MetaReader` will provide a common and intuitive API with which to interact with it, stitching together all the files in your dataset to work seamlessly together as a single dataset. Datasets are broken down by channel ID and time, allowing slicing into data that might be spread across multiple files as though it were a single contiguous memory structure. Data can be retrieved either on an ad-hoc basis, or as a continuous generator that allows you to iterate through on demand. Metadata like sampling rate, the length of data available in each channel, etc., can be retrieved through the API directly.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize the MetaReader instance.

        :raises FileNotFoundError: If the specified data file does not exist.

        Initialize instance attributes based on provided parameters and perform initialization tasks such as mapping data files, loading configurations, and setting sample rate.

        :param settings: a dict conforming to that which is required by the self.get_empty_settings() function
        :type settings: dict
        """
        super().__init__(settings)

    # Public API, probably usable as-is in most cases
    @log(logger=logger)
    def report_channel_status(self, channel: Optional[int] = None, init=False) -> str:
        """
        Return a string detailing any pertinent information about the status of analysis conducted on a given channel

        :param channel: channel ID
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool

        :return: the status of the channel as a string
        :rtype: str
        """
        if channel is None:
            report = ""
            for ch in self.get_channels():  # Changed to use get_channels()
                report += self.report_channel_status(ch, init)
            return report
        else:
            if init:
                return f"\nCh{channel}: {self.total_channel_samples[channel]/self.samplerate:.1f}s at {self.samplerate if self.samplerate.is_integer() else self.samplerate:.2f}Hz"
            else:
                return ""

    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. If channel is not None, handle only that channel, else close all of them. If no such operation is needed, it suffices to ``pass``. Note that readers that operate based on memmaps need not explicitly close those memmaps, as they will be handled by the garbage collector, but it does no harm to do so. Any open file handles should be closed explicitly if not closed at  the end of read operations.
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit.
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else close all of them. If reading through a channel does not create any persistent state changes in your plugin, you can simply ``pass`` this function.
        """
        pass

    @log(logger=logger)
    def load_data(
        self, start: float, length: float, channel: int = 0, raw_data: bool = False
    ) -> npt.NDArray[np.float64]:
        """
        Return raw data starting from index start and of length samples and rescale it to pA

        :param start: Starting index of data to load.
        :type start: int
        :param length: Number of samples to load.
        :type length: int
        :param channel: Channel number from which to load data.
        :type channel: int
        :param raw_data: Decide whether to rescale data or return raw adc codes
        :type raw_data: bool

        :return: Converted and rescaled data.
        :rtype: numpy.ndarray

        :raises ValueError: If start or end indices are out of bounds
        """
        try:
            channel = int(channel)
            start = int(start * self.samplerate)
            length = int(length * self.samplerate)
        except ValueError:
            raise ValueError(
                "channel, start, and length must all a type that can be coerced to int"
            )
        try:
            datamaps = self.datamaps[channel]
        except KeyError:  # Changed from IndexError to KeyError
            raise IndexError(
                "Data map for channel index {0} not available in reader".format(channel)
            )
        try:
            configs = self.configs[channel]
        except KeyError:  # Changed from IndexError to KeyError
            raise IndexError(
                "Configuration data for channel index {0} not available in reader".format(
                    channel
                )
            )
        samplerate = self.samplerate
        total_samples = self.total_channel_samples[channel]
        file_start_index = self.file_start_indices[channel]
        start_index = start
        end_index = start + length

        if start_index > total_samples:
            start_index = total_samples

        if end_index > total_samples:
            end_index = total_samples

        if (
            start_index < 0
            or start_index > total_samples
            or end_index < 0
            or start_index > end_index
        ):
            raise ValueError(
                "Invalid data load request: {0}s-{1}s in channel {2} with total duration {3}".format(
                    start, start + length, channel, total_samples / samplerate
                )
            )

        start_file_index = self._get_file_index(start_index, file_start_index)
        end_file_index = self._get_file_index(end_index, file_start_index)

        if start_file_index == end_file_index:
            tempdata = datamaps[start_file_index][
                start_index
                - file_start_index[start_file_index] : end_index
                - file_start_index[start_file_index]
            ]
            data = self._convert_data(tempdata, configs[start_file_index], raw_data)
            if raw_data:
                data, scale, offset = data
        else:
            tempdata = datamaps[start_file_index][
                start_index - file_start_index[start_file_index] :
            ]
            data = self._convert_data(tempdata, configs[start_file_index], raw_data)
            if raw_data:
                data, scale, offset = data
            for i in range(start_file_index + 1, end_file_index):
                tempdata = self._convert_data(datamaps[i], configs[i], raw_data)
                if raw_data:
                    tempdata, scale, offset = tempdata
                data = np.concatenate((data, tempdata))
            tempdata = self._convert_data(
                datamaps[end_file_index][
                    : end_index - file_start_index[end_file_index]
                ],
                configs[end_file_index],
                raw_data,
            )
            if raw_data:
                tempdata, scale, offset = tempdata
            data = np.concatenate((data, tempdata))

        if raw_data:
            return (
                data.astype(self.get_raw_dtype()),
                scale,
                offset,
            )  # assumes constant scale and offset between files
        else:
            return data

    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyes by metaclass
        :type globally_available_plugins: Optional[Mapping[str, List[str]]]
        :param standalone: True if this is outside the context of a GUI, False otherwise, Default False.
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaReader` subclass.

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
        and all MetaClass names

        These must have Type str and will cause the GUI to generate appropriate widgets to allow selection of these elements when used.

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaReader`, which already has an implementation of this function that ensures that settings will have the required :ref:`MetaReader` key available to users, in most cases you will need to override it to add any other settings required by your subclass. The implementation in :ref:`MetaReader` provides a single key, ``Input File``, without specifing file options. If you need additional settings, or if you want to specify the file types that will show up in related file dialogs and be accepted as inputs (recommended) you would override this to specidy options, but you **MUST** call ``settings = super().get_empty_settings(globally_available_plugins, standalone)`` first, which will ensure the existence of the "Input File" key. For example:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Input File"]["Options"] = ["ABF2 Files (*.abf)"]
            settings["Your Key"] = {"Type": float,
                                    "Value": None,
                                    "Min": 0.0,
                                    "Units": "pA"
                                    }
            return settings

        which will ensure that your have key specified above, as well as an additional key, ``Input File``, as required by readers. You can learn more about formatting input file option strings in the `PySide6 module documentation <https://doc.qt.io/qt-6/qfiledialog.html#getOpenFileName>`_.  In the case of multiple file types, supply the relevant strings as a comma-separated list in the "Options" key; poriscope will handle formatting it for :mod:`PySide6`.


        """
        settings: Dict[str, Dict[str, Any]] = {"Input File": {"Type": str}}
        return settings

    @log(logger=logger)
    def get_channel_length(
        self, channel: Optional[int] = None
    ) -> int | Dict[int, int]:  # Changed return type hint
        """
        Return the number of samples in a channel, or a dict of all of them if no channel is provided.

        :param channel: Channel number to get length for.
        :type channel: Optional[int]
        :return: Number of samples in the specified channel, or a dict of all channel lengths.
        :rtype: Union[int, Dict[int, int]]
        """
        if channel is not None:
            return self.total_channel_samples[channel]
        else:
            return self.total_channel_samples  # Changed return value

    @log(logger=logger)
    def get_samplerate(self) -> float:
        """
        Return the sampling rate for the dataset.

        :return: Sampling rate for the dataset.
        :rtype: float
        """
        return self.samplerate

    @log(logger=logger)
    def continuous_read(
        self,
        start: float = 0,
        total_length: float = 0,
        channel: int = 0,
        chunk_length: float = 0,
        raw_data: bool = False,
    ) -> npt.NDArray[np.float64]:
        """
        Read data in chunks and return it as a generator.

        :param start: Starting index in the timeseries data (default is 0).
        :type start: int
        :param total_length: Ending index in the timeseries data (default is 0, meaning end of data).
        :type total_length: int
        :param channel: channel index to analyze.
        :type channel: int
        :param chunk_length: Size of data chunks to process at a time (default is 0, auto-determined).
        :type chunk_length: int
        :param raw_data: Decide whether to rescale data or return raw adc codes
        :type raw_data: bool
        :return: Generator yielding data chunks.
        :rtype: numpy.ndarray
        """
        i = int(start * self.samplerate)
        start = int(start * self.samplerate)
        total_length = int(total_length * self.samplerate)
        chunk_length = int(chunk_length * self.samplerate)
        channel = int(channel)
        channel_length = self.get_channel_length(channel)
        if chunk_length == 0:
            chunk_length = int(
                np.minimum(self.get_samplerate(), self.get_channel_length(channel))
            )
        if total_length == 0:
            total_length = channel_length - start
        last_sample = np.minimum(channel_length, start + total_length)
        scale = None
        offset = None
        while i < last_sample:
            samples_to_load = np.minimum(chunk_length, last_sample - i)

            if (
                samples_to_load == chunk_length
                and last_sample - (i + chunk_length) < chunk_length / 2
            ):  # if we are near the end, just load it to avoid small offset errors
                samples_to_load = last_sample - i

            data = self.load_data(
                float(i / self.samplerate),
                float(samples_to_load / self.samplerate),
                channel,
                raw_data,
            )
            if raw_data:
                data, scale, offset = data
            i += len(data)
            if not raw_data:
                yield data
            else:
                yield data.astype(self.get_raw_dtype()), scale, offset

    @log(logger=logger)
    def get_channels(self) -> List[int]:  # Changed return type hint to List[int]
        """
        Return the number of channels in the reader

        :return: Number of channels in the reader
        :rtype: List[int]
        """
        channels = list(self.datamaps.keys())
        channels.sort()
        return channels  # Returns sorted keys as a list

    @log(logger=logger)
    def get_base_experiment_name(self) -> str:
        """
        Get the base name of the experiment being analyzed

        :return: name of the experiment being analyzed
        :rtype: str
        """
        return self.name_stub

    @log(logger=logger)
    def get_raw_dtype(self) -> None:
        """
        Return the data type for the raw data in files of this type

        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        """
        return self.dtype

    @log(logger=logger)
    def get_base_file(self) -> os.PathLike:
        """
        Return the full path to the file used to initiate this reader

        :return: path to the file used to initiate the reader
        :rtype: os.PathLike
        """
        return self.datafile

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        By default this simply returns ``False``, meaning that it is acceptable and thread-safe to run operations on different channels in different threads on this plugin. If such operation is not thread-safe, this function should be overridden to simply return ``True``. Most readers are thread-safe since reading from a file on disk is usually so, and therefore no override is necessary.
        """
        return False

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _validate_file_type(self, filename: os.PathLike) -> None:
        """
        Check that the file(s) being opened are of the correct type, and raise IOError if not

        :param filename: the path to one of the files to be opened
        :type filename: os.Pathlike
        :raises IOError: If the wrong type is file is fed to the plugin
        """
        pass

    @abstractmethod
    def _set_file_extension(self) -> str:
        """
        :return: the file extension
        :rtype: str

        **Purpose:** Set the file extension for the file type this reader plugin handles.

        This is a simple function that allows you to set the file extension (including the leading dot) of the file type that this reader plugin will read. It is used by downstream functions while mapping your data to assist in identifying files. It should be a single line:

        .. code-block:: python

            return ".ext"

        If you need to refer to this value again, you can access it via the class variable ``self.file_extension``.
        """
        pass

    @abstractmethod
    def _map_data(
        self, datafiles: List[os.PathLike], configs: List[dict]
    ) -> List[npt.NDArray[Any]]:
        """
        :param datafiles: List of data files to map.
        :type datafiles: List[os.PathLike]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of memmaps or numpy arrays mapped from data files.
        :rtype: List[numpy.ndarray]

        **Purpose:** Map the provided data files into an accessible format, preferably memory-mapped views.

        Using all the information provided in the implementations so far, in this function, you are asked to map the list of files provided in ``datafiles``, according to information given in ``configs``. You can assume that the lists are of equal length and that the config file at a given index corresponds to the data file at the same index. You must return a list of views into those files. We strongly encourage the use of :py:class:`~numpy.memmap` where possible, in which case you may return a list of such memmaps with length equal to the input list of filenames.

        .. warning::

            This function expects that the elements of the returned list can be indexed and sliced into like NumPy arrays, hence the suggestion to use memmaps, which avoid the need to actually load raw data into RAM before it is needed. In cases where memmap is not an option, you must still return NumPy array for each file, which may involve significant memory consumption. If this is impractical, it is possible to override this function to return, for example, a list of file handles instead, with the caveat that this will in turn require that you completely override :py:meth:`~poriscope.utils.MetaReader.MetaReader.load_data` as well to properly handle your file access method manually.
        """
        pass

    @abstractmethod
    def _set_raw_dtype(self, configs: List[dict]) -> np.dtype:
        """
        Set the data type for the raw data in files of this type

        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]

        :return: the dtype of the raw data in your data files
        :rtype: np.dtype

        **Purpose:** Inform Poriscope what NumPy datatype to expect for raw data on disk.

        This function is used to tell Poriscope what datatype to expect on disk for downstream use by :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._map_data`. You should return a NumPy dtype object. For example, if you are using a 16-bit ADC code, you might return ``np.uint16``. This is also a single-line function:

        .. code-block:: python

            return np.uint16

        If you need to refer to this value again, you can access it via the class variable ``self.dtype``. For more details on NumPy dtypes, refer to the `NumPy documentation on dtypes <https://numpy.org/doc/stable/reference/arrays.dtypes.html>`_.
        """
        pass

    @abstractmethod
    def _convert_data(
        self, data: npt.NDArray[np.int16], config: dict, raw_data: bool = False
    ) -> npt.NDArray[np.float64]:
        """
        :param data: Data to convert.
        :type data: numpy.ndarray
        :param config: Configuration dictionary for data conversion.
        :type config: dict
        :param raw_data: Decide whether to rescale data or return raw adc codes
        :type raw_data: bool

        :return: Converted data, and scale and offset if and only if raw_data is True
        :rtype: Union[Tuple[np.ndarray, float, float], np.ndarray]

        **Purpose:** Convert raw data from disk format to a usable numerical format.

        Given a numpy array of raw data extracted from one of the :py:class:`~numpy.memmap` instances you defined in the previous function along with its associated ``config`` dict, provide a means to turn this raw data into a numpy array of `~numpy.float64` double precision floats. For this purpose, if convenient, you can use the :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._scale_data` function, which will apply bitmasks, multiply data by a scaling factor, and add an offset, like so:

        .. code-block:: python

            def _scale_data(self, data: npt.NDArray[Any], copy:Optional[bool]=True, bitmask:Optional[np.uint64]=None, dtype:Optional[str]=None, scale:Optional[float]=None, offset:Optional[float]=None, raw_data:Optional[bool]=False) -> npt.NDArray[Any]:
                if bitmask == 0:
                    bitmask = None
                if not raw_data:
                    if (copy):
                        data = np.copy(data)
                    if (bitmask is not None):
                        data = np.bitwise_and(data.astype(type(bitmask)), bitmask)
                    if (dtype is not None):
                        data = data.astype(dtype)
                    if (scale is not None):
                        data *= scale
                    if (offset is not None):
                        data += offset
                    return data
                else:
                    if not dtype:
                        raise ValueError('Specify dtype to retrieve raw data')
                return data

        if ``raw_data`` is ``True``, your function must also return a scale and offset factor, like so:

        .. code-block:: python

            if raw_data:
                    return data, scale, offset
            else:
                    return data
        """
        pass

    @log(logger=logger)
    def _set_sample_rate(self) -> float:
        """
        Set the sampling rate for the reader.

        :return: the sampling rate that is applicable to the reader
        :rtype: float
        """
        samplerate = 0
        for key, val in self.configs.items():
            if samplerate == 0:
                samplerate = val[0]["samplerate"]
            else:
                if samplerate != val[0]["samplerate"]:
                    raise ValueError(
                        f"All channels must have the same samplerate, but channel {key} has samplerate {val[0]['samplerate']} while all previous channels have samplerate {samplerate}"
                    )
        if samplerate == 0:
            raise ValueError('Unable to set samplerate"')
        return float(samplerate)

    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Apply application-specific settings to the plugin, if needed.

        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaReader` that must occur after settings have been applied to the reader instance, you can override this function to add those operations, subject to the caveat below.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super()._finalize_initialization()`` **before** any additional code that you add, and take care to understand the implementation of both :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` and :py:meth:`~poriscope.utils.MetaReader.MetaReader._finalize_initialization` before doing so to ensure that you are not conflicting with those functions.
        """
        self.datafile = Path(self.settings["Input File"]["Value"])
        self.file_extension = self._set_file_extension()
        self._validate_file_extension(self.datafile)
        self._validate_file_type(self.datafile)

        # extract the active folder and filename of provided example file
        folder, file_name = os.path.split(self.datafile)

        # identify the base filename common to the whole experiment
        pattern = self._get_file_pattern(file_name)
        self.name_stub = pattern

        # get a list of all files matching the base pattern in the specified folder
        file_names = self._get_file_names(folder, pattern)

        # load config files to help decode each file into a 2D list matching the datafiles list
        configs = self._get_configs(file_names)

        self.dtype = self._set_raw_dtype(configs)

        # memory-map the data into a list of memmaps or numpy arrays
        datamaps = self._map_data(file_names, configs)

        # get a list of timestamps that encode serialization for each file, independent of channel
        time_stamps = self._get_file_time_stamps(file_names, configs)

        # get a list of channel identifiers corresponding to each file
        channel_stamps = self._get_file_channel_stamps(file_names, configs)

        # sort the files and configs into a 2D list where each row (first index) corresponds to a channel and each column (second index)
        # to a file in chronological order
        self.datafiles = self._sort_objects_by_channel_and_time(
            file_names, channel_stamps, time_stamps
        )
        self.configs = self._sort_objects_by_channel_and_time(
            configs, channel_stamps, time_stamps
        )
        self.datamaps = self._sort_objects_by_channel_and_time(
            datamaps, channel_stamps, time_stamps
        )

        # extract starting indices and channel sample counts from the mapped data
        self.file_start_indices = self._get_file_start_indices(self.datamaps)
        self.total_channel_samples = self._get_total_channel_samples(
            self.datamaps, self.file_start_indices
        )

        # run instance-specific initialization defined in subclasses for specific file types
        self.samplerate = self._set_sample_rate()

    @abstractmethod
    def _get_configs(self, datafiles: List[os.PathLike]) -> List[dict]:
        """
        :param datafiles: List of data files for which to load configurations.
        :type datafiles: List[os.PathLike]
        :return: List of configuration dictionaries.
        :rtype: List[dict]

        **Purpose:** Extract configuration metadata from dataset files.

        Given a list of filenames corresponding to the data files, construct a list of dictionaries containing any required configurations for use downstream. Your config dictionaries must have at a minimum the key `'samplerate'` in them, and the list of configs must correspond one-to-one to the provided list of data files. All files in a dataset must have the same samplerate. Your reader will use these configs to map the data on disk, so you could include information like endianness, raw data type, details of any columns within the data, etc. Aside from the required samplerate key, this can be anything.
        """
        pass

    @abstractmethod
    def _get_file_time_stamps(
        self, file_names: List[os.PathLike], configs: List[dict]
    ) -> List[Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]]:
        """
        :param file_names: List of file names to get time stamps for.
        :type file_names: List[os.PathLike]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of serialization keys for timestamps in almost any format.
        :rtype: List[Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]]

        **Purpose:** Extract time stamps for sorting files chronologically within a channel.

        Given a list of all the files in the experiment and the list of config dictionaries you defined above, extract a corresponding list of timestamps. These timestamps will be used to time-order the mapped data within each channel. The list must have the same length as both input lists and must be of a type that can be sorted into the desired time-ordering using the builtin :py:meth:`~list.sort()` method.
        """
        pass

    @abstractmethod
    def _get_file_channel_stamps(
        self, file_names: List[os.PathLike], configs: List[dict]
    ) -> List[int]:
        """
        :param file_names: List of file names to get channel stamps for.
        :type file_names: List[os.PathLike]
        :param configs: List of configuration dictionaries corresponding to data files.
        :type configs: List[dict]
        :return: List of serialization keys for channels
        :rtype: List[int]

        **Purpose:** Extract channel identifiers for grouping files by channel.

        Given a list of all the files in the experiment and the list of config dictionaries you defined above, extract a corresponding list of channel identifiers as integers. These channel indices will be used to group the mapped data by channel. The list must have the same length as both input lists and must be a list of integers.


        """
        pass

    @abstractmethod
    def _get_file_pattern(self, file_name: str) -> str:
        """
        :param file_name: File name to get the base pattern for.
        :type file_name: os.PathLike
        :return: Base pattern for matching other files.
        :rtype: str

        **Purpose:** Extract a `glob` pattern from an input filename to match all dataset files.

        When you instantiate a reader plugin, you provide a single filename as input. However, in some cases, a dataset might comprise many files. This function requires you to extract a pattern from the given filename that can be used by ``glob`` to match all files belonging to your dataset.

        If your dataset consists of only a single file, you can simply return the original filename.

        **Example:**

        Consider a scenario where your dataset files follow a pattern with channel numbers and serial numbers, such as:

        * ``experiment_1_channel_01_001.log``
        * ``experiment_1_channel_01_002.log``
        * ``experiment_1_channel_02_001.log``
        * ``experiment_1_channel_02_002.log``

        In this case, you could return a ``glob`` pattern like:

        .. code-block:: none

            experiment_1_channel_??_???.log

        This pattern assumes the channel stamp will always be two digits and the serial number always three. If the lengths of these varying parts are uncertain, a more general pattern using wildcards would be:

        .. code-block:: none

            experiment_1_channel_*_*.log

        Poriscope will use this file pattern to search the folder of the input file for other files that match the pattern. It will not search outside of that folder.

        For more information on ``glob`` patterns, refer to the `glob module documentation <https://docs.python.org/3/library/glob.html>`_.
        """
        pass

    @log(logger=logger)
    def _get_file_names(self, folder, pattern) -> List[str]:
        """
        Get a list of file names with data to map

        :param folder: File name to get the base pattern for.
        :type folder: os.PathLike
        :param pattern: pattern to match
        :type pattern: str

        :return: a list of file names
        :rtype: List[str]
        """
        return [str(f) for f in Path(folder).glob(pattern)]

    @log(logger=logger)
    def _sort_objects_by_channel_and_time(
        self,
        objects: List[Any],
        channel_numbers: List[Any],
        timestamps: List[
            Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]
        ],
    ) -> Dict[
        int,
        List[Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]],
    ]:
        """
        Sort a list of objects into a dictionary of lists, indexed by channel number.
        The objects within each channel's list are sorted by timestamp.

        :param objects: List of objects to sort.
        :type objects: List[Any]
        :param channel_numbers: List of channel numbers corresponding to objects.
        :type channel_numbers: List[int]
        :param timestamps: List of timestamps corresponding to objects.
        :type timestamps: List[Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]]
        :return: Dictionary where keys are channel numbers and values are lists of objects,
                        sorted by timestamp.
        :rtype: Dict[int, List[Union[str, int, float, datetime.datetime, datetime.date, np.datetime64]]
        :raises ValueError: If the input lists have inconsistent lengths.
        """
        if len(objects) != len(channel_numbers) or len(objects) != len(timestamps):
            raise ValueError(
                "A channel number and timestamp must be provided for every object to be sorted"
            )

        # Use int for channel numbers as keys for the final dict
        temp_dict: Dict[int, List[Any]] = {}

        for obj, channel, timestamp in zip(objects, channel_numbers, timestamps):
            # Ensure channel numbers are treated as integers.
            channel = int(channel)
            if channel not in temp_dict:
                temp_dict[channel] = []
            temp_dict[channel].append((timestamp, obj))

        # Sort each list of objects by timestamp
        for channel in temp_dict.keys():
            temp_dict[channel].sort()

        # Extract only the objects, discarding the timestamps
        for channel in temp_dict:
            temp_dict[channel] = [obj for _, obj in temp_dict[channel]]

        return temp_dict

    @log(logger=logger)
    def _scale_data(
        self,
        data: npt.NDArray[Any],
        copy: Optional[bool] = True,
        bitmask: Optional[np.uint64] = None,
        dtype: Optional[str] = None,
        scale: Optional[float] = None,
        offset: Optional[float] = None,
        raw_data: Optional[bool] = False,
    ) -> npt.NDArray[Any]:
        """
        Apply scaling and masking operations to data as needed.
                Default behavior assumes data is already scaled and does nothing.

                :param data: Data to scale.
                :type data: numpy.ndarray
                :param copy: Whether to create a copy of the data, defaults to True.
                :type copy: bool, optional
                :param bitmask: Bitmask to apply to data, defaults to None.
                :type bitmask: Optional[np.uint64], optional
                :param dtype: Desired data type after scaling, defaults to None.
                :type dtype: Optional[str], optional
                :param scale: Scaling factor, defaults to None.
                :type scale: Optional[float], optional
                :param offset: Offset to add to scaled data, defaults to None.
                :type offset: Optional[float], optional
                :param raw_data: is the data to be returned as the original type?
                :type raw_data: Optional[bool]
                :return: Scaled data.
                :rtype: numpy.NDArray[Any]
        """
        if bitmask == 0:
            bitmask = None
        if not raw_data:
            if copy:
                data = np.copy(data)
            if bitmask is not None:
                data = np.bitwise_and(data.astype(type(bitmask)), bitmask)
            if dtype is not None:
                data = data.astype(dtype)
            if scale is not None:
                data *= scale
            if offset is not None:
                data += offset
            return data
        else:
            if not dtype:
                raise ValueError("Specify dtype to retrieve raw data")
        return data

    @log(logger=logger)
    def _get_file_index(self, index: int, file_start_index: List[int]) -> int:
        """
        Get the index of the file containing the specified sample index given a 1D list (i.e. only one channel worth).

        :param index: Sample index to get file index for.
        :type index: int
        :param file_start_index: List of starting sample indices per file.
        :type file_start_index: List[int]
        :return: Index of the file containing the specified sample index.
        :rtype: int
        """
        # obtains file index corresponding to sample given a list of starting sample indices per file
        i = 0
        try:
            while index >= file_start_index[i + 1]:
                i += 1
        except IndexError:
            return i
        return i

    @log(logger=logger)
    def _get_file_start_indices(
        self, datamaps: Dict[int, List[npt.NDArray[np.float64]]]
    ) -> Dict[int, List[int]]:
        """
        Populate a dictionary of lists, keyed by channel number, that lists the starting index
        of the sample in each datamap within the global dataset.  This function now takes
        the dictionary output from _sort_objects_by_channel_and_time.

        :param datamaps: Dictionary of data maps, where keys are channel numbers.
        :type datamaps: Dict[int, List[numpy.ndarray]]
        :return: Dictionary of starting indices, keyed by channel number.
        :rtype: Dict[int, List[int]]
        """
        # Create a dictionary to store the sums, keyed by channel number
        sum_dict: Dict[int, List[int]] = {}

        for channel, row in datamaps.items():
            sum_list = [0] * len(row)  # Initialize a list for each channel
            cum_sum = 0
            for j in range(1, len(row)):
                if row[j - 1] is not None:
                    cum_sum += len(row[j - 1])
                sum_list[j] = cum_sum
            sum_dict[channel] = sum_list

        return sum_dict

    @log(logger=logger)
    def _get_total_channel_samples(
        self,
        datamaps: Dict[int, List[npt.NDArray[np.float64]]],
        file_start_indices: Dict[int, List[int]],
    ) -> Dict[int, int]:
        """
        Populate a dictionary of the number of datapoints in each channel.

        :param datamaps: Dictionary of data maps, keyed by channel number.
        :type datamaps: Dict[int, List[numpy.ndarray]]
        :param file_start_indices: Dictionary of starting indices for each file in each channel, keyed by channel number.
        :type file_start_indices: Dict[int, List[int]]
        :return: Dictionary of total channel samples, keyed by channel number.
        :rtype: Dict[int, int]
        """
        total_channel_samples: Dict[int, int] = {}

        for channel, maps in datamaps.items():
            if channel in file_start_indices:
                lengths = file_start_indices[channel]
                if maps and lengths:  # Ensure both lists are not empty
                    final_len = len(maps[-1])
                    final_start_length = lengths[-1]
                    total_channel_samples[channel] = final_len + final_start_length
                else:
                    total_channel_samples[channel] = 0  # Handle empty map/lengths
            else:
                total_channel_samples[channel] = 0

        return total_channel_samples

    @log(logger=logger)
    def _validate_file_extension(self, filename: os.PathLike) -> None:
        """
        Check that the file(s) being opened are of the correct type, and raise IOError if not

        :param filename: the path to one of the files to be opened
        :type filename: os.Pathlike
        :raises IOError: If the wrong type is file is fed to the plugin
        """
        _, ext = os.path.splitext(filename)
        if ext != self.file_extension:
            raise IOError(
                f"Invalid file extension {ext} for plugin {self.__class__.__name__}"
            )

    # Utility functions, specific to subclasses as needed

    # Utility functions, specific to subclasses as needed

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass
