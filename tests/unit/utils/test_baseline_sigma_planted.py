"""
Ground truth for the shared baseline fit: planted mean and sigma against what it reports.

Every sigma-denominated event-finder threshold comes from ``MetaEventFinder._fit_baseline_histogram``,
and the existing tests pin it on one chunk size at a 2% tolerance. These tests state what
the fit *should* recover from a planted Gaussian - mean within a tenth of a sigma, sigma
within 1% - at the three chunk sizes a finder actually sees, and from a two-population chunk
where a shallower occupied level sits beside the baseline. Where the fit cannot meet the
bound today the test is a strict expected failure naming the rule at fault; 2.1 step 4
replaces those rules (ruling D) and turns the failures green one by one.

Measured on 2026-10-05 at `64d8719c`, before step 4: sigma bias +2.0% (max 3.4%) at 10k
samples, +0.6% (max 1.1%) at 100k, +0.1% at 1M; the two-population mean right to 0.2 pA
up to 45% occupancy and the lower level reported at 55%; the two-population sigma +2.5%
at every occupancy. Rice's rule for the bins (step 4, first commit) took the 10k bias to
+0.03% and the two-population sigma to +0.15% at seed 0, so those two pins are plain
assertions now; the ``np.argmax(hist)`` peak rule is still behind the 55% flip.
"""

import numpy as np
import pytest

from tests.unit.utils.test_meta_event_finder import (
    FakeReader,
    build_finder,
    make_settings,
)

PLANTED_MEAN = 1000.0
PLANTED_SIGMA = 15.0
SIGMA_REL_BOUND = 0.01
MEAN_ABS_BOUND = 0.1 * PLANTED_SIGMA
SEED = 0

PEAK_RULE = pytest.mark.xfail(
    strict=True,
    reason=(
        "np.argmax(hist) at MetaEventFinder._fit_baseline_histogram:1005 follows the "
        "tallest bin, so past 50% occupancy the occupied level is reported as the "
        "baseline; ruling D, 2.1 step 4"
    ),
)


@pytest.fixture(scope="module")
def finder():
    """
    A concrete finder whose only job here is to expose the base class's histogram fit.

    :return: the finder double from the base-class tests
    :rtype: tests.unit.utils.test_meta_event_finder.ConcreteEventFinder
    """
    return build_finder(make_settings(FakeReader(np.zeros(16), samplerate=100.0)))


def planted(n: int, seed: int = SEED) -> np.ndarray:
    """
    Draw a planted Gaussian chunk.

    :param n: the chunk length in samples
    :type n: int
    :param seed: the generator seed
    :type seed: int
    :return: samples from N(PLANTED_MEAN, PLANTED_SIGMA)
    :rtype: numpy.ndarray
    """
    return np.random.default_rng(seed).normal(PLANTED_MEAN, PLANTED_SIGMA, n)


def fit(finder, data: np.ndarray):
    """
    Run the shared fit over the chunk's full range, as ClassicBlockageFinder does.

    :param finder: the finder exposing the base method
    :param data: the chunk
    :type data: numpy.ndarray
    :return: ``(mean, sigma)``
    :rtype: tuple
    """
    return finder._fit_baseline_histogram(data, float(data.min()), float(data.max()))


@pytest.mark.parametrize(
    "n",
    [
        pytest.param(10_000, id="10k"),
        pytest.param(100_000, id="100k"),
        pytest.param(1_000_000, id="1M"),
    ],
)
def test_the_fitted_sigma_is_within_one_percent_of_the_planted_sigma(
    finder, n: int
) -> None:
    """A one-second chunk at 10 kHz, 100 kHz and 1 MHz, which is what finders see."""
    _mean, sigma = fit(finder, planted(n))
    assert sigma == pytest.approx(PLANTED_SIGMA, rel=SIGMA_REL_BOUND), (
        f"n={n}: sigma {sigma:.3f} vs planted {PLANTED_SIGMA}, "
        f"bias {(sigma / PLANTED_SIGMA - 1) * 100:+.2f}%"
    )


@pytest.mark.parametrize("n", [10_000, 100_000, 1_000_000], ids=["10k", "100k", "1M"])
def test_the_fitted_mean_is_within_a_tenth_of_a_sigma(finder, n: int) -> None:
    """The mean is the easy half of the fit and must stay right at every size."""
    mean, _sigma = fit(finder, planted(n))
    assert abs(mean - PLANTED_MEAN) <= MEAN_ABS_BOUND, (n, mean)


def two_populations(occupancy: float, n: int = 100_000, seed: int = SEED) -> np.ndarray:
    """
    A baseline at 1000 pA beside an occupied level at 850 pA, both at the planted sigma.

    :param occupancy: the fraction of samples on the occupied level
    :type occupancy: float
    :param n: total samples
    :type n: int
    :param seed: the generator seed
    :type seed: int
    :return: the chunk
    :rtype: numpy.ndarray
    """
    rng = np.random.default_rng(seed)
    occupied = int(n * occupancy)
    return np.concatenate(
        [
            rng.normal(PLANTED_MEAN, PLANTED_SIGMA, n - occupied),
            rng.normal(PLANTED_MEAN - 150.0, PLANTED_SIGMA, occupied),
        ]
    )


@pytest.mark.parametrize(
    "occupancy",
    [
        pytest.param(0.10, id="10pct"),
        pytest.param(0.30, id="30pct"),
        pytest.param(0.45, id="45pct"),
        pytest.param(0.55, marks=PEAK_RULE, id="55pct"),
    ],
)
def test_the_baseline_is_the_planted_level_beside_an_occupied_one(
    finder, occupancy: float
) -> None:
    """
    The baseline is the fitted peak farthest from zero (Kyle, 2026-09-20), whatever the
    occupancy of the shallower level beside it.
    """
    mean, _sigma = fit(finder, two_populations(occupancy))
    assert abs(mean - PLANTED_MEAN) <= 1.0, (occupancy, mean)


def test_the_fitted_sigma_beside_an_occupied_level_is_within_one_percent(
    finder,
) -> None:
    """A second population below the baseline must not widen the baseline's sigma."""
    _mean, sigma = fit(finder, two_populations(0.30))
    assert sigma == pytest.approx(
        PLANTED_SIGMA, rel=SIGMA_REL_BOUND
    ), f"sigma {sigma:.3f}, bias {(sigma / PLANTED_SIGMA - 1) * 100:+.2f}%"
