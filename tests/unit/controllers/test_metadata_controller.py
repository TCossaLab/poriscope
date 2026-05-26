"""
Tests for poriscope.plugins.analysistabs.MetadataController.

Covers:
- _init creates view and model
- _setup_connections wires signals
- relay_table_by_column delegation
- relay_baseline_duration delegation
- set_exported_event_count delegation
- relay_event_query (query present, query empty with debug)
- relay_event_data_generator delegation
- relay_event_plot_data_generator delegation
- relay_plot_data delegation
- relay_units delegation
- update_column_names (names provided, empty list)
- update_column_units delegation
- get_experiment_names_for_tree delegation
- get_experiment_structure_ready (conversion, copy behaviour, multi-experiment)
- relay_query debug path, happy path, validate_new_filter, validate_edited_filter
"""

from __future__ import annotations

from typing import Dict, Iterator, List
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked MetadataView with Qt-like signals and state used by the controller.

    :param mocker: Pytest-mock fixture.
    :return: Mocked metadata view.
    """
    view: MagicMock = mocker.Mock()

    # Qt signal used inside relay_query
    view.add_text_to_display = mocker.Mock()
    view.add_text_to_display.emit = mocker.Mock()

    # State attributes read directly by relay_query
    view.subset_filters = {}  # type: ignore[misc]
    view._pending_filter_name = None  # type: ignore[misc]
    view._pending_filter_text = None  # type: ignore[misc]
    view._pending_old_filter_name = None  # type: ignore[misc]

    # Dicts populated by get_experiment_structure_ready
    view.available_experiment_and_channels_by_loader = {}  # type: ignore[misc]
    view.selected_experiment_and_channels_by_loader = {}  # type: ignore[misc]

    return view


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> MetadataController:
    """
    Construct a MetadataController with view, model, and logger replaced by mocks.

    Uses ``MetadataController.__new__`` to bypass ``__init__`` so no real Qt objects are created.
    The class-level ``logger`` is patched on the instance so log calls are
    traceable by the coverage tool and assertable in tests.

    :param mock_view: Mocked metadata view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: MetadataController = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataController.QMessageBox.warning"
    )
    return ctrl


# ----------------------- _init / _setup_connections -----------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates MetadataView and MetadataModel on the controller.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataController.MetadataView"
    )
    mock_model_cls: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataController.MetadataModel"
    )

    ctrl: MetadataController = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_runs_without_error(mocker: MockerFixture) -> None:
    """
    Verify that _setup_connections completes without raising.

    The method is intentionally empty (satisfies the abstract base class)
    so the only requirement is that it does not raise.

    :param mocker: Pytest-mock fixture.
    """
    ctrl: MetadataController = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.model = mocker.Mock()
    ctrl._setup_connections()  # should not raise


# ----------------------- relay_table_by_column -----------------------


def test_relay_table_by_column_passes_table_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Delegate a column-grouped table dict to the view unchanged.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    table: Dict[str, List[int]] = {"col_a": [1, 2], "col_b": [3, 4]}
    controller.relay_table_by_column(table)
    mock_view.set_table_by_column.assert_called_once_with(table)


# ---------------------- relay_baseline_duration ----------------------


def test_relay_baseline_duration_passes_value_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Delegate a non-zero baseline duration to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_baseline_duration(9.81)
    mock_view.set_baseline_duration.assert_called_once_with(9.81)


def test_relay_baseline_duration_passes_zero_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Delegate a zero baseline duration to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_baseline_duration(0.0)
    mock_view.set_baseline_duration.assert_called_once_with(0.0)


# -------------------- set_exported_event_count -----------------------


def test_set_exported_event_count_passes_count_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Delegate a positive exported event count to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.set_exported_event_count(42)
    mock_view.set_exported_event_count.assert_called_once_with(42)


def test_set_exported_event_count_passes_zero_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Delegate a zero exported event count to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.set_exported_event_count(0)
    mock_view.set_exported_event_count.assert_called_once_with(0)


# ----------------------- relay_event_query ---------------------------


def test_relay_event_query_sets_query_when_query_provided(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty event query to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_event_query("SELECT * FROM events", "")
    mock_view.set_event_query.assert_called_once_with("SELECT * FROM events")


def test_relay_event_query_calls_set_event_query_even_when_empty(
    controller: MetadataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Call set_event_query unconditionally even when the query is empty.

    The debug-message emit branch fires separately; set_event_query is
    still always invoked.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    :param mocker: Pytest-mock fixture.
    """
    controller.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    controller.add_text_to_display.emit = mocker.Mock()  # type: ignore[attr-defined,method-assign]
    controller.relay_event_query("", "debug message")
    mock_view.set_event_query.assert_called_once_with("")


# ------------------ relay_event_data_generator -----------------------


def test_relay_event_data_generator_passes_generator_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward an event data generator to the view for overlay use.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    gen: Iterator[Dict[str, int]] = iter([{"id": 1}, {"id": 2}])
    controller.relay_event_data_generator(gen)
    mock_view.set_event_data_generator.assert_called_once_with(gen)


# ---------------- relay_event_plot_data_generator --------------------


def test_relay_event_plot_data_generator_passes_generator_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward an event plot data generator to the view for plotting.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    gen: Iterator[float] = iter([1.0, 2.0, 3.0])
    controller.relay_event_plot_data_generator(gen)
    mock_view.set_event_plot_data_generator.assert_called_once_with(gen)


# ------------------------ relay_plot_data ----------------------------


def test_relay_plot_data_passes_data_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward structured plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    data: Dict[str, List[float]] = {"x": [0.1, 0.2], "y": [1.0, 2.0]}
    controller.relay_plot_data(data)
    mock_view.set_plot_data.assert_called_once_with(data)


# ------------------------- relay_units -------------------------------


def test_relay_units_passes_units_dict_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a column-to-unit mapping to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    units: Dict[str, str] = {"current": "pA", "time": "s"}
    controller.relay_units(units)
    mock_view.set_units.assert_called_once_with(units)


# ---------------------- update_column_names --------------------------


def test_update_column_names_updates_view_when_names_provided(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty list of column names to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.update_column_names(["col_a", "col_b"])
    mock_view.update_column_names.assert_called_once_with(["col_a", "col_b"])


def test_update_column_names_logs_info_when_names_provided(
    controller: MetadataController,
) -> None:
    """
    Log an info message after successfully updating the view with column names.

    :param controller: Controller under test.
    """
    controller.update_column_names(["col_a", "col_b"])
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_names_skips_view_when_list_is_empty(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Do not call update_column_names on the view when the list is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.update_column_names([])
    mock_view.update_column_names.assert_not_called()


def test_update_column_names_logs_warning_when_list_is_empty(
    controller: MetadataController,
) -> None:
    """
    Log a warning message when no column names are received.

    :param controller: Controller under test.
    """
    controller.update_column_names([])
    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]


# ---------------------- update_column_units --------------------------


def test_update_column_units_passes_units_and_y_axis_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward unit labels and axis identifier 'y' to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.update_column_units({"voltage": "mV"}, "y")
    mock_view.update_column_units.assert_called_once_with({"voltage": "mV"}, "y")


def test_update_column_units_passes_units_and_x_axis_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward unit labels and axis identifier 'x' to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.update_column_units({"time": "ms"}, "x")
    mock_view.update_column_units.assert_called_once_with({"time": "ms"}, "x")


# ------------------ get_experiment_names_for_tree --------------------


def test_get_experiment_names_for_tree_forwards_to_view(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward experiment names and loader name to the view tree display.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_names_for_tree(["exp_A", "exp_B"], "loader_1")
    mock_view.get_experiment_names_for_tree.assert_called_once_with(
        ["exp_A", "exp_B"], "loader_1"
    )


def test_get_experiment_names_for_tree_forwards_empty_list(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward an empty experiment list to the view tree display.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_names_for_tree([], "loader_1")
    mock_view.get_experiment_names_for_tree.assert_called_once_with([], "loader_1")


# ----------------- get_experiment_structure_ready --------------------


def test_get_experiment_structure_ready_converts_channel_ids_to_strings(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Convert integer channel IDs to strings before storing on the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_structure_ready({"exp1": [1, 2, 3]}, "ldr")
    result: Dict[str, List[str]] = (
        mock_view.available_experiment_and_channels_by_loader["ldr"]
    )
    assert result == {"exp1": ["1", "2", "3"]}


def test_get_experiment_structure_ready_logs_debug_with_loader_name(
    controller: MetadataController,
) -> None:
    """
    Log a debug message containing the loader name and structure on entry.

    :param controller: Controller under test.
    """
    controller.get_experiment_structure_ready({"exp1": [1]}, "my_loader")
    controller.logger.debug.assert_called_once()  # type: ignore[attr-defined]
    debug_msg: str = controller.logger.debug.call_args[0][0]  # type: ignore[attr-defined,index]
    assert "my_loader" in debug_msg


def test_get_experiment_structure_ready_stores_under_correct_loader_key(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Store the converted structure under the supplied loader name.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_structure_ready({"exp1": [0]}, "my_loader")
    assert "my_loader" in mock_view.available_experiment_and_channels_by_loader


def test_get_experiment_structure_ready_selected_equals_available(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Confirm that selected and available dicts contain the same data after construction.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_structure_ready({"exp1": [7]}, "ldr")
    avail: Dict[str, List[str]] = mock_view.available_experiment_and_channels_by_loader[
        "ldr"
    ]
    sel: Dict[str, List[str]] = mock_view.selected_experiment_and_channels_by_loader[
        "ldr"
    ]
    assert avail == sel


def test_get_experiment_structure_ready_selected_is_shallow_copy(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Document that str_structure.copy() is shallow: inner channel lists are shared.

    Mutating a channel list in available also mutates the same list in
    selected. This test pins the current behaviour; consider
    copy.deepcopy if independent mutation is required.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_structure_ready({"exp1": [5]}, "ldr")
    avail: Dict[str, List[str]] = mock_view.available_experiment_and_channels_by_loader[
        "ldr"
    ]
    sel: Dict[str, List[str]] = mock_view.selected_experiment_and_channels_by_loader[
        "ldr"
    ]
    avail["exp1"].append("MUTATED")
    assert "MUTATED" in sel["exp1"]


def test_get_experiment_structure_ready_handles_empty_structure(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Store an empty dict correctly when the input structure has no experiments.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.get_experiment_structure_ready({}, "ldr")
    assert mock_view.available_experiment_and_channels_by_loader["ldr"] == {}


def test_get_experiment_structure_ready_converts_multiple_experiments(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Convert all experiments and their channel lists in a multi-experiment structure.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    structure: Dict[str, List[int]] = {"exp1": [1], "exp2": [10, 20]}
    controller.get_experiment_structure_ready(structure, "ldr")
    result: Dict[str, List[str]] = (
        mock_view.available_experiment_and_channels_by_loader["ldr"]
    )
    assert result == {"exp1": ["1"], "exp2": ["10", "20"]}


# ------------------------- relay_query -------------------------------
# -- debug / error path -----------------------------------------------


def test_relay_query_emits_debug_message_when_query_is_empty(
    controller: MetadataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Show a QMessageBox warning when the query is empty and debug message is provided.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    :param mocker: Pytest-mock fixture.
    """
    mock_warning = mocker.patch(
        "poriscope.plugins.analysistabs.MetadataController.QMessageBox.warning"
    )
    controller.relay_query("", "something went wrong", "my_table")
    mock_warning.assert_called_once()
    call_args = mock_warning.call_args[0]
    assert "something went wrong" in call_args[2]


def test_relay_query_does_not_call_set_query_when_query_is_empty(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Skip set_query entirely when the query string is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("", "err", "my_table")
    mock_view.set_query.assert_not_called()


def test_relay_query_debug_path_clears_pending_for_validate_new_filter(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Clear pending filter state on the debug path for the validate_new_filter intent.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("", "err", "t", "validate_new_filter")
    mock_view.clear_pending_filter_state.assert_called_once()


def test_relay_query_debug_path_clears_pending_for_validate_edited_filter(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Clear pending filter state on the debug path for the validate_edited_filter intent.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("", "err", "t", "validate_edited_filter")
    mock_view.clear_pending_filter_state.assert_called_once()


def test_relay_query_debug_path_no_intent_does_not_clear_pending(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Do not clear pending state on the debug path when no intent is supplied.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("", "err", "t")
    mock_view.clear_pending_filter_state.assert_not_called()


# -- happy path, no intent --------------------------------------------


def test_relay_query_calls_set_query_with_correct_args(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a valid query and table name to the view when no intent is given.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("SELECT 1", "", "my_table")
    mock_view.set_query.assert_called_once_with("SELECT 1", "my_table")


def test_relay_query_clears_pending_state_after_valid_query(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Call clear_pending_filter_state after successfully forwarding a query.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.relay_query("SELECT 1", "", "my_table")
    mock_view.clear_pending_filter_state.assert_called_once()


# -- validate_new_filter ----------------------------------------------


def test_relay_query_new_filter_stored_in_subset_filters(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Store a validated new filter in subset_filters under its pending name with _assisted suffix.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = "fast_events"
    mock_view._pending_filter_text = "duration < 1.0"
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    assert mock_view.subset_filters["fast_events_assisted"] == "duration < 1.0"


def test_relay_query_new_filter_calls_replace_filter_item(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Call replace_filter_item on the view after storing the new filter with _assisted suffix.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = "fast_events"
    mock_view._pending_filter_text = "duration < 1.0"
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    mock_view.replace_filter_item.assert_called_once_with("fast_events_assisted")


def test_relay_query_new_filter_empty_text_stored_as_empty_string(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Store an empty string in subset_filters when the filter text is blank.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = "all_events"
    mock_view._pending_filter_text = ""
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    assert mock_view.subset_filters["all_events_assisted"] == ""


def test_relay_query_new_filter_empty_text_emits_all_rows_message(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Emit an informational all rows message when the filter text is blank.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = "all_events"
    mock_view._pending_filter_text = ""
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    emitted: str = " ".join(
        str(c) for c in mock_view.add_text_to_display.emit.call_args_list
    )
    assert "all rows" in emitted


def test_relay_query_new_filter_emits_added_confirmation(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Emit a confirmation message containing 'added' after storing the filter.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = "my_filter"
    mock_view._pending_filter_text = "x > 0"
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    emitted: str = " ".join(
        str(c) for c in mock_view.add_text_to_display.emit.call_args_list
    )
    assert "added" in emitted


def test_relay_query_new_filter_skipped_when_pending_name_is_none(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Skip all filter storage and UI update when the pending filter name is None.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = None
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter")
    mock_view.replace_filter_item.assert_not_called()
    assert mock_view.subset_filters == {}


# -- validate_edited_filter -------------------------------------------


def test_relay_query_edited_filter_removes_old_key(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Remove the old filter key from subset_filters when renaming a filter.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view.subset_filters["old_name"] = "x > 0"
    mock_view._pending_old_filter_name = "old_name"
    mock_view._pending_filter_name = "new_name"
    mock_view._pending_filter_text = "x > 5"
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    assert "old_name" not in mock_view.subset_filters


def test_relay_query_edited_filter_adds_new_key(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Add the new filter key with _assisted suffix to subset_filters after a rename.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view.subset_filters["old_name"] = "x > 0"
    mock_view._pending_old_filter_name = "old_name"
    mock_view._pending_filter_name = "new_name"
    mock_view._pending_filter_text = "x > 5"
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    assert mock_view.subset_filters["new_name_assisted"] == "x > 5"


def test_relay_query_edited_filter_calls_update_filter_name(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Call update_filter_name with old name and new name with _assisted suffix on the view.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_old_filter_name = "old_name"
    mock_view._pending_filter_name = "new_name"
    mock_view._pending_filter_text = "x > 5"
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    mock_view.update_filter_name.assert_called_once_with(
        "old_name", "new_name_assisted"
    )


def test_relay_query_edited_filter_empty_text_stored_as_empty_string(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """Store an empty string in subset_filters when the edited filter text is blank."""
    mock_view._pending_old_filter_name = "alpha"
    mock_view._pending_filter_name = "beta"
    mock_view._pending_filter_text = ""
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    assert mock_view.subset_filters["beta_assisted"] == ""


def test_relay_query_edited_filter_empty_text_emits_full_dataset_message(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Emit a message containing 'FULL DATASET' when the edited filter text is blank.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_old_filter_name = "alpha"
    mock_view._pending_filter_name = "beta"
    mock_view._pending_filter_text = ""
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    emitted: str = " ".join(
        str(c) for c in mock_view.add_text_to_display.emit.call_args_list
    )
    assert "FULL DATASET" in emitted


def test_relay_query_edited_filter_emits_updated_confirmation(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Emit a confirmation message containing 'updated' after renaming the filter.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_old_filter_name = "alpha"
    mock_view._pending_filter_name = "beta"
    mock_view._pending_filter_text = "y < 10"
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    emitted: str = " ".join(
        str(c) for c in mock_view.add_text_to_display.emit.call_args_list
    )
    assert "updated" in emitted


def test_relay_query_edited_filter_skipped_when_new_name_is_none(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Skip all rename logic when the pending new filter name is None.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view._pending_filter_name = None
    controller.relay_query("SELECT 1", "", "t", "validate_edited_filter")
    mock_view.update_filter_name.assert_not_called()
