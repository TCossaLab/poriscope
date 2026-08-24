"""
Unit tests for RangeValidator/IntegerRangeLineEdit (poriscope/views/integer_range_line_edit.py).

Covers:
- Mixed single-value/range combinations (e.g. "5,7-9,12-15,24") validating as
  Acceptable and resolving through get_values() to the correct flattened set.
- Leading '-' being rejected outright, since these fields only ever represent
  times or event indices, both of which are non-negative.
- Malformed multi-dash segments (e.g. "3-5-7") being rejected instead of being
  silently truncated to just the first two numbers.
"""

import pytest
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

from poriscope.views.integer_range_line_edit import IntegerRangeLineEdit, RangeValidator


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def validator(qt_app):
    return RangeValidator(None)


@pytest.fixture
def line_edit(qt_app):
    widget = IntegerRangeLineEdit()
    qt_app.processEvents()
    return widget


@pytest.mark.parametrize(
    "text",
    [
        "5,7-9,12-15,24",
        "1-3",
        "0-5",
        "5",
    ],
)
def test_final_validation_accepts_valid_combinations(validator, text):
    state, _, _ = validator._validate_final(text)
    assert state == QValidator.Acceptable


def test_get_values_resolves_mixed_single_values_and_ranges(line_edit):
    line_edit.setText("5,7-9,12-15,24")
    assert line_edit.get_values() == [5, 7, 8, 9, 12, 13, 14, 15, 24]


@pytest.mark.parametrize(
    "text",
    [
        "-5",
        "-5-10",
        "5--10",
        "5,-3",
        "3-5-7",
    ],
)
def test_final_validation_rejects_leading_minus_and_malformed_ranges(validator, text):
    state, _, _ = validator._validate_final(text)
    assert state == QValidator.Invalid


def test_get_values_skips_malformed_and_negative_segments(line_edit):
    line_edit.setText("5,-3,7-9,3-5-7")
    assert line_edit.get_values() == [5, 7, 8, 9]
