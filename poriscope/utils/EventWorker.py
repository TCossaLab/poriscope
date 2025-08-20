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

import logging

from PySide6.QtCore import QObject, QThread, Signal, Slot

from poriscope.utils.LogDecorator import log


class Worker(QObject):
    update_progressbar = Signal(float, str)
    stop_signal = Signal()
    logger = logging.getLogger(__name__)

    def __init__(self, generator, channel, key, lock=None):
        super().__init__()
        self.generator = generator
        self.channel = channel
        self.stop_requested = False
        self.key = key
        self.lock = lock
        self.logger = logging.getLogger(f"Worker[{self.key}/{self.channel}]")
        self.stop_signal.connect(self.stop)
        self.logger.debug("Worker initialized.")

    @log(logger=logger)
    def process_generator(self):
        """Run the generator loop in a separate thread."""
        p = 0
        while True:
            self.logger.debug(
                f"Worker [{self.key}/{self.channel}] waiting for generator output..."
            )
            try:
                try:
                    p = self.generator.send(self.stop_requested)
                except TypeError:
                    p = next(self.generator)
                self.logger.debug(
                    f"Worker [{self.key}/{self.channel}] Generator produced: {p}"
                )
            except StopIteration:
                self.logger.info(
                    f"Worker [{self.key}/{self.channel}] Generator finished StopIteration."
                )
                break
            except RuntimeError as e:
                self.logger.error(
                    f"Worker [{self.key}/{self.channel}] encountered RuntimeError: {e}"
                )
                break
            except ValueError as e:
                self.logger.error(
                    f"Worker [{self.key}/{self.channel}] encountered ValueError: {e}"
                )
                break
            except IOError as e:
                self.logger.error(
                    f"Worker [{self.key}/{self.channel}] encountered IOError: {e}"
                )
                break
            else:
                progress = 100 * p
                self.update_progressbar.emit(progress, f"{self.key}/{self.channel}")
                self.logger.debug(
                    f"Worker [{self.key}/{self.channel}] Progress updated: {progress:.2f}%"
                )

    @log(logger=logger)
    def run(self):
        self.logger.info(f"Worker [{self.key}/{self.channel}] started.")
        p = 0
        self.update_progressbar.emit(p, f"{self.key}/{self.channel}")
        try:
            if self.lock:
                with self.lock:
                    self.process_generator()
            else:
                self.process_generator()
        except:
            raise
        finally:
            self.update_progressbar.emit(100, f"{self.key}/{self.channel}")
            self.logger.info(f"Worker [{self.key}/{self.channel}] finished.")

    @Slot()
    @log(logger=logger)
    def stop(self):
        """Stop the worker gracefully."""
        self.stop_requested = True


class WorkerThread(QThread):
    workerthread_finished = Signal(int, str)
    logger = logging.getLogger(__name__)

    def __init__(self, worker, channel, key):
        super().__init__()
        self.worker = worker
        self.channel = channel
        self.key = key
        self.logger = logging.getLogger(f"WorkerThread[{self.key}/{self.channel}]")
        self.logger.debug("WorkerThread initialized.")

    @log(logger=logger)
    def run(self):
        """Run the worker inside the thread."""
        self.logger.info("WorkerThread started.")
        self.worker.run()
        self.workerthread_finished.emit(self.channel, self.key)
        self.logger.info("WorkerThread finished.")
