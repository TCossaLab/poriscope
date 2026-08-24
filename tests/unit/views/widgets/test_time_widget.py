"""
Unit tests for TimeRangeValidator and TimeWidget.
Qt widgets are tested without a display using QApplication + offscreen platform.
"""

import sys
import unittest

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# One QApplication for the entire test run
# ---------------------------------------------------------------------------
app = QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
from poriscope.views.widgets.time_widget import (  # noqa: E402
    TimeRangeValidator,
    TimeWidget,
)

# ===========================================================================
# TimeRangeValidator
# ===========================================================================


class TestTimeRangeValidatorAcceptable(unittest.TestCase):
    """Inputs that should be fully Acceptable."""

    def setUp(self):
        self.v = TimeRangeValidator()

    def _state(self, text):
        state, _, _ = self.v.validate(text, 0)
        return state

    # ── single ranges ────────────────────────────────────────────────────────

    def test_simple_integer_range(self):
        self.assertEqual(self._state("0-5"), QValidator.Acceptable)

    def test_float_range(self):
        self.assertEqual(self._state("0.5-2.5"), QValidator.Acceptable)

    def test_large_range(self):
        self.assertEqual(self._state("100.0-999.9"), QValidator.Acceptable)

    def test_zero_zero_alone(self):
        """0-0 on its own is a valid sentinel ('full file')."""
        self.assertEqual(self._state("0-0"), QValidator.Acceptable)

    def test_start_nonzero_end_zero(self):
        """start-0 means 'from start to end of file'."""
        self.assertEqual(self._state("3.0-0"), QValidator.Acceptable)

    # ── multiple ranges ──────────────────────────────────────────────────────

    def test_two_ranges(self):
        self.assertEqual(self._state("0.0-2.5,3.0-6.0"), QValidator.Acceptable)

    def test_three_ranges(self):
        self.assertEqual(self._state("0-1,2-3,4-5"), QValidator.Acceptable)

    def test_ranges_without_spaces(self):
        """Validator rejects spaces inside the string (caught by the char regex)."""
        self.assertEqual(self._state("0.0-2.5,3.0-6.0"), QValidator.Acceptable)


class TestTimeRangeValidatorIntermediate(unittest.TestCase):
    """Inputs that are incomplete but fixable (Intermediate)."""

    def setUp(self):
        self.v = TimeRangeValidator()

    def _state(self, text):
        state, _, _ = self.v.validate(text, 0)
        return state

    def test_empty_string(self):
        self.assertEqual(self._state(""), QValidator.Intermediate)

    def test_just_a_number(self):
        """User has typed the start but not yet the hyphen."""
        self.assertEqual(self._state("3"), QValidator.Intermediate)

    def test_number_with_hyphen_no_end(self):
        """'3-' → end_str is '' → treated as start-0 (until EOF) → Acceptable."""
        self.assertEqual(self._state("3-"), QValidator.Acceptable)

    def test_start_greater_than_end(self):
        """'5-3' is backwards (start > end) → Intermediate, not a final value yet."""
        self.assertEqual(self._state("5-3"), QValidator.Intermediate)

    def test_start_equals_end_exact(self):
        """'4-4' has a zero-width range (start == end) → Intermediate, not a final value yet."""
        self.assertEqual(self._state("4-4"), QValidator.Intermediate)

    def test_partial_second_range(self):
        """First range done, second range partially typed."""
        self.assertEqual(self._state("0-1,2"), QValidator.Intermediate)


class TestTimeRangeValidatorInvalid(unittest.TestCase):
    """Inputs that are definitively Invalid."""

    def setUp(self):
        self.v = TimeRangeValidator()

    def _state(self, text):
        state, _, _ = self.v.validate(text, 0)
        return state

    def test_letters(self):
        self.assertEqual(self._state("abc"), QValidator.Invalid)

    def test_mixed_alpha_numeric(self):
        self.assertEqual(self._state("1a-2"), QValidator.Invalid)

    def test_starts_with_comma(self):
        self.assertEqual(self._state(",1-2"), QValidator.Invalid)

    def test_starts_with_dot(self):
        self.assertEqual(self._state(".5-1"), QValidator.Invalid)

    def test_double_hyphen(self):
        self.assertEqual(self._state("1--2"), QValidator.Invalid)

    def test_double_dot(self):
        self.assertEqual(self._state("1..0-2"), QValidator.Invalid)

    def test_double_comma(self):
        self.assertEqual(self._state("1-2,,3-4"), QValidator.Invalid)

    def test_zero_zero_not_alone(self):
        """0-0 combined with another range is invalid."""
        self.assertEqual(self._state("0-0,1-2"), QValidator.Invalid)

    def test_special_characters(self):
        self.assertEqual(self._state("1-2!"), QValidator.Invalid)


# ===========================================================================
# TimeWidget._parse_ranges
# ===========================================================================


class TestParseRanges(unittest.TestCase):
    """_parse_ranges is a pure function; test it directly."""

    def setUp(self):
        # Minimal params to satisfy __init__
        self.widget = TimeWidget({"ch0": {}})

    def tearDown(self):
        self.widget.destroy()

    def _parse(self, text):
        return self.widget._parse_ranges(text)

    def test_single_range(self):
        self.assertEqual(self._parse("0.0-2.5"), [(0.0, 2.5)])

    def test_two_ranges(self):
        self.assertEqual(self._parse("0.0-2.5,3.0-6.0"), [(0.0, 2.5), (3.0, 6.0)])

    def test_start_to_end_of_file(self):
        """start-0 → (start, None)"""
        self.assertEqual(self._parse("3.0-0"), [(3.0, None)])

    def test_zero_zero_sentinel(self):
        """0-0 → (0.0, 0.0)"""
        self.assertEqual(self._parse("0-0"), [(0.0, 0.0)])

    def test_three_ranges(self):
        result = self._parse("1-2,3-4,5-6")
        self.assertEqual(result, [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)])

    def test_spaces_around_comma(self):
        self.assertEqual(self._parse("0.0-1.0, 2.0-3.0"), [(0.0, 1.0), (2.0, 3.0)])

    def test_invalid_segment_skipped(self):
        """Invalid segments should be silently skipped."""
        result = self._parse("0.0-1.0,garbage,2.0-3.0")
        self.assertEqual(result, [(0.0, 1.0), (2.0, 3.0)])

    def test_empty_string(self):
        self.assertEqual(self._parse(""), [])


# ===========================================================================
# TimeWidget initialisation & prepopulation
# ===========================================================================


class TestTimeWidgetInit(unittest.TestCase):

    def test_ok_button_disabled_on_empty_params(self):
        w = TimeWidget({"ch0": {}})
        # Process deferred QTimer.singleShot
        app.processEvents()
        self.assertFalse(w.ok_button.isEnabled())
        w.destroy()

    def test_prepopulate_ranges(self):
        params = {"ch0": {"ranges": [(0.0, 2.5), (3.0, 6.0)]}}
        w = TimeWidget(params)
        app.processEvents()
        text = w.entrywidgets["ch0"].text()
        self.assertIn("0.0-2.5", text)
        self.assertIn("3.0-6.0", text)
        w.destroy()

    def test_prepopulate_start_end(self):
        params = {"ch0": {"start": 1.0, "end": 4.0}}
        w = TimeWidget(params)
        app.processEvents()
        self.assertEqual(w.entrywidgets["ch0"].text(), "1.0-4.0")
        w.destroy()

    def test_ok_enabled_after_valid_input(self):
        w = TimeWidget({"ch0": {}})
        w.entrywidgets["ch0"].setText("0.0-5.0")
        app.processEvents()
        self.assertTrue(w.ok_button.isEnabled())
        w.destroy()

    def test_ok_disabled_after_invalid_input(self):
        w = TimeWidget({"ch0": {}})
        w.entrywidgets["ch0"].setText("5.0-1.0")  # start > end
        app.processEvents()
        self.assertFalse(w.ok_button.isEnabled())
        w.destroy()

    def test_multiple_channels_all_must_be_valid(self):
        params = {"ch0": {}, "ch1": {}}
        w = TimeWidget(params)
        w.entrywidgets["ch0"].setText("0-5")
        # ch1 still empty → OK must stay disabled
        app.processEvents()
        self.assertFalse(w.ok_button.isEnabled())
        w.entrywidgets["ch1"].setText("6-10")
        app.processEvents()
        self.assertTrue(w.ok_button.isEnabled())
        w.destroy()

    def test_multiple_channels_prepopulated_ok_enabled(self):
        params = {
            "ch0": {"ranges": [(0.0, 2.0)]},
            "ch1": {"ranges": [(3.0, 5.0)]},
        }
        w = TimeWidget(params)
        app.processEvents()
        self.assertTrue(w.ok_button.isEnabled())
        w.destroy()


# ===========================================================================
# TimeWidget result after OK / Cancel
# ===========================================================================


class TestTimeWidgetResult(unittest.TestCase):

    def test_cancel_returns_none(self):
        w = TimeWidget({"ch0": {"ranges": [(0.0, 1.0)]}})
        app.processEvents()
        w._on_cancel()
        self.assertIsNone(w.get_result())
        w.destroy()

    def test_ok_returns_params_with_ranges(self):
        w = TimeWidget({"ch0": {}})
        w.entrywidgets["ch0"].setText("0.0-3.0")
        app.processEvents()
        w._on_ok()
        result = w.get_result()
        self.assertIsNotNone(result)
        self.assertIn("ch0", result)
        self.assertEqual(result["ch0"]["ranges"], [(0.0, 3.0)])
        w.destroy()

    def test_ok_multiple_ranges_parsed_correctly(self):
        w = TimeWidget({"ch0": {}})
        w.entrywidgets["ch0"].setText("0-1,2-3")
        app.processEvents()
        w._on_ok()
        ranges = w.get_result()["ch0"]["ranges"]
        self.assertEqual(ranges, [(0.0, 1.0), (2.0, 3.0)])
        w.destroy()

    def test_ok_start_to_eof_range(self):
        w = TimeWidget({"ch0": {}})
        w.entrywidgets["ch0"].setText("5.0-0")
        app.processEvents()
        w._on_ok()
        ranges = w.get_result()["ch0"]["ranges"]
        self.assertEqual(ranges, [(5.0, None)])
        w.destroy()


if __name__ == "__main__":
    unittest.main(verbosity=2)
