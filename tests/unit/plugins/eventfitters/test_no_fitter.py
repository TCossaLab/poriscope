"""
Tests for NoFitter.py

Instantiate NoFitter via object.__new__ to bypass __init__. Settings and
metadata are injected directly onto the instance.

NoFitter uses a different sublevel-detection strategy than Basic_PeakFinder:
it assumes exactly one blockage level per event and walks backward from
padding_before to absorb any "rise time" baseline already inside the nominal
padding window, rather than running a peak-finding algorithm. Several of its
formulas were verified by actually running the real source against
hand-picked synthetic data before writing assertions (see comments below for
two behaviors worth flagging):

- get_empty_settings makes NO additions of its own; it returns whatever the
  superclass produced, completely unchanged.
- _populate_event_metadata's max_blockage_duration/min_blockage_duration/
  max_deviation_duration fields compute argmax/argmin on the trimmed
  [1:-1] slice of sublevel_blockage / sublevel_max_deviation, and look up
  sublevel_duration through that same trimmed slice, so the reported
  duration correctly corresponds to the sublevel that actually holds the
  max/min value.

Coverage targets:
- get_empty_settings (pure passthrough)
- close_resources / _init / _pre_process_events / _post_process_events / _validate_settings
- construct_fitted_event (None paths, AttributeError propagation, happy path)
- _locate_sublevel_transitions (no rise time, with rise time, sign handling)
- _populate_sublevel_metadata (happy path, Baseline Mismatch, degenerate slice branch)
- _populate_event_metadata (including the documented index-alignment quirk)
- _define_event_metadata_types / _define_sublevel_metadata_types
- _define_event_metadata_units / _define_sublevel_metadata_units
"""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from poriscope.plugins.eventfitters.NoFitter import NoFitter
from poriscope.utils.MetaEventFitter import MetaEventFitter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pf(rise_time=0):
    pf = object.__new__(NoFitter)
    pf.rise_time = rise_time
    return pf


# ---------------------------------------------------------------------------
# get_empty_settings
# ---------------------------------------------------------------------------


class TestGetEmptySettings(unittest.TestCase):
    def test_pure_passthrough_no_additions(self):
        # Unlike Basic_PeakFinder/IntraCUSUM, NoFitter adds nothing of its
        # own; it must return exactly what the superclass provided.
        base = {"Base Key": {"Type": str, "Value": "x"}}
        with patch.object(MetaEventFitter, "get_empty_settings", return_value=base):
            pf = object.__new__(NoFitter)
            settings = pf.get_empty_settings(standalone=True)
        self.assertEqual(settings, base)

    def test_forwards_arguments_to_super(self):
        with patch.object(
            MetaEventFitter, "get_empty_settings", return_value={}
        ) as mock_super:
            pf = object.__new__(NoFitter)
            pf.get_empty_settings(
                globally_available_plugins={"foo": ["bar"]}, standalone=True
            )
        mock_super.assert_called_once_with({"foo": ["bar"]}, True)


# ---------------------------------------------------------------------------
# Noop overrides
# ---------------------------------------------------------------------------


class TestNoopOverrides(unittest.TestCase):
    def setUp(self):
        self.pf = object.__new__(NoFitter)

    def test_init_noop(self):
        self.assertIsNone(self.pf._init())

    def test_pre_process_noop(self):
        self.assertIsNone(self.pf._pre_process_events(0))

    def test_post_process_noop(self):
        self.assertIsNone(self.pf._post_process_events(0))

    def test_validate_settings_noop(self):
        self.assertIsNone(self.pf._validate_settings({}))

    def test_close_resources_noop(self):
        self.assertIsNone(self.pf.close_resources())


# ---------------------------------------------------------------------------
# construct_fitted_event
# ---------------------------------------------------------------------------


class TestConstructFittedEvent(unittest.TestCase):
    def test_empty_sublevel_metadata_returns_none(self):
        pf = object.__new__(NoFitter)
        pf.sublevel_metadata = {}
        pf.eventfitting_status = {}
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_fitting_not_done_returns_none(self):
        pf = object.__new__(NoFitter)
        pf.sublevel_metadata = {0: {0: {}}}  # non-empty, so the {} check passes
        pf.eventfitting_status = {0: False}
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_eventloader_none_raises_attributeerror(self):
        # NoFitter raises AttributeError when eventloader is None, and that
        # error is NOT caught by the method's `except KeyError` clause, so
        # it propagates to the caller instead of returning None.
        pf = object.__new__(NoFitter)
        pf.sublevel_metadata = {0: {0: {"sublevel_current": np.array([200.0])}}}
        pf.eventfitting_status = {0: True}
        pf.eventloader = None
        with self.assertRaises(AttributeError):
            pf.construct_fitted_event(0, 0)

    def test_missing_sublevel_starts_entry_returns_none(self):
        pf = object.__new__(NoFitter)
        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = 1e6
        pf.sublevel_metadata = {0: {0: {"sublevel_current": np.array([200.0])}}}
        pf.eventfitting_status = {0: True}
        pf.sublevel_starts = {0: {99: np.array([0, 10])}}  # only index 99 exists
        pf.event_lengths = {0: {0: 100}}
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_happy_path_returns_expected_array(self):
        pf = object.__new__(NoFitter)
        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = 1e6
        pf.sublevel_metadata = {
            0: {0: {"sublevel_current": np.array([100.0, 300.0, 100.0])}}
        }
        pf.eventfitting_status = {0: True}
        pf.sublevel_starts = {0: {0: np.array([0, 30, 70])}}
        pf.event_lengths = {0: {0: 100}}

        result = pf.construct_fitted_event(0, 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 100)
        np.testing.assert_allclose(result[0:30], 100.0)
        np.testing.assert_allclose(result[30:70], 300.0)
        np.testing.assert_allclose(result[70:100], 100.0)

    def test_eventloader_samplerate_result_is_unused(self):
        # construct_fitted_event calls get_samplerate() but discards the
        # result -- sublevel_starts/event_lengths are already in raw sample
        # indices, not time, for this fitter. A nonsense return value should
        # have no effect on the output.
        pf = object.__new__(NoFitter)
        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = "not a real samplerate"
        pf.sublevel_metadata = {0: {0: {"sublevel_current": np.array([100.0])}}}
        pf.eventfitting_status = {0: True}
        pf.sublevel_starts = {0: {0: np.array([0])}}
        pf.event_lengths = {0: {0: 50}}

        result = pf.construct_fitted_event(0, 0)
        self.assertEqual(len(result), 50)
        np.testing.assert_allclose(result, 100.0)


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitions(unittest.TestCase):
    def test_no_rise_time(self):
        pf = object.__new__(NoFitter)
        data = np.full(50, 200.0)
        edges = pf._locate_sublevel_transitions(data, 1e6, 10, 5, 200.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 10, 45, 50])
        self.assertEqual(pf.rise_time, 0)

    def test_with_rise_time(self):
        pf = object.__new__(NoFitter)
        data = np.full(50, 200.0)
        data[6:11] = 150.0  # samples below baseline, inside the nominal padding
        edges = pf._locate_sublevel_transitions(data, 1e6, 10, 5, 200.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 5, 40, 50])
        self.assertEqual(pf.rise_time, 5)

    def test_negative_baseline_mirrors_positive_case(self):
        pf = object.__new__(NoFitter)
        data = np.full(50, -200.0)
        edges = pf._locate_sublevel_transitions(data, 1e6, 10, 5, -200.0, 5.0)
        np.testing.assert_array_equal(edges, [0, 10, 45, 50])
        self.assertEqual(pf.rise_time, 0)

    def test_first_and_last_edges_match_data_bounds(self):
        pf = object.__new__(NoFitter)
        data = np.full(80, 200.0)
        edges = pf._locate_sublevel_transitions(data, 1e6, 20, 10, 200.0, 5.0)
        self.assertEqual(edges[0], 0)
        self.assertEqual(edges[-1], len(data))


# ---------------------------------------------------------------------------
# _populate_sublevel_metadata
# ---------------------------------------------------------------------------


class TestPopulateSublevelMetadata(unittest.TestCase):
    def test_happy_path_values(self):
        pf = _make_pf(rise_time=0)
        data = np.concatenate(
            [np.full(20, 200.0), np.full(60, 150.0), np.full(20, 200.0)]
        )
        starts = np.array([0, 20, 80, 100])
        meta = pf._populate_sublevel_metadata(data, 1e6, 200.0, 5.0, starts)

        np.testing.assert_allclose(meta["sublevel_current"], [200.0, 150.0, 200.0])
        np.testing.assert_allclose(meta["sublevel_stdev"], [0.0, 0.0, 0.0])
        np.testing.assert_allclose(meta["sublevel_blockage"], [0.0, 50.0, 0.0])
        np.testing.assert_allclose(meta["sublevel_duration"], [20.0, 60.0, 20.0])
        np.testing.assert_allclose(meta["sublevel_start_times"], [0.0, 20.0, 80.0])
        np.testing.assert_allclose(meta["sublevel_end_times"], [20.0, 80.0, 100.0])
        np.testing.assert_allclose(meta["sublevel_max_deviation"], [0.0, 50.0, 0.0])
        np.testing.assert_allclose(meta["sublevel_raw_ecd"], [0.0, 0.003, 0.0])
        np.testing.assert_allclose(meta["sublevel_fitted_ecd"], [0.0, 0.003, 0.0])

    def test_required_keys_present(self):
        pf = _make_pf(rise_time=0)
        data = np.concatenate(
            [np.full(20, 200.0), np.full(60, 150.0), np.full(20, 200.0)]
        )
        starts = np.array([0, 20, 80, 100])
        meta = pf._populate_sublevel_metadata(data, 1e6, 200.0, 5.0, starts)
        for key in [
            "sublevel_current",
            "sublevel_stdev",
            "sublevel_blockage",
            "sublevel_duration",
            "sublevel_start_times",
            "sublevel_end_times",
            "sublevel_max_deviation",
            "sublevel_raw_ecd",
            "sublevel_fitted_ecd",
        ]:
            self.assertIn(key, meta)

    def test_baseline_mismatch_raises(self):
        pf = _make_pf(rise_time=0)
        data = np.concatenate(
            [np.full(20, 200.0), np.full(60, 150.0), np.full(20, 250.0)]
        )
        starts = np.array([0, 20, 80, 100])
        with self.assertRaises(ValueError):
            pf._populate_sublevel_metadata(data, 1e6, 200.0, 5.0, starts)

    def test_no_mismatch_when_within_tolerance(self):
        # Diff of exactly 2*baseline_std should NOT raise (condition is
        # strictly "> 2*baseline_std").
        pf = _make_pf(rise_time=0)
        data = np.concatenate(
            [np.full(20, 200.0), np.full(60, 150.0), np.full(20, 210.0)]
        )
        starts = np.array([0, 20, 80, 100])
        # diff = 10 = 2*5, not strictly greater -> should not raise
        meta = pf._populate_sublevel_metadata(data, 1e6, 200.0, 5.0, starts)
        self.assertIn("sublevel_current", meta)

    def test_degenerate_slice_branch_for_first_sublevel(self):
        # Asymmetric widths (first=10, last=30) with rise_time=10 makes only
        # the first sublevel's window fully consumed by rise_time, isolating
        # the "else" branch to that one sublevel.
        pf = _make_pf(rise_time=10)
        data = np.concatenate(
            [np.full(10, 200.0), np.full(60, 150.0), np.full(30, 200.0)]
        )
        starts = np.array([0, 10, 70, 100])
        meta = pf._populate_sublevel_metadata(data, 1e6, 200.0, 5.0, starts)

        # Degenerate branch: sublevel_current falls back to data[end - 1].
        self.assertEqual(meta["sublevel_current"][0], data[9])
        # Degenerate branch: sublevel_stdev falls back to baseline_std.
        self.assertEqual(meta["sublevel_stdev"][0], 5.0)
        # Non-degenerate sublevels are unaffected.
        self.assertEqual(meta["sublevel_current"][1], 150.0)
        self.assertEqual(meta["sublevel_stdev"][1], 0.0)
        self.assertEqual(meta["sublevel_current"][2], 200.0)
        self.assertEqual(meta["sublevel_stdev"][2], 0.0)


# ---------------------------------------------------------------------------
# _populate_event_metadata
# ---------------------------------------------------------------------------


class TestPopulateEventMetadata(unittest.TestCase):
    def _make_sublevel_meta(self):
        # 5 sublevels; inner [1:-1] corresponds to full-array indices 1,2,3.
        return {
            "sublevel_duration": np.array([5.0, 10.0, 20.0, 30.0, 5.0]),
            "sublevel_fitted_ecd": np.array([0.0, 1.0, 2.0, 3.0, 0.0]),
            "sublevel_raw_ecd": np.array([0.0, 1.1, 2.1, 3.1, 0.0]),
            "sublevel_blockage": np.array([0.0, 10.0, 50.0, 20.0, 0.0]),
            "sublevel_max_deviation": np.array([0.0, 5.0, 60.0, 7.0, 0.0]),
            "sublevel_current": np.array([200.0, 1.0, 2.0, 3.0, 200.0]),
            "sublevel_stdev": np.array([5.0, 1.0, 2.0, 3.0, 5.0]),
        }

    def test_all_keys_present(self):
        pf = object.__new__(NoFitter)
        result = pf._populate_event_metadata(
            np.zeros(10), 1e6, 200.0, 5.0, self._make_sublevel_meta()
        )
        for key in [
            "duration",
            "fitted_ecd",
            "raw_ecd",
            "max_blockage",
            "min_blockage",
            "max_deviation",
            "max_blockage_duration",
            "min_blockage_duration",
            "max_deviation_duration",
            "baseline_current",
            "baseline_stdev",
        ]:
            self.assertIn(key, result)

    def test_duration_and_ecd_sums_use_inner_sublevels_only(self):
        pf = object.__new__(NoFitter)
        result = pf._populate_event_metadata(
            np.zeros(10), 1e6, 200.0, 5.0, self._make_sublevel_meta()
        )
        self.assertAlmostEqual(result["duration"], 60.0)  # 10+20+30
        self.assertAlmostEqual(result["fitted_ecd"], 6.0)  # 1+2+3
        self.assertAlmostEqual(result["raw_ecd"], 6.3, places=6)  # 1.1+2.1+3.1

    def test_max_and_min_blockage_use_inner_sublevels_only(self):
        pf = object.__new__(NoFitter)
        result = pf._populate_event_metadata(
            np.zeros(10), 1e6, 200.0, 5.0, self._make_sublevel_meta()
        )
        self.assertEqual(result["max_blockage"], 50.0)
        self.assertEqual(result["min_blockage"], 10.0)
        self.assertEqual(result["max_deviation"], 60.0)

    def test_duration_alignment_matches_sublevel_holding_extreme_value(self):
        # sublevel_blockage inner [1:-1] slice is [10, 50, 20]: the max (50)
        # is at full-index 2, the min (10) is at full-index 1. argmax/argmin
        # are computed on that trimmed slice, and sublevel_duration is looked
        # up through the SAME trimmed slice, so the reported duration must
        # correspond to the sublevel that actually holds the extreme value.
        pf = object.__new__(NoFitter)
        meta = self._make_sublevel_meta()
        result = pf._populate_event_metadata(np.zeros(10), 1e6, 200.0, 5.0, meta)

        self.assertEqual(result["max_blockage_duration"], meta["sublevel_duration"][2])
        self.assertEqual(result["min_blockage_duration"], meta["sublevel_duration"][1])
        # sublevel_max_deviation inner slice [5, 60, 7] -> max at full-index 2
        self.assertEqual(result["max_deviation_duration"], meta["sublevel_duration"][2])

    def test_baseline_current_is_duration_weighted_average_of_endpoints(self):
        pf = object.__new__(NoFitter)
        meta = self._make_sublevel_meta()
        meta["sublevel_current"] = np.array([100.0, 1.0, 2.0, 3.0, 300.0])
        meta["sublevel_duration"] = np.array([10.0, 1.0, 1.0, 1.0, 30.0])
        result = pf._populate_event_metadata(np.zeros(10), 1e6, 200.0, 5.0, meta)
        expected = (100.0 * 10.0 + 300.0 * 30.0) / (10.0 + 30.0)
        self.assertAlmostEqual(result["baseline_current"], expected)

    def test_baseline_stdev_is_duration_weighted_average_of_endpoints(self):
        pf = object.__new__(NoFitter)
        meta = self._make_sublevel_meta()
        meta["sublevel_stdev"] = np.array([2.0, 1.0, 1.0, 1.0, 6.0])
        meta["sublevel_duration"] = np.array([10.0, 1.0, 1.0, 1.0, 30.0])
        result = pf._populate_event_metadata(np.zeros(10), 1e6, 200.0, 5.0, meta)
        expected = (2.0 * 10.0 + 6.0 * 30.0) / (10.0 + 30.0)
        self.assertAlmostEqual(result["baseline_stdev"], expected)


# ---------------------------------------------------------------------------
# _define_event_metadata_types / units, _define_sublevel_metadata_types / units
# ---------------------------------------------------------------------------


class TestDefineMetadataTypesAndUnits(unittest.TestCase):
    def setUp(self):
        self.pf = object.__new__(NoFitter)

    def test_event_metadata_types(self):
        t = self.pf._define_event_metadata_types()
        expected_keys = {
            "duration",
            "fitted_ecd",
            "raw_ecd",
            "max_blockage",
            "min_blockage",
            "max_deviation",
            "max_blockage_duration",
            "min_blockage_duration",
            "max_deviation_duration",
            "baseline_current",
            "baseline_stdev",
        }
        self.assertEqual(set(t.keys()), expected_keys)
        self.assertTrue(all(v is float for v in t.values()))

    def test_sublevel_metadata_types(self):
        t = self.pf._define_sublevel_metadata_types()
        expected_keys = {
            "sublevel_current",
            "sublevel_stdev",
            "sublevel_blockage",
            "sublevel_duration",
            "sublevel_start_times",
            "sublevel_end_times",
            "sublevel_max_deviation",
            "sublevel_raw_ecd",
            "sublevel_fitted_ecd",
        }
        self.assertEqual(set(t.keys()), expected_keys)
        self.assertTrue(all(v is float for v in t.values()))

    def test_event_metadata_units(self):
        u = self.pf._define_event_metadata_units()
        self.assertEqual(u["duration"], "us")
        self.assertEqual(u["fitted_ecd"], "pC")
        self.assertEqual(u["raw_ecd"], "pC")
        self.assertEqual(u["max_blockage"], "pA")
        self.assertEqual(u["min_blockage"], "pA")
        self.assertEqual(u["max_deviation"], "pA")
        self.assertEqual(u["max_blockage_duration"], "us")
        self.assertEqual(u["min_blockage_duration"], "us")
        self.assertEqual(u["max_deviation_duration"], "us")
        self.assertEqual(u["baseline_current"], "pA")
        self.assertEqual(u["baseline_stdev"], "pA")

    def test_sublevel_metadata_units(self):
        u = self.pf._define_sublevel_metadata_units()
        self.assertEqual(u["sublevel_current"], "pA")
        self.assertEqual(u["sublevel_stdev"], "pA")
        self.assertEqual(u["sublevel_blockage"], "pA")
        self.assertEqual(u["sublevel_duration"], "us")
        self.assertEqual(u["sublevel_start_times"], "us")
        self.assertEqual(u["sublevel_end_times"], "us")
        self.assertEqual(u["sublevel_max_deviation"], "pA")
        self.assertEqual(u["sublevel_raw_ecd"], "pC")
        self.assertEqual(u["sublevel_fitted_ecd"], "pC")

    def test_event_types_and_units_keys_align(self):
        types = self.pf._define_event_metadata_types()
        units = self.pf._define_event_metadata_units()
        self.assertEqual(set(types.keys()), set(units.keys()))

    def test_sublevel_types_and_units_keys_align(self):
        types = self.pf._define_sublevel_metadata_types()
        units = self.pf._define_sublevel_metadata_units()
        self.assertEqual(set(types.keys()), set(units.keys()))


if __name__ == "__main__":
    unittest.main()
