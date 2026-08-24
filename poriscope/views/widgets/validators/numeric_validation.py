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
from typing import Optional, Tuple, Union

from PySide6.QtCore import QObject
from PySide6.QtGui import QDoubleValidator, QIntValidator, QValidator
from PySide6.QtWidgets import QLineEdit, QWidget

from poriscope.utils.LogDecorator import log


class NumericLineEdit(QLineEdit):
    logger = logging.getLogger(__name__)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._validator: Optional[QValidator] = None

    @log(logger=logger)
    def setRange(
        self,
        min_val: Optional[Union[int, float]],
        max_val: Optional[Union[int, float]],
        valtype: type,
    ) -> None:
        min_val = valtype(min_val) if min_val is not None else None
        max_val = valtype(max_val) if max_val is not None else None
        if valtype is int:
            # Use the custom validator for integers
            self._validator = CustomIntValidator(min_val, max_val, self)
        elif valtype is float:
            # Use the QDoubleValidator for floating-point numbers
            self._validator = QDoubleValidator(self)
            if min_val is not None:
                self._validator.setBottom(min_val)
            if max_val is not None:
                self._validator.setTop(max_val)
        else:
            raise TypeError("Invalid min/max value types")

        self.setValidator(self._validator)

    def isValid(self) -> bool:
        if self.text() == "":
            return False
        if self._validator is not None:
            state, _, _ = self._validator.validate(self.text(), 0)
        else:
            raise AttributeError("Validator is not set in numeric_validation;")
        return state == QValidator.Acceptable

    def currentText(self) -> Union[int, float, str]:
        if isinstance(self._validator, QIntValidator):
            return int(self.text())
        elif isinstance(self._validator, QDoubleValidator):
            return float(self.text())
        else:
            return self.text()


class CustomIntValidator(QValidator):
    def __init__(
        self,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, input_text: str, pos: int) -> Tuple[QValidator.State, str, int]:
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
