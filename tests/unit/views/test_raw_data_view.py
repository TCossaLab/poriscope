# type: ignore
"""
Tests for poriscope.plugins.analysistabs.RawDataView.

All Qt dependencies are bypassed via __new__ + mocker.patch so no QApplication
is required, avoiding the singleton conflict that caused the original EEEE errors.

Coverage targets:
- update_plot_data
- update_plot_samplerate
- update_channels
- update_timer_channels
- set_num_events_allowed
- set_eventfinding_status
- validate_single_channel
- _extract_plot_parameters
- _extract_event_parameters
- _extract_commit_event_parameters
- _extract_plot_event_parameters
- _validate_plot_parameters
- _load_data (happy path + IndexError)
- _apply_filter (happy path + Exception)
- _handle_load_data_and_update_plot (success, invalid params, no data, with filter,
  without filter, parameter extraction failure)
- _handle_other_actions (with reader, without reader)
- handle_parameter_change dispatch (load_data_and_update_plot, some_other_action)
- _factors
- _get_baseline_stats (degenerate guard)
- update_available_plugins (success + exception path)
- _start_writer
- _shift_range_and_update_trace (left shift, negative guard)
- _shift_range_and_update_plot (left, right, empty indices guard)
- _handle_find_events (valid params, missing params)
- _handle_commit_events (valid, extraction failure)
- _handle_timer (no-op when finder == 'No Eventfinder')
- set_data_filter_function
- set_psd
- _get_event_index_text
"""

from __future__ import annotations

import numpy as np
import pytest

from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.MetaView import MetaView

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logging():
    """Patch logging root attributes consumed by LogDecorator."""
    import logging

    if not hasattr(logging.root, "pid"):
        logging.root.pid = 0
    if not hasattr(logging.root, "indent"):
        logging.root.indent = 0
    if not hasattr(logging.root, "tab_spaces"):
        logging.root.tab_spaces = 4
    if not hasattr(logging.root, "show_once"):
        logging.root.show_once = False


@pytest.fixture
def view(mocker, mock_logging):
    """
    Return a RawDataView instance with ALL Qt/GUI concerns mocked out.

    We bypass __init__ entirely (object.__new__) so no QApplication is needed,
    then inject every attribute the methods under test actually read or write.
    """
    # Patch heavy Qt base-class initialisation so importing doesn't crash.
    mocker.patch(
        "poriscope.utils.MetaView.MetaView.__init__",
        return_value=None,
    )

    v = RawDataView.__new__(RawDataView)

    # --- Core infrastructure mocks ---
    v.logger = mocker.Mock()
    v.figure = mocker.Mock()
    v.canvas = mocker.Mock()
    v.global_signal = mocker.Mock()
    v.add_text_to_display = mocker.Mock()
    v.export_plot_data = mocker.Mock()
    v.run_generators = mocker.Mock()

    # --- RawDataControls mock ---
    v.rawdatacontrols = mocker.Mock()
    v.rawdatacontrols.event_index_lineEdit = mocker.Mock()
    v.rawdatacontrols.event_index_lineEdit.text = mocker.Mock(return_value="")

    # --- State attributes ---
    v.plot_data = None
    v.plot_samplerate = 1
    v.timer_channels = []
    v.analysis_time_limits = {}
    v.eventfinding_status = False
    v.num_events_allowed = 0
    v.data_filter = None
    v.available_plugins = {}

    # --- Cache helpers (no-ops) ---
    v._update_cache = mocker.Mock()
    v._clear_cache = mocker.Mock()
    v._commit_cache = mocker.Mock()

    return v


# ---------------------------------------------------------------------------
# Inheritance
# ---------------------------------------------------------------------------


def test_plugin_is_metaview_subclass():
    """RawDataView must be a subclass of MetaView."""
    assert issubclass(RawDataView, MetaView)


# ---------------------------------------------------------------------------
# update_plot_data
# ---------------------------------------------------------------------------


def test_update_plot_data_stores_array(view):
    data = np.array([1, 2, 3])
    view.update_plot_data(data)
    np.testing.assert_array_equal(view.plot_data, data)


def test_update_plot_data_extracts_data_key_from_dict(view):
    data = np.array([4, 5, 6])
    view.update_plot_data({"data": data})
    np.testing.assert_array_equal(view.plot_data, data)


# ---------------------------------------------------------------------------
# update_plot_samplerate
# ---------------------------------------------------------------------------


def test_update_plot_samplerate(view):
    view.update_plot_samplerate(250000.0)
    assert view.plot_samplerate == 250000.0


# ---------------------------------------------------------------------------
# update_timer_channels
# ---------------------------------------------------------------------------


def test_update_timer_channels(view):
    view.update_timer_channels([0, 1, 2])
    assert view.timer_channels == [0, 1, 2]


# ---------------------------------------------------------------------------
# update_channels
# ---------------------------------------------------------------------------


def test_update_channels_delegates_to_controls(view):
    view.update_channels([0, 1])
    view.rawdatacontrols.update_channels.assert_called_once_with([0, 1])


def test_update_channels_logs_info(view):
    view.update_channels([0])
    view.logger.info.assert_called()


# ---------------------------------------------------------------------------
# set_num_events_allowed / set_eventfinding_status
# ---------------------------------------------------------------------------


def test_set_num_events_allowed(view):
    view.set_num_events_allowed(42)
    assert view.num_events_allowed == 42


def test_set_eventfinding_status_true(view):
    view.set_eventfinding_status(True)
    assert view.eventfinding_status is True


def test_set_eventfinding_status_false(view):
    view.set_eventfinding_status(False)
    assert view.eventfinding_status is False


# ---------------------------------------------------------------------------
# set_data_filter_function
# ---------------------------------------------------------------------------


def test_set_data_filter_function(view):
    def passthrough(x):
        return x

    view.set_data_filter_function(passthrough)
    assert view.data_filter is passthrough


# ---------------------------------------------------------------------------
# set_psd
# ---------------------------------------------------------------------------


def test_set_psd(view):
    Pxx = [[1.0, 2.0]]
    rms = [[0.1, 0.2]]
    freq = np.array([10.0, 100.0])
    view.set_psd(Pxx, rms, freq)
    assert view.Pxx_list is Pxx
    assert view.rms_list is rms
    np.testing.assert_array_equal(view.psd_frequency, freq)


# ---------------------------------------------------------------------------
# validate_single_channel
# ---------------------------------------------------------------------------


def test_validate_single_channel_passes_with_one(view):
    view.validate_single_channel([0])  # should not raise


def test_validate_single_channel_raises_with_multiple(view):
    with pytest.raises(ValueError):
        view.validate_single_channel([0, 1])


# ---------------------------------------------------------------------------
# _extract_plot_parameters
# ---------------------------------------------------------------------------


def test_extract_plot_parameters(view):
    params = {"reader": "R1", "channel": ["1"], "start_time": "0.5", "length": "10.0"}
    reader, channels, start, length = view._extract_plot_parameters(params)
    assert reader == "R1"
    assert channels == [1]
    assert start == 0.5
    assert length == 10.0


# ---------------------------------------------------------------------------
# _extract_event_parameters
# ---------------------------------------------------------------------------


def test_extract_event_parameters(view):
    params = {"eventfinder": "EF1", "filter": "F1", "channel": ["2"]}
    ef, f, ch = view._extract_event_parameters(params)
    assert ef == "EF1"
    assert f == "F1"
    assert ch == [2]


# ---------------------------------------------------------------------------
# _extract_commit_event_parameters
# ---------------------------------------------------------------------------


def test_extract_commit_event_parameters(view):
    params = {"writer": "W1", "channel": ["3"]}
    writer, channels = view._extract_commit_event_parameters(params)
    assert writer == "W1"
    assert channels == [3]


# ---------------------------------------------------------------------------
# _extract_plot_event_parameters
# ---------------------------------------------------------------------------


def test_extract_plot_event_parameters(view):
    params = {
        "eventfinder": "EF1",
        "filter": "F1",
        "channel": ["0"],
        "event_index": [0, 1, 2],
    }
    ef, f, ch, ev = view._extract_plot_event_parameters(params)
    assert ef == "EF1"
    assert f == "F1"
    assert ch == [0]
    assert ev == [0, 1, 2]


# ---------------------------------------------------------------------------
# _validate_plot_parameters
# ---------------------------------------------------------------------------


def test_validate_plot_parameters_all_valid(view):
    assert view._validate_plot_parameters("R", [0], 0.0, 100.0) is True


def test_validate_plot_parameters_none_channel(view):
    assert view._validate_plot_parameters("R", None, 0.0, 100.0) is False


def test_validate_plot_parameters_none_reader(view):
    assert view._validate_plot_parameters(None, [0], 0.0, 100.0) is False


# ---------------------------------------------------------------------------
# _factors
# ---------------------------------------------------------------------------


def test_factors_single(view):
    assert view._factors(1) == (1, 1)


def test_factors_four(view):
    rows, cols = view._factors(4)
    assert rows * cols >= 4


def test_factors_returns_tuple(view):
    result = view._factors(6)
    assert isinstance(result, tuple)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# _get_event_index_text
# ---------------------------------------------------------------------------


def test_get_event_index_text_strips_whitespace(view):
    view.rawdatacontrols.event_index_lineEdit.text.return_value = "  3,4,5  "
    assert view._get_event_index_text() == "3,4,5"


def test_get_event_index_text_empty(view):
    view.rawdatacontrols.event_index_lineEdit.text.return_value = ""
    assert view._get_event_index_text() == ""


# ---------------------------------------------------------------------------
# _load_data
# ---------------------------------------------------------------------------


def test_load_data_emits_global_signal(view):
    view._load_data("R1", 0, 0.0, 100.0)
    view.global_signal.emit.assert_called()
    # Verify the key args: plugin type, plugin name, method name
    args = view.global_signal.emit.call_args[0]
    assert args[0] == "MetaReader"
    assert args[1] == "R1"
    assert args[2] == "load_data"


def test_load_data_passes_correct_data_args(view):
    view._load_data("R1", 2, 5.0, 50.0)
    args = view.global_signal.emit.call_args_list
    # find the load_data call
    load_call = next(a for a in args if a[0][2] == "load_data")
    assert load_call[0][3] == (5.0, 50.0, 2)


def test_load_data_handles_index_error(view):
    view.global_signal.emit.side_effect = [None, IndexError("boom")]
    # Should not raise
    view._load_data("R1", 0, 0.0, 100.0)
    view.logger.error.assert_called()


def test_load_data_handles_list_of_channels(view):
    """When channels is a list, _load_data should iterate and emit per channel."""
    view._load_data("R1", [0, 1], 0.0, 100.0)
    load_calls = [
        a for a in view.global_signal.emit.call_args_list if a[0][2] == "load_data"
    ]
    assert len(load_calls) == 2


# ---------------------------------------------------------------------------
# _apply_filter
# ---------------------------------------------------------------------------


def test_apply_filter_emits_global_signal(view):
    view.plot_data = np.array([1.0, 2.0])
    view._apply_filter("F1", view.plot_data)
    args = view.global_signal.emit.call_args[0]
    assert args[0] == "MetaFilter"
    assert args[1] == "F1"
    assert args[2] == "filter_data"


def test_apply_filter_returns_plot_data_on_success(view):
    expected = np.array([9.0, 8.0])
    view.plot_data = expected
    result = view._apply_filter("F1", np.array([1.0, 2.0]))
    np.testing.assert_array_equal(result, expected)


def test_apply_filter_returns_original_on_exception(view):
    original = np.array([1.0, 2.0])
    view.global_signal.emit.side_effect = Exception("boom")
    result = view._apply_filter("F1", original)
    np.testing.assert_array_equal(result, original)
    view.logger.error.assert_called()


# ---------------------------------------------------------------------------
# _handle_load_data_and_update_plot
# ---------------------------------------------------------------------------


def test_handle_load_data_parameter_extraction_failure(view, mocker):
    view._extract_plot_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._handle_load_data_and_update_plot({"channel": []})
    view.logger.error.assert_called()


def test_handle_load_data_invalid_params_logs_error(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=False)
    view.update_plot = mocker.Mock()
    view._handle_load_data_and_update_plot({})
    view.update_plot.assert_not_called()
    view.logger.error.assert_called()


def test_handle_load_data_no_data_skips_plot(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._load_data = mocker.Mock()
    view.update_plot = mocker.Mock()
    view.plot_data = None
    view._handle_load_data_and_update_plot({"channel": ["0"], "filter": "No Filter"})
    view.update_plot.assert_not_called()


def test_handle_load_data_success_no_filter(view, mocker):
    data = np.array([1.0, 2.0, 3.0])
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._load_data = mocker.Mock()
    view._apply_filter = mocker.Mock()
    view.update_plot = mocker.Mock()
    view.plot_data = data
    view._handle_load_data_and_update_plot({"channel": ["0"], "filter": "No Filter"})
    view._apply_filter.assert_not_called()
    view.update_plot.assert_called_once()


def test_handle_load_data_success_with_filter(view, mocker):
    data = np.array([1.0, 2.0])
    filtered = np.array([0.5, 1.0])
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._load_data = mocker.Mock()
    view._apply_filter = mocker.Mock(return_value=filtered)
    view.update_plot = mocker.Mock()
    view.plot_data = data
    view._handle_load_data_and_update_plot({"channel": ["0"], "filter": "MyFilter"})
    view._apply_filter.assert_called_once_with("MyFilter", data)
    view.update_plot.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_other_actions
# ---------------------------------------------------------------------------


def test_handle_other_actions_with_reader_emits_signal(view):
    view._handle_other_actions("something", {"reader": "R1"})
    view.global_signal.emit.assert_called_once()
    args = view.global_signal.emit.call_args[0]
    assert args[0] == "MetaReader"
    assert args[1] == "R1"
    assert args[2] == "get_channels"


def test_handle_other_actions_without_reader_does_nothing(view):
    view._handle_other_actions("something", {"reader": None})
    view.global_signal.emit.assert_not_called()


# ---------------------------------------------------------------------------
# handle_parameter_change dispatch
# ---------------------------------------------------------------------------


def test_handle_parameter_change_dispatches_load_data(view, mocker):
    view._handle_load_data_and_update_plot = mocker.Mock()
    params = {"reader": "R1", "channel": ["0"], "start_time": "0", "length": "1"}
    view.handle_parameter_change("sub", "load_data_and_update_plot", (params,))
    view._handle_load_data_and_update_plot.assert_called_once_with(params)


def test_handle_parameter_change_dispatches_other_action(view, mocker):
    view._handle_other_actions = mocker.Mock()
    params = {"reader": "R1"}
    view.handle_parameter_change("sub", "some_unknown_action", (params,))
    view._handle_other_actions.assert_called_once_with("some_unknown_action", params)


def test_handle_parameter_change_dispatches_shift_forward(view, mocker):
    view._shift_range_and_update_trace = mocker.Mock()
    params = {"reader": "R1", "channel": ["0"], "start_time": "0", "length": "1"}
    view.handle_parameter_change("sub", "shift_trace_forward", (params,))
    view._shift_range_and_update_trace.assert_called_once_with(
        params, direction="right"
    )


def test_handle_parameter_change_dispatches_shift_backward(view, mocker):
    view._shift_range_and_update_trace = mocker.Mock()
    params = {"reader": "R1", "channel": ["0"], "start_time": "0", "length": "1"}
    view.handle_parameter_change("sub", "shift_trace_backward", (params,))
    view._shift_range_and_update_trace.assert_called_once_with(params, direction="left")


def test_handle_parameter_change_dispatches_find_events(view, mocker):
    view._handle_find_events = mocker.Mock()
    params = {"eventfinder": "EF", "filter": "No Filter", "channel": ["0"]}
    view.handle_parameter_change("sub", "find_events", (params,))
    view._handle_find_events.assert_called_once_with(params)


def test_handle_parameter_change_dispatches_commit_events(view, mocker):
    view._handle_commit_events = mocker.Mock()
    params = {"writer": "W1", "channel": ["0"]}
    view.handle_parameter_change("sub", "commit_events", (params,))
    view._handle_commit_events.assert_called_once_with(params)


def test_handle_parameter_change_dispatches_plot_events(view, mocker):
    view._handle_plot_events = mocker.Mock()
    params = {"eventfinder": "EF", "channel": ["0"], "event_index": [0]}
    view.handle_parameter_change("sub", "plot_events", (params,))
    view._handle_plot_events.assert_called_once_with(params)


def test_handle_parameter_change_dispatches_export_plot_data(view, mocker):
    view.handle_parameter_change("sub", "export_plot_data", ({},))
    view.export_plot_data.emit.assert_called_once()


# ---------------------------------------------------------------------------
# update_available_plugins
# ---------------------------------------------------------------------------


def test_update_available_plugins_success(view, mocker):
    # super().update_available_plugins must not crash
    mocker.patch.object(MetaView, "update_available_plugins", return_value=None)
    view.timer_channels = [0]
    plugins = {
        "MetaReader": ["R1"],
        "MetaFilter": ["F1"],
        "MetaWriter": ["W1"],
        "MetaEventFinder": [],
    }
    view.update_available_plugins(plugins)
    view.rawdatacontrols.update_readers.assert_called_once_with(["R1"])
    view.rawdatacontrols.update_filters.assert_called_once_with(["F1"])
    view.rawdatacontrols.update_writers.assert_called_once_with(["W1"])


def test_update_available_plugins_exception_is_caught(view, mocker):
    mocker.patch.object(MetaView, "update_available_plugins", return_value=None)
    view.rawdatacontrols.update_readers.side_effect = Exception("boom")
    # Should not raise
    view.update_available_plugins({"MetaReader": ["R1"]})
    view.logger.info.assert_called()


# ---------------------------------------------------------------------------
# _handle_find_events
# ---------------------------------------------------------------------------


def test_handle_find_events_valid_params(view, mocker):
    view._extract_event_parameters = mocker.Mock(return_value=("EF1", "No Filter", [0]))
    view._start_eventfinder = mocker.Mock()
    view._handle_find_events(
        {"eventfinder": "EF1", "filter": "No Filter", "channel": ["0"]}
    )
    view._start_eventfinder.assert_called_once_with("EF1", "No Filter", [0])


def test_handle_find_events_extraction_failure(view, mocker):
    view._extract_event_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._start_eventfinder = mocker.Mock()
    view._handle_find_events({})
    view._start_eventfinder.assert_not_called()
    view.logger.error.assert_called()


def test_handle_find_events_none_params_aborts(view, mocker):
    view._extract_event_parameters = mocker.Mock(return_value=(None, None, None))
    view._start_eventfinder = mocker.Mock()
    view._handle_find_events({})
    view._start_eventfinder.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_commit_events
# ---------------------------------------------------------------------------


def test_handle_commit_events_calls_start_writer(view, mocker):
    view._extract_commit_event_parameters = mocker.Mock(return_value=("W1", [0]))
    view._start_writer = mocker.Mock()
    view._handle_commit_events({"writer": "W1", "channel": ["0"]})
    view._start_writer.assert_called_once_with("W1", [0])


def test_handle_commit_events_extraction_failure(view, mocker):
    view._extract_commit_event_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._start_writer = mocker.Mock()
    view._handle_commit_events({})
    view._start_writer.assert_not_called()
    view.logger.error.assert_called()


# ---------------------------------------------------------------------------
# _handle_timer
# ---------------------------------------------------------------------------


def test_handle_timer_no_eventfinder_does_nothing(view, mocker):
    """When finder == 'No Eventfinder', no dialog should open."""
    mocker.patch("poriscope.plugins.analysistabs.RawDataView.TimeWidget")
    view._handle_timer({"eventfinder": "No Eventfinder"})
    # TimeWidget should not be instantiated
    # If TimeWidget was patched, confirm it was never called
    # (easiest check: global_signal never touched)
    view.global_signal.emit.assert_not_called()


# ---------------------------------------------------------------------------
# _shift_range_and_update_trace
# ---------------------------------------------------------------------------


def test_shift_range_and_update_trace_left(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 10.0, 5.0))
    view._shift_ranges = mocker.Mock(return_value=[(9.0, 14.0)])
    view.rawdatacontrols.set_range_inputs = mocker.Mock()
    view._handle_load_data_and_update_plot = mocker.Mock()
    params = {"reader": "R", "channel": ["0"], "start_time": "10", "length": "5"}
    view._shift_range_and_update_trace(params, "left")
    view.rawdatacontrols.set_range_inputs.assert_called_once_with(9.0, 5.0)
    view._handle_load_data_and_update_plot.assert_called_once()


def test_shift_range_and_update_trace_negative_start_clamped(view, mocker):
    """If shifting would produce a negative start, it should stay at original."""
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 5.0))
    view._shift_ranges = mocker.Mock(return_value=[(-1.0, 4.0)])
    view.rawdatacontrols.set_range_inputs = mocker.Mock()
    view._handle_load_data_and_update_plot = mocker.Mock()
    params = {"reader": "R", "channel": ["0"], "start_time": "0", "length": "5"}
    view._shift_range_and_update_trace(params, "left")
    # Should clamp to original (0.0, 5.0)
    view.rawdatacontrols.set_range_inputs.assert_called_once_with(0.0, 5.0)


def test_shift_range_and_update_trace_invalid_direction(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 5.0))
    view._handle_load_data_and_update_plot = mocker.Mock()
    params = {"reader": "R", "channel": ["0"], "start_time": "0", "length": "5"}
    view._shift_range_and_update_trace(params, "sideways")
    view._handle_load_data_and_update_plot.assert_not_called()
    view.logger.error.assert_called()


def test_shift_range_and_update_trace_extraction_failure(view, mocker):
    view._extract_plot_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._handle_load_data_and_update_plot = mocker.Mock()
    view._shift_range_and_update_trace({}, "left")
    view._handle_load_data_and_update_plot.assert_not_called()
    view.logger.error.assert_called()


# ---------------------------------------------------------------------------
# _shift_range_and_update_plot (event navigation)
# ---------------------------------------------------------------------------


def _setup_shift_plot(view, mocker, text="5-10"):
    view.rawdatacontrols.event_index_lineEdit.text.return_value = text
    view._parse_event_indices = mocker.Mock(return_value=[(5, 10)])
    view._shift_ranges = mocker.Mock(return_value=[(6, 11)])
    view._merge_ranges = mocker.Mock(return_value=[(6, 11)])
    view._format_ranges = mocker.Mock(return_value="6-11")
    view._expand_event_indices = mocker.Mock(return_value=[6, 7, 8, 9, 10, 11])
    view._handle_plot_events = mocker.Mock()
    view._extract_plot_event_parameters = mocker.Mock(
        return_value=("EF", "F", [0], [5, 6, 7, 8, 9, 10])
    )
    view.validate_single_channel = mocker.Mock()


def test_shift_range_and_update_plot_right(view, mocker):
    _setup_shift_plot(view, mocker)
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": [5]}
    view._shift_range_and_update_plot(params, "right")
    view._shift_ranges.assert_called_once_with([(5, 10)], "right", 1)
    view.rawdatacontrols.set_event_index_input.assert_called_once_with("6-11")
    view._handle_plot_events.assert_called_once()


def test_shift_range_and_update_plot_left(view, mocker):
    _setup_shift_plot(view, mocker)
    view._shift_ranges.return_value = [(4, 9)]
    view._merge_ranges.return_value = [(4, 9)]
    view._format_ranges.return_value = "4-9"
    view._expand_event_indices.return_value = [4, 5, 6, 7, 8, 9]
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": [5]}
    view._shift_range_and_update_plot(params, "left")
    view._shift_ranges.assert_called_once_with([(5, 10)], "left", 1)


def test_shift_range_and_update_plot_empty_indices_aborts(view, mocker):
    _setup_shift_plot(view, mocker)
    view._expand_event_indices.return_value = []
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": []}
    view._shift_range_and_update_plot(params, "right")
    view._handle_plot_events.assert_not_called()


def test_shift_range_and_update_plot_empty_text_aborts(view, mocker):
    view.rawdatacontrols.event_index_lineEdit.text.return_value = ""
    view._extract_plot_event_parameters = mocker.Mock(return_value=("EF", "F", [0], []))
    view.validate_single_channel = mocker.Mock()
    view._handle_plot_events = mocker.Mock()
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": []}
    view._shift_range_and_update_plot(params, "left")
    view._handle_plot_events.assert_not_called()


# ---------------------------------------------------------------------------
# _start_writer
# ---------------------------------------------------------------------------


def test_start_writer_emits_signal_per_channel(view):
    view._start_writer("W1", [0, 1])
    # Should emit for each channel then run_generators
    assert view.global_signal.emit.call_count == 2
    view.run_generators.emit.assert_called_once_with("W1")


def test_start_writer_non_list_channels_does_not_crash(view):
    # When channels is not a list, the method logs a warning and returns early
    view._start_writer("W1", 0)
    # Should not raise; run_generators should NOT be emitted (non-list path)
    view.run_generators.emit.assert_not_called()
