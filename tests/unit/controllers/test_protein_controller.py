"""
Unit-test suite for ProteinController.

Uses:
  - A session-scoped QApplication fixture
  - A per-test ProteinController() fixture (real view/model, as built by _init)
  - view.add_text_to_display mocked/observed per-test where relevant

Run with:
    pytest test_protein_controller.py -v
    pytest test_protein_controller.py --cov=poriscope --cov-report=html
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.ProteinModel import EnsembleFit, ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView

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
def controller(qt_app):
    """
    Real ProteinController, built via the real _init() (so self.view is a real
    ProteinView and self.model is a real ProteinModel, exactly as in the running
    application).
    """
    c = ProteinController()
    return c


# ===========================================================================
# Construction
# ===========================================================================


class TestInit:
    def test_creates_real_view(self, controller):
        assert isinstance(controller.view, ProteinView)

    def test_creates_real_model(self, controller):
        assert isinstance(controller.model, ProteinModel)


# ===========================================================================
# relay_query — the big dispatch method
# ===========================================================================


class TestRelayQuery:
    def test_debug_no_query_shows_warning_dialog(self, controller):
        with patch(
            "poriscope.utils.MetaSubsetTabController.QMessageBox.warning"
        ) as mock_warn:
            controller.relay_query("", "syntax error here", "events")
        mock_warn.assert_called_once()
        args = mock_warn.call_args[0]
        assert args[0] is controller.view
        assert "syntax error here" in args[2]

    def test_valid_query_sets_view_query(self, controller):
        controller.relay_query("SELECT * FROM events", "", "events")
        assert controller.view.query == "SELECT * FROM events"
        assert controller.view.table_name == "events"

    def test_new_filter_added_with_assisted_suffix(self, controller):
        # The name and text arrive as arguments rather than being read back off
        # the View, so the Controller never reads View-private state.
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
            "f1",
            None,
            "dur > 100",
        )
        assert "f1_assisted" in controller.view.subset_filters
        assert controller.view.subset_filters["f1_assisted"] == "dur > 100"

    def test_new_filter_does_not_double_suffix(self, controller):
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
            "f1_assisted",
            None,
            "dur > 100",
        )
        assert "f1_assisted" in controller.view.subset_filters
        assert "f1_assisted_assisted" not in controller.view.subset_filters

    def test_new_filter_empty_text_emits_full_dataset_message(self, controller):
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events",
            "",
            "events",
            "validate_new_filter",
            "f1",
            None,
            "",
        )
        assert any("no WHERE clause" in m for m in received)

    def test_new_filter_emits_added_message(self, controller):
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
            "f1",
            None,
            "dur > 100",
        )
        assert any("added" in m for m in received)

    def test_new_filter_calls_replace_filter_item(self, controller):
        with patch.object(controller.view, "replace_filter_item") as mock_replace:
            controller.relay_query(
                "SELECT dur FROM events WHERE dur > 100",
                "",
                "events",
                "validate_new_filter",
                "f1",
                None,
                "dur > 100",
            )
        mock_replace.assert_called_once_with("f1_assisted")

    def test_new_filter_none_name_skips_add(self, controller):
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 100",
            "",
            "events",
            "validate_new_filter",
            None,
            None,
            "dur > 100",
        )
        assert controller.view.subset_filters == {}

    def test_edited_filter_removes_old_adds_new(self, controller):
        controller.view.subset_filters["old_assisted"] = "dur > 1"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
            "new",
            "old_assisted",
            "dur > 200",
        )
        assert "old_assisted" not in controller.view.subset_filters
        assert "new_assisted" in controller.view.subset_filters
        assert controller.view.subset_filters["new_assisted"] == "dur > 200"

    def test_edited_filter_no_old_name_only_adds_new(self, controller):
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
            "new",
            None,
            "dur > 200",
        )
        assert "new_assisted" in controller.view.subset_filters

    def test_edited_filter_empty_text_emits_full_dataset_message(self, controller):
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events",
            "",
            "events",
            "validate_edited_filter",
            "new",
            "old",
            "",
        )
        assert any("FULL DATASET" in m for m in received)

    def test_edited_filter_emits_updated_message(self, controller):
        received = []
        controller.view.add_text_to_display.connect(lambda m, s: received.append(m))
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
            "new",
            "old",
            "dur > 200",
        )
        assert any("updated" in m for m in received)

    def test_edited_filter_calls_update_filter_name(self, controller):
        with patch.object(controller.view, "update_filter_name") as mock_update:
            controller.relay_query(
                "SELECT dur FROM events WHERE dur > 200",
                "",
                "events",
                "validate_edited_filter",
                "new",
                "old",
                "dur > 200",
            )
        mock_update.assert_called_once_with("old", "new_assisted")

    def test_edited_filter_none_name_skips_update(self, controller):
        controller.view.subset_filters["old"] = "dur > 1"
        controller.relay_query(
            "SELECT dur FROM events WHERE dur > 200",
            "",
            "events",
            "validate_edited_filter",
            None,
            "old",
            "dur > 200",
        )
        # old filter should remain untouched since new_name is None
        assert controller.view.subset_filters.get("old") == "dur > 1"


# ===========================================================================
# get_session_state / restore_session_state
# ===========================================================================


class TestSessionState:
    def test_get_session_state_returns_view_subset_filters(self, controller):
        controller.view.subset_filters = {"f1": "dur>100"}
        assert controller.get_session_state() == {"subset_filters": {"f1": "dur>100"}}

    def test_restore_session_state_applies_subset_filters(self, controller):
        controller.restore_session_state(
            {"metaclass": "MetaController", "subset_filters": {"f1": "dur>100"}}
        )
        assert controller.view.subset_filters == {"f1": "dur>100"}

    def test_restore_session_state_is_noop_without_subset_filters(self, controller):
        controller.restore_session_state({"metaclass": "MetaController"})
        assert controller.view.subset_filters == {}


# ===========================================================================
# fit_event_histograms / fit_distribution_events - the binning's destination
# ===========================================================================
#
# Neither slot once had a test of its own: their callers were covered, and that
# is exactly what made the gap invisible. They do real work now - bin, then fit, then hand
# back - so a wrong call shape or a swallowed failure would have satisfied the
# whole suite.


def _event(event_id=1, blockage=0.3, rng_seed=0):
    """
    One synthetic event, shaped as ``load_event_data`` yields them.

    :param event_id: the event's id
    :type event_id: int
    :param blockage: the fraction of the baseline the event blocks
    :type blockage: float
    :param rng_seed: the seed for the synthetic noise
    :type rng_seed: int
    :return: one event payload
    :rtype: dict
    """
    rng = np.random.default_rng(rng_seed)
    n, sr, padding_us = 2000, 1_000_000, 100
    pad = int(padding_us * sr * 1e-6)
    baseline = 1000.0
    trace = np.full(n, baseline * (1.0 - blockage)) + rng.normal(0, 10.0, n)
    trace[:pad] = baseline + rng.normal(0, 10.0, pad)
    trace[-pad:] = baseline + rng.normal(0, 10.0, pad)
    return {
        "id": event_id,
        "event_id": event_id,
        "experiment_id": 1,
        "channel_id": 0,
        "raw_data": trace.copy(),
        "filtered_data": trace.copy(),
        "samplerate": sr,
        "padding_before": padding_us,
        "padding_after": padding_us,
    }


def _two_level_event(event_id=1, low=0.25, high=0.55, rng_seed=0, noise=8.0):
    """
    An event that blocks the pore at two distinct levels.

    A single-level event's fractional-blockage histogram has one peak, which the
    double-gaussian sanity check refuses - correctly, since the protein tab exists
    to describe two-level events. Anything driving the chain to its end needs one
    of these.

    :param event_id: the event's id
    :type event_id: int
    :param low: the smaller fractional blockage
    :type low: float
    :param high: the larger fractional blockage
    :type high: float
    :param rng_seed: the seed for the synthetic noise
    :type rng_seed: int
    :param noise: the noise amplitude in picoamps
    :type noise: float
    :return: one event payload
    :rtype: dict
    """
    rng = np.random.default_rng(rng_seed)
    n, sr, padding_us = 4000, 1_000_000, 100
    pad = int(padding_us * sr * 1e-6)
    baseline = 1000.0
    trace = np.empty(n)
    trace[:pad] = baseline
    trace[-pad:] = baseline
    half = (n - 2 * pad) // 2
    trace[pad : pad + half] = baseline * (1.0 - low)
    trace[pad + half : n - pad] = baseline * (1.0 - high)
    trace += rng.normal(0, noise, n)
    return {
        "id": event_id,
        "event_id": event_id,
        "experiment_id": 1,
        "channel_id": 0,
        "raw_data": trace.copy(),
        "filtered_data": trace.copy(),
        "samplerate": sr,
        "padding_before": padding_us,
        "padding_after": padding_us,
    }


class TestFitEventHistograms:
    """Bin every event, fit every histogram, hand both back to be drawn."""

    def test_the_view_is_handed_one_histogram_and_one_fit_per_event(
        self, controller
    ) -> None:
        """
        The drawing half lays out one subplot per event in the order given, so the
        two lists it receives have to stay index-aligned with the events.
        """
        controller.view.set_event_histogram_fits = MagicMock()
        events = [_event(1), _event(2, rng_seed=1)]

        controller.fit_event_histograms(events, "Filtered Histogram", None, False)

        fits, histograms, event_data = (
            controller.view.set_event_histogram_fits.call_args.args
        )
        assert event_data is events
        assert len(fits) == len(histograms) == 2
        for bincenters, amplitude in histograms:
            assert len(bincenters) == len(amplitude) > 0

    def test_the_bin_request_reaches_the_binning(self, controller) -> None:
        """An explicit count is the cheapest way to see the request got through."""
        controller.view.set_event_histogram_fits = MagicMock()

        controller.fit_event_histograms([_event(1)], "Filtered Histogram", [37], False)

        histograms = controller.view.set_event_histogram_fits.call_args.args[1]
        assert len(histograms[0][0]) == 37

    def test_an_unusable_bin_request_is_reported_and_draws_nothing(
        self, controller, mocker
    ) -> None:
        """
        A stale grid of subplots must not be left under this request's label, and
        the refusal has to reach the user rather than only the log.
        """
        controller.view.set_event_histogram_fits = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

        controller.fit_event_histograms([_event(1)], "Filtered Histogram", "bad", False)

        controller.view.set_event_histogram_fits.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to fit the event histograms" in m for m in messages)


class TestUpdateIndividualDistribution:
    """Fetch, bin, fit and sample one subset; keep the fit; have the View draw it."""

    SCOPE = {"exp1": ["3"]}

    def _fetch(self, controller, events):
        """
        Answer the fetch with a query and the given events, without a real loader.

        :param controller: the controller under test
        :type controller: ProteinController
        :param events: the events to answer with
        :type events: list
        :return: the recorded fetch arguments
        :rtype: list
        """
        asked = []

        def fetch(*args):
            asked.append(args)
            return ("SELECT 1", iter(events))

        controller._fetch_event_subset = fetch
        return asked

    def _drawing(self, controller):
        controller.view.clear_plot = MagicMock()
        controller.view.set_event_query = MagicMock()
        controller.view.show_solutions = MagicMock()
        controller.view.show_peak_fits = MagicMock()

    def _plot(self, controller, filters=None, scope=None):
        return controller.update_individual_distribution(
            "ldr",
            {} if filters is None else filters,
            self.SCOPE if scope is None else scope,
            [60],
            False,
            10.0,
            20.0,
            5,
        )

    def test_the_fit_is_kept_and_its_frames_reach_the_view(self, controller) -> None:
        """
        Bin, fit, sample, draw - and the fit Commit Individual writes stays with the
        Model, after the Individual figures are reset.
        """
        self._drawing(controller)
        asked = self._fetch(controller, [_two_level_event(1)])

        assert self._plot(controller) is True

        assert asked == [("ldr", "", {"exp1": ["3"]}, "Full Dataset")]
        controller.view.clear_plot.assert_called_once_with("2d", "individual")
        shapes = [call.args for call in controller.view.show_solutions.call_args_list]
        # A family that sampled nothing is not drawn; this event samples oblate only.
        assert [(mode, label) for mode, _, label in shapes] == [
            ("individual", "Oblate Solutions")
        ]
        assert all(len(columns) == 2 for _, columns, _ in shapes)
        mode, peaks, label = controller.view.show_peak_fits.call_args.args
        assert (mode, label, len(peaks)) == (
            "individual",
            "Event Peak Fit Parameters",
            4,
        )
        assert controller.model.individual_fit["id"].tolist() == [1]

    def test_a_subset_with_nothing_fittable_is_reported_and_changes_nothing(
        self, controller, mocker
    ) -> None:
        """
        Every guard in the drawing half tests a frame built from these events, so
        without this the tab drew empty axes and said nothing at all. The figures and
        the previous fit stay as they were.
        """
        self._drawing(controller)
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        previous = pd.DataFrame({"id": [9]})
        controller.model.set_individual_fit(previous)
        flat = _event(2)
        flat["filtered_data"] = np.zeros_like(flat["filtered_data"])
        self._fetch(controller, [flat])

        assert self._plot(controller) is False

        controller.view.clear_plot.assert_not_called()
        controller.view.show_solutions.assert_not_called()
        assert controller.model.individual_fit is previous
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("nothing to plot" in m for m in messages)

    def test_a_failed_fit_is_reported(self, controller, mocker) -> None:
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

        fitted = controller._fit_individual_events(
            [_event(1)], "Sideways Histogram", None, False, 10.0, 20.0, 5
        )

        assert fitted is None
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to fit the event histograms" in m for m in messages)

    @pytest.mark.parametrize(
        ("filters", "scope", "message"),
        [
            (
                {},
                {"exp1": ["3"], "exp2": ["1"]},
                "Only a single experiment can be used for Filtered Histogram",
            ),
            (
                {"a": "x > 1", "b": "x > 2"},
                {"exp1": ["3"]},
                "Only a single subset can be used for protein analysis",
            ),
            (
                {},
                {"exp1": ["3", "4"]},
                "Only a single channel at a time can be used for protein analysis",
            ),
            (
                {},
                {"exp1": []},
                "Only a single channel at a time can be used for protein analysis",
            ),
        ],
        ids=["two experiments", "two subsets", "two channels", "no channel"],
    )
    def test_a_refused_selection_is_said_and_fetches_nothing(
        self, controller, mocker, filters, scope, message
    ) -> None:
        self._drawing(controller)
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        asked = self._fetch(controller, [_two_level_event(1)])

        assert self._plot(controller, filters=filters, scope=scope) is False

        assert asked == []
        controller.view.clear_plot.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert message in messages


def _two_peaks() -> pd.DataFrame:
    """
    A two-peaked averaged histogram, as the Model builds one.

    :return: bin centers and amplitudes
    :rtype: pd.DataFrame
    """
    current = np.linspace(0.0, 0.6, 200)
    amplitude = 100.0 * np.exp(
        -((current - 0.15) ** 2) / (2 * 0.03**2)
    ) + 60.0 * np.exp(-((current - 0.40) ** 2) / (2 * 0.04**2))
    return pd.DataFrame({"Normalized Current": current, "Amplitude": amplitude})


def _solutions(rows: int = 2) -> pd.DataFrame:
    """
    One family of sampled geometries.

    :param rows: how many samples
    :type rows: int
    :return: a frame with the four geometry columns
    :rtype: pd.DataFrame
    """
    return pd.DataFrame(
        {
            "V": [100.0 + i for i in range(rows)],
            "m": [2.0] * rows,
            "a": [4.0] * rows,
            "b": [2.0] * rows,
        }
    )


class TestUpdateEnsembleDistribution:
    """Fetch and average one subset, fit it, keep the fit, and have the View draw it all."""

    SCOPE = {"exp1": ["3"]}

    def _drawing(self, controller):
        controller.view.clear_plot = MagicMock()
        controller.view.set_event_query = MagicMock()
        controller.view.show_histogram = MagicMock()
        controller.view.show_solutions = MagicMock()

    def _fetch(self, controller, events):
        controller._fetch_event_subset = lambda *a: ("SELECT 1", iter(events))

    def _plot(self, controller, filters=None, scope=None):
        return controller.update_ensemble_distribution(
            "ldr",
            {} if filters is None else filters,
            self.SCOPE if scope is None else scope,
            [25],
            False,
            1.0,
            2.0,
            3,
        )

    def _said(self, controller, mocker):
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        return lambda: [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]

    def test_the_histogram_is_drawn_on_a_cleared_ensemble_figure(
        self, controller
    ) -> None:
        self._drawing(controller)
        self._fetch(controller, [_event(1), _event(2, rng_seed=1)])

        assert self._plot(controller) is True

        controller.view.clear_plot.assert_called_once_with("2d", "ensemble")
        controller.view.set_event_query.assert_called_once_with("SELECT 1")
        mode, plot_data, label = controller.view.show_histogram.call_args_list[0].args
        assert mode == "ensemble"
        assert list(plot_data.columns) == ["Normalized Current", "Amplitude"]
        assert len(plot_data) == 25
        assert label == "ldr | exp1 Ch 3: Full Dataset"

    def test_a_subset_with_no_usable_event_is_reported_and_changes_nothing(
        self, controller, mocker
    ) -> None:
        """The previous figure, the previous fit and the history all stay."""
        self._drawing(controller)
        said = self._said(controller, mocker)
        self._fetch(controller, [])

        assert self._plot(controller) is False

        controller.view.clear_plot.assert_not_called()
        controller.view.show_histogram.assert_not_called()
        assert any("No usable events" in m for m in said())

    def test_a_failed_fetch_draws_nothing(self, controller) -> None:
        self._drawing(controller)
        controller._fetch_event_subset = lambda *a: None

        assert self._plot(controller) is False

        controller.view.show_histogram.assert_not_called()

    def test_a_histogram_that_cannot_be_built_is_reported(
        self, controller, mocker
    ) -> None:
        self._drawing(controller)
        said = self._said(controller, mocker)
        self._fetch(controller, [_event(1)])
        controller.model.build_all_points_histogram = MagicMock(
            side_effect=ValueError("bad bins")
        )

        assert self._plot(controller) is False

        controller.view.show_histogram.assert_not_called()
        assert any("Unable to build the ensemble histogram" in m for m in said())

    def test_a_new_plot_whose_fit_fails_leaves_no_earlier_fit_to_report(
        self, controller
    ) -> None:
        """Report All describes the histogram on screen, not the one it replaced."""
        self._drawing(controller)
        self._fetch(controller, [_event(1), _event(2, rng_seed=1)])
        controller.model.set_ensemble_fit(
            EnsembleFit(np.ones(6), [25], False, _solutions(), _solutions())
        )
        controller.model.fit_histogram = MagicMock(return_value=(None, None))

        assert self._plot(controller) is True

        assert controller.model.ensemble_fit is None

    @pytest.mark.parametrize(
        ("filters", "scope", "message"),
        [
            (
                {},
                {"exp1": ["3"], "exp2": ["1"]},
                "Only a single experiment can be used for Filtered Histogram",
            ),
            (
                {"a": "x > 1", "b": "x > 2"},
                {"exp1": ["3"]},
                "Only a single subset can be used for Filtered Histogram",
            ),
            (
                {},
                {"exp1": ["3", "4"]},
                "Only a single channel at a time can be used for protein analysis",
            ),
        ],
        ids=["two experiments", "two subsets", "two channels"],
    )
    def test_a_refused_selection_is_said_and_draws_nothing(
        self, controller, mocker, filters, scope, message
    ) -> None:
        self._drawing(controller)
        said = self._said(controller, mocker)
        self._fetch(controller, [_event(1)])

        assert self._plot(controller, filters=filters, scope=scope) is False

        controller.view.clear_plot.assert_not_called()
        assert message in said()


class TestFitEnsemble:
    """The fit of an Ensemble histogram, its two bail-outs, and what Report All will read."""

    POPT = np.array([100.0, 0.15, 0.03, 60.0, 0.40, 0.04])

    def _drawing(self, controller, mocker):
        controller.view.show_histogram = MagicMock()
        controller.view.show_solutions = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        return lambda: [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]

    def test_a_fit_is_kept_with_its_binning_and_drawn_with_its_shapes(
        self, controller, mocker
    ) -> None:
        self._drawing(controller, mocker)
        curve = np.linspace(1.0, 2.0, 200)
        controller.model.fit_histogram = MagicMock(return_value=(self.POPT, curve))
        controller.model.sample_vm_solutions = MagicMock(
            return_value=(_solutions(), _solutions())
        )

        controller._fit_ensemble(_two_peaks(), [25], True, 10.0, 12.0, 2)

        fit = controller.model.ensemble_fit
        np.testing.assert_array_equal(fit.params, self.POPT)
        assert (fit.bins, fit.sizes) == ([25], True)
        mode, drawn, label = controller.view.show_histogram.call_args.args
        assert (mode, label) == ("ensemble", "Fit")
        np.testing.assert_array_equal(drawn["Amplitude"].values, curve)
        shapes = [call.args for call in controller.view.show_solutions.call_args_list]
        assert [(mode, label) for mode, _, label in shapes] == [
            ("ensemble", "Prolate Solutions"),
            ("ensemble", "Oblate Solutions"),
        ]

    def test_an_unfittable_histogram_is_reported_and_keeps_no_fit(
        self, controller, mocker
    ) -> None:
        said = self._drawing(controller, mocker)
        controller.model.fit_histogram = MagicMock(return_value=(None, None))

        controller._fit_ensemble(_two_peaks(), None, False, 10.0, 12.0, 2)

        controller.view.show_histogram.assert_not_called()
        assert controller.model.ensemble_fit is None
        assert any("Unable to fit a double gaussian" in m for m in said())

    def test_unphysical_geometry_is_reported_but_the_fit_is_still_drawn(
        self, controller, mocker
    ) -> None:
        """No sample satisfies the geometry; the fitted curve is still worth seeing."""
        said = self._drawing(controller, mocker)
        empty = pd.DataFrame(columns=["V", "m", "a", "b"])
        controller.model.fit_histogram = MagicMock(
            return_value=(self.POPT, np.ones(200))
        )
        controller.model.sample_vm_solutions = MagicMock(return_value=(empty, empty))

        controller._fit_ensemble(_two_peaks(), None, False, 10.0, 12.0, 2)

        assert any("unphysical geometry" in m for m in said())
        controller.view.show_histogram.assert_called_once()
        controller.view.show_solutions.assert_not_called()
        assert controller.model.ensemble_fit is not None


class TestReportEnsembleFit:
    """Report All hands the View the fit the Model keeps, or says there is none."""

    def test_the_fit_s_parts_reach_the_view(self, controller) -> None:
        controller.view.show_ensemble_report = MagicMock()
        prolate, oblate = _solutions(), _solutions(3)
        controller.model.set_ensemble_fit(
            EnsembleFit(np.ones(6), [25], False, prolate, oblate)
        )

        controller.report_ensemble_fit()

        params, bins, sizes, sent_prolate, sent_oblate = (
            controller.view.show_ensemble_report.call_args.args
        )
        assert (bins, sizes) == ([25], False)
        assert sent_prolate is prolate and sent_oblate is oblate

    def test_no_fit_reports_that_rather_than_an_empty_table(
        self, controller, mocker
    ) -> None:
        controller.view.show_ensemble_report = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

        controller.report_ensemble_fit()

        controller.view.show_ensemble_report.assert_not_called()
        (message, _), _ = controller.add_text_to_display.emit.call_args
        assert "No ensemble fit available" in message


class TestReset:
    """The recorded reset clears one mode's figures, and neither mode's fit."""

    def test_it_clears_its_mode_s_figures_and_keeps_both_fits(self, controller) -> None:
        controller.view.clear_plot = MagicMock()
        individual = pd.DataFrame({"id": [1]})
        ensemble = EnsembleFit(np.ones(6), None, False, _solutions(), _solutions())
        controller.model.set_individual_fit(individual)
        controller.model.set_ensemble_fit(ensemble)

        controller.reset("2d", "ensemble")

        controller.view.clear_plot.assert_called_once_with("2d", "ensemble")
        assert controller.model.individual_fit is individual
        assert controller.model.ensemble_fit is ensemble
