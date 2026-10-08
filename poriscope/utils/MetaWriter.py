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
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

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
    def commit_events(
        self, channel: int, overwrite: bool = False
    ) -> Generator[float, Optional[bool], None]:
        """
        Create a generator that will loop through events in self.eventfinder in channel
        and call self._write_data() to commit it to file

        If the output already holds ``channel`` (see
        :meth:`get_committed_experiment_name`), the commit is refused with
        ``ValueError`` unless ``overwrite`` is True, in which case the channel is reset
        first. Writing into it anyway would mix two runs' events in one channel. The
        Raw Data tab asks the user before passing ``overwrite``.

        :param channel: the index of the channel to commit
        :type channel: int
        :param overwrite: replace the channel's events if the output already holds it
        :type overwrite: bool
        :yield: the progress of the interator, normalized to [0,1]
        :ytype: float
        """
        yield from self._commit_events(channel, overwrite)

    @log(logger=logger)
    def get_committed_experiment_name(self, channel: int) -> Optional[str]:
        """
        Name the experiment the output already holds ``channel`` under, if it does.

        Asked before a commit, so it must not create the output file. The base returns
        None, meaning "this writer's output never already holds a channel"; override it
        in a writer that can write into an existing file, so :meth:`commit_events` can
        refuse to mix two runs in one channel.

        :param channel: the channel to look up
        :type channel: int
        :return: the stored experiment name, or None if the output does not hold the channel
        :rtype: Optional[str]
        """
        return None

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

        ``data`` is always in pA, exactly as the reader's ``load_data`` returns it, so it is
        consistent with the ``baseline_mean`` stored beside it. Until 2.0.0 a writer whose
        output type matched the reader's source type was handed unscaled samples with
        ``scale`` and ``offset`` keys and a ``raw_data`` flag; that path is gone.

        Treat a missing key as a programming error and raise, rather than substituting a
        default: a silently defaulted padding writes an event whose samples do not line
        up with its own metadata.

        :param event: One event, as ``get_single_event_data`` builds it.
        :type event: Dict[str, Any]
        :param channel: The channel the event belongs to.
        :type channel: int
        :param index: The event's index within that channel.
        :type index: int
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

        This function returns a string encoding a numpy datatype that tells the writer in what format the event data, which is always in pA, should be stored in the database. Double precision floating point (``"<f8"``) loses no meaningful precision for any input type, and is what the shipped writer uses.

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
    def _commit_events(
        self, channel: int, overwrite: bool = False
    ) -> Generator[float, Optional[bool], None]:
        """
        Create a generator that will loop through events in self.eventfinder in channel
        and call self._write_data() to commit it to file

        Each event is read by its index, inside the same per-event handler as the write,
        so an event the finder cannot read is rejected under its own reason and the commit
        carries on; its ``event_id`` is its index whether or not earlier events failed.

        :param channel: the index of the channel to commit
        :type channel: int
        :param overwrite: replace the channel's events if the output already holds it
        :type overwrite: bool
        :raises ValueError: if the output already holds the channel and ``overwrite`` is False
        :raises Exception: if the output file cannot be opened, if writing channel metadata fails unexpectedly, or if an unrecoverable error occurs while iterating events
        :yield: the progress of the interator, normalized to [0,1]
        :ytype: float
        """
        # Reset before anything can raise, so a refused commit reports what it wrote
        # (nothing) rather than the previous commit's tally.
        self.written[channel] = 0
        self.rejected[channel] = {}
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

        # After _initialize_database, which migrates an existing file's triggers before
        # anything is deleted from it.
        if self.get_committed_experiment_name(channel) is not None:
            if not overwrite:
                self.close_resources(channel)
                raise ValueError(
                    f"Channel {channel} already holds events in "
                    f"{self.get_output_file_name()}; commit it with overwrite=True to "
                    "replace them, or choose a new output file"
                )
            self.reset_channel(channel)

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
            abort = False
            try:
                for index in range(num_events):
                    abort_opt = yield index / num_events
                    abort = bool(abort_opt)
                    try:
                        event = self.eventfinder.get_single_event_data(
                            channel, index, data_filter=None, rectify=False
                        )
                        success = self._write_data(
                            event,
                            channel,
                            index,
                            abort=abort,
                            last_call=index == num_events - 1,
                        )
                    except Exception as e:
                        self.rejected[channel][str(e)] = (
                            self.rejected[channel].get(str(e), 0) + 1
                        )
                        self.logger.info(
                            f"Unable to write event data in channel {channel}: {str(e)}. Attempting to continue but data may be incomplete and will require manual verification or an overwrite"
                        )
                    else:
                        if abort is False:
                            if success:
                                self.written[channel] += 1
                            else:
                                reason = "Event not stored by the writer"
                                self.rejected[channel][reason] = (
                                    self.rejected[channel].get(reason, 0) + 1
                                )
                    if abort is True:
                        break
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
