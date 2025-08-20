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

from PySide6.QtCore import QEvent
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QLineEdit, QMessageBox

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class BaseLineEdit(QLineEdit):
    suspend_validation = False  # Control flag to suspend validation
    app_closing = False  # Flag to check if the application is closing

    def __init__(self, parent=None):
        super().__init__(parent)
        QApplication.instance().installEventFilter(self)  # Install global event filter
        QApplication.instance().aboutToQuit.connect(
            self.on_app_about_to_quit
        )  # Connect to the aboutToQuit signal

        try:
            validator = self.create_validator()
            if validator:
                self.setValidator(validator)
        except Exception:
            QMessageBox.critical(
                self, "Error", "Failed to initialize validator for BaseLineEdit."
            )
            raise ValueError("Failed to initialize validator for BaseLineEdit.")

    def create_validator(self):
        """Subclasses must override this method to return the appropriate validator."""
        pass

    def isValid(self):
        """Validates the current text of the line edit using the attached validator."""
        if BaseLineEdit.suspend_validation or BaseLineEdit.app_closing:
            return True
        validator = self.validator()
        if validator:
            state, _, _ = validator.validate(self.text(), 0)
            logging.debug(
                f"Validation state for {self.text()}: {state}"
            )  # Log the validation state
            return state == QValidator.Acceptable
        return False

    def focusOutEvent(self, event):
        """Handles the focus-out event to perform validation."""
        if BaseLineEdit.app_closing:
            # Do not process any focusOut events if the app is closing
            return
        if not self.isValid() and self.text() != "":
            self.setStyleSheet("border: 2px solid red;")
            self.setToolTip("Invalid input. Please enter a valid value.")
            event.ignore()  # Keep focus if validation fails
            self.setFocus()
        else:
            self.setStyleSheet("")  # Reset style if input is valid
            self.setToolTip("")  # Clear tooltip
            super().focusOutEvent(event)

    def eventFilter(self, obj, event):
        """Filter out focus-out events caused by QMessageBox to avoid validation issues."""
        if isinstance(obj, QMessageBox) and event.type() == QEvent.Show:
            BaseLineEdit.suspend_validation = True  # Suspend validation
        elif isinstance(obj, QMessageBox) and event.type() == QEvent.Hide:
            BaseLineEdit.suspend_validation = False  # Resume validation
        return super().eventFilter(obj, event)

    def on_app_about_to_quit(self):
        """Handle the application's about to quit signal."""
        BaseLineEdit.app_closing = True  # Set the flag indicating the app is closing
