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
import re
from abc import abstractmethod

from PySide6.QtGui import QValidator


class BaseValidator(QValidator):
    logger = logging.getLogger(__name__)

    def __init__(self, line_edit):
        super().__init__()
        self.line_edit = line_edit
        # this is a test

    def common_validation(self, input, pos):
        """Common validation logic to be applied implicitly by the base class."""
        if input == "":
            self.logger.debug("Input is empty but allowed.")
            return QValidator.Intermediate, input, pos

        # Disallow forbidden characters (can be customized by subclasses)
        if self.has_forbidden_characters(input):
            return QValidator.Invalid, input, pos

        # Disallow starting with a hyphen or comma
        if input.startswith("-") or input.startswith(","):
            self.logger.debug("Invalid input: starts with a hyphen or comma.")
            return QValidator.Invalid, input, pos

        # Disallow two or more consecutive hyphens, commas, or dots
        if re.search(r"-{2,}|,{2,}|\.{2,}", input):
            self.logger.debug(
                "Invalid input: contains two or more consecutive hyphens, commas, or dots."
            )
            return QValidator.Invalid, input, pos

        return QValidator.Acceptable, input, pos

    def has_forbidden_characters(self, input):
        """Check for forbidden characters. This can be overridden by subclasses."""
        # Default: disallow anything other than digits, commas, and hyphens
        return re.search(r"[^0-9,\-\.]", input)

    def validate(self, input, pos):
        """Base validation method that automatically handles common, intermediate, and final validation."""
        try:
            # Apply common validation
            state, input, pos = self.common_validation(input, pos)

            # If common validation fails, return immediately
            if state != QValidator.Acceptable:
                return state, input, pos

            # Automatically handle focus-based decision between intermediate and final validation
            if self.line_edit.hasFocus():
                return self._validate_intermediate(input, pos)
            else:
                return self._validate_final(input)
        except Exception as e:
            self.logger.error(f"Error during validation: {str(e)}")
            return QValidator.Invalid, input, pos

    @abstractmethod
    def _validate_intermediate(self, input, pos):
        """Intermediate validation to be implemented in subclass."""
        raise NotImplementedError(
            "Subclasses must implement the '_validate_intermediate' method."
        )

    @abstractmethod
    def _validate_final(self, input):
        """Final validation to be implemented in subclass."""
        raise NotImplementedError(
            "Subclasses must implement the '_validate_final' method."
        )
