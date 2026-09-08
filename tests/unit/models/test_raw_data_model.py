"""
Characterization tests for RawDataModel's baseline and Gaussian-fit computation.

Step 4c moved ``get_baseline_stats`` and ``gaussian_fit`` off ``RawDataView`` onto this
model - they were ``_get_baseline_stats`` and ``_gaussian_fit``, and the leading
underscore went because ``RawDataController`` calls them now. These tests came from
``tests/unit/views/test_raw_data_view_characterization.py`` with their assertions
unchanged; only the receiver moved, from ``view`` to ``model``.

They are the Step 2 characterization suite for the method whose own source comment calls
it "THE CRITICAL MATH FIX" and which the Step 2 audit found had **no** behavioural
coverage at all. That is why they were written before the move and why they are worth
following it carefully.

A fifth class, ``TestGaussian``, did not come across. ``RawDataView._gaussian`` was a
Gaussian model function with **zero callers anywhere in poriscope/** - ``gaussian_fit``
fits a parabola to ``log(histogram)`` rather than calling a model function - so Step 4c
deleted it instead of moving it, and its four tests went with it.
``ClassicBlockageFinder`` keeps its own separate copy, which is unaffected.

No Qt: these used to need a ``RawDataView`` built by ``__new__`` with its signals
shadowed, which is what moving the computation to a plain ``QObject`` model removes.
"""

from typing import Dict

import numpy as np
import numpy.typing as npt
import pytest

from poriscope.plugins.analysistabs.RawDataModel import RawDataModel

pytestmark = pytest.mark.characterization


@pytest.fixture
def model() -> RawDataModel:
    """
    A RawDataModel.

    :return: the model under test
    :rtype: RawDataModel
    """
    return RawDataModel()


def gaussian_curve(
    amplitude: float, mean: float, sigma: float, points: int = 201, span: float = 4.0
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Build a clean Gaussian sampled over +/- ``span`` standard deviations.

    :param amplitude: peak height
    :type amplitude: float
    :param mean: centre of the distribution
    :type mean: float
    :param sigma: standard deviation
    :type sigma: float
    :param points: number of samples
    :type points: int
    :param span: half-width of the sampled window, in standard deviations
    :type span: float
    :return: the bin centres and the curve values
    :rtype: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
    """
    centres = np.linspace(mean - span * sigma, mean + span * sigma, points)
    values = amplitude * np.exp(-((centres - mean) ** 2) / (2 * sigma**2))
    return centres, values


# ===========================================================================
# _gaussian_fit - the linearized least-squares fit
# ===========================================================================


class TestGaussianFitGuards:
    """The two documented raise paths."""

    def test_a_non_positive_stdev_guess_raises(self, model: RawDataModel) -> None:
        """Zero would divide by zero during standardisation."""
        centres, values = gaussian_curve(10.0, 0.0, 1.0)
        with pytest.raises(ValueError, match="Invalid standard deviation guess"):
            model.gaussian_fit(values, centres, 0.0, 0.0)

    def test_a_negative_stdev_guess_raises(self, model: RawDataModel) -> None:
        """Same guard, other side of zero."""
        centres, values = gaussian_curve(10.0, 0.0, 1.0)
        with pytest.raises(ValueError, match="Invalid standard deviation guess"):
            model.gaussian_fit(values, centres, 0.0, -1.0)

    def test_an_inverted_fit_raises(self, model: RawDataModel) -> None:
        """
        A quadratic coefficient at or above zero has no real standard deviation.

        An upward-curving profile, rather than a peak, produces exactly that.
        """
        centres = np.linspace(-1.0, 1.0, 51)
        values = 1.0 + centres**2
        with pytest.raises(ValueError, match="inverted fit"):
            model.gaussian_fit(values, centres, 0.0, 1.0)


class TestGaussianFitRecovery:
    """The fit recovers the parameters it was given, including the rescaling."""

    def test_it_recovers_a_known_gaussian(self, model: RawDataModel) -> None:
        """With guesses on the nose, all three parameters come back."""
        centres, values = gaussian_curve(100.0, 50.0, 5.0)

        amplitude, mean, stdev = model.gaussian_fit(values, centres, 50.0, 5.0)

        assert amplitude == pytest.approx(100.0, rel=1e-6)
        assert mean == pytest.approx(50.0, abs=1e-6)
        assert stdev == pytest.approx(5.0, rel=1e-6)

    def test_it_recovers_from_deliberately_wrong_guesses(
        self, model: RawDataModel
    ) -> None:
        """
        **This is the test that pins "THE CRITICAL MATH FIX".**

        The fit standardises by ``(x - mean_guess) / stdev_guess`` and must undo
        that afterwards. With guesses on the nose the multiplier is 1 and a missing
        de-standardisation would be invisible; here the guesses are deliberately
        off, so dropping either ``stdev *= stdev_guess`` or the ``* stdev_guess``
        in the mean would move the answer by hundreds of units.
        """
        centres, values = gaussian_curve(100.0, 5000.0, 250.0)

        amplitude, mean, stdev = model.gaussian_fit(values, centres, 4900.0, 300.0)

        assert amplitude == pytest.approx(100.0, rel=1e-5)
        assert mean == pytest.approx(5000.0, rel=1e-6)
        assert stdev == pytest.approx(250.0, rel=1e-5)

    def test_the_standard_deviation_is_returned_positive(
        self, model: RawDataModel
    ) -> None:
        """``np.absolute`` on the way out, so a negative root cannot escape."""
        centres, values = gaussian_curve(20.0, -30.0, 4.0)

        _, _, stdev = model.gaussian_fit(values, centres, -30.0, 4.0)

        assert stdev > 0

    def test_a_negative_mean_is_handled(self, model: RawDataModel) -> None:
        """Baselines are routinely negative, so the sign must survive the round trip."""
        centres, values = gaussian_curve(50.0, -2000.0, 100.0)

        _, mean, _ = model.gaussian_fit(values, centres, -1950.0, 120.0)

        assert mean == pytest.approx(-2000.0, rel=1e-6)


class TestGaussianFitGolden:
    """A parameter sweep, pinned as a numeric golden."""

    def test_sweep_is_unchanged(self, model: RawDataModel, num_regression) -> None:
        """
        Fit a family of clean Gaussians and record every recovered parameter.

        This is the regression net for Step 4c: the method moves to the Model, and
        if the standardisation, the moment matrix or the de-standardisation
        changes, the recovered numbers move and this diffs.

        It is deliberately *not* the net for the windowing threshold. Verified by
        perturbing it: changing ``exp(-4.5)`` to ``exp(-3.5)`` leaves every number
        here identical, because the linearized fit is exact for a true Gaussian on
        any symmetric sub-window. ``test_contaminated_sweep_is_unchanged`` below
        covers that.
        """
        cases = [
            (1.0, 0.0, 1.0),
            (10.0, 0.0, 1.0),
            (100.0, 50.0, 5.0),
            (100.0, 50.0, 0.5),
            (2000.0, 2000.0, 15.0),
            (50.0, -30.0, 4.0),
            (50.0, -2000.0, 100.0),
            (0.5, 1.0, 0.25),
            (100.0, 5000.0, 250.0),
            (75.0, 0.001, 0.0005),
            (1e5, 1e4, 1e3),
            (3.0, -0.5, 2.0),
        ]

        recorded: Dict[str, list] = {"amplitude": [], "mean": [], "stdev": []}
        for amplitude, mean, sigma in cases:
            centres, values = gaussian_curve(amplitude, mean, sigma)
            # Guesses are deliberately offset so the de-standardisation is exercised.
            fit_amp, fit_mean, fit_stdev = model.gaussian_fit(
                values, centres, mean + 0.2 * sigma, sigma * 1.2
            )
            recorded["amplitude"].append(fit_amp)
            recorded["mean"].append(fit_mean)
            recorded["stdev"].append(fit_stdev)

        num_regression.check({k: np.asarray(v) for k, v in recorded.items()})

    def test_contaminated_sweep_is_unchanged(
        self, model: RawDataModel, num_regression
    ) -> None:
        """
        The same fit over profiles that are *not* clean Gaussians.

        This is what pins the contiguous threshold mask. A real baseline histogram
        is a peak sitting on a pedestal with an event tail down one side, and there
        the choice of window changes the answer - so ``exp(-4.5)`` and the
        walk-outward-until-below-threshold logic are load-bearing. Against clean
        curves they are invisible, which is why this case exists separately.

        The profiles are a peak on a constant pedestal, a peak with a blockage
        shoulder on the low side, and a peak whose two halves have different
        widths.
        """
        recorded: Dict[str, list] = {"amplitude": [], "mean": [], "stdev": []}

        centres, values = gaussian_curve(100.0, 500.0, 20.0)
        pedestal = values + 3.0
        shoulder = values + 25.0 * np.exp(-((centres - 455.0) ** 2) / (2 * 12.0**2))
        asymmetric = np.where(
            centres < 500.0,
            100.0 * np.exp(-((centres - 500.0) ** 2) / (2 * 28.0**2)),
            100.0 * np.exp(-((centres - 500.0) ** 2) / (2 * 14.0**2)),
        )

        for profile in (pedestal, shoulder, asymmetric):
            amplitude, mean, stdev = model.gaussian_fit(profile, centres, 500.0, 20.0)
            recorded["amplitude"].append(amplitude)
            recorded["mean"].append(mean)
            recorded["stdev"].append(stdev)

        num_regression.check({k: np.asarray(v) for k, v in recorded.items()})


# ===========================================================================
# _get_baseline_stats - histogram, windowing, then the fit above
# ===========================================================================


class TestGetBaselineStats:
    """The chunk statistics that drive the raw-data trace display."""

    def test_flat_data_raises(self, model: RawDataModel) -> None:
        """
        No variation means no histogram width, which is a documented raise.

        The message matters: it is what the user sees when a chunk is constant.
        """
        with pytest.raises(ValueError, match="no variation in the data"):
            model.get_baseline_stats(np.full(1000, 5.0))

    def test_it_recovers_the_mean_and_width_of_noisy_data(
        self, model: RawDataModel
    ) -> None:
        """
        A normal sample's baseline is recovered to within a few percent.

        Deliberately a loose tolerance: the point is that the windowing plus fit
        lands on the right answer, not that it is exact. The exact numbers are
        pinned by the golden below.
        """
        rng = np.random.default_rng(20260905)
        data = rng.normal(2000.0, 15.0, 200_000)

        amplitude, mean, stdev = model.get_baseline_stats(data)

        assert mean == pytest.approx(2000.0, abs=1.0)
        assert stdev == pytest.approx(15.0, rel=0.15)
        assert amplitude > 0

    def test_it_returns_three_values_in_amplitude_mean_stdev_order(
        self, model: RawDataModel
    ) -> None:
        """The docstring fixes the order, and callers index it positionally."""
        rng = np.random.default_rng(7)
        out = model.get_baseline_stats(rng.normal(100.0, 2.0, 50_000))

        assert isinstance(out, np.ndarray)
        assert out.shape == (3,)

    def test_a_negative_baseline_is_handled(self, model: RawDataModel) -> None:
        """Nanopore baselines are commonly negative."""
        rng = np.random.default_rng(11)
        _, mean, stdev = model.get_baseline_stats(rng.normal(-1500.0, 20.0, 100_000))

        assert mean == pytest.approx(-1500.0, abs=2.0)
        assert stdev > 0

    def test_baseline_sweep_is_unchanged(
        self, model: RawDataModel, num_regression
    ) -> None:
        """
        Seeded noise through the full histogram-window-fit chain, pinned.

        Verified sensitive to the bin width (``len(data) ** (1/3)``) and to the
        first windowing bracket (``maxval / 5``), which is the one that actually
        *slices* the data handed to the fit.

        It is **not** sensitive to the second bracket (``0.6 * maxval``), and that
        is a finding rather than a gap: those indices are used only to build the
        ``mean_guess`` and ``stdev_guess``, and the fit undoes its own
        standardisation exactly, so the guesses barely reach the answer.
        Perturbing that constant to ``0.55`` moves nothing here. Worth knowing
        before Step 4c moves this code - half of the second pass is close to dead
        weight.
        """
        recorded: Dict[str, list] = {"amplitude": [], "mean": [], "stdev": []}
        for seed, (centre, width, size) in enumerate(
            [
                (2000.0, 15.0, 200_000),
                (2000.0, 5.0, 200_000),
                (-1500.0, 20.0, 100_000),
                (0.0, 1.0, 50_000),
                (100.0, 2.0, 50_000),
            ]
        ):
            rng = np.random.default_rng(1000 + seed)
            data = rng.normal(centre, width, size)
            amplitude, mean, stdev = model.get_baseline_stats(data)
            recorded["amplitude"].append(amplitude)
            recorded["mean"].append(mean)
            recorded["stdev"].append(stdev)

        num_regression.check({k: np.asarray(v) for k, v in recorded.items()})
