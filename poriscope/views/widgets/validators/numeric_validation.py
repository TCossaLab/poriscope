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

from PySide6.QtGui import QDoubleValidator, QIntValidator, QValidator
from PySide6.QtWidgets import QLineEdit

from poriscope.utils.LogDecorator import log


class NumericLineEdit(QLineEdit):
    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.validator = None

    @log(logger=logger)
    def setRange(self, min_val, max_val, valtype):
        min_val = valtype(min_val) if min_val is not None else None
        max_val = valtype(max_val) if max_val is not None else None
        if valtype is int:
            # Use the custom validator for integers
            self.validator = CustomIntValidator(min_val, max_val, self)
        elif valtype is float:
            # Use the QDoubleValidator for floating-point numbers
            self.validator = QDoubleValidator(self)
            if min_val is not None:
                self.validator.setBottom(min_val)
            if max_val is not None:
                self.validator.setTop(max_val)
        else:
            raise TypeError("Invalid min/max value types")

        self.setValidator(self.validator)

    def isValid(self):
        if self.text() == "":
            return False
        if self.validator is not None:
            state, _, _ = self.validator.validate(self.text(), 0)
        else:
            raise AttributeError("Validator is not set in numeric_validation;")
        return state == QValidator.Acceptable

    def currentText(self):
        if isinstance(self.validator, QIntValidator):
            return int(self.text())
        elif isinstance(self.validator, QDoubleValidator):
            return float(self.text())
        else:
            return self.text()


class CustomIntValidator(QValidator):
    def __init__(self, min_val=None, max_val=None, parent=None):
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_text, pos):
        if input_text == "":
            return QValidator.Intermediate, input_text, pos

        try:
            value = int(input_text)
        except ValueError:
            return QValidator.Invalid, input_text, pos

        if (self.min_val is not None and value < self.min_val) or (
            self.max_val is not None and value > self.max_val
        ):
            return QValidator.Invalid, input_text, pos

        return QValidator.Acceptable, input_text, pos
