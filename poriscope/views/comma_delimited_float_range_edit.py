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
from typing import List, Optional, Tuple

from PySide6.QtGui import QValidator

from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.utils.BaseValidator import BaseValidator


class CommaFloatRangeValidator(BaseValidator):
    logger = logging.getLogger(__name__)

    def has_forbidden_characters(self, input):
        """Only allow digits, dots, commas, and hyphens."""
        return re.search(r"[^0-9.,\-]", input)

    def _validate_intermediate(self, input, pos):
        """Allow intermediate inputs while editing."""
        if input == "" or input.endswith(("-", ",", ".")):
            return QValidator.Intermediate, input, pos
        return QValidator.Acceptable, input, pos

    def _validate_final(self, input):
        """Strict validation of float ranges."""
        input = input.strip()
        if input == "":
            return QValidator.Intermediate, input, len(input)

        if input.endswith(("-", ",", ".")):
            return QValidator.Invalid, input, len(input)

        parts = input.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                return QValidator.Invalid, input, len(input)

            if "-" not in part:
                self.logger.debug(f"Invalid input: '{part}' is not a range.")
                return QValidator.Invalid, input, len(input)

            try:
                start_str, end_str = part.split("-")
                start = float(start_str)
                end = float(end_str)

                # Disallow reversed ranges, unless end is 0 (open-ended)
                if start >= end and end != 0.0:
                    self.logger.debug(
                        f"Invalid range: start ({start}) is not less than end ({end})."
                    )
                    return QValidator.Invalid, input, len(input)

            except ValueError:
                self.logger.debug(f"Invalid float format in part: '{part}'")
                return QValidator.Invalid, input, len(input)

        return QValidator.Acceptable, input, len(input)


class CommaFloatRangeLineEdit(BaseLineEdit):
    logger = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._used_floats = False

    def create_validator(self):
        return CommaFloatRangeValidator(self)

    def get_values(self):
        """Parse and return a list of (start, end) tuples. None means open-ended."""
        text = self.text().strip()
        ranges: List[Tuple[Optional[float], Optional[float]]] = []
        self._used_floats = False

        if not text:
            return ranges

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

                    if start > end and end == 0.0:
                        ranges.append((start, None))  # open-ended
                    else:
                        ranges.append((start, end))
                except ValueError:
                    self.logger.error(f"Invalid range in segment: '{segment}'")
            else:
                self.logger.debug(f"Skipping non-range value: '{segment}'")

        return ranges

    def get_values_with_type_info(self):
        return self.get_values(), self._used_floats

    def used_floats(self) -> bool:
        return self._used_floats

    def get_start(self):
        values = self.get_values()
        if values:
            return values[0][0]
        return None

    def get_duration(self):
        values = self.get_values()
        if values:
            flat = [v for pair in values for v in pair if v is not None]
            return max(flat) - min(flat)
        return None

    def set_range(self, start: float, duration: float):
        end = start + duration
        if self._used_floats:
            self.setText(f"{start:.1f}-{end:.1f}")
        else:
            self.setText(f"{int(start)}-{int(end)}")
