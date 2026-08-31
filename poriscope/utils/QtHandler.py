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
# Alejandra Carolina González González

import logging
from collections import deque
from typing import Deque, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QMessageBox

# How many records may wait behind an open dialog before further ones are
# collapsed into a single "N more suppressed" notice. A cap is needed because a
# failing per-event or per-channel code path can log hundreds of records in a
# second, and one modal dialog per record would wedge the application.
MAX_PENDING_RECORDS = 10


# QObject designed solely to emit signals
class MessageBoxEmitter(QObject):
    emit_message = Signal(object)


class QtHandler(logging.Handler):
    """Surface log records to the user as modal dialogs.

    Attached to the root logger by :meth:`poriscope.main_app.App.configure_logger`
    alongside the console and file handlers.

    The default level is ``ERROR``, not ``NOTSET``. Log severity is not a
    statement about how the user should be interrupted: routine states legitimately
    log at ``WARNING`` - an empty channel, a cold start with no analysis tabs
    instantiated yet, an operation proceeding without an optional filter - and none
    of those warrant a modal dialog. Anything the user should be *told* rather than
    *interrupted* by belongs on the ``add_text_to_display`` panel instead.

    Note :meth:`poriscope.models.main_model.MainModel.update_logging_level`
    deliberately skips this handler when it applies a new level to the root logger's
    handlers, so choosing a more verbose log level does not turn warnings back into
    dialogs.
    """

    def __init__(self, parent: Optional[QObject] = None, level: int = logging.ERROR):
        """Build the handler and its cross-thread emitter.

        :param parent: Unused; accepted for symmetry with QObject constructors.
        :type parent: Optional[QObject]
        :param level: Minimum level that raises a dialog. Defaults to ``ERROR``.
        :type level: int
        """
        super().__init__(level)
        # Create an instance of the internal QObject to handle signal emissions
        self.emitter = MessageBoxEmitter()
        # Connect the internal signal to the message box displaying slot - queued connection to ensure thread safety
        self.emitter.emit_message.connect(self.show_message_box, Qt.QueuedConnection)
        self._dialog_open = False
        self._pending: Deque[logging.LogRecord] = deque()
        self._current_text: Optional[str] = None
        self._suppressed = 0

    def emit(self, record: logging.LogRecord) -> None:
        """Hand the record to the GUI thread.

        :param record: The record to display.
        :type record: logging.LogRecord
        """
        # Emit the signal with the log record
        self.emitter.emit_message.emit(record)

    @Slot(object)
    def show_message_box(self, record: logging.LogRecord) -> None:
        """Display one record, queueing any that arrive while a dialog is up.

        A modal QMessageBox runs its own nested event loop, during which further
        queued records are still delivered here. They used to be dropped outright,
        so a burst of genuine errors showed the first and silently lost the rest -
        the empty-state path that logs twice in a row lost its second message every
        time. They are now queued and shown in turn once the dialog closes.

        :param record: The record to display.
        :type record: logging.LogRecord
        """
        if self._dialog_open:
            self._queue_record(record)
            return
        self._dialog_open = True
        text = self.format(record)
        self._current_text = text
        try:
            # Create the message box based on the log level
            if record.levelno >= logging.ERROR:
                QMessageBox.critical(None, "Error", text)
            elif record.levelno >= logging.WARNING:
                QMessageBox.warning(None, "Warning", text)
        finally:
            self._dialog_open = False
            self._current_text = None
            self._show_next_pending()

    def _queue_record(self, record: logging.LogRecord) -> None:
        """Hold a record that arrived while a dialog was open.

        Records whose formatted text matches the one currently on screen, or one
        already waiting, are dropped rather than queued - so a loop logging the same
        failure per event or per channel yields one dialog rather than one per
        iteration. Distinct messages are all kept.

        :param record: The record to queue.
        :type record: logging.LogRecord
        """
        text = self.format(record)
        if text == self._current_text:
            return
        if any(self.format(pending) == text for pending in self._pending):
            return
        if len(self._pending) >= MAX_PENDING_RECORDS:
            self._suppressed += 1
            return
        self._pending.append(record)

    def _show_next_pending(self) -> None:
        """Re-post the next queued record, or report what was suppressed.

        The record is re-posted through the emitter rather than displayed directly
        so that it is handled on a later turn of the event loop; showing it inline
        would nest one dialog's handler inside another's for the whole queue.
        """
        if self._pending:
            self.emitter.emit_message.emit(self._pending.popleft())
            return
        if self._suppressed:
            suppressed, self._suppressed = self._suppressed, 0
            QMessageBox.warning(
                None,
                "Warning",
                f"{suppressed} further message(s) were suppressed while this dialog "
                "was open. See the log file for the full record.",
            )
