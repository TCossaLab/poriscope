"""
Unit-test suite for ProteinController.

Uses:
  - A session-scoped QApplication fixture
  - A per-test ProteinController() fixture (real view/model, as built by _init)
  - global_signal and view.add_text_to_display mocked/observed per-test where relevant

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
from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
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
    application). global_signal is replaced with a MagicMock so we can assert on
    emitted calls without a live event bus.
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
# alter_database_status
# ===========================================================================


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
        # Step 4d: the name and text arrive as arguments. They used to be read back
        # off the View, which is the private access this step removes.
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
# relay_event_query
# ===========================================================================


# ===========================================================================
# relay_event_data_generator / relay_event_plot_data_generator
# ===========================================================================


# ===========================================================================
# relay_units
# ===========================================================================


# ===========================================================================
# update_column_names
# ===========================================================================


# ===========================================================================
# request_experiment_structure
# ===========================================================================


# ===========================================================================
# set_experiment_id / set_channel_db_id
# ===========================================================================


# ===========================================================================
# on_raw_filter_validated
# ===========================================================================


# ``TestOnRawFilterValidated`` lived here and is gone with the method it called.
# ``MetaSubsetTabController.on_raw_filter_validated`` was a two-argument passthrough
# left behind by Step 4a, which replaced the bus round-trip it served with the
# ``raw_filter_validation_requested`` intent; nothing connected to it or called it
# afterwards. ``validate_raw_filter`` answers the View directly, and the View's half
# is covered in ``test_protein_view`` and ``test_duplicated_helpers``.


# ``TestRelayQueryResult`` lived here and is gone with the method: Step 4a's last
# conversion replaced the ``relay_query_result`` bus round-trip with the
# ``event_id_cache_requested`` intent, answered by
# ``MetaSubsetTabController.load_event_id_cache`` and parked by ``set_event_id_rows``.
# The promoted-method side is covered in ``test_duplicated_helpers``, and the
# Controller slot in ``test_subset_tab_controller``.


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
# Neither slot had a test of its own before Step 4's closeout, which is method
# rule 52 for the fourth time: their callers were covered, and that is exactly
# what made the gap invisible. They do real work now - bin, then fit, then hand
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


class TestFitDistributionEvents:
    """The same, plus the pore geometry the sampling half needs."""

    def test_the_three_frames_reach_the_view(self, controller) -> None:
        """
        Bin, fit, sample, draw - four Model calls behind one intent, and the View
        is handed only what it draws.
        """
        controller.view.set_distribution_fits = MagicMock()

        controller.fit_distribution_events(
            [_two_level_event(1)], "Filtered Histogram", [60], False, 10.0, 20.0, 5
        )

        df_prolate, df_oblate, fit_data = (
            controller.view.set_distribution_fits.call_args.args
        )
        assert list(df_prolate.columns) == ["V", "m", "a", "b"]
        assert list(df_oblate.columns) == ["V", "m", "a", "b"]
        assert fit_data["id"].tolist() == [1]

    def test_a_subset_with_nothing_fittable_is_reported_and_draws_nothing(
        self, controller, mocker
    ) -> None:
        """
        Every guard in the drawing half tests a frame built from these events, so
        without this the tab drew empty axes and said nothing at all.
        """
        controller.view.set_distribution_fits = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        flat = _event(2)
        flat["filtered_data"] = np.zeros_like(flat["filtered_data"])

        controller.fit_distribution_events(
            [flat], "Filtered Histogram", None, False, 10.0, 20.0, 5
        )

        controller.view.set_distribution_fits.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("nothing to plot" in m for m in messages)

    def test_a_failure_is_reported_and_draws_nothing(self, controller, mocker) -> None:
        controller.view.set_distribution_fits = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()

        controller.fit_distribution_events(
            [_event(1)], "Sideways Histogram", None, False, 10.0, 20.0, 5
        )

        controller.view.set_distribution_fits.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to fit the event histograms" in m for m in messages)


class TestBuildEnsembleHistogram:
    """Fetch one subset, average it, and hand the frame back to be drawn."""

    def _fetch(self, controller, generator):
        """
        Answer the fetch with a query and a generator, without a real loader.

        :param controller: the controller under test
        :type controller: ProteinController
        :param generator: the events to answer with
        :type generator: object
        :return: None
        :rtype: None
        """
        controller._fetch_event_subset = lambda *a: ("SELECT 1", generator)

    def test_the_frame_and_its_context_reach_the_view(self, controller) -> None:
        controller.view.set_ensemble_histogram = MagicMock()
        controller.view.set_event_query = MagicMock()
        self._fetch(controller, iter([_event(1), _event(2, rng_seed=1)]))

        controller.build_ensemble_histogram(
            "ldr",
            "",
            None,
            "Filtered Histogram",
            [25],
            False,
            "lbl",
            ("k",),
            1.0,
            2.0,
            3,
        )

        controller.view.set_event_query.assert_called_once_with("SELECT 1")
        args = controller.view.set_ensemble_histogram.call_args.args
        plot_data, plot_type, bins, sizes, label, key, d, L, N = args
        assert list(plot_data.columns) == ["Normalized Current", "Amplitude"]
        assert len(plot_data) == 25
        assert (plot_type, bins, sizes, label, key) == (
            "Filtered Histogram",
            [25],
            False,
            "lbl",
            ("k",),
        )
        assert (d, L, N) == (1.0, 2.0, 3)

    def test_a_subset_with_no_usable_event_is_reported_and_draws_nothing(
        self, controller, mocker
    ) -> None:
        """
        The query is not set either, so the previous figure and the previous
        applied-query echo both stay as they were.
        """
        controller.view.set_ensemble_histogram = MagicMock()
        controller.view.set_event_query = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        self._fetch(controller, iter([]))

        controller.build_ensemble_histogram(
            "ldr",
            "",
            None,
            "Filtered Histogram",
            None,
            False,
            "lbl",
            ("k",),
            1.0,
            2.0,
            3,
        )

        controller.view.set_ensemble_histogram.assert_not_called()
        controller.view.set_event_query.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("No usable events" in m for m in messages)

    def test_a_failed_fetch_draws_nothing(self, controller) -> None:
        controller.view.set_ensemble_histogram = MagicMock()
        controller._fetch_event_subset = lambda *a: None

        controller.build_ensemble_histogram(
            "ldr",
            "",
            None,
            "Filtered Histogram",
            None,
            False,
            "lbl",
            ("k",),
            1.0,
            2.0,
            3,
        )

        controller.view.set_ensemble_histogram.assert_not_called()

    def test_an_unusable_plot_type_is_reported(self, controller, mocker) -> None:
        controller.view.set_ensemble_histogram = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        self._fetch(controller, iter([_event(1)]))

        controller.build_ensemble_histogram(
            "ldr",
            "",
            None,
            "Sideways Histogram",
            None,
            False,
            "lbl",
            ("k",),
            1.0,
            2.0,
            3,
        )

        controller.view.set_ensemble_histogram.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to build the ensemble histogram" in m for m in messages)


class TestFitEnsembleGeometry:
    """The ensemble fit's two bail-outs, which the widget used to own."""

    def _run(self, controller, popt_bins=None):
        """
        Drive the slot with a two-peaked histogram.

        :param controller: the controller under test
        :type controller: ProteinController
        :param popt_bins: unused, kept for symmetry with the other drivers
        :type popt_bins: object
        :return: the frame handed in, so a test can assert against it
        :rtype: pd.DataFrame
        """
        current = np.linspace(0.0, 0.6, 200)
        amplitude = 100.0 * np.exp(
            -((current - 0.15) ** 2) / (2 * 0.03**2)
        ) + 60.0 * np.exp(-((current - 0.40) ** 2) / (2 * 0.04**2))
        plot_data = pd.DataFrame(
            {"Normalized Current": current, "Amplitude": amplitude}
        )
        controller.fit_ensemble_geometry(
            current, amplitude, plot_data, "Histogram", 10.0, 10.0, 5
        )
        return plot_data

    def test_an_unfittable_histogram_is_reported_on_the_status_panel(
        self, controller, mocker
    ) -> None:
        """
        The first bail-out: no double Gaussian could be fitted. The user is told on
        the status panel rather than left with an unchanged plot and no
        explanation.
        """
        controller.view.set_ensemble_geometry_fit = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        flat = np.linspace(0.0, 1.0, 50)

        controller.fit_ensemble_geometry(
            flat, np.ones_like(flat), pd.DataFrame(), "Histogram", 10.0, 10.0, 5
        )

        controller.view.set_ensemble_geometry_fit.assert_not_called()
        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("Unable to fit a double gaussian" in m for m in messages)

    def test_unphysical_geometry_is_reported_but_the_fit_is_still_drawn(
        self, controller, mocker
    ) -> None:
        """
        The second bail-out: the fit was fine but no sample satisfies the geometry.
        The fitted curve is still worth seeing, so the setter is called with two
        empty frames rather than skipped.
        """
        controller.view.set_ensemble_geometry_fit = MagicMock()
        controller.add_text_to_display = mocker.Mock()
        controller.add_text_to_display.emit = mocker.Mock()
        empty = pd.DataFrame(columns=["V", "m", "a", "b"])
        controller.model.sample_vm_solutions = lambda *a: (empty, empty)

        self._run(controller)

        messages = [
            call.args[0] for call in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("unphysical geometry" in m for m in messages)
        controller.view.set_ensemble_geometry_fit.assert_called_once()
        assert controller.view.set_ensemble_geometry_fit.call_args.args[4].empty
