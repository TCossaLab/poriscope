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
import re
import sys

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.utils.BaseValidator import BaseValidator

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)


class FloatRangeValidator(BaseValidator):
    logger = logging.getLogger(__name__)

    def has_forbidden_characters(self, input):
        """Check for forbidden characters specific to float ranges (commas are forbidden)."""
        return re.search(r"[^0-9.\-]", input)  # Allow only digits, dots, and hyphens

    def _validate_intermediate(self, input, pos):
        """Intermediate validation logic for float ranges, allowing incomplete inputs."""
        if input.endswith("-") or input.endswith(",") or input.endswith("."):
            return QValidator.Intermediate, input, pos
        return QValidator.Acceptable, input, pos

    def _validate_final(self, input):
        """Final validation logic for float ranges, enforcing correct format."""
        if input.endswith(",") or input.endswith("-") or input.endswith("."):
            return QValidator.Invalid, input, len(input)

        # Strip any leading or trailing spaces
        input = input.strip()

        # Validate the single range (e.g., "start-end")
        if "-" in input:
            try:
                # Split the input by the hyphen and convert to float
                start, end = map(float, input.split("-"))
                if start >= end:  # Ensure start is less than end
                    self.logger.debug(
                        f"Invalid range: start ({start}) is not less than end ({end})."
                    )
                    return QValidator.Invalid, input, len(input)
            except ValueError:
                self.logger.error(f"Invalid number format in input: '{input}'")
                return QValidator.Invalid, input, len(input)
        else:
            # Reject if no hyphen is found, as we expect a range like "start-end"
            self.logger.debug(
                f"Invalid input: '{input}' does not contain a valid range."
            )
            return QValidator.Invalid, input, len(input)

        # If everything is valid
        return QValidator.Acceptable, input, len(input)


class FloatRangeLineEdit(BaseLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._used_floats = False

    def create_validator(self):
        return FloatRangeValidator(self)

    def get_values(self):
        """Parse and return a list of floats covering the defined ranges."""
        text = self.text()
        result = set()
        self._used_floats = False  # Reset before parsing

        segments = text.split(",")
        for segment in segments:
            segment = segment.strip()
            if "-" in segment:
                try:
                    start_str, end_str = segment.split("-")
                    start = float(start_str)
                    end = float(end_str)
                    if "." in start_str or "." in end_str:
                        self._used_floats = True
                    result.update(
                        [start + i * 0.1 for i in range(int((end - start) * 10) + 1)]
                    )
                except ValueError:
                    self.logger.error(f"Invalid range in segment: '{segment}'")
            else:
                try:
                    num = float(segment)
                    if "." in segment:
                        self._used_floats = True
                    result.add(num)
                except ValueError:
                    self.logger.error(f"Invalid float in segment: '{segment}'")

        return sorted(result)

    def get_values_with_type_info(self):
        """
        Returns a tuple of (parsed values, used_floats flag).
        Example: ([1.0, 1.1, 1.2], True)
        """
        values = self.get_values()
        return values, self._used_floats

    def used_floats(self) -> bool:
        return self._used_floats

    def get_start(self):
        """Extracts and returns the starting float of the first valid range or number."""
        text = self.text().strip()
        if not text:
            self.logger.error("Start time input is empty.")
            return None

        first_segment = text.split(",")[0].strip()
        if "-" in first_segment:
            try:
                start, _ = map(float, first_segment.split("-"))
                return start
            except ValueError as e:
                self.logger.error(
                    f"Invalid range format in segment: '{first_segment}' with error: {e}"
                )
        else:
            try:
                return float(first_segment)
            except ValueError as e:
                self.logger.error(
                    f"Invalid float conversion for input: '{first_segment}' with error: {e}"
                )

        return None

    def get_duration(self):
        """Calculates and returns the duration of the first valid range."""
        values = self.get_values()
        if values:
            return max(values) - min(values)
        return None

    def set_range(self, start: float, duration: float):
        """
        Sets the displayed text to a formatted range like '1.0-4.0' or '1-4' depending on whether
        the user originally used floats.
        """
        end = start + duration
        if self._used_floats:
            self.setText(f"{start:.1f}-{end:.1f}")
        else:
            self.setText(f"{int(round(start))}-{int(round(end))}")


# Main application setup
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = QMainWindow()
    mainWidget = QWidget()
    mainLayout = QVBoxLayout()

    label = QLabel("Enter float ranges (e.g., 1.0-5.0, 10.1-20.2):")
    lineEdit = FloatRangeLineEdit()
    mainLayout.addWidget(label)
    mainLayout.addWidget(lineEdit)

    mainWidget.setLayout(mainLayout)
    mainWindow.setCentralWidget(mainWidget)
    mainWindow.show()

    sys.exit(app.exec())
