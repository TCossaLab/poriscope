"""
Tests for IntraCUSUM.py

IntraCUSUM only overrides four methods on top of CUSUM, and each one calls
super() and then layers its own logic on top. Rather than guess at what the
real CUSUM class returns (which previously caused a mismatch for
MetaEventFitter's base settings key), these tests mock out the CUSUM
superclass methods directly via unittest.mock.patch.object. This way each
test verifies only what IntraCUSUM itself contributes, and stays correct
regardless of what CUSUM actually does.

Instantiate IntraCUSUM via object.__new__ to bypass __init__. Settings are
injected directly onto the instance.

Coverage targets:
- get_empty_settings (own additions, on top of a mocked super() result)
- _populate_event_metadata (threshold_crossings counting logic + merge with
  a mocked super() result)
- _define_event_metadata_types (own addition, on top of a mocked super() result)
- _define_event_metadata_units (own addition, on top of a mocked super() result)
"""

import unittest
from unittest.mock import patch

import numpy as np

from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventfitters.IntraCUSUM import IntraCUSUM

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pf(threshold=20.0, hysteresis=10.0):
    """
    Return an IntraCUSUM with attributes injected, bypassing __init__.
    """
    pf = object.__new__(IntraCUSUM)
    pf.logger = IntraCUSUM.logger
    pf.settings = {
        "Intraevent Threshold": {"Value": threshold},
        "Intraevent Hysteresis": {"Value": hysteresis},
    }
    return pf


def _make_sublevel_metadata(baseline_current=200.0):
    return {"sublevel_current": np.array([baseline_current, baseline_current])}


# ---------------------------------------------------------------------------
# get_empty_settings
# ---------------------------------------------------------------------------


class TestGetEmptySettings(unittest.TestCase):
    def test_adds_own_keys_on_top_of_super(self):
        with patch.object(
            CUSUM,
            "get_empty_settings",
            return_value={"Base Key": {"Type": str, "Value": "x"}},
        ):
            pf = object.__new__(IntraCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        # Whatever CUSUM contributed is preserved untouched.
        self.assertIn("Base Key", settings)
        self.assertEqual(settings["Base Key"], {"Type": str, "Value": "x"})

        # IntraCUSUM's own additions are present.
        self.assertIn("Intraevent Threshold", settings)
        self.assertIn("Intraevent Hysteresis", settings)

    def test_intraevent_threshold_shape(self):
        with patch.object(CUSUM, "get_empty_settings", return_value={}):
            pf = object.__new__(IntraCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        threshold_setting = settings["Intraevent Threshold"]
        self.assertIs(threshold_setting["Type"], float)
        self.assertEqual(threshold_setting["Value"], 0)
        self.assertEqual(threshold_setting["Min"], 0)
        self.assertEqual(threshold_setting["Units"], "pA")

    def test_intraevent_hysteresis_shape(self):
        with patch.object(CUSUM, "get_empty_settings", return_value={}):
            pf = object.__new__(IntraCUSUM)
            settings = pf.get_empty_settings(standalone=True)

        hysteresis_setting = settings["Intraevent Hysteresis"]
        self.assertIs(hysteresis_setting["Type"], float)
        self.assertEqual(hysteresis_setting["Value"], 0)
        self.assertEqual(hysteresis_setting["Min"], 0)
        self.assertEqual(hysteresis_setting["Units"], "pA")

    def test_forwards_arguments_to_super(self):
        with patch.object(CUSUM, "get_empty_settings", return_value={}) as mock_super:
            pf = object.__new__(IntraCUSUM)
            pf.get_empty_settings(
                globally_available_plugins={"foo": ["bar"]}, standalone=True
            )

        mock_super.assert_called_once_with({"foo": ["bar"]}, True)


# ---------------------------------------------------------------------------
# _populate_event_metadata
# ---------------------------------------------------------------------------


class TestPopulateEventMetadata(unittest.TestCase):
    def _run(self, data, baseline_mean=200.0, baseline_std=5.0, **setting_overrides):
        pf = _make_pf(**setting_overrides)
        sublevel_metadata = _make_sublevel_metadata(baseline_current=baseline_mean)
        with patch.object(
            CUSUM, "_populate_event_metadata", return_value={"base_key": 1.0}
        ):
            return pf._populate_event_metadata(
                np.asarray(data, dtype=np.float64),
                1e6,
                baseline_mean,
                baseline_std,
                sublevel_metadata,
            )

    def test_merges_with_super_result(self):
        result = self._run(np.full(10, 200.0))
        self.assertIn("base_key", result)
        self.assertEqual(result["base_key"], 1.0)
        self.assertIn("threshold_crossings", result)

    def test_no_crossing_when_signal_stays_near_baseline(self):
        result = self._run(np.full(50, 200.0))
        self.assertEqual(result["threshold_crossings"], 0)

    def test_single_dip_and_recovery_counts_two_crossings(self):
        data = np.concatenate(
            [np.full(10, 200.0), np.full(10, 150.0), np.full(10, 200.0)]
        )
        result = self._run(data)
        self.assertEqual(result["threshold_crossings"], 2)

    def test_two_separate_dips_count_four_crossings(self):
        data = np.concatenate(
            [
                np.full(5, 200.0),
                np.full(5, 150.0),
                np.full(5, 200.0),
                np.full(5, 150.0),
                np.full(5, 200.0),
            ]
        )
        result = self._run(data)
        self.assertEqual(result["threshold_crossings"], 4)

    def test_dip_without_recovery_counts_one_crossing(self):
        data = np.concatenate([np.full(10, 200.0), np.full(10, 150.0)])
        result = self._run(data)
        self.assertEqual(result["threshold_crossings"], 1)

    def test_hysteresis_prevents_double_counting_a_wobble(self):
        # Dips below the down-threshold, wobbles up into the hysteresis dead
        # zone (between up- and down-threshold) without crossing the
        # up-threshold, then dips again before finally recovering. Should
        # register as a single down+up pair (2), not four crossings.
        data = np.concatenate(
            [
                np.full(5, 200.0),
                np.full(5, 150.0),  # dip: crosses down_threshold (180) -> +1
                np.full(5, 185.0),  # wobble: stays inside [180, 190], no change
                np.full(5, 150.0),  # still below; below_threshold already True
                np.full(5, 200.0),  # recovers: crosses up_threshold (190) -> +1
            ]
        )
        result = self._run(data)
        self.assertEqual(result["threshold_crossings"], 2)

    def test_negative_baseline_mirrors_positive_case(self):
        # sign(baseline_mean) flips both thresholds; behavior should mirror
        # the positive-baseline single-dip case.
        data = np.concatenate(
            [np.full(10, -200.0), np.full(10, -150.0), np.full(10, -200.0)]
        )
        result = self._run(data, baseline_mean=-200.0)
        self.assertEqual(result["threshold_crossings"], 2)

    def test_threshold_zero_with_nonzero_hysteresis(self):
        # threshold=0 -> down_threshold == baseline; any drop below baseline
        # immediately registers as a crossing.
        data = np.concatenate([np.full(5, 200.0), np.full(5, 199.0)])
        result = self._run(data, threshold=0.0, hysteresis=1.0)
        self.assertEqual(result["threshold_crossings"], 1)

    def test_does_not_mutate_input_data_array(self):
        data = np.concatenate(
            [np.full(10, 200.0), np.full(10, 150.0), np.full(10, 200.0)]
        )
        original = data.copy()
        self._run(data)
        np.testing.assert_array_equal(data, original)


# ---------------------------------------------------------------------------
# _define_event_metadata_types
# ---------------------------------------------------------------------------


class TestDefineEventMetadataTypes(unittest.TestCase):
    def test_adds_threshold_crossings_on_top_of_super(self):
        with patch.object(
            CUSUM, "_define_event_metadata_types", return_value={"base_key": float}
        ):
            pf = object.__new__(IntraCUSUM)
            result = pf._define_event_metadata_types()

        self.assertEqual(result["base_key"], float)
        self.assertIn("threshold_crossings", result)
        self.assertIs(result["threshold_crossings"], int)

    def test_does_not_remove_existing_keys(self):
        base = {"a": float, "b": str}
        with patch.object(CUSUM, "_define_event_metadata_types", return_value=base):
            pf = object.__new__(IntraCUSUM)
            result = pf._define_event_metadata_types()

        self.assertEqual(result["a"], float)
        self.assertEqual(result["b"], str)


# ---------------------------------------------------------------------------
# _define_event_metadata_units
# ---------------------------------------------------------------------------


class TestDefineEventMetadataUnits(unittest.TestCase):
    def test_adds_threshold_crossings_on_top_of_super(self):
        with patch.object(
            CUSUM, "_define_event_metadata_units", return_value={"base_key": "pA"}
        ):
            pf = object.__new__(IntraCUSUM)
            result = pf._define_event_metadata_units()

        self.assertEqual(result["base_key"], "pA")
        self.assertIn("threshold_crossings", result)
        self.assertEqual(result["threshold_crossings"], "")

    def test_does_not_remove_existing_keys(self):
        base = {"a": "pA", "b": None}
        with patch.object(CUSUM, "_define_event_metadata_units", return_value=base):
            pf = object.__new__(IntraCUSUM)
            result = pf._define_event_metadata_units()

        self.assertEqual(result["a"], "pA")
        self.assertIsNone(result["b"])


if __name__ == "__main__":
    unittest.main()
