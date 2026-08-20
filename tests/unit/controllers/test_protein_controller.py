"""
Tests for poriscope.plugins.analysistabs.ProteinController.

Covers:
- _init creates view and model
- _setup_connections is a no-op (satisfies abstract base class requirement)
- alter_database_status delegation
- relay_table_by_column delegation
- relay_baseline_duration delegation
- set_exported_event_count delegation
- relay_query (plain relay, empty-query warning dialog, validate_new_filter
  and validate_edited_filter intents, with and without filter text)
- relay_event_query (query present, debug-only path)
- relay_event_data_generator delegation
- relay_event_plot_data_generator delegation
- relay_plot_data delegation
- relay_units delegation
- update_column_names (names provided with info log, empty list with warning log)
- update_column_units delegation
- get_experiment_names_for_tree delegation
- get_experiment_structure_ready (stores str-cast structure for available/selected)
- set_experiment_id delegation
- set_channel_db_id delegation
- on_raw_filter_validated delegation
- relay_query_result delegation
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ProteinController import ProteinController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked ProteinView with the attributes/methods ProteinController touches.

    :param mocker: Pytest-mock fixture.
    :return: Mocked protein view.
    """
    view: MagicMock = mocker.Mock()
    view.subset_filters = {}
    view.add_text_to_display = mocker.Mock()
    view.add_text_to_display.emit = mocker.Mock()
    view.available_experiment_and_channels_by_loader = {}
    view.selected_experiment_and_channels_by_loader = {}
    view._pending_filter_name = None
    view._pending_filter_text = None
    view._pending_old_filter_name = None
    return view


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> ProteinController:
    """
    Construct a ProteinController with view, model, and signals replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked protein view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: ProteinController = ProteinController.__new__(ProteinController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.add_text_to_display = mocker.Mock()
    ctrl.add_text_to_display.emit = mocker.Mock()
    ctrl.global_signal = mocker.Mock()
    ctrl.global_signal.emit = mocker.Mock()
    ctrl.update_available_plugins = mocker.Mock()
    ctrl.update_available_plugins.emit = mocker.Mock()
    return ctrl


# ----------------------- _init / _setup_connections -------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates ProteinView and ProteinModel on the controller.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ProteinController.ProteinView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ProteinController.ProteinModel"
    )

    ctrl: ProteinController = ProteinController.__new__(ProteinController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_is_noop(controller: ProteinController) -> None:
    """
    Verify that _setup_connections runs without wiring any view signals.

    There is currently no view-side signal for ProteinController to connect to;
    the method exists only to satisfy MetaController's abstract interface.

    :param controller: Controller under test.
    """
    # Should not raise, and should not touch view/global_signal.
    controller._setup_connections()
    controller.global_signal.emit.assert_not_called()


# ------------------- alter_database_status ---------------------------


def test_alter_database_status_delegates_to_view(
    controller: ProteinController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the alteration status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.alter_database_status(True)
    mock_view.set_alter_database_status.assert_called_once_with(True)


def test_alter_database_status_delegates_false_to_view(
    controller: ProteinController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a False alteration status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.alter_database_status(False)
    mock_view.set_alter_database_status.assert_called_once_with(False)


# ----------------------- relay_table_by_column -------------------------


def test_relay_table_by_column_delegates_to_view(
    controller: ProteinController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a column-grouped table dict to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    table = {"col_a": ["events"], "col_b": ["events"]}
    controller.relay_table_by_column(table)
    mock_view.set_table_by_column.assert_called_once_with(table)


# ----------------------- relay_baseline_duration -----------------------


def test_relay_baseline_duration_delegates_to_view(
    controller: ProteinController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the computed baseline duration to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.relay_baseline_duration(123.45)
    mock_view.set_baseline_duration.assert_called_once_with(123.45)


# ----------------------- set_exported_event_count -----------------------


def test_set_exported_event_count_delegates_to_view(
    controller: ProteinController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the number of exported events to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.set_exported_event_count(42)
    mock_view.set_exported_event_count.assert_called_once_with(42)


# ------------------------- relay_query ---------------------------------


class TestRelayQuery:
    def test_plain_relay_sets_query_on_view(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Forward a valid query and table name to the view with no intent.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.relay_query("SELECT * FROM events", "", "events")
        mock_view.set_query.assert_called_once_with("SELECT * FROM events", "events")

    def test_empty_query_with_debug_shows_warning_and_returns(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Show a warning dialog and skip set_query when the query is empty and a
        debug message is present.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        with patch(
            "poriscope.plugins.analysistabs.ProteinController.QMessageBox"
        ) as mock_box:
            controller.relay_query("", "bad filter syntax", "events")
        mock_box.warning.assert_called_once()
        mock_view.set_query.assert_not_called()

    def test_empty_query_with_new_filter_intent_clears_pending_state(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Clear pending filter state when validation fails for a new filter.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        with patch("poriscope.plugins.analysistabs.ProteinController.QMessageBox"):
            controller.relay_query(
                "", "bad filter syntax", "events", "validate_new_filter"
            )
        mock_view.clear_pending_filter_state.assert_called_once()

    def test_empty_query_with_edited_filter_intent_clears_pending_state(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Clear pending filter state when validation fails for an edited filter.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        with patch("poriscope.plugins.analysistabs.ProteinController.QMessageBox"):
            controller.relay_query(
                "", "bad filter syntax", "events", "validate_edited_filter"
            )
        mock_view.clear_pending_filter_state.assert_called_once()

    def test_validate_new_filter_adds_suffixed_filter(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Add a new filter under an "_assisted"-suffixed name and select it in the view.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view._pending_filter_name = "myfilter"
        mock_view._pending_filter_text = "duration > 100"

        controller.relay_query(
            "SELECT duration FROM events WHERE duration > 100",
            "",
            "events",
            "validate_new_filter",
        )

        assert mock_view.subset_filters["myfilter_assisted"] == "duration > 100"
        mock_view.replace_filter_item.assert_called_once_with("myfilter_assisted")
        mock_view.clear_pending_filter_state.assert_called_once()

    def test_validate_new_filter_does_not_double_suffix(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Do not append a second "_assisted" suffix if the name already has one.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view._pending_filter_name = "myfilter_assisted"
        mock_view._pending_filter_text = "duration > 100"

        controller.relay_query(
            "SELECT duration FROM events WHERE duration > 100",
            "",
            "events",
            "validate_new_filter",
        )

        assert "myfilter_assisted" in mock_view.subset_filters
        assert "myfilter_assisted_assisted" not in mock_view.subset_filters

    def test_validate_new_filter_empty_text_emits_full_dataset_notice(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Emit an informational message when the new filter has no WHERE clause.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view._pending_filter_name = "allrows"
        mock_view._pending_filter_text = ""

        controller.relay_query(
            "SELECT duration FROM events", "", "events", "validate_new_filter"
        )

        messages = [
            call.args[0] for call in mock_view.add_text_to_display.emit.call_args_list
        ]
        assert any("uses all rows" in m for m in messages)

    def test_validate_new_filter_no_pending_name_skips_add(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Do nothing filter-related when no pending filter name is set.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view._pending_filter_name = None

        controller.relay_query(
            "SELECT duration FROM events", "", "events", "validate_new_filter"
        )

        mock_view.replace_filter_item.assert_not_called()
        mock_view.clear_pending_filter_state.assert_called_once()

    def test_validate_edited_filter_renames_filter(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Replace the old filter name with the new suffixed name and update the view.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view.subset_filters = {"oldname": "duration > 50"}
        mock_view._pending_old_filter_name = "oldname"
        mock_view._pending_filter_name = "newname"
        mock_view._pending_filter_text = "duration > 200"

        controller.relay_query(
            "SELECT duration FROM events WHERE duration > 200",
            "",
            "events",
            "validate_edited_filter",
        )

        assert "oldname" not in mock_view.subset_filters
        assert mock_view.subset_filters["newname_assisted"] == "duration > 200"
        mock_view.update_filter_name.assert_called_once_with(
            "oldname", "newname_assisted"
        )

    def test_validate_edited_filter_empty_text_emits_full_dataset_notice(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Emit an informational message when the edited filter has no WHERE clause.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view.subset_filters = {"oldname": "duration > 50"}
        mock_view._pending_old_filter_name = "oldname"
        mock_view._pending_filter_name = "newname"
        mock_view._pending_filter_text = ""

        controller.relay_query(
            "SELECT duration FROM events", "", "events", "validate_edited_filter"
        )

        messages = [
            call.args[0] for call in mock_view.add_text_to_display.emit.call_args_list
        ]
        assert any("FULL DATASET" in m for m in messages)

    def test_validate_edited_filter_no_pending_new_name_skips_rename(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Do nothing filter-related when no pending new filter name is set.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        mock_view._pending_filter_name = None

        controller.relay_query(
            "SELECT duration FROM events", "", "events", "validate_edited_filter"
        )

        mock_view.update_filter_name.assert_not_called()
        mock_view.clear_pending_filter_state.assert_called_once()

    def test_no_intent_still_clears_pending_state(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Clear pending filter state even when no intent arg is passed.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.relay_query("SELECT * FROM events", "", "events")
        mock_view.clear_pending_filter_state.assert_called_once()


# ----------------------- relay_event_query ------------------------------


def test_relay_event_query_forwards_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a valid event query to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.relay_event_query("SELECT * FROM events", "")
    mock_view.set_event_query.assert_called_once_with("SELECT * FROM events")


def test_relay_event_query_emits_debug_when_empty(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Emit a debug message via add_text_to_display when the event query is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.relay_event_query("", "no events found")
    controller.add_text_to_display.emit.assert_called_once_with(
        "no events found", "ProteinController"
    )
    mock_view.set_event_query.assert_called_once_with("")


# ----------------- relay_event_data_generator ----------------------------


def test_relay_event_data_generator_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward an event data generator to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    gen = iter([{"id": 1}])
    controller.relay_event_data_generator(gen)
    mock_view.set_event_data_generator.assert_called_once_with(gen)


# --------------- relay_event_plot_data_generator --------------------------


def test_relay_event_plot_data_generator_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward an event plot data generator to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    gen = iter([{"id": 1}])
    controller.relay_event_plot_data_generator(gen)
    mock_view.set_event_plot_data_generator.assert_called_once_with(gen)


# ----------------------- relay_plot_data -----------------------------


def test_relay_plot_data_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward structured plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    data = {"x": [1, 2], "y": [3, 4]}
    controller.relay_plot_data(data)
    mock_view.set_plot_data.assert_called_once_with(data)


# ------------------------- relay_units -------------------------------


def test_relay_units_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a column-to-unit mapping to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    units = {"volume": "nm^3"}
    controller.relay_units(units)
    mock_view.set_units.assert_called_once_with(units)


# -------------------- update_column_names ----------------------------


def test_update_column_names_updates_view_when_names_provided(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a non-empty list of column names to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.update_column_names(["col_a", "col_b"])
    mock_view.update_column_names.assert_called_once_with(["col_a", "col_b"])


def test_update_column_names_logs_info_when_names_provided(
    controller: ProteinController,
) -> None:
    """
    Log an info message after successfully updating the view with column names.

    :param controller: Controller under test.
    """
    controller.update_column_names(["col_a", "col_b"])
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_names_skips_view_when_list_is_empty(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Do not call update_column_names on the view when the list is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.update_column_names([])
    mock_view.update_column_names.assert_not_called()


def test_update_column_names_logs_warning_when_list_is_empty(
    controller: ProteinController,
) -> None:
    """
    Log a warning message when no column names are received.

    :param controller: Controller under test.
    """
    controller.update_column_names([])
    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]


# -------------------- update_column_units ----------------------------


def test_update_column_units_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a units dict and axis identifier to the view unconditionally.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.update_column_units({"volume": "nm^3"}, "x")
    mock_view.update_column_units.assert_called_once_with({"volume": "nm^3"}, "x")


def test_update_column_units_delegates_even_when_empty(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    ProteinController forwards update_column_units unconditionally, unlike
    ClusteringController which guards on a truthy dict.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.update_column_units({}, "y")
    mock_view.update_column_units.assert_called_once_with({}, "y")


# ----------------- get_experiment_names_for_tree -------------------------


def test_get_experiment_names_for_tree_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward experiment names and loader name to the view for tree display.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.get_experiment_names_for_tree(["exp1", "exp2"], "ldr")
    mock_view.get_experiment_names_for_tree.assert_called_once_with(
        ["exp1", "exp2"], "ldr"
    )


# ----------------- get_experiment_structure_ready -------------------------


class TestGetExperimentStructureReady:
    def test_stores_str_cast_structure_in_available(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Store the experiment/channel structure (channels cast to str) keyed by loader.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.get_experiment_structure_ready({"exp1": [0, 1]}, "ldr")
        assert mock_view.available_experiment_and_channels_by_loader["ldr"] == {
            "exp1": ["0", "1"]
        }

    def test_stores_str_cast_structure_in_selected(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Store a copy of the structure as the default selection for that loader.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.get_experiment_structure_ready({"exp1": [0, 1]}, "ldr")
        assert mock_view.selected_experiment_and_channels_by_loader["ldr"] == {
            "exp1": ["0", "1"]
        }

    def test_selected_is_shallow_copy_shares_inner_lists(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        NOTE: str_structure.copy() is a shallow copy — the outer dict is copied,
        but inner channel lists are shared between available_ and
        selected_experiment_and_channels_by_loader. Mutating a channel list via
        one reference is visible through the other. This documents current
        behavior rather than asserting it's necessarily desirable.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.get_experiment_structure_ready({"exp1": [0]}, "ldr")
        mock_view.selected_experiment_and_channels_by_loader["ldr"]["exp1"].append("1")
        assert mock_view.available_experiment_and_channels_by_loader["ldr"][
            "exp1"
        ] == ["0", "1"]

    def test_selected_and_available_are_separate_dict_objects(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        The outer dicts themselves are distinct objects (reassigning a key in
        one does not affect the other), even though inner lists are shared.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.get_experiment_structure_ready({"exp1": [0]}, "ldr")
        assert (
            mock_view.selected_experiment_and_channels_by_loader["ldr"]
            is not mock_view.available_experiment_and_channels_by_loader["ldr"]
        )
        
    def test_empty_structure(
        self, controller: ProteinController, mock_view: MagicMock
    ) -> None:
        """
        Handle an empty structure dict without error.

        :param controller: Controller under test.
        :param mock_view: Mocked protein view.
        """
        controller.get_experiment_structure_ready({}, "ldr")
        assert mock_view.available_experiment_and_channels_by_loader["ldr"] == {}
        assert mock_view.selected_experiment_and_channels_by_loader["ldr"] == {}


# ------------------------- set_experiment_id -------------------------------


def test_set_experiment_id_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward the experiment id to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.set_experiment_id(7)
    mock_view.set_experiment_id.assert_called_once_with(7)


def test_set_experiment_id_delegates_none(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a None experiment id to the view (e.g. lookup failure).

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.set_experiment_id(None)
    mock_view.set_experiment_id.assert_called_once_with(None)


# ------------------------- set_channel_db_id -------------------------------


def test_set_channel_db_id_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward the channel database id to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.set_channel_db_id(3)
    mock_view.set_channel_db_id.assert_called_once_with(3)


# ----------------------- on_raw_filter_validated ----------------------------


def test_on_raw_filter_validated_valid_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a successful raw filter validation result to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.on_raw_filter_validated(True, "")
    mock_view.on_raw_filter_validated.assert_called_once_with(True, "")


def test_on_raw_filter_validated_invalid_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a failed raw filter validation result, including the error message,
    to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    controller.on_raw_filter_validated(False, "syntax error near WHERE")
    mock_view.on_raw_filter_validated.assert_called_once_with(
        False, "syntax error near WHERE"
    )


# ------------------------- relay_query_result -------------------------------


def test_relay_query_result_delegates_to_view(
    controller: ProteinController, mock_view: MagicMock
) -> None:
    """
    Forward a direct database query result DataFrame to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked protein view.
    """
    df = pd.DataFrame({"event_id": [1, 2, 3]})
    controller.relay_query_result(df)
    mock_view.relay_query_result.assert_called_once()
    pd.testing.assert_frame_equal(
        mock_view.relay_query_result.call_args[0][0], df
    )