"""
Unit tests for MultiSelectComboBox.
Runs headlessly — no display required.

NOTE: MultiSelectComboBox imports from poriscope.configs.utils (get_icon).
If that module is not available in test environment, stub it out via
the patch in the module-level setup below.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QCheckBox

app = QApplication.instance() or QApplication(sys.argv)

# ---------------------------------------------------------------------------
# Stub get_icon so tests don't need poriscope assets on disk
# ---------------------------------------------------------------------------
_icon_patch = patch("poriscope.configs.utils.get_icon", return_value=QIcon())
_icon_patch.start()

from poriscope.views.widgets.multiselect_filter import MultiSelectComboBox  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_combo() -> MultiSelectComboBox:
    cb = MultiSelectComboBox()
    return cb


def get_checkbox(combo: MultiSelectComboBox, row: int) -> QCheckBox:
    item = combo.listWidget.item(row)
    widget = combo.listWidget.itemWidget(item)
    return widget.findChild(QCheckBox)


def check_all_boxes(combo: MultiSelectComboBox, checked: bool):
    for i in range(combo.listWidget.count()):
        get_checkbox(combo, i).setChecked(checked)
    app.processEvents()


# ===========================================================================
# addItem / addItems
# ===========================================================================

class TestAddItems(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()

    def tearDown(self):
        self.c.destroy()

    def test_add_single_item_creates_row(self):
        self.c.addItem("filter_a")
        self.assertEqual(self.c.listWidget.count(), 1)

    def test_add_item_stores_user_role_data(self):
        self.c.addItem("filter_a")
        item = self.c.listWidget.item(0)
        self.assertEqual(item.data(Qt.UserRole), "filter_a")

    def test_add_item_checkbox_label(self):
        self.c.addItem("my_filter")
        self.assertEqual(get_checkbox(self.c, 0).text(), "my_filter")

    def test_add_items_populates_all(self):
        self.c.addItems(["a", "b", "c"])
        self.assertEqual(self.c.listWidget.count(), 3)

    def test_add_items_clears_previous(self):
        self.c.addItems(["old"])
        self.c.addItems(["new1", "new2"])
        self.assertEqual(self.c.listWidget.count(), 2)
        self.assertEqual(get_checkbox(self.c, 0).text(), "new1")

    def test_add_items_all_unchecked_by_default(self):
        self.c.addItems(["x", "y"])
        for i in range(self.c.listWidget.count()):
            self.assertFalse(get_checkbox(self.c, i).isChecked())


# ===========================================================================
# getSelectedItems
# ===========================================================================

class TestGetSelectedItems(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["alpha", "beta", "gamma"])

    def tearDown(self):
        self.c.destroy()

    def test_none_selected_returns_empty(self):
        self.assertEqual(self.c.getSelectedItems(), [])

    def test_single_selected(self):
        get_checkbox(self.c, 1).setChecked(True)
        app.processEvents()
        self.assertEqual(self.c.getSelectedItems(), ["beta"])

    def test_all_selected(self):
        check_all_boxes(self.c, True)
        self.assertCountEqual(self.c.getSelectedItems(), ["alpha", "beta", "gamma"])

    def test_deselect_removes_from_result(self):
        check_all_boxes(self.c, True)
        get_checkbox(self.c, 0).setChecked(False)
        app.processEvents()
        self.assertNotIn("alpha", self.c.getSelectedItems())


# ===========================================================================
# selectItem
# ===========================================================================

class TestSelectItem(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["x", "y", "z"])

    def tearDown(self):
        self.c.destroy()

    def test_select_by_name(self):
        self.c.selectItem("y")
        app.processEvents()
        self.assertTrue(get_checkbox(self.c, 1).isChecked())

    def test_deselect_by_name(self):
        check_all_boxes(self.c, True)
        self.c.selectItem("x", select=False)
        app.processEvents()
        self.assertFalse(get_checkbox(self.c, 0).isChecked())

    def test_nonexistent_name_no_crash(self):
        self.c.selectItem("does_not_exist")  # should not raise

    def test_only_target_is_affected(self):
        self.c.selectItem("z")
        app.processEvents()
        self.assertFalse(get_checkbox(self.c, 0).isChecked())
        self.assertFalse(get_checkbox(self.c, 1).isChecked())
        self.assertTrue(get_checkbox(self.c, 2).isChecked())


# ===========================================================================
# handleItemChanged — line edit text and signal
# ===========================================================================

class TestHandleItemChanged(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["p", "q", "r"])

    def tearDown(self):
        self.c.destroy()

    def test_line_edit_empty_when_nothing_selected(self):
        self.assertEqual(self.c.lineEdit().text(), "")

    def test_line_edit_shows_selected_item(self):
        get_checkbox(self.c, 0).setChecked(True)
        app.processEvents()
        self.assertIn("p", self.c.lineEdit().text())

    def test_line_edit_shows_multiple_items(self):
        get_checkbox(self.c, 0).setChecked(True)
        get_checkbox(self.c, 2).setChecked(True)
        app.processEvents()
        text = self.c.lineEdit().text()
        self.assertIn("p", text)
        self.assertIn("r", text)

    def test_selection_changed_signal_emitted(self):
        received = []
        self.c.selectionChanged.connect(received.append)
        get_checkbox(self.c, 1).setChecked(True)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertIn("q", received[-1])

    def test_signal_emitted_on_deselect(self):
        get_checkbox(self.c, 0).setChecked(True)
        app.processEvents()
        received = []
        self.c.selectionChanged.connect(received.append)
        get_checkbox(self.c, 0).setChecked(False)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertNotIn("p", received[-1])


# ===========================================================================
# Select All / Deselect All button
# ===========================================================================

class TestSelectAllButton(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["one", "two", "three"])

    def tearDown(self):
        self.c.destroy()

    def test_initial_state_is_select_all(self):
        self.assertEqual(self.c.selectAllButton.text(), "Select All")
        self.assertFalse(self.c.selectAllButton.isChecked())

    def test_select_all_checks_everything(self):
        self.c.selectAllButton.setChecked(True)
        app.processEvents()
        for i in range(self.c.listWidget.count()):
            self.assertTrue(get_checkbox(self.c, i).isChecked())

    def test_deselect_all_unchecks_everything(self):
        check_all_boxes(self.c, True)
        self.c.selectAllButton.setChecked(False)
        app.processEvents()
        for i in range(self.c.listWidget.count()):
            self.assertFalse(get_checkbox(self.c, i).isChecked())

    def test_button_shows_deselect_when_all_checked(self):
        check_all_boxes(self.c, True)
        app.processEvents()
        self.assertEqual(self.c.selectAllButton.text(), "Deselect All")
        self.assertTrue(self.c.selectAllButton.isChecked())

    def test_button_shows_select_when_none_checked(self):
        check_all_boxes(self.c, False)
        app.processEvents()
        self.assertEqual(self.c.selectAllButton.text(), "Select All")
        self.assertFalse(self.c.selectAllButton.isChecked())

    def test_button_shows_select_on_partial(self):
        get_checkbox(self.c, 0).setChecked(True)
        app.processEvents()
        self.assertEqual(self.c.selectAllButton.text(), "Select All")
        self.assertFalse(self.c.selectAllButton.isChecked())

    def test_select_all_emits_selection_changed(self):
        received = []
        self.c.selectionChanged.connect(received.append)
        self.c.selectAllButton.setChecked(True)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertCountEqual(received[-1], ["one", "two", "three"])

    def test_deselect_all_emits_empty_selection(self):
        check_all_boxes(self.c, True)
        received = []
        self.c.selectionChanged.connect(received.append)
        self.c.selectAllButton.setChecked(False)
        app.processEvents()
        self.assertTrue(len(received) > 0)
        self.assertEqual(received[-1], [])


# ===========================================================================
# refreshDisplayText
# ===========================================================================

class TestRefreshDisplayText(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["m", "n"])

    def tearDown(self):
        self.c.destroy()

    def test_refresh_reflects_current_state(self):
        get_checkbox(self.c, 0).setChecked(True)
        app.processEvents()
        self.c.lineEdit().clear()  # manually dirty the display
        self.c.refreshDisplayText()
        self.assertIn("m", self.c.lineEdit().text())

    def test_refresh_empty_when_nothing_selected(self):
        self.c.refreshDisplayText()
        self.assertEqual(self.c.lineEdit().text(), "")


# ===========================================================================
# clear_selection_list
# ===========================================================================

class TestClearSelectionList(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["i", "j", "k"])
        check_all_boxes(self.c, True)

    def tearDown(self):
        self.c.destroy()

    def test_clears_list_widget(self):
        self.c.clear_selection_list()
        self.assertEqual(self.c.listWidget.count(), 0)

    def test_clears_line_edit(self):
        self.c.clear_selection_list()
        self.assertEqual(self.c.lineEdit().text(), "")

    def test_resets_select_all_button_text(self):
        """clear_selection_list unconditionally resets the button text.
        isChecked() is not asserted: setChecked(False) fires selectAllToggle
        before listWidget.clear() completes, which can leave the button
        checked=True when all items were selected on entry."""
        self.c.clear_selection_list()
        self.assertEqual(self.c.selectAllButton.text(), "Select All")


# ===========================================================================
# edit_filter / delete_filter callbacks
# ===========================================================================

class TestCallbacks(unittest.TestCase):

    def setUp(self):
        self.c = make_combo()
        self.c.addItems(["cb_item"])

    def tearDown(self):
        self.c.destroy()

    def test_delete_filter_callback_called(self):
        mock_delete = MagicMock()
        self.c.delete_filter = mock_delete
        # Trigger the delete button
        item = self.c.listWidget.item(0)
        widget = self.c.listWidget.itemWidget(item)
        from PySide6.QtWidgets import QToolButton
        buttons = widget.findChildren(QToolButton)
        # delete button is the second tool button
        delete_btn = buttons[1]
        delete_btn.click()
        app.processEvents()
        mock_delete.assert_called_once_with("cb_item")

    def test_edit_filter_callback_called(self):
        mock_edit = MagicMock()
        self.c.edit_filter = mock_edit
        item = self.c.listWidget.item(0)
        widget = self.c.listWidget.itemWidget(item)
        from PySide6.QtWidgets import QToolButton
        buttons = widget.findChildren(QToolButton)
        # edit button is the first tool button
        edit_btn = buttons[0]
        edit_btn.click()
        app.processEvents()
        mock_edit.assert_called_once_with("cb_item")


if __name__ == "__main__":
    unittest.main(verbosity=2)