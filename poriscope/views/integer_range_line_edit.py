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
from typing import Set

from PySide6.QtGui import QValidator

from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.utils.BaseValidator import BaseValidator


class RangeValidator(BaseValidator):
    logger = logging.getLogger(__name__)

    def has_forbidden_characters(self, input):
        return re.search(r"[^0-9,\-]", input)

    def _validate_intermediate(self, input, pos):
        """Intermediate validation logic for integer ranges."""
        self.logger.debug(f"Intermediate validation for input: {input}")

        # Allow trailing commas or hyphens during typing
        if input.endswith(",") or input.endswith("-"):
            self.logger.debug(
                f"Intermediate validation allows trailing comma or hyphen: {input}"
            )
            return QValidator.Intermediate, input, pos

        # Split the input by commas to handle each part
        parts = input.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                numbers = part.split("-")

                # Allow incomplete ranges during intermediate typing
                if len(numbers) == 2 and len(numbers[1]) == 0:
                    self.logger.debug(
                        "Intermediate validation: incomplete range, still typing."
                    )
                    return QValidator.Intermediate, input, pos

                try:
                    start = int(numbers[0])
                    end = int(numbers[1])

                    # Allow start > end during intermediate typing
                    if start > end:
                        self.logger.debug(
                            f"Intermediate validation: {start}-{end} (start > end), waiting for correction."
                        )
                        return QValidator.Intermediate, input, pos
                except ValueError:
                    self.logger.debug(f"Invalid range values in part: {part}")
                    return QValidator.Invalid, input, pos
            else:
                # Handle single numbers
                try:
                    int(part)
                except ValueError:
                    self.logger.debug(f"Invalid single value in part: {part}")
                    return QValidator.Invalid, input, pos

        # If we reach here, the input is valid and complete during intermediate typing
        self.logger.debug(
            "Intermediate validation passed: input is complete and valid."
        )
        return QValidator.Acceptable, input, len(input)

    def _validate_final(self, input):
        """Final validation for integer ranges."""
        self.logger.debug(f"Final validation for input: {input}")

        # Disallow trailing commas in final validation
        if input.endswith(","):
            self.logger.debug("Invalid input: trailing comma.")
            return QValidator.Invalid, input, 0

        parts = input.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                numbers = part.split("-")
                if len(numbers[0]) == 0 or len(numbers[1]) == 0:
                    self.logger.debug(f"Invalid range: incomplete range in '{part}'.")
                    return (
                        QValidator.Invalid,
                        input,
                        0,
                    )  # Invalid if the range is incomplete

                try:
                    start = int(numbers[0])
                    end = int(numbers[1])

                    # Strict validation: start must be smaller than end for final validation
                    if start >= end:
                        self.logger.debug(
                            f"Invalid range: {part}. Start ({start}) is not smaller than end ({end})."
                        )
                        return QValidator.Invalid, input, 0
                except ValueError:
                    return QValidator.Invalid, input, 0  # Invalid if not integers
            else:
                try:
                    int(part)  # Validate individual integers
                except ValueError:
                    self.logger.debug(f"Invalid integer: '{part}'")
                    return QValidator.Invalid, input, 0

        self.logger.debug("Final validation passed: input is acceptable.")
        return QValidator.Acceptable, input, len(input)


class IntegerRangeLineEdit(BaseLineEdit):
    logger = logging.getLogger(__name__)

    def create_validator(self):
        """Create the range validator for integer ranges."""
        return RangeValidator(self)

    def get_values(self):
        """Parse the text and return a sorted list of integers."""
        text = self.text()
        result: Set[int] = set()
        segments = text.split(",")
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            if "-" in segment:
                try:
                    start, end = map(int, segment.split("-"))
                    result.update(range(start, end + 1))
                except ValueError:
                    self.logger.debug(f"Invalid range in segment: '{segment}'")
            else:
                try:
                    result.add(int(segment))
                except ValueError:
                    self.logger.debug(f"Invalid integer in segment: '{segment}'")
        return sorted(result)

    def set_range(self, value: str):
        """
        Sets the input text for the line edit and triggers any connected signals or validation.
        """
        self.setText(value)
