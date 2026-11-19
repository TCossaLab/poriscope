"""
A validator holds its line edit weakly, so the two never form a reference cycle.

PySide hands a line edit's validator to the line edit, which keeps it alive. A
validator that also kept its line edit made a cycle that only the cyclic garbage
collector could free, and tearing that pair down corrupted the native heap: in
November 2026 the Windows CI leg crashed in pytest-qt's event processing right after
the first test that built an unparented ``IntegerRangeLineEdit``.
"""

from typing import Any, Type

import pytest
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QLineEdit

from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.views.float_range_line_edit import FloatRangeLineEdit
from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit, RangeValidator


@pytest.mark.parametrize("line_edit_cls", [IntegerRangeLineEdit, FloatRangeLineEdit])
def test_a_validator_holds_no_strong_reference_to_its_line_edit(
    qtbot: Any, line_edit_cls: Type[BaseLineEdit]
) -> None:
    field = line_edit_cls()
    qtbot.addWidget(field)
    validator = field.validator()

    assert validator.line_edit is field
    assert all(value is not field for value in vars(validator).values())


def test_a_validator_whose_line_edit_is_gone_validates_the_text_as_finished(
    qapp: Any,
) -> None:
    validator = RangeValidator(QLineEdit())

    assert validator.line_edit is None
    assert validator.validate("1-", 2)[0] == QValidator.State.Invalid
