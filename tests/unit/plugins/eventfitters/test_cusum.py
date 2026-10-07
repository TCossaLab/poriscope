"""
Unit tests for ``CUSUM``, the base of the CUSUM family of event fitters.

``ClassicCUSUM`` and ``IntraCUSUM`` inherit the detector from here, so the behaviour of
the shared pieces - how the local baseline sigma is recovered when the loader did not
report one, and how ``Step Size`` is expressed in units of that sigma - is pinned on the
base once rather than per subclass. The detector loop itself is exercised on clean steps
in ``test_classic_cusum.py`` and against planted, Bessel-filtered staircases in
``tests/unit/plugins/conformance/test_fitter_accuracy.py``.

Instances are built with ``object.__new__`` and a hand-made ``settings`` dict, as the
sibling modules do, so these tests see the algorithms and not the plugin lifecycle.
"""

import unittest
from unittest.mock import patch

import numpy as np

from poriscope.plugins.eventfitters.ClassicCUSUM import ClassicCUSUM
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from tests.synthetic_data.synthetic_events_db import build_bessel_filter


def _make(cls, step_size=5.0, rise_time_us=0.0, max_sublevels=0):
    """
    Return a fitter of ``cls`` with settings injected, bypassing ``__init__``.

    With ``samplerate=1e6`` in these tests a microsecond is a sample, so ``rise_time_us``
    maps 1:1 to samples.
    """
    pf = object.__new__(cls)
    pf.settings = {
        "Step Size": {"Value": step_size},
        "Rise Time": {"Value": rise_time_us},
        "Max Sublevels": {"Value": max_sublevels},
        "Sensitivity": {"Value": 1.0},
    }
    return pf


# ---------------------------------------------------------------------------
# Recovering the baseline sigma from the padding when the loader reports none
# ---------------------------------------------------------------------------


class TestResolveBaselineStd(unittest.TestCase):
    def setUp(self):
        rng = np.random.RandomState(0)
        # 100 samples of sigma-5 noise, a 100-sample level at 50, 100 more baseline samples
        self.noise = rng.normal(0.0, 5.0, 300)
        self.data = (
            np.concatenate([np.zeros(100), np.full(100, 50.0), np.zeros(100)])
            + self.noise
        )

    def test_a_reported_sigma_is_used_as_is(self):
        pf = _make(CUSUM)
        self.assertEqual(pf._resolve_baseline_std(self.data, 100, 100, 7.5), 7.5)

    def test_sigma_comes_from_the_padding_before_when_it_exists(self):
        pf = _make(CUSUM)
        self.assertAlmostEqual(
            pf._resolve_baseline_std(self.data, 100, None, None),
            float(np.std(self.data[:100])),
        )

    def test_sigma_comes_from_the_padding_after_when_only_it_exists(self):
        pf = _make(CUSUM)
        self.assertAlmostEqual(
            pf._resolve_baseline_std(self.data, None, 100, None),
            float(np.std(self.data[-100:])),
        )

    def test_a_zero_padding_before_is_treated_as_absent(self):
        # np.std(data[:0]) is nan; a zero padding holds no baseline samples, so the
        # trailing padding must be used instead.
        pf = _make(CUSUM)
        self.assertAlmostEqual(
            pf._resolve_baseline_std(self.data, 0, 100, None),
            float(np.std(self.data[-100:])),
        )

    def test_a_zero_padding_after_is_treated_as_absent(self):
        # data[-0:] is the whole event, not an empty padding.
        pf = _make(CUSUM)
        with self.assertRaisesRegex(ValueError, "standard deviation"):
            pf._resolve_baseline_std(self.data, None, 0, None)

    def test_no_padding_and_no_sigma_raises(self):
        pf = _make(CUSUM)
        with self.assertRaisesRegex(ValueError, "standard deviation"):
            pf._resolve_baseline_std(self.data, None, None, None)

    def test_the_detector_refuses_an_event_whose_only_padding_is_empty(self):
        # Through the detector: a zero padding_before with no padding_after used to put
        # nan into the step size and surface as "Too Few Levels" instead of the real
        # reason; a zero padding_after used to take the whole event as "baseline".
        for padding_before, padding_after in ((0, None), (None, 0)):
            with self.subTest(
                padding_before=padding_before, padding_after=padding_after
            ):
                pf = _make(ClassicCUSUM)
                with self.assertRaisesRegex(ValueError, "standard deviation"):
                    pf._locate_sublevel_transitions(
                        self.data, 1e6, padding_before, padding_after, 0.0, None
                    )


# ---------------------------------------------------------------------------
# Step Size in units of the baseline sigma: the one place the two fitters differ
# ---------------------------------------------------------------------------


class TestStepSizeInSigma(unittest.TestCase):
    def test_cusum_takes_step_size_in_picoamps_and_divides_by_sigma(self):
        pf = _make(CUSUM, step_size=100.0)
        self.assertAlmostEqual(pf._step_size_in_sigma(20.0), 5.0)

    def test_classic_cusum_takes_step_size_already_in_sigma(self):
        pf = _make(ClassicCUSUM, step_size=10.0)
        self.assertEqual(pf._step_size_in_sigma(20.0), 10.0)

    def test_classic_cusum_inherits_the_detector_rather_than_copying_it(self):
        # The subclass overrides only the step-size hook; the loop is CUSUM's.
        self.assertNotIn("_locate_sublevel_transitions", ClassicCUSUM.__dict__)
        self.assertIn("_step_size_in_sigma", ClassicCUSUM.__dict__)


# ---------------------------------------------------------------------------
# The detector's reset rule and its edge guard, against a planted staircase
# ---------------------------------------------------------------------------

SAMPLERATE_HZ = 500_000.0
#: A 400 pA blockage carrying three 40-sample steps 150 pA apart, 100 baseline samples
#: either side, white noise of 15 pA, Bessel-filtered at 100 kHz exactly as the
#: ground-truth fixtures are. After the filter the noise sigma is about 6.2 pA, so the
#: leading edge is about 64 sigma and each internal step about 24 sigma.
BASELINE_PA = 2000.0
STAIRCASE_PA = [1600.0, 1450.0, 1300.0]
STEP_SAMPLES = 40
PADDING_SAMPLES = 100


def _filtered_staircase(seed: int = 0) -> np.ndarray:
    """
    Build one Bessel-filtered staircase event the way the ground-truth fixtures do.

    :param seed: the noise seed
    :type seed: int
    :return: the event trace, paddings included
    :rtype: numpy.ndarray
    """
    rng = np.random.RandomState(seed)
    levels = np.concatenate(
        [np.full(PADDING_SAMPLES, BASELINE_PA)]
        + [np.full(STEP_SAMPLES, level) for level in STAIRCASE_PA]
        + [np.full(PADDING_SAMPLES, BASELINE_PA)]
    )
    trace = levels + rng.normal(0.0, 15.0, levels.size)
    return build_bessel_filter(SAMPLERATE_HZ, 100_000.0, 8).filter_data(trace)


def _filtered_sigma(seed: int = 1) -> float:
    rng = np.random.RandomState(seed)
    noise = rng.normal(0.0, 15.0, 200_000)
    return float(
        np.std(build_bessel_filter(SAMPLERATE_HZ, 100_000.0, 8).filter_data(noise))
    )


class TestResetOnEveryCrossing(unittest.TestCase):
    """
    After a large edge the detector must still see the steps that follow it.

    A threshold crossing the rise-time guard rejects used to leave the anchor where the
    accepted edge put it, mid-ramp, so Welford's variance from that anchor swallowed the
    rest of the ramp (hundreds of sigma squared) and the log-likelihoods, which scale as
    one over the variance, went blind to the 24 sigma steps that followed. Resetting on
    every crossing, as the reference C detector does, moves the anchor past the ramp.
    """

    def setUp(self):
        self.data = _filtered_staircase()
        self.sigma = _filtered_sigma()
        # planted boundaries: 100, 140, 180, 220
        self.planted = [
            PADDING_SAMPLES + STEP_SAMPLES * i for i in range(len(STAIRCASE_PA) + 1)
        ]

    def _assert_three_inner_levels(self, edges):
        self.assertEqual(len(edges), len(STAIRCASE_PA) + 3, list(edges))
        for found, planted in zip(edges[1:-1], self.planted):
            self.assertLessEqual(abs(int(found) - planted), 3, list(edges))

    def test_classic_cusum_resolves_the_steps_after_a_large_edge(self):
        pf = _make(ClassicCUSUM, step_size=10.0, rise_time_us=16.0, max_sublevels=10)
        edges = pf._locate_sublevel_transitions(
            self.data,
            SAMPLERATE_HZ,
            PADDING_SAMPLES,
            PADDING_SAMPLES,
            BASELINE_PA,
            self.sigma,
        )
        self._assert_three_inner_levels(edges)

    def test_cusum_resolves_the_steps_after_a_large_edge(self):
        pf = _make(
            CUSUM, step_size=10.0 * self.sigma, rise_time_us=16.0, max_sublevels=10
        )
        edges = pf._locate_sublevel_transitions(
            self.data,
            SAMPLERATE_HZ,
            PADDING_SAMPLES,
            PADDING_SAMPLES,
            BASELINE_PA,
            self.sigma,
        )
        self._assert_three_inner_levels(edges)


class TestEdgeGuard(unittest.TestCase):
    def test_a_jump_within_a_rise_time_of_the_end_is_not_an_edge(self):
        # Three clean plateaus, then a step three samples before the end. With a rise
        # time of eight samples the final step cannot start a sublevel long enough to
        # average, so it is refused the way a step within a rise time of the previous
        # edge is; the C detector guards both ends.
        pf = _make(ClassicCUSUM, step_size=5.0, rise_time_us=8.0)
        data = np.concatenate(
            [np.zeros(100), np.full(100, 50.0), np.zeros(97), np.full(3, 50.0)]
        )
        with patch.object(CUSUM, "_calculate_threshold", return_value=10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


class TestValidateSettings(unittest.TestCase):
    def test_a_zero_step_size_is_refused(self):
        # Zero passes the base class's range check (the minimum is zero) and used to
        # reach the threshold calculation as a division by zero, tallied as a rejection
        # reason on every event.
        for cls in (CUSUM, ClassicCUSUM):
            with self.subTest(cls=cls.__name__):
                pf = _make(cls, step_size=0.0)
                with self.assertRaisesRegex(ValueError, "Step Size"):
                    pf._validate_settings(pf.settings)

    def test_a_positive_step_size_is_accepted(self):
        for cls in (CUSUM, ClassicCUSUM):
            with self.subTest(cls=cls.__name__):
                pf = _make(cls, step_size=0.5)
                self.assertIsNone(pf._validate_settings(pf.settings))


if __name__ == "__main__":
    unittest.main()
