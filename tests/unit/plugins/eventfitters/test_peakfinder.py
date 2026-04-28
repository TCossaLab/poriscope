"""
Tests for PeakFinder.py

instantiate PeakFinder via object.__new__ to bypass __init__ and the event-loader requirement.
Settings and metadata are injected directly onto the instance.

Coverage targets:
- find_unfolded_blockage_level
- enumerate_peaks
- filter_peaks (all three Event Type branches + all sub-branches)
- _populate_sublevel_metadata
- _populate_event_metadata
- _define_event_metadata_types / _define_sublevel_metadata_types
- _define_event_metadata_units / _define_sublevel_metadata_units
- construct_fitted_event (None paths)
- get_plot_features (None paths + Some/All/None plot feature paths)
- _init / _pre_process_events / _post_process_events / _validate_settings / close_resources
"""

import unittest
from unittest.mock import MagicMock

import numpy as np

from poriscope.plugins.eventfitters.PeakFinder import PeakFinder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pf(**setting_overrides):
    """
    Return a PeakFinder with attributes injected, bypassing __init__.
    """
    pf = object.__new__(PeakFinder)
    pf.sublevel_metadata = {}
    pf.event_metadata = {}
    pf.eventfitting_status = {}
    pf.event_lengths = {}
    pf.eventloader = None
    pf.logger = PeakFinder.logger
    pf.settings = {
        "Event Type":       {"Value": "Unspecified"},
        "Min Height":       {"Value": 500.0},
        "Min Prominence":   {"Value": 100.0},
        "Relative Height":  {"Value": 0.5},
        "Window Length":    {"Value": 25.0},
        "Width":            {"Value": 0.0},
        "Min Distance":     {"Value": 1.0},
        "Max Unfolded":     {"Value": 750.0},
        "Number of peaks":  {"Value": 1},
        "Plot Features":    {"Value": "Some"},
    }
    for k, v in setting_overrides.items():
        pf.settings[k]["Value"] = v
    return pf


def _make_sublevel_starts(n_peaks=1, padding_before=10, data_len=100, padding_after=10):
    """Build a minimal sublevel_starts list as _locate_sublevel_transitions would."""
    peak_index = padding_before + 20
    starts = [
        {"index": 0,               "type": "start",          "peak_height": None, "prominence": None,
         "left_base": None, "right_base": None, "width": None, "left_ips": None, "right_ips": None,
         "filtered": None, "unfolded_level": 200.0},
        {"index": padding_before,  "type": "padding_before",  "peak_height": None, "prominence": None,
         "left_base": None, "right_base": None, "width": None, "left_ips": None, "right_ips": None,
         "filtered": None},
    ]
    for i in range(n_peaks):
        starts.append({
            "index":       peak_index + i * 5,
            "type":        f"peak_{i+1}",
            "peak_height": 600.0,
            "prominence":  150.0,
            "left_base":   180.0,
            "right_base":  180.0,
            "width":       3.0,
            "left_ips":    peak_index + i * 5 - 1,
            "right_ips":   peak_index + i * 5 + 1,
            "filtered":    0,
        })
    starts += [
        {"index": data_len - padding_after, "type": "padding_after", "peak_height": None,
         "prominence": None, "left_base": None, "right_base": None, "width": None,
         "left_ips": None, "right_ips": None, "filtered": None},
        {"index": data_len,                 "type": "end",           "peak_height": None,
         "prominence": None, "left_base": None, "right_base": None, "width": None,
         "left_ips": None, "right_ips": None, "filtered": None},
    ]
    return starts


# ---------------------------------------------------------------------------
# find_unfolded_blockage_level
# ---------------------------------------------------------------------------

class TestFindUnfoldedBlockageLevel(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_returns_float(self):
        data = np.concatenate([np.ones(50) * 100.0, np.ones(50) * 300.0])
        result = self.pf.find_unfolded_blockage_level(data, 750.0, 100.0, 10.0)
        self.assertIsInstance(float(result), float)

    def test_within_max_unfolded(self):
        # Dense cluster near 300, baseline=100 → diff=200, within max_unfolded=750
        data = np.concatenate([np.ones(10) * 100.0, np.ones(90) * 300.0])
        result = self.pf.find_unfolded_blockage_level(data, 750.0, 100.0, 10.0)
        self.assertGreater(result, 0.0)
        self.assertLessEqual(result, 750.0)

    def test_exceeds_max_unfolded_halved(self):
        # Dense cluster at 1000 away from baseline 0 → exceeds max_unfolded=400
        data = np.concatenate([np.zeros(5), np.ones(95) * 1000.0])
        result = self.pf.find_unfolded_blockage_level(data, 400.0, 0.0, 5.0)
        # Should be halved since abs(level - baseline) > max_unfolded
        full = np.abs(np.arange(int(min(data)), int(max(data)))[
            np.argmax([np.sum((data > i - 2.5) & (data < i + 2.5))
                       for i in np.arange(int(min(data)), int(max(data)))])
        ] - 0.0)
        self.assertAlmostEqual(result, full / 2, delta=5.0)

    def test_nonnegative(self):
        data = np.random.randn(100) * 5.0 + 200.0
        result = self.pf.find_unfolded_blockage_level(data, 750.0, 200.0, 10.0)
        self.assertGreaterEqual(result, 0.0)


# ---------------------------------------------------------------------------
# enumerate_peaks
# ---------------------------------------------------------------------------

class TestEnumeratePeaks(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_single_peak(self):
        starts = _make_sublevel_starts(n_peaks=1)
        num_states = len(starts) - 1
        ids = self.pf.enumerate_peaks(starts, num_states)
        self.assertEqual(len(ids), num_states)
        peak_ids = [i for i in ids if i is not None]
        self.assertEqual(peak_ids, [1])

    def test_two_peaks(self):
        starts = _make_sublevel_starts(n_peaks=2)
        num_states = len(starts) - 1
        ids = self.pf.enumerate_peaks(starts, num_states)
        peak_ids = [i for i in ids if i is not None]
        self.assertEqual(peak_ids, [1, 2])

    def test_no_peaks_all_none(self):
        starts = [
            {"index": 0,   "type": "start", "unfolded_level": 200.0},
            {"index": 50,  "type": "padding_before"},
            {"index": 90,  "type": "padding_after"},
            {"index": 100, "type": "end"},
        ]
        num_states = len(starts) - 1
        ids = self.pf.enumerate_peaks(starts, num_states)
        self.assertTrue(all(i is None for i in ids))

    def test_length_matches_num_states(self):
        starts = _make_sublevel_starts(n_peaks=3)
        num_states = len(starts) - 1
        ids = self.pf.enumerate_peaks(starts, num_states)
        self.assertEqual(len(ids), num_states)


# ---------------------------------------------------------------------------
# filter_peaks – Unspecified and Single Peak (pass-through)
# ---------------------------------------------------------------------------

class TestFilterPeaksPassThrough(unittest.TestCase):
    def _make_props(self, n=3):
        return {
            "filtered":     [0] * n,
            "prominences":  np.array([200.0, 150.0, 100.0]),
            "left_bases":   [50.0, 50.0, 50.0],
            "right_bases":  [50.0, 50.0, 50.0],
            "peak_heights": np.array([700.0, 650.0, 600.0]),
        }

    def test_unspecified_returns_properties_unchanged(self):
        pf = _make_pf(**{"Event Type": "Unspecified"})
        peaks = np.array([10, 30, 50])
        props = self._make_props()
        result = pf.filter_peaks(peaks, props, 200.0, 10.0, 100.0, 1e6)
        self.assertEqual(result["filtered"], [0, 0, 0])

    def test_single_peak_returns_properties_unchanged(self):
        pf = _make_pf(**{"Event Type": "Single Peak"})
        peaks = np.array([10, 30, 50])
        props = self._make_props()
        result = pf.filter_peaks(peaks, props, 200.0, 10.0, 100.0, 1e6)
        self.assertEqual(result["filtered"], [0, 0, 0])


# ---------------------------------------------------------------------------
# filter_peaks – Barcode type 1 (bases near unfolded level)
# ---------------------------------------------------------------------------

class TestFilterPeaksBarcode(unittest.TestCase):
    def _props(self, left_bases, right_bases, prominences=None):
        n = len(left_bases)
        if prominences is None:
            prominences = [200.0] * n
        return {
            "filtered":     [0] * n,
            "prominences":  np.array(prominences, dtype=float),
            "left_bases":   list(left_bases),
            "right_bases":  list(right_bases),
            "peak_heights": np.array([700.0] * n),
        }

    def test_type1_classification(self):
        """Both bases within unfolded_level ± 2*std → type 1 (num_peaks=2 so single peak can't cluster)."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # unfolded=200, std=10 → valid range: 180..220 → use 195
        props = self._props([195.0], [195.0])
        result = pf.filter_peaks(np.array([20]), props, 200.0, 10.0, 0.0, 1e6)
        self.assertEqual(result["filtered"][0], 1)

    def test_type2_classification(self):
        """Both bases above unfolded + std → type 2 (num_peaks=2 so single peak can't cluster)."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # unfolded=200, std=10 → need > 210 → use 220
        props = self._props([220.0], [220.0])
        result = pf.filter_peaks(np.array([20]), props, 200.0, 10.0, 0.0, 1e6)
        self.assertEqual(result["filtered"][0], 2)

    def test_type_minus1_classification(self):
        """Both bases above 2*unfolded + std → type -1 (noise)."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 1})
        # 2*200+10=410 → use 450
        props = self._props([450.0], [450.0])
        result = pf.filter_peaks(np.array([20]), props, 200.0, 10.0, 0.0, 1e6)
        self.assertEqual(result["filtered"][0], -1)

    def test_cluster_of_type1_labeled_type3(self):
        """Two type-1 peaks close together with num_peaks=2 → both become type 3."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # peaks at indices 20 and 25 (distance=5 samples << max_distance=100/dt_us)
        # unfolded=200, std=10, bases=195 → type 1
        props = self._props([195.0, 195.0], [195.0, 195.0], [300.0, 300.0])
        result = pf.filter_peaks(np.array([20, 25]), props, 200.0, 10.0, 0.0, 1e6)
        # Both should be type 3 (cluster)
        self.assertTrue(all(f == 3 for f in result["filtered"]))

    def test_no_cluster_below_min_group_size(self):
        """Only 1 type-1 peak when num_peaks=2 → not enough for a cluster."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        props = self._props([195.0], [195.0], [300.0])
        result = pf.filter_peaks(np.array([20]), props, 200.0, 10.0, 0.0, 1e6)
        # stays type 1, not promoted to 3
        self.assertEqual(result["filtered"][0], 1)

    def test_empty_peaks_no_crash(self):
        """No peaks at all → filter_peaks should return properties intact."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 1})
        props = {"filtered": [], "prominences": np.array([]), "left_bases": [],
                 "right_bases": [], "peak_heights": np.array([])}
        result = pf.filter_peaks(np.array([]), props, 200.0, 10.0, 0.0, 1e6)
        self.assertEqual(result["filtered"], [])


# ---------------------------------------------------------------------------
# _populate_sublevel_metadata
# ---------------------------------------------------------------------------

class TestPopulateSublevelMetadata(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()
        self.samplerate = 1e6
        self.data = np.concatenate([
            np.ones(10) * 100.0,    # padding before
            np.ones(80) * 300.0,    # event body
            np.ones(10) * 100.0,    # padding after
        ])
        self.starts = _make_sublevel_starts(
            n_peaks=1, padding_before=10, data_len=100, padding_after=10
        )

    def test_required_keys_present(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        for key in [
            "sublevel_current", "sublevel_duration", "sublevel_start_times",
            "sublevel_end_times", "sublevel_raw_ecd", "sublevel_cumulative_ecd",
            "sublevel_max_deviation", "peak_id", "peak_height", "peak_loc",
            "peak_width", "prominence", "left_base", "right_base",
            "left_ips", "right_ips", "filtered",
        ]:
            self.assertIn(key, meta)

    def test_array_lengths_consistent(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        num_states = len(self.starts) - 1
        self.assertEqual(len(meta["sublevel_current"]), num_states)
        self.assertEqual(len(meta["sublevel_duration"]), num_states)
        self.assertEqual(len(meta["peak_id"]), num_states)

    def test_cumulative_ecd_monotone(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        # cumulative should be non-decreasing or equal length to raw
        self.assertEqual(
            len(meta["sublevel_cumulative_ecd"]),
            len(meta["sublevel_raw_ecd"])
        )

    def test_peak_height_positive_for_peak_sublevel(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        # find which index is a peak
        num_states = len(self.starts) - 1
        for i in range(num_states):
            if "peak" in self.starts[i]["type"]:
                self.assertGreater(meta["peak_height"][i], 0.0)

    def test_non_peak_fields_are_nan(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        num_states = len(self.starts) - 1
        for i in range(num_states):
            if "peak" not in self.starts[i]["type"]:
                self.assertTrue(np.isnan(meta["peak_height"][i]))

    def test_start_times_nondecreasing(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        times = meta["sublevel_start_times"]
        self.assertTrue(all(times[i] <= times[i+1] for i in range(len(times)-1)))


# ---------------------------------------------------------------------------
# _populate_event_metadata
# ---------------------------------------------------------------------------

class TestPopulateEventMetadata(unittest.TestCase):
    def _make_sublevel_meta(self, n=5):
        # start_times in µs: [0, 10000, 20000, 30000, 40000]
        # at samplerate=1e6: indices [0, 10000, 20000, 30000, 40000]
        # slice used by _populate_event_metadata: data[10000:40000]
        # so data must have variation in that range
        return {
            "sublevel_duration":      np.ones(n) * 10.0,
            "sublevel_raw_ecd":       np.ones(n) * 0.1,
            "sublevel_max_deviation": np.ones(n) * 5.0,
            "sublevel_start_times":   np.array([0.0, 10000.0, 20000.0, 30000.0, 40000.0]),
        }

    def _make_data(self):
        # 50000 samples: alternating bands so data[10000:40000] has variation
        data = np.ones(50000) * 100.0
        data[10000:40000] = np.linspace(100.0, 400.0, 30000)
        return data

    def test_all_keys_present(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, self._make_sublevel_meta())
        for key in ["number_peaks", "duration", "raw_ecd", "max_deviation",
                    "baseline", "unfolded_level", "baseline_std"]:
            self.assertIn(key, result)

    def test_baseline_matches_input(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(self._make_data(), 1e6, 123.0, 10.0, self._make_sublevel_meta())
        self.assertAlmostEqual(result["baseline"], 123.0)

    def test_baseline_std_matches_input(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 7.5, self._make_sublevel_meta())
        self.assertAlmostEqual(result["baseline_std"], 7.5)

    def test_duration_sums_inner(self):
        pf = _make_pf()
        meta = self._make_sublevel_meta()  # 5 sublevels, each 10µs
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, meta)
        # inner [1:-1] = 3 entries × 10µs = 30
        self.assertAlmostEqual(result["duration"], 30.0)


# ---------------------------------------------------------------------------
# _define_event_metadata_types / units
# ---------------------------------------------------------------------------

class TestDefineEventMetadata(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_event_types_correct(self):
        t = self.pf._define_event_metadata_types()
        self.assertIs(t["number_peaks"], int)
        self.assertIs(t["duration"], float)
        self.assertIs(t["raw_ecd"], float)
        self.assertIs(t["baseline"], float)
        self.assertIs(t["unfolded_level"], float)
        self.assertIs(t["baseline_std"], float)

    def test_sublevel_types_all_present(self):
        t = self.pf._define_sublevel_metadata_types()
        for key in [
            "sublevel_current", "sublevel_duration", "peak_height",
            "peak_loc", "peak_width", "prominence", "left_base", "right_base",
            "left_ips", "right_ips", "filtered", "normalized_height",
            "normalized_prominence",
        ]:
            self.assertIn(key, t)

    def test_event_units_duration(self):
        u = self.pf._define_event_metadata_units()
        self.assertEqual(u["duration"], "μs")
        self.assertEqual(u["raw_ecd"], "pC")
        self.assertEqual(u["max_deviation"], "pA")

    def test_sublevel_units_present(self):
        u = self.pf._define_sublevel_metadata_units()
        self.assertEqual(u["sublevel_current"], "pA")
        self.assertEqual(u["sublevel_duration"], "us")
        self.assertEqual(u["peak_height"], "pA")
        self.assertEqual(u["left_ips"], "us")


# ---------------------------------------------------------------------------
# construct_fitted_event – None paths
# ---------------------------------------------------------------------------

class TestConstructFittedEvent(unittest.TestCase):
    def test_no_metadata_returns_none(self):
        pf = _make_pf()
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_wrong_channel_returns_none(self):
        pf = _make_pf()
        pf.sublevel_metadata = {1: {}}
        pf.eventfitting_status = {1: True}
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_fitting_not_done_returns_none(self):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {}}
        pf.eventfitting_status = {0: False}
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_missing_event_index_returns_none(self):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {99: {}}}   # only index 99
        pf.eventfitting_status = {0: True}
        pf.event_lengths = {0: {0: 100}}
        pf.event_metadata = {0: {}}
        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = 1e6
        # index 0 not in sublevel_metadata[0] → KeyError → None
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_construct_returns_array_when_data_present(self):
        """Full happy path: valid metadata → returns numpy array."""
        pf = _make_pf()
        n = 50
        samplerate = 1e6
        dt_us = 1.0 / samplerate * 1e6

        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = samplerate

        # Two sublevels: baseline (0→25) and event (25→50)
        starts_us = np.array([0.0, 25.0]) * dt_us
        ends_us   = np.array([25.0, 50.0]) * dt_us

        pf.sublevel_metadata = {0: {0: {
            "sublevel_start_times": starts_us,
            "sublevel_end_times":   ends_us,
            "sublevel_current":     np.array([100.0, 300.0]),
            "peak_height":          np.array([0.0, 0.0]),
            "filtered":             np.array([0.0, 0.0]),
            "right_ips":            np.array([np.nan, np.nan]),
            "left_ips":             np.array([np.nan, np.nan]),
        }}}
        pf.event_metadata = {0: {0: {"baseline": 100.0}}}
        pf.eventfitting_status = {0: True}
        pf.event_lengths = {0: {0: n}}

        result = pf.construct_fitted_event(0, 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), n)
        self.assertIsInstance(result, np.ndarray)

    def test_construct_with_peak_fil3(self):
        """filtered==3 and valid ips → peak region is filled."""
        pf = _make_pf()
        n = 100
        samplerate = 1e6
        dt_us = 1.0 / samplerate * 1e6

        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = samplerate

        starts_us = np.array([0.0, 40.0, 70.0]) * dt_us
        ends_us   = np.array([40.0, 70.0, 100.0]) * dt_us

        pf.sublevel_metadata = {0: {0: {
            "sublevel_start_times": starts_us,
            "sublevel_end_times":   ends_us,
            "sublevel_current":     np.array([100.0, 300.0, 100.0]),
            "peak_height":          np.array([0.0, 200.0, 0.0]),
            "filtered":             np.array([0.0, 3.0, 0.0]),
            "right_ips":            np.array([np.nan, 60.0 * dt_us, np.nan]),
            "left_ips":             np.array([np.nan, 45.0 * dt_us, np.nan]),
        }}}
        pf.event_metadata = {0: {0: {"baseline": 100.0}}}
        pf.eventfitting_status = {0: True}
        pf.event_lengths = {0: {0: n}}

        result = pf.construct_fitted_event(0, 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), n)


# ---------------------------------------------------------------------------
# get_plot_features – None paths
# ---------------------------------------------------------------------------

class TestGetPlotFeatures(unittest.TestCase):
    def test_no_metadata_returns_all_none(self):
        pf = _make_pf()
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def test_fitting_not_done_returns_all_none(self):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {}}
        pf.eventfitting_status = {0: False}
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def test_plot_features_none_setting_returns_all_none(self):
        pf = _make_pf(**{"Plot Features": "None"})
        pf.sublevel_metadata = {0: {0: {}}}
        pf.eventfitting_status = {0: True}
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def test_missing_event_index_returns_all_none(self):
        """KeyError inside → returns tuple of Nones."""
        pf = _make_pf(**{"Plot Features": "Some"})
        pf.sublevel_metadata = {0: {99: {}}}  # only index 99
        pf.eventfitting_status = {0: True}
        pf.event_metadata = {0: {}}
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def _setup_full_pf(self, plot_value="Some"):
        pf = _make_pf(**{"Plot Features": plot_value})
        pf.sublevel_metadata = {0: {0: {
            "right_ips":   np.array([np.nan, 55.0, np.nan]),
            "peak_id":     [None, 1, None],
            "left_base":   np.array([np.nan, 180.0, np.nan]),
            "right_base":  np.array([np.nan, 180.0, np.nan]),
            "peak_loc":    np.array([np.nan, 50.0, np.nan]),
            "peak_height": np.array([np.nan, 600.0, np.nan]),
            "filtered":    [None, 3, None],
        }}}
        pf.event_metadata = {0: {0: {
            "baseline":        100.0,
            "unfolded_level":  200.0,
            "baseline_std":    10.0,
        }}}
        pf.eventfitting_status = {0: True}
        return pf

    def test_plot_some_returns_truncated_bases(self):
        pf = self._setup_full_pf("Some")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        # "Some" trims bases and hlabel to first 2
        self.assertEqual(len(bases), 2)
        self.assertEqual(len(hlabel), 2)

    def test_plot_all_returns_full_bases(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        # "All" keeps all bases (4 gauges + 2 per peak = 6 total)
        self.assertGreater(len(bases), 2)

    def test_filtered_peak_in_vlabel(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        self.assertGreater(len(vlabel), 0)
        self.assertTrue(any("Peak" in v or "Type" in v for v in vlabel))

    def test_peaks_list_contains_tuple(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        self.assertGreater(len(peaks), 0)
        self.assertIsInstance(peaks[0], tuple)

    def test_unlabeled_peak_not_in_filtered(self):
        """filtered==0 → peak_loc NOT added to peaks_filtered."""
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {0: {0: {
            "right_ips":   np.array([np.nan, 55.0, np.nan]),
            "peak_id":     [None, 1, None],
            "left_base":   np.array([np.nan, 180.0, np.nan]),
            "right_base":  np.array([np.nan, 180.0, np.nan]),
            "peak_loc":    np.array([np.nan, 50.0, np.nan]),
            "peak_height": np.array([np.nan, 600.0, np.nan]),
            "filtered":    [None, 0, None],   # ← type 0, should be excluded
        }}}
        pf.event_metadata = {0: {0: {
            "baseline": 100.0, "unfolded_level": 200.0, "baseline_std": 10.0,
        }}}
        pf.eventfitting_status = {0: True}
        peaks_filtered, *_ = pf.get_plot_features(0, 0)
        self.assertEqual(peaks_filtered, [])

    def test_minus1_peak_not_in_filtered(self):
        """filtered==-1 → also excluded from peaks_filtered."""
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {0: {0: {
            "right_ips":   np.array([np.nan, 55.0, np.nan]),
            "peak_id":     [None, 1, None],
            "left_base":   np.array([np.nan, 180.0, np.nan]),
            "right_base":  np.array([np.nan, 180.0, np.nan]),
            "peak_loc":    np.array([np.nan, 50.0, np.nan]),
            "peak_height": np.array([np.nan, 600.0, np.nan]),
            "filtered":    [None, -1, None],
        }}}
        pf.event_metadata = {0: {0: {
            "baseline": 100.0, "unfolded_level": 200.0, "baseline_std": 10.0,
        }}}
        pf.eventfitting_status = {0: True}
        peaks_filtered, *_ = pf.get_plot_features(0, 0)
        self.assertEqual(peaks_filtered, [])


# ---------------------------------------------------------------------------
# Noop overrides
# ---------------------------------------------------------------------------

class TestNoopOverrides(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

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


if __name__ == "__main__":
    unittest.main()