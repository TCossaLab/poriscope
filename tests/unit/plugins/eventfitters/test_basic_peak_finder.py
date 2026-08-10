"""
Tests for Basic_PeakFinder.py

Instantiate Basic_PeakFinder via object.__new__ to bypass __init__ and the
event-loader requirement. Settings and metadata are injected directly onto
the instance.

Coverage targets:
- find_mode_blockage_level
- enumerate_peaks
- _locate_sublevel_transitions (happy path + all ValueError branches)
- _populate_sublevel_metadata
- _populate_event_metadata
- _define_event_metadata_types / _define_sublevel_metadata_types
- _define_event_metadata_units / _define_sublevel_metadata_units
- construct_fitted_event (None paths + happy path + max_blockage painting)
- get_plot_features (None paths + Some/All plot feature paths)
- _init / _pre_process_events / _post_process_events / _validate_settings / close_resources
- get_empty_settings
"""

import unittest
from unittest.mock import MagicMock

import numpy as np

from poriscope.plugins.eventfitters.Basic_PeakFinder import Basic_PeakFinder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pf(**setting_overrides):
    """
    Return a Basic_PeakFinder with attributes injected, bypassing __init__.
    """
    pf = object.__new__(Basic_PeakFinder)
    pf.sublevel_metadata = {}
    pf.event_metadata = {}
    pf.eventfitting_status = {}
    pf.event_lengths = {}
    pf.eventloader = None
    pf.logger = Basic_PeakFinder.logger
    pf.settings = {
        "Plot Features": {"Value": "Some"},
        "Min Height": {"Value": 500.0},
        "Min Prominence": {"Value": 100.0},
        "Relative Height": {"Value": 0.5},
        "Window Length": {"Value": 25.0},
        "Width": {"Value": 0.0},
        "Min Distance": {"Value": 1.0},
        "Plateau Size": {"Value": 0.0},
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
            "max_blockage": None,
            "plateau_size": None,
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
            "max_blockage": None,
            "plateau_size": None,
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
                "max_blockage": 220.0,
                "plateau_size": None,
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
            "max_blockage": None,
            "plateau_size": None,
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
            "max_blockage": None,
            "plateau_size": None,
        },
    ]
    return starts


# ---------------------------------------------------------------------------
# find_mode_blockage_level
# ---------------------------------------------------------------------------


class TestFindModeBlockageLevel(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_none_data_returns_zero(self):
        self.assertEqual(self.pf.find_mode_blockage_level(None, 200.0, 10.0), 0.0)

    def test_empty_data_returns_zero(self):
        self.assertEqual(
            self.pf.find_mode_blockage_level(np.array([]), 200.0, 10.0), 0.0
        )

    def test_degenerate_range_no_halving(self):
        # all-identical data: data_max <= data_min branch.
        # Unlike the carrier-aware variant, this implementation never halves.
        data = np.full(20, 50.0)
        result = self.pf.find_mode_blockage_level(data, 200.0, 10.0)
        self.assertAlmostEqual(result, abs(50.0 - 200.0))

    def test_baseline_std_none_falls_back_to_data_std(self):
        data = np.concatenate([np.ones(50) * 100.0, np.ones(50) * 100.0])
        # std of a constant array is 0, but the function should not crash
        result = self.pf.find_mode_blockage_level(data, 200.0, None)
        self.assertGreaterEqual(result, 0.0)

    def test_baseline_std_nonpositive_falls_back_to_data_std(self):
        data = np.concatenate([np.ones(10) * 100.0, np.ones(90) * 300.0])
        result = self.pf.find_mode_blockage_level(data, 0.0, -5.0)
        self.assertGreater(result, 0.0)

    def test_mode_detection_picks_dominant_cluster(self):
        # Dense cluster near 300 dominates a small cluster near 100.
        data = np.concatenate([np.ones(5) * 100.0, np.ones(95) * 300.0])
        result = self.pf.find_mode_blockage_level(data, 0.0, 10.0)
        self.assertAlmostEqual(result, 300.0, delta=15.0)

    def test_nonnegative(self):
        data = np.random.RandomState(0).randn(100) * 5.0 + 200.0
        result = self.pf.find_mode_blockage_level(data, 750.0, 10.0)
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

    def test_uses_sublevel_types_override_when_provided(self):
        # Edge "type" field disagrees with sublevel_types; sublevel_types wins.
        starts = [
            {"index": 0, "type": "start"},
            {"index": 10, "type": "padding_before"},
            {"index": 20, "type": "padding_after"},  # type says non-peak
            {"index": 30, "type": "end"},
        ]
        num_states = len(starts) - 1
        sublevel_types = ["padding", "peak", "padding"]  # but override says peak
        ids = self.pf.enumerate_peaks(starts, num_states, sublevel_types)
        self.assertEqual(ids, [None, 1, None])


# ---------------------------------------------------------------------------
# _locate_sublevel_transitions
# ---------------------------------------------------------------------------


class TestLocateSublevelTransitions(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf(**{"Min Height": 10.0, "Min Prominence": 10.0})

    def test_no_data_above_threshold_raises(self):
        data = np.full(300, 200.0)
        with self.assertRaises(ValueError):
            self.pf._locate_sublevel_transitions(data, 1e6, 50, 50, 200.0, 5.0)

    def test_carrier_too_short_raises(self):
        data = np.full(300, 200.0)
        data[60:65] = 50.0  # only 5 samples, below the 10-sample minimum
        with self.assertRaises(ValueError):
            self.pf._locate_sublevel_transitions(data, 1e6, 50, 50, 200.0, 5.0)

    def test_no_peaks_in_carrier_raises(self):
        data = np.full(300, 200.0)
        data[60:90] = 50.0  # flat carrier, nothing to detect as a peak
        with self.assertRaises(ValueError):
            self.pf._locate_sublevel_transitions(data, 1e6, 50, 50, 200.0, 5.0)

    def test_missing_baseline_std_and_padding_raises(self):
        data = np.full(300, 200.0)
        with self.assertRaises(ValueError):
            self.pf._locate_sublevel_transitions(data, 1e6, None, None, 200.0, None)

    def test_happy_path_returns_well_formed_edges(self):
        data = np.full(300, 200.0)
        data[60:90] = 50.0  # carrier level
        data[75] = -50.0  # a single, sharp peak inside the carrier

        edges = self.pf._locate_sublevel_transitions(data, 1e6, 50, 50, 200.0, 5.0)

        self.assertEqual(edges[0]["type"], "start")
        self.assertIn("unfolded_level", edges[0])
        self.assertEqual(edges[-1]["type"], "end")
        self.assertEqual(edges[-1]["index"], len(data))

        peak_edges = [e for e in edges if e["type"].startswith("peak_")]
        self.assertEqual(len(peak_edges), 1)

        peak = peak_edges[0]
        for key in (
            "peak_height",
            "prominence",
            "left_base",
            "right_base",
            "width",
            "left_ips",
            "right_ips",
            "max_blockage",
            "plateau_size",
        ):
            self.assertIn(key, peak)
        self.assertGreater(peak["peak_height"], 0.0)
        self.assertLess(peak["left_ips"], peak["right_ips"])

    def test_baseline_std_none_with_padding_before_falls_back(self):
        # baseline_std computed from data[:padding_before] instead of raising.
        data = np.full(300, 200.0)
        data[60:90] = 50.0
        data[75] = -50.0
        # padding_before slice is flat -> std 0 -> threshold 0 -> everything
        # outside exact baseline value counts as "above threshold", which is
        # fine here; we only assert that no exception propagates from the
        # std-computation branch itself and a list of edges comes back.
        edges = self.pf._locate_sublevel_transitions(data, 1e6, 50, 50, 200.0, None)
        self.assertIsInstance(edges, list)
        self.assertEqual(edges[0]["type"], "start")


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
            "sublevel_type",
            "sublevel_current",
            "sublevel_duration",
            "sublevel_start_times",
            "sublevel_end_times",
            "sublevel_raw_ecd",
            "sublevel_cumulative_ecd",
            "sublevel_max_deviation",
            "peak_id",
            "peak_loc",
            "peak_width",
            "peak_height",
            "normalized_height",
            "prominence",
            "normalized_prominence",
            "max_blockage",
            "normalized_blockage",
            "plateau_size",
            "left_base",
            "right_base",
            "left_ips",
            "right_ips",
            "height_ips",
            "filtered",
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
        self.assertEqual(len(meta["filtered"]), num_states)

    def test_filtered_is_always_nan(self):
        # Basic_PeakFinder does not classify peaks; "filtered" is a NaN
        # placeholder column for every sublevel.
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        self.assertTrue(all(np.isnan(f) for f in meta["filtered"]))

    def test_cumulative_ecd_length_matches_raw(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        self.assertEqual(
            len(meta["sublevel_cumulative_ecd"]), len(meta["sublevel_raw_ecd"])
        )

    def test_peak_height_positive_for_peak_sublevel(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
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

    def test_normalized_height_matches_ratio(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        unfolded_level = self.starts[0]["unfolded_level"]
        num_states = len(self.starts) - 1
        for i in range(num_states):
            if "peak" in self.starts[i]["type"]:
                self.assertAlmostEqual(
                    meta["normalized_height"][i],
                    self.starts[i]["peak_height"] / unfolded_level,
                )

    def test_start_times_nondecreasing(self):
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        times = meta["sublevel_start_times"]
        self.assertTrue(all(times[i] <= times[i + 1] for i in range(len(times) - 1)))

    def test_enumerate_peaks_called_with_sublevel_type(self):
        # peak_id should align with the "peak" entries in sublevel_type.
        meta = self.pf._populate_sublevel_metadata(
            self.data, self.samplerate, 100.0, 10.0, self.starts
        )
        for i, sub_type in enumerate(meta["sublevel_type"]):
            if sub_type == "peak":
                self.assertIsNotNone(meta["peak_id"][i])
            else:
                self.assertIsNone(meta["peak_id"][i])


# ---------------------------------------------------------------------------
# _populate_event_metadata
# ---------------------------------------------------------------------------


class TestPopulateEventMetadata(unittest.TestCase):
    def _make_sublevel_meta(self, n=5):
        return {
            "sublevel_current": np.array([123.0, 300.0, 300.0, 300.0, 123.0]),
            "sublevel_duration": np.ones(n) * 10.0,
            "sublevel_raw_ecd": np.ones(n) * 0.1,
            "sublevel_max_deviation": np.ones(n) * 5.0,
            "sublevel_start_times": np.array([0.0, 10000.0, 20000.0, 30000.0, 40000.0]),
            "peak_id": [None, 1, 2, 3, None],
        }

    def _make_data(self):
        # data[10000:40000] needs variation for find_mode_blockage_level
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
            "baseline_std",
        ]:
            self.assertIn(key, result)

    def test_baseline_current_is_passed_through_unchanged(self):
        # Unlike a weighted-average implementation, Basic_PeakFinder simply
        # echoes the baseline_mean argument it was given.
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 123.0, 10.0, self._make_sublevel_meta()
        )
        self.assertEqual(result["baseline_current"], 123.0)

    def test_baseline_std_is_passed_through_unchanged(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 100.0, 7.5, self._make_sublevel_meta()
        )
        self.assertEqual(result["baseline_std"], 7.5)

    def test_number_peaks_is_max_peak_id(self):
        pf = _make_pf()
        result = pf._populate_event_metadata(
            self._make_data(), 1e6, 100.0, 10.0, self._make_sublevel_meta()
        )
        self.assertEqual(result["number_peaks"], 3)

    def test_number_peaks_zero_when_no_peaks(self):
        pf = _make_pf()
        meta = self._make_sublevel_meta()
        meta["peak_id"] = [None, None, None, None, None]
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, meta)
        self.assertEqual(result["number_peaks"], 0)

    def test_duration_sums_inner_sublevels_only(self):
        pf = _make_pf()
        meta = self._make_sublevel_meta()  # 5 sublevels, each 10 us
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, meta)
        # inner [1:-1] = 3 entries x 10us = 30
        self.assertAlmostEqual(result["duration"], 30.0)

    def test_raw_ecd_sums_inner_sublevels_only(self):
        pf = _make_pf()
        meta = self._make_sublevel_meta()
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, meta)
        self.assertAlmostEqual(result["raw_ecd"], 0.3)

    def test_max_deviation_is_max_of_inner_sublevels(self):
        pf = _make_pf()
        meta = self._make_sublevel_meta()
        meta["sublevel_max_deviation"] = np.array([1.0, 7.0, 2.0, 9.0, 1.0])
        result = pf._populate_event_metadata(self._make_data(), 1e6, 100.0, 10.0, meta)
        self.assertEqual(result["max_deviation"], 9.0)


# ---------------------------------------------------------------------------
# _define_event_metadata_types / units, _define_sublevel_metadata_types / units
# ---------------------------------------------------------------------------


class TestDefineMetadataTypesAndUnits(unittest.TestCase):
    def setUp(self):
        self.pf = _make_pf()

    def test_event_types_correct(self):
        t = self.pf._define_event_metadata_types()
        self.assertIs(t["number_peaks"], int)
        self.assertIs(t["duration"], float)
        self.assertIs(t["raw_ecd"], float)
        self.assertIs(t["max_deviation"], float)
        self.assertIs(t["baseline_current"], float)
        self.assertIs(t["unfolded_level"], float)
        self.assertIs(t["baseline_std"], float)

    def test_sublevel_types_all_present(self):
        t = self.pf._define_sublevel_metadata_types()
        for key in [
            "sublevel_current",
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
            "plateau_size",
            "max_blockage",
            "left_base",
            "right_base",
            "left_ips",
            "right_ips",
            "height_ips",
            "normalized_height",
            "normalized_prominence",
            "normalized_blockage",
            "filtered",
        ]:
            self.assertIn(key, t)
        self.assertIs(t["filtered"], int)
        self.assertIs(t["peak_id"], int)
        self.assertIs(t["sublevel_type"], str)

    def test_event_units(self):
        u = self.pf._define_event_metadata_units()
        self.assertEqual(u["number_peaks"], " ")
        self.assertEqual(u["duration"], "μs")
        self.assertEqual(u["raw_ecd"], "pC")
        self.assertEqual(u["max_deviation"], "pA")
        self.assertEqual(u["baseline_current"], "pA")
        self.assertEqual(u["baseline_std"], "pA")
        self.assertEqual(u["unfolded_level"], "pA")

    def test_sublevel_units(self):
        u = self.pf._define_sublevel_metadata_units()
        self.assertEqual(u["sublevel_current"], "pA")
        self.assertEqual(u["sublevel_duration"], "us")
        self.assertEqual(u["peak_height"], "pA")
        self.assertEqual(u["left_ips"], "us")
        self.assertEqual(u["plateau_size"], "us")
        self.assertIsNone(u["normalized_blockage"])
        self.assertIsNone(u["filtered"])

    def test_metadata_types_and_units_keys_align(self):
        # Every key produced as event/sublevel metadata should have a unit
        # entry, even if that unit is None.
        types = self.pf._define_sublevel_metadata_types()
        units = self.pf._define_sublevel_metadata_units()
        self.assertEqual(set(types.keys()), set(units.keys()))


# ---------------------------------------------------------------------------
# get_empty_settings
# ---------------------------------------------------------------------------


class TestGetEmptySettings(unittest.TestCase):
    def test_includes_base_and_own_keys(self):
        pf = object.__new__(Basic_PeakFinder)
        settings = pf.get_empty_settings(standalone=True)
        for key in [
            "MetaEventLoader",
            "Plot Features",
            "Min Height",
            "Min Prominence",
            "Relative Height",
            "Window Length",
            "Width",
            "Min Distance",
            "Plateau Size",
        ]:
            self.assertIn(key, settings)

    def test_plot_features_options(self):
        pf = object.__new__(Basic_PeakFinder)
        settings = pf.get_empty_settings(standalone=True)
        self.assertEqual(settings["Plot Features"]["Options"], ["All", "Some", "None"])
        self.assertEqual(settings["Plot Features"]["Value"], "Some")

    def test_default_values(self):
        pf = object.__new__(Basic_PeakFinder)
        settings = pf.get_empty_settings(standalone=True)
        self.assertEqual(settings["Min Height"]["Value"], 500)
        self.assertEqual(settings["Min Prominence"]["Value"], 100)
        self.assertEqual(settings["Relative Height"]["Value"], 0.5)


# ---------------------------------------------------------------------------
# construct_fitted_event
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
        pf.sublevel_metadata = {0: {99: {}}}  # only index 99 exists
        pf.eventfitting_status = {0: True}
        pf.event_lengths = {0: {0: 100}}
        pf.event_metadata = {0: {}}
        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = 1e6
        self.assertIsNone(pf.construct_fitted_event(0, 0))

    def test_construct_returns_array_when_data_present(self):
        """Happy path: two sublevels, no peaks -> a baseline-only array."""
        pf = _make_pf()
        n = 50
        samplerate = 1e6
        dt_us = 1.0 / samplerate * 1e6

        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = samplerate

        starts_us = np.array([0.0, 25.0]) * dt_us
        ends_us = np.array([25.0, 50.0]) * dt_us

        pf.sublevel_metadata = {
            0: {
                0: {
                    "sublevel_start_times": starts_us,
                    "sublevel_end_times": ends_us,
                    "sublevel_current": np.array([100.0, 300.0]),
                    "peak_height": np.array([0.0, 0.0]),
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
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(len(result), n)
        np.testing.assert_allclose(result[:25], 100.0)
        np.testing.assert_allclose(result[25:], 300.0)

    def test_construct_paints_max_blockage_between_ips(self):
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
                    "right_ips": np.array([np.nan, 60.0 * dt_us, np.nan]),
                    "left_ips": np.array([np.nan, 45.0 * dt_us, np.nan]),
                    "max_blockage": np.array([np.nan, 50.0, np.nan]),
                }
            }
        }
        pf.event_metadata = {0: {0: {"baseline_current": 100.0}}}
        pf.eventfitting_status = {0: True}
        pf.event_lengths = {0: {0: n}}

        result = pf.construct_fitted_event(0, 0)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), n)
        # Between left/right ips, value is overwritten with baseline - sign(baseline)*max_blockage
        expected_peak_value = 100.0 - np.sign(100.0) * 50.0
        np.testing.assert_allclose(result[46:60], expected_peak_value)

    def test_construct_handles_missing_max_blockage_key(self):
        # max_blockage absent entirely -> falls back to [None]*len(peak_height)
        pf = _make_pf()
        n = 50
        samplerate = 1e6
        dt_us = 1.0 / samplerate * 1e6

        pf.eventloader = MagicMock()
        pf.eventloader.get_samplerate.return_value = samplerate

        starts_us = np.array([0.0, 25.0]) * dt_us
        ends_us = np.array([25.0, 50.0]) * dt_us

        pf.sublevel_metadata = {
            0: {
                0: {
                    "sublevel_start_times": starts_us,
                    "sublevel_end_times": ends_us,
                    "sublevel_current": np.array([100.0, 300.0]),
                    "peak_height": np.array([0.0, 0.0]),
                    "right_ips": np.array([np.nan, np.nan]),
                    "left_ips": np.array([np.nan, np.nan]),
                    # no "max_blockage" key at all
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
# get_plot_features
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

    def test_settings_none_returns_all_none(self):
        pf = _make_pf()
        pf.settings = None
        pf.sublevel_metadata = {0: {0: {}}}
        pf.eventfitting_status = {0: True}
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def test_missing_event_index_returns_all_none(self):
        """KeyError inside the try block -> tuple of Nones."""
        pf = _make_pf(**{"Plot Features": "Some"})
        pf.sublevel_metadata = {0: {99: {}}}  # only index 99 exists
        pf.eventfitting_status = {0: True}
        pf.event_metadata = {0: {}}
        result = pf.get_plot_features(0, 0)
        self.assertEqual(result, (None, None, None, None, None, None))

    def _setup_full_pf(self, plot_value="Some"):
        pf = _make_pf(**{"Plot Features": plot_value})
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, 55.0, np.nan]),
                    "peak_id": [None, 1, None],
                    "peak_loc": np.array([np.nan, 50.0, np.nan]),
                    "peak_height": np.array([np.nan, 600.0, np.nan]),
                }
            }
        }
        pf.event_metadata = {
            0: {
                0: {
                    "baseline_current": 100.0,
                    "unfolded_level": 200.0,
                }
            }
        }
        pf.eventfitting_status = {0: True}
        return pf

    def test_bases_always_length_two(self):
        # In Basic_PeakFinder, only "Baseline" and "unfolded level" are ever
        # appended to bases; "Some" vs "All" makes no observable difference
        # since nothing else is added inside the per-peak loop.
        for plot_value in ("Some", "All"):
            pf = self._setup_full_pf(plot_value)
            _, bases, _, _, hlabel, _ = pf.get_plot_features(0, 0)
            self.assertEqual(len(bases), 2)
            self.assertEqual(hlabel, ["Baseline", "unfolded level"])

    def test_baseline_and_unfolded_level_values(self):
        pf = self._setup_full_pf("Some")
        _, bases, _, _, _, _ = pf.get_plot_features(0, 0)
        baseline = 100.0
        unfolded_level = 200.0
        expected_unfolded_base = -np.sign(baseline) * unfolded_level + baseline
        self.assertAlmostEqual(bases[0], baseline)
        self.assertAlmostEqual(bases[1], expected_unfolded_base)

    def test_peak_label_has_no_type_suffix(self):
        # The "Type:" suffix is commented out in Basic_PeakFinder's
        # get_plot_features, unlike richer subclasses.
        pf = self._setup_full_pf("All")
        _, _, _, _, _, plabel = pf.get_plot_features(0, 0)
        self.assertEqual(plabel, ["Peak #1"])

    def test_peaks_list_contains_tuple_with_expected_value(self):
        pf = self._setup_full_pf("All")
        _, _, peaks, _, _, _ = pf.get_plot_features(0, 0)
        self.assertEqual(len(peaks), 1)
        loc, value = peaks[0]
        self.assertEqual(loc, 50.0)
        baseline = 100.0
        expected_value = -np.sign(baseline) * 600.0 + baseline
        self.assertAlmostEqual(value, expected_value)

    def test_only_entries_with_peak_id_are_included(self):
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, np.nan, np.nan]),
                    "peak_id": [None, None, None],  # nothing flagged as a peak
                    "peak_loc": np.array([np.nan, 50.0, np.nan]),
                    "peak_height": np.array([np.nan, 600.0, np.nan]),
                }
            }
        }
        pf.event_metadata = {
            0: {0: {"baseline_current": 100.0, "unfolded_level": 200.0}}
        }
        pf.eventfitting_status = {0: True}
        _, _, peaks, _, _, plabel = pf.get_plot_features(0, 0)
        self.assertEqual(peaks, [])
        self.assertEqual(plabel, [])

    def test_multiple_peaks_numbered_sequentially(self):
        pf = _make_pf(**{"Plot Features": "All"})
        pf.sublevel_metadata = {
            0: {
                0: {
                    "right_ips": np.array([np.nan, 55.0, np.nan, 90.0]),
                    "peak_id": [None, 1, None, 2],
                    "peak_loc": np.array([np.nan, 50.0, np.nan, 85.0]),
                    "peak_height": np.array([np.nan, 600.0, np.nan, 700.0]),
                }
            }
        }
        pf.event_metadata = {
            0: {0: {"baseline_current": 100.0, "unfolded_level": 200.0}}
        }
        pf.eventfitting_status = {0: True}
        _, _, peaks, _, _, plabel = pf.get_plot_features(0, 0)
        self.assertEqual(plabel, ["Peak #1", "Peak #2"])
        self.assertEqual(len(peaks), 2)


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
