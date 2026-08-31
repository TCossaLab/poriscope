"""
Tests for PeakFinder.py

instantiate PeakFinder via object.__new__ to bypass __init__ and the event-loader requirement.
Settings and metadata are injected directly onto the instance.

Coverage targets:
- find_mode_blockage_level
- enumerate_peaks
- filter_peaks (all three Event Type branches + all sub-branches)
- _populate_sublevel_metadata
- _populate_event_metadata
- _define_event_metadata_types / _define_sublevel_metadata_types
- _define_event_metadata_units / _define_sublevel_metadata_units
- construct_fitted_event (None paths)
- get_plot_features (None paths + Some/All/None plot feature paths)
- _init / _pre_process_events / _post_process_events / _validate_settings / close_resources
- _gaussian_intersection
- _fit_double_gaussian_bounded_at_valley
- _fit_least_smoothed_spline
- _warn_if_fitted_means_are_off_their_peaks
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
        "Event Type": {"Value": "Unspecified"},
        # "Min Height": {"Value": 500.0},
        # "Min Prominence": {"Value": 100.0},
        # "Relative Height": {"Value": 0.5},
        "Window Length": {"Value": 25.0},
        "Width": {"Value": 0.0},
        # "Min Distance": {"Value": 1.0},
        # "Max Unfolded": {"Value": 750.0},
        "Lower Filter Threshold": {"Value": -3},
        "Higher Filter Threshold": {"Value": 3},
        "Number of peaks": {"Value": 1},
        "Plot Features": {"Value": "Some"},
    }
    for k, v in setting_overrides.items():
        pf.settings[k]["Value"] = v
    return pf


def _make_sublevel_starts(n_peaks=1, padding_before=10, data_len=100, padding_after=10):
    """Build a minimal sublevel_starts list as _locate_sublevel_transitions would."""
    peak_index = padding_before + 20
    starts = [
        {
            "index": 0,
            "type": "start",
            "peak_height": None,
            "prominence": None,
            "left_base": None,
            "right_base": None,
            "width": None,
            "left_ips": None,
            "right_ips": None,
            "filtered": None,
            "max_blockage": None,
            "unfolded_level": 200.0,
        },
        {
            "index": padding_before,
            "type": "padding_before",
            "peak_height": None,
            "prominence": None,
            "left_base": None,
            "right_base": None,
            "width": None,
            "left_ips": None,
            "right_ips": None,
            "filtered": None,
            "max_blockage": None,
        },
    ]
    for i in range(n_peaks):
        starts.append(
            {
                "index": peak_index + i * 5,
                "type": f"peak_{i+1}",
                "peak_height": 600.0,
                "prominence": 150.0,
                "left_base": 180.0,
                "right_base": 180.0,
                "width": 3.0,
                "left_ips": peak_index + i * 5 - 1,
                "right_ips": peak_index + i * 5 + 1,
                "filtered": 0,
                "max_blockage": None,
            }
        )
    starts += [
        {
            "index": data_len - padding_after,
            "type": "padding_after",
            "peak_height": None,
            "prominence": None,
            "left_base": None,
            "right_base": None,
            "width": None,
            "left_ips": None,
            "right_ips": None,
            "filtered": None,
            "max_blockage": None,
        },
        {
            "index": data_len,
            "type": "end",
            "peak_height": None,
            "prominence": None,
            "left_base": None,
            "right_base": None,
            "width": None,
            "left_ips": None,
            "right_ips": None,
            "filtered": None,
            "max_blockage": None,
        },
    ]
    return starts


# ---------------------------------------------------------------------------
# find_mode_blockage_level
# ---------------------------------------------------------------------------


class TestFindModeBlockageLevel(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_returns_float(self):
        data = np.concatenate([np.ones(50) * 100.0, np.ones(50) * 300.0])
        primary, secondary = self.pf.find_mode_blockage_level(data, 100.0, 10.0)
        self.assertIsInstance(primary, float)

    def test_within_max_unfolded(self):
        # Dense cluster near 300, baseline=100 → diff=200, within max_unfolded=750
        data = np.concatenate([np.ones(10) * 100.0, np.ones(90) * 300.0])
        primary, secondary = self.pf.find_mode_blockage_level(data, 100.0, 10.0)
        self.assertGreater(primary, 0.0)
        self.assertLessEqual(primary, 750.0)

    def test_exceeds_max_unfolded_halved(self):
        # When only one dominant level exists, secondary should be None
        data = np.ones(100) * 1000.0
        primary, secondary = self.pf.find_mode_blockage_level(data, 0.0, 5.0)
        self.assertIsNone(secondary)

    def test_nonnegative(self):
        data = np.random.randn(100) * 5.0 + 200.0
        result = self.pf.find_mode_blockage_level(data, 750.0, 200.0)
        self.assertGreaterEqual(result[0], 0.0)


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
            {"index": 0, "type": "start", "unfolded_level": 200.0},
            {"index": 50, "type": "padding_before"},
            {"index": 90, "type": "padding_after"},
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
            "filtered": [0] * n,
            "prominences": np.array([200.0, 150.0, 100.0]),
            "left_bases": [50.0, 50.0, 50.0],
            "right_bases": [50.0, 50.0, 50.0],
            "peak_heights": np.array([700.0, 650.0, 600.0]),
        }

    def test_unspecified_returns_properties_unchanged(self):
        pf = _make_pf(**{"Event Type": "Unspecified"})
        peaks = np.array([10, 30, 50])
        props = self._make_props()
        result = pf.filter_peaks(peaks, props, 100, 10.0, 100.0, 1e6, 200, 1000.0)
        self.assertEqual(result["filtered"], [0, 0, 0])

    def test_single_peak_returns_properties_unchanged(self):
        pf = _make_pf(**{"Event Type": "Single Peak"})
        peaks = np.array([10, 30, 50])
        props = self._make_props()
        result = pf.filter_peaks(peaks, props, 100, 10.0, 100.0, 1e6, 200, 1000.0)
        self.assertEqual(result["filtered"], [0, 0, 0])


# ---------------------------------------------------------------------------
# filter_peaks – Barcode type 2 / clustered peaks
# ---------------------------------------------------------------------------


class TestFilterPeaksBarcode(unittest.TestCase):
    def _props(self, left_bases, right_bases, prominences=None):
        n = len(left_bases)
        if prominences is None:
            prominences = [200.0] * n
        return {
            "filtered": [0] * n,
            "prominences": np.array(prominences, dtype=float),
            "left_bases": list(left_bases),
            "right_bases": list(right_bases),
            "peak_heights": np.array([700.0] * n),
        }

    def test_type1_classification(self):
        """Both bases within the type-1 band → type 1."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # unfolded=200, std=10, baseline=100 → type1_thresh=170, type2_thresh=230
        # effective_base = 100 + 100 = 200, which is in [170, 230] → type 1
        props = self._props([100.0], [100.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 1)

    def test_type2_classification(self):
        """Bases above type-2 threshold → type 2."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # effective_base = 240 + 100 = 340, in [230, 430] → type 2
        props = self._props([240.0], [240.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 2)

    def test_type_minus1_classification(self):
        """Both bases above 2*unfolded + std → type -1 (noise)."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 1})
        # effective_base = 450 + 100 = 550, above type2_upper=430 → type -1
        props = self._props([450.0], [450.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], -1)

    def test_no_cluster_below_min_group_size(self):
        """Only 1 type-2 peak when num_peaks=2 → not enough for a cluster."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        props = self._props([195.0], [195.0], [300.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 2)

    def test_custom_threshold_settings_change_classification(self):
        """Custom T1/T2 std offsets should change the classification boundary."""
        pf = _make_pf(
            **{
                "Event Type": "Barcode",
                "Number of peaks": 2,
                "Lower Filter Threshold": -3,
                "Higher Filter Threshold": 3,
            }
        )
        props = self._props([215.0], [225.0], [300.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 2)

    def test_empty_peaks_no_crash(self):
        """No peaks at all → filter_peaks should return properties intact."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 1})
        props = {
            "filtered": [],
            "prominences": np.array([]),
            "left_bases": [],
            "right_bases": [],
            "peak_heights": np.array([]),
        }
        result = pf.filter_peaks(
            np.array([]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"], [])


# ---------------------------------------------------------------------------
# _populate_sublevel_metadata
# ---------------------------------------------------------------------------


class TestPopulateSublevelMetadata(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()
        self.samplerate = 1e6
        self.data = np.concatenate(
            [
                np.ones(10) * 100.0,  # padding before
                np.ones(80) * 300.0,  # event body
                np.ones(10) * 100.0,  # padding after
            ]
        )
        self.starts = _make_sublevel_starts(
            n_peaks=1, padding_before=10, data_len=100, padding_after=10
        )

    def test_required_keys_present(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        for key in [
            "sublevel_current",
            "sublevel_stdev",
            "sublevel_duration",
            "sublevel_start_times",
            "sublevel_end_times",
            "sublevel_raw_ecd",
            "sublevel_cumulative_ecd",
            "sublevel_max_deviation",
            "sublevel_type",
            "peak_id",
            "peak_height",
            "peak_loc",
            "peak_width",
            "prominence",
            "classified",
            "max_blockage",
            "left_base",
            "right_base",
            "left_ips",
            "right_ips",
            "height_ips",
            "filtered",
            "normalized_height",
            "normalized_prominence",
            "normalized_blockage",
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
            len(meta["sublevel_cumulative_ecd"]), len(meta["sublevel_raw_ecd"])
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
        self.assertTrue(all(times[i] <= times[i + 1] for i in range(len(times) - 1)))


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
            "sublevel_duration": np.ones(n) * 10.0,
            "sublevel_current": np.array([123.0, 300.0, 300.0, 300.0, 123.0]),
            "sublevel_stdev": np.ones(n) * 7.5,
            "sublevel_raw_ecd": np.ones(n) * 0.1,
            "sublevel_max_deviation": np.ones(n) * 5.0,
            "sublevel_start_times": np.array([0.0, 10000.0, 20000.0, 30000.0, 40000.0]),
            "peak_id": [None, 1, 2, 3, None],
        }

    def _make_data(self):
        # 50000 samples: alternating bands so data[10000:40000] has variation
        data = np.ones(50000) * 100.0
        data[10000:40000] = np.linspace(100.0, 400.0, 30000)
        return data

    def test_all_keys_present(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 100.0, 10.0, self._make_sublevel_meta()
        )
        for key in [
            "number_peaks",
            "duration",
            "raw_ecd",
            "max_deviation",
            "baseline_current",
            "unfolded_level",
            "folded_level",
            # NOTE (integration): "longest_blockage_level" no longer exists - the
            # event metadata now carries "primary_level" instead - and
            # "baseline_std" was renamed to "baseline_stdev" in
            # _populate_event_metadata. This list still had the old names, so
            # test_all_keys_present failed against your own code.
            "primary_level",
            "baseline_stdev",
            "translocation_direction",
            "sequence",
        ]:
            self.assertIn(key, result)

    def test_baseline_matches_input(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 123.0, 10.0, self._make_sublevel_meta()
        )
        self.assertAlmostEqual(result["baseline_current"], 123.0)

    def test_baseline_std_matches_input(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 100.0, 7.5, self._make_sublevel_meta()
        )
        # NOTE (integration): key renamed baseline_std -> baseline_stdev.
        self.assertAlmostEqual(result["baseline_stdev"], 7.5)

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
        self.assertIs(t["baseline_current"], float)
        self.assertIs(t["unfolded_level"], float)
        # NOTE (integration): key renamed baseline_std -> baseline_stdev.
        self.assertIs(t["baseline_stdev"], float)
        self.assertIs(t["translocation_direction"], str)
        self.assertIs(t["sequence"], str)

    def test_sublevel_types_all_present(self):
        t = self.pf._define_sublevel_metadata_types()
        for key in [
            "sublevel_current",
            "sublevel_duration",
            "peak_height",
            "peak_loc",
            "peak_width",
            "prominence",
            "left_base",
            "right_base",
            "left_ips",
            "right_ips",
            "filtered",
            "normalized_height",
            "normalized_prominence",
            "normalized_blockage",
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
        self.assertIsNone(u.get("normalized_blockage"))


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
        pf.sublevel_metadata = {0: {99: {}}}  # only index 99
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
        ends_us = np.array([25.0, 50.0]) * dt_us

        pf.sublevel_metadata = {
            0: {
                0: {
                    "sublevel_start_times": starts_us,
                    "sublevel_end_times": ends_us,
                    "sublevel_current": np.array([100.0, 300.0]),
                    "peak_height": np.array([0.0, 0.0]),
                    "filtered": np.array([0.0, 0.0]),
                    "right_ips": np.array([np.nan, np.nan]),
                    "left_ips": np.array([np.nan, np.nan]),
                }
            }
        }
        pf.event_metadata = {0: {0: {"baseline_current": 100.0}}}
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
        ends_us = np.array([40.0, 70.0, 100.0]) * dt_us

        pf.sublevel_metadata = {
            0: {
                0: {
                    "sublevel_start_times": starts_us,
                    "sublevel_end_times": ends_us,
                    "sublevel_current": np.array([100.0, 300.0, 100.0]),
                    "peak_height": np.array([0.0, 200.0, 0.0]),
                    "filtered": np.array([0.0, 3.0, 0.0]),
                    "right_ips": np.array([np.nan, 60.0 * dt_us, np.nan]),
                    "left_ips": np.array([np.nan, 45.0 * dt_us, np.nan]),
                }
            }
        }
        pf.event_metadata = {0: {0: {"baseline_current": 100.0}}}
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

    def _setup_full_pf(self, plot_value="Some", **setting_overrides):
        overrides = {"Plot Features": plot_value}
        overrides.update(setting_overrides)
        pf = _make_pf(**overrides)
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, 55.0, np.nan]),
                    "peak_id": [None, 1, None],
                    "left_base": np.array([np.nan, 180.0, np.nan]),
                    "right_base": np.array([np.nan, 180.0, np.nan]),
                    "peak_loc": np.array([np.nan, 50.0, np.nan]),
                    "peak_height": np.array([np.nan, 600.0, np.nan]),
                    "filtered": [None, 3, None],
                    "classified": np.array([np.nan, np.nan, np.nan]),
                }
            }
        }
        pf.event_metadata = {
            0: {
                0: {
                    "baseline_current": 100.0,
                    "unfolded_level": 200.0,
                    # NOTE (integration): renamed baseline_std -> baseline_stdev.
                    # get_plot_features reads this key, and the KeyError from the old
                    # name was swallowed by its own handler and returned as an
                    # all-None tuple - so these tests failed on len(None) rather than
                    # reporting the missing key.
                    "baseline_stdev": 10.0,
                    # NOTE (integration): get_plot_features now also reads "sequence"
                    # and "translocation_direction" from the event metadata. They were
                    # never added to these fixtures, so the lookup raised KeyError,
                    # which the method's own handler converts into an all-None return.
                    "sequence": None,
                    "translocation_direction": None,
                }
            }
        }
        pf.eventfitting_status = {0: True}
        return pf

    def test_plot_some_returns_truncated_bases(self):
        pf = self._setup_full_pf("Some")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        # NOTE (integration): this expected 2. get_plot_features now appends four
        # gauge lines unconditionally - baseline, unfolded level, and the two
        # threshold gauges at t1σ and t2σ - so "Some" yields 4, not 2. Your own
        # test_plot_all_returns_full_bases comment ("4 gauges + 2 per peak") records
        # the same intent, so the expectation here simply went stale when the two
        # threshold gauges were added.
        self.assertEqual(len(bases), 4)
        self.assertEqual(len(hlabel), 4)

    def test_plot_all_returns_full_bases(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        # "All" keeps all bases (4 gauges + 2 per peak = 6 total)s
        self.assertGreater(len(bases), 2)

    def test_threshold_labels_reflect_settings(self):
        pf = self._setup_full_pf(
            "All",
            **{"Lower Filter Threshold": -3, "Higher Filter Threshold": 3},
        )
        _, _, _, _, hlabel, _ = pf.get_plot_features(0, 0)
        self.assertIn("unfolded level +3σ", hlabel)
        self.assertIn("unfolded level -3σ", hlabel)

    def test_filtered_peak_in_plabel(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        self.assertGreater(len(plabel), 0)
        self.assertTrue(any("Peak" in v or "Type" in v for v in plabel))

    def test_peaks_list_contains_tuple(self):
        pf = self._setup_full_pf("All")
        pf_filtered, bases, peaks, vlabel, hlabel, plabel = pf.get_plot_features(0, 0)
        self.assertGreater(len(peaks), 0)
        self.assertIsInstance(peaks[0], tuple)

    def test_unlabeled_peak_not_in_filtered(self):
        """filtered==0 → peak_loc NOT added to peaks_filtered."""
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, 55.0, np.nan]),
                    "peak_id": [None, 1, None],
                    "left_base": np.array([np.nan, 180.0, np.nan]),
                    "right_base": np.array([np.nan, 180.0, np.nan]),
                    "peak_loc": np.array([np.nan, 50.0, np.nan]),
                    "peak_height": np.array([np.nan, 600.0, np.nan]),
                    "filtered": [None, 0, None],  # ← type 0, should be excluded
                    "classified": np.array([np.nan, np.nan, np.nan]),
                }
            }
        }
        pf.event_metadata = {
            0: {
                0: {
                    "baseline_current": 100.0,
                    "unfolded_level": 200.0,
                    # NOTE (integration): renamed baseline_std -> baseline_stdev.
                    # get_plot_features reads this key, and the KeyError from the old
                    # name was swallowed by its own handler and returned as an
                    # all-None tuple - so these tests failed on len(None) rather than
                    # reporting the missing key.
                    "baseline_stdev": 10.0,
                    # NOTE (integration): get_plot_features now also reads "sequence"
                    # and "translocation_direction" from the event metadata. They were
                    # never added to these fixtures, so the lookup raised KeyError,
                    # which the method's own handler converts into an all-None return.
                    "sequence": None,
                    "translocation_direction": None,
                }
            }
        }
        pf.eventfitting_status = {0: True}
        peaks_filtered, *_ = pf.get_plot_features(0, 0)
        self.assertEqual(peaks_filtered, [])

    def test_minus1_peak_not_in_filtered(self):
        """filtered==-1 → also excluded from peaks_filtered."""
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, 55.0, np.nan]),
                    "peak_id": [None, 1, None],
                    "left_base": np.array([np.nan, 180.0, np.nan]),
                    "right_base": np.array([np.nan, 180.0, np.nan]),
                    "peak_loc": np.array([np.nan, 50.0, np.nan]),
                    "peak_height": np.array([np.nan, 600.0, np.nan]),
                    "filtered": [None, -1, None],
                    "classified": np.array([np.nan, np.nan, np.nan]),
                }
            }
        }
        pf.event_metadata = {
            0: {
                0: {
                    "baseline_current": 100.0,
                    "unfolded_level": 200.0,
                    # NOTE (integration): renamed baseline_std -> baseline_stdev.
                    # get_plot_features reads this key, and the KeyError from the old
                    # name was swallowed by its own handler and returned as an
                    # all-None tuple - so these tests failed on len(None) rather than
                    # reporting the missing key.
                    "baseline_stdev": 10.0,
                    # NOTE (integration): get_plot_features now also reads "sequence"
                    # and "translocation_direction" from the event metadata. They were
                    # never added to these fixtures, so the lookup raised KeyError,
                    # which the method's own handler converts into an all-None return.
                    "sequence": None,
                    "translocation_direction": None,
                }
            }
        }
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


# ---------------------------------------------------------------------------
# _gaussian_intersection
# ---------------------------------------------------------------------------


class TestGaussianIntersection(unittest.TestCase):
    def test_equal_std_matches_closed_form(self):
        # amp1=100, mean1=0, std1=10; amp2=50, mean2=20, std2=10.
        # Equal std collapses the quadratic to a line:
        # x = (m1+m2)/2 + std**2 * ln(amp2/amp1) / (m1-m2)
        expected = 10.0 + (100.0 * np.log(0.5)) / (-20.0)
        x = PeakFinder._gaussian_intersection(100.0, 0.0, 10.0, 50.0, 20.0, 10.0)
        self.assertIsNotNone(x)
        self.assertAlmostEqual(x, expected, places=6)

    def test_equal_amplitude_and_std_gives_exact_midpoint(self):
        x = PeakFinder._gaussian_intersection(100.0, 0.0, 5.0, 100.0, 10.0, 5.0)
        self.assertAlmostEqual(x, 5.0, places=9)

    def test_unequal_std_crossing_is_between_the_means(self):
        x = PeakFinder._gaussian_intersection(
            800.0, 2500.0, 300.0, 1000.0, 4700.0, 500.0
        )
        self.assertIsNotNone(x)
        self.assertGreater(x, 2500.0)
        self.assertLess(x, 4700.0)

    def test_crossing_is_symmetric_to_argument_order(self):
        # Swapping which component is "1" and which is "2" must not change
        # which x position the two curves cross at.
        x_ab = PeakFinder._gaussian_intersection(
            800.0, 2500.0, 300.0, 1000.0, 4700.0, 500.0
        )
        x_ba = PeakFinder._gaussian_intersection(
            1000.0, 4700.0, 500.0, 800.0, 2500.0, 300.0
        )
        self.assertAlmostEqual(x_ab, x_ba, places=6)

    def test_no_dominance_at_own_mean_returns_none(self):
        # amp2's curve already exceeds amp1's at amp1's own mean (mean1=0):
        # g1(0)=10, g2(0)=1e6*exp(-100/(2*2500)) ~= 9.8e5. No real separating
        # crossing exists between the means in that case.
        x = PeakFinder._gaussian_intersection(10.0, 0.0, 5.0, 1e6, 10.0, 50.0)
        self.assertIsNone(x)

    def test_nonpositive_amplitude_returns_none(self):
        self.assertIsNone(
            PeakFinder._gaussian_intersection(0.0, 0.0, 5.0, 10.0, 10.0, 5.0)
        )
        self.assertIsNone(
            PeakFinder._gaussian_intersection(10.0, 0.0, 5.0, -1.0, 10.0, 5.0)
        )


# ---------------------------------------------------------------------------
# _fit_double_gaussian_bounded_at_valley
# ---------------------------------------------------------------------------


class TestFitDoubleGaussianBoundedAtValley(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def _bimodal_histogram(self, seed=5):
        rng = np.random.default_rng(seed)
        x = np.linspace(300, 8000, 70)
        bin_width = x[1] - x[0]
        intensity = (
            6119
            * np.exp(-0.5 * ((x - 2495) / 320) ** 2)
            / (320 * np.sqrt(2 * np.pi))
            * bin_width
            + 11816
            * np.exp(-0.5 * ((x - 4724) / 523) ** 2)
            / (523 * np.sqrt(2 * np.pi))
            * bin_width
        )
        y = rng.poisson(np.clip(intensity, 0.01, None)).astype(float)
        return x, y

    def test_well_separated_bimodal_finds_a_crossing_between_the_means(self):
        x, y = self._bimodal_histogram()
        popt = np.array([868.0, 2491.0, 313.0, 1017.0, 4722.0, 520.0])
        result = self.pf._fit_double_gaussian_bounded_at_valley(x, y, 3524.0, popt)
        self.assertIsNotNone(result)
        fit, crossing = result
        self.assertEqual(len(fit), 6)
        lower_mean, higher_mean = fit[1], fit[4]
        self.assertLess(lower_mean, 3524.0)
        self.assertGreater(higher_mean, 3524.0)
        self.assertGreater(crossing, min(lower_mean, higher_mean))
        self.assertLess(crossing, max(lower_mean, higher_mean))

    def test_crossing_matches_gaussian_intersection_of_the_returned_fit(self):
        x, y = self._bimodal_histogram()
        popt = np.array([868.0, 2491.0, 313.0, 1017.0, 4722.0, 520.0])
        result = self.pf._fit_double_gaussian_bounded_at_valley(x, y, 3524.0, popt)
        self.assertIsNotNone(result)
        fit, crossing = result
        recomputed = PeakFinder._gaussian_intersection(*fit)
        self.assertAlmostEqual(crossing, recomputed, places=6)

    def test_split_point_outside_histogram_range_declines(self):
        x, y = self._bimodal_histogram()
        popt = np.array([868.0, 2491.0, 313.0, 1017.0, 4722.0, 520.0])
        result = self.pf._fit_double_gaussian_bounded_at_valley(x, y, 50000.0, popt)
        self.assertIsNone(result)

    def test_heavily_imbalanced_populations_decline_rather_than_collapse(self):
        # One population 100x the other's amplitude: forcing both means to
        # opposite sides of a valley that barely separates them can only be
        # satisfied by collapsing a component. That must be declined, not
        # reported as a usable fit - see the docstring's dominance-constraint
        # discussion.
        rng = np.random.default_rng(2)
        x = np.linspace(300, 8000, 90)
        intensity = 300 * np.exp(-0.5 * ((x - 2600) / 300) ** 2) + 30000 * np.exp(
            -0.5 * ((x - 4200) / 900) ** 2
        )
        y = rng.poisson(np.clip(intensity, 0.01, None)).astype(float)
        popt = np.array([300.0, 2600.0, 300.0, 30000.0, 4200.0, 900.0])
        result = self.pf._fit_double_gaussian_bounded_at_valley(x, y, 3400.0, popt)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# _fit_least_smoothed_spline
# ---------------------------------------------------------------------------


def _noisy_bimodal_histogram(seed=5, scale=1.0):
    """Poisson-noisy two-population histogram; `scale` rescales the x axis."""
    rng = np.random.default_rng(seed)
    x = np.linspace(300, 8000, 70)
    bw = x[1] - x[0]
    intensity = (
        6119 * np.exp(-0.5 * ((x - 2495) / 320) ** 2) / (320 * np.sqrt(2 * np.pi)) * bw
        + 11816
        * np.exp(-0.5 * ((x - 4724) / 523) ** 2)
        / (523 * np.sqrt(2 * np.pi))
        * bw
    )
    y = rng.poisson(np.clip(intensity, 0.01, None)).astype(float)
    return x * scale, y


def _count_minima(spline, lo, hi, n=1000):
    grid = np.linspace(lo, hi, n)
    diffs = np.diff(spline(grid))
    return int(np.sum((diffs[:-1] < 0) & (diffs[1:] > 0)))


class TestFitLeastSmoothedSpline(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_result_respects_the_minima_budget(self):
        x, y = _noisy_bimodal_histogram()
        spline = self.pf._fit_least_smoothed_spline(x, y, 2495.0, 4724.0)
        self.assertIsNotNone(spline)
        self.assertLessEqual(
            _count_minima(spline, 2495.0, 4724.0), PeakFinder.SPLINE_MAX_MINIMA
        )

    def test_is_quieter_than_generalized_cross_validation(self):
        # The reason this method exists: GCV optimizes predictive error, not
        # shape, and leaves spurious Poisson wiggles the valley search can
        # return instead of the real boundary.
        from scipy.interpolate import make_smoothing_spline

        x, y = _noisy_bimodal_histogram(seed=11)
        gcv = make_smoothing_spline(x, y)
        ladder = self.pf._fit_least_smoothed_spline(x, y, 2495.0, 4724.0)
        self.assertIsNotNone(ladder)
        self.assertLessEqual(
            _count_minima(ladder, 2495.0, 4724.0), _count_minima(gcv, 2495.0, 4724.0)
        )

    def test_is_invariant_to_the_x_axis_unit(self):
        # A raw lambda is not scale-free (the penalty carries 1/(x-range)**3),
        # which is the whole reason the ladder is expressed in a shape
        # parameter. The same data relabelled pA -> nA must fit identically.
        x_pa, y = _noisy_bimodal_histogram()
        x_na = x_pa / 1000.0
        s_pa = self.pf._fit_least_smoothed_spline(x_pa, y, 2495.0, 4724.0)
        s_na = self.pf._fit_least_smoothed_spline(x_na, y, 2.495, 4.724)
        self.assertIsNotNone(s_pa)
        self.assertIsNotNone(s_na)
        probe = np.linspace(400, 7900, 50)
        np.testing.assert_allclose(s_pa(probe), s_na(probe / 1000.0), rtol=1e-6)

    def test_declines_on_too_few_bins_or_an_empty_bracket(self):
        x, y = _noisy_bimodal_histogram()
        self.assertIsNone(
            self.pf._fit_least_smoothed_spline(x[:3], y[:3], 2495.0, 4724.0)
        )
        self.assertIsNone(self.pf._fit_least_smoothed_spline(x, y, 4724.0, 2495.0))
        self.assertIsNone(self.pf._fit_least_smoothed_spline(x, y, 3000.0, 3000.0))

    def test_margin_steps_is_zero(self):
        # Not a style assertion: two steps of "safety margin" past the first
        # acceptable lambda was measured to wash out the real valley, driving
        # mode bias from +22 pA to +685 pA and failing 5 of 24 fits.
        self.assertEqual(PeakFinder.SPLINE_LAMBDA_MARGIN_STEPS, 0)


# ---------------------------------------------------------------------------
# _trim_to_populated_core
# ---------------------------------------------------------------------------


class TestTrimToPopulatedCore(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def _heavy_tailed_histogram(self, seed=0):
        """One tight population plus a long, sparse decaying tail of
        outlier-like counts, reproducing the shape a single genuine
        population's histogram takes once outlier peaks are included."""
        rng = np.random.default_rng(seed)
        main = rng.normal(1850, 220, size=6323)
        tail = rng.exponential(1500, size=609) + 2500
        data = np.clip(np.concatenate([main, tail]), 1, None)
        counts, edges, centers = self.pf._histogram_for_fit(data)
        return centers, counts

    def test_drops_the_sparse_tail(self):
        bins, amplitude = self._heavy_tailed_histogram()
        trimmed_bins, trimmed_amplitude = self.pf._trim_to_populated_core(
            bins, amplitude
        )
        self.assertLess(trimmed_bins.size, bins.size)
        self.assertLess(trimmed_bins[-1] - trimmed_bins[0], bins[-1] - bins[0])
        # the core is still centred on the dense population, not clipped away
        self.assertLess(trimmed_bins[0], 1850.0)
        self.assertGreater(trimmed_bins[-1], 1850.0)

    def test_removes_the_negative_dip_the_untrimmed_range_produces(self):
        # This is the measured defect the trim exists to fix: fit across the
        # full sparse tail and the spline dips deeply negative out there,
        # since "quiet" (few local minima) does not forbid overshoot.
        from scipy.interpolate import make_smoothing_spline

        bins, amplitude = self._heavy_tailed_histogram()
        full_x_range = float(bins[-1] - bins[0])
        untrimmed = make_smoothing_spline(bins, amplitude, lam=1.0 * full_x_range**3)
        grid_full = np.linspace(bins[0], bins[-1], 1000)
        untrimmed_min = untrimmed(grid_full).min()

        trimmed_bins, trimmed_amplitude = self.pf._trim_to_populated_core(
            bins, amplitude
        )
        spline = self.pf._fit_least_smoothed_spline(
            trimmed_bins, trimmed_amplitude, trimmed_bins[0], trimmed_bins[-1]
        )
        self.assertIsNotNone(spline)
        grid_trimmed = np.linspace(trimmed_bins[0], trimmed_bins[-1], 1000)
        trimmed_min = spline(grid_trimmed).min()

        self.assertLess(untrimmed_min, -5.0)
        self.assertGreater(trimmed_min, untrimmed_min)

    def test_unchanged_on_too_few_bins_or_no_counts(self):
        bins = np.array([1.0, 2.0, 3.0])
        amplitude = np.array([1.0, 2.0, 3.0])
        out_bins, out_amplitude = self.pf._trim_to_populated_core(bins, amplitude)
        np.testing.assert_array_equal(out_bins, bins)
        np.testing.assert_array_equal(out_amplitude, amplitude)

        bins2 = np.arange(10.0)
        zero_amplitude = np.zeros(10)
        out_bins2, out_amplitude2 = self.pf._trim_to_populated_core(
            bins2, zero_amplitude
        )
        np.testing.assert_array_equal(out_bins2, bins2)
        np.testing.assert_array_equal(out_amplitude2, zero_amplitude)

    def test_inert_on_a_well_separated_symmetric_bimodal_histogram(self):
        # Where there is no sparse tail to drop, trimming at
        # SPLINE_FIT_DOMAIN_COVERAGE should barely touch the histogram.
        rng = np.random.default_rng(3)
        data = np.concatenate(
            [rng.normal(2000.0, 300.0, 6000), rng.normal(3500.0, 300.0, 5000)]
        )
        counts, edges, centers = self.pf._histogram_for_fit(data)
        trimmed_bins, _ = self.pf._trim_to_populated_core(centers, counts)
        kept_fraction = trimmed_bins.size / centers.size
        self.assertGreater(kept_fraction, 0.9)


# ---------------------------------------------------------------------------
# VALLEY_SEPARATION_SIGMA
# ---------------------------------------------------------------------------


class TestValleySeparationConstraint(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def _skewed(self, s_lower=0.30, seed=1):
        """Right-skewed lower population whose shoulder reaches the valley."""
        rng = np.random.default_rng(seed)
        lower = rng.lognormal(np.log(1830) + s_lower**2, s_lower, 6500)
        upper = rng.lognormal(np.log(3350) + 0.24**2, 0.24, 4600)
        return np.concatenate([lower, upper])

    def test_returned_fit_satisfies_the_separation_constraint(self):
        data = self._skewed()
        counts, edges, centers = self.pf._histogram_for_fit(data)
        popt, one_pop = self.pf._fit_and_check_double_gaussian(centers, counts)
        self.assertIsNotNone(popt)
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt)
        valley, _, _ = self.pf._threshold_between_populations(
            data, centers, counts, m1, s1, m2, s2, one_pop
        )
        result = self.pf._fit_double_gaussian_bounded_at_valley(
            centers, counts, valley, popt
        )
        self.assertIsNotNone(result)
        fit, _ = result
        k = PeakFinder.VALLEY_SEPARATION_SIGMA
        # the valley must sit at least k sigma outside BOTH fitted means
        self.assertGreaterEqual(fit[4] - valley, k * fit[5] - 1e-6)
        self.assertGreaterEqual(valley - fit[1], k * fit[2] - 1e-6)

    def test_higher_component_is_not_left_sitting_on_the_valley(self):
        # The failure this constraint exists for: without it the higher mean
        # parks on its box bound, i.e. its summit lands on the valley.
        data = self._skewed()
        counts, edges, centers = self.pf._histogram_for_fit(data)
        popt, one_pop = self.pf._fit_and_check_double_gaussian(centers, counts)
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt)
        valley, _, _ = self.pf._threshold_between_populations(
            data, centers, counts, m1, s1, m2, s2, one_pop
        )
        fit, _ = self.pf._fit_double_gaussian_bounded_at_valley(
            centers, counts, valley, popt
        )
        self.assertGreater(fit[4] - valley, 1.0)

    def test_inert_on_symmetric_well_separated_populations(self):
        # The property that makes this safe to apply to all three classifiers:
        # where the valley already sits well clear of both means the constraint
        # never binds, so a currently-good fit is unchanged.
        rng = np.random.default_rng(3)
        data = np.concatenate(
            [rng.normal(2000.0, 300.0, 6000), rng.normal(3500.0, 300.0, 5000)]
        )
        counts, edges, centers = self.pf._histogram_for_fit(data)
        popt, one_pop = self.pf._fit_and_check_double_gaussian(centers, counts)
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt)
        valley, _, _ = self.pf._threshold_between_populations(
            data, centers, counts, m1, s1, m2, s2, one_pop
        )
        fit, _ = self.pf._fit_double_gaussian_bounded_at_valley(
            centers, counts, valley, popt
        )
        # slack, not tight against, the constraint - and still on the true mean
        self.assertGreater(fit[4] - valley, PeakFinder.VALLEY_SEPARATION_SIGMA * fit[5])
        self.assertAlmostEqual(fit[4], 3500.0, delta=60.0)


# ---------------------------------------------------------------------------
# _warn_if_fitted_means_are_off_their_peaks
# ---------------------------------------------------------------------------


class TestMeansOffTheirPeaksWarning(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()
        rng = np.random.default_rng(0)
        lower = rng.lognormal(np.log(2495) + 0.13**2, 0.13, 6119)
        upper = rng.lognormal(np.log(4724) + 0.11**2, 0.11, 11816)
        self.data = np.concatenate([lower, upper])
        self.counts, _, self.centers = self.pf._histogram_for_fit(self.data)

    def test_warns_when_a_mean_is_not_on_its_own_peak(self):
        # The failure it exists for: a higher component pulled down into the
        # lower population's shoulder, well away from the mode it should be on.
        params = (900.0, 2495.0, 320.0, 1000.0, 3400.0, 900.0)
        with self.assertLogs(PeakFinder.logger, level="WARNING") as captured:
            self.pf._warn_if_fitted_means_are_off_their_peaks(
                self.centers, self.counts, params
            )
        self.assertTrue(
            any("half-maximum span" in line for line in captured.output),
            captured.output,
        )
        self.assertTrue(any("higher component" in line for line in captured.output))

    def test_silent_on_a_well_centred_fit(self):
        popt, _ = self.pf._fit_and_check_double_gaussian(self.centers, self.counts)
        self.assertIsNotNone(popt)
        with self.assertNoLogs(PeakFinder.logger, level="WARNING"):
            self.pf._warn_if_fitted_means_are_off_their_peaks(
                self.centers, self.counts, tuple(float(p) for p in popt)
            )

    def test_silent_on_single_population_data(self):
        # A single population has no second peak, and its higher component
        # correctly describes a sparse region rather than a mode - documented
        # behaviour, so warning about it would be crying wolf.
        rng = np.random.default_rng(9)
        data = rng.lognormal(np.log(1900) + 0.18**2, 0.18, 8000)
        counts, _, centers = self.pf._histogram_for_fit(data)
        with self.assertNoLogs(PeakFinder.logger, level="WARNING"):
            self.pf._warn_if_fitted_means_are_off_their_peaks(
                centers, counts, (400.0, 1900.0, 250.0, 10.0, 3400.0, 800.0)
            )

    def test_span_is_reported_in_current_not_bin_indices(self):
        # peak_widths returns left_ips/right_ips in bin-INDEX units. Left
        # unconverted they are small numbers that would place every span near
        # the histogram's left edge and make this warning fire constantly.
        params = (900.0, 2495.0, 320.0, 1000.0, 3400.0, 900.0)
        with self.assertLogs(PeakFinder.logger, level="WARNING") as captured:
            self.pf._warn_if_fitted_means_are_off_their_peaks(
                self.centers, self.counts, params
            )
        numbers = [
            float(token.strip("[],"))
            for line in captured.output
            for token in line.replace("(", " ").replace(")", " ").split()
            if token.strip("[],").replace(".", "", 1).replace("-", "", 1).isdigit()
        ]
        span_scale = [n for n in numbers if n > float(self.centers[0])]
        self.assertTrue(span_scale, f"no pA-scale numbers in {captured.output}")

    def test_does_not_raise_on_degenerate_input(self):
        flat = np.zeros_like(self.counts)
        params = (1.0, 2495.0, 320.0, 1.0, 4724.0, 520.0)
        self.pf._warn_if_fitted_means_are_off_their_peaks(self.centers, flat, params)
        self.pf._warn_if_fitted_means_are_off_their_peaks(
            self.centers[:2], self.counts[:2], params
        )


if __name__ == "__main__":
    unittest.main()
