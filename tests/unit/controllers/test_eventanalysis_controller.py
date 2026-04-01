"""
Tests for poriscope.plugins.analysistabs.EventAnalysisController.

Covers:
- _init creates view and model
- _setup_connections runs without error (empty)
- update_available_plugins logs debug and delegates to model and view
- set_event_filter delegates to view
- set_eventfitting_status delegates to view (True and False)
- update_plot_data delegates to view (data present, data absent)
- update_features (all features with matching labels, no labels, mismatched vlabels,
  mismatched hlabels, mismatched plabels, all None)
- update_plot_samplerate delegates to view
- update_channels delegates to view
- set_num_events_allowed delegates to view
- relay_eventfitting_status delegates to view (True and False)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.EventAnalysisController import (
    EventAnalysisController,
)

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked EventAnalysisView.

    :param mocker: Pytest-mock fixture.
    :return: Mocked event analysis view.
    """
    return mocker.Mock()


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> EventAnalysisController:
    """
    Construct an EventAnalysisController with view, model, and logger replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked event analysis view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: EventAnalysisController = EventAnalysisController.__new__(EventAnalysisController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    return ctrl


# ----------------------- _init / _setup_connections ------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates EventAnalysisView and EventAnalysisModel.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls = mocker.patch(
        "poriscope.plugins.analysistabs.EventAnalysisController.EventAnalysisView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.plugins.analysistabs.EventAnalysisController.EventAnalysisModel"
    )

    ctrl: EventAnalysisController = EventAnalysisController.__new__(EventAnalysisController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_runs_without_error(
    controller: EventAnalysisController,
) -> None:
    """
    Verify that _setup_connections completes without raising.

    The method is intentionally empty so the only requirement is no exception.

    :param controller: Controller under test.
    """
    controller._setup_connections()  # should not raise


# ------------------- update_available_plugins ------------------------


def test_update_available_plugins_delegates_to_model_and_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the available plugins dict to both model and view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    plugins = {"MetaReader": ["R1", "R2"]}
    controller.update_available_plugins(plugins)
    controller.model.update_available_plugins.assert_called_once_with(plugins)
    mock_view.update_available_plugins.assert_called_once_with(plugins)


def test_update_available_plugins_logs_debug(
    controller: EventAnalysisController,
) -> None:
    """
    Log a debug message when the available plugins are updated.

    :param controller: Controller under test.
    """
    controller.update_available_plugins({"MetaReader": ["R1"]})
    controller.logger.debug.assert_called_once()  # type: ignore[attr-defined]


# ----------------------- set_event_filter ----------------------------


def test_set_event_filter_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Forward the data filter callable to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    :param mocker: Pytest-mock fixture.
    """
    data_filter = mocker.Mock()
    controller.set_event_filter(data_filter)
    mock_view.set_data_filter_function.assert_called_once_with(data_filter)


# ------------------ set_eventfitting_status --------------------------


def test_set_eventfitting_status_true_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a True event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_eventfitting_status(True)
    mock_view.set_eventfitting_status.assert_called_once_with(True)


def test_set_eventfitting_status_false_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a False event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_eventfitting_status(False)
    mock_view.set_eventfitting_status.assert_called_once_with(False)


# ----------------------- update_plot_data ----------------------------


def test_update_plot_data_delegates_data_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    data = {"x": [1, 2], "y": [3, 4]}
    controller.update_plot_data(data)
    mock_view.update_plot_data.assert_called_once_with(data)


def test_update_plot_data_delegates_none_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward None to the view when no data is provided.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_plot_data()
    mock_view.update_plot_data.assert_called_once_with(None)


# ----------------------- update_features ----------------------------


def test_update_features_forwards_all_args_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward all feature and label lists to the view when lengths match.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    vertical = [[1.0], [2.0]]
    horizontal = [[3.0], [4.0]]
    points = [[(0.5, 1.5)], [(1.5, 2.5)]]
    vlabels = ["v1", "v2"]
    hlabels = ["h1", "h2"]
    plabels = ["p1", "p2"]

    controller.update_features(
        vertical=vertical,
        horizontal=horizontal,
        points=points,
        vlabels=vlabels,
        hlabels=hlabels,
        plabels=plabels,
    )

    mock_view.update_plot_features.assert_called_once_with(
        vertical, horizontal, points, vlabels, hlabels, plabels
    )


def test_update_features_forwards_all_none_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward all None arguments to the view when no features are provided.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_features()
    mock_view.update_plot_features.assert_called_once_with(
        None, None, None, None, None, None
    )


def test_update_features_raises_on_mismatched_vlabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when vlabels length does not match vertical lines length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="vertical line"):
        controller.update_features(
            vertical=[[1.0], [2.0]],
            vlabels=["only_one_label"],
        )


def test_update_features_raises_on_mismatched_hlabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when hlabels length does not match horizontal lines length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="horizontal line"):
        controller.update_features(
            horizontal=[[1.0], [2.0]],
            hlabels=["only_one_label"],
        )


def test_update_features_raises_on_mismatched_plabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when plabels length does not match points length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="point"):
        controller.update_features(
            points=[[(0.5, 1.5)], [(1.5, 2.5)]],
            plabels=["only_one_label"],
        )


def test_update_features_allows_no_labels(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Allow features without labels and forward them to the view without error.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    vertical = [[1.0], [2.0]]
    controller.update_features(vertical=vertical)
    mock_view.update_plot_features.assert_called_once_with(
        vertical, None, None, None, None, None
    )


# ------------------- update_plot_samplerate --------------------------


def test_update_plot_samplerate_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the sampling rate to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_plot_samplerate(50000.0)
    mock_view.update_plot_samplerate.assert_called_once_with(50000.0)


# ----------------------- update_channels ----------------------------


def test_update_channels_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the channels dict to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    channels = {"num_channels": 2}
    controller.update_channels(channels)
    mock_view.update_channels.assert_called_once_with(channels)


# ------------------- set_num_events_allowed --------------------------


def test_set_num_events_allowed_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the maximum event count to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_num_events_allowed(1000)
    mock_view.set_num_events_allowed.assert_called_once_with(1000)


# ---------------- relay_eventfitting_status --------------------------


def test_relay_eventfitting_status_true_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a True event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.relay_eventfitting_status(True)
    mock_view.set_eventfitting_status.assert_called_once_with(True)


def test_relay_eventfitting_status_false_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a False event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.relay_eventfitting_status(False)
    mock_view.set_eventfitting_status.assert_called_once_with(False)