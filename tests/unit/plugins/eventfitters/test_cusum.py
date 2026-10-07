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

import numpy as np

from poriscope.plugins.eventfitters.ClassicCUSUM import ClassicCUSUM
from poriscope.plugins.eventfitters.CUSUM import CUSUM


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
            with self.subTest(padding_before=padding_before, padding_after=padding_after):
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


if __name__ == "__main__":
    unittest.main()
