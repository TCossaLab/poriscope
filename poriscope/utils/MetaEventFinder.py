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
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaReader import MetaReader


@inherit_docstrings
class MetaEventFinder(BaseDataPlugin):
    """
    :ref:`MetaEventFinder` is the base class for finding events within your nanopore data and represents the first analysis and transformation step. :ref:`MetaEventFinder` depends on and is linked at instantiation to a :ref:`MetaReader` subclass instance that serves as its source of nanopore data, meaning that creating and using one of these plugins requires that you first instantiate a reader. :ref:`MetaEventFinder` can in turn be the child object of :ref:`MetaWriter` subclass isntance for downstream saving of the data found by a instance of a subclass of :ref:`MetaEventFinder`.

    What you get by inheriting from MetaEventFinder
    -----------------------------------------------

    :ref:`MetaEventFinder` provides a common and intuitive API through which to identify segments of a nanopore timeseries that represent events (whatever that means for you) and flag them for writing to disk, excluding the uninteresting parts. In practice, this means that the size of nanopore data can be reduced by up to 1000x by keeping only the segments that matter. This operation is a precursor to downstream analysis, which operates only on the data segments flagged by subclasses of this base class.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None) -> None:
        """
        Initialize the MetaEventFinder instance.
        """
        super().__init__(settings)
        self.num_events_found: Dict[int, int] = {}
        self.event_starts: Dict[int, List[int]] = {}
        self.event_ends: Dict[int, List[int]] = {}
        self.padding_before: Dict[int, List[int]] = {}
        self.padding_after: Dict[int, List[int]] = {}
        self.baseline_means: Dict[int, List[float]] = {}
        self.baseline_stds: Dict[int, List[float]] = {}
        self.rejected_data: Dict[int, float] = {}
        self.accepted_data: Dict[int, float] = {}
        self.rejected_events: Dict[int, Dict[str, int]] = {}
        self.eventfinding_finished: Dict[int, bool] = {}
        self.reader: Optional[MetaReader] = None

    # public API, must be overridden by subclasses
    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: the channel identifier
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them (taking care to respect thread safety if necessary). If no such operation is needed, it suffices to ``pass``.
        """
        pass

    # public API, should generally be left alone by subclasses
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
            for ch in self.get_channels():
                report += self.report_channel_status(ch, init)
            return report
        else:
            if init:
                return ""
            else:
                if self.eventfinding_finished.get(channel):
                    report = (
                        f"\nCh{channel}: Found {self.num_events_found[channel]} events"
                    )
                    if self.rejected_data.get(channel):
                        report += (
                            f"\nAccepted {self.accepted_data[channel]:.1f}s of data"
                        )
                        if self.rejected_data[channel] > 0:
                            report += (
                                f"\nRejected {self.rejected_data[channel]:.1f}s of data"
                            )
                    if self.rejected_events.get(channel):
                        report += "\nRejected Events:\n"
                        report += "\n".join(
                            f"{key}: {value}"
                            for key, value in self.rejected_events[channel].items()
                        )
                    return report
                else:
                    return f"\nCh{channel}: event finding incomplete"

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).

        By default, eventfinder plugins defer to the thread safety of their child :ref:`MetaReader` instance. If any operation in your event finder is not thread-safe independent of the child reader object, this function should be overridden to simply return ``True``. Most event finders are thread-safe since reading from a file on disk is usually so, and therefore no override is necessary. Take care to verify that the :ref:`MetaReader`: subclass instance on which this object depends is also threadsafe by calling ``self.reader.force_serial_channel_operations()`` to check.
        """
        serial = False
        if self.reader is not None:
            try:
                serial = self.reader.force_serial_channel_operations()
            except Exception as e:
                self.logger.info(
                    f"Unable to check if serial mode is necessary for {self.__class__.__name__}, defaulting to {serial}: {str(e)}"
                )
        else:
            raise AttributeError(
                "Eventfinders need an attached MetaReader object to function"
            )
        return serial

    @log(logger=logger)
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: the channel identifier
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run, or all of them if no channel is specified.

        :ref:`MetaEventFinder` already has an implementation of this function, but you may override it is you need to do further resetting beyond what is included in :py:meth:`~poriscope.utils.MetaEventFinder.MetaEventFinder.reset_channel` already.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super().reset_channel(channel)`` **before** any additional code that you add and it is on you to ensure that your additional code does not conflict with the implementation in :ref:`MetaEventFinder`.
        """
        if channel is not None:
            self.event_starts[channel] = []
            self.event_ends[channel] = []
            self.padding_before[channel] = []
            self.padding_after[channel] = []
            self.baseline_means[channel] = []
            self.baseline_stds[channel] = []
            self.rejected_events[channel] = {}
            self.rejected_data[channel] = 0
            self.accepted_data[channel] = 0
            self.eventfinding_finished[channel] = False
        else:
            for channel in self.get_channels():
                self.event_starts[channel] = []
                self.event_ends[channel] = []
                self.padding_before[channel] = []
                self.padding_after[channel] = []
                self.baseline_means[channel] = []
                self.baseline_stds[channel] = []
                self.rejected_events[channel] = {}
                self.rejected_data[channel] = 0
                self.accepted_data[channel] = 0
                self.eventfinding_finished[channel] = False

    @log(logger=logger)
    def get_samplerate(self) -> float:
        """
        Return the samplerate of the associated reader object.

        :return: the samplerate of the associated reader object
        :rtype: float
        """
        if self.reader is not None:
            return self.reader.get_samplerate()
        else:
            raise AttributeError(
                "Eventfinders need an attached MetaReader object to function"
            )

    @log(logger=logger)
    def get_base_experiment_name(self) -> str:
        """
        Get the base name of the experiment being analyzed

        :return: name of the experiment being analyzed
        :rtype: str
        """
        if self.reader is not None:
            return self.reader.get_base_experiment_name()
        else:
            raise AttributeError(
                "Eventfinders need an attached MetaReader object to function"
            )

    @log(logger=logger)
    def find_events(
        self,
        channel: int,
        ranges: List[Tuple[float, float]],
        chunk_length: float = 1.0,
        data_filter: Optional[Callable] = None,
    ) -> Generator[float, Optional[bool], None]:
        """
        Orchestrates event finding over multiple (start, end) ranges for a single channel.
        Yields progress for each chunk processed.

        :param channel: The channel to process.
        :param ranges: List of (start, end) tuples in seconds.
        :param chunk_length: Length of each chunk in seconds.
        :param data_filter: Optional callable filter to apply to each chunk.
        :return: Generator yielding fractional progress (0.0–1.0)
        """
        if self.reader is None:
            raise AttributeError(
                "Eventfinders need an attached MetaReader object to function"
            )
        if channel not in self.reader.get_channels():
            self.logger.error(
                f"Reader {self.reader.get_key()} only has channels {self.reader.get_channels()}. "
                f"Requested channel={channel} is invalid"
            )
            raise RuntimeError(f"Invalid channel: {channel}")

        self.logger.info(
            f"Starting eventfinding on channel {channel} for {len(ranges)} ranges"
        )

        # Reset state
        self.event_starts[channel] = []
        self.event_ends[channel] = []
        self.padding_before[channel] = []
        self.padding_after[channel] = []
        self.baseline_means[channel] = []
        self.baseline_stds[channel] = []
        self.eventfinding_finished[channel] = False
        self.rejected_data[channel] = 0
        self.accepted_data[channel] = 0
        self.rejected_events[channel] = {}

        self.reader.get_samplerate()
        total_found = 0
        ranges = [
            (
                (start, end)
                if end is not None and end > 0
                else (
                    start,
                    self.reader.get_channel_length(channel)
                    / self.reader.get_samplerate(),
                )
            )
            for start, end in ranges
        ]

        ranges = self._merge_overlapping_ranges(ranges)
        lengths = [end - start for start, end in ranges]

        total_length = sum(length for length in lengths if length > 0)
        completed = float(0)
        abort: Optional[bool] = False
        for i, (start, end) in enumerate(ranges):
            if start < 0:
                self.logger.info(f"Setting start to 0 instead of {start}")
                start = 0

            if end is None or end == 0:
                end = (
                    self.reader.get_channel_length(channel)
                    / self.reader.get_samplerate()
                )
                self.logger.info(
                    f"Range {i}: Interpreted as ({start}, end) → ({start}, {end})"
                )

            if start >= end:
                self.logger.warning(
                    f"Range {i}: Skipping invalid range ({start}, {end})"
                )
                continue

            self.logger.info(f"Processing range {i+1}/{len(ranges)}: ({start}, {end})")
            events_before = len(self.event_starts[channel])

            try:
                weight = (end - start) / total_length
                for value in self._find_events_single_range(
                    channel, start, end, chunk_length, data_filter
                ):
                    abort = yield value * weight + completed
                    abort = bool(abort)
                    if abort is True:
                        break
            except RuntimeError as e:
                continue
            except StopIteration:
                continue

            events_after = len(self.event_starts[channel])
            events_in_range = events_after - events_before
            total_found += events_in_range
            self.logger.info(f"Range {i+1}: Found {events_in_range} events")
            completed += weight

        # Final consistency check
        if abort is False:
            if (
                len(self.event_starts[channel]) > 0
                and len(self.event_ends[channel]) > 0
            ):
                if self.event_starts[channel][-1] > self.event_ends[channel][-1]:
                    self.event_starts[channel].pop()
                if self.event_ends[channel][0] < self.event_starts[channel][0]:
                    self.event_ends[channel].pop(0)

                if len(self.event_starts[channel]) != len(self.event_ends[channel]):
                    self.logger.warning(
                        f"Mismatched event starts and ends: {len(self.event_starts[channel])} vs {len(self.event_ends[channel])} in channel {channel}"
                    )
                    self.reset_channel(channel)
                    raise RuntimeError("Mismatched number of event starts and ends")

                self.num_events_found[channel] = len(self.event_starts[channel])
                self.eventfinding_finished[channel] = True
                self.logger.info(
                    f"Total events found for channel {channel}: {total_found}"
                )
                yield 1.0
            else:
                self.logger.info(f"No events found in channel {channel}")
                self.reset_channel(channel)
        else:
            self.logger.info(f"Eventfinding aborted in channel {channel}")
            self.reset_channel(channel)

    @log(logger=logger)
    def _find_events_single_range(
        self,
        channel: int,
        start: float = 0,
        end: float = 0,
        chunk_length: float = 1.0,
        data_filter: Optional[Callable] = None,
    ) -> Generator[float, Optional[bool], None]:
        """
        Set up a generator that will walk through all provided data and find events, yielding its percentage completion each time next() is called on it.
        If silent flag is set, run through without yielding progress reports on the first call to next(). Once StopIteration is reached, internal
        lists of event starts and ends will be populated as entries in a dict keyed by channel index.

        :return: Yield completion fraction on each iteration.
        :rtype: Generator[float, Optional[bool], None]
        """

        if start < 0:
            self.logger.error(f"Start must be positive: got {start}")
            raise RuntimeError(f"Start must be positive: got {start}")
        if self.reader is None:
            raise AttributeError(
                "Event finders need an attached MetaReader object to function"
            )
        if channel not in self.reader.get_channels():
            self.logger.error(
                f"Reader {self.reader.get_key()} only has channels {self.reader.get_channels()}. Requested channel={channel} is invalid"
            )
            raise RuntimeError(
                f"Reader {self.reader.get_key()} only has channels {self.reader.get_channels()}. Requested channel={channel} is invalid"
            )

        samplerate = self.reader.get_samplerate()
        channel = int(channel)
        start = int(start * samplerate)
        total_samples = self.reader.get_channel_length(channel)
        end = int(end * samplerate) if end > 0 else total_samples
        if end > total_samples:
            end = total_samples
        if chunk_length is not None:
            chunk_length = int(chunk_length * samplerate)
        else:
            chunk_length = int(samplerate)
        total_samples = end - start
        last_sample = total_samples + start
        if chunk_length > total_samples:
            chunk_length = total_samples
        entry_state = False
        first_chunk = True
        last_call = False
        index_offset = start
        processed = 0
        last_end = 0
        prev_start = None
        while processed < total_samples:
            if (
                total_samples - processed < 2 * chunk_length
            ):  # offset rounding errors and avoid having a tiny trailing array that causes filter issues
                chunk_length = total_samples - processed
            data = self.reader.load_data(
                start / samplerate, chunk_length / samplerate, channel
            )
            if data_filter:
                data = data_filter(data)

            try:
                mean, std = self._get_baseline_stats(data)
                if (
                    mean * np.sign(mean) < 3 * std
                    or mean * np.sign(mean) < self.settings["Threshold"]["Value"]
                ):
                    # do not attempt to fit when no voltage is applied
                    self.rejected_data[channel] += len(data) / samplerate
                    self.logger.info(
                        f"Skipping chunk with mean {mean}pA, {std}pA for channel {channel}"
                    )
                    continue
            except ValueError as e:
                self.rejected_data[channel] += len(data) / samplerate
                self.logger.info(
                    f"Error processing data chunk {start/samplerate}-{(start+len(data))/samplerate}s for channel {channel}: {str(e)}"
                )
                yield float(processed / total_samples)
                continue
            else:
                self.accepted_data[channel] += len(data) / samplerate
                event_starts, event_ends, entry_state = self._find_events_in_chunk(
                    data * np.sign(mean),
                    mean * np.sign(mean),
                    std,
                    index_offset,
                    entry_state,
                    first_chunk,
                )
            finally:
                first_chunk = False
                index_offset += len(data)
                start += len(data)
                processed += len(data)
                if processed >= total_samples:
                    last_call = True

            if (
                prev_start
            ):  # if we saved a start from last iteration, insert it at the beginning of this chunk
                event_starts.insert(0, prev_start)

            if len(event_starts) > len(event_ends):
                # if we have a trailing start, pop it and save it for later
                prev_start = event_starts.pop()
            else:
                prev_start = None

            if (
                len(event_ends) > len(event_starts)
                and len(event_starts) > 0
                and len(event_ends) > 0
                and first_chunk
                and event_ends[0] < event_starts[0]
            ):
                # if we have a leading event end in the first chunk, drop it
                event_ends.pop(0)

            if len(event_starts) > 0:
                try:
                    last_duration = (
                        self.event_ends[channel][-1] - self.event_starts[channel][-1]
                    )
                except IndexError:
                    last_duration = None

                bad_indices, rejected_reasons = self._filter_events(
                    event_starts, event_ends, channel, last_end
                )
                for bad_index, reason in zip(bad_indices, rejected_reasons):
                    self.rejected_events[channel][reason] = (
                        self.rejected_events[channel].get(reason, 0) + 1
                    )

                first_chunk = False
                try:
                    (
                        padding_before,
                        padding_after,
                        last_end,
                        padding_after_previous_end,
                    ) = self._get_padding_length(
                        event_starts,
                        event_ends,
                        last_end,
                        last_duration,
                        samplerate,
                        last_call,
                        last_sample,
                    )
                except RuntimeError as e:
                    self.logger.info(f"Error getting padding: {str(e)}")
                    continue

                if len(self.padding_after[channel]) < len(self.event_starts[channel]):
                    self.padding_after[channel].append(padding_after_previous_end)

                start_subset = [
                    item
                    for idx, item in enumerate(event_starts)
                    if idx not in bad_indices
                ]
                end_subset = [
                    item
                    for idx, item in enumerate(event_ends)
                    if idx not in bad_indices
                ]
                padding_before_subset = [
                    item
                    for idx, item in enumerate(padding_before)
                    if idx not in bad_indices
                ]
                padding_after_subset = [
                    item
                    for idx, item in enumerate(padding_after)
                    if idx not in bad_indices
                ]

                self.event_starts[channel] += start_subset
                self.event_ends[channel] += end_subset
                self.padding_before[channel] += padding_before_subset
                self.padding_after[channel] += padding_after_subset
                self.baseline_means[channel] += [mean] * len(start_subset)
                self.baseline_stds[channel] += [std] * len(start_subset)

            yield float(processed / total_samples)

        self.logger.info(
            f"Range complete: Found {len(self.event_starts[channel])} events in channel {channel}"
        )
        if len(self.event_starts[channel]) > 0 and len(self.event_ends[channel]) > 0:
            if self.event_starts[channel][-1] > self.event_ends[channel][-1]:
                self.event_starts[
                    channel
                ].pop()  # drop trailing partial event from dataset
            if (
                self.event_ends[channel][0] < self.event_starts[channel][0]
            ):  # if the dataset starts mid event, drop the first end
                self.event_ends[channel].pop(0)
            if len(self.event_starts[channel]) != len(self.event_ends[channel]):
                self.logger.warning(
                    f"Mismatched event starts and event ends: {len(self.event_starts[channel])} and {len(self.event_ends[channel])} in channel {channel}"
                )
                self.reset_channel(channel)
                raise RuntimeError(
                    f"Mismatched event starts and event ends: {len(self.event_starts[channel])} and {len(self.event_ends[channel])} in channel {channel}"
                )
        else:
            self.logger.info(
                f"No events found in channel {channel} with specified paramters"
            )

        if len(self.padding_after[channel]) < len(self.event_starts[channel]):
            self.padding_after[channel].append(
                np.minimum(
                    int(self.event_ends[channel][-1] - self.event_starts[channel][-1]),
                    end - self.event_ends[channel][-1],
                )
            )
        self.num_events_found[channel] = len(self.event_starts[channel])
        self.eventfinding_finished[channel] = True
        yield 1.0

    @log(logger=logger)
    def _get_padding_length(
        self,
        event_starts: List[int],
        event_ends: List[int],
        last_end: int,
        last_duration: int,
        samplerate: float,
        last_call: bool = False,
        last_sample: int = 0,
    ) -> Tuple[List[int], List[int], int, int]:
        """
        Determine the number of data points before and after an event to use for visual padding.

        :param event_starts: List of start indices of events in a chunk of data, referenced from the start of the file. May contain events which are later rejected.
        :type event_starts: List[int]
        :param event_ends: List of start indices of events in a chunk of data, referenced from the start of the file. May contain events which are later rejected.
        :type event_ends: List[int]
        :param last_end: index of the end of the last event detected in the previous chunk
        :type last-end: int
        :param samplerate: Sampling rate for the reader in question
        :type samplerate: float
        :param last_call: is this the last time the function will be called?
        :type last_call: bool
        :param last_sample: what is the value of the last data index in the channel? Can be 0 if last_call is False.
        :type last_sample: int

        :return: a list of padding before values and padding after values that do not conflict with neightbouring events, whether good or bad. Also an int for the amount of padding to add to the trailing end of events already saved, or None oif this is not necessary, and the value of the last evnet end
        :type: Tuple[List[int], List[int], int]
        """
        padding_before = []
        padding_after = []

        # we can assume that we always start with an event start and that we always end with an event end, and that we have an equal number of each
        if len(event_starts) != len(event_ends) or event_starts[0] > event_ends[0]:
            self.logger.info("Somethign went horribly wrong with finding events")
            raise RuntimeError(
                "Unable to match event start and end times for this chunk"
            )

        if last_duration:
            target_padding = int(np.maximum(100e-6 * samplerate, last_duration))
        else:
            target_padding = int(100e-6 * samplerate)
        padding_after_previous_end = target_padding
        if padding_after_previous_end > event_starts[0] - last_end:
            padding_after_previous_end = event_starts[0] - last_end

        for i, (start, end) in enumerate(zip(event_starts, event_ends)):
            target_padding = int(
                np.maximum(100e-6 * samplerate, end - start)
            )  # try to pad with length equal to the event or 100 microseconds of data, whichever is longer
            pb = target_padding
            if pb > start - last_end:
                pb = int(0.75 * (start - last_end))
            padding_before.append(pb)

            try:
                next_start = event_starts[i + 1]
            except IndexError:
                last_end = end
            else:
                pa = target_padding
                if pa > next_start - end:
                    pa = int(0.75 * (next_start - end))
                if end + pa > last_sample:
                    pa = int(0.75 * (last_sample - end))
                padding_after.append(pa)
                last_end = end

        return padding_before, padding_after, last_end, padding_after_previous_end

    @log(logger=logger)
    def get_event_data_generator(
        self,
        channel: int,
        data_filter: Optional[Callable] = None,
        rectify: bool = False,
        raw_data: bool = False,
    ) -> Generator[npt.NDArray[np.float64], None, None]:
        """
        Set up a generator that will return the start and end indices of event i within the data chunk analyzed. If offset was provided during analysis, it will be included here.

        :param channel: label for the channel from which to retrieve event indices
        :type channel: int

        :raises ValueError: If events have not been found or if index is out of bounds.

        :return: A Generator that gives data in an event and the index of the start of that event relative to the start of the file. If offset was provided during analysis, it will be included here.
        :rtype: Generator[Tuple[int,int], None, None]
        """
        if (
            self.event_starts.get(channel) is None
            or self.event_ends.get(channel) is None
        ):
            raise KeyError(f"Channel {channel} is not present in the eventfinder")
        elif self.event_starts[channel] == {} or self.event_ends[channel] == {}:
            raise ValueError("Eventfinder may not have run yet")
        elif self.event_starts.get(channel) == []:
            raise ValueError(f"No event starts found for channel {channel}")
        elif (
            self.event_ends.get(channel) is not None
            and self.event_ends.get(channel) == []
        ):
            raise ValueError(f"No event ends found for channel {channel}")
        elif not self.eventfinding_finished.get(channel):
            raise ValueError(f"Event finding not yet completed for channel {channel}")

        else:
            for i in range(len(self.event_starts[channel])):
                yield self.get_single_event_data(
                    channel, i, data_filter, rectify, raw_data
                )

    @log(logger=logger)
    def get_channels(self):
        """
        get the number of available channels in the reader
        """
        if self.reader is None:
            raise AttributeError("Reader has not been initialized.")
        return self.reader.get_channels()

    @log(logger=logger)
    def get_single_event_data(
        self,
        channel: int,
        index: int,
        data_filter: Optional[Callable] = None,
        rectify: Optional[bool] = False,
        raw_data: Optional[bool] = False,
    ) -> Optional[Dict[str, Union[npt.NDArray[np.float64], float]]]:
        """
        Return a dictionary of data and metadata for the requested event

        :param channel: label for the channel from which to retrieve event indices
        :type channel: int
        :param index: The index of the event to retrieve data for
        :type index: int
        :param data_filter: a function that is called to preprocess the data before it is returned
        :type data_filter: Optional[Callable]
        :param rectify: should the data be returned rectified?
        :type rectify: Optional[bool]
        :param raw_data: return raw adc codes on True, pA values on False
        :type raw_data: Optional[bool]


        :raises IndexError: If index is out of bounds
        :raises KeyError: If the channel does not exist
        :raises ValueError: if no events have been found in the channel

        :return: A dictionary of data and metadata for the specicied event
        :rtype: Dict[str, Union[npt.NDArray[np.float64], float]]
        """
        if self.event_starts == {} or self.event_ends == {}:
            raise ValueError("Eventfinder may not have run yet")
        elif self.event_starts.get(channel) is None:
            raise KeyError(f"Channel {channel} is not present in the eventfinder")
        elif self.event_starts.get(channel) == []:
            raise ValueError(f"No event starts found for channel {channel}")
        elif (
            self.event_ends.get(channel) is not None
            and self.event_ends.get(channel) == []
        ):
            raise ValueError(f"No event ends found for channel {channel}")
        else:
            if self.reader is None:
                raise AttributeError(
                    "Event finders need an attached MetaEventReader instance to function"
                )
            scale = None
            offset = None
            try:
                start = (
                    self.event_starts[channel][index]
                    - self.padding_before[channel][index]
                ) / self.reader.get_samplerate()
                length = (
                    self.event_ends[channel][index]
                    - self.event_starts[channel][index]
                    + self.padding_before[channel][index]
                    + self.padding_after[channel][index]
                ) / self.reader.get_samplerate()
                data = self.reader.load_data(start, length, channel, raw_data)
                if raw_data:
                    data, scale, offset = data
                if data_filter and not raw_data:
                    data = data_filter(data)
                if rectify and not raw_data:
                    data *= np.sign(data[0])

                event = {
                    "data": data,
                    "start_sample": self.event_starts[channel][index]
                    - self.padding_before[channel][index],
                    "padding_before": self.padding_before[channel][index],
                    "padding_after": self.padding_after[channel][index],
                    "baseline_mean": self.baseline_means[channel][index],
                    "baseline_std": self.baseline_stds[channel][index],
                    "scale": scale,
                    "offset": offset,
                }
                return event
            except IndexError:
                self.logger.error(
                    f"Event index {index} out of bounds for channel {channel}"
                )
                return None

    @log(logger=logger)
    def get_event_indices(
        self, index: int
    ) -> Tuple[Dict[int, List[int]], Dict[int, List[int]]]:
        """
        return the start and end indices of event i within the data chunk analyzed.

        :param index: The index of the event to retrieve data for
        :type index: int

        :raises IndexError: If index is out of bounds
        :return: Lists of start and end indices for all events found in the data. If offset was provided during analysis, it will be included here.
        :rtype: Tuple[List[int],List[int]]
        """
        if self.event_starts == [] or self.event_ends == []:
            raise ValueError("Events have not been located or no events were found")
        else:
            return self.event_starts, self.event_ends

    @log(logger=logger)
    def get_dtype(self) -> object:
        """
        return the raw data type of the associated reader

        :return: the raw data type of the associated reader
        :rtype: object
        """
        if self.reader is not None:
            return self.reader.get_raw_dtype()
        else:
            raise AttributeError(
                "Event finders needs an attached MetaReader object to function"
            )

    @log(logger=logger)
    def get_num_events_found(self, channel: int) -> int:
        """
        Retrieve the number of events found

        :param channel: the channel in question
        :type channel: int

        :return: the number of events found
        :rtype: int
        """
        if self.eventfinding_finished.get(channel):
            return self.num_events_found[channel]
        else:
            return 0

    @log(logger=logger)
    def get_eventfinding_status(self, channel: int) -> int:
        """
        Check whether the eventfinder has finished processing a given channel yet

        :param channel: the channel in question
        :type channel: int

        :return: True if the channel is done processing, False otherwise
        :rtype: bool
        """
        try:
            return self.eventfinding_finished[channel]
        except KeyError:
            return False

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _find_events_in_chunk(
        self,
        data: npt.NDArray[np.float64],
        mean: float,
        std: float,
        offset: int,
        entry_state: bool = False,
        first_chunk: bool = False,
    ) -> Tuple[List[int], List[int], bool]:
        """
        :param data: Chunk of timeseries data to analyze. Assume it is rectified so that a blockage will always represent a reduction in absolute value.
        :type data: npt.NDArray[np.float64]
        :param mean: Mean of the baseline on the given chunk. Must be positive.
        :type mean: float
        :param std: Standard deviation of the baseline on the given chunk
        :type std: float
        :param offset: the index of the start of the chunk in the global dataset
        :type offset: int
        :param entry_state: Bool indicating whether we start in the middle of an event (True) or not (False)
        :type entry_state: bool
        :param first_chunk: Bool indicating whether this is the first chunk of data in the series to be analyzed
        :type first_chunk: bool
        :raises ValueError: If event_params are invalid.
        :return: Lists of event start and end indices, and boolean entry state.
        :rtype: tuple[List[int], List[int],bool]


        This is the core of the event finder. You will be given a segment of data as well as a series of related arguments, and you must write a function that flags the start and end times of all events in that data chunk. Bear in mind that events might straddle more than one event chunk. The ``entrey_state`` argument encodes whether or not the previous data chunk ended inside an event, and the ``first_chunk`` argument encodes whether this is the first call to this function. You are also given the mean and standard deviation of the chunk as determined by your implementation of :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._get_baseline_stats` as an input.

        Your function must return two lists and a boolean: integers representing the start times and end times of all events flagged in that chunk, and a bollean  flag inficating whether nor not the chunk ended partway through an  evnet. These lists can be different lengths, since as noted previously, your chunk could have events that straddle the start, end, or both, of the chunk.You are responsible only for flagging the start and end of events that are present in the given data chunk; the base class will handle stitching them all together.
        """
        pass

    @abstractmethod
    def _filter_events(
        self, event_starts: List[int], event_ends: List[int], channel: int, last_end=0
    ) -> Tuple[List[int], List[str]]:
        """
        :param event_starts: a list of starting data indices for events. You may assume that event_starts[0] < event_ends[0]. It is possible that there will be one more entry in this list than in event_ends.
        :type event_starts: List[int]
        :param event_ends: a list of ending data indices for events. You may assume that event_starts[0] < event_ends[0]
        :type event_ends: List[int]
        :param channel: Bool indicating whether this is the first chunk of data in the series to be analyzed
        :type channel: int
        :param last_end: the index of the end of the last accepted event
        :type last_end: int
        :return:  A list of indices to reject from the given list of event starts and ends, and a list of reason for rejection
        :rtype: Tuple[List[int], List[str]]

        Given the lists of event start and event ends calculated by your implementation of :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin._find_events_in_chunk`, select which ones to reject. For this, you may assume that poriscope has corrected for events that straddle the start of the chink, but not the end, which is to say that ``event_starts[0] < event_ends[0]`` will be ``True``, but it is possible that ``event_start`` will have an additional trailing entry that you should not attempt to reject. You must return a list of indices (N.B, not the actual values in ``event_starts`` or ``event_ends``) to reject, and an equal-length list of strings that provide a reason for rejection (be very terse).
        """
        pass

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    @abstractmethod
    def _get_baseline_stats(self, data: npt.NDArray[np.float64]) -> tuple[float, float]:
        """ "

        :param data: Chunk of timeseries data to compute statistics on.
        :type data: npt.NDArray[np.float64]
        :return: Tuple of mean, and standard deviation the baseline.
        :rtype: tuple[float, float]

        This function must calculate and return the mean and standard deviation of the baseline for the given chunk of data, excluding any events present in the chunk. These values are used downstream to determine where the baseline deviates from the open pore current. By default, :ref:`MetaEventFinder` assumes a Gaussian distribution of baseline noise. You may assume that the data is rectified.
        """
        pass

    # private API, should generally be left alone by subclasses
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

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaEventFinder` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        Your Eventfinder MUST include at least the "MetaReader" key, which can be ensured by calling ``settings = super().get_empty_settings(globally_available_plugins, standalone)`` before adding any additional settings keys

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventFinder`, which already has an implementation of this function that ensures that settings will have the required :ref:`MetaReader` key available to users, in most cases you will need to override it to add any other settings required by your subclass. If you need additional settings, which you almost ccertainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Threshold"] = {"Type": float,
                                    "Value": None,
                                    "Min": 0.0,
                                    "Units": "pA"
                                    }
            settings["Min Duration"] = {"Type": float,
                                        "Value": 0.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Max Duration"] = {"Type": float,
                                        "Value": 1000000.0,
                                        "Min": 0.0,
                                        "Units": "us"
                                        }
            settings["Min Separation"] = {"Type": float,
                                            "Value": 0.0,
                                            "Min": 0.0,
                                            "Units": "us"
                                        }
            return settings

        which will ensure that your have the 3 keys specified above, as well as an additional key, ``"MetaReader"``, as required by eventfinders. In the case of categorical settings, you can also supply the "Options" key in the second level dictionaries.
        """
        reader_options = None
        if globally_available_plugins:
            reader_options = globally_available_plugins.get("MetaReader")
        if reader_options == [] and not standalone:
            raise KeyError(
                "Cannot instantiate an eventfinder without first instantiating a data reader"
            )
        elif standalone:
            reader_options = None

        settings: Dict[str, Dict[str, Any]] = {
            "MetaReader": {
                "Type": str,
                "Value": reader_options[0] if reader_options is not None else "",
                "Options": reader_options,
            }
        }
        return settings

    @log(logger=logger)
    def _finalize_initialization(self) -> None:
        """
        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.

        **Purpose:** Apply application-specific settings to the plugin, if needed.

        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaEventFinder` that must occur after settings have been applied to the reader instance, you can override this function to add those operations, subject to the caveat below.

        .. warning::

            This function implements core functionality required for broader plugin integration into Poriscope. If you do need to override it, you **MUST** call ``super()._finalize_initialization()`` **before** any additional code that you add, and take care to understand the implementation of both :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.apply_settings` and :py:meth:`~poriscope.utils.MetaEventFinder.MetaEventFinder._finalize_initialization` before doing so to ensure that you are not conflicting with those functions.

        Should Raise if initialization fails.
        """
        self.reader = self.settings["MetaReader"]["Value"]

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
                if param == "MetaReader":
                    if not issubclass(val["Value"].__class__, MetaReader):
                        raise TypeError(
                            "MetaReader key must have as value an object that inherits from MetaReader"
                        )

    # Utility functions, specific to subclasses as needed

    def _merge_overlapping_ranges(self, ranges):
        """
        Merge a list of overlapping or adjacent (start, end) ranges into non-overlapping intervals.

        Ranges with start >= end are filtered out as invalid.
        Overlapping or adjacent ranges are merged into a single continuous interval.

        :param ranges: List of (start, end) tuples representing numeric ranges.
        :type ranges: list[tuple[float, float]]
        :return: List of merged non-overlapping (start, end) tuples.
        :rtype: list[tuple[float, float]]
        """
        # Filter out any invalid or malformed ranges
        valid_ranges = [(start, end) for start, end in ranges if start < end]

        # Sort ranges by start time
        sorted_ranges = sorted(valid_ranges, key=lambda x: x[0])

        merged: List[Tuple[float, float]] = []
        for current in sorted_ranges:
            if not merged:
                merged.append(current)
            else:
                last_start, last_end = merged[-1]
                current_start, current_end = current
                if current_start <= last_end:  # Overlap or adjacent
                    # Merge by extending the end to the max of both
                    merged[-1] = (last_start, max(last_end, current_end))
                else:
                    merged.append(current)
        return merged
