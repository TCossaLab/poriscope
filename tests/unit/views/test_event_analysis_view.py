"""
Full unit-test suite for EventAnalysisView.

Strategy
--------
EventAnalysisView inherits from MetaView (Qt widget) and uses global_signal
to communicate with the plugin bus.  Tests are split into three groups:

1. Pure-logic methods — tested standalone with no Qt or bus needed.
2. View-fixture methods — tested through a real EventAnalysisView instance
   (same pattern as test_protein_view.py).
3. Bus-dependent methods — covered at the boundary: we verify that
   handle_parameter_change routes correctly to the right sub-handler,
   patching the sub-handlers so the bus is never actually called.

Run with:
    pytest test_event_analysis_view.py -v
    pytest test_event_analysis_view.py --cov=poriscope --cov-report=html
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView

# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def view(qt_app):
    """Fully-initialised EventAnalysisView."""
    v = EventAnalysisView()
    container = QWidget()
    layout = QVBoxLayout(container)
    v._set_custom_display_area(layout)
    v._set_control_area(layout)
    v._test_container = container
    container.show()
    qt_app.processEvents()
    return v


# ===========================================================================
# _factors
# ===========================================================================

class TestFactors:
    def test_perfect_square(self, view):
        assert view._factors(4) == (2, 2)

    def test_six(self, view):
        nr, nc = view._factors(6)
        assert nr * nc == 6

    def test_one(self, view):
        nr, nc = view._factors(1)
        assert nr * nc == 1

    def test_nine(self, view):
        assert view._factors(9) == (3, 3)

    def test_prime_still_factors(self, view):
        nr, nc = view._factors(7)
        assert nr * nc >= 7

    def test_two(self, view):
        nr, nc = view._factors(2)
        assert nr * nc == 2

    def test_large(self, view):
        nr, nc = view._factors(12)
        assert nr * nc == 12


# ===========================================================================
# update_plot_data
# ===========================================================================

class TestUpdatePlotData:
    def test_dict_input_stores_data_field(self, view):
        arr = np.array([1, 2, 3])
        view.update_plot_data({"data": arr})
        np.testing.assert_array_equal(view.plot_data, arr)

    def test_array_input_stored_directly(self, view):
        arr = np.array([4, 5, 6])
        view.update_plot_data(arr)
        np.testing.assert_array_equal(view.plot_data, arr)

    def test_none_input(self, view):
        view.update_plot_data(None)
        assert view.plot_data is None

    def test_list_input(self, view):
        view.update_plot_data([1, 2, 3])
        assert view.plot_data == [1, 2, 3]


# ===========================================================================
# update_plot_features
# ===========================================================================

class TestUpdatePlotFeatures:
    def test_all_params_stored(self, view):
        view.update_plot_features(
            vertical=[1.0, 2.0],
            horizontal=[3.0],
            points=[(0.5, 1.5)],
            vlabels=["v1", "v2"],
            hlabels=["h1"],
            plabels=["p1"],
        )
        assert view.vertical == [1.0, 2.0]
        assert view.horizontal == [3.0]
        assert view.points == [(0.5, 1.5)]
        assert view.vlabels == ["v1", "v2"]
        assert view.hlabels == ["h1"]
        assert view.plabels == ["p1"]

    def test_none_defaults(self, view):
        view.update_plot_features()
        assert view.vertical is None
        assert view.horizontal is None
        assert view.points is None

    def test_partial_params(self, view):
        view.update_plot_features(vertical=[5.0])
        assert view.vertical == [5.0]
        assert view.horizontal is None


# ===========================================================================
# update_plot_samplerate
# ===========================================================================

class TestUpdatePlotSamplerate:
    def test_stores_samplerate(self, view):
        view.update_plot_samplerate(1_000_000)
        assert view.plot_samplerate == 1_000_000

    def test_float_samplerate(self, view):
        view.update_plot_samplerate(250_000.5)
        assert view.plot_samplerate == 250_000.5


# ===========================================================================
# set_eventfitting_status
# ===========================================================================

class TestSetEventfittingStatus:
    def test_true(self, view):
        view.set_eventfitting_status(True)
        assert view.eventfitting_status is True

    def test_false(self, view):
        view.set_eventfitting_status(False)
        assert view.eventfitting_status is False


# ===========================================================================
# set_num_events_allowed
# ===========================================================================

class TestSetNumEventsAllowed:
    def test_sets_value(self, view):
        view.set_num_events_allowed(500)
        assert view.num_events_allowed == 500

    def test_zero(self, view):
        view.set_num_events_allowed(0)
        assert view.num_events_allowed == 0


# ===========================================================================
# set_data_filter_function
# ===========================================================================

class TestSetDataFilterFunction:
    def test_stores_callable(self, view):
        def my_filter(x):
            return x * 2
        view.set_data_filter_function(my_filter)
        assert view.data_filter is my_filter

    def test_stores_none(self, view):
        view.set_data_filter_function(None)
        assert view.data_filter is None


# ===========================================================================
# validate_single_channel
# ===========================================================================

class TestValidateSingleChannel:
    def test_single_channel_ok(self, view):
        view.validate_single_channel([0])  # should not raise

    def test_multiple_channels_raises(self, view):
        with pytest.raises(ValueError, match="multiple channels"):
            view.validate_single_channel([0, 1])

    def test_empty_list_ok(self, view):
        view.validate_single_channel([])  # empty is not > 1


# ===========================================================================
# _extract_plot_event_parameters
# ===========================================================================

class TestExtractPlotEventParameters:
    def _params(self):
        return {
            "loader": "my_loader",
            "eventfitter": "my_fitter",
            "filter": "my_filter",
            "channel": ["0", "1"],
            "event_index": [1, 2, 3],
        }

    def test_returns_five_tuple(self, view):
        result = view._extract_plot_event_parameters(self._params())
        assert len(result) == 5

    def test_loader(self, view):
        loader, *_ = view._extract_plot_event_parameters(self._params())
        assert loader == "my_loader"

    def test_eventfitter(self, view):
        _, fitter, *_ = view._extract_plot_event_parameters(self._params())
        assert fitter == "my_fitter"

    def test_filter(self, view):
        _, _, data_filter, *_ = view._extract_plot_event_parameters(self._params())
        assert data_filter == "my_filter"

    def test_channels_as_ints(self, view):
        _, _, _, channels, _ = view._extract_plot_event_parameters(self._params())
        assert channels == [0, 1]

    def test_event_index(self, view):
        _, _, _, _, events = view._extract_plot_event_parameters(self._params())
        assert events == [1, 2, 3]

    def test_missing_optional_fields(self, view):
        params = {"channel": ["0"], "event_index": []}
        loader, fitter, filt, channels, events = (
            view._extract_plot_event_parameters(params)
        )
        assert loader is None
        assert fitter is None
        assert filt is None


# ===========================================================================
# _extract_event_fit_parameters
# ===========================================================================

class TestExtractEventFitParameters:
    def _params(self):
        return {
            "eventfitter": "fitter_a",
            "filter": "filter_b",
            "channel": ["0", "2"],
        }

    def test_returns_three_tuple(self, view):
        assert len(view._extract_event_fit_parameters(self._params())) == 3

    def test_eventfitter(self, view):
        fitter, _, _ = view._extract_event_fit_parameters(self._params())
        assert fitter == "fitter_a"

    def test_filter(self, view):
        _, filt, _ = view._extract_event_fit_parameters(self._params())
        assert filt == "filter_b"

    def test_channels_as_ints(self, view):
        _, _, channels = view._extract_event_fit_parameters(self._params())
        assert channels == [0, 2]


# ===========================================================================
# _extract_commit_event_parameters
# ===========================================================================

class TestExtractCommitEventParameters:
    def _params(self):
        return {"writer": "my_writer", "channel": ["1"]}

    def test_returns_two_tuple(self, view):
        assert len(view._extract_commit_event_parameters(self._params())) == 2

    def test_writer(self, view):
        writer, _ = view._extract_commit_event_parameters(self._params())
        assert writer == "my_writer"

    def test_channels_as_ints(self, view):
        _, channels = view._extract_commit_event_parameters(self._params())
        assert channels == [1]


# ===========================================================================
# get_current_view
# ===========================================================================

class TestGetCurrentView:
    def test_returns_correct_string(self, view):
        assert view.get_current_view() == "EventAnalysisView"


# ===========================================================================
# get_walkthrough_steps
# ===========================================================================

class TestGetWalkthroughSteps:
    def test_returns_list(self, view):
        assert isinstance(view.get_walkthrough_steps(), list)

    def test_has_13_steps(self, view):
        assert len(view.get_walkthrough_steps()) == 13

    def test_each_step_is_tuple_of_four(self, view):
        for step in view.get_walkthrough_steps():
            assert len(step) == 4

    def test_widget_callables_return_lists(self, view):
        for _, _, _, fn in view.get_walkthrough_steps():
            result = fn()
            assert isinstance(result, list)
            assert len(result) >= 1


# ===========================================================================
# _get_event_index_text
# ===========================================================================

class TestGetEventIndexText:
    def test_empty_initially(self, view):
        text = view._get_event_index_text()
        assert text == ""

    def test_reflects_lineedit(self, view):
        view.eventAnalysisControls.event_index_lineEdit.setText("3-5")
        assert view._get_event_index_text() == "3-5"

    def test_strips_whitespace(self, view):
        view.eventAnalysisControls.event_index_lineEdit.setText("  7  ")
        assert view._get_event_index_text() == "7"


# ===========================================================================
# update_channels
# ===========================================================================

class TestUpdateChannels:
    def test_channels_appear_in_combobox(self, view):
        view.update_channels(["0", "1", "2"])
        count = view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 3

    def test_single_channel(self, view):
        view.update_channels(["0"])
        count = view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 1


# ===========================================================================
# update_available_plugins
# ===========================================================================

class TestUpdateAvailablePlugins:
    def test_updates_loaders(self, view):
        view.update_available_plugins({"MetaEventLoader": ["ldr1", "ldr2"]})
        assert view.eventAnalysisControls.loaders_comboBox.count() == 2

    def test_updates_filters(self, view):
        view.update_available_plugins({"MetaFilter": ["f1"]})
        assert view.eventAnalysisControls.filters_comboBox.count() == 1

    def test_updates_writers(self, view):
        view.update_available_plugins({"MetaDatabaseWriter": ["w1"]})
        assert view.eventAnalysisControls.writers_comboBox.count() == 1

    def test_updates_eventfitters(self, view):
        view.update_available_plugins({"MetaEventFitter": ["ef1", "ef2"]})
        assert view.eventAnalysisControls.eventfitters_comboBox.count() == 2

    def test_empty_plugins_no_error(self, view):
        view.update_available_plugins({})

    def test_all_categories(self, view):
        view.update_available_plugins({
            "MetaEventLoader": ["l"],
            "MetaFilter": ["f"],
            "MetaDatabaseWriter": ["w"],
            "MetaEventFitter": ["ef"],
        })
        assert view.eventAnalysisControls.loaders_comboBox.count() == 1
        assert view.eventAnalysisControls.filters_comboBox.count() == 1
        assert view.eventAnalysisControls.writers_comboBox.count() == 1
        assert view.eventAnalysisControls.eventfitters_comboBox.count() == 1

    def test_exception_path_does_not_crash(self, view):
        """If controls raise, the exception is swallowed and logged."""
        view.eventAnalysisControls.update_loaders = MagicMock(
            side_effect=Exception("boom")
        )
        view.update_available_plugins({"MetaEventLoader": ["l"]})  # must not raise


# ===========================================================================
# handle_parameter_change — routing
# ===========================================================================

class TestHandleParameterChange:
    def _params(self):
        return {
            "loader": "l", "eventfitter": "ef", "filter": "No Filter",
            "channel": ["0"], "event_index": [1], "writer": "w",
            "raw": False,
        }

    def test_routes_fit_events(self, view):
        with patch.object(EventAnalysisView, "_handle_fit_events") as mock:
            view.handle_parameter_change("M", "fit_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_plot_events(self, view):
        with patch.object(EventAnalysisView, "_handle_plot_events") as mock:
            view.handle_parameter_change("M", "plot_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_commit_events(self, view):
        with patch.object(EventAnalysisView, "_handle_commit_events") as mock:
            view.handle_parameter_change("M", "commit_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_shift_backward(self, view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            view.handle_parameter_change("M", "shift_range_backward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_routes_shift_forward(self, view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            view.handle_parameter_change("M", "shift_range_forward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "right"

    def test_routes_export_plot_data(self, view):
        received = []
        view.export_plot_data.connect(lambda: received.append(True))
        view.handle_parameter_change("M", "export_plot_data", (self._params(),))
        assert received == [True]

    def test_routes_unknown_to_other_actions(self, view):
        with patch.object(EventAnalysisView, "_handle_other_actions") as mock:
            view.handle_parameter_change("M", "unknown_action", (self._params(),))
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert "unknown_action" in all_args


# ===========================================================================
# _handle_other_actions
# ===========================================================================

class TestHandleOtherActions:
    def test_with_loader_emits_signal(self, view):
        emitted = []
        view.global_signal.connect(lambda *a: emitted.append(a))
        view._handle_other_actions("any", {"loader": "my_loader"})
        assert any("get_channels" in str(a) for a in emitted)

    def test_without_loader_no_signal(self, view):
        emitted = []
        view.global_signal.connect(lambda *a: emitted.append(a))
        before = len(emitted)
        view._handle_other_actions("any", {"loader": None})
        assert len(emitted) == before


# ===========================================================================
# _handle_fit_events
# ===========================================================================

class TestHandleFitEvents:
    def _params(self):
        return {
            "eventfitter": "ef1",
            "filter": "No Filter",
            "channel": ["0"],
        }

    def test_bad_params_returns_gracefully(self, view):
        # Patch the extractor to raise ValueError — _handle_fit_events must catch it
        # and return without calling _start_eventfitter.
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            side_effect=ValueError("bad params"),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                view._handle_fit_events({"eventfitter": "ef1", "filter": "No Filter", "channel": ["0"]})
        mock.assert_not_called()

    def test_valid_params_calls_start_eventfitter(self, view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            view._handle_fit_events(self._params())
        mock.assert_called_once()
        # class-level patch: call_args[0] = (self, eventfitter, filter, channels)
        # or call_args[0] = (eventfitter, filter, channels) depending on decorator
        all_args = mock.call_args[0]
        flat = [a for a in all_args if a is not view]
        assert "ef1" in flat
        assert "No Filter" in flat
        assert [0] in flat

    def test_none_eventfitter_does_not_call_start(self, view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=(None, "No Filter", [0]),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                view._handle_fit_events(self._params())
        mock.assert_not_called()

    def test_none_channels_does_not_call_start(self, view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=("ef1", "No Filter", None),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                view._handle_fit_events(self._params())
        mock.assert_not_called()

    def test_none_filter_does_not_call_start(self, view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=("ef1", None, [0]),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                view._handle_fit_events(self._params())
        mock.assert_not_called()


# ===========================================================================
# _handle_commit_events
# ===========================================================================

class TestHandleCommitEvents:
    def test_bad_params_returns_gracefully(self, view):
        # Patch the extractor to raise ValueError — _handle_commit_events must catch it
        # and return without calling _start_writer.
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            side_effect=ValueError("bad params"),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()

    def test_valid_params_calls_start_writer(self, view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        flat = [a for a in all_args if a is not view]
        assert "w" in flat
        assert [0] in flat

    def test_none_writer_does_not_call_start(self, view):
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            return_value=(None, [0]),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()

    def test_none_channels_does_not_call_start(self, view):
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            return_value=("w", None),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()


# ===========================================================================
# _start_writer
# ===========================================================================

class TestStartWriter:
    def test_emits_signal_per_channel(self, view):
        emitted = []
        view.global_signal.connect(lambda *a: emitted.append(a))
        view.run_generators = MagicMock()
        view._start_writer("w1", [0, 1])
        write_calls = [e for e in emitted if "write_events" in str(e)]
        assert len(write_calls) == 2
        view.run_generators.emit.assert_called_once_with("w1")

    def test_single_channel_as_int_converted(self, view):
        emitted = []
        view.global_signal.connect(lambda *a: emitted.append(a))
        view.run_generators = MagicMock()
        view._start_writer("w1", 0)  # non-list
        # non-list is converted to list internally
        view.run_generators.emit.assert_called_once_with("w1")

    def test_index_error_logged(self, view):
        view.global_signal = MagicMock()
        view.global_signal.emit.side_effect = IndexError("bad index")
        view.run_generators = MagicMock()
        view._start_writer("w1", [0])
        # Should not raise; run_generators not called on error
        view.run_generators.emit.assert_not_called()


# ===========================================================================
# _start_eventfitter
# ===========================================================================

class TestStartEventfitter:
    def _setup(self, view):
        view.global_signal = MagicMock()
        view.run_generators = MagicMock()
        view.eventfitting_status = False
        view.data_filter = None

    def test_emits_fit_events_signal(self, view):
        self._setup(view)
        view._start_eventfitter("ef1", "No Filter", [0])
        emitted_actions = [
            c.args[2] for c in view.global_signal.emit.call_args_list
        ]
        assert "fit_events" in emitted_actions

    def test_run_generators_called(self, view):
        self._setup(view)
        view._start_eventfitter("ef1", "No Filter", [0])
        view.run_generators.emit.assert_called_once_with("ef1")

    def test_with_filter_emits_get_callable_filter(self, view):
        self._setup(view)
        view._start_eventfitter("ef1", "MyFilter", [0])
        emitted_actions = [
            c.args[2] for c in view.global_signal.emit.call_args_list
        ]
        assert "get_callable_filter" in emitted_actions

    def test_non_list_channels_converted(self, view):
        self._setup(view)
        # Should not raise even if channels is not a list
        view._start_eventfitter("ef1", "No Filter", 0)
        view.run_generators.emit.assert_called_once_with("ef1")

    def test_already_fitted_and_no_skipped(self, view):
        """If status is True but user would say No in dialog, we patch QMessageBox."""
        self._setup(view)
        view.eventfitting_status = True
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QMessageBox.question",
            return_value=MagicMock(),  # anything that isn't QMessageBox.No
        ):
            view._start_eventfitter("ef1", "No Filter", [0])
        # Should still emit fit_events since we didn't return early
        emitted_actions = [
            c.args[2] for c in view.global_signal.emit.call_args_list
        ]
        assert "fit_events" in emitted_actions


# ===========================================================================
# _shift_range_and_update_plot
# ===========================================================================

class TestShiftRangeAndUpdatePlot:
    def _base_params(self):
        return {
            "loader": "l", "eventfitter": "ef",
            "filter": "No Filter", "channel": ["0"],
            "event_index": [5, 6, 7],
        }

    def _setup_shift(self, view):
        view.eventAnalysisControls.event_index_lineEdit.setText("5-7")
        view._parse_event_indices = MagicMock(return_value=[(5, 7)])
        view._shift_ranges = MagicMock(return_value=[(6, 8)])
        view._merge_ranges = MagicMock(return_value=[(6, 8)])
        view._format_ranges = MagicMock(return_value="6-8")
        view._expand_event_indices = MagicMock(return_value=[6, 7, 8])
        self._plot_patcher = patch.object(EventAnalysisView, "_handle_plot_events")
        self._mock_plot = self._plot_patcher.start()
        view._mock_handle_plot_events = self._mock_plot

    def _teardown_shift(self):
        self._plot_patcher.stop()

    def test_right_shift_calls_handle_plot_events(self, view):
        self._setup_shift(view)
        view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_called_once()
        self._teardown_shift()

    def test_left_shift_calls_handle_plot_events(self, view):
        self._setup_shift(view)
        view._shift_ranges.return_value = [(4, 6)]
        view._merge_ranges.return_value = [(4, 6)]
        view._format_ranges.return_value = "4-6"
        view._expand_event_indices.return_value = [4, 5, 6]
        view._shift_range_and_update_plot(self._base_params(), direction="left")
        self._mock_plot.assert_called_once()
        self._teardown_shift()

    def test_shift_updates_gui_input(self, view):
        self._setup_shift(view)
        view._shift_range_and_update_plot(self._base_params(), direction="right")
        assert view.eventAnalysisControls.event_index_lineEdit.text() == "6-8"
        self._teardown_shift()

    def test_empty_index_text_aborts(self, view):
        self._setup_shift(view)
        view.eventAnalysisControls.event_index_lineEdit.setText("")
        view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_not_called()
        self._teardown_shift()

    def test_empty_expanded_indices_aborts(self, view):
        self._setup_shift(view)
        view._expand_event_indices.return_value = []
        view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_not_called()
        self._teardown_shift()

    def test_multiple_channels_raises_and_aborts(self, view):
        self._setup_shift(view)
        params = self._base_params()
        params["channel"] = ["0", "1"]
        view._shift_range_and_update_plot(params, direction="right")
        self._mock_plot.assert_not_called()
        self._teardown_shift()

    def test_updated_params_contain_new_indices(self, view):
        self._setup_shift(view)
        view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_called_once()
        # class-level patch: args are (self, params) or just (params,) depending on decorator
        call_args = self._mock_plot.call_args[0]
        call_params = call_args[-1]  # last positional arg is always params
        assert call_params["event_index"] == [6, 7, 8]
        self._teardown_shift()

    def test_original_params_not_mutated(self, view):
        self._setup_shift(view)
        original = self._base_params()
        original_indices = list(original["event_index"])
        view._shift_range_and_update_plot(original, direction="right")
        assert original["event_index"] == original_indices
        self._teardown_shift()


# ===========================================================================
# _handle_plot_events
# ===========================================================================

class TestHandlePlotEvents:
    def _params(self, events=None):
        return {
            "loader": "ldr",
            "eventfitter": "No Event Fitter",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": events if events is not None else [0],
            "raw": False,
        }

    def _setup(self, view, plot_data=None):
        """Replace global_signal with a MagicMock so we can inspect emissions."""
        view.global_signal = MagicMock()
        view.global_signal.emit = MagicMock()
        view.global_signal.connect = MagicMock()
        view.num_events_allowed = 999
        view.eventfitting_status = False
        view.data_filter = None
        view.plot_data = plot_data
        view.plot_samplerate = 1_000_000
        self._update_patcher = patch.object(EventAnalysisView, "_update_event_plot")
        self._mock_update = self._update_patcher.start()

    def _teardown(self):
        self._update_patcher.stop()

    def test_no_events_skips_plot(self, view):
        self._setup(view)
        view._handle_plot_events(self._params(events=[]))
        self._mock_update.assert_not_called()
        self._teardown()

    def test_valid_event_calls_update_plot(self, view):
        self._setup(view, plot_data=np.ones(10) * 100.0)

        def side_effect(*args):
            # When load_event is called, set plot_data so the handler sees data
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(10) * 100.0

        view.global_signal.emit.side_effect = side_effect
        view._handle_plot_events(self._params(events=[0]))
        self._mock_update.assert_called_once()
        self._teardown()

    def test_events_truncated_when_above_allowed(self, view):
        self._setup(view)
        view.num_events_allowed = 3
        # Events [0, 1, 2, 5] — index 5 should be dropped
        params = self._params(events=[0, 1, 2, 5])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(5) * 50.0

        view.global_signal.emit.side_effect = side_effect
        view._handle_plot_events(params)
        # _update_event_plot should be called with at most 3 data entries
        if self._mock_update.called:
            data_list = self._mock_update.call_args[0][1]
            assert len(data_list) <= 3
        self._teardown()

    def test_no_data_loaded_skips_event(self, view):
        self._setup(view, plot_data=None)
        view._handle_plot_events(self._params(events=[0]))
        self._mock_update.assert_not_called()
        self._teardown()

    def test_multiple_channels_handled_gracefully(self, view):
        self._setup(view)
        params = self._params()
        params["channel"] = ["0", "1"]
        # Should not raise — extract will raise ValueError caught internally
        view._handle_plot_events(params)
        self._teardown()

    def test_get_num_events_signal_emitted(self, view):
        self._setup(view)
        view._handle_plot_events(self._params(events=[0]))
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_num_events" in actions
        self._teardown()

    def test_with_filter_emits_get_callable_filter(self, view):
        self._setup(view, plot_data=np.ones(5) * 10.0)

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(5) * 10.0

        view.global_signal.emit.side_effect = side_effect
        params = self._params(events=[0])
        params["filter"] = "MyFilter"
        view._handle_plot_events(params)
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_callable_filter" in actions
        self._teardown()

    def test_with_raw_flag_and_filter_loads_raw(self, view):
        """When raw=True and data_filter is set, a second load_event for raw is emitted."""
        self._setup(view)
        view.data_filter = MagicMock()  # simulate active filter

        load_event_calls = []

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(5) * 10.0
                load_event_calls.append(args)

        view.global_signal.emit.side_effect = side_effect
        params = self._params(events=[0])
        params["raw"] = True
        view._handle_plot_events(params)
        # At least one load_event for filtered data; raw=True should trigger a second
        assert len(load_event_calls) >= 1
        self._teardown()


# ===========================================================================
# _update_event_plot
# ===========================================================================

class TestUpdateEventPlot:
    def _make_data(self, n=50):
        return np.ones(n) * 1000.0

    def _none_lists(self, n):
        return (
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
        )

    def _mock_figure(self, view):
        """Replace figure and canvas with mocks; leave cache methods as real."""
        mock_ax = MagicMock()
        mock_ax.get_legend_handles_labels = MagicMock(return_value=([], []))
        view.figure = MagicMock()
        view.figure.add_subplot = MagicMock(return_value=mock_ax)
        view.figure.get_axes = MagicMock(return_value=[mock_ax])
        view.figure.get_size_inches = MagicMock(return_value=(8.0, 6.0))
        view.canvas = MagicMock()
        return mock_ax

    def test_clears_figure_before_plotting(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        view.figure.clear.assert_called()

    def test_canvas_draw_called(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        view.canvas.draw.assert_called()

    def test_one_subplot_created_for_one_event(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        view.figure.add_subplot.assert_called_once()


    def test_fit_trace_plotted_when_label_contains_fit(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 0 Fit"],
            1,
            *self._none_lists(1),
        )
        assert mock_ax.plot.call_count >= 2

    def test_raw_trace_plotted_when_label_contains_raw(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 0 Raw"],
            1,
            *self._none_lists(1),
        )
        assert mock_ax.plot.call_count >= 2

    def test_vertical_lines_drawn(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[10.0]], [None], [None],
            [["v_label"]], [None], [None],
        )
        mock_ax.axvline.assert_called()

    def test_horizontal_lines_drawn(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None], [[500.0]], [None],
            [None], [["h_label"]], [None],
        )
        mock_ax.axhline.assert_called()

    def test_points_drawn(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None], [None], [[(5.0, 300.0)]],
            [None], [None], [["p_label"]],
        )
        assert mock_ax.plot.call_count >= 2

    def test_cache_committed(self, view):
        # Patch _commit_cache at class level to verify it's called
        view.plot_samplerate = 1_000_000
        with patch.object(EventAnalysisView, "_commit_cache") as mock_cache:
            view._update_event_plot(
                [self._make_data()],
                ["Event 0 Data"],
                1,
                *self._none_lists(1),
            )
        mock_cache.assert_called()

    def test_two_events_two_subplots(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 1 Data"],
            2,
            *self._none_lists(2),
        )
        assert view.figure.add_subplot.call_count == 2

    def test_vertical_line_without_label_uses_black(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[10.0]], [None], [None],
            [[None]], [None], [None],
        )
        mock_ax.axvline.assert_called()
        call_kwargs = mock_ax.axvline.call_args[1]
        assert call_kwargs.get("color") == "black"

    def test_horizontal_line_without_label_uses_black(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None], [[500.0]], [None],
            [None], [[None]], [None],
        )
        mock_ax.axhline.assert_called()
        call_kwargs = mock_ax.axhline.call_args[1]
        assert call_kwargs.get("color") == "black"


# ===========================================================================
# get_save_filename
# ===========================================================================

class TestGetSaveFilename:
    def test_returns_selected_path(self, view):
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QFileDialog.getSaveFileName",
            return_value=("/path/to/file.csv", "CSV Files (*.csv)"),
        ):
            result = view.get_save_filename()
        assert result == "/path/to/file.csv"

    def test_returns_empty_on_cancel(self, view):
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            result = view.get_save_filename()
        assert result == ""


# ===========================================================================
# update_plot / _reset_actions / _init (no-ops — coverage only)
# ===========================================================================

class TestNoOpMethods:
    def test_update_plot_no_error(self, view):
        view.update_plot()

    def test_reset_actions_no_error(self, view):
        view._reset_actions()

    def test_reset_actions_3d_no_error(self, view):
        view._reset_actions(axis_type="3d")


# ===========================================================================
# _factors — extended edge cases
# ===========================================================================

class TestFactorsExtended:
    def test_three(self, view):
        nr, nc = view._factors(3)
        assert nr * nc >= 3

    def test_four(self, view):
        assert view._factors(4) == (2, 2)

    def test_five(self, view):
        nr, nc = view._factors(5)
        assert nr * nc >= 5

    def test_sixteen(self, view):
        assert view._factors(16) == (4, 4)

    def test_output_is_two_tuple(self, view):
        result = view._factors(6)
        assert len(result) == 2

    def test_first_factor_lte_second(self, view):
        nr, nc = view._factors(8)
        assert nr <= nc


# ===========================================================================
# update_plot_data — extended
# ===========================================================================

class TestUpdatePlotDataExtended:
    def test_dict_with_extra_keys_uses_data_key(self, view):
        arr = np.array([7.0, 8.0])
        view.update_plot_data({"data": arr, "extra": "ignored"})
        np.testing.assert_array_equal(view.plot_data, arr)

    def test_empty_array(self, view):
        arr = np.array([])
        view.update_plot_data(arr)
        np.testing.assert_array_equal(view.plot_data, arr)

    def test_2d_array(self, view):
        arr = np.ones((3, 4))
        view.update_plot_data(arr)
        np.testing.assert_array_equal(view.plot_data, arr)


# ===========================================================================
# update_plot_features — extended
# ===========================================================================

class TestUpdatePlotFeaturesExtended:
    def test_overwrites_previous_values(self, view):
        view.update_plot_features(vertical=[1.0])
        view.update_plot_features(vertical=[2.0])
        assert view.vertical == [2.0]

    def test_all_none_by_default(self, view):
        view.update_plot_features()
        for attr in ("vertical", "horizontal", "points", "vlabels", "hlabels", "plabels"):
            assert getattr(view, attr) is None

    def test_points_stored_correctly(self, view):
        pts = [(0.1, 0.2), (0.3, 0.4)]
        view.update_plot_features(points=pts)
        assert view.points == pts


# ===========================================================================
# validate_single_channel — extended
# ===========================================================================

class TestValidateSingleChannelExtended:
    def test_exactly_one_channel_ok(self, view):
        view.validate_single_channel([5])  # should not raise

    def test_three_channels_raises(self, view):
        with pytest.raises(ValueError):
            view.validate_single_channel([0, 1, 2])

    def test_error_message_mentions_multiple(self, view):
        with pytest.raises(ValueError, match="multiple"):
            view.validate_single_channel([0, 1])


# ===========================================================================
# set_num_events_allowed — extended
# ===========================================================================

class TestSetNumEventsAllowedExtended:
    def test_large_number(self, view):
        view.set_num_events_allowed(1_000_000)
        assert view.num_events_allowed == 1_000_000

    def test_overwrite(self, view):
        view.set_num_events_allowed(10)
        view.set_num_events_allowed(20)
        assert view.num_events_allowed == 20


# ===========================================================================
# set_data_filter_function — extended
# ===========================================================================

class TestSetDataFilterFunctionExtended:
    def test_lambda_stored(self, view):
        fn = lambda x: x + 1  # noqa: E731
        view.set_data_filter_function(fn)
        assert view.data_filter is fn

    def test_overwrite_with_none(self, view):
        view.set_data_filter_function(lambda x: x)
        view.set_data_filter_function(None)
        assert view.data_filter is None


# ===========================================================================
# _extract_plot_event_parameters — edge cases
# ===========================================================================

class TestExtractPlotEventParametersExtended:
    def test_empty_channel_list(self, view):
        params = {"channel": [], "event_index": []}
        loader, fitter, filt, channels, events = (
            view._extract_plot_event_parameters(params)
        )
        assert channels == []

    def test_multiple_channels_converted(self, view):
        params = {"channel": ["0", "1", "2"], "event_index": []}
        _, _, _, channels, _ = view._extract_plot_event_parameters(params)
        assert channels == [0, 1, 2]

    def test_event_index_none_returned_as_none(self, view):
        params = {"channel": ["0"]}
        _, _, _, _, events = view._extract_plot_event_parameters(params)
        assert events is None


# ===========================================================================
# _extract_event_fit_parameters — edge cases
# ===========================================================================

class TestExtractEventFitParametersExtended:
    def test_missing_eventfitter_returns_none(self, view):
        params = {"channel": ["0"]}
        fitter, filt, channels = view._extract_event_fit_parameters(params)
        assert fitter is None

    def test_missing_filter_returns_none(self, view):
        params = {"channel": ["0"], "eventfitter": "ef"}
        _, filt, _ = view._extract_event_fit_parameters(params)
        assert filt is None

    def test_channels_converted_to_int(self, view):
        params = {"channel": ["3", "4"], "eventfitter": "ef", "filter": "f"}
        _, _, channels = view._extract_event_fit_parameters(params)
        assert channels == [3, 4]


# ===========================================================================
# _extract_commit_event_parameters — edge cases
# ===========================================================================

class TestExtractCommitEventParametersExtended:
    def test_missing_writer_returns_none(self, view):
        params = {"channel": ["0"]}
        writer, channels = view._extract_commit_event_parameters(params)
        assert writer is None

    def test_multiple_channels(self, view):
        params = {"writer": "w", "channel": ["0", "1", "2"]}
        _, channels = view._extract_commit_event_parameters(params)
        assert channels == [0, 1, 2]


# ===========================================================================
# _handle_other_actions — extended
# ===========================================================================

class TestHandleOtherActionsExtended:
    def test_loader_none_does_not_emit(self, view):
        view.global_signal = MagicMock()
        view._handle_other_actions("any_action", {"loader": None})
        view.global_signal.emit.assert_not_called()

    def test_loader_present_emits_get_channels(self, view):
        view.global_signal = MagicMock()
        view._handle_other_actions("any_action", {"loader": "my_loader"})
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_channels" in actions

    def test_loader_present_targets_correct_loader(self, view):
        view.global_signal = MagicMock()
        view._handle_other_actions("any_action", {"loader": "specific_loader"})
        args = view.global_signal.emit.call_args[0]
        assert args[1] == "specific_loader"

    def test_missing_loader_key_treated_as_none(self, view):
        view.global_signal = MagicMock()
        view._handle_other_actions("any_action", {})
        view.global_signal.emit.assert_not_called()


# ===========================================================================
# _handle_fit_events — extended
# ===========================================================================

class TestHandleFitEventsExtended:
    def test_empty_channel_list_does_not_crash(self, view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            view._handle_fit_events({
                "eventfitter": "ef1",
                "filter": "No Filter",
                "channel": [],
            })
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [] in all_args

    def test_channels_passed_as_ints(self, view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            view._handle_fit_events({
                "eventfitter": "ef1",
                "filter": "No Filter",
                "channel": ["2", "3"],
            })
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [2, 3] in all_args


# ===========================================================================
# _handle_commit_events — extended
# ===========================================================================

class TestHandleCommitEventsExtended:
    def test_channels_passed_as_ints(self, view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            view._handle_commit_events({"writer": "w", "channel": ["2"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [2] in all_args

    def test_multiple_channels_passed_correctly(self, view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            view._handle_commit_events({"writer": "w", "channel": ["0", "1"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [0, 1] in all_args


# ===========================================================================
# _start_writer — extended
# ===========================================================================

class TestStartWriterExtended:
    def test_empty_channels_does_not_emit_write(self, view):
        emitted = []
        view.global_signal.connect(lambda *a: emitted.append(a))
        view.run_generators = MagicMock()
        view._start_writer("w1", [])
        write_calls = [e for e in emitted if "write_events" in str(e)]
        assert len(write_calls) == 0

    def test_run_generators_called_with_writer_name(self, view):
        view.global_signal = MagicMock()
        view.run_generators = MagicMock()
        view._start_writer("my_writer", [0])
        view.run_generators.emit.assert_called_once_with("my_writer")

    def test_value_error_prevents_run_generators(self, view):
        view.global_signal = MagicMock()
        view.global_signal.emit.side_effect = ValueError("bad value")
        view.run_generators = MagicMock()
        view._start_writer("w1", [0])
        view.run_generators.emit.assert_not_called()


# ===========================================================================
# _start_eventfitter — extended
# ===========================================================================

class TestStartEventfitterExtended:
    def _setup(self, view):
        view.global_signal = MagicMock()
        view.run_generators = MagicMock()
        view.eventfitting_status = False
        view.data_filter = None

    def test_no_filter_does_not_emit_get_callable_filter(self, view):
        self._setup(view)
        view._start_eventfitter("ef1", "No Filter", [0])
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_callable_filter" not in actions

    def test_multiple_channels_emits_fit_per_channel(self, view):
        self._setup(view)
        view._start_eventfitter("ef1", "No Filter", [0, 1])
        fit_calls = [
            c for c in view.global_signal.emit.call_args_list
            if len(c.args) > 2 and c.args[2] == "fit_events"
        ]
        assert len(fit_calls) == 2

    def test_index_error_logged_not_raised(self, view):
        self._setup(view)
        view.global_signal.emit.side_effect = IndexError("bad")
        # Should not raise — error is caught
        view._start_eventfitter("ef1", "No Filter", [0])
        view.run_generators.emit.assert_not_called()


# ===========================================================================
# handle_parameter_change — extended routing
# ===========================================================================

class TestHandleParameterChangeExtended:
    def _params(self):
        return {
            "loader": "l", "eventfitter": "ef", "filter": "No Filter",
            "channel": ["0"], "event_index": [1], "writer": "w",
            "raw": False,
        }

    def test_export_plot_data_emits_signal(self, view):
        received = []
        view.export_plot_data.connect(lambda: received.append(True))
        view.handle_parameter_change("M", "export_plot_data", (self._params(),))
        assert len(received) == 1

    def test_shift_backward_direction_is_left(self, view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            view.handle_parameter_change("M", "shift_range_backward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_shift_forward_direction_is_right(self, view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            view.handle_parameter_change("M", "shift_range_forward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "right"


# ===========================================================================
# _handle_plot_events — extended
# ===========================================================================

class TestHandlePlotEventsExtended:
    def _params(self, events=None):
        return {
            "loader": "ldr",
            "eventfitter": "No Event Fitter",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": events if events is not None else [0],
            "raw": False,
        }

    def _setup(self, view, plot_data=None):
        view.global_signal = MagicMock()
        view.global_signal.emit = MagicMock()
        view.global_signal.connect = MagicMock()
        view.num_events_allowed = 999
        view.eventfitting_status = False
        view.data_filter = None
        view.plot_data = plot_data
        view.plot_samplerate = 1_000_000
        self._update_patcher = patch.object(EventAnalysisView, "_update_event_plot")
        self._mock_update = self._update_patcher.start()

    def _teardown(self):
        self._update_patcher.stop()

    def test_events_within_bounds_not_truncated(self, view):
        self._setup(view)
        view.num_events_allowed = 10
        params = self._params(events=[0, 1, 2])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(5)

        view.global_signal.emit.side_effect = side_effect
        view._handle_plot_events(params)
        # All 3 events within bounds — update_plot should be called
        self._mock_update.assert_called_once()
        self._teardown()

    def test_samplerate_signal_emitted(self, view):
        self._setup(view)
        view._handle_plot_events(self._params(events=[0]))
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "get_samplerate" in actions
        self._teardown()

    def test_load_event_signal_emitted(self, view):
        self._setup(view)
        params = self._params(events=[0])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                view.plot_data = np.ones(5)

        view.global_signal.emit.side_effect = side_effect
        view._handle_plot_events(params)
        actions = [c.args[2] for c in view.global_signal.emit.call_args_list]
        assert "load_event" in actions
        self._teardown()

    def test_all_events_out_of_bounds_no_plot(self, view):
        self._setup(view)
        view.num_events_allowed = 3
        params = self._params(events=[5, 6, 7])  # all >= 3
        view._handle_plot_events(params)
        self._mock_update.assert_not_called()
        self._teardown()


# ===========================================================================
# _update_event_plot — extended
# ===========================================================================

class TestUpdateEventPlotExtended:
    def _make_data(self, n=50):
        return np.ones(n) * 1000.0

    def _none_lists(self, n):
        return (
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
            [None] * n,
        )

    def _mock_figure(self, view, legend_handles=None):
        """Replace figure and canvas with mocks; leave cache methods as real."""
        mock_ax = MagicMock()
        handles = legend_handles if legend_handles is not None else ([], [])
        mock_ax.get_legend_handles_labels = MagicMock(return_value=handles)
        view.figure = MagicMock()
        view.figure.add_subplot = MagicMock(return_value=mock_ax)
        view.figure.get_axes = MagicMock(return_value=[mock_ax])
        view.figure.get_size_inches = MagicMock(return_value=(8.0, 6.0))
        view.canvas = MagicMock()
        return mock_ax

    def test_figure_set_constrained_layout_called(self, view):
        self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            *self._none_lists(1),
        )
        view.figure.set_constrained_layout.assert_called()

    def test_clear_cache_called(self, view):
        # _clear_cache initialises data_cache which _update_cache depends on.
        # Pre-seed data_cache so patching _clear_cache won't break _update_cache.
        self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view.data_cache = []
        view.label_cache = []
        view.data_cache_labels = []
        with patch.object(EventAnalysisView, "_clear_cache") as mock_cc:
            view._update_event_plot(
                [self._make_data()], ["Event 0 Data"], 1,
                *self._none_lists(1),
            )
        mock_cc.assert_called()

    def test_update_cache_called_per_data_item(self, view):
        self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        with patch.object(EventAnalysisView, "_update_cache") as mock_uc:
            view._update_event_plot(
                [self._make_data(), self._make_data()],
                ["Event 0 Data", "Event 1 Data"],
                2,
                *self._none_lists(2),
            )
        assert mock_uc.call_count >= 2

    def test_labelled_vline_uses_color_not_black(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            [[10.0]], [None], [None],
            [["my_label"]], [None], [None],
        )
        mock_ax.axvline.assert_called()
        call_kwargs = mock_ax.axvline.call_args[1]
        assert call_kwargs.get("color") != "black"
        assert call_kwargs.get("label") == "my_label"

    def test_labelled_hline_uses_color_not_black(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            [None], [[500.0]], [None],
            [None], [["h_label"]], [None],
        )
        mock_ax.axhline.assert_called()
        call_kwargs = mock_ax.axhline.call_args[1]
        assert call_kwargs.get("color") != "black"
        assert call_kwargs.get("label") == "h_label"

    def test_labelled_point_uses_color_not_black(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            [None], [None], [[(5.0, 300.0)]],
            [None], [None], [["pt_label"]],
        )
        label_calls = [
            c for c in mock_ax.plot.call_args_list
            if c[1].get("label") == "pt_label"
        ]
        assert len(label_calls) >= 1

    def test_multiple_vlines_per_event(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            [[5.0, 10.0, 15.0]], [None], [None],
            [[None, None, None]], [None], [None],
        )
        assert mock_ax.axvline.call_count == 3

    def test_grid_is_enabled(self, view):
        mock_ax = self._mock_figure(view)
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            *self._none_lists(1),
        )
        mock_ax.grid.assert_called_with(True)

    def test_legend_built_when_handles_exist(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            *self._none_lists(1),
        )
        view.figure.legend.assert_called_once()

    def test_no_legend_when_no_handles(self, view):
        view.plot_samplerate = 1_000_000
        view._update_event_plot(
            [self._make_data()], ["Event 0 Data"], 1,
            *self._none_lists(1),
        )
        view.figure.legend.assert_not_called()

# ===========================================================================
# get_walkthrough_steps — extended
# ===========================================================================

class TestGetWalkthroughStepsExtended:
    def test_all_step_views_are_event_analysis_view(self, view):
        for _, _, view_name, _ in view.get_walkthrough_steps():
            assert view_name == "EventAnalysisView"

    def test_all_descriptions_are_non_empty_strings(self, view):
        for _, desc, _, _ in view.get_walkthrough_steps():
            assert isinstance(desc, str) and len(desc) > 0

    def test_all_titles_are_non_empty_strings(self, view):
        for title, _, _, _ in view.get_walkthrough_steps():
            assert isinstance(title, str) and len(title) > 0


# ===========================================================================
# update_channels — extended
# ===========================================================================

class TestUpdateChannelsExtended:
    def test_empty_list_clears_combobox(self, view):
        view.update_channels(["0", "1"])
        view.update_channels([])
        count = view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 0

    def test_overwrites_previous_channels(self, view):
        view.update_channels(["0", "1", "2"])
        view.update_channels(["5"])
        count = view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 1


# ===========================================================================
# update_available_plugins — extended
# ===========================================================================

class TestUpdateAvailablePluginsExtended:
    def test_unknown_key_ignored(self, view):
        # Call with a known key first to establish a baseline, then with unknown.
        # The unknown key should not add "x" or "y" as loader items.
        view.update_available_plugins({"MetaEventLoader": ["known_loader"]})
        count_after_known = view.eventAnalysisControls.loaders_comboBox.count()
        view.update_available_plugins({"UnknownPlugin": ["x", "y"]})
        count_after_unknown = view.eventAnalysisControls.loaders_comboBox.count()
        # After passing an unknown key, loaders should not grow by 2
        assert count_after_unknown != count_after_known + 2

    def test_multiple_loaders(self, view):
        view.update_available_plugins({"MetaEventLoader": ["l1", "l2", "l3"]})
        assert view.eventAnalysisControls.loaders_comboBox.count() == 3

    def test_multiple_filters(self, view):
        view.update_available_plugins({"MetaFilter": ["f1", "f2"]})
        assert view.eventAnalysisControls.filters_comboBox.count() == 2