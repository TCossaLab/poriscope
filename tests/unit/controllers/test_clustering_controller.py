"""
Tests for poriscope.plugins.analysistabs.ClusteringController.

Covers:
- _init creates view and model
- _setup_connections is a no-op that does not raise
- display_write_status (success and failure branches)
- check_cluster_column_exists delegation
- alter_database_status delegation
- relay_query (query present, debug-only path)
- relay_event_data_generator delegation
- relay_plot_data delegation
- relay_units delegation
- update_column_names (names provided with info log, empty list with warning log)
- update_column_units (units provided with info log, empty dict skips view)
- request_column_names / request_column_units, the Step 4a replacements for two
  ``global_signal`` round trips: they call the plugin through ``self.model.call`` and
  report a failure instead of leaving the View with the previous loader's answer
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ClusteringController import ClusteringController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked ClusteringView.

    :param mocker: Pytest-mock fixture.
    :return: Mocked clustering view.
    """
    view: MagicMock = mocker.Mock()
    return view


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> ClusteringController:
    """
    Construct a ClusteringController with view, model, and signals replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked clustering view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: ClusteringController = ClusteringController.__new__(ClusteringController)  # type: ignore[type-abstract]
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


# ----------------------- _init / _setup_connections ------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates ClusteringView and ClusteringModel on the controller.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ClusteringController.ClusteringView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ClusteringController.ClusteringModel"
    )

    ctrl: ClusteringController = ClusteringController.__new__(ClusteringController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_does_not_raise(
    controller: ClusteringController,
) -> None:
    """
    Verify that _setup_connections is currently a no-op and does not raise.

    :param controller: Controller under test.
    """
    controller._setup_connections()


# -------------------- display_write_status ---------------------------


def test_display_write_status_emits_success_message(
    controller: ClusteringController,
) -> None:
    """
    Emit a success message when the write status is True.

    :param controller: Controller under test.
    """
    controller.display_write_status(True)
    controller.add_text_to_display.emit.assert_called_once_with(
        "Successfully wrote clustering data", "ClusteringController"
    )


def test_display_write_status_emits_failure_message(
    controller: ClusteringController,
) -> None:
    """
    Emit a failure message when the write status is False.

    :param controller: Controller under test.
    """
    controller.display_write_status(False)
    controller.add_text_to_display.emit.assert_called_once_with(
        "Failed to write clustering data", "ClusteringController"
    )


# ---------------- check_cluster_column_exists ------------------------


def test_check_cluster_column_exists_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the table name to the view to check for a cluster column.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.check_cluster_column_exists("events")
    mock_view.set_cluster_column_exists.assert_called_once_with("events")


# ------------------- alter_database_status ---------------------------


def test_alter_database_status_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the alteration status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.alter_database_status(True)
    mock_view.set_alter_database_status.assert_called_once_with(True)


def test_alter_database_status_delegates_false_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a False alteration status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.alter_database_status(False)
    mock_view.set_alter_database_status.assert_called_once_with(False)


# ------------------------- relay_query -------------------------------


def test_relay_query_forwards_query_and_table_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a valid query and table name to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.relay_query("SELECT * FROM events", "", "events")
    mock_view.set_query.assert_called_once_with("SELECT * FROM events", "events")


def test_relay_query_emits_debug_when_query_empty(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Emit a debug message and still call set_query when the query string is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.relay_query("", "debug message", "events")
    controller.add_text_to_display.emit.assert_called_once_with(
        "debug message", "ClusteringController"
    )
    mock_view.set_query.assert_called_once_with("", "events")


# --------------- relay_event_data_generator --------------------------


def test_relay_event_data_generator_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward an event data generator to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    gen = iter([{"id": 1}, {"id": 2}])
    controller.relay_event_data_generator(gen)
    mock_view.set_event_data_generator.assert_called_once_with(gen)


# ----------------------- relay_plot_data -----------------------------


def test_relay_plot_data_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward structured plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    data = {"x": [1.0, 2.0], "y": [3.0, 4.0]}
    controller.relay_plot_data(data)
    mock_view.set_plot_data.assert_called_once_with(data)


# ------------------------- relay_units -------------------------------


def test_relay_units_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a column-to-unit mapping to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    units = {"current": "pA", "time": "s"}
    controller.relay_units(units)
    mock_view.set_units.assert_called_once_with(units)


# -------------------- request_column_names (Step 4a) ------------------


class TestRequestColumnNames:
    """
    The Step 4a replacement for a ``global_signal`` round trip.

    What it replaces mattered: the bus resolved the return function by string seven
    hops away, and ``_dispatch_to`` logged and returned on four separate conditions -
    so a loader that could not be read left the View showing the *previous* loader's
    columns, with nothing the View could detect.
    """

    def test_it_calls_the_plugin_through_the_model(
        self, controller: ClusteringController
    ) -> None:
        """One hop, by key, through the sanctioned API."""
        controller.model.call.return_value = ["duration", "current"]

        controller.request_column_names("SQLiteDBLoader_0")

        controller.model.call.assert_called_once_with(
            "MetaDatabaseLoader", "SQLiteDBLoader_0", "get_column_names_by_table"
        )

    def test_it_hands_the_result_to_the_view(
        self, controller: ClusteringController
    ) -> None:
        """The result path, which Decision B routes through the Controller."""
        controller.model.call.return_value = ["duration", "current"]

        controller.request_column_names("SQLiteDBLoader_0")

        controller.view.update_column_names.assert_called_once_with(
            ["duration", "current"]
        )

    def test_a_failure_is_reported_and_the_view_is_left_alone(
        self, controller: ClusteringController
    ) -> None:
        """
        The whole point of the change.

        The View must not be updated with anything, and the user must be told - rather
        than the failure being logged several hops away where nobody sees it.
        """
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_column_names("gone")

        controller.view.update_column_names.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_it_does_not_raise_out_of_the_slot(
        self, controller: ClusteringController
    ) -> None:
        """
        Qt invoked this from a signal, so an exception must not escape into C++.

        ``call()`` raising is the correct behaviour one level down; catching it here is
        what turns that into something the user sees.
        """
        controller.model.call.side_effect = RuntimeError("the plugin failed")

        controller.request_column_names("SQLiteDBLoader_0")


# -------------------- request_column_units (Step 4a) ------------------


class TestRequestColumnUnits:
    """The same conversion, for one column's unit string."""

    def test_it_passes_the_column_to_the_plugin(
        self, controller: ClusteringController
    ) -> None:
        """The column name is an argument now, not a ``ret_args`` tuple."""
        controller.model.call.return_value = "ms"

        controller.request_column_units("SQLiteDBLoader_0", "duration")

        controller.model.call.assert_called_once_with(
            "MetaDatabaseLoader", "SQLiteDBLoader_0", "get_column_units", "duration"
        )

    def test_it_hands_the_unit_and_the_column_to_the_view(
        self, controller: ClusteringController
    ) -> None:
        """
        Both halves, in the order the View's setter expects.

        The bus carried the column back as ``ret_args`` appended after the result,
        which is why the receiver's parameter is still called ``axis``.
        """
        controller.model.call.return_value = "ms"

        controller.request_column_units("SQLiteDBLoader_0", "duration")

        controller.view.update_column_units.assert_called_once_with("ms", "duration")

    def test_a_failure_leaves_the_view_alone(
        self, controller: ClusteringController
    ) -> None:
        """A unit that cannot be read must not overwrite the label that is showing."""
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_column_units("gone", "duration")

        controller.view.update_column_units.assert_not_called()


# -------------------- update_column_names ----------------------------


def test_update_column_names_updates_view_when_names_provided(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty list of column names to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_names(["col_a", "col_b"])
    mock_view.update_column_names.assert_called_once_with(["col_a", "col_b"])


def test_update_column_names_logs_info_when_names_provided(
    controller: ClusteringController,
) -> None:
    """
    Log an info message after successfully updating the view with column names.

    :param controller: Controller under test.
    """
    controller.update_column_names(["col_a", "col_b"])
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_names_skips_view_when_list_is_empty(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Do not call update_column_names on the view when the list is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_names([])
    mock_view.update_column_names.assert_not_called()


def test_update_column_names_logs_warning_when_list_is_empty(
    controller: ClusteringController,
) -> None:
    """
    Log a warning message when no column names are received.

    :param controller: Controller under test.
    """
    controller.update_column_names([])
    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]


# -------------------- update_column_units ----------------------------


def test_update_column_units_updates_view_when_units_provided(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty units dict and axis identifier to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_units({"voltage": "mV"}, "y")
    mock_view.update_column_units.assert_called_once_with({"voltage": "mV"}, "y")


def test_update_column_units_logs_info_when_units_provided(
    controller: ClusteringController,
) -> None:
    """
    Log an info message after successfully updating unit labels in the view.

    :param controller: Controller under test.
    """
    controller.update_column_units({"voltage": "mV"}, "y")
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_units_skips_view_when_units_empty(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Do not call update_column_units on the view when the units dict is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_units({}, "x")
    mock_view.update_column_units.assert_not_called()
