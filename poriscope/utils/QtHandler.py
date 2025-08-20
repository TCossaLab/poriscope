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

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QMessageBox


# QObject designed solely to emit signals
class MessageBoxEmitter(QObject):
    emit_message = Signal(object)


class QtHandler(logging.Handler):
    def __init__(self, parent=None):
        super().__init__()
        # Create an instance of the internal QObject to handle signal emissions
        self.emitter = MessageBoxEmitter()
        # Connect the internal signal to the message box displaying slot - queued connection to ensure thread safety
        self.emitter.emit_message.connect(self.show_message_box, Qt.QueuedConnection)

    def emit(self, record):
        # Emit the signal with the log record
        self.emitter.emit_message.emit(record)

    @Slot(object)
    def show_message_box(self, record):
        # Create the message box based on the log level
        if record.levelno >= logging.ERROR:
            QMessageBox.critical(None, "Error", self.format(record))
        elif record.levelno >= logging.WARNING:
            QMessageBox.warning(None, "Warning", self.format(record))
