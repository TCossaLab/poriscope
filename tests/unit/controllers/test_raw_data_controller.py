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
- _load_and_filter reads each channel through call(), dropping what fails (4a)
- load_trace_data / load_psd_data hand the result to the matching view setter
- update_available_plugins resolves eventfinder channels before pushing names (4a)
- _resolve_eventfinder_channels queries every finder and omits one that raises
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
    # Real MetaController signal, needed by any slot that reports a failure to the
    # status panel. Added when Step 4a gave this controller its first such slot.
    ctrl.add_text_to_display = mocker.Mock()
    ctrl.add_text_to_display.emit = mocker.Mock()
    return ctrl


# ----------------------- request_reader_channels (Step 4a) -----------


class TestRequestReaderChannels:
    """
    The Step 4a replacement for a ``global_signal`` round trip.

    The View asked a reader for its channel list over the bus and the answer came back
    seven hops later through a return function named by string. It is one call now, and
    a reader that cannot be read leaves the channel combobox alone instead of being
    reported nowhere the user can see it.
    """

    def test_it_asks_the_reader_through_the_model(
        self, controller: RawDataController
    ) -> None:
        """By key, through the sanctioned API."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_reader_channels("BinaryReader1X_0")

        controller.model.call.assert_called_once_with(
            "MetaReader", "BinaryReader1X_0", "get_channels"
        )

    def test_it_hands_the_channels_to_the_view(
        self, controller: RawDataController
    ) -> None:
        """The result path, which populates the channel combobox."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_reader_channels("BinaryReader1X_0")

        controller.view.update_channels.assert_called_once_with([0, 1, 2])

    def test_a_failure_leaves_the_combobox_alone(
        self, controller: RawDataController
    ) -> None:
        """
        Not repopulated with nothing.

        Clearing it would look to the user like a reader with no channels, which is a
        different and more alarming thing than a reader that could not be read.
        """
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_reader_channels("gone")

        controller.view.update_channels.assert_not_called()

    def test_it_does_not_raise_out_of_the_slot(
        self, controller: RawDataController
    ) -> None:
        """Qt invoked this from a signal; an exception must not escape into C++."""
        controller.model.call.side_effect = RuntimeError("reader failed")

        controller.request_reader_channels("BinaryReader1X_0")


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
    kept_indices: list[int] = [0]

    controller.model.calculate_psd.return_value = (
        Pxx_list,
        rms_list,
        frequency,
        kept_indices,
    )

    controller.calculate_psd(psd_data, samplerate)

    controller.model.calculate_psd.assert_called_once_with(psd_data, samplerate)
    mock_view.set_psd.assert_called_once_with(
        Pxx_list, rms_list, frequency, kept_indices
    )


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


# ------------- trace loading and filtering (Step 4a) -----------------


def test_load_and_filter_returns_data_and_surviving_channels(
    controller: RawDataController,
    mocker: MockerFixture,
) -> None:
    """
    Each channel is read through call(), and the two lists stay index-aligned.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.model.call.side_effect = [250000.0, "ch0", "ch1"]

    data, kept = controller._load_and_filter("R", [0, 1], 2.0, 9.0, "")

    assert (data, kept) == (["ch0", "ch1"], [0, 1])
    assert controller.model.call.call_args_list[1:] == [
        mocker.call("MetaReader", "R", "load_data", 2.0, 9.0, 0),
        mocker.call("MetaReader", "R", "load_data", 2.0, 9.0, 1),
    ]


def test_load_and_filter_drops_a_channel_the_reader_cannot_supply(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    **The stale-read bug this step closes.** The View used to emit ``load_data`` per
    channel and read the answer off ``self.plot_data``, which is written only on success
    and never cleared before the emit. Because the dispatcher swallowed the failure, the
    caller's ``is not None`` guard passed and the *previous* channel's array was appended
    and plotted under this channel's label. ``call()`` raises, so the channel is dropped
    and the lists stay aligned - asserted here as "channel 1 is absent and channel 0's
    data appears exactly once".

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.model.call.side_effect = [250000.0, "ch0", Exception("boom"), "ch2"]

    data, kept = controller._load_and_filter("R", [0, 1, 2], 0.0, 1.0, "")

    assert (data, kept) == (["ch0", "ch2"], [0, 2])
    assert data.count("ch0") == 1
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]


def test_load_and_filter_drops_a_channel_that_returns_none(
    controller: RawDataController,
) -> None:
    """
    A reader that returns None rather than raising is also dropped, as before.

    :param controller: Controller under test.
    """
    controller.model.call.side_effect = [250000.0, None, "ch1"]

    data, kept = controller._load_and_filter("R", [0, 1], 0.0, 1.0, "")

    assert (data, kept) == (["ch1"], [1])


def test_load_and_filter_filters_each_channel_when_asked(
    controller: RawDataController,
    mocker: MockerFixture,
) -> None:
    """
    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.model.call.side_effect = [250000.0, "raw0", "filtered0"]

    data, kept = controller._load_and_filter("R", [0], 0.0, 1.0, "F1")

    assert (data, kept) == (["filtered0"], [0])
    assert controller.model.call.call_args_list[-1] == mocker.call(
        "MetaFilter", "F1", "filter_data", "raw0"
    )


def test_load_and_filter_keeps_the_unfiltered_channel_when_the_filter_fails(
    controller: RawDataController,
) -> None:
    """
    A failed filter yields that channel's own input, not another channel's output.

    This is what the old ``_apply_filter``'s except branch meant to do and could not:
    the dispatcher swallowed the failure, so it returned ``self.plot_data`` - the last
    array any successful filter had parked there.

    :param controller: Controller under test.
    """
    controller.model.call.side_effect = [
        250000.0,
        "raw0",
        "filtered0",
        "raw1",
        Exception("boom"),
    ]

    data, kept = controller._load_and_filter("R", [0, 1], 0.0, 1.0, "F1")

    assert (data, kept) == (["filtered0", "raw1"], [0, 1])


def test_load_and_filter_fetches_the_samplerate_once_per_request(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    The old per-channel ``_load_data`` asked once per channel.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    controller.model.call.side_effect = [250000.0, "ch0", "ch1", "ch2"]

    controller._load_and_filter("R", [0, 1, 2], 0.0, 1.0, "")

    samplerate_calls = [
        c
        for c in controller.model.call.call_args_list
        if c == mocker.call("MetaReader", "R", "get_samplerate")
    ]
    assert len(samplerate_calls) == 1
    mock_view.update_plot_samplerate.assert_called_once_with(250000.0)


def test_load_and_filter_falls_back_to_samplerate_one(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    An unreadable samplerate plots against raw indices, as it did before.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.model.call.side_effect = [Exception("boom"), "ch0"]

    controller._load_and_filter("R", [0], 0.0, 1.0, "")

    mock_view.update_plot_samplerate.assert_called_once_with(1)
    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]


def test_load_trace_data_hands_the_result_back_for_plotting(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    controller._load_and_filter = mocker.Mock(return_value=(["d0"], [0]))

    controller.load_trace_data("R", [0], 3.0, 9.0, "", True)

    mock_view.set_trace_data.assert_called_once_with(["d0"], [0], 3.0, True)


def test_load_psd_data_hands_the_result_back_for_the_psd(
    controller: RawDataController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    :param mocker: Pytest-mock fixture.
    """
    controller._load_and_filter = mocker.Mock(return_value=(["d0"], [0]))

    controller.load_psd_data("R", [0], 3.0, 9.0, "F1")

    mock_view.set_trace_for_psd.assert_called_once_with(["d0"], [0])


# ---------------- eventfinder channel resolution (4a) ----------------


def test_update_available_plugins_registers_channels_before_pushing_names(
    controller: RawDataController,
    mock_view: MagicMock,
) -> None:
    """
    The channel map reaches the View before the plugin names do.

    Stated as an ordering invariant rather than as two independent calls. Populating a
    combobox fires a selection change synchronously, which is the shape that made the
    plugin-instance push order load-bearing earlier on this branch; a test asserting
    only that both calls happened would pass against the wrong order, which is exactly
    how the first regression test for that bug came out too weak.

    :param controller: Controller under test.
    :param mock_view: Mocked raw data view.
    """
    controller.model.call.return_value = [0, 1]
    controller.update_available_plugins({"MetaEventFinder": ["EF1"]})

    names: list[str] = [name for name, _, _ in mock_view.mock_calls]
    assert names.index("register_eventfinder_channels") < names.index(
        "update_available_plugins"
    )


def test_resolve_eventfinder_channels_asks_every_finder(
    controller: RawDataController,
    mocker: MockerFixture,
) -> None:
    """
    Every finder is queried through call(), not only the ones not yet registered.

    :param controller: Controller under test.
    :param mocker: Pytest-mock fixture.
    """
    controller.model.call.return_value = [0, 1]

    resolved = controller._resolve_eventfinder_channels(["EF1", "EF2"])

    assert resolved == {"EF1": [0, 1], "EF2": [0, 1]}
    assert controller.model.call.call_args_list == [
        mocker.call("MetaEventFinder", "EF1", "get_channels"),
        mocker.call("MetaEventFinder", "EF2", "get_channels"),
    ]


def test_resolve_eventfinder_channels_omits_a_finder_that_cannot_answer(
    controller: RawDataController,
) -> None:
    """
    A finder that raises is left out of the map rather than mapped to an empty list.

    The distinction is load-bearing: the View registers defaults for a finder it finds
    in the map and leaves the rest alone, so "did not answer" has to be absence. Mapping
    it to ``[]`` would read as "this finder has no channels" and register nothing while
    also never retrying.

    :param controller: Controller under test.
    """
    controller.model.call.side_effect = [[0], Exception("boom"), [2]]

    resolved = controller._resolve_eventfinder_channels(["EF1", "EF2", "EF3"])

    assert resolved == {"EF1": [0], "EF3": [2]}
    assert "EF2" not in resolved
    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]


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
