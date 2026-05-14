"""
Unit tests for SelectionTree.
Runs headlessly — no display required.
"""

import sys
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from poriscope.views.widgets.SelectionTree import SelectionTree  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STRUCTURE = {
    "Experiment A": ["ch0", "ch1", "ch2"],
    "Experiment B": ["ch3", "ch4"],
}


def make_widget() -> SelectionTree:
    w = SelectionTree()
    return w


def top_item(w: SelectionTree, row: int):
    return w.tree.topLevelItem(row)


def child_item(w: SelectionTree, parent_row: int, child_row: int):
    return w.tree.topLevelItem(parent_row).child(child_row)


# ===========================================================================
# populate_tree
# ===========================================================================


class TestPopulateTree(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()

    def tearDown(self):
        self.w.destroy()

    def test_correct_number_of_top_level_items(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertEqual(self.w.tree.topLevelItemCount(), 2)

    def test_correct_number_of_children(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertEqual(top_item(self.w, 0).childCount(), 3)
        self.assertEqual(top_item(self.w, 1).childCount(), 2)

    def test_parent_names(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertEqual(top_item(self.w, 0).text(0), "Experiment A")
        self.assertEqual(top_item(self.w, 1).text(0), "Experiment B")

    def test_child_names(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertEqual(child_item(self.w, 0, 0).text(0), "ch0")
        self.assertEqual(child_item(self.w, 0, 2).text(0), "ch2")

    def test_all_checked_by_default(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        for i in range(self.w.tree.topLevelItemCount()):
            parent = top_item(self.w, i)
            self.assertEqual(parent.checkState(0), Qt.Checked)
            for j in range(parent.childCount()):
                self.assertEqual(parent.child(j).checkState(0), Qt.Checked)

    def test_respects_provided_selection(self):
        selected = {"Experiment A": ["ch0", "ch2"]}
        self.w.populate_tree(STRUCTURE, "loader1", selected=selected)
        self.assertEqual(child_item(self.w, 0, 0).checkState(0), Qt.Checked)
        self.assertEqual(child_item(self.w, 0, 1).checkState(0), Qt.Unchecked)
        self.assertEqual(child_item(self.w, 0, 2).checkState(0), Qt.Checked)

    def test_partial_selection_gives_partial_parent(self):
        selected = {"Experiment A": ["ch0"]}
        self.w.populate_tree(STRUCTURE, "loader1", selected=selected)
        self.assertEqual(top_item(self.w, 0).checkState(0), Qt.PartiallyChecked)

    def test_no_selection_gives_unchecked_parent(self):
        selected = {}
        self.w.populate_tree(STRUCTURE, "loader1", selected=selected)
        self.assertEqual(top_item(self.w, 0).checkState(0), Qt.Unchecked)
        self.assertEqual(top_item(self.w, 1).checkState(0), Qt.Unchecked)

    def test_clear_replaces_previous_tree(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.w.populate_tree({"Only": ["x"]}, "loader2")
        self.assertEqual(self.w.tree.topLevelItemCount(), 1)

    def test_caches_full_selection_on_first_load(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertIn("loader1", self.w.selection_by_loader)
        cached = self.w.selection_by_loader["loader1"]
        self.assertEqual(set(cached["Experiment A"]), {"ch0", "ch1", "ch2"})

    def test_uses_cached_selection_on_reload(self):
        self.w.selection_by_loader["loader1"] = {"Experiment A": ["ch1"]}
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertEqual(child_item(self.w, 0, 0).checkState(0), Qt.Unchecked)
        self.assertEqual(child_item(self.w, 0, 1).checkState(0), Qt.Checked)

    def test_items_are_expanded(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.assertTrue(top_item(self.w, 0).isExpanded())
        self.assertTrue(top_item(self.w, 1).isExpanded())


# ===========================================================================
# on_item_changed — checking/unchecking items
# ===========================================================================


class TestOnItemChanged(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()
        self.w.populate_tree(STRUCTURE, "loader1")

    def tearDown(self):
        self.w.destroy()

    def test_unchecking_parent_unchecks_all_children(self):
        top_item(self.w, 0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        for j in range(top_item(self.w, 0).childCount()):
            self.assertEqual(child_item(self.w, 0, j).checkState(0), Qt.Unchecked)

    def test_checking_parent_checks_all_children(self):
        top_item(self.w, 0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        top_item(self.w, 0).setCheckState(0, Qt.Checked)
        app.processEvents()
        for j in range(top_item(self.w, 0).childCount()):
            self.assertEqual(child_item(self.w, 0, j).checkState(0), Qt.Checked)

    def test_unchecking_one_child_makes_parent_partial(self):
        child_item(self.w, 0, 0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        self.assertEqual(top_item(self.w, 0).checkState(0), Qt.PartiallyChecked)

    def test_unchecking_all_children_makes_parent_unchecked(self):
        for j in range(top_item(self.w, 0).childCount()):
            child_item(self.w, 0, j).setCheckState(0, Qt.Unchecked)
            app.processEvents()
        self.assertEqual(top_item(self.w, 0).checkState(0), Qt.Unchecked)

    def test_checking_all_children_makes_parent_checked(self):
        top_item(self.w, 0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        for j in range(top_item(self.w, 0).childCount()):
            child_item(self.w, 0, j).setCheckState(0, Qt.Checked)
            app.processEvents()
        self.assertEqual(top_item(self.w, 0).checkState(0), Qt.Checked)


# ===========================================================================
# Select All / Deselect All button
# ===========================================================================


class TestSelectAllButton(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()
        self.w.populate_tree(STRUCTURE, "loader1")

    def tearDown(self):
        self.w.destroy()

    def test_all_checked_button_shows_deselect(self):
        app.processEvents()
        self.assertEqual(self.w.select_all_button.text(), "Deselect All")
        self.assertTrue(self.w.select_all_button.isChecked())

    def test_deselect_all_unchecks_everything(self):
        self.w.select_all_button.setChecked(False)
        app.processEvents()
        for i in range(self.w.tree.topLevelItemCount()):
            for j in range(top_item(self.w, i).childCount()):
                self.assertEqual(child_item(self.w, i, j).checkState(0), Qt.Unchecked)

    def test_select_all_checks_everything(self):
        self.w.select_all_button.setChecked(False)
        app.processEvents()
        self.w.select_all_button.setChecked(True)
        app.processEvents()
        for i in range(self.w.tree.topLevelItemCount()):
            for j in range(top_item(self.w, i).childCount()):
                self.assertEqual(child_item(self.w, i, j).checkState(0), Qt.Checked)

    def test_partial_selection_shows_select_all(self):
        child_item(self.w, 0, 0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        self.assertEqual(self.w.select_all_button.text(), "Select All")
        self.assertFalse(self.w.select_all_button.isChecked())

    def test_all_unchecked_shows_select_all(self):
        self.w.select_all_button.setChecked(False)
        app.processEvents()
        self.assertEqual(self.w.select_all_button.text(), "Select All")
        self.assertFalse(self.w.select_all_button.isChecked())

    def test_empty_tree_shows_select_all_unchecked(self):
        self.w.populate_tree({}, "empty_loader")
        app.processEvents()
        self.assertEqual(self.w.select_all_button.text(), "Select All")
        self.assertFalse(self.w.select_all_button.isChecked())


# ===========================================================================
# get_selected
# ===========================================================================


class TestGetSelected(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()

    def tearDown(self):
        self.w.destroy()

    def test_all_checked_returns_full_structure(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        result = self.w.get_selected()
        self.assertEqual(set(result["Experiment A"]), {"ch0", "ch1", "ch2"})
        self.assertEqual(set(result["Experiment B"]), {"ch3", "ch4"})

    def test_none_checked_returns_empty_dict(self):
        self.w.populate_tree(STRUCTURE, "loader1", selected={})
        result = self.w.get_selected()
        self.assertEqual(result, {})

    def test_partial_selection_returns_only_checked(self):
        selected = {"Experiment A": ["ch1"]}
        self.w.populate_tree(STRUCTURE, "loader1", selected=selected)
        result = self.w.get_selected()
        self.assertEqual(result.get("Experiment A"), ["ch1"])
        self.assertNotIn("Experiment B", result)

    def test_parent_absent_when_no_children_selected(self):
        selected = {"Experiment B": ["ch3", "ch4"]}
        self.w.populate_tree(STRUCTURE, "loader1", selected=selected)
        result = self.w.get_selected()
        self.assertNotIn("Experiment A", result)
        self.assertIn("Experiment B", result)

    def test_empty_tree_returns_empty(self):
        self.w.populate_tree({}, "loader1")
        self.assertEqual(self.w.get_selected(), {})


# ===========================================================================
# selection_by_loader caching across loaders
# ===========================================================================


class TestSelectionCache(unittest.TestCase):

    def setUp(self):
        self.w = make_widget()

    def tearDown(self):
        self.w.destroy()

    def test_two_loaders_cached_independently(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        self.w.populate_tree({"X": ["a", "b"]}, "loader2")
        self.assertIn("loader1", self.w.selection_by_loader)
        self.assertIn("loader2", self.w.selection_by_loader)

    def test_switching_loader_restores_previous_cache(self):
        self.w.populate_tree(STRUCTURE, "loader1")
        # Manually dirty the cache for loader1
        self.w.selection_by_loader["loader1"] = {"Experiment A": ["ch2"]}
        # Load a different loader then come back
        self.w.populate_tree({"X": ["a"]}, "loader2")
        self.w.populate_tree(STRUCTURE, "loader1")
        # Should restore from cache
        self.assertEqual(child_item(self.w, 0, 0).checkState(0), Qt.Unchecked)  # ch0
        self.assertEqual(child_item(self.w, 0, 2).checkState(0), Qt.Checked)  # ch2


if __name__ == "__main__":
    unittest.main(verbosity=2)
