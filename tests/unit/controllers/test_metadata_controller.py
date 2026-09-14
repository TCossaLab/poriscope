"""
Tests for poriscope.plugins.analysistabs.MetadataController.

Covers:
- _init creates view and model
- _setup_connections wires signals
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

import numpy as np
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

    # The filter store, plus the two methods the controller reaches it through.
    # These carry the real bodies rather than bare Mocks: what relay_query decides
    # is the suffixed name and which entry it replaces, and a Mock would accept any
    # of that silently. Step 4d took the controller's direct writes to the dict out
    # (DECISIONS.md, 2026-09-13); the dict itself stays on the view.
    view.subset_filters = {}  # type: ignore[misc]

    def commit_filter(name, filter_text, old_name=None):
        if old_name is not None:
            view.subset_filters.pop(old_name, None)
        view.subset_filters[name] = filter_text or ""

    view.commit_filter = commit_filter  # type: ignore[misc]
    view.get_subset_filters = lambda: dict(view.subset_filters)  # type: ignore[misc]

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
    mocker.patch("poriscope.utils.MetaSubsetTabController.QMessageBox.warning")
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


def test_request_column_units_applies_the_y_axis_too(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    The twin of the x-axis case: the axis is carried, not inferred.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.model.call.return_value = "mV"

    controller.request_column_units("ldr", "voltage", "y_axis")

    mock_view.update_column_units.assert_called_once_with("mV", "y_axis")


def test_request_column_units_asks_the_loader_and_applies_the_axis(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Step 4a: the base's ``update_column_units`` relay became this slot.

    The relay existed only as a bus return function; nothing names it now. The axis
    travels with the request and back out again, which is what the bus carried in its
    ``ret_args``.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.model.call.return_value = "ms"

    controller.request_column_units("ldr", "duration", "x_axis")

    controller.model.call.assert_called_once_with(
        "MetaDatabaseLoader", "ldr", "get_column_units", "duration"
    )
    mock_view.update_column_units.assert_called_once_with("ms", "x_axis")


def test_request_column_units_leaves_the_label_alone_on_failure(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    A loader that cannot answer leaves the existing label rather than blanking it.

    ``DECISIONS.md`` 2026-09-04 records that ``get_column_units``' empty-string
    conflation is inert because every consumer collapses the distinction, so writing a
    blank would be indistinguishable from a real unitless column.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.model.call.side_effect = RuntimeError("boom")

    controller.request_column_units("ldr", "duration", "x_axis")

    mock_view.update_column_units.assert_not_called()


def test_request_column_units_does_not_raise_out_of_the_slot(
    controller: MetadataController,
) -> None:
    """
    Qt invoked this from a signal; an exception must not escape into C++.

    :param controller: Controller under test.
    """
    controller.model.call.side_effect = RuntimeError("boom")

    controller.request_column_units("ldr", "duration", "x_axis")


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


def test_get_experiment_structure_ready_selection_is_independent_of_available(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    The selection's channel lists are its own, not the available structure's.

    **This assertion is reversed from what it used to be.** It pinned
    ``str_structure.copy()`` being shallow - the two dicts sharing their inner
    lists - and said in its own docstring to "consider copy.deepcopy if independent
    mutation is required". That turned out to be required: the scope fix narrows the
    selection, and sharing the lists would have narrowed what the selection tree
    offers at the same time.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view.available_experiment_and_channels_by_loader = {}
    mock_view.selected_experiment_and_channels_by_loader = {}

    controller.get_experiment_structure_ready({"exp1": [5]}, "ldr")
    avail: Dict[str, List[str]] = mock_view.available_experiment_and_channels_by_loader[
        "ldr"
    ]
    sel: Dict[str, List[str]] = mock_view.selected_experiment_and_channels_by_loader[
        "ldr"
    ]
    avail["exp1"].append("MUTATED")
    assert "MUTATED" not in sel["exp1"]


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
        "poriscope.utils.MetaSubsetTabController.QMessageBox.warning"
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
    # Step 4d: the name and text arrive as arguments rather than being read back off
    # the view, which is the Controller-reads-View-private access this step removes.
    controller.relay_query(
        "SELECT 1",
        "",
        "t",
        "validate_new_filter",
        "fast_events",
        None,
        "duration < 1.0",
    )
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
    controller.relay_query(
        "SELECT 1",
        "",
        "t",
        "validate_new_filter",
        "fast_events",
        None,
        "duration < 1.0",
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_new_filter", "all_events", None, ""
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_new_filter", "all_events", None, ""
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_new_filter", "my_filter", None, "x > 0"
    )
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
    controller.relay_query("SELECT 1", "", "t", "validate_new_filter", None, None, "x")
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "new_name", "old_name", "x > 5"
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "new_name", "old_name", "x > 5"
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "new_name", "old_name", "x > 5"
    )
    mock_view.update_filter_name.assert_called_once_with(
        "old_name", "new_name_assisted"
    )


def test_relay_query_edited_filter_empty_text_stored_as_empty_string(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """Store an empty string in subset_filters when the edited filter text is blank."""
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "beta", "alpha", ""
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "beta", "alpha", ""
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", "beta", "alpha", "y < 10"
    )
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
    controller.relay_query(
        "SELECT 1", "", "t", "validate_edited_filter", None, "alpha", "y < 10"
    )


# ----------------------------- session state ------------------------------


def test_get_session_state_returns_view_subset_filters(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Include a copy of the view's live subset filters in the returned session state.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    mock_view.subset_filters = {"f1": "voltage > 0"}

    state = controller.get_session_state()

    assert state == {"subset_filters": {"f1": "voltage > 0"}}


def test_restore_session_state_applies_subset_filters(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a session entry's subset filters to the view's restore method.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.restore_session_state(
        {"metaclass": "MetaController", "subset_filters": {"f1": "voltage > 0"}}
    )

    mock_view.restore_subset_filters.assert_called_once_with({"f1": "voltage > 0"})


def test_restore_session_state_is_noop_without_subset_filters(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Do nothing when the session entry carries no subset filters to restore.

    :param controller: Controller under test.
    :param mock_view: Mocked metadata view.
    """
    controller.restore_session_state({"metaclass": "MetaController"})

    mock_view.restore_subset_filters.assert_not_called()
    mock_view.update_filter_name.assert_not_called()


def test_get_experiment_structure_ready_keeps_an_existing_channel_selection(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    Re-reading the structure must not throw away the scope the user chose.

    Reported from a real run: a heatmap refused with "Only a single channel can be
    used for Heatmap" while one channel was ticked in Scope. Every fetch of the
    experiment structure overwrote the *selection* with the whole structure, so any
    later refresh silently widened a one-channel scope back to every channel - and
    the heatmap guard, which is the only plot type that checks, was the one that
    noticed.
    """
    mock_view.available_experiment_and_channels_by_loader = {}
    mock_view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": ["2"]}}

    controller.get_experiment_structure_ready({"exp1": [1, 2, 3]}, "ldr")

    assert mock_view.selected_experiment_and_channels_by_loader["ldr"] == {
        "exp1": ["2"]
    }


def test_get_experiment_structure_ready_selects_everything_when_nothing_is_chosen(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """With no prior scope, defaulting to the whole structure is the useful start."""
    mock_view.available_experiment_and_channels_by_loader = {}
    mock_view.selected_experiment_and_channels_by_loader = {}

    controller.get_experiment_structure_ready({"exp1": [1, 2]}, "ldr")

    assert mock_view.selected_experiment_and_channels_by_loader["ldr"] == {
        "exp1": ["1", "2"]
    }


def test_get_experiment_structure_ready_drops_channels_that_no_longer_exist(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    A remembered scope is pruned to what the database still holds.

    Keeping a selection must not mean keeping a channel that has gone, which would
    scope a query to nothing and plot an empty figure.
    """
    mock_view.available_experiment_and_channels_by_loader = {}
    mock_view.selected_experiment_and_channels_by_loader = {
        "ldr": {"exp1": ["2", "9"], "gone": ["1"]}
    }

    controller.get_experiment_structure_ready({"exp1": [1, 2, 3]}, "ldr")

    assert mock_view.selected_experiment_and_channels_by_loader["ldr"] == {
        "exp1": ["2"]
    }


def test_get_experiment_structure_ready_does_not_alias_the_available_structure(
    controller: MetadataController,
    mock_view: MagicMock,
) -> None:
    """
    The selection must not share its channel lists with the available structure.

    ``dict.copy()`` is shallow, so the two dicts held the *same* list objects and
    narrowing the scope in place would have narrowed what the tree offers.
    """
    mock_view.available_experiment_and_channels_by_loader = {}
    mock_view.selected_experiment_and_channels_by_loader = {}

    controller.get_experiment_structure_ready({"exp1": [1, 2]}, "ldr")

    selected = mock_view.selected_experiment_and_channels_by_loader["ldr"]
    available = mock_view.available_experiment_and_channels_by_loader["ldr"]
    selected["exp1"].remove("1")

    assert available["exp1"] == ["1", "2"]


# --------------------- fit_capture_rate, Step 4 closeout ---------------------
#
# The inter-event times moved here from MetadataView, and both conditions that were
# judged on them came with the computation: too little surviving data, and how much
# the log filter dropped. The View's tests for those were deleted rather than
# re-pointed, because the behaviour is not there any more.


class TestFitCaptureRate:
    """Decision B's command path, with two guards on the Model's answer."""

    @pytest.fixture(autouse=True)
    def _stub_status_panel(self, controller, mocker) -> None:
        """
        Give the controller a status-panel signal it can emit on.

        ``MetadataController`` is built with ``__new__`` here, so its real Qt signal
        has no object behind it and emitting raises "Signal source has been deleted".
        The file's convention is to stub it per test; every test in this class reports
        or is checked for not reporting, so it is done once for all of them.

        :param controller: the controller under test
        :type controller: MetadataController
        :param mocker: the pytest-mock fixture
        :type mocker: pytest_mock.MockerFixture
        :return: None
        :rtype: None
        """
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

    @staticmethod
    def _request(controller, times):
        """
        Drive the slot with a column of event times.

        :param controller: the controller under test
        :type controller: MetadataController
        :param times: the event times the View would have sent
        :type times: list
        :return: None
        :rtype: None
        """
        controller.fit_capture_rate(
            np.asarray(times), None, False, MagicMock(), "x", "y", "label"
        )

    @staticmethod
    def _messages(controller):
        """
        Every line the slot put on the status panel.

        :param controller: the controller under test
        :type controller: MetadataController
        :return: the messages, in order
        :rtype: list
        """
        return [c.args[0] for c in controller.add_text_to_display.emit.call_args_list]

    def test_the_column_goes_to_the_model_unreduced(self, controller) -> None:
        """
        The View sends event times; turning them into gaps is the Model's.

        A Controller that reduced the column itself, or forwarded it to the fit
        untouched, would fail here.
        """
        controller.model.interevent_log_times.return_value = np.arange(20.0)

        self._request(controller, [1.0, 2.0, 4.0, 8.0])

        sent = controller.model.interevent_log_times.call_args.args[0]
        np.testing.assert_array_equal(sent, [1.0, 2.0, 4.0, 8.0])

    def test_the_fit_is_given_what_the_model_returned(self, controller) -> None:
        """A Controller that fitted the raw times would produce a meaningless rate."""
        log_times = np.arange(20.0)
        controller.model.interevent_log_times.return_value = log_times
        controller.model.fit_capture_rate.return_value = (1, 2, 3, 4, 5.0, 6.0)

        self._request(controller, list(range(30)))

        np.testing.assert_array_equal(
            controller.model.fit_capture_rate.call_args.args[0], log_times
        )

    def test_too_little_surviving_data_is_reported_and_stops(self, controller) -> None:
        """
        Reported rather than raised, and with the count in it.

        In the View this raised a ValueError that ``update_plot`` turned into the
        generic "no data available after filtering"; the user now gets the number.
        """
        controller.model.interevent_log_times.return_value = np.arange(9.0)

        self._request(controller, list(range(20)))

        assert any("Not enough data passes the log filter: 9" in m
                   for m in self._messages(controller))
        controller.model.fit_capture_rate.assert_not_called()

    def test_exactly_ten_survivors_is_enough(self, controller) -> None:
        """The boundary is ``< 10``, so ten proceeds - pinned so it cannot drift."""
        controller.model.interevent_log_times.return_value = np.arange(10.0)
        controller.model.fit_capture_rate.return_value = (1, 2, 3, 4, 5.0, 6.0)

        self._request(controller, list(range(20)))

        controller.model.fit_capture_rate.assert_called_once()

    def test_dropped_rows_are_reported(self, controller) -> None:
        controller.model.interevent_log_times.return_value = np.arange(12.0)
        controller.model.fit_capture_rate.return_value = (1, 2, 3, 4, 5.0, 6.0)

        self._request(controller, list(range(20)))

        assert any("8 rows dropped by log filter" in m
                   for m in self._messages(controller))

    def test_a_clean_column_still_reports_one_dropped_row(self, controller) -> None:
        """
        Preserved, not corrected: the interval count is one less than the event count
        by construction, and the original counted that as a drop. Pinned so the move
        is provably behaviour-preserving; filed in ``future_fixes.md`` as the cosmetic
        defect it is.
        """
        controller.model.interevent_log_times.return_value = np.arange(19.0)
        controller.model.fit_capture_rate.return_value = (1, 2, 3, 4, 5.0, 6.0)

        self._request(controller, list(range(20)))

        assert any("1 rows dropped by log filter" in m
                   for m in self._messages(controller))

    def test_the_view_is_handed_the_log_times_not_the_raw_column(
        self, controller, mock_view
    ) -> None:
        """
        ``set_capture_rate`` draws the histogram from this, so handing back the raw
        times would plot event times against inter-event-time bins.
        """
        log_times = np.arange(20.0)
        controller.model.interevent_log_times.return_value = log_times
        controller.model.fit_capture_rate.return_value = (1, 2, 3, 4, 5.0, 6.0)

        self._request(controller, list(range(30)))

        np.testing.assert_array_equal(
            mock_view.set_capture_rate.call_args.args[6], log_times
        )

    def test_a_fit_that_will_not_converge_is_reported(self, controller) -> None:
        controller.model.interevent_log_times.return_value = np.arange(20.0)
        controller.model.fit_capture_rate.side_effect = RuntimeError("no convergence")

        self._request(controller, list(range(30)))

        assert any("Unable to fit the capture rate" in m
                   for m in self._messages(controller))


# ------------------- count_categories, Step 4 closeout -----------------------


class TestCountCategories:
    """Decision B's command path: datasets in, tallies back through a setter."""

    @pytest.fixture(autouse=True)
    def _stub_status_panel(self, controller, mocker) -> None:
        """
        Give the controller a status-panel signal it can emit on.

        :param controller: the controller under test
        :type controller: MetadataController
        :param mocker: the pytest-mock fixture
        :type mocker: pytest_mock.MockerFixture
        :return: None
        :rtype: None
        """
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

    def test_every_dataset_goes_down_in_one_call(self, controller) -> None:
        """
        One round trip for all the overlaid datasets, not one each - the same reason
        estimate_kernel_densities loops in the Model: no answer is parked between them.
        """
        datasets = [np.array(["a"]), np.array(["b"])]

        controller.count_categories(datasets, ["d1", "d2"], MagicMock(), "x", "y")

        assert controller.model.categorical_counts.call_args.args[0] is datasets

    def test_the_tallies_go_back_to_the_view(self, controller, mock_view) -> None:
        counts = [(["a"], np.array([1.0]))]
        controller.model.categorical_counts.return_value = counts
        ax = MagicMock()

        controller.count_categories([np.array(["a"])], ["d1"], ax, "x", "y")

        mock_view.set_categorical_counts.assert_called_once_with(
            counts, ["d1"], ax, "x", "y"
        )

    def test_a_column_the_tally_cannot_sort_is_reported(self, controller) -> None:
        """
        Reported rather than allowed to escape a Qt slot: nothing between the View and
        _overlay_plot catches it, which is how the NULL column defect surfaced as a
        crash before the tally learned to count nulls apart.
        """
        controller.model.categorical_counts.side_effect = TypeError(
            "'<' not supported between instances of 'NoneType' and 'str'"
        )

        controller.count_categories([np.array(["a"])], ["d1"], MagicMock(), "x", "y")

        messages = [
            c.args[0] for c in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to count categories" in m for m in messages)

    def test_a_failed_tally_draws_nothing(self, controller, mock_view) -> None:
        """A stale bar chart must not be left under this dataset's label."""
        controller.model.categorical_counts.side_effect = ValueError("boom")

        controller.count_categories([np.array(["a"])], ["d1"], MagicMock(), "x", "y")

        mock_view.set_categorical_counts.assert_not_called()
