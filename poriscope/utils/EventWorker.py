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
from typing import Any, Generator

from PySide6.QtCore import QObject, QThread, Signal, Slot

from poriscope.utils.LogDecorator import log


class Worker(QObject):
    update_progressbar = Signal(float, str)
    stop_signal = Signal()
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        generator: Generator[Any, Any, Any],
        channel: int,
        key: str,
    ) -> None:
        super().__init__()
        self.generator = generator
        self.channel = channel
        self.stop_requested = False
        self.key = key
        self.logger = logging.getLogger(f"Worker[{self.key}/{self.channel}]")
        self.stop_signal.connect(self.stop)
        self.logger.debug("Worker initialized.")

    @log(logger=logger)
    def process_generator(self) -> None:
        """
        Drive the generator to completion on this worker's thread, relaying its yielded progress.

        The generator is primed with a single ``next()`` on the first iteration and driven with
        ``send(self.stop_requested)`` on every iteration after that. Priming explicitly matters:
        ``send()`` on a not-yet-started generator raises ``TypeError`` by design, and the loop
        used to absorb that with a blanket ``except TypeError: next(self.generator)``. That arm
        could not distinguish the unstarted-generator case from a ``TypeError`` raised inside the
        generator *body* - by which point the generator is already closed, so the ``next()``
        fallback raised ``StopIteration`` and the run was logged as a successful finish at INFO.
        A failed analysis was indistinguishable from one that legitimately found nothing.

        Every failure is therefore now reported through one ``except Exception`` arm, with a
        traceback. The typed arms this replaces (``RuntimeError``, ``ValueError``, ``IOError``)
        differed only in wording and all ended the run identically, and per-type special-casing
        in this loop is what allowed the bug above - so there is deliberately no per-type
        handling here beyond ``StopIteration``, which is the success path.

        Every exit arm emits a completion value for the progress bar explicitly rather than
        relying on the ``finally`` in :py:meth:`run`, and does so *before* logging the failure:
        the progress-bar teardown travels on a queued connection while an ERROR record raises a
        modal dialog, so emitting first is what stops the bar being stranded behind that dialog.
        """
        identifier = f"{self.key}/{self.channel}"
        p: float = 0
        started = False
        while True:
            self.logger.debug(f"Worker [{identifier}] waiting for generator output...")
            try:
                if started:
                    p = self.generator.send(self.stop_requested)
                else:
                    p = next(self.generator)
                    started = True
                self.logger.debug(f"Worker [{identifier}] Generator produced: {p}")
            except StopIteration:
                self.update_progressbar.emit(100, identifier)
                self.logger.info(f"Worker [{identifier}] Generator finished.")
                break
            except Exception as e:
                self.update_progressbar.emit(100, identifier)
                self.logger.exception(
                    f"Worker [{identifier}] failed after {'0' if not started else 'at least one'} "
                    f"generator step: {repr(e)}"
                )
                break
            else:
                progress = 100 * p
                self.update_progressbar.emit(progress, identifier)
                self.logger.debug(
                    f"Worker [{identifier}] Progress updated: {progress:.2f}%"
                )

    @log(logger=logger)
    def run(self) -> None:
        self.logger.info(f"Worker [{self.key}/{self.channel}] started.")
        p: float = 0
        self.update_progressbar.emit(p, f"{self.key}/{self.channel}")
        try:
            # Serialization across channels, where a plugin declares it is required, is
            # taken by the plugin itself inside its own generator; see
            # poriscope.utils.SerializeDecorator.serialize_channels. The worker used to
            # hold a lock supplied by MetaModel, which was scoped to the model rather than
            # to the plugin instance.
            self.process_generator()
        finally:
            self.update_progressbar.emit(100, f"{self.key}/{self.channel}")
            self.logger.info(f"Worker [{self.key}/{self.channel}] finished.")

    @Slot()
    @log(logger=logger)
    def stop(self) -> None:
        """Stop the worker gracefully."""
        self.stop_requested = True


class WorkerThread(QThread):
    workerthread_finished = Signal(int, str)
    logger = logging.getLogger(__name__)

    def __init__(self, worker: Worker, channel: int, key: str) -> None:
        super().__init__()
        self.worker = worker
        self.channel = channel
        self.key = key
        self.logger = logging.getLogger(f"WorkerThread[{self.key}/{self.channel}]")
        self.logger.debug("WorkerThread initialized.")

    @log(logger=logger)
    def run(self) -> None:
        """Run the worker inside the thread."""
        self.logger.info("WorkerThread started.")
        try:
            self.worker.run()
        except Exception:
            self.logger.exception(
                f"WorkerThread [{self.key}/{self.channel}] worker raised an unexpected exception."
            )
        finally:
            self.workerthread_finished.emit(self.channel, self.key)
            self.logger.info("WorkerThread finished.")
