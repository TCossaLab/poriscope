"""
Full unit-test suite for EventAnalysisControls.

All tests use a real EventAnalysisControls instance — no mocking needed
since the class has no file dialogs, no database calls, and no blocking modals
(get_plugin_data reads a file but is never called from the UI automatically).

Run with:
    pytest test_event_analysis_controls.py -v
    pytest test_event_analysis_controls.py --cov=poriscope --cov-report=html
"""

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QToolButton

from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)

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
def ec(qt_app):
    """Fresh EventAnalysisControls for each test."""
    widget = EventAnalysisControls()
    qt_app.processEvents()
    return widget


# ===========================================================================
# Helpers
# ===========================================================================


def _select_channel(ec, channel_text):
    """Add and select a channel in the MultiSelectComboBox."""
    ec.update_channels([channel_text])


def _collect_actions(ec):
    received = []
    ec.actionTriggered.connect(lambda m, a, p: received.append((m, a)))
    return received


# ===========================================================================
# Instantiation / setupUi
# ===========================================================================


class TestInstantiation:
    def test_creates_without_error(self, ec):
        assert ec is not None

    def test_has_loaders_combobox(self, ec):
        assert hasattr(ec, "loaders_comboBox")
        assert isinstance(ec.loaders_comboBox, QComboBox)

    def test_has_filters_combobox(self, ec):
        assert hasattr(ec, "filters_comboBox")

    def test_has_writers_combobox(self, ec):
        assert hasattr(ec, "writers_comboBox")

    def test_has_eventfitters_combobox(self, ec):
        assert hasattr(ec, "eventfitters_comboBox")

    def test_has_channel_combobox(self, ec):
        assert hasattr(ec, "channel_comboBox")

    def test_has_event_index_lineedit(self, ec):
        assert hasattr(ec, "event_index_lineEdit")

    def test_has_all_buttons(self, ec):
        for attr in [
            "plot_events_pushButton",
            "left_arrow_button",
            "right_arrow_button",
            "fit_events_pushButton",
            "commit_btn",
            "export_plot_data_pushButton",
            "loaders_add_button",
            "loaders_info_button",
            "loaders_delete_button",
            "filters_add_button",
            "filters_info_button",
            "filters_delete_button",
            "eventfitters_add_button",
            "eventfitters_info_button",
            "eventfitters_delete_button",
            "writers_add_button",
            "writers_info_button",
            "writers_delete_button",
        ]:
            assert hasattr(ec, attr), f"Missing: {attr}"

    def test_has_raw_checkbox(self, ec):
        assert hasattr(ec, "raw_checkbox")
        assert not ec.raw_checkbox.isChecked()

    def test_max_range_size(self, ec):
        assert ec.max_range_size == 16

    def test_active_popups_empty(self, ec):
        assert ec.active_popups == {}


# ===========================================================================
# Widget factories
# ===========================================================================


class TestWidgetFactories:
    def test_create_combobox(self, ec):
        cb = ec.create_comboBox(ec)
        assert isinstance(cb, QComboBox)

    def test_createButton_text(self, ec):
        btn = ec.createButton(ec, "My Button")
        assert btn.text() == "My Button"

    def test_createButton_checkable(self, ec):
        btn = ec.createButton(ec, "X")
        assert btn.isCheckable()

    def test_createButton_bold(self, ec):
        btn = ec.createButton(ec, "X", bold=True)
        assert btn.font().bold()

    def test_createButton_not_bold(self, ec):
        btn = ec.createButton(ec, "X", bold=False)
        assert not btn.font().bold()

    def test_createLabel_text(self, ec):
        lbl = ec.createLabel(ec, 12, "TEST LABEL")
        assert lbl.text() == "TEST LABEL"

    def test_create_add_button(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_add_button(ec, cb, "Add", "SomeClass")
        assert isinstance(btn, QToolButton)
        assert btn.isEnabled()

    def test_create_info_button(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_info_button(ec, cb, "Edit", "SomeClass")
        assert isinstance(btn, QToolButton)

    def test_create_delete_button(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_delete_button(ec, cb, "Delete", "SomeClass")
        assert isinstance(btn, QToolButton)

    def test_add_button_tooltip(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_add_button(ec, cb, "My Tooltip", "X")
        assert btn.toolTip() == "My Tooltip"

    def test_info_button_tooltip(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_info_button(ec, cb, "Edit Tooltip", "X")
        assert btn.toolTip() == "Edit Tooltip"

    def test_delete_button_tooltip(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.create_delete_button(ec, cb, "Delete Tooltip", "X")
        assert btn.toolTip() == "Delete Tooltip"


# ===========================================================================
# is_placeholder_item / toggle_info_button
# ===========================================================================


class TestPlaceholderAndToggle:
    def test_no_loader_is_placeholder(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("No Loader")
        assert ec.is_placeholder_item(ec.loaders_comboBox)

    def test_no_database_writer_is_placeholder(self, ec):
        ec.writers_comboBox.clear()
        ec.writers_comboBox.addItem("No Database Writer")
        assert ec.is_placeholder_item(ec.writers_comboBox)

    def test_no_filter_is_placeholder(self, ec):
        ec.filters_comboBox.clear()
        ec.filters_comboBox.addItem("No Filter")
        assert ec.is_placeholder_item(ec.filters_comboBox)

    def test_no_eventfitter_is_placeholder(self, ec):
        ec.eventfitters_comboBox.clear()
        ec.eventfitters_comboBox.addItem("No Event Fitter")
        assert ec.is_placeholder_item(ec.eventfitters_comboBox)

    def test_real_item_not_placeholder(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("my_loader.sqlite")
        assert not ec.is_placeholder_item(ec.loaders_comboBox)

    def test_toggle_enables_with_real_item(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("real_loader")
        btn = ec.createButton(ec, "t")
        ec.toggle_info_button(btn, ec.loaders_comboBox)
        assert btn.isEnabled()

    def test_toggle_disables_with_placeholder(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("No Loader")
        btn = ec.createButton(ec, "t")
        ec.toggle_info_button(btn, ec.loaders_comboBox)
        assert not btn.isEnabled()

    def test_toggle_disables_empty_combobox(self, ec):
        cb = ec.create_comboBox(ec)
        btn = ec.createButton(ec, "t")
        ec.toggle_info_button(btn, cb)
        assert not btn.isEnabled()


# ===========================================================================
# clear_popup_reference
# ===========================================================================


class TestClearPopupReference:
    def test_removes_existing(self, ec):
        cb = ec.create_comboBox(ec)
        ec.active_popups[cb] = object()
        ec.clear_popup_reference(cb)
        assert cb not in ec.active_popups

    def test_missing_key_no_error(self, ec):
        cb = ec.create_comboBox(ec)
        ec.clear_popup_reference(cb)  # should not raise


# ===========================================================================
# show_plugin_edit_manager / show_plugin_add_manager / delete_plugin
# ===========================================================================


class TestPluginManagers:
    def test_edit_emits_edit_processed(self, ec):
        received = []
        ec.edit_processed.connect(lambda m, k: received.append((m, k)))
        ec.loaders_comboBox.addItem("my_loader")
        ec.loaders_comboBox.setCurrentText("my_loader")
        ec.show_plugin_edit_manager(ec.loaders_comboBox, "MetaEventLoader")
        assert received == [("MetaEventLoader", "my_loader")]

    def test_add_emits_add_processed(self, ec):
        received = []
        ec.add_processed.connect(lambda m: received.append(m))
        ec.show_plugin_add_manager(ec.loaders_comboBox, "MetaEventLoader")
        assert received == ["MetaEventLoader"]

    def test_delete_emits_delete_processed(self, ec):
        received = []
        ec.delete_processed.connect(lambda m, k: received.append((m, k)))
        ec.loaders_comboBox.addItem("my_loader")
        ec.loaders_comboBox.setCurrentText("my_loader")
        ec.delete_plugin(ec.loaders_comboBox, "MetaEventLoader")
        assert received == [("MetaEventLoader", "my_loader")]


# ===========================================================================
# collect_parameters
# ===========================================================================


class TestCollectParameters:
    def test_returns_dict(self, ec):
        params = ec.collect_parameters()
        assert isinstance(params, dict)

    def test_default_loader(self, ec):
        params = ec.collect_parameters()
        assert params["loader"] == "No Loader"

    def test_default_filter(self, ec):
        params = ec.collect_parameters()
        assert params["filter"] == "No Filter"

    def test_default_writer(self, ec):
        params = ec.collect_parameters()
        assert params["writer"] == "No Database Writer"

    def test_default_eventfitter(self, ec):
        params = ec.collect_parameters()
        assert params["eventfitter"] == "No Event Fitter"

    def test_event_index_empty_by_default(self, ec):
        params = ec.collect_parameters()
        assert params["event_index"] == []

    def test_raw_false_by_default(self, ec):
        params = ec.collect_parameters()
        assert params["raw"] is False

    def test_raw_true_when_checked(self, ec):
        ec.raw_checkbox.setChecked(True)
        params = ec.collect_parameters()
        assert params["raw"] is True

    def test_loader_reflects_combobox(self, ec):
        ec.loaders_comboBox.addItem("test_loader")
        ec.loaders_comboBox.setCurrentText("test_loader")
        params = ec.collect_parameters()
        assert params["loader"] == "test_loader"

    def test_filter_reflects_combobox(self, ec):
        ec.filters_comboBox.addItem("my_filter")
        ec.filters_comboBox.setCurrentText("my_filter")
        params = ec.collect_parameters()
        assert params["filter"] == "my_filter"

    def test_writer_reflects_combobox(self, ec):
        ec.writers_comboBox.addItem("my_writer")
        ec.writers_comboBox.setCurrentText("my_writer")
        params = ec.collect_parameters()
        assert params["writer"] == "my_writer"

    def test_eventfitter_reflects_combobox(self, ec):
        ec.eventfitters_comboBox.addItem("my_fitter")
        ec.eventfitters_comboBox.setCurrentText("my_fitter")
        params = ec.collect_parameters()
        assert params["eventfitter"] == "my_fitter"

    def test_channel_reflects_selection(self, ec):
        ec.update_channels(["0", "1"])
        selected = ec.channel_comboBox.getSelectedItems()
        params = ec.collect_parameters()
        assert params["channel"] == selected


# ===========================================================================
# on_parameter_changed
# ===========================================================================


class TestOnParameterChanged:
    def test_emits_parameter_changed(self, ec):
        received = []
        ec.actionTriggered.connect(lambda m, a, p: received.append(a))
        ec.on_parameter_changed()
        assert "parameter_changed" in received

    def test_triggered_by_loader_change(self, ec):
        received = []
        ec.actionTriggered.connect(lambda m, a, p: received.append(a))
        ec.loaders_comboBox.addItem("ldr")
        ec.loaders_comboBox.setCurrentIndex(ec.loaders_comboBox.count() - 1)
        assert "parameter_changed" in received

    def test_triggered_by_filter_change(self, ec):
        received = []
        ec.actionTriggered.connect(lambda m, a, p: received.append(a))
        ec.filters_comboBox.addItem("f1")
        ec.filters_comboBox.setCurrentIndex(ec.filters_comboBox.count() - 1)
        assert "parameter_changed" in received

    def test_triggered_by_writer_change(self, ec):
        received = []
        ec.actionTriggered.connect(lambda m, a, p: received.append(a))
        ec.writers_comboBox.addItem("w1")
        ec.writers_comboBox.setCurrentIndex(ec.writers_comboBox.count() - 1)
        assert "parameter_changed" in received

    def test_triggered_by_eventfitter_change(self, ec):
        received = []
        ec.actionTriggered.connect(lambda m, a, p: received.append(a))
        ec.eventfitters_comboBox.addItem("ef1")
        ec.eventfitters_comboBox.setCurrentIndex(ec.eventfitters_comboBox.count() - 1)
        assert "parameter_changed" in received


# ===========================================================================
# validate_inputs — button state
# ===========================================================================


class TestValidateInputs:
    def test_no_loader_disables_plot_events(self, ec):
        ec.loaders_comboBox.clear()
        ec.validate_inputs()
        assert not ec.plot_events_pushButton.isEnabled()

    def test_no_loader_disables_fit_events(self, ec):
        ec.loaders_comboBox.clear()
        ec.validate_inputs()
        assert not ec.fit_events_pushButton.isEnabled()

    def test_no_channels_disables_plot_events(self, ec):
        ec.loaders_comboBox.addItem("ldr")
        # channel_comboBox empty → no channels selected
        ec.validate_inputs()
        assert not ec.plot_events_pushButton.isEnabled()

    def test_no_channels_disables_commit(self, ec):
        ec.validate_inputs()
        assert not ec.commit_btn.isEnabled()

    def test_multiple_channels_disables_plot_events(self, ec):
        ec.loaders_comboBox.addItem("ldr")
        ec.update_channels(["0", "1"])
        # Both selected by default on first load
        ec.validate_inputs()
        assert not ec.plot_events_pushButton.isEnabled()

    def test_single_channel_with_loader_enables_fit_events(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("ldr")
        ec.eventfitters_comboBox.clear()
        ec.eventfitters_comboBox.addItem("ef1")
        ec.update_channels(["0"])
        ec.validate_inputs()
        assert ec.fit_events_pushButton.isEnabled()

    def test_no_writer_disables_commit(self, ec):
        ec.writers_comboBox.clear()
        ec.validate_inputs()
        assert not ec.commit_btn.isEnabled()

    def test_with_loader_and_writer_and_channel_enables_commit(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("ldr")
        ec.writers_comboBox.clear()
        ec.writers_comboBox.addItem("wrt")
        ec.update_channels(["0"])
        ec.validate_inputs()
        assert ec.commit_btn.isEnabled()

    def test_placeholder_loader_disables_plot_events(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("No Loader")
        ec.update_channels(["0"])
        ec.validate_inputs()
        assert not ec.plot_events_pushButton.isEnabled()

    def test_placeholder_writer_disables_commit(self, ec):
        ec.loaders_comboBox.clear()
        ec.loaders_comboBox.addItem("ldr")
        ec.writers_comboBox.clear()
        ec.writers_comboBox.addItem("No Database Writer")
        ec.update_channels(["0"])
        ec.validate_inputs()
        assert not ec.commit_btn.isEnabled()


# ===========================================================================
# on_button_clicked — signal emission and auto-uncheck
# ===========================================================================


class TestOnButtonClicked:
    def test_export_plot_data(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("export_plot_data")
        assert any(a == "export_plot_data" for _, a in received)

    def test_fit_events(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("fit_events")
        assert any(a == "fit_events" for _, a in received)

    def test_left_arrow(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("left_arrow")
        assert any(a == "shift_range_backward" for _, a in received)

    def test_plot_events(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("plot_events")
        assert any(a == "plot_events" for _, a in received)

    def test_right_arrow(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("right_arrow")
        assert any(a == "shift_range_forward" for _, a in received)

    def test_commit_events(self, ec):
        received = _collect_actions(ec)
        ec.on_button_clicked("commit_events")
        assert any(a == "commit_events" for _, a in received)

    def test_all_emit_event_analysis_model(self, ec):
        for btn in [
            "export_plot_data",
            "fit_events",
            "plot_events",
            "left_arrow",
            "right_arrow",
            "commit_events",
        ]:
            received = []
            ec.actionTriggered.connect(lambda m, a, p, _b=btn: received.append(m))
            ec.on_button_clicked(btn)
            assert all(m == "EventAnalysisModel" for m in received)

    def test_button_auto_unchecked(self, ec):
        ec.plot_events_pushButton.setChecked(True)
        ec.on_button_clicked("plot_events")
        assert not ec.plot_events_pushButton.isChecked()

    def test_commit_btn_auto_unchecked(self, ec):
        ec.commit_btn.setChecked(True)
        ec.on_button_clicked("commit_events")
        assert not ec.commit_btn.isChecked()

    def test_unknown_button_is_ignored(self, ec):
        # An unmapped button_type is a no-op. This used to raise AttributeError,
        # because the fallback passed to button_mapping.get() was a plain
        # function with no setChecked.
        ec.on_button_clicked("nonexistent")

    def test_parameters_included_in_signal(self, ec):
        received_params = []
        ec.actionTriggered.connect(lambda m, a, p: received_params.append(p))
        ec.on_button_clicked("plot_events")
        assert len(received_params) > 0
        assert "loader" in received_params[0][0]


# ===========================================================================
# update_channels
# ===========================================================================


class TestUpdateChannels:
    def test_first_load_selects_all(self, ec):
        ec.update_channels(["0", "1", "2"])
        selected = ec.channel_comboBox.getSelectedItems()
        assert set(selected) == {"0", "1", "2"}

    def test_restores_previous_selection(self, ec):
        ec.update_channels(["0", "1", "2"])
        # Deselect 1 and 2, keep 0
        ec.channel_comboBox.selectItem("1", select=False)
        ec.channel_comboBox.selectItem("2", select=False)
        ec.update_channels(["0", "1", "2"])
        selected = ec.channel_comboBox.getSelectedItems()
        assert "0" in selected

    def test_new_channels_cleared_on_rebuild(self, ec):
        ec.update_channels(["0", "1"])
        ec.update_channels(["2", "3"])
        items = [
            ec.channel_comboBox.listWidget.item(i).text()
            for i in range(ec.channel_comboBox.listWidget.count())
        ]
        assert "0" not in items
        assert "2" in items

    def test_integer_channels_converted_to_str(self, ec):
        ec.update_channels([0, 1, 2])
        items = [
            ec.channel_comboBox.listWidget.item(i).text()
            for i in range(ec.channel_comboBox.listWidget.count())
        ]
        assert "0" in items

    def test_single_channel(self, ec):
        ec.update_channels(["0"])
        assert ec.channel_comboBox.listWidget.count() == 1


# ===========================================================================
# update_loaders
# ===========================================================================


class TestUpdateLoaders:
    def test_populates_combobox(self, ec):
        ec.update_loaders(["ldr1", "ldr2"])
        assert ec.loaders_comboBox.count() == 2

    def test_empty_inserts_placeholder(self, ec):
        ec.update_loaders([])
        assert ec.loaders_comboBox.itemText(0) == "No Loader"

    def test_restores_previous_selection(self, ec):
        ec.update_loaders(["ldr1", "ldr2"])
        ec.loaders_comboBox.setCurrentText("ldr2")
        ec.update_loaders(["ldr1", "ldr2", "ldr3"])
        assert ec.loaders_comboBox.currentText() == "ldr2"

    def test_falls_back_to_first_when_gone(self, ec):
        ec.update_loaders(["ldr1", "ldr2"])
        ec.loaders_comboBox.setCurrentText("ldr2")
        ec.update_loaders(["ldr3"])
        assert ec.loaders_comboBox.currentIndex() == 0


# ===========================================================================
# update_filters
# ===========================================================================


class TestUpdateFilters:
    def test_populates_combobox(self, ec):
        ec.update_filters(["f1", "f2"])
        assert ec.filters_comboBox.count() == 2

    def test_empty_inserts_placeholder(self, ec):
        ec.update_filters([])
        assert ec.filters_comboBox.itemText(0) == "No Filter"

    def test_restores_previous_selection(self, ec):
        ec.update_filters(["f1", "f2"])
        ec.filters_comboBox.setCurrentText("f2")
        ec.update_filters(["f1", "f2"])
        assert ec.filters_comboBox.currentText() == "f2"

    def test_falls_back_to_first(self, ec):
        ec.update_filters(["f1"])
        ec.filters_comboBox.setCurrentText("f1")
        ec.update_filters(["f2"])
        assert ec.filters_comboBox.currentIndex() == 0


# ===========================================================================
# update_writers
# ===========================================================================


class TestUpdateWriters:
    def test_populates_combobox(self, ec):
        ec.update_writers(["w1", "w2"])
        assert ec.writers_comboBox.count() == 2

    def test_empty_inserts_placeholder(self, ec):
        ec.update_writers([])
        assert ec.writers_comboBox.itemText(0) == "No Database Writer"

    def test_restores_previous_selection(self, ec):
        ec.update_writers(["w1", "w2"])
        ec.writers_comboBox.setCurrentText("w2")
        ec.update_writers(["w1", "w2"])
        assert ec.writers_comboBox.currentText() == "w2"

    def test_falls_back_to_first(self, ec):
        ec.update_writers(["w1"])
        ec.writers_comboBox.setCurrentText("w1")
        ec.update_writers(["w2"])
        assert ec.writers_comboBox.currentIndex() == 0


# ===========================================================================
# update_eventfitters
# ===========================================================================


class TestUpdateEventFitters:
    def test_populates_combobox(self, ec):
        ec.update_eventfitters(["ef1", "ef2"])
        assert ec.eventfitters_comboBox.count() == 2

    def test_empty_inserts_placeholder(self, ec):
        ec.update_eventfitters([])
        assert ec.eventfitters_comboBox.itemText(0) == "No Event Fitter"

    def test_restores_previous_selection(self, ec):
        ec.update_eventfitters(["ef1", "ef2"])
        ec.eventfitters_comboBox.setCurrentText("ef2")
        ec.update_eventfitters(["ef1", "ef2"])
        assert ec.eventfitters_comboBox.currentText() == "ef2"

    def test_falls_back_to_first(self, ec):
        ec.update_eventfitters(["ef1"])
        ec.eventfitters_comboBox.setCurrentText("ef1")
        ec.update_eventfitters(["ef2"])
        assert ec.eventfitters_comboBox.currentIndex() == 0


# ===========================================================================
# set_event_index_input
# ===========================================================================


class TestSetEventIndexInput:
    def test_does_not_raise(self, ec):
        ec.set_event_index_input("1-5")

    def test_empty_string(self, ec):
        ec.set_event_index_input("")

    def test_single_value(self, ec):
        ec.set_event_index_input("3")
