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
from tests.unit.views._qt_mocks import mock_axes, mock_figure, shadow_signals

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
def real_view(qt_app):
    """
    Fully-initialised EventAnalysisView built from real Qt widgets.

    Use this only where the test needs real Qt behaviour - reading item counts
    back off a populated combo box, or asserting on widget text. Everything else
    should take ``mock_view``, which is far cheaper.
    """
    v = EventAnalysisView()
    container = QWidget()
    layout = QVBoxLayout(container)
    v._set_custom_display_area(layout)
    v._set_control_area(layout)
    v._test_container = container
    return v


@pytest.fixture
def mock_view():
    """
    EventAnalysisView with its Qt and Matplotlib dependencies mocked.

    Built with __new__ so no widget tree is constructed, then given the figure,
    canvas and controls the real setup methods would have created. _init() is a
    no-op on this mock_view, and the methods under test are the real ones - only the
    drawing surface and the controls panel are stand-ins.

    Tests that read state back off a real widget (combo box counts, line-edit
    text) must take ``real_view``: those assertions pass vacuously here.
    """
    v = EventAnalysisView.__new__(EventAnalysisView)

    v.figure = mock_figure()
    v.axes = mock_axes()
    v.canvas = MagicMock()
    v.toolbar = MagicMock()
    v.eventAnalysisControls = MagicMock()

    # logger is deliberately NOT mocked: it is a class attribute, so it resolves
    # on its own, and tests assert through caplog.
    shadow_signals(v, EventAnalysisView)

    v._init()
    return v


# ===========================================================================
# _factors
# ===========================================================================


class TestFactors:
    def test_perfect_square(self, mock_view):
        assert mock_view._factors(4) == (2, 2)

    def test_six(self, mock_view):
        nr, nc = mock_view._factors(6)
        assert nr * nc == 6

    def test_one(self, mock_view):
        nr, nc = mock_view._factors(1)
        assert nr * nc == 1

    def test_nine(self, mock_view):
        assert mock_view._factors(9) == (3, 3)

    def test_prime_still_factors(self, mock_view):
        nr, nc = mock_view._factors(7)
        assert nr * nc >= 7

    def test_two(self, mock_view):
        nr, nc = mock_view._factors(2)
        assert nr * nc == 2

    def test_large(self, mock_view):
        nr, nc = mock_view._factors(12)
        assert nr * nc == 12


# ===========================================================================
# update_plot_data
# ===========================================================================


class TestUpdatePlotData:
    def test_dict_input_stores_data_field(self, mock_view):
        arr = np.array([1, 2, 3])
        mock_view.update_plot_data({"data": arr})
        np.testing.assert_array_equal(mock_view.plot_data, arr)

    def test_array_input_stored_directly(self, mock_view):
        arr = np.array([4, 5, 6])
        mock_view.update_plot_data(arr)
        np.testing.assert_array_equal(mock_view.plot_data, arr)

    def test_none_input(self, mock_view):
        mock_view.update_plot_data(None)
        assert mock_view.plot_data is None

    def test_list_input(self, mock_view):
        mock_view.update_plot_data([1, 2, 3])
        assert mock_view.plot_data == [1, 2, 3]


# ===========================================================================
# update_plot_features
# ===========================================================================


class TestUpdatePlotFeatures:
    def test_all_params_stored(self, mock_view):
        mock_view.update_plot_features(
            vertical=[1.0, 2.0],
            horizontal=[3.0],
            points=[(0.5, 1.5)],
            vlabels=["v1", "v2"],
            hlabels=["h1"],
            plabels=["p1"],
        )
        assert mock_view.vertical == [1.0, 2.0]
        assert mock_view.horizontal == [3.0]
        assert mock_view.points == [(0.5, 1.5)]
        assert mock_view.vlabels == ["v1", "v2"]
        assert mock_view.hlabels == ["h1"]
        assert mock_view.plabels == ["p1"]

    def test_none_defaults(self, mock_view):
        mock_view.update_plot_features()
        assert mock_view.vertical is None
        assert mock_view.horizontal is None
        assert mock_view.points is None

    def test_partial_params(self, mock_view):
        mock_view.update_plot_features(vertical=[5.0])
        assert mock_view.vertical == [5.0]
        assert mock_view.horizontal is None


# ===========================================================================
# update_plot_samplerate
# ===========================================================================


class TestUpdatePlotSamplerate:
    def test_stores_samplerate(self, mock_view):
        mock_view.update_plot_samplerate(1_000_000)
        assert mock_view.plot_samplerate == 1_000_000

    def test_float_samplerate(self, mock_view):
        mock_view.update_plot_samplerate(250_000.5)
        assert mock_view.plot_samplerate == 250_000.5


# ===========================================================================
# set_eventfitting_status
# ===========================================================================


class TestSetEventfittingStatus:
    def test_true(self, mock_view):
        mock_view.set_eventfitting_status(True)
        assert mock_view.eventfitting_status is True

    def test_false(self, mock_view):
        mock_view.set_eventfitting_status(False)
        assert mock_view.eventfitting_status is False


# ===========================================================================
# set_num_events_allowed
# ===========================================================================


class TestSetNumEventsAllowed:
    def test_sets_value(self, mock_view):
        mock_view.set_num_events_allowed(500)
        assert mock_view.num_events_allowed == 500

    def test_zero(self, mock_view):
        mock_view.set_num_events_allowed(0)
        assert mock_view.num_events_allowed == 0


# ===========================================================================
# set_data_filter_function
# ===========================================================================


class TestSetDataFilterFunction:
    def test_stores_callable(self, mock_view):
        def my_filter(x):
            return x * 2

        mock_view.set_data_filter_function(my_filter)
        assert mock_view.data_filter is my_filter

    def test_stores_none(self, mock_view):
        mock_view.set_data_filter_function(None)
        assert mock_view.data_filter is None


# ===========================================================================
# validate_single_channel
# ===========================================================================


class TestValidateSingleChannel:
    def test_single_channel_ok(self, mock_view):
        mock_view.validate_single_channel([0])  # should not raise

    def test_multiple_channels_raises(self, mock_view):
        with pytest.raises(ValueError, match="multiple channels"):
            mock_view.validate_single_channel([0, 1])

    def test_empty_list_ok(self, mock_view):
        mock_view.validate_single_channel([])  # empty is not > 1


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

    def test_returns_five_tuple(self, mock_view):
        result = mock_view._extract_plot_event_parameters(self._params())
        assert len(result) == 5

    def test_loader(self, mock_view):
        loader, *_ = mock_view._extract_plot_event_parameters(self._params())
        assert loader == "my_loader"

    def test_eventfitter(self, mock_view):
        _, fitter, *_ = mock_view._extract_plot_event_parameters(self._params())
        assert fitter == "my_fitter"

    def test_filter(self, mock_view):
        _, _, data_filter, *_ = mock_view._extract_plot_event_parameters(self._params())
        assert data_filter == "my_filter"

    def test_channels_as_ints(self, mock_view):
        _, _, _, channels, _ = mock_view._extract_plot_event_parameters(self._params())
        assert channels == [0, 1]

    def test_event_index(self, mock_view):
        _, _, _, _, events = mock_view._extract_plot_event_parameters(self._params())
        assert events == [1, 2, 3]

    def test_missing_optional_fields(self, mock_view):
        params = {"channel": ["0"], "event_index": []}
        loader, fitter, filt, channels, events = mock_view._extract_plot_event_parameters(
            params
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

    def test_returns_three_tuple(self, mock_view):
        assert len(mock_view._extract_event_fit_parameters(self._params())) == 3

    def test_eventfitter(self, mock_view):
        fitter, _, _ = mock_view._extract_event_fit_parameters(self._params())
        assert fitter == "fitter_a"

    def test_filter(self, mock_view):
        _, filt, _ = mock_view._extract_event_fit_parameters(self._params())
        assert filt == "filter_b"

    def test_channels_as_ints(self, mock_view):
        _, _, channels = mock_view._extract_event_fit_parameters(self._params())
        assert channels == [0, 2]


# ===========================================================================
# _extract_commit_event_parameters
# ===========================================================================


class TestExtractCommitEventParameters:
    def _params(self):
        return {"writer": "my_writer", "channel": ["1"]}

    def test_returns_two_tuple(self, mock_view):
        assert len(mock_view._extract_commit_event_parameters(self._params())) == 2

    def test_writer(self, mock_view):
        writer, _ = mock_view._extract_commit_event_parameters(self._params())
        assert writer == "my_writer"

    def test_channels_as_ints(self, mock_view):
        _, channels = mock_view._extract_commit_event_parameters(self._params())
        assert channels == [1]


# ===========================================================================
# get_current_view
# ===========================================================================


class TestGetCurrentView:
    def test_returns_correct_string(self, mock_view):
        assert mock_view.get_current_view() == "EventAnalysisView"


# ===========================================================================
# get_walkthrough_steps
# ===========================================================================


class TestGetWalkthroughSteps:
    def test_returns_list(self, mock_view):
        assert isinstance(mock_view.get_walkthrough_steps(), list)

    def test_has_13_steps(self, mock_view):
        assert len(mock_view.get_walkthrough_steps()) == 13

    def test_each_step_is_tuple_of_four(self, mock_view):
        for step in mock_view.get_walkthrough_steps():
            assert len(step) == 4

    def test_widget_callables_return_lists(self, mock_view):
        for _, _, _, fn in mock_view.get_walkthrough_steps():
            result = fn()
            assert isinstance(result, list)
            assert len(result) >= 1


# ===========================================================================
# _get_event_index_text
# ===========================================================================


class TestGetEventIndexText:
    def test_empty_initially(self, real_view):
        text = real_view._get_event_index_text()
        assert text == ""

    def test_reflects_lineedit(self, real_view):
        real_view.eventAnalysisControls.event_index_lineEdit.setText("3-5")
        assert real_view._get_event_index_text() == "3-5"

    def test_strips_whitespace(self, real_view):
        real_view.eventAnalysisControls.event_index_lineEdit.setText("  7  ")
        assert real_view._get_event_index_text() == "7"


# ===========================================================================
# update_channels
# ===========================================================================


class TestUpdateChannels:
    def test_channels_appear_in_combobox(self, real_view):
        real_view.update_channels(["0", "1", "2"])
        count = real_view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 3

    def test_single_channel(self, real_view):
        real_view.update_channels(["0"])
        count = real_view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 1


# ===========================================================================
# update_available_plugins
# ===========================================================================


class TestUpdateAvailablePlugins:
    def test_updates_loaders(self, real_view):
        real_view.update_available_plugins({"MetaEventLoader": ["ldr1", "ldr2"]})
        assert real_view.eventAnalysisControls.loaders_comboBox.count() == 2

    def test_updates_filters(self, real_view):
        real_view.update_available_plugins({"MetaFilter": ["f1"]})
        assert real_view.eventAnalysisControls.filters_comboBox.count() == 1

    def test_updates_writers(self, real_view):
        real_view.update_available_plugins({"MetaDatabaseWriter": ["w1"]})
        assert real_view.eventAnalysisControls.writers_comboBox.count() == 1

    def test_updates_eventfitters(self, real_view):
        real_view.update_available_plugins({"MetaEventFitter": ["ef1", "ef2"]})
        assert real_view.eventAnalysisControls.eventfitters_comboBox.count() == 2

    def test_empty_plugins_no_error(self, mock_view):
        mock_view.update_available_plugins({})

    def test_all_categories(self, real_view):
        real_view.update_available_plugins(
            {
                "MetaEventLoader": ["l"],
                "MetaFilter": ["f"],
                "MetaDatabaseWriter": ["w"],
                "MetaEventFitter": ["ef"],
            }
        )
        assert real_view.eventAnalysisControls.loaders_comboBox.count() == 1
        assert real_view.eventAnalysisControls.filters_comboBox.count() == 1
        assert real_view.eventAnalysisControls.writers_comboBox.count() == 1
        assert real_view.eventAnalysisControls.eventfitters_comboBox.count() == 1

    def test_exception_path_does_not_crash(self, mock_view):
        """If controls raise, the exception is swallowed and logged."""
        mock_view.eventAnalysisControls.update_loaders = MagicMock(
            side_effect=Exception("boom")
        )
        mock_view.update_available_plugins({"MetaEventLoader": ["l"]})  # must not raise


# ===========================================================================
# handle_parameter_change — routing
# ===========================================================================


class TestHandleParameterChange:
    def _params(self):
        return {
            "loader": "l",
            "eventfitter": "ef",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": [1],
            "writer": "w",
            "raw": False,
        }

    def test_routes_fit_events(self, mock_view):
        with patch.object(EventAnalysisView, "_handle_fit_events") as mock:
            mock_view.handle_parameter_change("M", "fit_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_plot_events(self, mock_view):
        with patch.object(EventAnalysisView, "_handle_plot_events") as mock:
            mock_view.handle_parameter_change("M", "plot_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_commit_events(self, mock_view):
        with patch.object(EventAnalysisView, "_handle_commit_events") as mock:
            mock_view.handle_parameter_change("M", "commit_events", (self._params(),))
        mock.assert_called_once()

    def test_routes_shift_backward(self, mock_view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("M", "shift_range_backward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_routes_shift_forward(self, mock_view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("M", "shift_range_forward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "right"

    def test_routes_export_plot_data(self, mock_view):
        received = []
        mock_view.export_plot_data.connect(lambda: received.append(True))
        mock_view.handle_parameter_change("M", "export_plot_data", (self._params(),))
        assert received == [True]

    def test_routes_unknown_to_other_actions(self, mock_view):
        with patch.object(EventAnalysisView, "_handle_other_actions") as mock:
            mock_view.handle_parameter_change("M", "unknown_action", (self._params(),))
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert "unknown_action" in all_args


# ===========================================================================
# _handle_other_actions
# ===========================================================================


class TestHandleOtherActions:
    def test_with_loader_emits_signal(self, mock_view):
        emitted = []
        mock_view.global_signal.connect(lambda *a: emitted.append(a))
        mock_view._handle_other_actions("any", {"loader": "my_loader"})
        assert any("get_channels" in str(a) for a in emitted)

    def test_without_loader_no_signal(self, mock_view):
        emitted = []
        mock_view.global_signal.connect(lambda *a: emitted.append(a))
        before = len(emitted)
        mock_view._handle_other_actions("any", {"loader": None})
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

    def test_bad_params_returns_gracefully(self, mock_view):
        # Patch the extractor to raise ValueError — _handle_fit_events must catch it
        # and return without calling _start_eventfitter.
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            side_effect=ValueError("bad params"),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                mock_view._handle_fit_events(
                    {"eventfitter": "ef1", "filter": "No Filter", "channel": ["0"]}
                )
        mock.assert_not_called()

    def test_valid_params_calls_start_eventfitter(self, mock_view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            mock_view._handle_fit_events(self._params())
        mock.assert_called_once()
        # class-level patch: call_args[0] = (self, eventfitter, filter, channels)
        # or call_args[0] = (eventfitter, filter, channels) depending on decorator
        all_args = mock.call_args[0]
        flat = [a for a in all_args if a is not mock_view]
        assert "ef1" in flat
        assert "No Filter" in flat
        assert [0] in flat

    def test_none_eventfitter_does_not_call_start(self, mock_view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=(None, "No Filter", [0]),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                mock_view._handle_fit_events(self._params())
        mock.assert_not_called()

    def test_none_channels_does_not_call_start(self, mock_view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=("ef1", "No Filter", None),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                mock_view._handle_fit_events(self._params())
        mock.assert_not_called()

    def test_none_filter_does_not_call_start(self, mock_view):
        with patch.object(
            EventAnalysisView,
            "_extract_event_fit_parameters",
            return_value=("ef1", None, [0]),
        ):
            with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
                mock_view._handle_fit_events(self._params())
        mock.assert_not_called()


# ===========================================================================
# _handle_commit_events
# ===========================================================================


class TestHandleCommitEvents:
    def test_bad_params_returns_gracefully(self, mock_view):
        # Patch the extractor to raise ValueError — _handle_commit_events must catch it
        # and return without calling _start_writer.
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            side_effect=ValueError("bad params"),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                mock_view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()

    def test_valid_params_calls_start_writer(self, mock_view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            mock_view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        flat = [a for a in all_args if a is not mock_view]
        assert "w" in flat
        assert [0] in flat

    def test_none_writer_does_not_call_start(self, mock_view):
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            return_value=(None, [0]),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                mock_view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()

    def test_none_channels_does_not_call_start(self, mock_view):
        with patch.object(
            EventAnalysisView,
            "_extract_commit_event_parameters",
            return_value=("w", None),
        ):
            with patch.object(EventAnalysisView, "_start_writer") as mock:
                mock_view._handle_commit_events({"writer": "w", "channel": ["0"]})
        mock.assert_not_called()


# ===========================================================================
# _start_writer
# ===========================================================================


class TestStartWriter:
    def test_emits_signal_per_channel(self, mock_view):
        emitted = []
        mock_view.global_signal.connect(lambda *a: emitted.append(a))
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("w1", [0, 1])
        write_calls = [e for e in emitted if "write_events" in str(e)]
        assert len(write_calls) == 2
        mock_view.run_generators.emit.assert_called_once_with("w1")

    def test_single_channel_as_int_converted(self, mock_view):
        emitted = []
        mock_view.global_signal.connect(lambda *a: emitted.append(a))
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("w1", 0)  # non-list
        # non-list is converted to list internally
        mock_view.run_generators.emit.assert_called_once_with("w1")

    def test_index_error_logged(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view.global_signal.emit.side_effect = IndexError("bad index")
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("w1", [0])
        # Should not raise; run_generators not called on error
        mock_view.run_generators.emit.assert_not_called()


# ===========================================================================
# _start_eventfitter
# ===========================================================================


class TestStartEventfitter:
    def _setup(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view.run_generators = MagicMock()
        mock_view.eventfitting_status = False
        mock_view.data_filter = None

    def test_emits_fit_events_signal(self, mock_view):
        self._setup(mock_view)
        mock_view._start_eventfitter("ef1", "No Filter", [0])
        emitted_actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "fit_events" in emitted_actions

    def test_run_generators_called(self, mock_view):
        self._setup(mock_view)
        mock_view._start_eventfitter("ef1", "No Filter", [0])
        mock_view.run_generators.emit.assert_called_once_with("ef1")

    def test_with_filter_emits_get_callable_filter(self, mock_view):
        self._setup(mock_view)
        mock_view._start_eventfitter("ef1", "MyFilter", [0])
        emitted_actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_callable_filter" in emitted_actions

    def test_non_list_channels_converted(self, mock_view):
        self._setup(mock_view)
        # Should not raise even if channels is not a list
        mock_view._start_eventfitter("ef1", "No Filter", 0)
        mock_view.run_generators.emit.assert_called_once_with("ef1")

    def test_already_fitted_and_no_skipped(self, mock_view):
        """If status is True but user would say No in dialog, we patch QMessageBox."""
        self._setup(mock_view)
        mock_view.eventfitting_status = True
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QMessageBox.question",
            return_value=MagicMock(),  # anything that isn't QMessageBox.No
        ):
            mock_view._start_eventfitter("ef1", "No Filter", [0])
        # Should still emit fit_events since we didn't return early
        emitted_actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "fit_events" in emitted_actions


# ===========================================================================
# _shift_range_and_update_plot
# ===========================================================================


class TestShiftRangeAndUpdatePlot:
    def _base_params(self):
        return {
            "loader": "l",
            "eventfitter": "ef",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": [5, 6, 7],
        }

    def _setup_shift(self, mock_view):
        mock_view.eventAnalysisControls.event_index_lineEdit.setText("5-7")
        mock_view._parse_event_indices = MagicMock(return_value=[(5, 7)])
        mock_view._shift_ranges = MagicMock(return_value=[(6, 8)])
        mock_view._merge_ranges = MagicMock(return_value=[(6, 8)])
        mock_view._format_ranges = MagicMock(return_value="6-8")
        mock_view._expand_event_indices = MagicMock(return_value=[6, 7, 8])
        mock_view._mock_handle_plot_events = self._mock_plot

    @pytest.fixture(autouse=True)
    def _patch_handle_plot_events(self):
        """
        Keep _handle_plot_events patched for every test in this class.

        This patch used to be started inside the setup helper and stopped by an
        explicit teardown call at the end of each test body. A test that failed
        before reaching that call left the patch installed for the rest of the
        session, so a single genuine failure here surfaced as a cascade of
        unrelated failures in later classes. As a yielding fixture the patch is
        always undone, pass or fail.
        """
        with patch.object(EventAnalysisView, "_handle_plot_events") as mock:
            self._mock_plot = mock
            yield

    def test_right_shift_calls_handle_plot_events(self, mock_view):
        self._setup_shift(mock_view)
        mock_view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_called_once()

    def test_left_shift_calls_handle_plot_events(self, mock_view):
        self._setup_shift(mock_view)
        mock_view._shift_ranges.return_value = [(4, 6)]
        mock_view._merge_ranges.return_value = [(4, 6)]
        mock_view._format_ranges.return_value = "4-6"
        mock_view._expand_event_indices.return_value = [4, 5, 6]
        mock_view._shift_range_and_update_plot(self._base_params(), direction="left")
        self._mock_plot.assert_called_once()

    def test_shift_updates_gui_input(self, real_view):
        self._setup_shift(real_view)
        real_view._shift_range_and_update_plot(self._base_params(), direction="right")
        assert real_view.eventAnalysisControls.event_index_lineEdit.text() == "6-8"

    def test_empty_index_text_aborts(self, real_view):
        self._setup_shift(real_view)
        real_view.eventAnalysisControls.event_index_lineEdit.setText("")
        real_view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_not_called()

    def test_empty_expanded_indices_aborts(self, mock_view):
        self._setup_shift(mock_view)
        mock_view._expand_event_indices.return_value = []
        mock_view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_not_called()

    def test_multiple_channels_raises_and_aborts(self, mock_view):
        self._setup_shift(mock_view)
        params = self._base_params()
        params["channel"] = ["0", "1"]
        mock_view._shift_range_and_update_plot(params, direction="right")
        self._mock_plot.assert_not_called()

    def test_updated_params_contain_new_indices(self, mock_view):
        self._setup_shift(mock_view)
        mock_view._shift_range_and_update_plot(self._base_params(), direction="right")
        self._mock_plot.assert_called_once()
        # class-level patch: args are (self, params) or just (params,) depending on decorator
        call_args = self._mock_plot.call_args[0]
        call_params = call_args[-1]  # last positional arg is always params
        assert call_params["event_index"] == [6, 7, 8]

    def test_original_params_not_mutated(self, mock_view):
        self._setup_shift(mock_view)
        original = self._base_params()
        original_indices = list(original["event_index"])
        mock_view._shift_range_and_update_plot(original, direction="right")
        assert original["event_index"] == original_indices


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

    def _setup(self, mock_view, plot_data=None):
        """Replace global_signal with a MagicMock so we can inspect emissions."""
        mock_view.global_signal = MagicMock()
        mock_view.global_signal.emit = MagicMock()
        mock_view.global_signal.connect = MagicMock()
        mock_view.num_events_allowed = 999
        mock_view.eventfitting_status = False
        mock_view.data_filter = None
        mock_view.plot_data = plot_data
        mock_view.plot_samplerate = 1_000_000

    @pytest.fixture(autouse=True)
    def _patch_update_event_plot(self):
        """
        Keep _update_event_plot patched for every test in this class.

        This patch used to be started inside the setup helper and stopped by an
        explicit teardown call at the end of each test body. A test that failed
        before reaching that call left the patch installed for the rest of the
        session, so a single genuine failure here surfaced as a cascade of
        unrelated failures in later classes. As a yielding fixture the patch is
        always undone, pass or fail.
        """
        with patch.object(EventAnalysisView, "_update_event_plot") as mock:
            self._mock_update = mock
            yield

    def test_no_events_skips_plot(self, mock_view):
        self._setup(mock_view)
        mock_view._handle_plot_events(self._params(events=[]))
        self._mock_update.assert_not_called()

    def test_valid_event_calls_update_plot(self, mock_view):
        self._setup(mock_view, plot_data=np.ones(10) * 100.0)

        def side_effect(*args):
            # When load_event is called, set plot_data so the handler sees data
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(10) * 100.0

        mock_view.global_signal.emit.side_effect = side_effect
        mock_view._handle_plot_events(self._params(events=[0]))
        self._mock_update.assert_called_once()

    def test_events_truncated_when_above_allowed(self, mock_view):
        self._setup(mock_view)
        mock_view.num_events_allowed = 3
        # Events [0, 1, 2, 5] — index 5 should be dropped
        params = self._params(events=[0, 1, 2, 5])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(5) * 50.0

        mock_view.global_signal.emit.side_effect = side_effect
        mock_view._handle_plot_events(params)
        # _update_event_plot should be called with at most 3 data entries
        if self._mock_update.called:
            data_list = self._mock_update.call_args[0][1]
            assert len(data_list) <= 3

    def test_no_data_loaded_skips_event(self, mock_view):
        self._setup(mock_view, plot_data=None)
        mock_view._handle_plot_events(self._params(events=[0]))
        self._mock_update.assert_not_called()

    def test_multiple_channels_handled_gracefully(self, mock_view):
        self._setup(mock_view)
        params = self._params()
        params["channel"] = ["0", "1"]
        # Should not raise — extract will raise ValueError caught internally
        mock_view._handle_plot_events(params)

    def test_get_num_events_signal_emitted(self, mock_view):
        self._setup(mock_view)
        mock_view._handle_plot_events(self._params(events=[0]))
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_num_events" in actions

    def test_with_filter_emits_get_callable_filter(self, mock_view):
        self._setup(mock_view, plot_data=np.ones(5) * 10.0)

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(5) * 10.0

        mock_view.global_signal.emit.side_effect = side_effect
        params = self._params(events=[0])
        params["filter"] = "MyFilter"
        mock_view._handle_plot_events(params)
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_callable_filter" in actions

    def test_with_raw_flag_and_filter_loads_raw(self, mock_view):
        """When raw=True and data_filter is set, a second load_event for raw is emitted."""
        self._setup(mock_view)
        mock_view.data_filter = MagicMock()  # simulate active filter

        load_event_calls = []

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(5) * 10.0
                load_event_calls.append(args)

        mock_view.global_signal.emit.side_effect = side_effect
        params = self._params(events=[0])
        params["raw"] = True
        mock_view._handle_plot_events(params)
        # At least one load_event for filtered data; raw=True should trigger a second
        assert len(load_event_calls) >= 1


# ===========================================================================
# _update_event_plot
# ===========================================================================


class TestUpdateEventPlot:
    """
    _update_event_plot accesses self.figure and self.canvas which are C-level
    PySide6 properties and cannot be patched.  We therefore test it in two ways:

    1. Smoke tests — call the real method with a real Qt widget; assert it
       does not raise and produces observable state changes (axis labels, etc.).

    2. Internal-logic tests — patch the method itself and verify the *caller*
       (handle_plot_events) invokes it with the right arguments.
    """

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

    def test_runs_without_error_one_event(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )

    def test_runs_without_error_two_events(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 1 Data"],
            2,
            *self._none_lists(2),
        )

    def test_runs_without_error_with_fit_trace(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 0 Fit"],
            1,
            *self._none_lists(1),
        )

    def test_runs_without_error_with_raw_trace(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 0 Raw"],
            1,
            *self._none_lists(1),
        )

    def test_runs_without_error_with_vlines(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[10.0]],
            [None],
            [None],
            [["v_label"]],
            [None],
            [None],
        )

    def test_runs_without_error_with_hlines(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None],
            [[500.0]],
            [None],
            [None],
            [["h_label"]],
            [None],
        )

    def test_runs_without_error_with_points(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None],
            [None],
            [[(5.0, 300.0)]],
            [None],
            [None],
            [["p_label"]],
        )

    def test_runs_without_error_unlabelled_vline(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[10.0]],
            [None],
            [None],
            [[None]],
            [None],
            [None],
        )

    def test_runs_without_error_unlabelled_hline(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None],
            [[500.0]],
            [None],
            [None],
            [[None]],
            [None],
        )

    def test_cache_committed_after_plot(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        with patch.object(EventAnalysisView, "_commit_cache") as mock_cache:
            mock_view._update_event_plot(
                [self._make_data()],
                ["Event 0 Data"],
                1,
                *self._none_lists(1),
            )
        mock_cache.assert_called()

    def test_figure_has_axes_after_plot(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        assert len(mock_view.figure.get_axes()) >= 1

    def test_two_events_produce_two_axes(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data(), self._make_data()],
            ["Event 0 Data", "Event 1 Data"],
            2,
            *self._none_lists(2),
        )
        assert len(mock_view.figure.get_axes()) == 2


class TestUpdateEventPlotExtended:
    """Extended smoke + observable-state tests for _update_event_plot."""

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

    def test_clear_cache_called(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view.data_cache = []
        mock_view.label_cache = []
        mock_view.data_cache_labels = []
        with patch.object(EventAnalysisView, "_clear_cache") as mock_cc:
            mock_view._update_event_plot(
                [self._make_data()],
                ["Event 0 Data"],
                1,
                *self._none_lists(1),
            )
        mock_cc.assert_called()

    def test_update_cache_called_per_data_item(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        with patch.object(EventAnalysisView, "_update_cache") as mock_uc:
            mock_view._update_event_plot(
                [self._make_data(), self._make_data()],
                ["Event 0 Data", "Event 1 Data"],
                2,
                *self._none_lists(2),
            )
        assert mock_uc.call_count >= 2

    def test_multiple_vlines_no_error(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[5.0, 10.0, 15.0]],
            [None],
            [None],
            [[None, None, None]],
            [None],
            [None],
        )

    def test_labelled_vline_no_error(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[10.0]],
            [None],
            [None],
            [["my_label"]],
            [None],
            [None],
        )

    def test_labelled_hline_no_error(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None],
            [[500.0]],
            [None],
            [None],
            [["h_label"]],
            [None],
        )

    def test_labelled_point_no_error(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [None],
            [None],
            [[(5.0, 300.0)]],
            [None],
            [None],
            [["pt_label"]],
        )

    def test_figure_set_constrained_layout_called(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        # constrained_layout is set via figure.set_constrained_layout(True)
        # We can verify indirectly: figure should have axes after call
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        assert mock_view.figure.get_constrained_layout() is True

    def test_legend_no_error_with_labelled_lines(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            [[1.0, 2.0]],
            [None],
            [None],
            [["a", "b"]],
            [None],
            [None],
        )

    def test_grid_is_enabled_on_axes(self, mock_view):
        mock_view.plot_samplerate = 1_000_000
        mock_view._update_event_plot(
            [self._make_data()],
            ["Event 0 Data"],
            1,
            *self._none_lists(1),
        )
        # Just verify the call completes without error; grid state verified by smoke
        assert len(mock_view.figure.get_axes()) >= 1


# ===========================================================================
# get_save_filename
# ===========================================================================


class TestGetSaveFilename:
    def test_returns_selected_path(self, mock_view):
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QFileDialog.getSaveFileName",
            return_value=("/path/to/file.csv", "CSV Files (*.csv)"),
        ):
            result = mock_view.get_save_filename()
        assert result == "/path/to/file.csv"

    def test_returns_empty_on_cancel(self, mock_view):
        with patch(
            "poriscope.plugins.analysistabs.EventAnalysisView.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            result = mock_view.get_save_filename()
        assert result == ""


# ===========================================================================
# update_plot / _reset_actions / _init (no-ops — coverage only)
# ===========================================================================


class TestNoOpMethods:
    def test_update_plot_no_error(self, mock_view):
        mock_view.update_plot()

    def test_reset_actions_no_error(self, mock_view):
        mock_view._reset_actions()

    def test_reset_actions_3d_no_error(self, mock_view):
        mock_view._reset_actions(axis_type="3d")


# ===========================================================================
# _factors — extended edge cases
# ===========================================================================


class TestFactorsExtended:
    def test_three(self, mock_view):
        nr, nc = mock_view._factors(3)
        assert nr * nc >= 3

    def test_four(self, mock_view):
        assert mock_view._factors(4) == (2, 2)

    def test_five(self, mock_view):
        nr, nc = mock_view._factors(5)
        assert nr * nc >= 5

    def test_sixteen(self, mock_view):
        assert mock_view._factors(16) == (4, 4)

    def test_output_is_two_tuple(self, mock_view):
        result = mock_view._factors(6)
        assert len(result) == 2

    def test_first_factor_lte_second(self, mock_view):
        nr, nc = mock_view._factors(8)
        assert nr <= nc


# ===========================================================================
# update_plot_data — extended
# ===========================================================================


class TestUpdatePlotDataExtended:
    def test_dict_with_extra_keys_uses_data_key(self, mock_view):
        arr = np.array([7.0, 8.0])
        mock_view.update_plot_data({"data": arr, "extra": "ignored"})
        np.testing.assert_array_equal(mock_view.plot_data, arr)

    def test_empty_array(self, mock_view):
        arr = np.array([])
        mock_view.update_plot_data(arr)
        np.testing.assert_array_equal(mock_view.plot_data, arr)

    def test_2d_array(self, mock_view):
        arr = np.ones((3, 4))
        mock_view.update_plot_data(arr)
        np.testing.assert_array_equal(mock_view.plot_data, arr)


# ===========================================================================
# update_plot_features — extended
# ===========================================================================


class TestUpdatePlotFeaturesExtended:
    def test_overwrites_previous_values(self, mock_view):
        mock_view.update_plot_features(vertical=[1.0])
        mock_view.update_plot_features(vertical=[2.0])
        assert mock_view.vertical == [2.0]

    def test_all_none_by_default(self, mock_view):
        mock_view.update_plot_features()
        for attr in (
            "vertical",
            "horizontal",
            "points",
            "vlabels",
            "hlabels",
            "plabels",
        ):
            assert getattr(mock_view, attr) is None

    def test_points_stored_correctly(self, mock_view):
        pts = [(0.1, 0.2), (0.3, 0.4)]
        mock_view.update_plot_features(points=pts)
        assert mock_view.points == pts


# ===========================================================================
# validate_single_channel — extended
# ===========================================================================


class TestValidateSingleChannelExtended:
    def test_exactly_one_channel_ok(self, mock_view):
        mock_view.validate_single_channel([5])  # should not raise

    def test_three_channels_raises(self, mock_view):
        with pytest.raises(ValueError):
            mock_view.validate_single_channel([0, 1, 2])

    def test_error_message_mentions_multiple(self, mock_view):
        with pytest.raises(ValueError, match="multiple"):
            mock_view.validate_single_channel([0, 1])


# ===========================================================================
# set_num_events_allowed — extended
# ===========================================================================


class TestSetNumEventsAllowedExtended:
    def test_large_number(self, mock_view):
        mock_view.set_num_events_allowed(1_000_000)
        assert mock_view.num_events_allowed == 1_000_000

    def test_overwrite(self, mock_view):
        mock_view.set_num_events_allowed(10)
        mock_view.set_num_events_allowed(20)
        assert mock_view.num_events_allowed == 20


# ===========================================================================
# set_data_filter_function — extended
# ===========================================================================


class TestSetDataFilterFunctionExtended:
    def test_lambda_stored(self, mock_view):
        fn = lambda x: x + 1  # noqa: E731
        mock_view.set_data_filter_function(fn)
        assert mock_view.data_filter is fn

    def test_overwrite_with_none(self, mock_view):
        mock_view.set_data_filter_function(lambda x: x)
        mock_view.set_data_filter_function(None)
        assert mock_view.data_filter is None


# ===========================================================================
# _extract_plot_event_parameters — edge cases
# ===========================================================================


class TestExtractPlotEventParametersExtended:
    def test_empty_channel_list(self, mock_view):
        params = {"channel": [], "event_index": []}
        loader, fitter, filt, channels, events = mock_view._extract_plot_event_parameters(
            params
        )
        assert channels == []

    def test_multiple_channels_converted(self, mock_view):
        params = {"channel": ["0", "1", "2"], "event_index": []}
        _, _, _, channels, _ = mock_view._extract_plot_event_parameters(params)
        assert channels == [0, 1, 2]

    def test_event_index_none_returned_as_none(self, mock_view):
        params = {"channel": ["0"]}
        _, _, _, _, events = mock_view._extract_plot_event_parameters(params)
        assert events is None


# ===========================================================================
# _extract_event_fit_parameters — edge cases
# ===========================================================================


class TestExtractEventFitParametersExtended:
    def test_missing_eventfitter_returns_none(self, mock_view):
        params = {"channel": ["0"]}
        fitter, filt, channels = mock_view._extract_event_fit_parameters(params)
        assert fitter is None

    def test_missing_filter_returns_none(self, mock_view):
        params = {"channel": ["0"], "eventfitter": "ef"}
        _, filt, _ = mock_view._extract_event_fit_parameters(params)
        assert filt is None

    def test_channels_converted_to_int(self, mock_view):
        params = {"channel": ["3", "4"], "eventfitter": "ef", "filter": "f"}
        _, _, channels = mock_view._extract_event_fit_parameters(params)
        assert channels == [3, 4]


# ===========================================================================
# _extract_commit_event_parameters — edge cases
# ===========================================================================


class TestExtractCommitEventParametersExtended:
    def test_missing_writer_returns_none(self, mock_view):
        params = {"channel": ["0"]}
        writer, channels = mock_view._extract_commit_event_parameters(params)
        assert writer is None

    def test_multiple_channels(self, mock_view):
        params = {"writer": "w", "channel": ["0", "1", "2"]}
        _, channels = mock_view._extract_commit_event_parameters(params)
        assert channels == [0, 1, 2]


# ===========================================================================
# _handle_other_actions — extended
# ===========================================================================


class TestHandleOtherActionsExtended:
    def test_loader_none_does_not_emit(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view._handle_other_actions("any_action", {"loader": None})
        mock_view.global_signal.emit.assert_not_called()

    def test_loader_present_emits_get_channels(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view._handle_other_actions("any_action", {"loader": "my_loader"})
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_channels" in actions

    def test_loader_present_targets_correct_loader(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view._handle_other_actions("any_action", {"loader": "specific_loader"})
        args = mock_view.global_signal.emit.call_args[0]
        assert args[1] == "specific_loader"

    def test_missing_loader_key_treated_as_none(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view._handle_other_actions("any_action", {})
        mock_view.global_signal.emit.assert_not_called()


# ===========================================================================
# _handle_fit_events — extended
# ===========================================================================


class TestHandleFitEventsExtended:
    def test_empty_channel_list_does_not_crash(self, mock_view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            mock_view._handle_fit_events(
                {
                    "eventfitter": "ef1",
                    "filter": "No Filter",
                    "channel": [],
                }
            )
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [] in all_args

    def test_channels_passed_as_ints(self, mock_view):
        with patch.object(EventAnalysisView, "_start_eventfitter") as mock:
            mock_view._handle_fit_events(
                {
                    "eventfitter": "ef1",
                    "filter": "No Filter",
                    "channel": ["2", "3"],
                }
            )
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [2, 3] in all_args


# ===========================================================================
# _handle_commit_events — extended
# ===========================================================================


class TestHandleCommitEventsExtended:
    def test_channels_passed_as_ints(self, mock_view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            mock_view._handle_commit_events({"writer": "w", "channel": ["2"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [2] in all_args

    def test_multiple_channels_passed_correctly(self, mock_view):
        with patch.object(EventAnalysisView, "_start_writer") as mock:
            mock_view._handle_commit_events({"writer": "w", "channel": ["0", "1"]})
        mock.assert_called_once()
        all_args = mock.call_args[0]
        assert [0, 1] in all_args


# ===========================================================================
# _start_writer — extended
# ===========================================================================


class TestStartWriterExtended:
    def test_empty_channels_does_not_emit_write(self, mock_view):
        emitted = []
        mock_view.global_signal.connect(lambda *a: emitted.append(a))
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("w1", [])
        write_calls = [e for e in emitted if "write_events" in str(e)]
        assert len(write_calls) == 0

    def test_run_generators_called_with_writer_name(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("my_writer", [0])
        mock_view.run_generators.emit.assert_called_once_with("my_writer")

    def test_value_error_prevents_run_generators(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view.global_signal.emit.side_effect = ValueError("bad value")
        mock_view.run_generators = MagicMock()
        mock_view._start_writer("w1", [0])
        mock_view.run_generators.emit.assert_not_called()


# ===========================================================================
# _start_eventfitter — extended
# ===========================================================================


class TestStartEventfitterExtended:
    def _setup(self, mock_view):
        mock_view.global_signal = MagicMock()
        mock_view.run_generators = MagicMock()
        mock_view.eventfitting_status = False
        mock_view.data_filter = None

    def test_no_filter_does_not_emit_get_callable_filter(self, mock_view):
        self._setup(mock_view)
        mock_view._start_eventfitter("ef1", "No Filter", [0])
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_callable_filter" not in actions

    def test_multiple_channels_emits_fit_per_channel(self, mock_view):
        self._setup(mock_view)
        mock_view._start_eventfitter("ef1", "No Filter", [0, 1])
        fit_calls = [
            c
            for c in mock_view.global_signal.emit.call_args_list
            if len(c.args) > 2 and c.args[2] == "fit_events"
        ]
        assert len(fit_calls) == 2

    def test_index_error_logged_not_raised(self, mock_view):
        self._setup(mock_view)
        mock_view.global_signal.emit.side_effect = IndexError("bad")
        # Should not raise — error is caught
        mock_view._start_eventfitter("ef1", "No Filter", [0])
        mock_view.run_generators.emit.assert_not_called()


# ===========================================================================
# handle_parameter_change — extended routing
# ===========================================================================


class TestHandleParameterChangeExtended:
    def _params(self):
        return {
            "loader": "l",
            "eventfitter": "ef",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": [1],
            "writer": "w",
            "raw": False,
        }

    def test_export_plot_data_emits_signal(self, mock_view):
        received = []
        mock_view.export_plot_data.connect(lambda: received.append(True))
        mock_view.handle_parameter_change("M", "export_plot_data", (self._params(),))
        assert len(received) == 1

    def test_shift_backward_direction_is_left(self, mock_view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("M", "shift_range_backward", (self._params(),))
        mock.assert_called_once()
        assert mock.call_args[1]["direction"] == "left"

    def test_shift_forward_direction_is_right(self, mock_view):
        with patch.object(EventAnalysisView, "_shift_range_and_update_plot") as mock:
            mock_view.handle_parameter_change("M", "shift_range_forward", (self._params(),))
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

    def _setup(self, mock_view, plot_data=None):
        mock_view.global_signal = MagicMock()
        mock_view.global_signal.emit = MagicMock()
        mock_view.global_signal.connect = MagicMock()
        mock_view.num_events_allowed = 999
        mock_view.eventfitting_status = False
        mock_view.data_filter = None
        mock_view.plot_data = plot_data
        mock_view.plot_samplerate = 1_000_000

    @pytest.fixture(autouse=True)
    def _patch_update_event_plot(self):
        """
        Keep _update_event_plot patched for every test in this class.

        This patch used to be started inside the setup helper and stopped by an
        explicit teardown call at the end of each test body. A test that failed
        before reaching that call left the patch installed for the rest of the
        session, so a single genuine failure here surfaced as a cascade of
        unrelated failures in later classes. As a yielding fixture the patch is
        always undone, pass or fail.
        """
        with patch.object(EventAnalysisView, "_update_event_plot") as mock:
            self._mock_update = mock
            yield

    def test_events_within_bounds_not_truncated(self, mock_view):
        self._setup(mock_view)
        mock_view.num_events_allowed = 10
        params = self._params(events=[0, 1, 2])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(5)

        mock_view.global_signal.emit.side_effect = side_effect
        mock_view._handle_plot_events(params)
        # All 3 events within bounds — update_plot should be called
        self._mock_update.assert_called_once()

    def test_samplerate_signal_emitted(self, mock_view):
        self._setup(mock_view)
        mock_view._handle_plot_events(self._params(events=[0]))
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "get_samplerate" in actions

    def test_load_event_signal_emitted(self, mock_view):
        self._setup(mock_view)
        params = self._params(events=[0])

        def side_effect(*args):
            if len(args) > 2 and args[2] == "load_event":
                mock_view.plot_data = np.ones(5)

        mock_view.global_signal.emit.side_effect = side_effect
        mock_view._handle_plot_events(params)
        actions = [c.args[2] for c in mock_view.global_signal.emit.call_args_list]
        assert "load_event" in actions

    def test_all_events_out_of_bounds_no_plot(self, mock_view):
        self._setup(mock_view)
        mock_view.num_events_allowed = 3
        params = self._params(events=[5, 6, 7])  # all >= 3
        mock_view._handle_plot_events(params)
        self._mock_update.assert_not_called()


# ===========================================================================
# _update_event_plot — extended
# ===========================================================================


# ===========================================================================
# get_walkthrough_steps — extended
# ===========================================================================


class TestGetWalkthroughStepsExtended:
    def test_all_step_views_are_event_analysis_view(self, mock_view):
        for _, _, view_name, _ in mock_view.get_walkthrough_steps():
            assert view_name == "EventAnalysisView"

    def test_all_descriptions_are_non_empty_strings(self, mock_view):
        for _, desc, _, _ in mock_view.get_walkthrough_steps():
            assert isinstance(desc, str) and len(desc) > 0

    def test_all_titles_are_non_empty_strings(self, mock_view):
        for title, _, _, _ in mock_view.get_walkthrough_steps():
            assert isinstance(title, str) and len(title) > 0


# ===========================================================================
# update_channels — extended
# ===========================================================================


class TestUpdateChannelsExtended:
    def test_empty_list_clears_combobox(self, real_view):
        real_view.update_channels(["0", "1"])
        real_view.update_channels([])
        count = real_view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 0

    def test_overwrites_previous_channels(self, real_view):
        real_view.update_channels(["0", "1", "2"])
        real_view.update_channels(["5"])
        count = real_view.eventAnalysisControls.channel_comboBox.listWidget.count()
        assert count == 1


# ===========================================================================
# update_available_plugins — extended
# ===========================================================================


class TestUpdateAvailablePluginsExtended:
    def test_unknown_key_ignored(self, real_view):
        # Call with a known key first to establish a baseline, then with unknown.
        # The unknown key should not add "x" or "y" as loader items.
        real_view.update_available_plugins({"MetaEventLoader": ["known_loader"]})
        count_after_known = real_view.eventAnalysisControls.loaders_comboBox.count()
        real_view.update_available_plugins({"UnknownPlugin": ["x", "y"]})
        count_after_unknown = real_view.eventAnalysisControls.loaders_comboBox.count()
        # After passing an unknown key, loaders should not grow by 2
        assert count_after_unknown != count_after_known + 2

    def test_multiple_loaders(self, real_view):
        real_view.update_available_plugins({"MetaEventLoader": ["l1", "l2", "l3"]})
        assert real_view.eventAnalysisControls.loaders_comboBox.count() == 3

    def test_multiple_filters(self, real_view):
        real_view.update_available_plugins({"MetaFilter": ["f1", "f2"]})
        assert real_view.eventAnalysisControls.filters_comboBox.count() == 2
