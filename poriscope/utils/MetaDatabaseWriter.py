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

import logging
import traceback
from abc import abstractmethod
from typing import Any, Dict, Generator, List, Optional, Union

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFitter import MetaEventFitter


@inherit_docstrings
class MetaDatabaseWriter(BaseDataPlugin):
    """
    What you get by inheriting from MetaDatabaseWriter
    --------------------------------------------------

    :ref:`MetaDatabaseWriter` is the base class for writing the metadata corresponding to events fitted by a :ref:`MetaEventFitter` subclass instance and is the end of most poriscope analysis workflows prior to post-processing. :ref:`MetaDatabaseWriter` depends on and is linked at instantiation to a :ref:`MetaEventFitter` subclass instance that serves as its source of nanopore data, meaning that creating and using one of these plugins requires that you first instantiate an eventfitter.

    Poriscope ships with a subclass of :ref:`MetaDatabaseWriter` already that writes data to a :mod:`sqlite3` format. While additional subclasses can write to almost any format you desire, we strongly encourage standardization around this format. Think twice before creating additional subclasses of this base class. It is not sufficient to write just a :ref:`MetaWriter` subclass. In addition to this base class, you will also need a paired :ref:`MetaEventLoader` subclass to read back and use the data you write to any other format for downstream analysis.

    .. warning::

        We strongly encourage standardization on the :ref:SQLiteDBWriter subclass, so please think carefully before creating other formats. If you do, your database must be queryable with standard SQL and be able to implement everything required by :ref:`MetaDatabaseLoader` in order to be compatible with the poriscope loaders and workflows, and you will need to also create an associated database loader

    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None):
        """
        Initialize and set up output environment, save metadata for subclasses.
        """
        super().__init__(settings)
        self.database_initialized = False
        self.written: Dict[int, int] = {}
        self.rejected: Dict[int, Dict[str, int]] = {}

    # public API, MUST be implemented by subclasses
    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion, as well as at the end of any batch write operation, to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. Your files should be flushed and closed here, if they are not in your writing step. If no such operation is needed, it suffices to ``pass``. In the case of writers, this method is also called with a specific channel identifier at the end of any batch write operation (a call to :py:meth:`~poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter.write_events`), and so can be used to ensure atomic write operations if possible.
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else close all of them. Most database writers will create permanent state changes in the form of data written to the output file, that should be deleted or otherwise set up for subsequent overwrite when this function is called.
        """
        pass

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        By default, writer plugins are assumed to not be threadsafe and will run in serial mode when called from the poriscope GUI. If you want to change this, you must also ensure that the parent eventfitter object is threadsafe for pulling data from it. You can play it safe by calling ``self.eventfitter.force_serial_channel_operations()``.
        """
        return True

    @log(logger=logger)
    def write_events(self, channel: int) -> Generator[float, Optional[bool], None]:
        """
        Create a generator that will loop through events in self.eventfitter in channel
        and call self._write_data() to commit it to file

        :param channel: the index of the channel to commit
        :type channel: int

        :return: the progress of the generator, normalized to [0,1]
        :rtype: Generator[float, Optional[bool], None]
        """

        def lookahead_generator(gen):
            try:
                current = next(gen)
            except StopIteration:
                return
            while True:
                try:
                    next_item = next(gen)
                    yield current, False  # False means there's more
                    current = next_item
                except StopIteration:
                    yield current, True  # True means this is the last item
                    break

        try:
            self._initialize_database(channel)
        except Exception as e:
            self.close_resources(channel)
            self.logger.info(
                f"Unable to open file: {type(e).__name__}: {e}, Traceback: {traceback.format_exc()}"
            )
            yield 1.0
            return

        try:
            self._write_experiment_metadata(channel)
        except Exception as e:
            self.close_resources(channel)
            self.logger.error(
                f"Unexpected error writing experimental metadata for channel {channel}: {e}",
                exc_info=True,
            )
            raise

        try:
            self._write_channel_metadata(channel)
        except Exception as e:
            self.close_resources(channel)
            self.logger.error(
                f"Unexpected error writing channel metadata for channel {channel}: {e}",
                exc_info=True,
            )
            raise

        if not self.eventfitter.get_eventfitting_status(channel):
            self.close_resources(channel)
            raise ValueError(
                f"Eventfitting has not completed in channel {channel} unable to write events"
            )

        index = 0
        num_events = self.eventfitter.get_num_events(channel)
        if num_events == 0:
            self.close_resources(channel)
            self.logger.warning(
                f"No events found for channel {channel}. Nothing to write."
            )
            yield 1.0
            return

        event_generator = self.eventfitter.get_event_metadata_generator(channel)
        self.rejected[channel] = {}
        self.written[channel] = 0
        abort = False
        index = 1
        try:
            for (
                event_metadata,
                sublevel_metadata,
                filtered_data,
                raw_data,
                fit_data,
            ), last_call in lookahead_generator(event_generator):
                if (
                    event_metadata is not None
                    and sublevel_metadata is not None
                    and raw_data is not None
                    and filtered_data is not None
                    and fit_data is not None
                ):
                    abort_opt: Optional[bool] = yield index / num_events
                    abort = bool(abort_opt)
                    try:
                        if abort is True:
                            break
                        success = self._write_event(
                            channel,
                            event_metadata,
                            sublevel_metadata,
                            filtered_data,
                            raw_data,
                            fit_data,
                            abort=abort,
                            last_call=last_call,
                        )
                        if success:
                            self.written[channel] += 1
                        else:
                            raise IOError("Cannot Overwrite Existing Event")
                    except Exception as e:
                        self.rejected[channel][str(e)] = (
                            self.rejected[channel].get(str(e), 0) + 1
                        )
                index += 1
        except StopIteration:
            pass
        finally:
            if abort is True:
                self.reset_channel(channel)
                self.written[channel] = 0
            self.close_resources(channel)

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed
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
            for ch in self.eventfitter.get_channels():
                report += self.report_channel_status(ch, init)
            return report
        else:
            if init:
                return ""
            else:
                report = f"\nCh{channel}: "
                if channel in self.written:
                    report += f"Wrote {self.written[channel]}"
                else:
                    report += "Wrote 0"  # Or any other default value
                report += f"/{self.eventfitter.get_num_events(channel)} events"

                if channel in self.rejected:
                    report += " Rejected Events:\n"
                    report += "\n".join(
                        f"{key}: {value}"
                        for key, value in self.rejected[channel].items()
                    )
                return report

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _write_event(
        self,
        channel: int,
        event_metadata: Dict[str, Union[int, float, str, bool]],
        sublevel_metadata: Dict[str, List[Union[int, float, str, bool]]],
        event_data: npt.NDArray[np.float64],
        raw_data: npt.NDArray[np.float64],
        fit_data: npt.NDArray[np.float64],
        abort: Optional[bool] = False,
        last_call: Optional[bool] = False,
    ) -> bool:
        """
        :param channel: identifier for the channel to write events from
        :type channel: int
        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: numpy.ndarray
        :param event_metadata: a dict of metadata associated to the event
        :type event_metadata: Dict[str, Union[int, float, str, bool]]
        :param event_metadata: a dict of lists of metadata associated to sublevels within the event. You can assume they all have the same length.
        :type event_metadata: Dict[str, List[Union[int, float, str, bool]]]
        :param event_data: the raw data for the event (not filtered)
        :type event_data: npt.NDArray[np.float64]
        :param raw_data: A numpy array of raw event data to be stored as binary in the database.
        :type raw_data: npt.NDArray[np.float64]
        :param fit_data: A numpy array of fitted event data to be stored as binary in the database.
        :type fit_data: npt.NDArray[np.float64]
        :param abort: True if an abort request was issued in the caller, perform cleanup as needed
        :type abort: Optional[bool]
        :param last_call: True if this is the last time the function will be called, commit to file and clean up as needed
        :type last_call: Optional[bool]

        :return: True on successful write, False on failure or ignore
        :rtype: bool

        **Purpose:** Write a single event worth of data and metadata to the database.

        Given all of the event information above, write whatever subset you want to save to the database for both event metadata and sublevel metadata for each event. We strongly encourage atomic operations, but given event volume, you might consider committing or flushing events only every few hundred events, or opening a file handle for writing the first time this is called and using the open handle for subsequent writes. Ensure that the ``events`` table has a refernece to the ``channels`` and ``experiments`` tables, and that the ``sublevels`` tables has a way to reference both of those and the ``events`` table for the parent event.
        """
        pass

    @abstractmethod
    def _write_experiment_metadata(self, channel: Optional[int] = None) -> None:
        """
        :param channel: int indicating which output to flush
        :type channel: int

        **Purpose:** Write any information you need to save about the experiment itself.

        Given an optional channel argument, write any experiment level information (for example, as provided by the user in the settings dict) to the database files you created in :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._initialize_database`.
        """
        pass

    @abstractmethod
    def _write_channel_metadata(self, channel: int) -> None:
        """
        :param channel: int indicating which output to flush
        :type channel: int

        **Purpose:** Write any information you need to save about the channel

        Given a channel, write any channel level information (for example, as provided by the user in the settings dict, or the associated samplerate) to the database files you created in :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._initialize_database`. Your ``channels`` table in yout database should share a key with ``experiments`` or ahev some other way of cross-referencing channels to experiments in cases where experiments can have many channels.
        """
        pass

    @abstractmethod
    def _initialize_database(self, channel: Optional[int] = None) -> None:
        """
        :param channel: int indicating which output to flush
        :type channel: Optional[int]

        **Purpose:** initialize your database for writing

        In this function, do whatever you need to do in order to prepare your database for writing data to it. This is called at the start of a batch write operation, with an optional channel argument. In the case of a single database file you can ignore channel and simply create the file and database schema. In the case of a single file per channel, you might open a file handle associated to each channel and write any top-level metadata required. We strongly encourage atomic operations, so that file handles are closed in the same function they are opened wherever possible to avoid trailing file handles in the event of an unrecoverable exception.
        """
        pass

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaReader` that must occur after settings have been applied to the reader instance, you can override this function to add those operations, subject to the caveat below.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super()._finalize_initialization()`` **before** any additional code that you add, and take care to understand the implementation of both :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` and :py:meth:`~poriscope.utils.MetaDatabaseWriter.MetaDatabaseWriter._finalize_initialization` before doing so to ensure that you are not conflicting with those functions.
        """
        self.eventfitter = self.settings["MetaEventFitter"]["Value"]

    @log(logger=logger)
    def _validate_param_types(self, settings: dict) -> None:
        """
        Validate that the filter_params dict contains correct data types

        param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        super()._validate_param_types(settings)
        if settings:
            for param, val in settings.items():
                if param == "MetaEventFitter":
                    if not issubclass(val["Value"].__class__, MetaEventFitter):
                        raise TypeError(
                            "MetaEventFitter key must have as value an object that inherits from MetaEventFitter"
                        )

    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        This function must implement returning of a dictionary of settings required to initialize the writer, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaWriter`, which already has an implementation of this function that ensures that settings will have the required :ref:`MetaEventFinder` key and ``Output File`` key available to users, in most cases you will need to override it to add any other settings required by your subclass. If you need additional settings, which you almost certainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Output File"]["Options"] = [
                                    "SQLite3 Files (*.sqlite3)",
                                    "Database Files (*.db)",
                                    "SQLite Files (*.sqlite)",
                                    ]
            settings["Experiment Name"] = {"Type": str}
            settings["Voltage"] = {"Type": float, "Units": "mV"}
            settings["Membrane Thickness"] = {"Type": float, "Units": "nm", "Min": 0}
            settings["Conductivity"] = {"Type": float, "Units": "S/m", "Min": 0}
            return settings

        which will ensure that your have the 4 keys specified above, as well as two additional keys, ``MetaReader`` and ``Output File``. By default, it will accept any file type as output, hence the specification of the ``Options`` key for the relevant plugin in the example above.
        """
        eventfitter_options = None
        if globally_available_plugins:
            eventfitter_options = globally_available_plugins.get("MetaEventFitter")
        if eventfitter_options == [] and not standalone:
            raise KeyError(
                "Cannot instantiate a DatabaseWriter without first instantiating an EventFitter"
            )
        elif standalone:
            eventfitter_options = None

        settings: Dict[str, Dict[str, Any]] = {
            "MetaEventFitter": {
                "Type": str,
                "Value": (
                    eventfitter_options[0] if eventfitter_options is not None else ""
                ),
                "Options": eventfitter_options,
            },
            "Output File": {"Type": str, "Options": ["All Files (*.*)"]},
        }
        return settings

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    # Utility functions, specific to subclasses as needed
