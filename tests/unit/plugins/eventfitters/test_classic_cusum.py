"""
Tests for ClassicCUSUM.py

ClassicCUSUM overrides two methods on CUSUM:
  - get_empty_settings: adds "Step Size" and "Sensitivity" on top of super().
  - _locate_sublevel_transitions: the actual CUSUM change-point detection
    algorithm (running mean/variance, log-likelihood accumulation, jump
    detection, iterative small-step merging, and a retry loop that grows
    step_size if too many sublevels are found).

_locate_sublevel_transitions calls self._calculate_threshold(length,
step_size), which lives on the real CUSUM class and is not available here.
Every test mocks it via unittest.mock.patch.object(CUSUM,
"_calculate_threshold", return_value=...) so behavior is deterministic and
these tests don't depend on guessing what the real implementation does.

This algorithm is genuinely complex (running variance updates, CUSUM
decision functions, a merge-small-steps inner loop, a step-size-growing
retry outer loop), so rather than hand-deriving expected edges, every
scenario below was first run against the actual source with hand-built
step data and the printed/inspected output was used to write the
assertions. Where a scenario depends on a specific interaction (e.g. the
retry loop actually succeeding in reducing sublevel count, vs. it being
unable to and raising "Too Many Levels", vs. it accidentally reducing
below 3 and raising "Too Few Levels" instead) the comment next to each test
explains why that particular data/threshold/max_sublevels combination
produces that particular outcome.

Instantiate ClassicCUSUM via object.__new__ to bypass __init__. Settings are
injected directly onto the instance.

Coverage targets:
- get_empty_settings (own additions, including a documented quirk: "Step
  Size" is given no "Value" key at all, unlike every other setting in this
  codebase)
- _locate_sublevel_transitions:
    - baseline_std=None handling (both the immediate-raise and the
      computed-from-padding fallback paths)
    - "Too Few Levels" (flat data, single-jump data)
    - happy path with a clean multi-plateau signal
    - small-step merging removing a step from the result
    - rise_time suppressing a short-lived intermediate plateau
    - the max_sublevels retry loop: a case where retries succeed in merging
      down to an acceptable sublevel count, and a case where retries are
      exhausted and "Too Many Levels" is raised
    - symmetric handling of downward jumps
"""

import unittest
from unittest.mock import patch

import numpy as np

from poriscope.plugins.eventfitters.ClassicCUSUM import ClassicCUSUM
from poriscope.plugins.eventfitters.CUSUM import CUSUM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pf(step_size=5.0, rise_time_us=0.0, max_sublevels=0):
    """
    Return a ClassicCUSUM with attributes injected, bypassing __init__.
    rise_time_us is in microseconds; with samplerate=1e6 in these tests,
    1e-6 * rise_time_us * 1e6 == rise_time_us, so it maps 1:1 to samples.
    """
    pf = object.__new__(ClassicCUSUM)
    pf.settings = {
        "Step Size": {"Value": step_size},
        "Rise Time": {"Value": rise_time_us},
        "Max Sublevels": {"Value": max_sublevels},
    }
    return pf


def _mock_threshold(value=10.0):
    """Patch CUSUM._calculate_threshold so tests are deterministic."""
    return patch.object(CUSUM, "_calculate_threshold", return_value=value)


# ---------------------------------------------------------------------------
# get_empty_settings
# ---------------------------------------------------------------------------


class TestGetEmptySettings(unittest.TestCase):
    def test_adds_own_keys_on_top_of_super(self):
        with patch.object(
            CUSUM, "get_empty_settings", return_value={"Base Key": {"Type": str}}
        ):
            pf = object.__new__(ClassicCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        self.assertIn("Base Key", settings)
        self.assertIn("Step Size", settings)
        self.assertIn("Sensitivity", settings)

    def test_step_size_has_no_value_key(self):
        # Unlike every other setting dict in this codebase, "Step Size" is
        # given Type/Min/Units but no "Value" key at all. This is tested
        # explicitly as documented, observed behavior.
        with patch.object(CUSUM, "get_empty_settings", return_value={}):
            pf = object.__new__(ClassicCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        step_size_setting = settings["Step Size"]
        self.assertIs(step_size_setting["Type"], float)
        self.assertEqual(step_size_setting["Min"], 0.0)
        self.assertEqual(step_size_setting["Units"], "σ")
        self.assertNotIn("Value", step_size_setting)

    def test_sensitivity_shape(self):
        with patch.object(CUSUM, "get_empty_settings", return_value={}):
            pf = object.__new__(ClassicCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        sensitivity_setting = settings["Sensitivity"]
        self.assertIs(sensitivity_setting["Type"], float)
        self.assertEqual(sensitivity_setting["Value"], 1)
        self.assertEqual(sensitivity_setting["Min"], 1)
        self.assertEqual(sensitivity_setting["Max"], 5)

    def test_forwards_arguments_to_super(self):
        with patch.object(CUSUM, "get_empty_settings", return_value={}) as mock_super:
            pf = object.__new__(ClassicCUSUM)
            pf.get_empty_settings(
                globally_available_plugins={"foo": ["bar"]}, standalone=True
            )
        mock_super.assert_called_once_with({"foo": ["bar"]}, True)


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: baseline_std handling
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsBaselineStd(unittest.TestCase):
    def test_missing_baseline_std_and_padding_raises(self):
        pf = _make_pf()
        with self.assertRaises(ValueError):
            pf._locate_sublevel_transitions(np.zeros(10), 1e6, None, None, 0.0, None)

    def test_baseline_std_computed_from_padding_before(self):
        # baseline_std=None with padding_before given -> computed from
        # data[:padding_before] via np.std. Using a fixed seed for
        # reproducibility; the resulting edges were confirmed by actually
        # running this exact scenario.
        rng = np.random.RandomState(0)
        noise = rng.normal(0, 5.0, 300)
        data = (
            np.concatenate([np.zeros(100), np.full(100, 50.0), np.zeros(100)]) + noise
        )
        pf = _make_pf()
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, 50, None, 0.0, None)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: Too Few Levels
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsTooFewLevels(unittest.TestCase):
    def test_flat_data_raises_too_few_levels(self):
        pf = _make_pf()
        data = np.zeros(300)
        with _mock_threshold(10.0):
            with self.assertRaisesRegex(ValueError, "Too Few Levels"):
                pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)

    def test_single_jump_raises_too_few_levels(self):
        # Only one real transition -> 2 segments, below the minimum of 3.
        pf = _make_pf()
        data = np.concatenate([np.zeros(150), np.full(150, 50.0)])
        with _mock_threshold(10.0):
            with self.assertRaisesRegex(ValueError, "Too Few Levels"):
                pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: happy path
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsHappyPath(unittest.TestCase):
    def test_three_clean_plateaus_detected_correctly(self):
        pf = _make_pf()
        data = np.concatenate([np.zeros(100), np.full(100, 50.0), np.zeros(100)])
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])
        self.assertEqual(edges.dtype, np.int64)

    def test_downward_jump_detected_symmetrically(self):
        pf = _make_pf()
        data = np.concatenate([np.zeros(100), np.full(100, -50.0), np.zeros(100)])
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])

    def test_calculate_threshold_called_with_length_and_step_size(self):
        pf = _make_pf(step_size=5.0)
        data = np.concatenate([np.zeros(100), np.full(100, 50.0), np.zeros(100)])
        with _mock_threshold(10.0) as mock_calc:
            pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        mock_calc.assert_called_once_with(300, 5.0)


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: small-step merging
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsSmallStepMerging(unittest.TestCase):
    def test_small_step_between_large_jumps_gets_merged(self):
        # Plateaus at 0, 50, 58, 0. The 50->58 step (diff=8) is below the
        # "too small" cutoff of step_size*baseline_std/2 = 5*5/2 = 12.5, so
        # it gets merged away by the iterative small-step-removal loop,
        # leaving 3 final segments instead of 4.
        pf = _make_pf(step_size=5.0)
        data = np.concatenate(
            [
                np.zeros(100),
                np.full(50, 50.0),
                np.full(50, 58.0),
                np.zeros(100),
            ]
        )
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: rise_time suppression
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsRiseTime(unittest.TestCase):
    def _make_short_plateau_data(self):
        # A short (10-sample) intermediate plateau sandwiched between two
        # longer ones.
        return np.concatenate(
            [
                np.full(100, 0.0),
                np.full(10, 50.0),
                np.full(90, 100.0),
                np.full(100, 0.0),
            ]
        )

    def test_rise_time_zero_keeps_short_plateau(self):
        pf = _make_pf(rise_time_us=0.0)
        data = self._make_short_plateau_data()
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 110, 200, 300])

    def test_rise_time_suppresses_short_plateau(self):
        # With rise_time=30 samples, the jump only 10 samples after the
        # previous one (110 - 100 = 10 <= 30) is rejected by the
        # `jump - edges[num_states] > rise_time` check, so the short
        # plateau never becomes its own sublevel.
        pf = _make_pf(rise_time_us=30.0)
        data = self._make_short_plateau_data()
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 100, 200, 300])


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions: max_sublevels retry loop
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitionsMaxSublevels(unittest.TestCase):
    def test_retry_successfully_merges_down_to_max_sublevels(self):
        # 5 plateaus at 0, 15, 30, 45, 60 (step=15 each). With
        # max_sublevels=3, the outer retry loop grows step_size on each
        # attempt; once it's grown enough, the small-step merge pass
        # collapses adjacent plateaus until exactly 3 segments remain.
        pf = _make_pf(step_size=5.0, max_sublevels=3)
        data = np.concatenate(
            [
                np.full(60, 0.0),
                np.full(60, 15.0),
                np.full(60, 30.0),
                np.full(60, 45.0),
                np.full(60, 60.0),
            ]
        )
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 120, 240, 300])

    def test_too_many_levels_raised_after_retries_exhausted(self):
        # 5 plateaus with very large, well-separated jumps (0, 100, 200,
        # 300, 400) relative to baseline_std=5. Even after the retry loop
        # grows step_size repeatedly, the genuine jumps never look "too
        # small", so sublevel count never drops to max_sublevels (2), and
        # after retries are exhausted "Too Many Levels" is raised.
        pf = _make_pf(step_size=5.0, max_sublevels=2)
        data = np.concatenate(
            [
                np.full(60, 0.0),
                np.full(60, 100.0),
                np.full(60, 200.0),
                np.full(60, 300.0),
                np.full(60, 400.0),
            ]
        )
        with _mock_threshold(10.0):
            with self.assertRaisesRegex(ValueError, "Too Many Levels"):
                pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)

    def test_max_sublevels_zero_disables_the_retry_and_cap(self):
        # max_sublevels=0 means neither the retry condition nor the final
        # "Too Many Levels" check ever fire, regardless of how many
        # sublevels are found.
        pf = _make_pf(step_size=5.0, max_sublevels=0)
        data = np.concatenate(
            [
                np.full(60, 0.0),
                np.full(60, 100.0),
                np.full(60, 200.0),
                np.full(60, 300.0),
                np.full(60, 400.0),
            ]
        )
        with _mock_threshold(10.0):
            edges = pf._locate_sublevel_transitions(data, 1e6, None, None, 0.0, 5.0)
        # 5 plateaus -> 5 segments, all preserved since there's no cap.
        self.assertEqual(len(edges) - 1, 5)


if __name__ == "__main__":
    unittest.main()
