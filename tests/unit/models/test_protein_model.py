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
import pytest

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.utils.MetaModel import MetaModel

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
