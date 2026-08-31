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
from typing import Any, Dict, Generator, List, Optional

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Qt, Signal, Slot

from poriscope.utils.EventWorker import Worker, WorkerThread
from poriscope.utils.LogDecorator import log
from poriscope.utils.QObjectABCMeta import QObjectABCMeta


class MetaModel(QObject, metaclass=QObjectABCMeta):
    """
    Abstract base class for models.
    """

    global_signal = Signal(
        str, str, str, tuple, str, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval (can be None), added args for retval
    # NOTE: every connection to global_signal/data_plugin_controller_signal must stay
    # Qt.ConnectionType.DirectConnection (or otherwise guaranteed same-thread). A caller
    # that passes a return_function_name reads the result back off an attribute the
    # callback sets, on the very next statement after .emit() - a queued connection
    # would silently degrade that read to stale/None data with no error and no log line.
    data_plugin_controller_signal = Signal(
        str, str, str, tuple, str, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval (can be None), added args for retval
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize the MetaModel

        :param \\**kwargs: Additional parameters to set as attributes on the instance
        :type \\**kwargs: Any
        """

        self.available_plugins: Dict[str, List[str]] = {}
        self.reporter_metaclasses: Dict[str, str] = {}
        self.generators: Dict[
            str, Dict[int, Generator[float, Optional[bool], None]]
        ] = {}
        self.threads: Dict[str, Dict[int, WorkerThread]] = (
            {}
        )  # Holds worker objects per key/channel
        self.workers: Dict[str, Dict[int, Worker]] = (
            {}
        )  # Holds worker threads per key/channel
        self.thread_running: Dict[str, Dict[int, bool]] = (
            {}
        )  # Track running state per key/channel

        # nested dicts keyed by plugin key and channel number
        self.cache_data: Optional[List[np.ndarray]] = None
        self.cache_labels: Optional[List[str]] = None

        super().__init__()
        for (
            k,
            v,
        ) in kwargs.items():  # set class parameters with kwargs dict for use later
            setattr(self, k, v)
        self._init()

    # private API, must be implemented by sublcasses
    @abstractmethod
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        pass

    # public API, must be implemented by sublcasses

    @log(logger=logger)
    def set_generator(
        self,
        generator: Generator[float, Optional[bool], None],
        channel: int,
        key: str,
        metaclass: str,
    ) -> None:
        """Add generator and set it to be run by a QThread."""
        if key not in self.thread_running.keys():
            self.thread_running[key] = {}
        thread_running = self.thread_running[key].get(channel)
        if not thread_running:
            if key not in self.generators.keys():
                self.generators[key] = {}
            self.reporter_metaclasses[key] = metaclass
            self.generators[key][channel] = generator

    @log(logger=logger)
    def run_generators(self, key: str) -> None:
        """
        Start one worker thread per channel for which a generator has been staged under this key.

        Serialization is not decided here. A plugin that declares
        ``force_serial_channel_operations()`` now takes its *own* lock inside its
        generator (see
        :py:func:`~poriscope.utils.SerializeDecorator.serialize_channels`), so this
        method no longer asks the plugin anything and no longer hands the worker a lock.
        It used to emit ``global_signal`` for that answer and read it back off
        ``self.serial_ops`` on the next statement, which worked only because every hop in
        that chain was a same-thread automatic connection Qt resolves as a direct call -
        one ``Qt.QueuedConnection`` anywhere in it would have silently degraded the lock
        to ``None``, with no error and no log line.

        :param key: the plugin key whose staged generators should be run
        :type key: str
        """
        for channel, generator in self.generators[key].items():
            thread_running = self.thread_running[key].get(channel)
            if not thread_running:
                self.thread_running[key][channel] = True
                if key not in self.workers.keys():
                    self.workers[key] = {}
                if key not in self.threads.keys():
                    self.threads[key] = {}

                self.workers[key][channel] = Worker(generator, channel, key)
                self.workers[key][channel].update_progressbar.connect(
                    self.emit_progress_update, Qt.QueuedConnection
                )
                self.threads[key][channel] = WorkerThread(
                    self.workers[key][channel], channel, key
                )
                self.threads[key][channel].workerthread_finished.connect(
                    self.discard_generator, Qt.QueuedConnection
                )
                self.threads[key][channel].workerthread_finished.connect(
                    self.generate_report, Qt.QueuedConnection
                )
                self.threads[key][channel].start()

    @log(logger=logger)
    @Slot(int, str)
    def discard_generator(self, channel: int, key: str) -> None:
        """
        Clear the run state for one (key, channel) once its worker thread has finished.

        Formerly ``reset_lock``, which reset no lock - it clears the ``thread_running``
        flag, which is what allows :py:meth:`set_generator` to stage a new run for this
        key and channel, and drops the spent generator.

        The generator is explicitly closed before being dropped. A plugin that declares
        serial channel operations holds its own lock across the generator's ``yield``\ s,
        and that lock is released when the generator is exhausted *or closed*; relying on
        the reference count falling to zero to finalize it would make release depend on
        garbage-collection timing, and a stranded lock here is a silent hang rather than an
        error. ``close()`` is a harmless no-op on a generator that already ran to
        completion.

        :param channel: the channel whose run has finished
        :type channel: int
        :param key: the plugin key whose run has finished
        :type key: str
        """
        self.thread_running[key][channel] = False
        try:
            generator = self.generators[key].pop(channel)
        except KeyError:
            return
        generator.close()

    @log(logger=logger)
    @Slot(int, str)
    def generate_report(self, channel: int, key: str) -> None:
        metaclass = self.reporter_metaclasses[key]
        report_channel_status_args = (channel,)
        ret_args = (key,)
        self.global_signal.emit(
            metaclass,
            key,
            "report_channel_status",
            report_channel_status_args,
            "relay_add_text_to_display",
            ret_args,
        )

    @log(logger=logger)
    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up to date list of possible data sources for use by this plugin.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        self.logger.info(f"Model updated: {available_plugins}")
        self.available_plugins = available_plugins

    @log(logger=logger)
    @Slot(list, list)
    def cache_plot_data(self, data: List[np.ndarray], labels: List[str]) -> None:
        self.cache_data = data
        self.cache_labels = labels

    @log(logger=logger)
    def format_cache_data(self) -> Optional[pd.DataFrame]:
        if self.cache_data and self.cache_labels:
            max_length = max([len(arr) for arr in self.cache_data])
            # Convert arrays to float type first to allow np.nan
            padded_data = np.array(
                [
                    np.pad(
                        arr.astype(float),
                        pad_width=(0, max_length - len(arr)),
                        constant_values=np.nan,
                    )
                    for arr in self.cache_data
                ]
            )
            df = pd.DataFrame(padded_data.T, columns=self.cache_labels)
            return df
        return None

    @log(logger=logger)
    def stop_workers(
        self,
        key: Optional[str] = None,
        channel: Optional[int] = None,
        exiting: bool = False,
    ) -> None:
        """Stop workers based on specified key and/or channel."""
        if key is None:
            # If no key is provided, stop workers for all keys
            self.logger.info("Stopping all workers across all keys.")
            for current_key in list(
                self.workers.keys()
            ):  # Iterate over a copy to avoid modification issues
                if (
                    current_key in self.workers
                ):  # Ensure key still exists before calling stop
                    self.stop_workers(current_key, exiting=exiting)
            return  # Exit after stopping all workers

        if key not in self.workers:
            self.logger.warning(
                f"No active workers found for key '{key}'. Full dictionary: {self.workers}"
            )
            return

        if channel is None:
            # Stop all workers for the given key
            self.logger.info(f"Stopping all workers for key: {key}")
            for chan in list(
                self.workers[key].keys()
            ):  # Iterate over a copy of channels
                if chan in self.workers[key]:  # Ensure channel still exists
                    self.stop_workers(key, chan, exiting=exiting)
        else:
            # Stop only the specific channel's worker within the given key
            if channel in self.workers[key]:
                self.logger.info(f"Stopping worker for key: {key}, channel: {channel}")
                if self.thread_running[key][channel] is True:
                    self.workers[key][channel].stop_signal.emit()  # Ask worker to stop

                if exiting:
                    # On app exit we must block until the thread actually
                    # finishes, otherwise Qt destroys a QThread still running.
                    self.threads[key][channel].wait()
                # Otherwise let workerthread_finished emit and trigger
                # discard_generator() asynchronously - avoid blocking here.
                self.logger.debug(
                    f"Worker and thread stopped for key: {key}, channel: {channel}"
                )

    # private API, should generally be left alone by subclasses

    # public API, should generally be left alone by subclasses

    @log(logger=logger)
    @Slot(float, str)
    def emit_progress_update(self, progress: float, identifier: str) -> None:
        """
        Emit the progress update signal
        """
        self.logger.info(f"Progress update received: {progress}% for {identifier}")
        self.update_progressbar.emit(progress, identifier)
