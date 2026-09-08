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


# ----------------------- Step 4a -------------------------------------


class TestFittingLaunch:
    """
    The three bus round trips ``EventAnalysisView._start_eventfitter`` used to make.

    Split across two slots because the launch has a question for the user in the middle
    of it, exactly as RawData's event finding does. These invariants were pinned against
    the View before the conversion and moved here with the calls; two of the old ones
    would have gone on passing for the wrong reason instead of failing, since they
    asserted that something was *not* emitted.
    """

    def test_the_status_is_asked_per_channel_and_handed_back_with_the_filter(
        self,
        controller: EventAnalysisController,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        One call per channel, and the filter key travels through untouched.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = [True, False]

        controller.request_fitting_statuses("ef1", [0, 1], "MyFilter")

        assert controller.model.call.call_args_list == [
            mocker.call("MetaEventFitter", "ef1", "get_eventfitting_status", 0),
            mocker.call("MetaEventFitter", "ef1", "get_eventfitting_status", 1),
        ]
        mock_view.set_fitting_statuses.assert_called_once_with(
            "ef1", [(0, True), (1, False)], "MyFilter"
        )

    def test_a_channel_whose_status_cannot_be_read_is_dropped(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        **The stale read this half closes.** The View parked each answer on
        ``self.eventfitting_status``, which nothing cleared, so a swallowed failure left
        the *previous* channel's fitted-ness in place - and the "start over?" prompt was
        then shown, or skipped, for the wrong channel.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        controller.model.call.side_effect = [True, RuntimeError("boom"), False]

        controller.request_fitting_statuses("ef1", [0, 1, 2], "")

        assert mock_view.set_fitting_statuses.call_args[0][1] == [(0, True), (2, False)]
        controller.add_text_to_display.emit.assert_called_once()

    def test_the_status_is_coerced_to_a_bool(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The View branches on it, so a truthy non-bool must not reach the prompt as-is.

        Asserted with ``is True`` and a non-int value: ``== True`` cannot see a missing
        ``bool()`` because ``1 == True`` in Python, which is how the equivalent RawData
        test passed against perturbed code.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        controller.model.call.return_value = "fitted"

        controller.request_fitting_statuses("ef1", [0], "")

        handed_back = mock_view.set_fitting_statuses.call_args[0][1]
        assert handed_back == [(0, True)]
        assert handed_back[0][1] is True

    def test_fit_events_is_called_per_channel_with_the_real_signature(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        ``fit_events(channel, silent=False, data_filter=None, indices=None)``.

        ``silent`` and ``indices`` are passed explicitly because the View always did,
        even though both match their defaults - written from the signature rather than
        the old call site (rule 42).

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 2], "")

        assert controller.model.call.call_args_list == [
            mocker.call("MetaEventFitter", "ef1", "fit_events", 0, False, None, None),
            mocker.call("MetaEventFitter", "ef1", "fit_events", 2, False, None, None),
        ]

    def test_each_generator_is_registered_against_its_channel_and_fitter(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        What the bus used to carry as the return function's extra arguments.

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "")

        assert controller.model.set_generator.call_args_list == [
            mocker.call("gen0", 0, "ef1", "MetaEventFitter"),
            mocker.call("gen1", 1, "ef1", "MetaEventFitter"),
        ]

    def test_the_generators_run_once_for_the_fitter(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Registration and running stay separate steps, as through the bus.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "")

        controller.model.run_generators.assert_called_once_with("ef1")

    def test_a_named_filter_is_fetched_once_and_passed_to_every_channel(
        self, controller: EventAnalysisController
    ) -> None:
        """
        One fetch for the batch, through the helper now shared with RawData.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["a-callable", "gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "MyFilter")

        fit_calls = [
            call.args
            for call in controller.model.call.call_args_list
            if call.args[2] == "fit_events"
        ]
        assert len(fit_calls) == 2
        for args in fit_calls:
            assert args[5] == "a-callable"

    def test_an_empty_filter_key_fetches_no_callable(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Replaces the old test that asserted the View did not emit get_callable_filter -
        which would have passed trivially once the View stopped emitting anything.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0"]

        controller.start_fitting("ef1", [0], "")

        assert not [
            call
            for call in controller.model.call.call_args_list
            if call.args[2] == "get_callable_filter"
        ]

    def test_a_channel_that_cannot_launch_is_skipped_and_the_rest_run(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Replaces the old test_index_error_logged_not_raised, whose assertion that
        ``run_generators`` was not called became trivially true.

        The behaviour is deliberately different: the View abandoned the whole batch, and
        losing one channel beats losing every channel's fit.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", RuntimeError("boom"), "gen2"]

        controller.start_fitting("ef1", [0, 1, 2], "")

        registered = [
            call.args[1] for call in controller.model.set_generator.call_args_list
        ]
        assert registered == [0, 2]
        controller.model.run_generators.assert_called_once_with("ef1")
        controller.add_text_to_display.emit.assert_called_once()


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
