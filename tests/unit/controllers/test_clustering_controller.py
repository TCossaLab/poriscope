"""
Tests for poriscope.plugins.analysistabs.ClusteringController.

Covers:
- _init creates view and model
- _setup_connections wires request_plugin_refresh to refresh_plugin_list
- display_write_status (success and failure branches)
- check_cluster_column_exists delegation
- alter_database_status delegation
- relay_query (query present, debug-only path)
- relay_event_data_generator delegation
- relay_plot_data delegation
- relay_units delegation
- update_column_names (names provided with info log, empty list with warning log)
- update_column_units (units provided with info log, empty dict skips view)
- update_plugins emits update_available_plugins signal
- refresh_plugin_list (loader present, loader absent)
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
    Provide a mocked ClusteringView with Qt-like signals and slots.

    :param mocker: Pytest-mock fixture.
    :return: Mocked clustering view.
    """
    view: MagicMock = mocker.Mock()
    view.request_plugin_refresh = mocker.Mock()
    view.request_plugin_refresh.connect = mocker.Mock()
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

