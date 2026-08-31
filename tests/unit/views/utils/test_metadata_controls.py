"""
Full unit-test suite for MetadataControls.

All tests use a real MetadataControls instance — no mocking needed since
the class has no file dialogs, no database calls, and no blocking modals.

Run with:
    pytest test_metadata_controls.py -v
    pytest test_metadata_controls.py --cov=poriscope --cov-report=html
"""

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QToolButton

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mc(qt_app):
    """Fresh MetadataControls for each test."""
    widget = MetadataControls()
    qt_app.processEvents()
    return widget


# ===========================================================================
# Instantiation / setupUi
# ===========================================================================


class TestInstantiation:
    def test_creates_without_error(self, mc):
        assert mc is not None

    def test_has_db_loader_combobox(self, mc):
        assert hasattr(mc, "db_loader_comboBox")
        assert isinstance(mc.db_loader_comboBox, QComboBox)

    def test_has_plot_type_combobox(self, mc):
        assert hasattr(mc, "plot_type_comboBox")
        assert mc.plot_type_comboBox.count() == 15  # 15 plot type options

    def test_plot_type_first_item(self, mc):
        assert mc.plot_type_comboBox.itemText(0) == "Select Plot Type"

    def test_has_axis_comboboxes(self, mc):
        assert hasattr(mc, "x_axis_comboBox")
        assert hasattr(mc, "y_axis_comboBox")
        assert hasattr(mc, "z_axis_comboBox")

    def test_has_filter_combobox(self, mc):
        assert hasattr(mc, "filter_comboBox")

    def test_has_bins_lineedit(self, mc):
        assert hasattr(mc, "bins_lineEdit")

    def test_has_sizes_checkbox(self, mc):
        assert hasattr(mc, "sizes_checkbox")
        assert not mc.sizes_checkbox.isChecked()

    def test_has_event_id_lineedit(self, mc):
        assert hasattr(mc, "event_id_lineEdit")

    def test_has_n_events_lineedit(self, mc):
        assert hasattr(mc, "n_events_lineEdit")

    def test_has_all_buttons(self, mc):
        for attr in [
            "update_plot_button",
            "undo_button",
            "reset_button",
            "load_button",
            "save_plot_button",
            "export_csv_subset_button",
            "export_plot_data_pushButton",
            "filter_add_button",
            "filter_info_button",
            "filter_delete_button",
            "save_filter_button",
            "load_filter_button",
            "plot_events_pushButton",
            "left_arrow_button",
            "right_arrow_button",
            "db_loader_add_button",
            "db_loader_info_button",
            "db_loader_delete_button",
            "selection_tree_button",
        ]:
            assert hasattr(mc, attr), f"Missing button: {attr}"

    def test_active_popups_empty(self, mc):
        assert mc.active_popups == {}


# ===========================================================================
# _on_sizes_checkbox_toggled
# ===========================================================================


class TestSizesCheckbox:
    def test_unchecked_uses_int_placeholder(self, mc):
        mc.sizes_checkbox.setChecked(False)
        assert "10" in mc.bins_lineEdit.placeholderText()

    def test_checked_uses_float_placeholder(self, mc):
        mc.sizes_checkbox.setChecked(True)
        assert "1.2" in mc.bins_lineEdit.placeholderText()

    def test_toggle_back_to_int(self, mc):
        mc.sizes_checkbox.setChecked(True)
        mc.sizes_checkbox.setChecked(False)
        assert "10" in mc.bins_lineEdit.placeholderText()


# ===========================================================================
# createButton / createLabel / create_comboBox
# ===========================================================================


class TestWidgetFactories:
    def test_create_comboBox_returns_combobox(self, mc):
        cb = mc.create_comboBox(mc)
        assert isinstance(cb, QComboBox)

    def test_createButton_text(self, mc):
        btn = mc.createButton(mc, "Test Button")
        assert btn.text() == "Test Button"

    def test_createButton_checkable(self, mc):
        btn = mc.createButton(mc, "X")
        assert btn.isCheckable()

    def test_createButton_bold(self, mc):
        btn = mc.createButton(mc, "X", bold=True)
        assert btn.font().bold()

    def test_createButton_not_bold(self, mc):
        btn = mc.createButton(mc, "X", bold=False)
        assert not btn.font().bold()

    def test_createLabel_text(self, mc):
        lbl = mc.createLabel(mc, 12, "MY LABEL")
        assert lbl.text() == "MY LABEL"

    def test_create_add_button_returns_toolbutton(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_add_button(mc, cb, "Add", "SomeClass")
        assert isinstance(btn, QToolButton)
        assert btn.isEnabled()

    def test_create_info_button_returns_toolbutton(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_info_button(mc, cb, "Edit", "SomeClass")
        assert isinstance(btn, QToolButton)

    def test_create_delete_button_returns_toolbutton(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_delete_button(mc, cb, "Delete", "SomeClass")
        assert isinstance(btn, QToolButton)

    def test_create_filter_info_button(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_filter_info_button(mc, cb, "Edit filter")
        assert isinstance(btn, QToolButton)
        assert btn.toolTip() == "Edit filter"

    def test_create_add_filter_button(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_add_filter_button(mc, cb, "Add filter")
        assert isinstance(btn, QToolButton)
        assert btn.toolTip() == "Add filter"

    def test_create_filter_delete_button(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.create_filter_delete_button(mc, cb, "Delete filter")
        assert isinstance(btn, QToolButton)
        assert btn.toolTip() == "Delete filter"


# ===========================================================================
# is_placeholder_item / toggle_info_button
# ===========================================================================


class TestPlaceholderAndToggle:
    def test_is_placeholder_no_database(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("No Event Database")
        assert mc.is_placeholder_item(mc.db_loader_comboBox)

    def test_is_placeholder_real_item(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("my_db.sqlite")
        assert not mc.is_placeholder_item(mc.db_loader_comboBox)

    def test_toggle_info_button_enables_with_real_item(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("my_db.sqlite")
        btn = mc.createButton(mc, "test")
        mc.toggle_info_button(btn, mc.db_loader_comboBox)
        assert btn.isEnabled()

    def test_toggle_info_button_disables_with_placeholder(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("No Event Database")
        btn = mc.createButton(mc, "test")
        mc.toggle_info_button(btn, mc.db_loader_comboBox)
        assert not btn.isEnabled()

    def test_toggle_info_button_disables_empty_combobox(self, mc):
        cb = mc.create_comboBox(mc)
        btn = mc.createButton(mc, "test")
        mc.toggle_info_button(btn, cb)
        assert not btn.isEnabled()


# ===========================================================================
# _plot_type_changed — axis enable/disable logic
# ===========================================================================


class TestPlotTypeChanged:
    def _set_plot_type(self, mc, plot_type):
        idx = mc.plot_type_comboBox.findText(plot_type)
        assert idx >= 0, f"Plot type '{plot_type}' not found"
        mc.plot_type_comboBox.setCurrentIndex(idx)

    def test_heatmap_enables_xy_disables_z(self, mc):
        self._set_plot_type(mc, "Heatmap")
        assert mc.x_axis_comboBox.isEnabled()
        assert mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_scatterplot_enables_xy_disables_z(self, mc):
        self._set_plot_type(mc, "Scatterplot")
        assert mc.x_axis_comboBox.isEnabled()
        assert mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_histogram_enables_x_disables_yz(self, mc):
        self._set_plot_type(mc, "Histogram")
        assert mc.x_axis_comboBox.isEnabled()
        assert not mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_kernel_density_enables_x_disables_yz(self, mc):
        self._set_plot_type(mc, "Kernel Density Plot")
        assert mc.x_axis_comboBox.isEnabled()
        assert not mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_3d_scatterplot_enables_xyz(self, mc):
        self._set_plot_type(mc, "3D Scatterplot")
        assert mc.x_axis_comboBox.isEnabled()
        assert mc.y_axis_comboBox.isEnabled()
        assert mc.z_axis_comboBox.isEnabled()

    def test_raw_all_points_histogram_disables_all_axes(self, mc):
        self._set_plot_type(mc, "Raw All Points Histogram")
        assert not mc.x_axis_comboBox.isEnabled()
        assert not mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_filtered_all_points_histogram_disables_all_axes(self, mc):
        self._set_plot_type(mc, "Filtered All Points Histogram")
        assert not mc.x_axis_comboBox.isEnabled()
        assert not mc.y_axis_comboBox.isEnabled()
        assert not mc.z_axis_comboBox.isEnabled()

    def test_heatmap_clears_z_logscale(self, mc):
        mc.z_axis_logscale_checkbox.setChecked(True)
        self._set_plot_type(mc, "Heatmap")
        assert not mc.z_axis_logscale_checkbox.isChecked()

    def test_histogram_clears_yz_logscale(self, mc):
        mc.y_axis_logscale_checkbox.setChecked(True)
        mc.z_axis_logscale_checkbox.setChecked(True)
        self._set_plot_type(mc, "Histogram")
        assert not mc.y_axis_logscale_checkbox.isChecked()
        assert not mc.z_axis_logscale_checkbox.isChecked()

    def test_plot_type_changed_emits_signal(self, mc):
        received = []
        mc.actionTriggered.connect(lambda m, a, p: received.append(a))
        self._set_plot_type(mc, "Scatterplot")
        assert "plot_type_changed" in received


# ===========================================================================
# update_axes
# ===========================================================================


class TestUpdateAxes:
    def test_populates_all_three_comboboxes(self, mc):
        mc.update_axes(["duration", "voltage", "current"])
        assert mc.x_axis_comboBox.count() == 3
        assert mc.y_axis_comboBox.count() == 3
        assert mc.z_axis_comboBox.count() == 3

    def test_restores_previous_x_selection(self, mc):
        mc.update_axes(["duration", "voltage", "current"])
        mc.x_axis_comboBox.setCurrentText("voltage")
        mc.update_axes(["duration", "voltage", "current"])
        assert mc.x_axis_comboBox.currentText() == "voltage"

    def test_restores_previous_y_selection(self, mc):
        mc.update_axes(["duration", "voltage", "current"])
        mc.y_axis_comboBox.setCurrentText("current")
        mc.update_axes(["duration", "voltage", "current"])
        assert mc.y_axis_comboBox.currentText() == "current"

    def test_restores_previous_z_selection(self, mc):
        mc.update_axes(["duration", "voltage", "current"])
        mc.z_axis_comboBox.setCurrentText("duration")
        mc.update_axes(["duration", "voltage", "current"])
        assert mc.z_axis_comboBox.currentText() == "duration"

    def test_clears_selection_when_item_removed(self, mc):
        mc.update_axes(["duration", "voltage"])
        mc.x_axis_comboBox.setCurrentText("voltage")
        mc.update_axes(["duration"])  # voltage gone
        assert mc.x_axis_comboBox.currentText() != "voltage"

    def test_empty_axes_clears_comboboxes(self, mc):
        mc.update_axes(["a", "b"])
        mc.update_axes([])
        assert mc.x_axis_comboBox.count() == 0


# ===========================================================================
# update_column_units_label
# ===========================================================================


class TestUpdateColumnUnitsLabel:
    def test_sets_x_axis_units(self, mc):
        mc.update_column_units_label("ms", "x_axis")
        assert mc.x_axis_units_label.text() == "ms"

    def test_sets_y_axis_units(self, mc):
        mc.update_column_units_label("pA", "y_axis")
        assert mc.y_axis_units_label.text() == "pA"

    def test_sets_z_axis_units(self, mc):
        mc.update_column_units_label("nm", "z_axis")
        assert mc.z_axis_units_label.text() == "nm"

    def test_none_units_becomes_space(self, mc):
        mc.update_column_units_label(None, "x_axis")
        assert mc.x_axis_units_label.text() == " "

    def test_empty_units_becomes_space(self, mc):
        mc.update_column_units_label("", "y_axis")
        assert mc.y_axis_units_label.text() == " "

    def test_unknown_axis_is_noop(self, mc):
        mc.x_axis_units_label.setText("original")
        mc.update_column_units_label("ms", "unknown_axis")
        assert mc.x_axis_units_label.text() == "original"


# ===========================================================================
# show_filter_info_dialog_single / delete_filter_by_name
# ===========================================================================


class TestFilterCallbacks:
    def test_show_filter_info_emits_edit_filter_requested(self, mc):
        received = []
        mc.edit_filter_requested.connect(
            lambda name, loader: received.append((name, loader))
        )
        mc.db_loader_comboBox.addItem("my_loader")
        mc.db_loader_comboBox.setCurrentText("my_loader")
        mc.show_filter_info_dialog_single("my_filter")
        assert received == [("my_filter", "my_loader")]

    def test_delete_filter_by_name_emits_delete_filter_requested(self, mc):
        received = []
        mc.delete_filter_requested.connect(lambda n: received.append(n))
        mc.delete_filter_by_name("old_filter")
        assert received == ["old_filter"]


# ===========================================================================
# show_plugin_edit_manager / show_plugin_add_manager / delete_plugin
# ===========================================================================


class TestPluginManagers:
    def test_show_plugin_edit_manager_emits_edit_processed(self, mc):
        received = []
        mc.edit_processed.connect(lambda m, k: received.append((m, k)))
        mc.db_loader_comboBox.addItem("loader_a")
        mc.db_loader_comboBox.setCurrentText("loader_a")
        mc.show_plugin_edit_manager(mc.db_loader_comboBox, "MetaDatabaseLoader")
        assert received == [("MetaDatabaseLoader", "loader_a")]

    def test_show_plugin_add_manager_emits_add_processed(self, mc):
        received = []
        mc.add_processed.connect(lambda m: received.append(m))
        mc.show_plugin_add_manager(mc.db_loader_comboBox, "MetaDatabaseLoader")
        assert received == ["MetaDatabaseLoader"]

    def test_delete_plugin_emits_delete_processed(self, mc):
        received = []
        mc.delete_processed.connect(lambda m, k: received.append((m, k)))
        mc.db_loader_comboBox.addItem("loader_b")
        mc.db_loader_comboBox.setCurrentText("loader_b")
        mc.delete_plugin(mc.db_loader_comboBox, "MetaDatabaseLoader")
        assert received == [("MetaDatabaseLoader", "loader_b")]


# ===========================================================================
# clear_popup_reference
# ===========================================================================


class TestClearPopupReference:
    def test_removes_existing_popup(self, mc):
        cb = mc.create_comboBox(mc)
        mc.active_popups[cb] = object()
        mc.clear_popup_reference(cb)
        assert cb not in mc.active_popups

    def test_ignores_missing_popup(self, mc):
        cb = mc.create_comboBox(mc)
        mc.clear_popup_reference(cb)  # should not raise


# ===========================================================================
# collect_parameters
# ===========================================================================


class TestCollectParameters:
    def test_returns_dict(self, mc):
        params = mc.collect_parameters()
        assert isinstance(params, dict)

    def test_default_plot_type(self, mc):
        params = mc.collect_parameters()
        assert params["plot_type"] == "Select Plot Type"

    def test_sizes_false_by_default(self, mc):
        params = mc.collect_parameters()
        assert params["sizes"] is False

    def test_raw_false_by_default(self, mc):
        params = mc.collect_parameters()
        assert params["raw"] is False

    def test_bins_none_when_empty(self, mc):
        mc.bins_lineEdit.setText("")
        params = mc.collect_parameters()
        assert params["bins"] is None

    def test_bins_as_int_list(self, mc):
        mc.bins_lineEdit.setText("50")
        mc.sizes_checkbox.setChecked(False)
        params = mc.collect_parameters()
        assert params["bins"] == [50]

    def test_bins_as_float_list_when_sizes_checked(self, mc):
        mc.sizes_checkbox.setChecked(True)
        mc.bins_lineEdit.setText("0.5")
        params = mc.collect_parameters()
        assert params["bins"] == [0.5]

    def test_multiple_bins(self, mc):
        mc.bins_lineEdit.setText("10,20,30")
        mc.sizes_checkbox.setChecked(False)
        params = mc.collect_parameters()
        assert params["bins"] == [10, 20, 30]

    def test_x_axis_reflects_combobox(self, mc):
        mc.update_axes(["duration", "voltage"])
        mc.x_axis_comboBox.setCurrentText("voltage")
        params = mc.collect_parameters()
        assert params["x_axis"] == "voltage"

    def test_logscale_flags(self, mc):
        mc.x_axis_logscale_checkbox.setChecked(True)
        mc.y_axis_logscale_checkbox.setChecked(False)
        params = mc.collect_parameters()
        assert params["x_log"] is True
        assert params["y_log"] is False

    def test_event_id_none_by_default(self, mc):
        params = mc.collect_parameters()
        assert params["event_id"] is None

    def test_n_events_defaults_to_one(self, mc):
        params = mc.collect_parameters()
        assert params["n_events"] == 1

    def test_db_loader_reflects_combobox(self, mc):
        mc.db_loader_comboBox.addItem("test_loader")
        mc.db_loader_comboBox.setCurrentText("test_loader")
        params = mc.collect_parameters()
        assert params["db_loader"] == "test_loader"


# ===========================================================================
# on_loader_changed
# ===========================================================================


class TestOnLoaderChanged:
    def test_emits_loader_changed_action(self, mc):
        received = []
        mc.actionTriggered.connect(lambda m, a, p: received.append(a))
        mc.on_loader_changed()
        assert "loader_changed" in received

    def test_triggered_by_combobox_change(self, mc):
        received = []
        mc.actionTriggered.connect(lambda m, a, p: received.append(a))
        mc.db_loader_comboBox.addItem("new_loader")
        mc.db_loader_comboBox.setCurrentIndex(mc.db_loader_comboBox.count() - 1)
        assert "loader_changed" in received


# ===========================================================================
# get_selected_filter_names
# ===========================================================================


class TestGetSelectedFilterNames:
    def test_empty_by_default(self, mc):
        assert mc.get_selected_filter_names() == []

    def test_returns_selected_items(self, mc):
        mc.filter_comboBox.addItem("filter_a")
        mc.filter_comboBox.selectItem("filter_a", select=True)
        assert "filter_a" in mc.get_selected_filter_names()


# ===========================================================================
# validate_inputs — button state logic
# ===========================================================================


class TestValidateInputs:
    def test_no_loader_disables_load_button(self, mc):
        mc.db_loader_comboBox.clear()
        mc.validate_inputs()
        assert not mc.load_button.isEnabled()

    def test_no_loader_disables_save_plot(self, mc):
        mc.db_loader_comboBox.clear()
        mc.validate_inputs()
        assert not mc.save_plot_button.isEnabled()

    def test_no_loader_disables_plot_events(self, mc):
        mc.db_loader_comboBox.clear()
        mc.validate_inputs()
        assert not mc.plot_events_pushButton.isEnabled()

    def test_no_loader_disables_filter_add(self, mc):
        mc.db_loader_comboBox.clear()
        mc.validate_inputs()
        assert not mc.filter_add_button.isEnabled()

    def test_with_loader_enables_filter_add(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("my_loader")
        mc.validate_inputs()
        assert mc.filter_add_button.isEnabled()

    def test_no_plot_type_disables_update_plot(self, mc):
        mc.plot_type_comboBox.setCurrentIndex(0)  # "Select Plot Type"
        mc.validate_inputs()
        assert not mc.update_plot_button.isEnabled()

    def test_plot_type_selected_enables_update_plot(self, mc):
        mc.update_axes(["duration"])
        mc.x_axis_comboBox.setCurrentText("duration")
        mc.plot_type_comboBox.setCurrentIndex(1)  # "Histogram"
        mc.db_loader_comboBox.addItem("ldr")
        mc.validate_inputs()
        assert mc.update_plot_button.isEnabled()

    def test_no_filter_selected_disables_filter_edit(self, mc):
        mc.validate_inputs()
        assert not mc.filter_info_button.isEnabled()

    def test_filter_selected_enables_filter_edit(self, mc):
        mc.filter_comboBox.addItem("f1")
        mc.filter_comboBox.selectItem("f1", select=True)
        mc.validate_inputs()
        assert mc.filter_info_button.isEnabled()

    def test_filter_selected_enables_filter_delete(self, mc):
        mc.filter_comboBox.addItem("f1")
        mc.filter_comboBox.selectItem("f1", select=True)
        mc.validate_inputs()
        assert mc.filter_delete_button.isEnabled()

    def test_export_csv_always_enabled(self, mc):
        mc.validate_inputs()
        assert mc.export_csv_subset_button.isEnabled()

    def test_no_database_placeholder_disables_loader(self, mc):
        mc.db_loader_comboBox.clear()
        mc.db_loader_comboBox.addItem("No Event Database")
        mc.validate_inputs()
        assert not mc.load_button.isEnabled()


# ===========================================================================
# on_button_clicked — signal emission and auto-uncheck
# ===========================================================================


class TestOnButtonClicked:
    def _collect_actions(self, mc):
        received = []
        mc.actionTriggered.connect(lambda m, a, p: received.append((m, a)))
        return received

    def test_update_plot_emits_update_plot(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("update_plot")
        assert any(a == "update_plot" for _, a in received)

    def test_reset_emits_reset_plot(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("reset")
        assert any(a == "reset_plot" for _, a in received)

    def test_undo_emits_undo_plot(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("undo")
        assert any(a == "undo_plot" for _, a in received)

    def test_plot_events_emits_plot_events(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("plot_events")
        assert any(a == "plot_events" for _, a in received)

    def test_left_arrow_emits_shift_backward(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("left_arrow")
        assert any(a == "shift_range_backward" for _, a in received)

    def test_right_arrow_emits_shift_forward(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("right_arrow")
        assert any(a == "shift_range_forward" for _, a in received)

    def test_add_filter_emits_add_filter(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("add_filter")
        assert any(a == "add_filter" for _, a in received)

    def test_edit_filter_emits_edit_filter(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("edit_filter")
        assert any(a == "edit_filter" for _, a in received)

    def test_delete_filter_emits_delete_filter(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("delete_filter")
        assert any(a == "delete_filter" for _, a in received)

    def test_save_filter_emits_save_filter(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("save_filter")
        assert any(a == "save_filter" for _, a in received)

    def test_load_filter_emits_load_filter(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("load_filter")
        assert any(a == "load_filter" for _, a in received)

    def test_save_plot_emits_save_plot_config(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("save_plot")
        assert any(a == "save_plot_config" for _, a in received)

    def test_export_csv_emits_export_csv_subset(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("export_csv_subset")
        assert any(a == "export_csv_subset" for _, a in received)

    def test_export_plot_data_emits_export_plot_data(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("export_plot_data")
        assert any(a == "export_plot_data" for _, a in received)

    def test_load_emits_load_plot(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("load")
        assert any(a == "load_plot" for _, a in received)

    def test_selection_tree_emits_select_experiment(self, mc):
        received = self._collect_actions(mc)
        mc.on_button_clicked("selection_tree")
        assert any(a == "select_experiment_and_channel" for _, a in received)

    def test_unknown_button_is_ignored(self, mc):
        # An unmapped button_type emits nothing and unchecks nothing. This used
        # to raise AttributeError, because the fallback passed to
        # button_mapping.get() was a plain function with no setChecked.
        received = self._collect_actions(mc)
        mc.on_button_clicked("nonexistent_button")
        assert received == []

    def test_button_auto_unchecked_after_click(self, mc):
        mc.update_plot_button.setChecked(True)
        mc.on_button_clicked("update_plot")
        assert not mc.update_plot_button.isChecked()

    def test_emitted_parameters_contain_db_loader(self, mc):
        received_params = []
        mc.actionTriggered.connect(lambda m, a, p: received_params.append(p))
        mc.on_button_clicked("update_plot")
        assert len(received_params) > 0
        assert "db_loader" in received_params[0][0]


# ===========================================================================
# update_loaders
# ===========================================================================


class TestUpdateLoaders:
    def test_populates_combobox(self, mc):
        mc.update_loaders(["db1", "db2", "db3"])
        assert mc.db_loader_comboBox.count() == 3

    def test_empty_list_inserts_placeholder(self, mc):
        mc.update_loaders([])
        assert mc.db_loader_comboBox.itemText(0) == "No Event Database"

    def test_restores_previous_selection(self, mc):
        mc.update_loaders(["db1", "db2"])
        mc.db_loader_comboBox.setCurrentText("db2")
        mc.update_loaders(["db1", "db2", "db3"])
        assert mc.db_loader_comboBox.currentText() == "db2"

    def test_falls_back_to_first_when_selection_gone(self, mc):
        mc.update_loaders(["db1", "db2"])
        mc.db_loader_comboBox.setCurrentText("db2")
        mc.update_loaders(["db3", "db4"])
        assert mc.db_loader_comboBox.currentIndex() == 0

    def test_single_loader(self, mc):
        mc.update_loaders(["only_db"])
        assert mc.db_loader_comboBox.count() == 1
        assert mc.db_loader_comboBox.currentText() == "only_db"


# ===========================================================================
# set_event_index_input
# ===========================================================================


class TestSetEventIdInput:
    def test_sets_value(self, mc):
        mc.set_event_id_input(5)
        assert mc.event_id_lineEdit.text() == "5"

    def test_updates_value_on_subsequent_calls(self, mc):
        mc.set_event_id_input(5)
        mc.set_event_id_input(12)
        assert mc.event_id_lineEdit.text() == "12"


# ===========================================================================
# update_filters
# ===========================================================================


class TestUpdateFilters:
    def test_populates_filter_combobox(self, mc):
        mc.update_filters(["filter_a", "filter_b"])
        assert mc.filter_comboBox.listWidget.count() == 2

    def test_restores_previous_selection(self, mc):
        mc.update_filters(["f1", "f2"])
        mc.filter_comboBox.selectItem("f2", select=True)
        mc.update_filters(["f1", "f2", "f3"])
        assert "f2" in mc.filter_comboBox.getSelectedItems()

    def test_clears_old_items(self, mc):
        mc.update_filters(["old_f"])
        mc.update_filters(["new_f1", "new_f2"])
        assert mc.filter_comboBox.listWidget.count() == 2

    def test_integer_filters_converted_to_str(self, mc):
        mc.update_filters([1, 2, 3])
        # Should not raise — int filters are converted to str internally


# ===========================================================================
# update_units (signal emission)
# ===========================================================================


class TestUpdateUnits:
    def test_emits_columns_updated(self, mc):
        received = []
        mc.actionTriggered.connect(lambda m, a, p: received.append(a))
        mc.update_units(mc.x_axis_comboBox, mc.x_axis_units_label)
        assert "columns_updated" in received
