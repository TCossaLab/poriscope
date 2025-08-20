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
import threading
from abc import abstractmethod
from typing import Dict, Generator, List, Optional

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
    data_plugin_controller_signal = Signal(
        str, str, str, tuple, str, tuple
    )  # metaclass type, subclass key, function to call, args for function to call, function to call with reval (can be None), added args for retval
    update_progressbar = Signal(float, str)
    add_text_to_display = Signal(str, str)
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs) -> None:
        """
        Initialize the MetaModel

        :param kwargs: Additional parameters to set as attributes on the instance
        :type kwargs: dict
        """

        self.available_plugins: Dict[str, List[str]] = {}
        self.reporter_metaclasses: Dict[str, str] = {}
        self.generators: Dict[str, Dict[int, Generator]] = {}
        self.threads: Dict[str, Dict[int, WorkerThread]] = (
            {}
        )  # Holds worker objects per key/channel
        self.workers: Dict[str, Dict[int, Worker]] = (
            {}
        )  # Holds worker threads per key/channel
        self.thread_running: Dict[str, Dict[int, bool]] = (
            {}
        )  # Track running state per key/channel
        self.serial_ops: Dict[str, Dict[int, bool]] = {}
        self.lock: threading.Lock = threading.Lock()

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
    def set_generator(self, generator, channel, key, metaclass):
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
    def run_generators(self, key):
        metaclass = self.reporter_metaclasses[key]
        for channel, generator in self.generators[key].items():
            thread_running = self.thread_running[key].get(channel)
            if not thread_running:
                self.thread_running[key][channel] = True
                if key not in self.workers.keys():
                    self.workers[key] = {}
                if key not in self.threads.keys():
                    self.threads[key] = {}

                self.global_signal.emit(
                    metaclass,
                    key,
                    "force_serial_channel_operations",
                    (),
                    "set_force_serial_channel_operations",
                    (key, channel),
                )
                lock = self.lock if self.serial_ops[key][channel] else None
                self.workers[key][channel] = Worker(generator, channel, key, lock)
                self.workers[key][channel].update_progressbar.connect(
                    self.emit_progress_update, Qt.QueuedConnection
                )
                self.threads[key][channel] = WorkerThread(
                    self.workers[key][channel], channel, key
                )
                self.threads[key][channel].workerthread_finished.connect(
                    self.reset_lock, Qt.QueuedConnection
                )
                self.threads[key][channel].workerthread_finished.connect(
                    self.generate_report, Qt.QueuedConnection
                )
                self.threads[key][channel].start()

    @log(logger=logger)
    @Slot(int, str)
    def reset_lock(self, channel, key):
        self.thread_running[key][channel] = False
        try:
            self.generators[key].pop(channel)
        except KeyError:
            pass

    @log(logger=logger)
    def set_force_serial_channel_operations(self, serial_ops, key, channel):
        if key not in self.serial_ops.keys():
            self.serial_ops[key] = {}
        self.serial_ops[key][channel] = serial_ops

    @log(logger=logger)
    @Slot(int, str)
    def generate_report(self, channel, key):
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
    def update_available_plugins(self, available_plugins: dict) -> None:
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up to date list of possible data sources for use by this plugin.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: dict
        """
        self.logger.info(f"Model updated: {available_plugins}")
        self.available_plugins = available_plugins

    @log(logger=logger)
    @Slot(list, list)
    def cache_plot_data(self, data, labels):
        self.cache_data = data
        self.cache_labels = labels

    @log(logger=logger)
    def format_cache_data(self):
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

    @log(logger=logger)
    def stop_workers(self, key=None, channel=None, exiting=False):
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

                # Let workerthread_finished emit and trigger reset_lock() - avoid race conditions - UNNECESSARY
                # self.threads[key][channel].wait()
                self.logger.debug(
                    f"Worker and thread stopped for key: {key}, channel: {channel}"
                )

    # private API, should generally be left alone by subclasses

    # public API, should generally be left alone by subclasses

    @log(logger=logger)
    @Slot(float, str)
    def emit_progress_update(self, progress, identifier):
        """
        Emit the progress update signal
        """
        self.logger.info(f"Progress update received: {progress}% for {identifier}")
        self.update_progressbar.emit(progress, identifier)
