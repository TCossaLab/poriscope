"""
Tests for poriscope.plugins.analysistabs.RawDataController.

Covers:
- _init creates view and model
- _setup_connections wires calculate_psd signal
- calculate_psd computes PSD via model and updates view
- update_available_plugins logs debug and delegates to model and view
- set_event_filter delegates to view
- update_plot_data delegates to view
- update_plot_samplerate delegates to view
- update_channels delegates to view
- update_timer_channels delegates to view
- set_num_events_allowed delegates to view
- set_eventfinding_status delegates to view
- relay_eventfinding_status delegates to view
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.RawDataController import RawDataController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked RawDataView with Qt-like signals used by the controller.

    :param mocker: Pytest-mock fixture.
    :return: Mocked raw data view.
    """
    view: MagicMock = mocker.Mock()
    view.calculate_psd = mocker.Mock()
    view.calculate_psd.connect = mocker.Mock()
    return view


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> RawDataController:
    """
    Construct a RawDataController with view, model, and logger replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: RawDataController = RawDataController.__new__(RawDataController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    return ctrl


# ----------------------- _init / _setup_connections ------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates RawDataView and RawDataModel on the controller.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.RawDataController.RawDataView"
    )
    mock_model_cls: MagicMock = mocker.patch(
        "poriscope.plugins.analysistabs.RawDataController.RawDataModel"
    )

    ctrl: RawDataController = RawDataController.__new__(RawDataController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_wires_calculate_psd(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Verify that _setup_connections connects calculate_psd to the controller slot.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller._setup_connections()
    mock_view.calculate_psd.connect.assert_called_once_with(controller.calculate_psd)


# ----------------------- calculate_psd ------------------------------


def test_calculate_psd_calls_model_and_updates_view(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Compute PSD via the model and forward results to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    psd_data: list[list[float]] = [[1.0, 2.0, 3.0]]
    samplerate: float = 50000.0
    Pxx_list: list[list[float]] = [[0.1, 0.2]]
    rms_list: list[float] = [0.05]
    frequency: list[float] = [0.0, 100.0]

    controller.model.calculate_psd.return_value = (Pxx_list, rms_list, frequency)

    controller.calculate_psd(psd_data, samplerate)

    controller.model.calculate_psd.assert_called_once_with(psd_data, samplerate)
    mock_view.set_psd.assert_called_once_with(Pxx_list, rms_list, frequency)


# ------------------- update_available_plugins ------------------------


def test_update_available_plugins_delegates_to_model_and_view(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Forward the available plugins dict to both the model and the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    plugins: dict[str, list[str]] = {"MetaReader": ["R1", "R2"]}
    controller.update_available_plugins(plugins)
    controller.model.update_available_plugins.assert_called_once_with(plugins)
    mock_view.update_available_plugins.assert_called_once_with(plugins)


def test_update_available_plugins_logs_debug(
    controller: RawDataController,
) -> None:
    """
    Log a debug message when the available plugins are updated.

    :param controller: Controller under test.
    """
    controller.update_available_plugins({"MetaReader": ["R1"]})
    controller.logger.debug.assert_called_once()  # type: ignore[attr-defined]


# ----------------------- set_event_filter ----------------------------


def test_set_event_filter_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Forward the data filter callable to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    data_filter: Callable[..., Any] = mocker.Mock()
    controller.set_event_filter(data_filter)
    mock_view.set_data_filter_function.assert_called_once_with(data_filter)


# ----------------------- update_plot_data ----------------------------


def test_update_plot_data_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward new plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    data: dict[str, list[int]] = {"x": [1, 2], "y": [3, 4]}
    controller.update_plot_data(data)
    mock_view.update_plot_data.assert_called_once_with(data)


# ------------------- update_plot_samplerate --------------------------


def test_update_plot_samplerate_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the sampling rate to the view for time axis conversion.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.update_plot_samplerate(50000.0)
    mock_view.update_plot_samplerate.assert_called_once_with(50000.0)


# ----------------------- update_channels ----------------------------


def test_update_channels_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the channel information dict to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    channels: dict[str, int] = {"num_channels": 4}
    controller.update_channels(channels)
    mock_view.update_channels.assert_called_once_with(channels)


# ------------------- update_timer_channels ---------------------------


def test_update_timer_channels_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the timer channel list to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    channels: list[int] = [0, 1, 2]
    controller.update_timer_channels(channels)
    mock_view.update_timer_channels.assert_called_once_with(channels)


# ------------------- set_num_events_allowed --------------------------


def test_set_num_events_allowed_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the maximum event count to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.set_num_events_allowed(500)
    mock_view.set_num_events_allowed.assert_called_once_with(500)


# ------------------ set_eventfinding_status --------------------------


def test_set_eventfinding_status_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the event finding status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.set_eventfinding_status(True)
    mock_view.set_eventfinding_status.assert_called_once_with(True)


def test_set_eventfinding_status_delegates_false_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a False event finding status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.set_eventfinding_status(False)
    mock_view.set_eventfinding_status.assert_called_once_with(False)


# ---------------- relay_eventfinding_status --------------------------


def test_relay_eventfinding_status_delegates_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a True event finding status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.relay_eventfinding_status(True)
    mock_view.set_eventfinding_status.assert_called_once_with(True)


def test_relay_eventfinding_status_delegates_false_to_view(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a False event finding status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.relay_eventfinding_status(False)
    mock_view.set_eventfinding_status.assert_called_once_with(False)