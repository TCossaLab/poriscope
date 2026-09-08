# type: ignore
"""
Tests for poriscope.plugins.analysistabs.RawDataView.

All Qt dependencies are bypassed via __new__ + mocker.patch so no QApplication
is required, avoiding the singleton conflict that caused the original EEEE errors.

Coverage targets:
- update_plot_data
- update_plot_samplerate
- update_channels
- register_eventfinder_channels
- set_num_events_allowed
- set_eventfinding_status
- validate_single_channel
- _extract_plot_parameters
- _extract_event_parameters
- _extract_commit_event_parameters
- _extract_plot_event_parameters
- _validate_plot_parameters
- _filter_key (every "no filter" spelling)
- _handle_load_data_and_update_plot / set_trace_data (Step 4a intent + result)
- _handle_load_data_and_update_psd / set_trace_for_psd (Step 4a intent + result)
- _handle_other_actions (with reader, without reader)
- handle_parameter_change dispatch (load_data_and_update_plot, some_other_action)
- _factors
- update_available_plugins (success + exception path)
- _shift_range_and_update_trace (left shift, negative guard)
- _shift_range_and_update_plot (left, right, empty indices guard)
- _handle_find_events (valid params, missing params)
- _handle_commit_events (valid, extraction failure)
- _handle_timer (no-op when finder == 'No Eventfinder')
- set_data_filter_function
- set_psd
- _get_event_index_text

Not covered here: the numeric methods ``_get_baseline_stats``, ``_gaussian_fit``
and ``_gaussian`` live in ``test_raw_data_view_characterization.py``. This roster
used to claim ``_get_baseline_stats (degenerate guard)`` while no such test
existed anywhere in the repository.
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
    # Step 4a's intent signals. Mocked by hand like the rest here: this fixture builds
    # the view with __new__, so a class-level Signal has no C++ object behind it and
    # emitting one would raise "Signal source has been deleted".
    v.reader_channels_requested = mocker.Mock()
    v.baseline_stats_requested = mocker.Mock()
    v.trace_data_requested = mocker.Mock()
    v.psd_data_requested = mocker.Mock()
    v.event_plot_requested = mocker.Mock()
    v.commit_requested = mocker.Mock()
    v.calculate_psd = mocker.Mock()
    v.export_plot_data = mocker.Mock()
    v.run_generators = mocker.Mock()

    # --- RawDataControls mock ---
    v.rawdatacontrols = mocker.Mock()
    v.rawdatacontrols.event_index_lineEdit = mocker.Mock()
    v.rawdatacontrols.event_index_lineEdit.text = mocker.Mock(return_value="")

    # --- State attributes ---
    v.plot_data = None
    v.plot_samplerate = 1
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
# register_eventfinder_channels
# ---------------------------------------------------------------------------


def test_register_eventfinder_channels_gives_a_new_finder_defaults(view):
    view.register_eventfinder_channels({"EF1": [0, 2]})
    assert view.analysis_time_limits == {
        "EF1": {0: {"start": 0, "end": 0}, 2: {"start": 0, "end": 0}}
    }


def test_register_eventfinder_channels_keeps_ranges_the_user_already_set(view):
    """A finder already registered is not reset by a later plugin-registry push."""
    view.analysis_time_limits = {"EF1": {0: {"start": 1.5, "end": 3.0}}}
    view.register_eventfinder_channels({"EF1": [0, 1, 2]})
    assert view.analysis_time_limits == {"EF1": {0: {"start": 1.5, "end": 3.0}}}


def test_register_eventfinder_channels_leaves_a_silent_finder_unregistered(view):
    """
    No channels means no registration, so the next push retries the finder.

    This is the surviving half of the 1.9.0 fix for ``timer_channels``: the finder key
    used to be registered before its channels were known, so one failed lookup poisoned
    that finder's time limits permanently.
    """
    view.register_eventfinder_channels({"EF1": []})
    assert view.analysis_time_limits == {}


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
    kept_indices = [0]
    view.set_psd(Pxx, rms, freq, kept_indices)
    assert view.Pxx_list is Pxx
    assert view.rms_list is rms
    np.testing.assert_array_equal(view.psd_frequency, freq)
    assert view.psd_kept_indices is kept_indices


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
# _filter_key
# ---------------------------------------------------------------------------


def test_filter_key_reads_the_selected_filter(view):
    assert view._filter_key({"filter": "MyFilter"}) == "MyFilter"


@pytest.mark.parametrize("parameters", [{}, {"filter": None}, {"filter": "No Filter"}])
def test_filter_key_collapses_every_no_filter_spelling(view, parameters):
    """The controls panel reports "none" three ways; all mean no filtering."""
    assert view._filter_key(parameters) == ""


# ---------------------------------------------------------------------------
# _handle_load_data_and_update_plot / set_trace_data  (Step 4a)
# ---------------------------------------------------------------------------


def test_handle_load_data_parameter_extraction_failure(view, mocker):
    view._extract_plot_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._handle_load_data_and_update_plot({"channel": []})
    view.logger.error.assert_called()
    view.trace_data_requested.emit.assert_not_called()


def test_handle_load_data_invalid_params_requests_nothing(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=False)
    view._handle_load_data_and_update_plot({})
    view.trace_data_requested.emit.assert_not_called()
    view.logger.error.assert_called()


def test_handle_load_data_emits_a_typed_intent(view, mocker):
    """
    Step 4a: the orchestrator asks, and stops. Loading is the Controller's.
    """
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0, 1], 2.0, 100.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._handle_load_data_and_update_plot({"channel": ["0"], "filter": "MyFilter"})
    view.trace_data_requested.emit.assert_called_once_with(
        "R", [0, 1], 2.0, 100.0, "MyFilter", False
    )


def test_handle_load_data_passes_the_baseline_flag_through(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 0.0, 1.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._handle_load_data_and_update_plot({"channel": ["0"]}, baseline=True)
    assert view.trace_data_requested.emit.call_args[0][-1] is True


def test_handle_load_data_makes_no_plugin_call_of_its_own(view, mocker):
    """Step 4a: the bus round trip per channel is gone from this path entirely."""
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0, 1], 0.0, 1.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._handle_load_data_and_update_plot({"channel": ["0"]})
    view.global_signal.emit.assert_not_called()


def test_set_trace_data_reports_when_nothing_loaded(view, mocker):
    view.update_plot = mocker.Mock()
    view.set_trace_data([], [], 0.0, False)
    view.update_plot.assert_not_called()
    view.baseline_stats_requested.emit.assert_not_called()
    view.add_text_to_display.emit.assert_called_once()


def test_set_trace_data_plots_what_the_controller_loaded(view, mocker):
    data = [np.array([1.0, 2.0])]
    view.update_plot = mocker.Mock()
    view.set_trace_data(data, [0], 3.0, False)
    view.update_plot.assert_called_once_with(data, [0], 3.0)
    view.baseline_stats_requested.emit.assert_not_called()


def test_set_trace_data_asks_for_baseline_stats_instead_when_wanted(view, mocker):
    data = [np.array([1.0, 2.0])]
    view.update_plot = mocker.Mock()
    view.set_trace_data(data, [0], 3.0, True)
    view.baseline_stats_requested.emit.assert_called_once_with(data, [0], 3.0)
    view.update_plot.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_load_data_and_update_psd / set_trace_for_psd  (Step 4a)
# ---------------------------------------------------------------------------


def test_handle_load_data_psd_emits_a_typed_intent(view, mocker):
    view._extract_plot_parameters = mocker.Mock(return_value=("R", [0], 1.0, 9.0))
    view._validate_plot_parameters = mocker.Mock(return_value=True)
    view._handle_load_data_and_update_psd({"channel": ["0"], "filter": "No Filter"})
    view.psd_data_requested.emit.assert_called_once_with("R", [0], 1.0, 9.0, "")
    view.global_signal.emit.assert_not_called()


def test_set_trace_for_psd_reports_when_nothing_loaded(view, mocker):
    view.update_psd = mocker.Mock()
    view.set_trace_for_psd([], [])
    view.update_psd.assert_not_called()
    view.calculate_psd.emit.assert_not_called()
    view.add_text_to_display.emit.assert_called_once()


def test_set_trace_for_psd_computes_and_draws(view, mocker):
    """
    The PSD computation path itself is unchanged by 4a and still reads back off the
    attributes set_psd parks, which is safe because that connection is direct.
    """
    data = [np.array([1.0, 2.0])]
    view.update_psd = mocker.Mock()
    view.plot_samplerate = 100.0
    view.psd_kept_indices = [0]
    view.Pxx_list = ["pxx"]
    view.rms_list = ["rms"]
    view.psd_frequency = "freq"
    view.set_trace_for_psd(data, [7])
    view.calculate_psd.emit.assert_called_once_with(data, 100.0)
    view.update_psd.assert_called_once_with(["pxx"], ["rms"], "freq", [7])


# ---------------------------------------------------------------------------
# _handle_other_actions
# ---------------------------------------------------------------------------


def test_handle_other_actions_with_reader_requests_its_channels(view):
    """
    Step 4a: an intent naming the reader, not a bus call describing the dispatch.

    The View no longer names the plugin method or the return function - which is the
    point, since it was naming both by string across seven hops.
    """
    view._handle_other_actions("something", {"reader": "R1"})

    view.reader_channels_requested.emit.assert_called_once_with("R1")


def test_handle_other_actions_without_reader_does_nothing(view):
    """The placeholder is a normal empty state, not a plugin key."""
    view._handle_other_actions("something", {"reader": None})

    view.reader_channels_requested.emit.assert_not_called()


def test_handle_other_actions_ignores_the_placeholder_reader(view):
    """ "No Reader" is what the combobox shows before anything is chosen."""
    view._handle_other_actions("something", {"reader": "No Reader"})

    view.reader_channels_requested.emit.assert_not_called()


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


def test_update_available_plugins_makes_no_plugin_call_of_its_own(view, mocker):
    """
    Step 4a: populating the comboboxes reaches no plugin, and registers no finder.

    This method used to emit ``global_signal`` once per unregistered finder and read the
    answer back off ``self.timer_channels`` - an emit-then-read nested inside a push the
    Controller was already running. ``RawDataController`` resolves the channels now, so
    what is left here is combobox population and nothing else.
    """
    mocker.patch.object(MetaView, "update_available_plugins", return_value=None)

    view.update_available_plugins(
        {"MetaReader": ["R1"], "MetaEventFinder": ["EF1", "EF2"]}
    )

    view.global_signal.emit.assert_not_called()
    assert view.analysis_time_limits == {}


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


def test_handle_commit_events_emits_a_typed_intent(view, mocker):
    """Step 4a: the commit call itself is the Controller's."""
    view._extract_commit_event_parameters = mocker.Mock(return_value=("W1", [0]))
    view._handle_commit_events({"writer": "W1", "channel": ["0"]})
    view.commit_requested.emit.assert_called_once_with("W1", [0])


def test_handle_commit_events_normalises_a_bare_channel(view, mocker):
    """``_start_writer`` used to coerce this; the intent carries a list either way."""
    view._extract_commit_event_parameters = mocker.Mock(return_value=("W1", 0))
    view._handle_commit_events({"writer": "W1", "channel": ["0"]})
    view.commit_requested.emit.assert_called_once_with("W1", [0])


def test_handle_commit_events_extraction_failure(view, mocker):
    view._extract_commit_event_parameters = mocker.Mock(side_effect=ValueError("bad"))
    view._handle_commit_events({})
    view.commit_requested.emit.assert_not_called()
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


def test_shift_below_zero_is_reported_on_the_status_panel(view, mocker):
    """
    Declining the shift is correct; saying so only on the console was not.

    Shifting the event index left past 0 expands to nothing, which the method has always
    logged as "Indices must be positive" - a string an EventAnalysis e2e test pins - while
    the user saw the arrow simply stop responding.
    """
    _setup_shift_plot(view, mocker)
    view._expand_event_indices.return_value = []
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": [0]}

    view._shift_range_and_update_plot(params, "left")

    view._handle_plot_events.assert_not_called()
    view.add_text_to_display.emit.assert_called_once()
    assert "below 0" in view.add_text_to_display.emit.call_args[0][0]


def test_shift_range_and_update_plot_empty_text_aborts(view, mocker):
    view.rawdatacontrols.event_index_lineEdit.text.return_value = ""
    view._extract_plot_event_parameters = mocker.Mock(return_value=("EF", "F", [0], []))
    view.validate_single_channel = mocker.Mock()
    view._handle_plot_events = mocker.Mock()
    params = {"eventfinder": "EF", "filter": "F", "channel": ["0"], "event_index": []}
    view._shift_range_and_update_plot(params, "left")
    view._handle_plot_events.assert_not_called()




# ---------------------------------------------------------------------------
# the unfiltered-run confirmation
# ---------------------------------------------------------------------------


def test_find_events_asks_before_running_unfiltered(view, mocker):
    """
    Running an event finder with no filter can register every sample as an event.

    On a noisy trace that grinds for a very long time and is easy to mistake for a hang.
    Cancelling does work - the abort flag is read at every chunk boundary - but a chunk
    holding that many events takes long enough that it can look unresponsive. So the
    launch asks first.
    """
    view._start_eventfinder = mocker.Mock()
    view._extract_event_parameters = mocker.Mock(return_value=("EF1", "No Filter", [0]))
    view.confirm_unfiltered_run = mocker.Mock(return_value=True)

    view._handle_find_events({})

    view.confirm_unfiltered_run.assert_called_once_with("Event finding")
    view._start_eventfinder.assert_called_once()


def test_declining_the_unfiltered_confirmation_runs_nothing(view, mocker):
    """Answering No has to stop the launch, not merely warn about it."""
    view._start_eventfinder = mocker.Mock()
    view._extract_event_parameters = mocker.Mock(return_value=("EF1", "No Filter", [0]))
    view.confirm_unfiltered_run = mocker.Mock(return_value=False)

    view._handle_find_events({})

    view._start_eventfinder.assert_not_called()


def test_a_selected_filter_is_not_second_guessed(view, mocker):
    """The confirmation is about the unfiltered case only; a real filter just runs."""
    view._start_eventfinder = mocker.Mock()
    view._extract_event_parameters = mocker.Mock(
        return_value=("EF1", "LowPass_0", [0])
    )
    view.confirm_unfiltered_run = mocker.Mock(return_value=True)

    view._handle_find_events({})

    view.confirm_unfiltered_run.assert_not_called()
    view._start_eventfinder.assert_called_once()


# _start_writer is gone: Step 4a moved the commit call to
# RawDataController.commit_events, which registers the generator with the Model itself.
# Its per-channel and bare-channel behaviour is asserted there and just above.
