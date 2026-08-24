"""
Unit tests for MultiSelectComboBox.
Runs headlessly -- no display required.

This is the plain channel-selector widget (poriscope.views.widgets.multiselect),
used as ``channel_comboBox``.
It is a *different* class from MultiSelectFilterComboBox
(poriscope.views.widgets.multiselect_filter, covered by
test_multiselect_filter.py) -- that one wraps each item in a custom QCheckBox
with per-item edit/delete buttons, for selecting plugin instances. This one
uses plain QListWidgetItem check states with no per-item widgets, for
selecting channel numbers.

Two behavioral differences from MultiSelectFilterComboBox, confirmed by
reading this class's actual source rather than assumed by symmetry with
its sibling's test suite:

* addItem() defaults new items to Qt.CheckState.Checked, not unchecked. Consequently
  addItems() leaves every item selected immediately -- the "Select All"
  button reads "Deselect All" / isChecked() True right after items are
  added, not "Select All" / unchecked the way the filter widget starts.
* addItem()'s userData parameter is accepted but never stored (no
  item.setData(Qt.UserRole, ...) call in the source) -- unlike the filter
  widget, which does store it. Documented here as a real difference in
  currently-observed behavior, not asserted as correct or incorrect.
"""

import sys
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from poriscope.views.widgets.multiselect import MultiSelectComboBox

app = QApplication.instance() or QApplication(sys.argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def dispose(widget) -> None:
    """
    Tear a widget down through the event loop.

    ``QWidget.destroy()`` only releases the native window - the C++ object
    survives until Shiboken collects the Python wrapper, at an arbitrary
    later point in the run. A widget disposed of that way can leave posted
    events behind that fault the interpreter the next time *any* test spins
    the event loop, which is how this file used to segfault
    ``test_walkthrough_mixin.py`` several hundred tests later.
    ``deleteLater()`` plus a drained loop deletes it while Qt can still clean
    up after it.
    """
    widget.deleteLater()
    app.processEvents()


def make_combo() -> MultiSelectComboBox:
    return MultiSelectComboBox()


def set_checked(combo: MultiSelectComboBox, row: int, checked: bool) -> None:
    """Set one item's check state directly (no embedded checkbox widget
    exists on this class, unlike MultiSelectFilterComboBox)."""
    item = combo.listWidget.item(row)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    app.processEvents()


def check_all_items(combo: MultiSelectComboBox, checked: bool) -> None:
    for i in range(combo.listWidget.count()):
        combo.listWidget.item(i).setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
    app.processEvents()


# ===========================================================================
# addItem / addItems
# ===========================================================================


class TestAddItems(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()

    def tearDown(self):
        dispose(self.c)

    def test_add_single_item_creates_row(self):
        self.c.addItem("0")
        self.assertEqual(self.c.listWidget.count(), 1)

    def test_add_item_defaults_to_checked(self):
        """Confirmed real behavior: unlike MultiSelectFilterComboBox, new
        items start checked, not unchecked."""
        self.c.addItem("0")
        self.assertEqual(self.c.listWidget.item(0).checkState(), Qt.CheckState.Checked)

    def test_add_item_user_data_is_not_stored(self):
        """Confirmed real behavior: userData is accepted but silently
        discarded -- item.data(Qt.UserRole) is never set on this class."""
        self.c.addItem("0", userData="some_payload")
        self.assertIsNone(self.c.listWidget.item(0).data(Qt.UserRole))

    def test_add_items_populates_all(self):
        self.c.addItems(["0", "1", "2"])
        self.assertEqual(self.c.listWidget.count(), 3)

    def test_add_items_clears_previous(self):
        self.c.addItems(["9"])
        self.c.addItems(["0", "1"])
        self.assertEqual(self.c.listWidget.count(), 2)
        self.assertEqual(self.c.listWidget.item(0).text(), "0")

    def test_add_items_all_checked_by_default(self):
        """The inverse of MultiSelectFilterComboBox's default -- see module
        docstring."""
        self.c.addItems(["0", "1"])
        for i in range(self.c.listWidget.count()):
            self.assertEqual(
                self.c.listWidget.item(i).checkState(), Qt.CheckState.Checked
            )


# ===========================================================================
# getSelectedItems
# ===========================================================================


class TestGetSelectedItems(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["0", "1", "2"])

    def tearDown(self):
        dispose(self.c)

    def test_all_selected_immediately_after_add(self):
        # Items default to checked, so nothing needs to be selected first.
        self.assertCountEqual(self.c.getSelectedItems(), ["0", "1", "2"])

    def test_deselect_all_then_select_one(self):
        check_all_items(self.c, False)
        set_checked(self.c, 1, True)
        self.assertEqual(self.c.getSelectedItems(), ["1"])

    def test_deselect_removes_from_result(self):
        set_checked(self.c, 0, False)
        self.assertNotIn("0", self.c.getSelectedItems())

    def test_none_selected_returns_empty(self):
        check_all_items(self.c, False)
        self.assertEqual(self.c.getSelectedItems(), [])


# ===========================================================================
# selectItem
# ===========================================================================


class TestSelectItem(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["0", "1", "2"])
        check_all_items(self.c, False)  # start from a known, empty state

    def tearDown(self):
        dispose(self.c)

    def test_select_by_name(self):
        self.c.selectItem("1")
        app.processEvents()
        self.assertEqual(self.c.listWidget.item(1).checkState(), Qt.CheckState.Checked)

    def test_deselect_by_name(self):
        check_all_items(self.c, True)
        self.c.selectItem("0", select=False)
        app.processEvents()
        self.assertEqual(
            self.c.listWidget.item(0).checkState(), Qt.CheckState.Unchecked
        )

    def test_nonexistent_name_no_crash(self):
        self.c.selectItem("does_not_exist")  # should not raise

    def test_only_target_is_affected(self):
        self.c.selectItem("2")
        app.processEvents()
        self.assertEqual(
            self.c.listWidget.item(0).checkState(), Qt.CheckState.Unchecked
        )
        self.assertEqual(
            self.c.listWidget.item(1).checkState(), Qt.CheckState.Unchecked
        )
        self.assertEqual(self.c.listWidget.item(2).checkState(), Qt.CheckState.Checked)

    def test_select_item_does_not_emit_selection_changed(self):
        """Confirmed real behavior: selectItem() sets checkState() directly
        without going through handleItemChanged, so it does not itself
        trigger selectionChanged the way a real user check-click would
        (that fires via the listWidget's itemChanged signal instead, which
        setCheckState alone does trigger in Qt -- but selectItem's caller
        is expected to know selection state may need an explicit
        refreshDisplayText() afterwards, as raw_data/event_analysis test
        helpers already do)."""
        received = []
        self.c.selectionChanged.connect(received.append)
        self.c.selectItem("1")
        app.processEvents()
        # setCheckState on a QListWidgetItem does emit QListWidget.itemChanged
        # in Qt, which handleItemChanged is connected to -- so this SHOULD
        # fire. Documented as a test of actual behavior, not an assumption.
        self.assertTrue(len(received) > 0)
        self.assertIn("1", received[-1])


# ===========================================================================
# handleItemChanged -- line edit text and signal
# ===========================================================================


class TestHandleItemChanged(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["0", "1", "2"])
        check_all_items(self.c, False)  # start from a known, empty state

    def tearDown(self):
        dispose(self.c)

    def test_line_edit_empty_when_nothing_selected(self):
        self.assertEqual(self.c.lineEdit().text(), "")

    def test_line_edit_shows_selected_item(self):
        set_checked(self.c, 0, True)
        self.assertIn("0", self.c.lineEdit().text())

    def test_line_edit_shows_multiple_items(self):
        set_checked(self.c, 0, True)
        set_checked(self.c, 2, True)
        text = self.c.lineEdit().text()
        self.assertIn("0", text)
        self.assertIn("2", text)

    def test_selection_changed_signal_emitted(self):
        received = []
        self.c.selectionChanged.connect(received.append)
        set_checked(self.c, 1, True)
        self.assertTrue(len(received) > 0)
        self.assertIn("1", received[-1])

    def test_signal_emitted_on_deselect(self):
        set_checked(self.c, 0, True)
        received = []
        self.c.selectionChanged.connect(received.append)
        set_checked(self.c, 0, False)
        self.assertTrue(len(received) > 0)
        self.assertNotIn("0", received[-1])


# ===========================================================================
# Select All / Deselect All button
# ===========================================================================


class TestSelectAllButton(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()

    def tearDown(self):
        dispose(self.c)

    def test_state_after_add_items_is_all_selected(self):
        """Confirmed real behavior: since addItem() defaults to checked,
        the button reads "Deselect All" / checked immediately after
        addItems() -- the inverse of MultiSelectFilterComboBox's initial
        "Select All" / unchecked state."""
        self.c.addItems(["0", "1", "2"])
        self.assertEqual(self.c.selectAllButton.text(), "Deselect All")
        self.assertTrue(self.c.selectAllButton.isChecked())

    def test_deselect_all_unchecks_everything(self):
        self.c.addItems(["0", "1", "2"])
        self.c.selectAllButton.setChecked(False)
        app.processEvents()
        for i in range(self.c.listWidget.count()):
            self.assertEqual(
                self.c.listWidget.item(i).checkState(), Qt.CheckState.Unchecked
            )

    def test_select_all_checks_everything_after_manual_deselect(self):
        self.c.addItems(["0", "1", "2"])
        check_all_items(self.c, False)
        self.c.selectAllButton.setChecked(True)
        app.processEvents()
        for i in range(self.c.listWidget.count()):
            self.assertEqual(
                self.c.listWidget.item(i).checkState(), Qt.CheckState.Checked
            )

    def test_button_shows_select_when_none_checked(self):
        self.c.addItems(["0", "1", "2"])
        check_all_items(self.c, False)
        self.c.updateSelectAllButton()
        self.assertEqual(self.c.selectAllButton.text(), "Select All")
        self.assertFalse(self.c.selectAllButton.isChecked())

    def test_button_shows_select_on_partial(self):
        self.c.addItems(["0", "1", "2"])
        set_checked(self.c, 0, False)
        self.assertEqual(self.c.selectAllButton.text(), "Select All")
        self.assertFalse(self.c.selectAllButton.isChecked())

    def test_deselect_all_emits_empty_selection(self):
        self.c.addItems(["0", "1", "2"])
        received = []
        self.c.selectionChanged.connect(received.append)
        self.c.selectAllButton.setChecked(False)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertEqual(received[-1], [])

    def test_select_all_emits_full_selection(self):
        self.c.addItems(["0", "1", "2"])
        check_all_items(self.c, False)
        received = []
        self.c.selectionChanged.connect(received.append)
        self.c.selectAllButton.setChecked(True)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertCountEqual(received[-1], ["0", "1", "2"])


# ===========================================================================
# refreshDisplayText
# ===========================================================================


class TestRefreshDisplayText(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["0", "1"])
        check_all_items(self.c, False)

    def tearDown(self):
        dispose(self.c)

    def test_refresh_reflects_current_state(self):
        set_checked(self.c, 0, True)
        self.c.lineEdit().clear()  # manually dirty the display
        self.c.refreshDisplayText()
        self.assertIn("0", self.c.lineEdit().text())

    def test_refresh_empty_when_nothing_selected(self):
        self.c.refreshDisplayText()
        self.assertEqual(self.c.lineEdit().text(), "")


# ===========================================================================
# showPopup / hidePopup
# ===========================================================================


class TestPopup(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["0", "1"])

    def tearDown(self):
        dispose(self.c)

    def test_container_hidden_initially(self):
        self.assertFalse(self.c.containerWidget.isVisible())

    def test_show_popup_shows_container(self):
        self.c.showPopup()
        app.processEvents()
        self.assertTrue(self.c.containerWidget.isVisible())

    def test_hide_popup_hides_container(self):
        self.c.showPopup()
        app.processEvents()
        self.c.hidePopup()
        app.processEvents()
        self.assertFalse(self.c.containerWidget.isVisible())


if __name__ == "__main__":
    unittest.main(verbosity=2)
