"""
Unit-test suite for ProteinController.

Uses:
  - A session-scoped QApplication fixture
  - A per-test ProteinController() fixture (real view/model, as built by _init)
  - global_signal and view.add_text_to_display mocked/observed per-test where relevant

Run with:
    pytest test_protein_controller.py -v
    pytest test_protein_controller.py --cov=poriscope --cov-report=html
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView

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
def controller(qt_app):
    """
    Real ProteinController, built via the real _init() (so self.view is a real
    ProteinView and self.model is a real ProteinModel, exactly as in the running
    application). global_signal is replaced with a MagicMock so we can assert on
    emitted calls without a live event bus.
    """
    c = ProteinController()
    c.global_signal = MagicMock()
    return c


# ===========================================================================
# Construction
# ===========================================================================


class TestInit:
    def test_creates_real_view(self, controller):
        assert isinstance(controller.view, ProteinView)

    def test_creates_real_model(self, controller):
        assert isinstance(controller.model, ProteinModel)


class TestSetupConnections:
    def test_request_plugin_refresh_routes_to_refresh_plugin_list(self, controller):
        with patch.object(controller, "refresh_plugin_list") as mock:
            controller.view.request_plugin_refresh.emit("ldr1")
        mock.assert_called_once_with("ldr1")


# ===========================================================================
# refresh_plugin_list
# ===========================================================================


class TestRefreshPluginList:
    def test_emits_list_plugins_with_loader(self, controller):
        controller.refresh_plugin_list("ldr1")
        controller.global_signal.emit.assert_called_once_with(
            "MetaDatabaseLoader", "ldr1", "list_plugins", (), "update_plugins", ()
        )

    def test_no_loader_does_not_emit(self, controller):
        controller.refresh_plugin_list(None)
        controller.global_signal.emit.assert_not_called()

    def test_empty_string_loader_does_not_emit(self, controller):
        controller.refresh_plugin_list("")
        controller.global_signal.emit.assert_not_called()


# ===========================================================================
# alter_database_status
# ===========================================================================


class TestAlterDatabaseStatus:
    def test_forwards_true_to_view(self, controller):
        controller.alter_database_status(True)
        assert controller.view.operation_success is True

    def test_forwards_false_to_view(self, controller):
        controller.alter_database_status(False)
        assert controller.view.operation_success is False


# ===========================================================================
# update_plugins
# ===========================================================================


class TestUpdatePlugins:
    def test_emits_update_available_plugins(self, controller):
        controller.update_available_plugins = MagicMock()
        controller.update_plugins(["ldr1", "ldr2"])
        controller.update_available_plugins.emit.assert_called_once_with(
            "MetaDatabaseLoader", ["ldr1", "ldr2"]
        )


# ===========================================================================
# relay_table_by_column
# ===========================================================================


class TestRelayTableByColumn:
    def test_forwards_table_to_view(self, controller):
        controller.view.involved_tables = []
        controller.relay_table_by_column("events")
        assert "events" in controller.view.involved_tables

    def test_forwards_none_ignored_by_view(self, controller):
        controller.view.involved_tables = []
        controller.relay_table_by_column(None)
        assert controller.view.involved_tables == []


# ===========================================================================
# relay_baseline_duration
# ===========================================================================


class TestRelayBaselineDuration:
    def test_forwards_duration_to_view(self, controller):
        controller.relay_baseline_duration(500)
        assert controller.view.baseline_duration == 500


# ===========================================================================
# relay_query — the big dispatch method
# ===========================================================================


class TestRelayQuery:
    def test_debug_no_query_shows_warning_dialog(self, controller):
        with patch(
            "poriscope.plugins.analysistabs.ProteinController.QMessageBox.warning"
        ) as mock_warn:
            controller.relay_query("", "syntax error here", "events")
        mock_warn.assert_called_once()
        args = mock_warn.call_args[0]
        assert args[0] is controller.view
        assert "syntax error here" in args[2]

    def test_debug_no_query_clears_pending_for_new_filter(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 5"
        controller.view._pending_old_filter_name = None
        with patch(
            "poriscope.plugins.analysistabs.ProteinController.QMessageBox.warning"
        ):
            controller.relay_query("", "bad syntax", "events", "validate_new_filter")
        assert controller.view._pending_filter_name is None
        assert controller.view._pending_filter_text is None

    def test_debug_no_query_clears_pending_for_edited_filter(self, controller):
        controller.view._pending_filter_name = "f2"
        controller.view._pending_filter_text = "dur > 10"
        controller.view._pending_old_filter_name = "f1"
        with patch(
            "poriscope.plugins.analysistabs.ProteinController.QMessageBox.warning"
        ):
            controller.relay_query("", "bad syntax", "events", "validate_edited_filter")
        assert controller.view._pending_old_filter_name is None

    def test_debug_no_query_no_intent_leaves_pending_untouched(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 5"
        controller.view._pending_old_filter_name = None
        with patch(
            "poriscope.plugins.analysistabs.ProteinController.QMessageBox.warning"
        ):
            controller.relay_query("", "bad syntax", "events")
        # no intent arg supplied -> early return before clear_pending_filter_state,
        # so pending state should be untouched
        assert controller.view._pending_filter_name == "f1"

    def test_valid_query_sets_view_query(self, controller):
        controller.relay_query("SELECT * FROM events", "", "events")
        assert controller.view.query == "SELECT * FROM events"
        assert controller.view.table_name == "events"

    def test_new_filter_added_with_assisted_suffix(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 100"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
        )
        assert "f1_assisted" in controller.view.subset_filters
        assert controller.view.subset_filters["f1_assisted"] == "dur > 100"

    def test_new_filter_does_not_double_suffix(self, controller):
        controller.view._pending_filter_name = "f1_assisted"
        controller.view._pending_filter_text = "dur > 100"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
        )
        assert "f1_assisted" in controller.view.subset_filters
        assert "f1_assisted_assisted" not in controller.view.subset_filters

    def test_new_filter_empty_text_emits_full_dataset_message(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = ""
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query("SELECT dur FROM events", "", "events", "validate_new_filter")
        assert any("no WHERE clause" in m for m in received)

    def test_new_filter_emits_added_message(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 100"
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
        )
        assert any("added" in m for m in received)

    def test_new_filter_calls_replace_filter_item(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 100"
        with patch.object(controller.view, "replace_filter_item") as mock_replace:
            controller.relay_query(
                "SELECT dur FROM events WHERE dur > 100",
                "",
                "events",
                "validate_new_filter",
            )
        mock_replace.assert_called_once_with("f1_assisted")

    def test_new_filter_none_name_skips_add(self, controller):
        controller.view._pending_filter_name = None
        controller.view._pending_filter_text = "dur > 100"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
        )
        assert controller.view.subset_filters == {}

    def test_edited_filter_removes_old_adds_new(self, controller):
        controller.view.subset_filters["old_assisted"] = "dur > 1"
        controller.view._pending_old_filter_name = "old_assisted"
        controller.view._pending_filter_name = "new"
        controller.view._pending_filter_text = "dur > 200"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
        )
        assert "old_assisted" not in controller.view.subset_filters
        assert "new_assisted" in controller.view.subset_filters
        assert controller.view.subset_filters["new_assisted"] == "dur > 200"

    def test_edited_filter_no_old_name_only_adds_new(self, controller):
        controller.view._pending_old_filter_name = None
        controller.view._pending_filter_name = "new"
        controller.view._pending_filter_text = "dur > 200"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
        )
        assert "new_assisted" in controller.view.subset_filters

    def test_edited_filter_empty_text_emits_full_dataset_message(self, controller):
        controller.view._pending_old_filter_name = "old"
        controller.view._pending_filter_name = "new"
        controller.view._pending_filter_text = ""
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events", "", "events", "validate_edited_filter"
        )
        assert any("FULL DATASET" in m for m in received)

    def test_edited_filter_emits_updated_message(self, controller):
        controller.view._pending_old_filter_name = "old"
        controller.view._pending_filter_name = "new"
        controller.view._pending_filter_text = "dur > 200"
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
        )
        assert any("updated" in m for m in received)

    def test_edited_filter_calls_update_filter_name(self, controller):
        controller.view._pending_old_filter_name = "old"
        controller.view._pending_filter_name = "new"
        controller.view._pending_filter_text = "dur > 200"
        with patch.object(controller.view, "update_filter_name") as mock_update:
            controller.relay_query(
                "SELECT dur FROM events WHERE dur > 200",
                "",
                "events",
                "validate_edited_filter",
            )
        mock_update.assert_called_once_with("old", "new_assisted")

    def test_edited_filter_none_name_skips_update(self, controller):
        controller.view.subset_filters["old"] = "dur > 1"
        controller.view._pending_old_filter_name = "old"
        controller.view._pending_filter_name = None
        controller.view._pending_filter_text = "dur > 200"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
        )
        # old filter should remain untouched since new_name is None
        assert controller.view.subset_filters.get("old") == "dur > 1"

    def test_unknown_intent_still_clears_pending(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 5"
        controller.view._pending_old_filter_name = None
        controller.relay_query(
            "SELECT dur FROM events", "", "events", "some_other_intent"
        )
        assert controller.view._pending_filter_name is None
        assert controller.view._pending_filter_text is None
        assert controller.view._pending_old_filter_name is None

    def test_no_intent_still_clears_pending_on_valid_query(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "dur > 5"
        controller.relay_query("SELECT dur FROM events", "", "events")
        assert controller.view._pending_filter_name is None


# ===========================================================================
# relay_event_query
# ===========================================================================


class TestRelayEventQuery:
    def test_valid_query_sets_view_event_query(self, controller):
        controller.relay_event_query("SELECT * FROM events", "")
        assert controller.view.event_query == "SELECT * FROM events"

    def test_debug_no_query_emits_debug_message(self, controller):
        controller.add_text_to_display = MagicMock()
        controller.relay_event_query("", "no events matched")
        controller.add_text_to_display.emit.assert_called_once_with(
            "no events matched", controller.__class__.__name__
        )

    def test_valid_query_no_debug_message_emitted(self, controller):
        controller.add_text_to_display = MagicMock()
        controller.relay_event_query("SELECT * FROM events", "")
        controller.add_text_to_display.emit.assert_not_called()


# ===========================================================================
# relay_event_data_generator / relay_event_plot_data_generator
# ===========================================================================


class TestRelayGenerators:
    def test_relay_event_data_generator_sets_view_generator(self, controller):
        g = iter([1, 2, 3])
        controller.relay_event_data_generator(g)
        assert controller.view.event_data_generator is g

    def test_relay_event_plot_data_generator_sets_view_generator(self, controller):
        g = iter([])
        controller.relay_event_plot_data_generator(g)
        assert controller.view.plot_events_generator is g
        assert controller.view.plot_events_generator_updated is True


# ===========================================================================
# relay_units
# ===========================================================================


class TestRelayUnits:
    def test_forwards_units_to_view(self, controller):
        controller.relay_units("nm")
        assert controller.view.units == "nm"


# ===========================================================================
# update_column_names
# ===========================================================================


class TestUpdateColumnNames:
    def test_nonempty_list_updates_view(self, controller):
        controller.update_column_names(["a", "b", "c"])
        assert controller.view.available_columns == ["a", "b", "c"]

    def test_empty_list_does_not_update_view(self, controller):
        controller.view.available_columns = ["existing"]
        controller.update_column_names([])
        assert controller.view.available_columns == ["existing"]

    def test_none_does_not_update_view(self, controller):
        controller.view.available_columns = ["existing"]
        controller.update_column_names(None)
        assert controller.view.available_columns == ["existing"]


# ===========================================================================
# get_experiment_structure_ready
# ===========================================================================


class TestGetExperimentStructureReady:
    def test_stringifies_channels_in_available_structure(self, controller):
        controller.get_experiment_structure_ready({"exp1": [0, 1, 2]}, "ldr1")
        assert controller.view.available_experiment_and_channels_by_loader["ldr1"] == {
            "exp1": ["0", "1", "2"]
        }

    def test_populates_selected_as_copy_of_available(self, controller):
        controller.get_experiment_structure_ready({"exp1": [0]}, "ldr1")
        available = controller.view.available_experiment_and_channels_by_loader["ldr1"]
        selected = controller.view.selected_experiment_and_channels_by_loader["ldr1"]
        assert available == selected
        assert available is not selected  # must be a copy, not the same dict

    def test_multiple_experiments(self, controller):
        controller.get_experiment_structure_ready(
            {"exp1": [0, 1], "exp2": [0]}, "ldr1"
        )
        result = controller.view.available_experiment_and_channels_by_loader["ldr1"]
        assert result == {"exp1": ["0", "1"], "exp2": ["0"]}

    def test_empty_structure(self, controller):
        controller.get_experiment_structure_ready({}, "ldr1")
        assert controller.view.available_experiment_and_channels_by_loader["ldr1"] == {}

    def test_multiple_loaders_independent(self, controller):
        controller.get_experiment_structure_ready({"exp1": [0]}, "ldrA")
        controller.get_experiment_structure_ready({"exp2": [1]}, "ldrB")
        assert "ldrA" in controller.view.available_experiment_and_channels_by_loader
        assert "ldrB" in controller.view.available_experiment_and_channels_by_loader
        assert controller.view.available_experiment_and_channels_by_loader[
            "ldrA"
        ] != controller.view.available_experiment_and_channels_by_loader["ldrB"]


# ===========================================================================
# set_experiment_id / set_channel_db_id
# ===========================================================================


class TestSetExperimentAndChannelIds:
    def test_set_experiment_id_forwards_to_view(self, controller):
        controller.set_experiment_id(42)
        assert controller.view.experiment_id == 42

    def test_set_experiment_id_none_forwards_none(self, controller):
        controller.set_experiment_id(None)
        assert controller.view.experiment_id is None

    def test_set_channel_db_id_forwards_to_view(self, controller):
        controller.set_channel_db_id(7)
        assert controller.view.channel_db_id == 7


# ===========================================================================
# on_raw_filter_validated
# ===========================================================================


class TestOnRawFilterValidated:
    def test_invalid_forwards_to_view(self, controller):
        controller.view._pending_filter_name = "f1"
        controller.view._pending_filter_text = "SELECT * FROM events"
        controller.view._pending_old_filter_name = None
        controller.on_raw_filter_validated(False, "bad syntax")
        assert controller.view._pending_filter_name is None

    def test_valid_add_path_forwards_to_view(self, controller):
        controller.view._pending_filter_name = "f1_raw"
        controller.view._pending_filter_text = "SELECT * FROM events"
        controller.view._pending_old_filter_name = None
        controller.on_raw_filter_validated(True, "")
        assert "f1_raw" in controller.view.subset_filters

    def test_valid_edit_path_forwards_to_view(self, controller):
        controller.view.subset_filters["old_raw"] = "SELECT * FROM events"
        controller.view.proteincontrols.filter_comboBox.addItem("old_raw")
        controller.view._pending_filter_name = "new_raw"
        controller.view._pending_filter_text = "SELECT dur FROM events"
        controller.view._pending_old_filter_name = "old_raw"
        controller.on_raw_filter_validated(True, "")
        assert "old_raw" not in controller.view.subset_filters
        assert "new_raw" in controller.view.subset_filters


# ===========================================================================
# relay_query_result
# ===========================================================================


class TestRelayQueryResult:
    def test_forwards_dataframe_to_view(self, controller):
        df = pd.DataFrame({"event_id": [1, 2, 3]})
        controller.relay_query_result(df)
        assert controller.view.relayed_query_result is df

    def test_forwards_none_to_view(self, controller):
        controller.relay_query_result(None)
        assert controller.view.relayed_query_result is None