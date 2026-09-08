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
    # Real MetaController signal, needed by any slot that reports a failure to the
    # status panel. Added when Step 4a gave this controller its first such slots.
    ctrl.add_text_to_display = mocker.Mock()
    ctrl.add_text_to_display.emit = mocker.Mock()
    return ctrl


# ----------------------- Step 4a: the two single-emit paths ----------


class TestRequestLoaderChannels:
    """
    The Step 4a replacement for a ``global_signal`` round trip, against MetaEventLoader.

    The direct analogue of ``RawDataController.request_reader_channels``: the View asked a
    loader for its channel list over the bus and the answer came back seven hops later
    through a return function named by string. It is one call now.
    """

    def test_it_asks_the_loader_through_the_model(
        self, controller: EventAnalysisController
    ) -> None:
        """By key, through the sanctioned API."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_loader_channels("SQLiteEventLoader_0")

        controller.model.call.assert_called_once_with(
            "MetaEventLoader", "SQLiteEventLoader_0", "get_channels"
        )

    def test_it_hands_the_channels_to_the_view(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """The result path, which populates the channel combobox."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_loader_channels("SQLiteEventLoader_0")

        mock_view.update_channels.assert_called_once_with([0, 1, 2])

    def test_a_failure_leaves_the_combobox_alone(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        Not repopulated with nothing.

        Clearing it would look to the user like a loader with no channels, which is a
        different and more alarming thing than a loader that could not be read.
        """
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_loader_channels("gone")

        mock_view.update_channels.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_it_does_not_raise_out_of_the_slot(
        self, controller: EventAnalysisController
    ) -> None:
        """Qt invoked this from a signal; an exception must not escape into C++."""
        controller.model.call.side_effect = RuntimeError("loader failed")

        controller.request_loader_channels("SQLiteEventLoader_0")


class TestWriteEvents:
    """
    The write call, moved off the View with the tests that pinned it.

    Never an emit-then-read: ``write_events`` returns a generator and the bus passed it
    into ``set_generator`` as an argument, so there was no attribute to park it on.
    """

    def test_each_channel_is_written_and_its_generator_registered(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        One call per channel, and the generator it returns goes to the Model.

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.write_events("w1", [0, 1])

        assert controller.model.call.call_args_list == [
            mocker.call("MetaDatabaseWriter", "w1", "write_events", 0),
            mocker.call("MetaDatabaseWriter", "w1", "write_events", 1),
        ]
        assert controller.model.set_generator.call_args_list == [
            mocker.call("gen0", 0, "w1", "MetaDatabaseWriter"),
            mocker.call("gen1", 1, "w1", "MetaDatabaseWriter"),
        ]

    def test_the_generators_are_run_once_for_the_writer(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Registration and running stay separate steps, as through the bus.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0"]

        controller.write_events("my_writer", [0])

        controller.model.run_generators.assert_called_once_with("my_writer")

    def test_no_channels_writes_nothing_but_still_runs(
        self, controller: EventAnalysisController
    ) -> None:
        """
        The old test asserted no write emit for an empty list; this is the same property.

        ``run_generators`` is still called unconditionally, as the View did.

        :param controller: Controller under test.
        """
        controller.write_events("w1", [])

        controller.model.call.assert_not_called()
        controller.model.run_generators.assert_called_once_with("w1")

    def test_a_channel_that_cannot_be_written_is_skipped_not_fatal(
        self, controller: EventAnalysisController
    ) -> None:
        """
        **The deliberate behaviour change**, matching RawData's commit path.

        The View's ``except (IndexError, ValueError)`` abandoned the whole batch and
        skipped ``run_generators``, and could not catch a plugin failure anyway because
        the bus swallowed those first. Losing one channel beats losing every channel's
        write, and an arbitrary writer exception must not escape a Qt slot.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", RuntimeError("boom"), "gen2"]

        controller.write_events("w1", [0, 1, 2])

        registered = [
            call.args[1] for call in controller.model.set_generator.call_args_list
        ]
        assert registered == [0, 2]
        controller.model.run_generators.assert_called_once_with("w1")
        controller.add_text_to_display.emit.assert_called_once()


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
