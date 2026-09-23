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
import warnings
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.SerializeDecorator import serialize_channels


@inherit_docstrings
class MetaWriter(BaseDataPlugin):
    """
    What you get by inheriting from MetaWriter
    ------------------------------------------

    :ref:`MetaWriter` is the base class for writing the data corresponding to events found by a :ref:`MetaEventFinder` subclass instance events within your nanopore data and represents the first analysis and transformation step. :ref:`MetaWriter` depends on and is linked at instantiation to a :ref:`MetaEventFinder` subclass instance that serves as its source of nanopore data, meaning that creating and using one of these plugins requires that you first instantiate an eventfinder.

    Poriscope ships with :ref:`SQLiteEventWriter`, a subclass of :ref:`MetaWriter` already that writes data to a :mod:`sqlite3` format. While additional subclasses can write to almost any format you desire, we strongly encourage standardization around this format. Think twice before creating additional subclasses of this base class. It is not sufficient to write just a :ref:`MetaWriter` subclass. In addition to this base class, you will also need a paired :ref:`MetaEventLoader` subclass to read back and use the data you write to any other format for downstream analysis.

    .. warning::

        We strongly encourage standardization on the :ref:SQLiteDBWriter subclass, so please think carefully before creating other formats.

    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize and set up output environment, save metadata for subclasses.
        """
        super().__init__(settings)
        self.written: Dict[int, int] = {}
        self.output_dtype = self._set_output_dtype()
        self.rejected: Dict[int, Dict[str, int]] = {}

        self.eventfinder: MetaEventFinder
        self.output_file_name: Path

    # public API, MUST be implemented by subclasses
    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion, as well as at the end of any batch write operation, to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. Your files should be closed here, if they are not in your writing step. If no such operation is needed, it suffices to ``pass``. In the case of writers, this method is also called with a specific channel identifier at the end of any batch write operation (a call to :py:meth:`~poriscope.utils.MetaWriter.MetaWriter.commit_events`), and so should be used to ensure atomic write operations if possible.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else close all of them. Most writers will create permanent state changes in the form of data written to the output file, that should be deleted or otherwise set up for subsequent overwrite when this function is called.

        :param channel: channel ID
        :type channel: Optional[int]
        """
        pass

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Type is required; Value may be omitted or set to None, both meaning there is no default and the user must supply one. All values provided must be consistent with Type.

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

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :raises KeyError: if no :ref:`MetaEventFinder` has been instantiated and standalone is False
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
        """
        eventfinder_options = None
        if globally_available_plugins:
            eventfinder_options = globally_available_plugins.get("MetaEventFinder")
        if eventfinder_options == [] and not standalone:
            raise KeyError(
                "Cannot instantiate a Writer without first instantiating an EventFinder"
            )
        elif standalone:
            eventfinder_options = None

        settings: Dict[str, Dict[str, Any]] = {
            "MetaEventFinder": {
                # A script holds the parent object and has no controller to resolve a
                # name, so standalone declares the class it must be an instance of.
                "Type": MetaEventFinder if standalone else str,
                "Value": eventfinder_options[0] if eventfinder_options else "",
                "Options": eventfinder_options,
            },
            "Output File": {"Type": str, "Options": ["All Files (*.*)"]},
        }
        return settings

    @serialize_channels
    @log(logger=logger)
    def commit_events(self, channel: int) -> Generator[float, Optional[bool], None]:
        """
        Create a generator that will loop through events in self.eventfinder in channel
        and call self._write_data() to commit it to file

        :param channel: the index of the channel to commit
        :type channel: int
        :yield: the progress of the interator, normalized to [0,1]
        :ytype: float
        """
        yield from self._commit_events(channel)

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        By default, writer plugins are assumed to not be threadsafe and will run in serial mode when called from the poriscope GUI. If you want to change this, you must also ensure that the parent eventfinder object is threadsafe for pulling data from it. You can play it safe by calling ``self.eventfinder.force_serial_channel_operations()``, but it is possible that an eventfinder is not threadsafe for eventfinding but may be for pulling the events found for writing. **How this is enforced:** returning ``True`` means *this plugin instance's* channel operations must not overlap each other; different instances still run concurrently. The guard is taken by the plugin itself, inside its own generator, via :py:func:`~poriscope.utils.SerializeDecorator.serialize_channels` and :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.serialize_channel_operations`, and the lock is held for the whole run of that generator. It used to be enforced by the analysis tab's model using a lock scoped to the model rather than to the plugin, which meant two tabs driving the same plugin took different locks and did not serialize at all.

        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool
        """
        return True

    @log(logger=logger)
    def report_channel_status(
        self, channel: Optional[int] = None, init: bool = False
    ) -> str:
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
            for ch in self.eventfinder.get_channels():
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
                report += f"/{self.eventfinder.get_num_events_found(channel)} events"

                if channel in self.rejected:
                    report += " Rejected Events:\n"
                    report += "\n".join(
                        f"{key}: {value}"
                        for key, value in self.rejected[channel].items()
                    )
                return report

    @log(logger=logger)
    def get_output_file_name(self) -> Path:
        """
        get the name of the output file
        """
        return self.output_file_name

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _write_data(
        self,
        event: Dict[str, Any],
        channel: int,
        index: int,
        raw_data: bool = False,
        abort: Optional[bool] = False,
        last_call: Optional[bool] = False,
    ) -> bool:
        """
        **Purpose**: Append a single event's data and metadata to the output file.

        Given one event, write it to the active file for ``channel`` (appending to an
        existing file in the case of atomic operations) and return True if that
        succeeds. If the write fails, raise: raising does not crash poriscope, which
        carries on to the next event and files the exception's text as that event's
        rejection reason for downstream reporting.

        ``event`` is the dict :meth:`MetaEventFinder.get_single_event_data` produces, and
        is passed through whole rather than exploded into arguments - this took thirteen
        positional parameters until 2.0.0, of which ten were its keys. Its keys are:

        - ``data`` - the event's samples, as a 1D numpy array.
        - ``start_sample`` - index of the first sample *of the event itself*, not of the
          padding before it, relative to the start of the channel.
        - ``padding_before`` / ``padding_after`` - samples of context included on each
          side. ``data`` therefore spans
          ``start_sample - padding_before`` to ``start_sample + len(event) + padding_after``.
        - ``baseline_mean`` / ``baseline_std`` - the local baseline the event sits on.
        - ``scale`` / ``offset`` - the factors that convert ``data`` to pA, present only
          when ``raw_data`` is True; both are None otherwise.

        Treat a missing key as a programming error and raise, rather than substituting a
        default: a silently defaulted padding writes an event whose samples do not line
        up with its own metadata.

        :param event: One event, as ``get_single_event_data`` builds it.
        :type event: Dict[str, Any]
        :param channel: The channel the event belongs to.
        :type channel: int
        :param index: The event's index within that channel.
        :type index: int
        :param raw_data: True when ``data`` holds unscaled ADC codes rather than pA.
        :type raw_data: bool
        :param abort: True to discard the channel's uncommitted batch and stop.
        :type abort: Optional[bool]
        :param last_call: True when this is the final event of the channel.
        :type last_call: Optional[bool]
        :return: True if the event was written.
        :rtype: bool
        """
        pass

    @abstractmethod
    def _set_output_dtype(self) -> str:
        """
        **Purpose**: Set the datatype of the data to be saved for each event.

        This function returns a string encoding a numpy datatype that tells the writer in what format the data should be stored in the database. If the output dtype exactly matches the intput dtype, the plugin will attempt to store raw data without any precision loss. In the case of a mismatch, it is not possible for poriscope to guarantee that there is no loss of precision between the input and output operation. If there is any dount, we suggest that use of double precision floating point numbers (``"<f8"``) will not incur any meaningful loss of precision in the vast majority of operations regardless of input type.

        :return: A string representing a :mod:`numpy` dtype
        :rtype: str
        """
        pass

    @abstractmethod
    def _initialize_database(self, channel: int) -> None:
        """
        **Purpose**: Initialize a database for subsequent write operations.

        This function is called at the start of a write operation and is used to do anything you need to do in order to open the output file for writing. You are responsible for checking whether such an operation is needed (for example, by setting an appropriate flag to avoid duplicate innitialization). Note that this operation will be called for each channel and you must ensure that any initializations operations are threadsafe if you are not forcing serial channel operations (see :py:meth:`~poriscope.utils.MetaWriter.MetaWriter.force_serial_channel_operations`).

        We strongly encourage atomic operations by ensuring that any file handles opened in this function are later closed in :py:meth:`~poriscope.utils.MetaWriter.MetaWriter.close_resources` which will be called at the end of any batch write operation.

        :param channel: the channel for which to initialize the database
        :type channel: int
        """
        pass

    @abstractmethod
    def _write_channel_metadata(self, channel: int) -> None:
        """
        **Purpose**: Save any metadata required at the level of channels (for example, samplerate).

        Given a channel index, write any required metadata for that channel. Typically this is done once per channel on the first related write operation. Remember to close any file handles used either in this function or :py:meth:`~poriscope.utils.MetaWriter.MetaWriter.close_resources` depending on whether you need to keep those resources open for the event writing step that follows.

        :param channel: int indicating which output to flush
        :type channel: int
        """
        pass

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed

    @log(logger=logger)
    def _commit_events(self, channel: int) -> Generator[float, Optional[bool], None]:
        """
        Create a generator that will loop through events in self.eventfinder in channel
        and call self._write_data() to commit it to file

        :param channel: the index of the channel to commit
        :type channel: int
        :raises Exception: if the output file cannot be opened, if writing channel metadata fails unexpectedly, or if an unrecoverable error occurs while iterating events
        :yield: the progress of the interator, normalized to [0,1]
        :ytype: float
        """

        def lookahead_generator(
            gen: Generator[Any, None, None],
        ) -> Generator[Tuple[Any, bool], None, None]:
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
        except Exception:
            # Raised rather than reported as a finished run. This used to log at
            # INFO and then `yield 1.0; return`, which EventWorker turns into a
            # 100% progress bar and "Generator finished." at INFO - so a writer
            # that could not open its output file was indistinguishable from one
            # that had written everything, and the user was left with an empty
            # database and no indication anything had gone wrong. The sibling
            # handler below, for channel-metadata failures, has always raised;
            # EventWorker's own `except Exception` arm reports a raised failure
            # with a traceback and still emits the progress-bar completion value.
            self.logger.error(
                f"Unable to open output file for channel {channel}", exc_info=True
            )
            self.close_resources(channel)
            raise

        try:
            self._write_channel_metadata(channel)
        except Exception as e:
            self.logger.error(
                f"Unexpected error writing channel metadata for channel {channel}: {e}",
                exc_info=True,
            )
            self.close_resources(channel)
            raise
        try:
            self.written[channel] = 0
            self.rejected[channel] = {}
            num_events = self.eventfinder.get_num_events_found(channel)
            if num_events == 0:
                self.logger.info(
                    f"No events found in channel {channel}, skpping writing"
                )
                yield 1.0
                return
            if not self.eventfinder.get_eventfinding_status(channel):
                self.logger.info(
                    f"Eventfinding has not completed in channel {channel}, skipping writing"
                )
                yield 1.0
                return
            source_dtype = self.eventfinder.get_dtype()
            raw_data = False
            if source_dtype == self.output_dtype:
                raw_data = True

            event_generator = self.eventfinder.get_event_data_generator(
                channel, data_filter=None, rectify=False, raw_data=raw_data
            )

            index = 0
            abort = False
            try:
                for event, last_call in lookahead_generator(event_generator):
                    try:
                        abort_opt = yield index / num_events
                        abort = bool(abort_opt)
                        try:
                            success = self._write_data(
                                event,
                                channel,
                                index,
                                raw_data,
                                abort=abort,
                                last_call=last_call,
                            )
                            if abort is True:
                                break
                        except Exception as e:
                            self.rejected[channel][str(e)] = (
                                self.rejected[channel].get(str(e), 0) + 1
                            )
                            self.logger.info(
                                f"Unable to write event data in channel {channel}: {str(e)}. Attempting to continue but data may be incomplete and will require manual verification or an overwrite"
                            )
                            continue
                        else:
                            if success:
                                self.written[channel] += 1

                    except StopIteration:
                        break
                    index += 1
            except Exception:
                raise
            finally:
                if abort is True:
                    # Guarded because reset_channel now raises on failure and this
                    # is a finally block, where an unguarded raise would replace
                    # whatever exception was already propagating. written is left
                    # as it stands on failure rather than zeroed, so it does not
                    # claim a clean slate the output never got.
                    try:
                        self.reset_channel(channel)
                        self.written[channel] = 0
                    except Exception:
                        self.logger.error(
                            f"Abort requested but channel {channel} could not be "
                            "reset; the output still holds its partial events.",
                            exc_info=True,
                        )
        finally:
            # Guarded for the same reason: close_resources raises if the commit it
            # performs fails, and that is the only commit for a batch that ends
            # here, so the failure must be reported without masking an in-flight
            # exception.
            try:
                self.close_resources(channel)
            except Exception:
                self.logger.error(
                    f"Failed to finalize the output for channel {channel}; events "
                    "written in this batch may not have been saved.",
                    exc_info=True,
                )

    @log(logger=logger)
    def _validate_param_types(self, settings: dict) -> None:
        """
        Validate that the filter_params dict contains correct data types

        :param settings: A dict specifying the parameters of the filter to be created. Required keys depend on subclass.
        :type settings: dict
        :raises TypeError: If the filter_params parameters are of the wrong type
        """
        super()._validate_param_types(settings)
        if settings:
            for param, val in settings.items():
                if param == "MetaEventFinder":
                    if not issubclass(val["Value"].__class__, MetaEventFinder):
                        raise TypeError(
                            "MetaEventFinder key must have as value an object that inherits from MetaEventFinder"
                        )

    @log(logger=logger)
    def _rescale_data_to_adc(
        self,
        data: npt.NDArray[np.number],
        scale: Optional[float] = None,
        offset: Optional[float] = None,
        raw_data: bool = False,
        dtype: npt.DTypeLike = np.int16,
        adc_min: int = np.iinfo(np.int16).min,
        adc_max: int = np.iinfo(np.int16).max,
    ) -> tuple[npt.NDArray[np.number], Optional[float], Optional[float]]:
        """
        Rescale data to int16 Chimera VC100-style adc codes.

        For other adc code types or encoding schemes, this function should be overridden. Default to Chimera-style conversion.

        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: npt.NDArray[np.number]
        :param scale: Float indicating scaling between provided data type and encoded form for storage. If None, scale is calculated based on the data to maximally use the available adc range.
        :type scale: Optional[float]
        :param offset: Float indicating offset between provided data type and encoded form for storage. If None, offset is calculated based on the data to maximally use the available adc range.
        :type offset: Optional[float]
        :param raw_data: Boolean, True means to simply write data as-is to file, False indicates to first rescale it. Default False.
        :type raw_data: bool
        :param dtype: Numpy dtype to use for storage. Defaults to 16-bit signed int.
        :type dtype: npt.DTypeLike
        :param adc_min: Integer encoding the minimum adc code for the adc conversion.
        :type adc_min: int
        :param adc_max: Integer encoding the maximum adc code for the adc conversion.
        :type adc_max: int
        :raises ValueError: If scale cannot be computed from the data.
        :raises IOError: If raw_data is True but scale or offset is not provided.
        :return: Tuple containing rescaled data as numpy array, scale factor, and offset.
        :rtype: tuple[npt.NDArray[np.number], Optional[float], Optional[float]]
        """
        if not raw_data:
            if scale is not None and offset is not None:
                data = (data - offset) / scale
            else:
                warnings.warn(
                    "Rescaling data to ADC codes without providing a gain setting may result in loss of precision!",
                    stacklevel=2,
                )
                data_max = np.max(data)
                data_min = np.min(data)
                data_range = data_max - data_min
                adc_range = adc_max - adc_min
                scale = data_range / adc_range
                if scale is None:
                    raise ValueError("Scale could not be computed.")
                offset = data_max - scale * adc_max
                data = (data - offset) / scale
        else:
            if scale is None or offset is None:
                raise IOError(
                    "Scale and offset must be provided in order to save raw data"
                )
        return data.astype(dtype), scale, offset

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters required to configure this writer.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    @abstractmethod
    def _finalize_initialization(self) -> None:
        """
        **Purpose:** Perform generic class construction operations after settings are applied. This function is called at the end of the :py:meth:`~poriscope.utils.MetaFilter.MetaFilter.apply_settings` function to perform additional initialization specific to the algorithm being implemented.

        Perform any initialization tasks required after settings are applied. You can access the values in the settings dict provided as needed in the class variable ``self.settings[key]['Value']`` where ``key`` corresponds to the keys in the provided settings dict (as provided to :py:meth:`~poriscope.utils.MetaFilter.MetaFilter.apply_settings` or to the constructor). You can freely make class variables here and you can assume (if using the poriscope app) that this will only be called from a single thread. .

        Should Raise if initialization fails.
        """
        pass

    # private API continued, can be implemented by subclasses, but default behavior is suitable for most use cases

    # Utility functions, specific to subclasses as needed
