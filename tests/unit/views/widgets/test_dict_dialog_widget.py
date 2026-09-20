"""
Unit tests for DictDialog, the settings dialog every data plugin is configured through.

The widget had no unit test file at all: its only coverage was incidental, through e2e
suites that open it, dismiss it, and reach past it into ``_result``. That is enough to
notice the dialog failing to open and nothing else, so what is pinned here is the
behaviour those suites step over -- which widget each declared ``Type`` produces, what
the OK button waits for, and what ``get_result`` reports for each way the dialog can be
closed.

Runs headlessly; no display required.
"""

import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

# One QApplication for the entire test run, as the sibling widget suites do.
app = QApplication.instance() or QApplication(sys.argv)

from poriscope.views.widgets.dict_dialog_widget import DictDialog  # noqa: E402
from poriscope.views.widgets.validators.numeric_validation import (  # noqa: E402
    NumericLineEdit,
)


def params(**overrides):
    """
    Build a settings dict in the shape ``get_empty_settings`` returns.

    :param overrides: one entry per setting, each already in the Type/Value/... shape
    :type overrides: dict
    :return: the settings dict
    :rtype: dict
    """
    return dict(overrides)


class DictDialogTestCase(unittest.TestCase):
    """Common teardown: dialogs are closed so no widget outlives its test."""

    def setUp(self):
        self._dialogs = []

    def tearDown(self):
        for dlg in self._dialogs:
            dlg.close()
            dlg.deleteLater()
        app.processEvents()

    def build(self, settings, name="plugin_0", **kwargs):
        """
        Construct a dialog and register it for teardown.

        :param settings: the params dict to edit
        :type settings: dict
        :param name: the plugin name prefilled into the name field
        :type name: str
        :param kwargs: passed through to DictDialog
        :type kwargs: dict
        :return: the dialog
        :rtype: DictDialog
        """
        dlg = DictDialog(settings, name, **kwargs)
        self._dialogs.append(dlg)
        return dlg


# ===========================================================================
# Which widget a declared Type produces
# ===========================================================================
class TestWidgetForEachType(DictDialogTestCase):
    """
    The mapping from a setting's declared ``Type`` to the widget the user sees.

    This is the dialog's half of the settings contract: a plugin author writes
    ``get_empty_settings`` and gets these widgets, and nothing else states the mapping.
    """

    def test_str_becomes_a_line_edit_prefilled_with_the_value(self):
        dlg = self.build(params(Label={"Type": str, "Value": "abc", "Units": None}))
        widget = dlg.entrywidgets["Label"]
        self.assertIsInstance(widget, QLineEdit)
        self.assertEqual(widget.text(), "abc")

    def test_bool_becomes_a_checkbox_set_from_the_value(self):
        dlg = self.build(params(Flag={"Type": bool, "Value": True, "Units": None}))
        widget = dlg.entrywidgets["Flag"]
        self.assertIsInstance(widget, QCheckBox)
        self.assertTrue(widget.isChecked())

    def test_int_and_float_become_numeric_line_edits(self):
        dlg = self.build(
            params(
                Count={"Type": int, "Value": 3, "Min": 0, "Max": 10, "Units": None},
                Size={"Type": float, "Value": 1.5, "Min": 0.0, "Units": "pA"},
            )
        )
        self.assertIsInstance(dlg.entrywidgets["Count"], NumericLineEdit)
        self.assertIsInstance(dlg.entrywidgets["Size"], NumericLineEdit)
        self.assertEqual(dlg.entrywidgets["Count"].text(), "3")

    def test_options_become_a_combobox_regardless_of_type(self):
        dlg = self.build(
            params(
                Mode={
                    "Type": str,
                    "Value": "b",
                    "Options": ["a", "b", "c"],
                    "Units": None,
                }
            )
        )
        widget = dlg.entrywidgets["Mode"]
        self.assertIsInstance(widget, QComboBox)
        self.assertEqual(widget.currentText(), "b")
        self.assertEqual([widget.itemText(i) for i in range(widget.count())], ["a", "b", "c"])

    def test_a_bool_with_options_is_still_a_checkbox(self):
        """``Options`` is ignored for bool, which would otherwise render as a dropdown."""
        dlg = self.build(
            params(Flag={"Type": bool, "Value": False, "Options": [True, False]})
        )
        self.assertIsInstance(dlg.entrywidgets["Flag"], QCheckBox)

    def test_an_unsupported_type_is_refused_rather_than_skipped(self):
        """A setting the dialog cannot render must not be silently dropped."""
        with self.assertRaises(ValueError) as caught:
            DictDialog(params(Odd={"Type": list, "Value": []}), "plugin_0")
        self.assertIn("Odd", str(caught.exception))

    def test_units_are_shown_beside_the_field(self):
        dlg = self.build(params(Size={"Type": float, "Value": 1.0, "Units": "pA"}))
        self.assertIsInstance(dlg.unitwidgets["Size"], QLabel)
        self.assertEqual(dlg.unitwidgets["Size"].text(), "pA")

    def test_a_reserved_file_key_becomes_a_picker_button(self):
        """
        The three reserved keys render as a button plus a checkbox, not a text field.

        The checkbox is the dialog's record that a path has been chosen, and it is
        disabled so only the picker can set it.
        """
        for key in ("Input File", "Output File", "Folder"):
            with self.subTest(key=key):
                dlg = self.build({key: {"Type": str, "Value": None}})
                self.assertIsInstance(dlg.entrywidgets[key], QPushButton)
                self.assertIsInstance(dlg.unitwidgets[key], QCheckBox)
                self.assertFalse(dlg.unitwidgets[key].isChecked())
                self.assertFalse(dlg.unitwidgets[key].isEnabled())

    def test_a_reserved_key_that_already_has_a_path_starts_satisfied(self):
        """Editing an existing plugin must not force the user back through the picker."""
        dlg = self.build({"Input File": {"Type": str, "Value": "C:/data/run.log"}})
        self.assertTrue(dlg.unitwidgets["Input File"].isChecked())


# ===========================================================================
# What OK waits for
# ===========================================================================
class TestOkButtonEnablement(DictDialogTestCase):
    """
    ``check_validity`` is the only thing standing between a bad settings dict and a
    plugin instantiated from it, and every condition it applies is asserted here.
    """

    def test_ok_is_disabled_until_the_name_is_filled_in(self):
        dlg = self.build(params(Label={"Type": str, "Value": "x"}), name="")
        dlg.check_validity()
        self.assertFalse(dlg.ok_button.isEnabled())

        dlg.name_entry.setText("plugin_0")
        dlg.check_validity()
        self.assertTrue(dlg.ok_button.isEnabled())

    def test_ok_is_disabled_while_a_numeric_field_is_out_of_range(self):
        dlg = self.build(
            params(Count={"Type": int, "Value": 5, "Min": 0, "Max": 10, "Units": None})
        )
        dlg.entrywidgets["Count"].setText("500")
        dlg.check_validity()
        self.assertFalse(dlg.ok_button.isEnabled())

        dlg.entrywidgets["Count"].setText("5")
        dlg.check_validity()
        self.assertTrue(dlg.ok_button.isEnabled())

    def test_ok_waits_for_every_reserved_file_key(self):
        """With two pickers unsatisfied, satisfying one is not enough."""
        dlg = self.build(
            {
                "Input File": {"Type": str, "Value": None},
                "Output File": {"Type": str, "Value": None},
            }
        )
        dlg.check_validity()
        self.assertFalse(dlg.ok_button.isEnabled())

        dlg.unitwidgets["Input File"].setChecked(True)
        dlg.check_validity()
        self.assertFalse(dlg.ok_button.isEnabled())

        dlg.unitwidgets["Output File"].setChecked(True)
        dlg.check_validity()
        self.assertTrue(dlg.ok_button.isEnabled())


# ===========================================================================
# What get_result reports, for each way out of the dialog
# ===========================================================================
class TestResult(DictDialogTestCase):
    """
    ``get_result`` has one shape - ``(params, name)`` on OK and ``(None, None)``
    otherwise - and ``delete_requested`` carries the delete case separately rather
    than encoding it as a third return value.
    """

    def test_ok_returns_the_edited_params_and_the_name(self):
        dlg = self.build(
            params(
                Label={"Type": str, "Value": "before", "Units": None},
                Count={"Type": int, "Value": 1, "Min": 0, "Max": 9, "Units": None},
                Flag={"Type": bool, "Value": False, "Units": None},
            ),
            name="plugin_0",
        )
        dlg.entrywidgets["Label"].setText("after")
        dlg.entrywidgets["Count"].setText("7")
        dlg.entrywidgets["Flag"].setChecked(True)
        dlg.name_entry.setText("renamed")

        dlg.on_ok()

        result, name = dlg.get_result()
        self.assertEqual(name, "renamed")
        self.assertEqual(result["Label"]["Value"], "after")
        self.assertEqual(result["Count"]["Value"], 7)
        self.assertIs(result["Count"]["Value"].__class__, int)
        self.assertTrue(result["Flag"]["Value"])

    def test_a_combobox_choice_is_cast_to_the_declared_type(self):
        """Options render as strings, so the declared Type is what converts them back."""
        dlg = self.build(
            params(Count={"Type": int, "Value": 2, "Options": [2, 4, 8], "Units": None})
        )
        dlg.entrywidgets["Count"].setCurrentText("8")
        dlg.on_ok()
        result, _ = dlg.get_result()
        self.assertEqual(result["Count"]["Value"], 8)
        self.assertIs(result["Count"]["Value"].__class__, int)

    def test_cancel_reports_nothing(self):
        dlg = self.build(params(Label={"Type": str, "Value": "x", "Units": None}))
        dlg.entrywidgets["Label"].setText("edited")
        dlg.on_cancel()
        self.assertEqual(dlg.get_result(), (None, None))

    def test_an_untouched_dialog_reports_nothing(self):
        """
        Esc and the window close button run no handler at all.

        The initial value of ``_result`` is what answers for them, which is why it is
        set in ``__init__`` rather than only by the button slots.
        """
        dlg = self.build(params(Label={"Type": str, "Value": "x", "Units": None}))
        self.assertEqual(dlg.get_result(), (None, None))
        self.assertFalse(dlg.delete_requested())

    def test_delete_is_reported_separately_from_the_result(self):
        dlg = self.build(
            params(Label={"Type": str, "Value": "x", "Units": None}), show_delete=True
        )
        dlg.on_delete()
        self.assertTrue(dlg.delete_requested())
        self.assertEqual(dlg.get_result(), (None, None))

    def test_no_delete_button_unless_it_was_asked_for(self):
        dlg = self.build(params(Label={"Type": str, "Value": "x", "Units": None}))
        self.assertFalse(hasattr(dlg, "delete_button"))


# ===========================================================================
# The file pickers
# ===========================================================================
class TestFilePickers(DictDialogTestCase):
    """
    The pickers are patched at their source, never opened.

    Each one writes straight into ``params`` rather than into a widget, which is why
    ``on_ok`` skips the three reserved keys when it harvests the entry widgets.
    """

    def test_choosing_an_input_file_records_it_and_satisfies_the_gate(self):
        dlg = self.build({"Input File": {"Type": str, "Value": None}})
        with patch(
            "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
            return_value=("C:/data/run.log", ""),
        ):
            dlg.get_input_file(starting_file_path="C:/data/old.log")

        self.assertEqual(dlg.params["Input File"]["Value"], "C:/data/run.log")
        self.assertTrue(dlg.unitwidgets["Input File"].isChecked())
        self.assertTrue(dlg.ok_button.isEnabled())

    def test_cancelling_the_picker_changes_nothing(self):
        dlg = self.build({"Input File": {"Type": str, "Value": None}})
        with patch(
            "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ):
            dlg.get_input_file()

        self.assertIsNone(dlg.params["Input File"]["Value"])
        self.assertFalse(dlg.unitwidgets["Input File"].isChecked())
        self.assertFalse(dlg.ok_button.isEnabled())

    def test_choosing_a_folder_records_it(self):
        dlg = self.build({"Folder": {"Type": str, "Value": None}})
        with patch(
            "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getExistingDirectory",
            return_value="C:/data/out",
        ):
            dlg.get_folder()

        self.assertEqual(dlg.params["Folder"]["Value"], "C:/data/out")
        self.assertTrue(dlg.unitwidgets["Folder"].isChecked())

    def test_a_chosen_path_survives_ok_untouched(self):
        """
        ``on_ok`` must not try to read a path off the picker button.

        The button's text is "Select Input File"; harvesting it the way the other
        widgets are harvested would overwrite the real path with that label.
        """
        dlg = self.build(
            {
                "Input File": {"Type": str, "Value": None},
                "Label": {"Type": str, "Value": "x", "Units": None},
            }
        )
        with patch(
            "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
            return_value=("C:/data/run.log", ""),
        ):
            dlg.get_input_file()

        dlg.on_ok()
        result, _ = dlg.get_result()
        self.assertEqual(result["Input File"]["Value"], "C:/data/run.log")


# ===========================================================================
# Construction options
# ===========================================================================
class TestConstructionOptions(DictDialogTestCase):
    """The flags the plugin controller passes when it opens the dialog."""

    def test_the_title_reaches_the_window(self):
        dlg = self.build(
            params(Label={"Type": str, "Value": "x", "Units": None}),
            title="Edit SQLiteDBLoader_0",
        )
        self.assertEqual(dlg.windowTitle(), "Edit SQLiteDBLoader_0")

    def test_a_non_editable_dialog_locks_the_name(self):
        dlg = self.build(
            params(Label={"Type": str, "Value": "x", "Units": None}), editable=False
        )
        self.assertFalse(dlg.name_entry.isEnabled())

    def test_a_source_plugin_choice_can_be_frozen(self):
        """
        Re-pointing a plugin at a different parent is refused while it holds state.

        The combobox still shows the current choice; it just cannot be changed.
        """
        settings = params(
            MetaReader={
                "Type": str,
                "Value": "reader_0",
                "Options": ["reader_0", "reader_1"],
                "Units": None,
            }
        )
        dlg = self.build(
            settings,
            source_plugins=["MetaReader"],
            editable_source_plugins=False,
        )
        self.assertFalse(dlg.entrywidgets["MetaReader"].isEnabled())
        self.assertEqual(dlg.entrywidgets["MetaReader"].currentText(), "reader_0")

    def test_a_source_plugin_choice_is_editable_by_default(self):
        settings = params(
            MetaReader={
                "Type": str,
                "Value": "reader_0",
                "Options": ["reader_0", "reader_1"],
                "Units": None,
            }
        )
        dlg = self.build(settings, source_plugins=["MetaReader"])
        self.assertTrue(dlg.entrywidgets["MetaReader"].isEnabled())


if __name__ == "__main__":
    unittest.main()
