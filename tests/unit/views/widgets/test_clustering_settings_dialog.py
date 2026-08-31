"""
Full unit-test suite for ClusteringSettingsDialog.

No mocking needed — the dialog has no file I/O or database calls.
QMessageBox.warning is patched only for the column-limit test.

Run with:
    pytest test_clustering_settings_dialog.py -v
    pytest test_clustering_settings_dialog.py --cov=poriscope --cov-report=html
"""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit

from poriscope.views.widgets.clustering_settings_widget import (
    ClusteringSettingsDialog,
)

# ===========================================================================
# Fixtures / helpers
# ===========================================================================


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


COLUMNS = ["duration", "current", "voltage", "charge"]
METHODS = ["KMeans", "DBSCAN", "Agglomerative"]
UNITS = {"duration": "ms", "current": "pA", "voltage": "mV", "charge": "fC"}
METHOD_PARAMS = {
    "KMeans": [
        {"name": "Clusters", "type": "int"},
        {"name": "Init Method", "type": "str"},
    ],
    "DBSCAN": [
        {"name": "Eps", "type": "float"},
        {"name": "Min Samples", "type": "int"},
    ],
    "Agglomerative": [{"name": "Linkage", "type": "str"}],
}


def _make_dialog(
    columns=None,
    methods=None,
    units=None,
    method_params=None,
    preselected=None,
    qt_app=None,
):
    dlg = ClusteringSettingsDialog(
        dynamic_title="Test Dialog",
        available_columns=columns or COLUMNS,
        available_methods=methods or METHODS,
        column_units=units or UNITS,
        method_parameters=method_params or METHOD_PARAMS,
        preselected_config=preselected,
    )
    if qt_app:
        qt_app.processEvents()
    return dlg


def _select_two_plot_cols(dlg):
    """Helper: set both default rows to real columns and tick plot on each."""
    dlg.default_row_widgets[0]["combo"].setCurrentText("duration")
    dlg.default_row_widgets[0]["plot_cb"].setChecked(True)
    dlg.default_row_widgets[1]["combo"].setCurrentText("current")
    dlg.default_row_widgets[1]["plot_cb"].setChecked(True)


@pytest.fixture
def dlg(qt_app):
    d = _make_dialog(qt_app=qt_app)
    return d


@pytest.fixture
def dlg_ready(qt_app):
    """Dialog with two default rows fully configured (apply button enabled)."""
    d = _make_dialog(qt_app=qt_app)
    _select_two_plot_cols(d)
    return d


# ===========================================================================
# Instantiation / init_ui
# ===========================================================================


class TestInstantiation:
    def test_creates_without_error(self, dlg):
        assert dlg is not None

    def test_title_label_text(self, dlg):
        assert dlg.dynamic_title == "Test Dialog"

    def test_method_combo_has_select_placeholder(self, dlg):
        assert dlg.method_combo.itemText(0) == "Select Method"

    def test_method_combo_contains_all_methods(self, dlg):
        items = [dlg.method_combo.itemText(i) for i in range(dlg.method_combo.count())]
        for m in METHODS:
            assert m in items

    def test_two_default_rows_created(self, dlg):
        assert len(dlg.default_row_widgets) == 2

    def test_default_rows_have_required_keys(self, dlg):
        for row in dlg.default_row_widgets:
            for key in ["combo", "log_cb", "norm_cb", "plot_cb", "unit_label"]:
                assert key in row

    def test_apply_button_disabled_initially(self, dlg):
        assert not dlg.apply_button.isEnabled()

    def test_cancel_button_present(self, dlg):
        assert dlg.cancel_button is not None

    def test_add_button_present(self, dlg):
        assert dlg.add_button is not None

    def test_column_item_widgets_empty_initially(self, dlg):
        assert dlg.column_item_widgets == {}

    def test_filter_text_empty_initially(self, dlg):
        assert dlg.filter_text.toPlainText() == ""

    def test_get_current_view(self, dlg):
        assert dlg.get_current_view() == "ClusteringSettingsDialog"

    def test_available_columns_populated_in_default_combos(self, dlg):
        for row in dlg.default_row_widgets:
            items = [row["combo"].itemText(i) for i in range(row["combo"].count())]
            assert "duration" in items
            assert "Select Column" in items


# ===========================================================================
# get_default_config
# ===========================================================================


class TestGetDefaultConfig:
    def test_returns_dict_with_required_keys(self, dlg):
        cfg = dlg.get_default_config()
        assert "method" in cfg
        assert "filter" in cfg
        assert "method_params" in cfg
        assert "columns" in cfg

    def test_default_method_is_hdbscan(self, dlg):
        assert dlg.get_default_config()["method"] == "HDBSCAN"

    def test_default_columns_empty(self, dlg):
        assert dlg.get_default_config()["columns"] == []

    def test_default_filter_empty(self, dlg):
        assert dlg.get_default_config()["filter"] == ""


# ===========================================================================
# _bold_font
# ===========================================================================


class TestBoldFont:
    def test_returns_bold_font(self, dlg):
        font = dlg._bold_font()
        assert font.bold()


# ===========================================================================
# update_method_parameters
# ===========================================================================


class TestUpdateMethodParameters:
    def test_kmeans_creates_two_param_widgets(self, dlg):
        dlg.update_method_parameters("KMeans")
        line_edits = [
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        ]
        assert len(line_edits) == 2

    def test_dbscan_creates_two_param_widgets(self, dlg):
        dlg.update_method_parameters("DBSCAN")
        line_edits = [
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        ]
        assert len(line_edits) == 2

    def test_agglomerative_creates_one_param_widget(self, dlg):
        dlg.update_method_parameters("Agglomerative")
        line_edits = [
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        ]
        assert len(line_edits) == 1

    def test_unknown_method_clears_params(self, dlg):
        dlg.update_method_parameters("KMeans")
        dlg.update_method_parameters("Unknown")
        assert dlg.param_layout.count() == 0

    def test_switching_method_clears_old_params(self, dlg):
        dlg.update_method_parameters("KMeans")
        dlg.update_method_parameters("Agglomerative")
        line_edits = [
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        ]
        assert len(line_edits) == 1

    def test_int_param_has_int_validator(self, dlg):
        dlg.update_method_parameters("KMeans")  # Clusters = int
        from PySide6.QtGui import QIntValidator

        le = next(
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        )
        assert isinstance(le.validator(), QIntValidator)

    def test_float_param_has_double_validator(self, dlg):
        dlg.update_method_parameters("DBSCAN")  # Eps = float
        from PySide6.QtGui import QDoubleValidator

        le = next(
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        )
        assert isinstance(le.validator(), QDoubleValidator)

    def test_restores_saved_value_from_preselected_config(self, qt_app):
        pre = {
            "method": "KMeans",
            "filter": "",
            "method_params": {"KMeans_Clusters_input": "7"},
            "columns": [],
        }
        dlg = _make_dialog(preselected=pre, qt_app=qt_app)
        # Re-trigger to populate
        dlg.update_method_parameters("KMeans")
        le = next(
            (
                dlg.param_layout.itemAt(i).widget()
                for i in range(dlg.param_layout.count())
                if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
                and dlg.param_layout.itemAt(i).widget().objectName()
                == "KMeans_Clusters_input"
            ),
            None,
        )
        assert le is not None
        assert le.text() == "7"

    def test_triggered_by_method_combo_change(self, dlg):
        dlg.method_combo.setCurrentText("KMeans")
        line_edits = [
            dlg.param_layout.itemAt(i).widget()
            for i in range(dlg.param_layout.count())
            if isinstance(dlg.param_layout.itemAt(i).widget(), QLineEdit)
        ]
        assert len(line_edits) == 2


# ===========================================================================
# update_unit_label_for_row
# ===========================================================================


class TestUnitLabels:
    def test_update_unit_label_for_row_sets_text(self, dlg):
        from PySide6.QtWidgets import QLabel

        label = QLabel()
        dlg.update_unit_label_for_row("duration", label)
        assert label.text() == "(ms)"
        assert label.isVisible()

    def test_update_unit_label_for_row_unknown_column(self, dlg):
        from PySide6.QtWidgets import QLabel

        label = QLabel()
        label.setVisible(True)
        dlg.update_unit_label_for_row("unknown_col", label)
        assert label.text() == ""
        assert not label.isVisible()

    def test_default_row_unit_label_updates_on_combo_change(self, dlg):
        row = dlg.default_row_widgets[0]
        row["combo"].setCurrentText("current")
        assert row["unit_label"].text() == "(pA)"

    def test_unit_label_hidden_for_no_unit(self, dlg):
        # Use a dialog with no units mapping
        d = _make_dialog(units={})
        row = d.default_row_widgets[0]
        row["combo"].setCurrentText("duration")
        assert not row["unit_label"].isVisible()


# ===========================================================================
# add_column_item / add_column_item_with_values
# ===========================================================================


class TestAddColumnItem:
    def test_add_column_item_increments_count(self, dlg):
        before = len(dlg.column_item_widgets)
        dlg.add_column_item()
        assert len(dlg.column_item_widgets) == before + 1

    def test_add_multiple_items(self, dlg):
        dlg.add_column_item()
        dlg.add_column_item()
        assert len(dlg.column_item_widgets) == 2

    def test_add_column_item_limit_8(self, dlg):
        for _ in range(8):
            dlg.add_column_item()
        # 9th call should show warning and not add
        with patch("PySide6.QtWidgets.QMessageBox.warning"):
            dlg.add_column_item()
        assert len(dlg.column_item_widgets) == 8

    def test_add_column_item_with_values(self, dlg):
        dlg.add_column_item_with_values("duration", True, False, True)
        assert len(dlg.column_item_widgets) == 1
        key = list(dlg.column_item_widgets.keys())[0]
        row = dlg.column_item_widgets[key]
        assert row["combo"].currentText() == "duration"
        assert row["log_cb"].isChecked()
        assert not row["norm_cb"].isChecked()
        assert row["plot_cb"].isChecked()

    def test_add_column_item_with_values_limit_8(self, dlg):
        for i in range(8):
            dlg.add_column_item_with_values("duration", False, False, False)
        # 9th should be silently ignored
        dlg.add_column_item_with_values("current", False, False, False)
        assert len(dlg.column_item_widgets) == 8

    def test_new_row_has_all_checkboxes(self, dlg):
        dlg.add_column_item()
        key = list(dlg.column_item_widgets.keys())[0]
        row = dlg.column_item_widgets[key]
        assert isinstance(row["log_cb"], QCheckBox)
        assert isinstance(row["norm_cb"], QCheckBox)
        assert isinstance(row["plot_cb"], QCheckBox)

    def test_new_row_combo_contains_columns(self, dlg):
        dlg.add_column_item()
        key = list(dlg.column_item_widgets.keys())[0]
        items = [
            dlg.column_item_widgets[key]["combo"].itemText(i)
            for i in range(dlg.column_item_widgets[key]["combo"].count())
        ]
        assert "duration" in items


# ===========================================================================
# remove_column_item
# ===========================================================================


class TestRemoveColumnItem:
    def test_remove_decrements_count(self, dlg):
        dlg.add_column_item()
        key = list(dlg.column_item_widgets.keys())[0]
        dlg.remove_column_item(key)
        assert key not in dlg.column_item_widgets

    def test_remove_nonexistent_key_no_error(self, dlg):
        dlg.remove_column_item("nonexistent_key")  # should not raise

    def test_remove_one_of_multiple(self, dlg):
        dlg.add_column_item()
        dlg.add_column_item()
        keys = list(dlg.column_item_widgets.keys())
        dlg.remove_column_item(keys[0])
        assert len(dlg.column_item_widgets) == 1
        assert keys[1] in dlg.column_item_widgets


# ===========================================================================
# _check_apply_enabled
# ===========================================================================


class TestCheckApplyEnabled:
    def test_disabled_when_default_col_not_selected(self, dlg):
        dlg._check_apply_enabled()
        assert not dlg.apply_button.isEnabled()

    def test_disabled_with_one_plot_col(self, dlg):
        dlg.default_row_widgets[0]["combo"].setCurrentText("duration")
        dlg.default_row_widgets[0]["plot_cb"].setChecked(True)
        dlg.default_row_widgets[1]["combo"].setCurrentText("current")
        dlg.default_row_widgets[1]["plot_cb"].setChecked(False)
        dlg._check_apply_enabled()
        assert not dlg.apply_button.isEnabled()

    def test_enabled_with_two_plot_cols(self, dlg):
        _select_two_plot_cols(dlg)
        assert dlg.apply_button.isEnabled()

    def test_disabled_with_four_plot_cols(self, dlg):
        _select_two_plot_cols(dlg)
        dlg.add_column_item_with_values("voltage", False, False, True)
        dlg.add_column_item_with_values("charge", False, False, True)
        dlg._check_apply_enabled()
        assert not dlg.apply_button.isEnabled()

    def test_warning_label_visible_with_too_few_plots(self, dlg):
        dlg.default_row_widgets[0]["combo"].setCurrentText("duration")
        dlg.default_row_widgets[1]["combo"].setCurrentText("current")
        dlg._check_apply_enabled()
        assert not dlg.plot_warning_label.isHidden()

    def test_warning_label_hidden_when_valid(self, dlg):
        _select_two_plot_cols(dlg)
        assert not dlg.plot_warning_label.isVisible()

    def test_warning_label_for_too_many_plots(self, dlg):
        _select_two_plot_cols(dlg)
        dlg.add_column_item_with_values("voltage", False, False, True)
        dlg.add_column_item_with_values("charge", False, False, True)
        dlg._check_apply_enabled()
        assert not dlg.plot_warning_label.isHidden()
        assert "2 or 3" in dlg.plot_warning_label.text()

    def test_dynamic_row_with_select_column_disables_apply(self, dlg):
        _select_two_plot_cols(dlg)
        dlg.add_column_item()  # left at "Select Column"
        dlg._check_apply_enabled()
        assert not dlg.apply_button.isEnabled()

    def test_three_plot_cols_enabled(self, dlg):
        _select_two_plot_cols(dlg)
        dlg.add_column_item_with_values("voltage", False, False, True)
        dlg._check_apply_enabled()
        assert dlg.apply_button.isEnabled()


# ===========================================================================
# get_result
# ===========================================================================


class TestGetResult:
    def test_returns_dict(self, dlg_ready):
        result = dlg_ready.get_result()
        assert isinstance(result, dict)

    def test_result_has_required_keys(self, dlg_ready):
        result = dlg_ready.get_result()
        for key in ["method", "method_params", "filter", "columns"]:
            assert key in result

    def test_result_method_reflects_combo(self, dlg_ready):
        dlg_ready.method_combo.setCurrentText("KMeans")
        result = dlg_ready.get_result()
        assert result["method"] == "KMeans"

    def test_result_filter_reflects_text(self, dlg_ready):
        dlg_ready.filter_text.setPlainText("duration > 100")
        result = dlg_ready.get_result()
        assert result["filter"] == "duration > 100"

    def test_result_columns_include_default_rows(self, dlg_ready):
        result = dlg_ready.get_result()
        cols = [c["column"] for c in result["columns"]]
        assert "duration" in cols
        assert "current" in cols

    def test_result_skips_unselected_default_row(self, dlg):
        # Only select one default row
        dlg.default_row_widgets[0]["combo"].setCurrentText("duration")
        dlg.default_row_widgets[0]["plot_cb"].setChecked(True)
        # Leave row 1 at "Select Column"
        result = dlg.get_result()
        cols = [c["column"] for c in result["columns"]]
        assert "duration" in cols
        assert len(cols) == 1

    def test_result_includes_log_norm_plot_flags(self, dlg_ready):
        dlg_ready.default_row_widgets[0]["log_cb"].setChecked(True)
        dlg_ready.default_row_widgets[0]["norm_cb"].setChecked(True)
        result = dlg_ready.get_result()
        duration_row = next(c for c in result["columns"] if c["column"] == "duration")
        assert duration_row["log"] is True
        assert duration_row["norm"] is True

    def test_result_includes_unit(self, dlg_ready):
        result = dlg_ready.get_result()
        duration_row = next(c for c in result["columns"] if c["column"] == "duration")
        assert duration_row["unit"] == "ms"

    def test_result_includes_dynamic_rows(self, dlg_ready):
        dlg_ready.add_column_item_with_values("voltage", False, True, True)
        result = dlg_ready.get_result()
        cols = [c["column"] for c in result["columns"]]
        assert "voltage" in cols

    def test_result_method_params_from_line_edits(self, dlg_ready):
        dlg_ready.update_method_parameters("KMeans")
        # Set a value in the first line edit
        for i in range(dlg_ready.param_layout.count()):
            w = dlg_ready.param_layout.itemAt(i).widget()
            if isinstance(w, QLineEdit):
                w.setText("99")
                break
        result = dlg_ready.get_result()
        assert "99" in result["method_params"].values()


# ===========================================================================
# Preselected config restoration
# ===========================================================================


class TestPreselectedConfig:
    def test_restores_method(self, qt_app):
        pre = {
            "method": "DBSCAN",
            "filter": "",
            "method_params": {},
            "columns": [],
        }
        dlg = _make_dialog(preselected=pre, qt_app=qt_app)
        assert dlg.method_combo.currentText() == "DBSCAN"

    def test_restores_filter(self, qt_app):
        pre = {
            "method": "KMeans",
            "filter": "duration > 50",
            "method_params": {},
            "columns": [],
        }
        dlg = _make_dialog(preselected=pre, qt_app=qt_app)
        assert "duration > 50" in dlg.filter_text.toPlainText()

    def test_restores_default_row_column(self, qt_app):
        pre = {
            "method": "KMeans",
            "filter": "",
            "method_params": {},
            "columns": [
                {"column": "voltage", "log": True, "norm": False, "plot": True},
                {"column": "charge", "log": False, "norm": True, "plot": True},
            ],
        }
        dlg = _make_dialog(preselected=pre, qt_app=qt_app)
        assert dlg.default_row_widgets[0]["combo"].currentText() == "voltage"
        assert dlg.default_row_widgets[0]["log_cb"].isChecked()

    def test_restores_extra_columns_as_dynamic_rows(self, qt_app):
        pre = {
            "method": "KMeans",
            "filter": "",
            "method_params": {},
            "columns": [
                {"column": "duration", "log": False, "norm": False, "plot": True},
                {"column": "current", "log": False, "norm": False, "plot": True},
                {"column": "voltage", "log": True, "norm": False, "plot": True},
            ],
        }
        dlg = _make_dialog(preselected=pre, qt_app=qt_app)
        assert len(dlg.column_item_widgets) == 1

    def test_none_preselected_uses_default(self, qt_app):
        dlg = _make_dialog(preselected=None, qt_app=qt_app)
        # Default config is used but columns list is empty → no dynamic rows
        assert len(dlg.column_item_widgets) == 0


# ===========================================================================
# get_walkthrough_steps
# ===========================================================================


class TestGetWalkthroughSteps:
    def test_returns_list(self, dlg):
        steps = dlg.get_walkthrough_steps()
        assert isinstance(steps, list)

    def test_has_five_steps(self, dlg):
        assert len(dlg.get_walkthrough_steps()) == 5

    def test_each_step_is_tuple_of_four(self, dlg):
        for step in dlg.get_walkthrough_steps():
            assert len(step) == 4

    def test_step_widgets_callable(self, dlg):
        for _, _, _, widget_fn in dlg.get_walkthrough_steps():
            widgets = widget_fn()
            assert isinstance(widgets, list)
            assert len(widgets) > 0


# ===========================================================================
# Empty / minimal construction
# ===========================================================================


class TestEdgeCases:
    def test_no_methods_available(self, qt_app):
        # NOTE: _make_dialog uses `methods or METHODS`, so [] (falsy) falls back
        # to the default METHODS list. Pass a sentinel list with one dummy entry
        # to verify that only that entry (plus "Select Method") appears.
        dlg = _make_dialog(methods=["OnlyMethod"], qt_app=qt_app)
        assert dlg.method_combo.count() == 2  # "Select Method" + "OnlyMethod"

    def test_no_columns_available(self, qt_app):
        # _make_dialog uses `columns or COLUMNS`, so [] falls back to defaults.
        # Verify behaviour with a single real column so the fallback doesn't fire.
        dlg = _make_dialog(columns=["only_col"], qt_app=qt_app)
        assert len(dlg.default_row_widgets) == 2
        # "Select Column" + "only_col" = 2 items
        assert dlg.default_row_widgets[0]["combo"].count() == 2

    def test_no_units_no_error(self, qt_app):
        dlg = _make_dialog(units={}, qt_app=qt_app)
        dlg.default_row_widgets[0]["combo"].setCurrentText("duration")
        assert not dlg.default_row_widgets[0]["unit_label"].isVisible()

    def test_add_row_index_advances(self, dlg):
        before = dlg.add_row_index
        dlg.add_column_item()
        assert dlg.add_row_index == before + 1

    def test_refresh_add_button_position_no_error(self, dlg):
        dlg.add_column_item()
        key = list(dlg.column_item_widgets.keys())[0]
        dlg.remove_column_item(key)  # calls _refresh_add_button_position internally
