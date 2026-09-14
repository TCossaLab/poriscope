"""
Unit-test suite for ProteinModel.

ProteinModel was a minimal MetaModel subclass with a no-op _init(). **Step 4c
gave it the protein tab's double-gaussian fitting**, moved off ProteinView so
that scipy.optimize, scipy.signal and scipy.stats leave the View layer.

The construction tests below predate that and still hold. The fitting tests
were written from measured behaviour rather than from the implementation: the
parameter order that comes back is not the order the peaks appear in, so they
assert on sorted means (see TestFitDoubleGaussian).

Run with:
    pytest test_protein_model.py -v
    pytest test_protein_model.py --cov=poriscope --cov-report=html
"""

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.utils.MetaModel import MetaModel


def _make_double_gaussian_histogram(
    mean1=0.2, std1=0.02, amp1=1.0, mean2=0.6, std2=0.03, amp2=0.8, n_bins=200
):
    """
    Build a clean two-peak histogram.

    Moved verbatim from ``tests/unit/views/test_protein_view.py`` with the methods it
    exercises, so the pins below are the same inputs they were before Step 4c.

    :return: the bin centers and the amplitudes
    :rtype: tuple
    """
    x = np.linspace(0.0, 1.0, n_bins)
    g1 = amp1 * np.exp(-((x - mean1) ** 2) / (2 * std1**2))
    g2 = amp2 * np.exp(-((x - mean2) ** 2) / (2 * std2**2))
    return x, g1 + g2


# ===========================================================================
# Construction / inheritance
# ===========================================================================


class TestConstruction:
    def test_instantiates_without_error(self):
        model = ProteinModel()
        assert model is not None

    def test_is_instance_of_meta_model(self):
        model = ProteinModel()
        assert isinstance(model, MetaModel)

    def test_is_instance_of_protein_model(self):
        model = ProteinModel()
        assert isinstance(model, ProteinModel)


# ===========================================================================
# _init — should be a genuine no-op
# ===========================================================================


class TestInit:
    def test_init_does_not_raise(self):
        # Constructing the model already calls _init() internally via
        # MetaModel.__init__; this just makes the intent explicit.
        model = ProteinModel()
        model._init()  # calling again directly should also be safe/idempotent

    def test_init_does_not_set_any_new_instance_attributes(self):
        model = ProteinModel()
        before = set(vars(model).keys())
        model._init()
        after = set(vars(model).keys())
        assert before == after

    def test_init_returns_none(self):
        model = ProteinModel()
        assert model._init() is None

    def test_has_logger_attribute(self):
        # logger is a class-level attribute set via logging.getLogger(__name__)
        assert ProteinModel.logger is not None

    def test_logger_name_matches_module(self):
        assert ProteinModel.logger.name == "poriscope.plugins.analysistabs.ProteinModel"


# ===========================================================================
# Double-gaussian fitting - moved off ProteinView by Step 4c
# ===========================================================================


@pytest.fixture
def model():
    """
    A ProteinModel to fit with.

    :return: a constructed ProteinModel
    :rtype: ProteinModel
    """
    return ProteinModel()


@pytest.fixture
def bins():
    """
    Bin centers shared by every fitting test.

    :return: 200 evenly spaced points spanning both peaks
    :rtype: np.ndarray
    """
    return np.linspace(0, 10, 200)


class TestDoubleGaussian:
    """The model function curve_fit is handed."""

    def test_is_the_sum_of_two_gaussians(self, model, bins):
        """Each component peaks at its own mean, and the total is their sum."""
        both = model._double_gaussian(bins, 1.0, 3.0, 0.5, 2.0, 7.0, 0.5)
        first = model._double_gaussian(bins, 1.0, 3.0, 0.5, 0.0, 7.0, 0.5)
        second = model._double_gaussian(bins, 0.0, 3.0, 0.5, 2.0, 7.0, 0.5)

        np.testing.assert_allclose(both, first + second)

    def test_amplitude_is_reached_at_the_mean(self, model):
        """A single component evaluates to its amplitude at its own mean."""
        at_mean = model._double_gaussian(np.array([3.0]), 1.5, 3.0, 0.5, 0.0, 7.0, 0.5)

        np.testing.assert_allclose(at_mean, [1.5])

    # --- pins moved from test_protein_view.py by Step 4c, receiver re-pointed ---

    def test_peak_at_mean1(self, model):
        r = model._double_gaussian(np.array([0.2]), 1.0, 0.2, 0.05, 0.8, 0.6, 0.05)
        assert r[0] == pytest.approx(1.0, rel=1e-6)

    def test_peak_at_mean2(self, model):
        r = model._double_gaussian(np.array([0.6]), 1.0, 0.2, 0.05, 0.8, 0.6, 0.05)
        assert r[0] == pytest.approx(0.8, rel=1e-6)

    def test_zero_amplitudes(self, model):
        x = np.linspace(0, 1, 50)
        np.testing.assert_array_equal(
            model._double_gaussian(x, 0, 0.3, 0.05, 0, 0.7, 0.05), 0
        )

    def test_output_shape(self, model):
        x = np.linspace(0, 1, 100)
        assert model._double_gaussian(x, 1, 0.3, 0.1, 1, 0.7, 0.1).shape == (100,)

    def test_tails_near_zero(self, model):
        x = np.array([-10.0, 10.0])
        assert np.all(model._double_gaussian(x, 1, 0.3, 0.05, 1, 0.7, 0.05) < 1e-10)

    def test_symmetry(self, model):
        x = np.linspace(0, 1, 50)
        r1 = model._double_gaussian(x, 1.0, 0.3, 0.05, 0.5, 0.7, 0.05)
        r2 = model._double_gaussian(x, 0.5, 0.7, 0.05, 1.0, 0.3, 0.05)
        np.testing.assert_allclose(r1, r2, rtol=1e-12)

    def test_non_negative(self, model):
        x = np.linspace(-1, 2, 200)
        assert np.all(model._double_gaussian(x, 2, 0.3, 0.1, 1.5, 0.8, 0.15) >= 0)


class TestFitDoubleGaussian:
    """The raw fit, before any sanity checking."""

    def test_recovers_two_well_separated_peaks(self, model, bins):
        """
        The parameters come back in an order curve_fit chooses, not the order the
        peaks appear in - measured, and the reason this asserts on sorted means.
        """
        data = model._double_gaussian(bins, 1.0, 3.0, 0.5, 1.0, 7.0, 0.5)

        popt, pcov = model._fit_double_gaussian(bins, data)

        assert popt is not None and pcov is not None
        np.testing.assert_allclose(sorted([popt[1], popt[4]]), [3.0, 7.0], atol=1e-3)

    def test_unfittable_data_returns_a_pair_of_nones(self, model, bins):
        """
        Both fallback branches exhaust on a flat histogram. The return stays a
        two-tuple, because the caller unpacks it before testing either half.
        """
        popt, pcov = model._fit_double_gaussian(bins, np.zeros_like(bins))

        assert popt is None
        assert pcov is None

    # --- pins moved from test_protein_view.py by Step 4c, receiver re-pointed ---
    # The ``qt_app`` fixture and its ``processEvents()`` calls went with the move:
    # a Model builds no widget, so there is no event loop to pump.

    def test_clean_two_peak_signal(self, model):
        x, y = _make_double_gaussian_histogram()
        popt, pcov = model._fit_double_gaussian(x, y)
        assert popt is not None and len(popt) == 6

    def test_single_peak_fallback_degenerate_bug(self, model):
        # BUG: fallback produces a degenerate two-component fit at the same position
        x = np.linspace(0, 1, 200)
        y = np.exp(-((x - 0.5) ** 2) / (2 * 0.05**2))
        popt, _ = model._fit_double_gaussian(x, y)
        assert popt is not None and len(popt) == 6
        assert abs(popt[1] - popt[4]) < 0.05

    def test_flat_returns_none(self, model):
        x = np.linspace(0, 1, 100)
        popt, _ = model._fit_double_gaussian(x, np.zeros_like(x))
        assert popt is None


class TestFitAndSanityCheckDoubleGaussian:
    """The checks that decide whether a successful fit is believable."""

    def test_a_clean_bimodal_histogram_is_accepted(self, model, bins):
        """The good case survives every check and returns six parameters."""
        data = model._double_gaussian(bins, 1.0, 3.0, 0.5, 1.0, 7.0, 0.5)

        popt = model._fit_and_sanity_check_double_gaussian(bins, data)

        assert popt is not None
        assert len(popt) == 6

    def test_a_failed_fit_is_rejected(self, model, bins):
        """Nothing to sanity check when the fit itself did not converge."""
        assert (
            model._fit_and_sanity_check_double_gaussian(bins, np.zeros_like(bins))
            is None
        )

    def test_a_fit_with_large_parameter_errors_is_rejected(self, model, bins):
        """
        The raw fit succeeds on this input and the sanity check refuses it, which is
        what distinguishes this test from the failed-fit case above.

        **The guard that fires is the parameter-error check**, ``perr > |popt| * 10``
        - established by deleting each guard in turn, not by reading the code. A
        second population at 2% never clears ``find_peaks``' 5%-of-maximum prominence
        threshold, so the fit lands both components on the dominant peak and returns
        a degenerate one with a standard deviation of zero; it is that degeneracy the
        error check catches. The amplitude-ratio guard below it is *reached* and does
        not fire, because the fitted amplitudes are then near-equal whatever the input
        ratio was.
        """
        data = model._double_gaussian(bins, 1.0, 3.0, 0.5, 0.02, 7.0, 0.5)

        raw, _ = model._fit_double_gaussian(bins, data)
        checked = model._fit_and_sanity_check_double_gaussian(bins, data)

        assert raw is not None
        assert checked is None

    # --- pins moved from test_protein_view.py by Step 4c, receiver re-pointed ---

    def test_clean_signal_passes(self, model):
        x, y = _make_double_gaussian_histogram()
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None and len(popt) == 6

    def test_recovered_means(self, model):
        x, y = _make_double_gaussian_histogram(mean1=0.2, mean2=0.6)
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        means = sorted([popt[1], popt[4]])
        assert means[0] == pytest.approx(0.2, abs=0.01)
        assert means[1] == pytest.approx(0.6, abs=0.01)

    def test_flat_input_returns_none(self, model):
        x = np.linspace(0, 1, 100)
        assert model._fit_and_sanity_check_double_gaussian(x, np.zeros_like(x)) is None

    def test_single_peak_behaviour_documented(self, model):
        # Documents that single-peak input may pass or fail the sanity check
        x = np.linspace(0, 1, 200)
        y = np.exp(-((x - 0.5) ** 2) / (2 * 0.05**2))
        result = model._fit_and_sanity_check_double_gaussian(x, y)
        assert result is None or (
            len(result) == 6 and abs(result[1] - result[4]) < 0.05
        )

    def test_dominated_peak_behaviour_documented(self, model):
        # BUG: dominated-peak guard is unreliable when fallback co-locates both
        # components. This is the same observation as the amplitude-ratio guard
        # never firing in TestFitAndSanityCheckDoubleGaussian above - the repo had
        # already recorded it here, which is why it is not filed as a new finding.
        x = np.linspace(0, 1, 300)
        y = model._double_gaussian(x, 1.0, 0.2, 0.02, 0.001, 0.7, 0.02)
        result = model._fit_and_sanity_check_double_gaussian(x, y)
        assert result is None or len(result) == 6

    def test_roundtrip_residuals(self, model):
        x, y = _make_double_gaussian_histogram()
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        assert np.max(np.abs(y - model._double_gaussian(x, *popt))) < 0.02

    def test_double_gaussian_roundtrip(self, model):
        x, y = _make_double_gaussian_histogram()
        popt = model._fit_and_sanity_check_double_gaussian(x, y)
        assert popt is not None
        y_fit = model._double_gaussian(x, *popt)
        assert np.max(np.abs(y - y_fit)) < 0.02


class TestFitHistogram:
    """The public single-histogram entry point, which also evaluates the curve."""

    def test_returns_the_curve_evaluated_at_the_same_bins(self, model, bins):
        """
        Returning the curve is what keeps ``_double_gaussian`` out of the View, so
        the curve must be exactly what the View used to compute for itself.
        """
        data = model._double_gaussian(bins, 1.0, 3.0, 0.5, 1.0, 7.0, 0.5)

        popt, curve = model.fit_histogram(bins, data)

        assert popt is not None and curve is not None
        np.testing.assert_allclose(curve, model._double_gaussian(bins, *popt))
        assert curve.shape == bins.shape

    def test_a_rejected_fit_yields_a_pair_of_nones(self, model, bins):
        """The failure shape matches the success shape, so callers unpack either."""
        popt, curve = model.fit_histogram(bins, np.zeros_like(bins))

        assert popt is None
        assert curve is None


class TestFitHistograms:
    """The batch entry point the per-event plotting loops use."""

    def test_results_stay_index_aligned_with_the_input(self, model, bins):
        """
        A histogram that cannot be fitted yields ``(None, None)`` in its own slot
        rather than being dropped, so the caller can skip exactly that event.
        """
        good = model._double_gaussian(bins, 1.0, 3.0, 0.5, 1.0, 7.0, 0.5)
        bad = np.zeros_like(bins)

        results = model.fit_histograms([(bins, good), (bins, bad), (bins, good)])

        assert len(results) == 3
        assert [popt is None for popt, _ in results] == [False, True, False]

    def test_no_histograms_gives_no_results(self, model):
        """The empty case is a plain empty list, not None."""
        assert model.fit_histograms([]) == []


# ===========================================================================
# The SQL Step 4b moved down - drop_fit_columns, resolve_event_ids,
# load_events_by_id
# ===========================================================================
#
# All three are destinations of a Step 4b move and none had a test naming it, so
# the refactor-coverage audit read RUNS ONLY for all three: their bodies ran under
# the e2e suite and nothing asserted what they authored. These assert on the exact
# statements handed to the loader, and the stubbed ``call`` answers from the
# declared return types on ``MetaDatabaseLoader`` - bool for alter_database,
# Optional[pd.DataFrame] for query_database_directly, a generator for
# load_event_data.


class TestDropFitColumns:
    """
    Two statements per column: one drops it from the events table, one removes its
    row from the ``columns`` metadata table, which is what tells the rest of the
    application the column exists. Dropping only the first leaves the column
    advertised and gone.
    """

    def test_both_statements_are_issued_for_one_column(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=True)

        model.drop_fit_columns("L", "events", ["fit_a"])

        assert call.call_args.args[3] == [
            "ALTER TABLE events DROP COLUMN fit_a",
            "DELETE FROM columns WHERE name = 'fit_a'",
        ]

    def test_all_alters_precede_all_deletes(self, model, mocker):
        """
        The order is a property of how the list is built - every ALTER, then every
        DELETE - rather than column by column. Pinned because an interleaved rewrite
        would look equivalent and is not: a failure partway through would leave a
        different half-state.
        """
        call = mocker.patch.object(model, "call", return_value=True)

        model.drop_fit_columns("L", "events", ["a", "b"])

        assert call.call_args.args[3] == [
            "ALTER TABLE events DROP COLUMN a",
            "ALTER TABLE events DROP COLUMN b",
            "DELETE FROM columns WHERE name = 'a'",
            "DELETE FROM columns WHERE name = 'b'",
        ]

    def test_the_table_name_is_used_as_given(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=True)

        model.drop_fit_columns("L", "sublevels", ["x"])

        assert call.call_args.args[3][0] == "ALTER TABLE sublevels DROP COLUMN x"

    def test_the_call_is_routed_to_alter_database(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=True)

        model.drop_fit_columns("SQLiteDBLoader_0", "events", ["x"])

        assert call.call_args.args[:3] == (
            "MetaDatabaseLoader",
            "SQLiteDBLoader_0",
            "alter_database",
        )

    def test_no_columns_issues_no_statements(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=True)

        model.drop_fit_columns("L", "events", [])

        assert call.call_args.args[3] == []

    def test_the_loaders_verdict_is_returned(self, model, mocker):
        """
        A refused write must not read as a success - the caller announces new columns
        to the other tabs on the strength of this.
        """
        mocker.patch.object(model, "call", return_value=False)

        assert model.drop_fit_columns("L", "events", ["x"]) is False


def _authored_query(model, mocker, event_ids, exp_id, channel):
    """
    Run resolve_event_ids against a stubbed loader and return the SQL it authored.

    :param model: the model under test
    :type model: ProteinModel
    :param mocker: the pytest-mock fixture
    :type mocker: pytest_mock.MockerFixture
    :param event_ids: the event_id values to resolve
    :type event_ids: list
    :param exp_id: the experiment's database id, or None
    :type exp_id: object
    :param channel: the channel to scope to, or None
    :type channel: object
    :return: the query string passed to the loader
    :rtype: str
    """
    call = mocker.patch.object(model, "call", return_value=pd.DataFrame())
    model.resolve_event_ids("L", event_ids, exp_id, channel)
    query: str = call.call_args.args[3]
    return query


class TestResolveEventIds:
    """
    The protein copy projects ``id, event_id`` where the metadata copy projects
    ``id`` alone, because its caller re-sorts the rows into the order it asked for
    them in and cannot do that from the primary keys. That is one of the real
    differences the queued promotion review has to preserve, so it is pinned on both
    sides.
    """

    def test_projects_id_and_event_id(self, model, mocker):
        query = _authored_query(model, mocker, [7], None, None)

        assert query == "SELECT id, event_id FROM events WHERE event_id IN (7)"

    def test_an_experiment_narrows_the_scope(self, model, mocker):
        query = _authored_query(model, mocker, [7, 9], 3, None)

        assert query == (
            "SELECT id, event_id FROM events WHERE event_id IN (7,9) "
            "AND experiment_id = 3"
        )

    def test_a_channel_narrows_the_scope(self, model, mocker):
        query = _authored_query(model, mocker, [7], None, 2)

        assert query == (
            "SELECT id, event_id FROM events WHERE event_id IN (7) AND channel_id = 2"
        )

    def test_both_scopes_are_applied_in_order(self, model, mocker):
        query = _authored_query(model, mocker, [7], 3, 2)

        assert query == (
            "SELECT id, event_id FROM events WHERE event_id IN (7) "
            "AND experiment_id = 3 AND channel_id = 2"
        )

    def test_the_call_is_routed_to_the_named_loader(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=pd.DataFrame())

        model.resolve_event_ids("SQLiteDBLoader_0", [1], None, None)

        assert call.call_args.args[:3] == (
            "MetaDatabaseLoader",
            "SQLiteDBLoader_0",
            "query_database_directly",
        )

    def test_a_failed_query_comes_back_as_none(self, model, mocker):
        mocker.patch.object(model, "call", return_value=None)

        assert model.resolve_event_ids("L", [1], None, None) is None


class TestLoadEventsById:
    """``e.id IN (...)`` is a WHERE-clause body, which is what load_event_data takes."""

    def test_builds_a_where_clause_body_not_a_select(self, model, mocker):
        """
        A complete ``SELECT`` here is the shape that made the protein tab's raw
        filter branch never return a row - the loader splices this in after its own
        ``WHERE``.
        """
        call = mocker.patch.object(model, "call", return_value=iter(()))

        model.load_events_by_id("L", "3,4,5", None)

        conditions = call.call_args.args[3]
        assert conditions == "e.id IN (3,4,5)"
        assert "SELECT" not in conditions

    def test_the_scope_is_passed_through_untouched(self, model, mocker):
        call = mocker.patch.object(model, "call", return_value=iter(()))
        scope = {"exp_a": [2]}

        model.load_events_by_id("L", "3", scope)

        assert call.call_args.args[4] is scope

    def test_the_generator_is_returned_unchanged(self, model, mocker):
        generator = iter([{"data": [1.0]}])
        mocker.patch.object(model, "call", return_value=generator)

        assert model.load_events_by_id("L", "3", None) is generator


# ===========================================================================
# build_event_histograms - the per-event binning, moved off ProteinView
# ===========================================================================


def _make_event(
    event_id=1,
    n=2000,
    sr=1_000_000,
    padding_us=100,
    blockage=0.3,
    noise=0.01,
    rng_seed=0,
):
    """
    Synthetic event dict matching what ``load_event_data`` yields.

    Moved from ``tests/unit/views/test_protein_view.py`` with the binning it feeds,
    so the pins below are the same inputs they were before Step 4's closeout.

    :param event_id: the event's id
    :type event_id: int
    :param n: how many samples the event carries
    :type n: int
    :param sr: the sampling rate in Hz
    :type sr: int
    :param padding_us: the padding either side, in microseconds
    :type padding_us: int
    :param blockage: the fraction of the baseline the event blocks
    :type blockage: float
    :param noise: the noise amplitude as a fraction of the baseline
    :type noise: float
    :param rng_seed: the seed for the synthetic noise
    :type rng_seed: int
    :return: one event payload
    :rtype: dict
    """
    rng = np.random.default_rng(rng_seed)
    pb = int(padding_us * sr * 1e-6)
    pa = int(padding_us * sr * 1e-6)
    baseline = 1000.0
    event_current = baseline * (1.0 - blockage)
    ts = np.full(n, event_current) + rng.normal(0, noise * baseline, n)
    ts[:pb] = baseline + rng.normal(0, noise * baseline, pb)
    ts[-pa:] = baseline + rng.normal(0, noise * baseline, pa)
    return {
        "id": event_id,
        "event_id": event_id,
        "experiment_id": 1,
        "channel_id": 0,
        "raw_data": ts.copy(),
        "filtered_data": ts.copy(),
        "samplerate": sr,
        "padding_before": padding_us,
        "padding_after": padding_us,
    }


class TestBuildEventHistograms:
    """
    One histogram per event, each binned over its own range.

    These came from ``test_protein_view``'s ``TestConstructSingleEventHistogram``
    with the method, rewritten against the list-returning shape: the DataFrame the
    View used to build was unpacked into two arrays at every reader, so the Model
    hands back the arrays.
    """

    def test_one_pair_per_event(self, model):
        events = [_make_event(i, rng_seed=i) for i in range(3)]

        histograms = model.build_event_histograms(
            events, "Filtered Histogram", None, False
        )

        assert len(histograms) == 3
        for bincenters, amplitude in histograms:
            assert len(bincenters) == len(amplitude) > 0

    def test_default_uses_freedman_diaconis(self, model):
        """
        Default binning is data-dependent, so assert it is a sane positive count
        rather than a fixed one - the fixed hundred is the degenerate fallback.
        """
        ((bincenters, _),) = model.build_event_histograms(
            [_make_event()], "Filtered Histogram", None, False
        )

        assert len(bincenters) > 0

    def test_an_explicit_count_overrides_the_rule(self, model):
        ((bincenters, _),) = model.build_event_histograms(
            [_make_event()], "Filtered Histogram", [50], False
        )

        assert len(bincenters) == 50

    def test_a_bin_width_is_divided_into_the_event_range(self, model):
        ((bincenters, _),) = model.build_event_histograms(
            [_make_event()], "Filtered Histogram", [0.01], True
        )

        assert len(bincenters) > 0

    def test_an_event_with_no_samples_between_its_paddings_is_none(self, model):
        """A padding pair covering the whole event leaves nothing to bin."""
        event = _make_event()
        event["padding_before"] = 1000
        event["padding_after"] = 1000

        assert model.build_event_histograms(
            [event], "Filtered Histogram", None, False
        ) == [None]

    def test_a_zero_baseline_event_is_none_rather_than_a_row_of_nans(self, model):
        """
        Dividing by a zero baseline used to reach ``np.linspace`` as NaN limits,
        which numpy accepts: the event came back as a histogram of NaN bin centers
        and zero amplitudes, drawn as an empty subplot and exported as a column of
        NaNs. The all-points path already skipped such events explicitly; both do
        now.
        """
        event = _make_event()
        event["filtered_data"] = np.zeros_like(event["filtered_data"])

        assert model.build_event_histograms(
            [event], "Filtered Histogram", None, False
        ) == [None]

    def test_a_skipped_event_keeps_the_others_in_place(self, model):
        """
        The result is index-aligned with the events, because the drawing half lays
        out one subplot per event in the original order.
        """
        good, bad = _make_event(1), _make_event(2)
        bad["filtered_data"] = np.zeros_like(bad["filtered_data"])

        histograms = model.build_event_histograms(
            [good, bad, _make_event(3, rng_seed=3)],
            "Filtered Histogram",
            None,
            False,
        )

        assert histograms[1] is None
        assert histograms[0] is not None and histograms[2] is not None

    def test_each_event_is_binned_over_its_own_range(self, model):
        """
        Requested 2026-09-14, and the reason the two paths now share this method:
        the individual-distribution path let the limits accumulate across a plot's
        events, so the fifth event was binned over the union of the first five and
        the edges depended on the order they arrived in.
        """
        shallow = _make_event(1, blockage=0.1)
        deep = _make_event(2, blockage=0.8, rng_seed=1)

        forwards = model.build_event_histograms(
            [shallow, deep], "Filtered Histogram", None, False
        )
        backwards = model.build_event_histograms(
            [deep, shallow], "Filtered Histogram", None, False
        )

        assert forwards[0][0] == pytest.approx(backwards[1][0])
        assert forwards[1][0] == pytest.approx(backwards[0][0])

    def test_raw_and_filtered_both_bin(self, model):
        event = _make_event()

        assert (
            model.build_event_histograms([event], "Raw Histogram", None, False)[0]
            is not None
        )
        assert (
            model.build_event_histograms([event], "Filtered Histogram", None, False)[0]
            is not None
        )

    def test_an_unusable_bin_request_is_refused_once(self, model):
        """
        The request is the same for every event, so it is refused rather than
        absorbed per event - which used to log one line each and draw a grid of
        empty subplots.
        """
        with pytest.raises((ValueError, TypeError)):
            model.build_event_histograms(
                [_make_event(), _make_event(2)], "Filtered Histogram", "bad", False
            )

    def test_an_unknown_plot_type_is_refused(self, model):
        with pytest.raises(ValueError, match="Unknown plot_type"):
            model.build_event_histograms(
                [_make_event()], "Sideways Histogram", None, False
            )

    def test_no_events_gives_no_histograms(self, model):
        assert model.build_event_histograms([], "Filtered Histogram", None, False) == []
