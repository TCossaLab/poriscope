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
- _ClassificationWarningCollector
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from poriscope.plugins.eventfitters.PeakFinder import (
    PeakFinder,
    _ClassificationWarningCollector,
)

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
        "Peak to Peak Distance Ratio": {"Value": 5.0},
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
    def _props(
        self,
        left_bases,
        right_bases,
        prominences=None,
        peak_loc=None,
        ecds=None,
        widths=None,
    ):
        n = len(left_bases)
        if prominences is None:
            prominences = [200.0] * n
        if peak_loc is None:
            peak_loc = [float(i) for i in range(n)]
        props = {
            "filtered": [0] * n,
            "prominences": np.array(prominences, dtype=float),
            "left_bases": list(left_bases),
            "right_bases": list(right_bases),
            "peak_heights": np.array([700.0] * n),
            # microseconds, as _populate_sublevel_metadata stores it
            "peak_loc": list(peak_loc),
        }
        if ecds is not None:
            props["sublevel_raw_ecd"] = list(ecds)
        if widths is not None:
            props["peak_width"] = list(widths)
        return props

    def _carrier(
        self,
        locs,
        widths=None,
        ecds=None,
        k=4,
        ratio=100.0,
        event_length=1000.0,
        pf=None,
    ):
        """
        Run the barcode branch over peaks that all sit on the unfolded
        carrier, so step 1 types every one of them 1 and only the barcode
        selection decides the outcome.

        unfolded=200, std=10, baseline=100 puts the type-1 band at [160, 220]
        and an effective base of 200 inside it.
        """
        if pf is None:
            pf = _make_pf(
                **{
                    "Event Type": "Barcode",
                    "Number of peaks": k,
                    "Peak to Peak Distance Ratio": ratio,
                }
            )
        n = len(locs)
        props = self._props(
            [100.0] * n,
            [100.0] * n,
            peak_loc=list(locs),
            ecds=ecds,
            widths=widths,
        )
        out = pf.filter_peaks(
            np.arange(n), props, 200.0, None, 10.0, 100.0, 1e6, event_length
        )
        return list(out["filtered"])

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

    def test_a_later_cluster_can_win_on_score(self):
        """
        Two separated, non-adjacent type-1 clusters of equal size: the one
        that scores better must win, not whichever is found first.

        Inherited from a regression guard against candidates being
        pre-filtered to the `num_peaks` most prominent peaks *globally* before
        any set was looked for, which on this geometry left no two candidates
        close enough to pair and found no barcode at all. Prominence no longer
        decides the selection, so the same geometry is now driven by width:
        the *later* cluster is the matched pair, and has to be picked over the
        earlier one that the tie-break would otherwise favour.
        """
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # Cluster A: peaks 0-1, 10 us apart, widths 2.0 / 8.0 - mismatched.
        # Cluster B: peaks 2-3, 10 us apart, widths 5.0 / 5.0 - matched.
        # A and B are 490 us apart, far beyond the 50 us (5%) limit, so they
        # never merge, and A is earlier - so only the score can promote B.
        props = self._props(
            [100.0, 100.0, 100.0, 100.0],
            [100.0, 100.0, 100.0, 100.0],
            prominences=[90.0, 90.0, 95.0, 1.0],
            peak_loc=[0.0, 10.0, 500.0, 510.0],
            widths=[2.0, 8.0, 5.0, 5.0],
        )
        result = pf.filter_peaks(
            np.array([0, 10, 500, 510]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(list(result["filtered"]), [1, 1, 3, 3])

    def test_cluster_distance_is_independent_of_sample_rate(self):
        """
        The peak-to-peak limit is a percentage of event length, and both sides
        of that comparison are in microseconds - so identical event geometry
        must cluster identically however fast it was sampled.

        Regression guard for a unit bug: max_distance was converted to samples
        while peak_loc stayed in microseconds, so the effective limit scaled
        with the sample rate in MHz. It was invisible at exactly 1 MHz, which
        is the only rate every other test in this class uses.
        """
        results = []
        for samplerate in (250e3, 1e6, 4e6):
            pf = _make_pf(
                **{
                    "Event Type": "Barcode",
                    "Number of peaks": 2,
                    "Peak to Peak Distance Ratio": 5.0,
                }
            )
            # Two carrier-level peaks 40 us apart in a 1000 us event. The 5%
            # limit is 50 us, so they are one cluster at any sample rate.
            props = self._props([100.0, 100.0], [100.0, 100.0], peak_loc=[0.0, 40.0])
            out = pf.filter_peaks(
                np.array([0, 40]),
                props,
                200.0,
                None,
                10.0,
                100.0,
                samplerate,
                1000.0,
            )
            results.append(list(out["filtered"]))

        self.assertEqual(results[0], results[1], "250 kHz disagreed with 1 MHz")
        self.assertEqual(results[1], results[2], "4 MHz disagreed with 1 MHz")
        for filtered in results:
            self.assertEqual(filtered, [3, 3])

    def test_peaks_beyond_the_distance_limit_do_not_cluster(self):
        """
        60 us apart against the same 50 us limit: no cluster, and a fast
        sample rate must not buy them one.
        """
        pf = _make_pf(
            **{
                "Event Type": "Barcode",
                "Number of peaks": 2,
                "Peak to Peak Distance Ratio": 5.0,
            }
        )
        props = self._props([100.0, 100.0], [100.0, 100.0], peak_loc=[0.0, 60.0])
        out = pf.filter_peaks(
            np.array([0, 60]), props, 200.0, None, 10.0, 100.0, 4e6, 1000.0
        )
        self.assertEqual(list(out["filtered"]), [1, 1])

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

    def test_carrier_peak_wins_where_the_baseline_band_overlaps_type1(self):
        """
        A peak seated on the unfolded carrier must be type 1 even when the
        baseline band reaches it.

        Regression guard for type 0 being tested first: with unfolded=50 and
        std=10 the type-1 band opens at 50 - 4*10 = 10 while the baseline band
        closes at BASELINE_BAND_SIGMA * 10 = 30, so a base at depth 20 is
        inside both. Type 1 has to win, or a carrier peak is lost from the
        barcode pool as a baseline peak.
        """
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # effective_base = -80 + 100 = 20, inside both bands
        props = self._props([-80.0], [-80.0])
        result = pf.filter_peaks(
            np.array([200]), props, 50.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 1)

    def test_baseline_peak_is_still_typed_zero(self):
        """
        Type 0 stays reachable: a base below the type-1 floor and inside the
        baseline band is a baseline peak.
        """
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        # effective_base = -95 + 100 = 5, below the type-1 floor of 10 and
        # inside the 30-wide baseline band
        props = self._props([-95.0], [-95.0])
        result = pf.filter_peaks(
            np.array([200]), props, 50.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 0)

    def test_baseline_band_ignores_higher_filter_threshold(self):
        """
        The baseline band is BASELINE_BAND_SIGMA, not t2, so raising t2 must
        not widen it.

        At t2=5 the old band would have been 50 wide and claimed this base as
        type 0; the fixed band closes at 30, and the base is nowhere near the
        type-1 floor of 160, so it is rejected instead.
        """
        pf = _make_pf(
            **{
                "Event Type": "Barcode",
                "Number of peaks": 2,
                "Lower Filter Threshold": -4,
                "Higher Filter Threshold": 5,
            }
        )
        # effective_base = -60 + 100 = 40: outside the 30-wide baseline band,
        # below the type-1 floor of 200 - 40 = 160
        props = self._props([-60.0], [-60.0])
        result = pf.filter_peaks(
            np.array([200]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], -1)

    def _edge_props(self, base_at_edge):
        """Two carrier-seated peaks, with the given base_at_edge flags."""
        props = self._props([100.0, 100.0], [100.0, 100.0], peak_loc=[0.0, 10.0])
        props["base_at_edge"] = list(base_at_edge)
        return props

    def test_type1_peak_with_base_at_either_edge_is_rejected(self):
        """
        A type-1 peak whose base was pinned to an end of the trimmed event is
        rejected to -1, and both ends are treated alike.

        Number of peaks is set above the peak count so nothing is promoted to
        type 3 and the typing is what is being measured.
        """
        for flags, expected in (
            ([0.0, 0.0], [1, 1]),
            ([1.0, 0.0], [-1, 1]),
            ([0.0, 1.0], [1, -1]),
            ([1.0, 1.0], [-1, -1]),
        ):
            with self.subTest(flags=flags):
                pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 5})
                result = pf.filter_peaks(
                    np.array([0, 10]),
                    self._edge_props(flags),
                    200.0,
                    None,
                    10.0,
                    100.0,
                    1e6,
                    1000.0,
                )
                self.assertEqual(list(result["filtered"]), expected)

    def test_edge_flag_does_not_affect_a_baseline_peak(self):
        """The rejection applies to type 1 only, not to every flagged peak."""
        pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 2})
        props = self._props([-95.0], [-95.0])
        props["base_at_edge"] = [1.0]
        result = pf.filter_peaks(
            np.array([200]), props, 50.0, None, 10.0, 100.0, 1e6, 1000.0
        )
        self.assertEqual(result["filtered"][0], 0)

    def test_absent_or_nan_edge_flags_type_as_before(self):
        """
        A database written before the column existed, or a peak record built
        without it, must type exactly as it used to rather than being
        rejected.
        """
        for flags in (None, [np.nan, np.nan]):
            with self.subTest(flags=flags):
                pf = _make_pf(**{"Event Type": "Barcode", "Number of peaks": 5})
                props = self._props(
                    [100.0, 100.0], [100.0, 100.0], peak_loc=[0.0, 10.0]
                )
                if flags is not None:
                    props["base_at_edge"] = list(flags)
                result = pf.filter_peaks(
                    np.array([0, 10]), props, 200.0, None, 10.0, 100.0, 1e6, 1000.0
                )
                self.assertEqual(list(result["filtered"]), [1, 1])

    # -----------------------------------------------------------------
    # barcode selection: which type-1 peaks become type 3
    # -----------------------------------------------------------------

    def test_ideal_event_promotes_the_whole_regular_train(self):
        """Four evenly spaced peaks of equal width are the barcode."""
        self.assertEqual(
            self._carrier([0.0, 45.0, 90.0, 135.0], [2.0, 2.0, 2.0, 2.0], k=4),
            [3, 3, 3, 3],
        )

    def test_an_off_pattern_peak_is_skipped_and_keeps_type_1(self):
        """
        The selection need not be consecutive: a peak that breaks both the
        spacing and the width pattern is skipped from the middle of the train,
        and keeps its type 1 rather than being rejected.
        """
        self.assertEqual(
            self._carrier(
                [0.0, 45.0, 60.0, 90.0, 135.0],
                [2.0, 2.0, 9.0, 2.0, 2.0],
                k=4,
            ),
            [3, 3, 1, 3, 3],
        )

    def test_width_similarity_chooses_between_two_regular_trains(self):
        """
        Two equally regular candidate trains, far enough apart never to
        merge: the one whose peaks have matching widths wins.

        Also the guard that every candidate set is considered, not just the
        first one found - the winning train here is the earlier, but it wins
        on score rather than on position (see the tie-break test for what
        happens when scores are equal).
        """
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 120.0, 400.0, 440.0, 480.0, 520.0],
                [2.0, 2.0, 2.0, 2.0, 1.0, 7.0, 3.0, 9.0],
                k=4,
                ratio=6.0,
            ),
            [3, 3, 3, 3, 1, 1, 1, 1],
        )

    def test_ecd_similarity_applies_when_its_weight_is_raised(self):
        """
        The ECD term is present but zero-weighted by default. Raising it makes
        it choose, on a geometry where widths are uniform and so cannot.
        """
        pf = _make_pf(
            **{
                "Event Type": "Barcode",
                "Number of peaks": 4,
                "Peak to Peak Distance Ratio": 6.0,
            }
        )
        pf.BARCODE_ECD_WEIGHT = 1.0
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 120.0, 400.0, 440.0, 480.0, 520.0],
                [2.0] * 8,
                ecds=[2.0, 2.0, 2.0, 2.0, 1.0, 7.0, 3.0, 9.0],
                k=4,
                ratio=6.0,
                pf=pf,
            ),
            [3, 3, 3, 3, 1, 1, 1, 1],
        )

    def test_skipping_is_refused_when_the_recomputed_gap_is_too_wide(self):
        """
        max_distance is a constraint on the *selected* set, so a skip that
        would put two type-3 peaks more than max_distance apart is illegal
        however well it scores.

        These four peaks are 40 us apart against a 50 us limit, and the middle
        one has a badly mismatched width - so the selection would rather skip
        it, but doing so leaves an 80 us gap. With k=4 every peak has to be
        taken; with k=3 the set stays adjacent instead of skipping.
        """
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 120.0], [2.0, 2.0, 9.0, 2.0], k=4, ratio=5.0
            ),
            [3, 3, 3, 3],
        )
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 120.0], [2.0, 2.0, 9.0, 2.0], k=3, ratio=5.0
            ),
            [3, 3, 3, 1],
        )

    def test_equally_matched_sets_go_to_the_largest_total_ecd(self):
        """
        Two identical geometries, both perfectly regular and of uniform
        width: total ECD decides, and it does so even though the ECD term
        itself is zero-weighted.
        """
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 400.0, 440.0, 480.0],
                [2.0] * 6,
                ecds=[1.0, 1.0, 1.0, 5.0, 5.0, 5.0],
                k=3,
                ratio=6.0,
            ),
            [1, 1, 1, 3, 3, 3],
        )

    def test_selection_is_exactly_num_peaks(self):
        """A longer regular train is still labelled only num_peaks wide."""
        result = self._carrier([0.0, 40.0, 80.0, 120.0, 160.0, 200.0], [2.0] * 6, k=4)
        self.assertEqual(result.count(3), 4)

    def test_selection_without_width_or_ecd_falls_back_to_spacing(self):
        """
        A database written before peak_width and sublevel_raw_ecd were plumbed
        through supplies neither, which drops both terms rather than poisoning
        the score: the regular train is still found on spacing alone.
        """
        # Neither widths= nor ecds=, so the properties dict carries neither.
        self.assertEqual(
            self._carrier([0.0, 45.0, 90.0, 135.0], k=4),
            [3, 3, 3, 3],
        )

    def test_event_35304_geometry_skips_the_noise_peak(self):
        """
        A real event that the consecutive-run rule got wrong, and that the
        ECD term alone also got wrong when the noise peak happened to be the
        wide one.

        Five type-1 peaks: a regular train at ~105 us spacing (p2, p3, p4, p6)
        with a low, narrow noise peak (p5) sitting 60 us after p4. Selecting
        p5 costs two badly mismatched spacings, so the right answer skips it
        and treats p4 -> p6 as one 110 us gap - which only the recomputed-gap
        rule permits, and only while max_distance allows 110 us.
        """
        locs = [1830.0, 1935.0, 2040.0, 2100.0, 2150.0]
        widths = [12.0, 12.0, 12.0, 20.0, 12.0]
        # 15% of an 1100 us event is 165 us, so the 110 us skip gap is legal.
        self.assertEqual(
            self._carrier(locs, widths, k=4, ratio=15.0, event_length=1100.0),
            [3, 3, 3, 1, 3],
        )

    def test_a_skip_needs_headroom_in_the_distance_limit(self):
        """
        The same event with the limit set just below the skip gap: skipping is
        now illegal, so the noise peak is taken and the regular train is not
        recovered. Worth pinning, because it is the tension between allowing
        skips and treating max_distance as a hard constraint - a skip needs
        room for the gap it leaves behind.
        """
        locs = [1830.0, 1935.0, 2040.0, 2100.0, 2150.0]
        widths = [12.0, 12.0, 12.0, 20.0, 12.0]
        # 9.5% of 1100 us is 104.5 us: under the 105 us train spacing, so only
        # the tight trailing peaks can pair at all.
        result = self._carrier(locs, widths, k=4, ratio=9.5, event_length=1100.0)
        self.assertNotEqual(result, [3, 3, 3, 1, 3])

    def test_no_selection_when_too_few_candidates(self):
        """Fewer type-1 peaks than num_peaks means no barcode at all."""
        self.assertEqual(
            self._carrier([0.0, 45.0, 90.0], [2.0, 2.0, 2.0], k=4),
            [1, 1, 1],
        )

    def test_isolated_peaks_are_not_candidates(self):
        """
        A type-1 peak with no neighbour inside max_distance cannot be part of
        any legal set, so it never reaches the search.
        """
        # Three tight peaks plus one 500 us away, k=3 and a 60 us limit.
        self.assertEqual(
            self._carrier(
                [0.0, 40.0, 80.0, 580.0],
                [2.0, 2.0, 2.0, 2.0],
                k=3,
                ratio=6.0,
            ),
            [3, 3, 3, 1],
        )


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
        # NOTE (integration): key renamed baseline_std -> baseline_stdev.
        self.assertIs(t["baseline_stdev"], float)
        self.assertIs(t["translocation_direction"], str)
        self.assertIs(t["sequence"], str)

    def test_private_metadata_is_not_declared(self):
        """
        The working values PeakFinder keeps for itself must not appear in the
        declared types or units, or the writer would create columns for them
        that get_single_event_metadata never supplies.
        """
        event_types = self.pf._define_event_metadata_types()
        event_units = self.pf._define_event_metadata_units()
        for key in PeakFinder.PRIVATE_EVENT_METADATA:
            self.assertNotIn(key, event_types)
            self.assertNotIn(key, event_units)

        sublevel_types = self.pf._define_sublevel_metadata_types()
        sublevel_units = self.pf._define_sublevel_metadata_units()
        for key in PeakFinder.PRIVATE_SUBLEVEL_METADATA:
            self.assertNotIn(key, sublevel_types)
            self.assertNotIn(key, sublevel_units)

    def test_declared_types_and_units_agree(self):
        """
        The writer creates columns from the types dict and labels them from
        the units dict, so a key in one and not the other is a bug either way.
        """
        self.assertEqual(
            set(self.pf._define_event_metadata_types()),
            set(self.pf._define_event_metadata_units()),
        )
        self.assertEqual(
            set(self.pf._define_sublevel_metadata_types()),
            set(self.pf._define_sublevel_metadata_units()),
        )

    def test_get_single_event_metadata_strips_private_keys(self):
        """
        The accessor MetaDatabaseWriter iterates must not hand out the private
        working values, and must not disturb the internal dicts it copies
        from - get_plot_features and the classifiers still read those.
        """
        pf = _make_pf()
        pf.eventfitting_status = {0: True}
        pf.event_metadata = {
            0: {
                7: {
                    "duration": 100.0,
                    "unfolded_level": 500.0,
                    "folded_level": 1000.0,
                    "bound_star": "long end",
                    "translocation_confidence": 0.9,
                }
            }
        }
        pf.sublevel_metadata = {
            0: {7: {"peak_loc": np.array([1.0]), "base_at_edge": np.array([1.0])}}
        }
        loader = MagicMock()
        loader.load_event.return_value = {"data": np.zeros(4)}
        pf.eventloader = loader
        pf.applied_filters = {}
        pf.construct_fitted_event = MagicMock(return_value=None)

        event_metadata, sublevel_metadata, _, _, _ = pf.get_single_event_metadata(0, 7)

        for key in PeakFinder.PRIVATE_EVENT_METADATA:
            self.assertNotIn(key, event_metadata)
        for key in PeakFinder.PRIVATE_SUBLEVEL_METADATA:
            self.assertNotIn(key, sublevel_metadata)
        # what is left is untouched, and the internals still carry everything
        self.assertEqual(event_metadata["duration"], 100.0)
        self.assertIn("unfolded_level", pf.event_metadata[0][7])
        self.assertIn("base_at_edge", pf.sublevel_metadata[0][7])

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

    def test_default_settings(self):
        """
        The shipped defaults, pinned: this plugin exists to read barcodes, so
        it should be usable without retuning every field first.
        """
        settings = self.pf.get_empty_settings(standalone=True)
        expected = {
            "Event Type": "Barcode",
            "Number of peaks": 4,
            "Lower Filter Threshold": -5,
            "Higher Filter Threshold": 5,
            "Peak to Peak Distance Ratio": 30.0,
            "Window Length Percentage": 10.0,
            "Min Carrier Blockage": 300.0,
        }
        for key, value in expected.items():
            self.assertEqual(settings[key]["Value"], value, key)


# ---------------------------------------------------------------------------
# FIT_CONSTANT_OFFSET - the flat constant fitted alongside the two Gaussians
# ---------------------------------------------------------------------------


class TestFitConstantOffset(unittest.TestCase):
    """
    The seventh fitted parameter: a flat background belonging to neither
    population.

    It goes last in `params` so positions 0-5 keep their meanings, it is
    bounded like an amplitude, and it is kept only when it improves the
    residual - the guard that stops the extra degree of freedom from walking
    the fit into a worse local minimum.
    """

    def setUp(self):
        self.pf = _make_pf()

    @staticmethod
    def _two_populations(background=0, seed=0, n_hi=5000):
        """Two symmetric populations (sigma 300), optionally on a pedestal."""
        rng = np.random.default_rng(seed)
        core = np.concatenate(
            [rng.normal(2000.0, 300.0, 6000), rng.normal(3500.0, 300.0, n_hi)]
        )
        if not background:
            return core
        return np.concatenate([core, rng.uniform(core.min(), core.max(), background)])

    def _fit(self, data, use_offset=True):
        self.pf.FIT_CONSTANT_OFFSET = use_offset
        counts, _, centers = self.pf._histogram_for_fit(data)
        popt, _ = self.pf._fit_and_check_double_gaussian(centers, counts)
        self.assertIsNotNone(popt)
        residual = float(
            np.sum((self.pf._double_gaussian(centers, *popt) - counts) ** 2)
        )
        return popt, residual, centers, counts

    # -- the model itself ---------------------------------------------------

    def test_the_constant_is_added_to_both_components(self):
        x = np.array([0.0, 5.0, 10.0])
        without = self.pf._double_gaussian(x, 10.0, 0.0, 2.0, 10.0, 10.0, 2.0)
        with_offset = self.pf._double_gaussian(x, 10.0, 0.0, 2.0, 10.0, 10.0, 2.0, 7.0)
        np.testing.assert_allclose(with_offset, without + 7.0)

    def test_the_constant_defaults_to_zero(self):
        # so every call written before the constant existed still describes
        # the pure double Gaussian
        x = np.linspace(-5.0, 15.0, 21)
        np.testing.assert_allclose(
            self.pf._double_gaussian(x, 10.0, 0.0, 2.0, 10.0, 10.0, 2.0),
            self.pf._double_gaussian(x, 10.0, 0.0, 2.0, 10.0, 10.0, 2.0, 0.0),
        )

    # -- what it buys -------------------------------------------------------

    def test_a_real_background_is_recovered_and_the_widths_stop_absorbing_it(self):
        # 2500 uniform events under two sigma-300 populations. Without the
        # constant the widths inflate to cover the pedestal.
        data = self._two_populations(background=2500)
        with_off, rss_with, centers, counts = self._fit(data, True)
        without, rss_without, _, _ = self._fit(data, False)

        self.assertEqual(len(with_off), 7)
        self.assertEqual(len(without), 6)

        # the pedestal's true height in counts per bin
        expected = 2500.0 / len(counts)
        self.assertAlmostEqual(float(with_off[6]), expected, delta=0.25 * expected)

        # widths land closer to the true 300 with the constant than without
        for std_index in (2, 5):
            self.assertLess(
                abs(float(with_off[std_index]) - 300.0),
                abs(float(without[std_index]) - 300.0),
            )
        self.assertLess(rss_with, rss_without)

    def test_inert_when_there_is_no_background(self):
        # The property that makes it safe to switch on everywhere: on data
        # with no pedestal it settles near zero and moves no mean.
        data = self._two_populations()
        with_off, _, _, _ = self._fit(data, True)
        without, _, _, _ = self._fit(data, False)
        self.assertLess(float(with_off[6]), 0.02 * float(np.max([1.0, with_off[0]])))
        for mean_index in (1, 4):
            self.assertAlmostEqual(
                float(with_off[mean_index]),
                float(without[mean_index]),
                delta=0.001 * abs(float(without[mean_index])),
            )

    # -- the residual guard -------------------------------------------------

    def _curve_fit_returning(self, seven, six):
        """
        Patch `curve_fit` to return chosen parameters per fit arity, so the
        residual comparison can be driven directly.
        """

        def fake(f, xdata, ydata, p0=None, bounds=None, **kwargs):
            chosen = seven if len(p0) == 7 else six
            popt = np.asarray(chosen, dtype=float)
            return popt, np.zeros((popt.size, popt.size))

        return patch(
            "poriscope.plugins.eventfitters.PeakFinder.curve_fit", side_effect=fake
        )

    def test_a_constant_that_makes_the_residual_worse_is_discarded(self):
        # The guard, driven directly: the seven-parameter fit comes back with a
        # clearly worse residual, so the six-parameter one is kept. Real
        # seeding does not exercise this - it never lost there over the
        # benchmark in `_curve_fit_bounded`'s docstring - which is exactly why
        # the rule is worth pinning on its own.
        data = self._two_populations(background=2500)
        counts, _, centers = self.pf._histogram_for_fit(data)
        self.pf.FIT_CONSTANT_OFFSET = True

        good = (400.0, 2000.0, 300.0, 340.0, 3500.0, 300.0)
        # both components collapsed onto the low end: a bad fit by any measure
        bad_with_offset = (5.0, 2000.0, 150.0, 5.0, 2050.0, 150.0, 1.0)
        with self._curve_fit_returning(bad_with_offset, good):
            popt, _ = self.pf._curve_fit_bounded(centers, counts, good)
        self.assertEqual(len(popt), 6, "the worse seven-parameter fit won")
        np.testing.assert_allclose(popt, good)

    def test_a_constant_that_improves_the_residual_is_kept(self):
        # the mirror of the guard: where the constant earns its place it wins
        data = self._two_populations(background=2500)
        counts, _, centers = self.pf._histogram_for_fit(data)
        self.pf.FIT_CONSTANT_OFFSET = True

        without = (400.0, 2000.0, 300.0, 340.0, 3500.0, 300.0)
        with_offset = without + (2500.0 / len(counts),)
        with self._curve_fit_returning(with_offset, without):
            popt, _ = self.pf._curve_fit_bounded(centers, counts, without)
        self.assertEqual(len(popt), 7)
        np.testing.assert_allclose(popt, with_offset)

    def test_the_surviving_fit_is_used_when_the_other_one_raises(self):
        # one arity failing to converge must not lose the fit that did
        data = self._two_populations(background=2500)
        counts, _, centers = self.pf._histogram_for_fit(data)
        self.pf.FIT_CONSTANT_OFFSET = True
        good = (400.0, 2000.0, 300.0, 340.0, 3500.0, 300.0)

        def only_six(f, xdata, ydata, p0=None, bounds=None, **kwargs):
            if len(p0) == 7:
                raise RuntimeError("did not converge")
            popt = np.asarray(good, dtype=float)
            return popt, np.zeros((6, 6))

        with patch(
            "poriscope.plugins.eventfitters.PeakFinder.curve_fit",
            side_effect=only_six,
        ):
            popt, _ = self.pf._curve_fit_bounded(centers, counts, good)
        self.assertEqual(len(popt), 6)

    def test_both_failing_still_propagates(self):
        # so `_fit_double_gaussian` can still fall through to its next seed
        data = self._two_populations()
        counts, _, centers = self.pf._histogram_for_fit(data)
        self.pf.FIT_CONSTANT_OFFSET = True
        with patch(
            "poriscope.plugins.eventfitters.PeakFinder.curve_fit",
            side_effect=RuntimeError("did not converge"),
        ):
            with self.assertRaises(RuntimeError):
                self.pf._curve_fit_bounded(
                    centers, counts, (400.0, 2000.0, 300.0, 340.0, 3500.0, 300.0)
                )

    def test_the_kept_fit_is_never_the_worse_of_the_two(self):
        # the guard's invariant, over background and background-free data and
        # over a minority second population
        for background, n_hi in ((0, 5000), (2500, 5000), (0, 300)):
            with self.subTest(background=background, n_hi=n_hi):
                data = self._two_populations(background=background, n_hi=n_hi, seed=3)
                _, rss_with, _, _ = self._fit(data, True)
                _, rss_without, _, _ = self._fit(data, False)
                self.assertLessEqual(rss_with, rss_without * (1.0 + 1e-6) + 1e-6)

    def test_a_near_tie_keeps_the_seven_parameter_fit(self):
        # With no background the constant converges to ~0 and the two fits are
        # the same curve to within float noise. Letting that noise decide
        # would flip len(params) between runs on equivalent data, so near-ties
        # go to the more general model and the output shape stays stable.
        for seed in (0, 5, 9):
            with self.subTest(seed=seed):
                data = self._two_populations(n_hi=600, seed=seed)
                popt, _, _, _ = self._fit(data, True)
                self.assertEqual(len(popt), 7)

    def test_switching_the_constant_off_gives_six_parameters(self):
        data = self._two_populations(background=2500)
        popt, _, _, _ = self._fit(data, False)
        self.assertEqual(len(popt), 6)

    # -- what fit_threshold reports -----------------------------------------

    def test_the_constant_is_on_by_default(self):
        self.assertTrue(PeakFinder.FIT_CONSTANT_OFFSET)

    def test_fit_threshold_reports_the_constant_in_params_and_on_its_own(self):
        self.pf.FIT_CONSTANT_OFFSET = True
        bt = self.pf.fit_threshold(self._two_populations(background=2500))
        self.assertEqual(len(bt["params"]), 7)
        self.assertEqual(bt["params"][6], bt["offset"])
        self.assertGreater(bt["offset"], 0.0)

    def test_the_constant_is_zero_not_absent_when_none_was_fitted(self):
        # so a consumer can read "offset" unconditionally
        self.pf.FIT_CONSTANT_OFFSET = False
        bt = self.pf.fit_threshold(self._two_populations(background=2500))
        self.assertEqual(bt["offset"], 0.0)
        self.assertEqual(len(bt["params"]), 7)
        self.assertEqual(bt["params"][6], 0.0)

    def test_the_widths_params_indices_are_unmoved_by_the_constant(self):
        # `_classify_peak_prominences` reads params[2] and params[5] for the
        # two standard deviations; appending the constant must not shift them
        bt = self.pf.fit_threshold(self._two_populations(background=2500))
        self.assertAlmostEqual(bt["params"][2], 300.0, delta=60.0)
        self.assertAlmostEqual(bt["params"][5], 300.0, delta=60.0)

    # -- what it must NOT touch ---------------------------------------------

    def test_the_constant_does_not_move_the_gaussian_crossing(self):
        # it is common to both curves, so it cancels out of g1 == g2
        without = PeakFinder._gaussian_intersection(100.0, 0.0, 10.0, 50.0, 20.0, 10.0)
        params = (100.0, 0.0, 10.0, 50.0, 20.0, 10.0, 37.0)
        with_offset = PeakFinder._gaussian_intersection(*params[:6])
        self.assertAlmostEqual(without, with_offset, places=12)

    def test_confidence_ignores_a_trailing_constant(self):
        # excluded by design, so a "constrained" threshold still reads 0.5
        # exactly at the crossing - see _classification_confidence
        values = np.array([-5.0, 0.0, 5.0, 10.0, 15.0])
        six = (100.0, 0.0, 10.0, 100.0, 10.0, 10.0)
        is_higher = values >= 5.0
        np.testing.assert_allclose(
            self.pf._classification_confidence(values, six, is_higher),
            self.pf._classification_confidence(values, six + (25.0,), is_higher),
        )

    def test_confidence_still_reads_a_half_at_the_crossing(self):
        params = (100.0, 0.0, 10.0, 100.0, 10.0, 10.0, 25.0)
        crossing = PeakFinder._gaussian_intersection(*params[:6])
        got = self.pf._classification_confidence(
            np.array([crossing]), params, np.array([True])
        )
        self.assertAlmostEqual(float(got[0]), 0.5, places=9)

    def test_a_near_zero_constant_does_not_trip_the_unconstrained_warning(self):
        # a relative-error test can never be passed by a parameter whose
        # correct value is zero, so the constant is exempt from it
        data = self._two_populations()
        self.pf.FIT_CONSTANT_OFFSET = True
        counts, _, centers = self.pf._histogram_for_fit(data)
        with self.assertNoLogs(PeakFinder.logger, level="WARNING"):
            self.pf._fit_and_check_double_gaussian(centers, counts)

    # -- the constrained refit ----------------------------------------------

    def test_the_constrained_refit_keeps_the_constant_free(self):
        data = self._two_populations(background=2500)
        popt, _, centers, counts = self._fit(data, True)
        m1, s1, m2, s2 = (float(popt[i]) for i in (1, 2, 4, 5))
        if m1 > m2:
            m1, s1, m2, s2 = m2, s2, m1, s1
        valley, method, _ = self.pf._threshold_between_populations(
            data, centers, counts, m1, s1, m2, s2, False
        )
        result = self.pf._fit_double_gaussian_bounded_at_valley(
            centers, counts, valley, popt
        )
        self.assertIsNotNone(result)
        fit, _ = result
        self.assertEqual(len(fit), 7)
        self.assertGreater(float(fit[6]), 0.0)

    def test_the_refit_stays_six_long_when_the_joint_fit_had_no_constant(self):
        # the refit carries the joint fit's constant rather than inventing one
        x, y = self._bimodal_for_valley()
        popt = np.array([868.0, 2491.0, 313.0, 1017.0, 4722.0, 520.0])
        result = self.pf._fit_double_gaussian_bounded_at_valley(x, y, 3524.0, popt)
        self.assertIsNotNone(result)
        fit, _ = result
        self.assertEqual(len(fit), 6)

    @staticmethod
    def _bimodal_for_valley(seed=5):
        rng = np.random.default_rng(seed)
        x = np.linspace(300, 8000, 70)
        bw = x[1] - x[0]
        intensity = (
            6119
            * np.exp(-0.5 * ((x - 2495) / 320) ** 2)
            / (320 * np.sqrt(2 * np.pi))
            * bw
            + 11816
            * np.exp(-0.5 * ((x - 4724) / 523) ** 2)
            / (523 * np.sqrt(2 * np.pi))
            * bw
        )
        return x, rng.poisson(np.clip(intensity, 0.01, None)).astype(float)

    def test_a_flat_tail_the_constant_absorbs_makes_the_refit_decline(self):
        # The one behaviour change the constant produces on the constrained
        # path, and an improvement. On this dataset the threshold search puts
        # the valley at 6383 - past the end of both populations - and the
        # six-parameter refit "succeeded" there by parking a broad, near-flat
        # higher component at 8324 with std 3883 to cover the sparse tail.
        # With a pedestal available that flat contribution goes to the
        # constant instead, the higher component collapses below the bin
        # width, and the existing guard declines rather than reporting a
        # component 5000 pA past any data. The joint fit is kept.
        rng = np.random.default_rng(1)
        data = np.concatenate(
            [
                rng.lognormal(np.log(1830) + 0.30**2, 0.30, 6500),
                rng.lognormal(np.log(3350) + 0.24**2, 0.24, 4600),
            ]
        )
        popt, _, centers, counts = self._fit(data, True)
        m1, s1, m2, s2 = (float(popt[i]) for i in (1, 2, 4, 5))
        if m1 > m2:
            m1, s1, m2, s2 = m2, s2, m1, s1
        valley, method, _ = self.pf._threshold_between_populations(
            data, centers, counts, m1, s1, m2, s2, False
        )
        self.assertGreater(valley, max(m1, m2), "this corner needs a tail valley")
        with self.assertLogs(PeakFinder.logger, level="WARNING") as captured:
            result = self.pf._fit_double_gaussian_bounded_at_valley(
                centers, counts, valley, popt
            )
        self.assertIsNone(result)
        self.assertTrue(
            any("collapsed a component" in line for line in captured.output),
            captured.output,
        )

    # -- the plot -----------------------------------------------------------

    def test_the_overlay_accepts_seven_parameters_and_draws_the_background(self):
        ax = MagicMock()
        self.pf._overlay_fitted_gaussians(
            ax,
            (100.0, 0.0, 10.0, 100.0, 30.0, 10.0, 12.0),
            np.linspace(-40.0, 70.0, 50),
            "lower",
            "higher",
            "test",
        )
        self.assertEqual(ax.plot.call_count, 2)
        ax.axhline.assert_called_once()
        self.assertEqual(ax.axhline.call_args[0][0], 12.0)
        # both component curves are drawn sitting on the pedestal
        for call in ax.plot.call_args_list:
            self.assertGreaterEqual(float(np.min(call[0][1])), 12.0 - 1e-9)

    def test_the_overlay_draws_no_background_line_when_there_is_none(self):
        # so a plot with no fitted pedestal looks as it did before
        ax = MagicMock()
        self.pf._overlay_fitted_gaussians(
            ax,
            (100.0, 0.0, 10.0, 100.0, 30.0, 10.0, 0.0),
            np.linspace(-40.0, 70.0, 50),
            "lower",
            "higher",
            "test",
        )
        self.assertEqual(ax.plot.call_count, 2)
        ax.axhline.assert_not_called()

    def test_the_overlay_still_rejects_a_wrong_length_params(self):
        ax = MagicMock()
        with self.assertLogs(PeakFinder.logger, level="WARNING"):
            self.pf._overlay_fitted_gaussians(
                ax, (1.0, 2.0, 3.0), np.linspace(0.0, 1.0, 5), "a", "b", "test"
            )
        ax.plot.assert_not_called()


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

    def _skewed(self, s_lower=0.30, seed=0):
        """
        Right-skewed lower population whose shoulder reaches the valley.

        Seed 0 rather than 1: on seed 1 the threshold search puts its valley at
        6383, past the end of both populations, so the refit there is not
        exercising the separation constraint these tests are about. That corner
        has a test of its own in `TestFitConstantOffset`.
        """
        rng = np.random.default_rng(seed)
        lower = rng.lognormal(np.log(1830) + s_lower**2, s_lower, 6500)
        upper = rng.lognormal(np.log(3350) + 0.24**2, 0.24, 4600)
        return np.concatenate([lower, upper])

    def test_returned_fit_satisfies_the_separation_constraint(self):
        data = self._skewed()
        counts, edges, centers = self.pf._histogram_for_fit(data)
        popt, one_pop = self.pf._fit_and_check_double_gaussian(centers, counts)
        self.assertIsNotNone(popt)
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt[:6])
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
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt[:6])
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
        a1, m1, s1, a2, m2, s2 = (float(p) for p in popt[:6])
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


# ---------------------------------------------------------------------------
# _classify_peak_prominences - which peaks are fitted and classified
# ---------------------------------------------------------------------------


class TestClassifyPeakProminences(unittest.TestCase):
    """
    Types 1, 2 and 3 are fitted and classified; everything else keeps NaN.

    The fit is taken on log10(normalized prominence), so the threshold the
    fit returns is in log units and the split has to happen there - the
    fixture's threshold of -1.0 is a prominence ratio of 10**-1 = 0.1.
    """

    NAN = np.nan
    FIT_RESULT = {
        "threshold": -1.0,
        "centers": np.array([-1.6, -0.5]),
        "params": (100.0, -1.6, 0.2, 100.0, -0.5, 0.2),
        "n_components": 2,
        "hist": (None, None),
    }

    def _run(self, filtered, normalized):
        pf = _make_pf()
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array(filtered, dtype=float),
                    "normalized_prominence": np.array(normalized, dtype=float),
                    "peak_id": [float(i) for i in range(len(filtered))],
                }
            }
        }
        pf.event_metadata = {0: {0: {}}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        return pf

    def test_types_1_2_and_3_are_fitted_and_others_are_not(self):
        """Types 0, -1 and the two star codes are excluded from the fit."""
        pf = self._run(
            [3.0, 1.0, 2.0, 0.0, -1.0, 4.0, 5.0],
            [0.20, 0.30, 0.40, 0.92, 0.93, 0.94, 0.95],
        )
        fitted = pf.fit_threshold.call_args[0][0]
        np.testing.assert_allclose(sorted(fitted), np.log10([0.20, 0.30, 0.40]))

    def test_the_fit_is_taken_on_the_log_of_the_normalized_prominence(self):
        """
        `fit_threshold` must see log10 values, not the ratios themselves - a
        Gaussian there is the log-normal the upper population actually is.
        """
        ratios = [0.10, 0.20, 0.50, 0.90]
        pf = self._run([3.0] * 4, ratios)
        fitted = pf.fit_threshold.call_args[0][0]
        np.testing.assert_allclose(sorted(fitted), np.log10(sorted(ratios)))

    def test_the_split_happens_in_log_space(self):
        """
        The threshold the fit returns is in log units, so it is compared
        against the log values: 10**-1.0 = 0.1 divides these four.
        """
        pf = self._run([3.0] * 4, [0.05, 0.09, 0.50, 0.90])
        classified = pf.sublevel_metadata[0][0]["classified"]
        np.testing.assert_array_equal(classified, [0.0, 0.0, 1.0, 1.0])

    def test_the_report_gets_ratios_not_log_units(self):
        """
        The classification stays in log space but the report is read by a
        person, so the threshold and centres are converted back with 10**x.
        """
        pf = self._run([3.0] * 3, [0.10, 0.30, 0.90])
        results = pf._peak_prominence_classification_results
        self.assertAlmostEqual(results["threshold"], 10.0**-1.0)
        np.testing.assert_allclose(results["centers"], 10.0 ** np.array([-1.6, -0.5]))

    def test_non_positive_prominences_are_dropped_from_the_log_fit(self):
        """
        Zero and negative ratios have no logarithm. They are dropped from the
        fit and left unclassified rather than becoming -inf and taking the
        histogram's range with them.
        """
        pf = self._run([3.0] * 4, [0.0, -0.5, 0.30, 0.90])
        fitted = pf.fit_threshold.call_args[0][0]
        np.testing.assert_allclose(sorted(fitted), np.log10([0.30, 0.90]))
        classified = pf.sublevel_metadata[0][0]["classified"]
        self.assertTrue(np.isnan(classified[0]))
        self.assertTrue(np.isnan(classified[1]))
        self.assertFalse(np.isnan(classified[2]))

    def test_declines_when_no_peak_is_eligible(self):
        """
        With no type 1, 2 or 3 peak there is nothing to fit; the columns are
        still allocated so a reader finds NaN rather than a missing key.
        """
        pf = self._run([0.0, -1.0, 4.0], [0.2, 0.5, 0.8])
        pf.fit_threshold.assert_not_called()
        self.assertTrue(np.all(np.isnan(pf.sublevel_metadata[0][0]["classified"])))
        self.assertTrue(
            np.all(np.isnan(pf.sublevel_metadata[0][0]["classification_confidence"]))
        )

    def test_linear_fit_when_the_log_scale_is_switched_off(self):
        """
        PROMINENCE_FIT_LOG_SCALE False fits the ratios directly, which is the
        only change needed to compare the two scales on one dataset.
        """
        pf = _make_pf()
        pf.PROMINENCE_FIT_LOG_SCALE = False
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0, 3.0, 3.0], dtype=float),
                    "normalized_prominence": np.array([0.1, 0.3, 0.9]),
                    "peak_id": [0.0, 1.0, 2.0],
                }
            }
        }
        pf.event_metadata = {0: {0: {}}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])

        fitted = pf.fit_threshold.call_args[0][0]
        np.testing.assert_allclose(sorted(fitted), [0.1, 0.3, 0.9])
        # and the report is not exponentiated on this path
        self.assertAlmostEqual(
            pf._peak_prominence_classification_results["threshold"], -1.0
        )

    def test_unfolded_reference_prefers_the_folding_fits_centre(self):
        """
        `_run_unfolded_level` prefers the folding fit's own lower centre over
        any per-event level, since it is the run-wide population mean.
        """
        pf = _make_pf()
        pf._classification_results = {"lower_center": 120.0}
        pf.event_metadata = {0: {0: {"unfolded_level": 50.0}}}
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0] * 3, dtype=float),
                    "normalized_prominence": np.array([0.10, 0.30, 0.90]),
                    "peak_id": [0.0, 1.0, 2.0],
                }
            }
        }
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        results = pf._peak_prominence_classification_results
        self.assertEqual(results["unfolded_reference"], 120.0)
        self.assertEqual(results["unfolded_reference_source"], "fitted unfolded centre")

    def test_unfolded_reference_falls_back_to_the_median_event_level(self):
        """
        With no folding fit available, the median of the per-event
        `unfolded_level` values stands in.
        """
        pf = _make_pf()
        pf.event_metadata = {
            0: {0: {"unfolded_level": 40.0}, 1: {"unfolded_level": 60.0}}
        }
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0] * 3, dtype=float),
                    "normalized_prominence": np.array([0.10, 0.30, 0.90]),
                    "peak_id": [0.0, 1.0, 2.0],
                },
                1: {
                    "filtered": np.array([], dtype=float),
                    "normalized_prominence": np.array([], dtype=float),
                    "peak_id": [],
                },
            }
        }
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        results = pf._peak_prominence_classification_results
        self.assertEqual(results["unfolded_reference"], 50.0)
        self.assertEqual(
            results["unfolded_reference_source"], "median per-event unfolded level"
        )

    def test_unfolded_reference_absent_when_neither_source_is_available(self):
        """With no folding fit and no per-event level, both come back None."""
        pf = self._run([3.0] * 3, [0.10, 0.30, 0.90])
        results = pf._peak_prominence_classification_results
        self.assertIsNone(results["unfolded_reference"])
        self.assertIsNone(results["unfolded_reference_source"])

    def test_report_carries_fitted_ratio_and_std_factor_fields(self):
        """
        The report dict carries the fitted (log10) values alongside the
        prominence-ratio conversions and the multiplicative std factors, so a
        reader gets all three unit systems for threshold, centres and std.
        """
        pf = self._run([3.0] * 3, [0.10, 0.30, 0.90])
        results = pf._peak_prominence_classification_results
        self.assertTrue(results["log_scale"])
        self.assertAlmostEqual(results["threshold_fitted"], -1.0)
        np.testing.assert_allclose(results["centers_fitted"], [-1.6, -0.5])
        np.testing.assert_allclose(results["stds_fitted"], [0.2, 0.2])
        np.testing.assert_allclose(results["std_factors"], 10.0 ** np.array([0.2, 0.2]))

    def test_std_is_reported_as_the_total_pa_span_of_one_sigma(self):
        """
        A log-space width is a multiplicative spread, so +/-1 sigma runs from
        centre/factor to centre*factor - not symmetric about the centre and so
        with no single "+/- x pA". What it has is a total width, and that is
        what the report carries: centre * (factor - 1/factor), in pA.
        """
        pf = _make_pf()
        pf._classification_results = {"lower_center": 689.3}
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0] * 3, dtype=float),
                    "normalized_prominence": np.array([0.10, 0.30, 0.90]),
                    "peak_id": [0.0, 1.0, 2.0],
                }
            }
        }
        pf.event_metadata = {0: {0: {}}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        results = pf._peak_prominence_classification_results

        expected = []
        for center_fitted, std in zip([-1.6, -0.5], [0.2, 0.2]):
            center_ratio = 10.0**center_fitted
            factor = 10.0**std
            expected.append(center_ratio * (factor - 1.0 / factor) * 689.3)
        np.testing.assert_allclose(results["std_currents"], expected)

        # and it is the width of the span the factor describes, so it agrees
        # with the two ends computed independently
        for position, center_ratio in enumerate(results["centers"]):
            factor = results["std_factors"][position]
            low = center_ratio / factor * 689.3
            high = center_ratio * factor * 689.3
            self.assertAlmostEqual(results["std_currents"][position], high - low)

    def test_std_currents_are_empty_without_a_reference_level(self):
        # no folding fit and no per-event level, so there is no pA scale
        pf = self._run([3.0] * 3, [0.10, 0.30, 0.90])
        self.assertEqual(pf._peak_prominence_classification_results["std_currents"], [])

    def test_a_linear_std_is_only_scaled_by_the_reference(self):
        # with no log transform the width is already a ratio
        pf = _make_pf()
        pf.PROMINENCE_FIT_LOG_SCALE = False
        pf._classification_results = {"lower_center": 500.0}
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0] * 3, dtype=float),
                    "normalized_prominence": np.array([0.1, 0.3, 0.9]),
                    "peak_id": [0.0, 1.0, 2.0],
                }
            }
        }
        pf.event_metadata = {0: {0: {}}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        results = pf._peak_prominence_classification_results
        np.testing.assert_allclose(results["std_currents"], [0.2 * 500.0, 0.2 * 500.0])

    def test_std_factors_empty_when_log_scale_is_off(self):
        """
        With `PROMINENCE_FIT_LOG_SCALE` off there is no multiplicative
        factor to report - the std is already a linear width.
        """
        pf = _make_pf()
        pf.PROMINENCE_FIT_LOG_SCALE = False
        pf.sublevel_metadata = {
            0: {
                0: {
                    "filtered": np.array([3.0] * 3, dtype=float),
                    "normalized_prominence": np.array([0.1, 0.3, 0.9]),
                    "peak_id": [0.0, 1.0, 2.0],
                }
            }
        }
        pf.event_metadata = {0: {0: {}}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_peak_prominences([0])
        results = pf._peak_prominence_classification_results
        self.assertFalse(results["log_scale"])
        self.assertEqual(results["std_factors"], [])


# ---------------------------------------------------------------------------
# _classify_translocation_direction - fit sample vs classified set
# ---------------------------------------------------------------------------


def _ecd_event(log_ratio):
    """
    Build one event's sublevel metadata with a chosen log10 ECD ratio.

    A single type-3 peak at index 1 makes the pre-peak ECD `csum[0]` and the
    post-peak ECD `csum[-1] - csum[1]`, so fixing the latter at 1 makes the
    ratio - and its log - whatever `csum[0]` is set to.
    """
    before = 10.0**log_ratio
    return {
        "filtered": np.array([np.nan, 3.0, np.nan]),
        "sublevel_cumulative_ecd": np.array([before, before + 1.0, before + 2.0]),
    }


class TestTranslocationDirectionFitSample(unittest.TestCase):
    """
    The fit is estimated from the percentile core, but every event with a
    usable ECD ratio must still be classified against the threshold it yields.

    Fitting the untrimmed array is what broke this pass: `_histogram_for_fit`
    takes its bin width from the IQR but its range from the extremes, so a few
    events several decades out leave the two real populations sharing a handful
    of bins, the six-parameter fit collapses onto one mode, and `n_components`
    coming back 1 declines the whole pass - every event ends up with no
    direction at all.
    """

    FIT_RESULT = {
        "threshold": 0.05,
        "centers": np.array([-0.3, 0.4]),
        "params": (100.0, -0.3, 0.1, 100.0, 0.4, 0.08),
        "n_components": 2,
        "hist": (None, None),
    }

    def _run(self, log_ratios):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {i: _ecd_event(r) for i, r in enumerate(log_ratios)}}
        pf.event_metadata = {0: {i: {} for i in range(len(log_ratios))}}
        pf.fit_threshold = MagicMock(return_value=dict(self.FIT_RESULT))
        pf._classify_translocation_direction([0])
        return pf

    @staticmethod
    def _core_and_extremes():
        # 90 events in a tight bimodal core, plus 5 extreme events at each end
        # standing in for near-zero pre- or post-barcode ECDs.
        core = list(np.linspace(-0.4, -0.2, 45)) + list(np.linspace(0.3, 0.5, 45))
        low = [-4.0, -3.9, -3.8, -3.7, -3.6]
        high = [3.6, 3.7, 3.8, 3.9, 4.0]
        return core, low, high

    def test_extremes_are_kept_out_of_the_fit(self):
        core, low, high = self._core_and_extremes()
        pf = self._run(low + core + high)
        fitted = pf.fit_threshold.call_args[0][0]
        self.assertEqual(fitted.size, len(core))
        self.assertGreater(float(np.min(fitted)), max(low))
        self.assertLess(float(np.max(fitted)), min(high))

    def test_every_event_is_still_classified(self):
        core, low, high = self._core_and_extremes()
        ratios = low + core + high
        pf = self._run(ratios)
        directions = [
            pf.event_metadata[0][i].get("translocation_direction")
            for i in range(len(ratios))
        ]
        self.assertEqual(len(directions), len(ratios))
        for i, direction in enumerate(directions):
            self.assertIn(
                direction,
                ("forward", "backward"),
                f"event {i} (log ratio {ratios[i]:.2f}) was left unclassified",
            )
        self.assertEqual(
            pf._translocation_direction_results["total_events"], len(ratios)
        )

    def test_the_extremes_land_on_the_side_the_threshold_puts_them(self):
        # The trim must not change which side of the threshold an event falls
        # on - it only changes what the threshold was estimated from.
        core, low, high = self._core_and_extremes()
        ratios = low + core + high
        pf = self._run(ratios)
        for i in range(len(low)):
            self.assertEqual(
                pf.event_metadata[0][i]["translocation_direction"], "backward"
            )
        for i in range(len(ratios) - len(high), len(ratios)):
            self.assertEqual(
                pf.event_metadata[0][i]["translocation_direction"], "forward"
            )

    def test_small_samples_are_fitted_whole(self):
        # Same gate as the case below, reached from the other direction:
        # six events cannot yield a core anywhere near the bin floor.
        ratios = [-0.3, -0.28, 0.4, 0.42, -4.0, 4.0]
        pf = self._run(ratios)
        fitted = pf.fit_threshold.call_args[0][0]
        self.assertEqual(fitted.size, len(ratios))

    def test_a_core_too_small_to_fit_falls_back_to_the_whole_array(self):
        # 25 events: the core would come out under the MIN_FIT_BINS floor, so
        # trimming would trade one bad fit for another. The full array is
        # used instead.
        ratios = list(np.linspace(-0.4, 0.5, 25))
        pf = self._run(ratios)
        fitted = pf.fit_threshold.call_args[0][0]
        self.assertEqual(fitted.size, len(ratios))


# ---------------------------------------------------------------------------
# get_plot_features - label contents
# ---------------------------------------------------------------------------


class TestPlotFeatureLabels(unittest.TestCase):
    """
    The legend must not claim a value the metadata does not carry: an
    unclassified peak has no class, and printing "Class: nan" reads as a
    classification that ran and failed rather than one never attempted.
    """

    NAN = np.nan

    def _sublevel(self, drop=()):
        filtered = [self.NAN, -1.0, 3.0, self.NAN]
        data = {
            "sublevel_start_times": np.array([0.0, 10.0, 20.0, 30.0]),
            "right_ips": np.zeros(4),
            "peak_id": [None, 1, 2, None],
            "peak_loc": np.array([0.0, 10.0, 20.0, 30.0]),
            "peak_height": np.full(4, 500.0),
            "filtered": np.array(filtered, dtype=float),
            "classified": np.array([self.NAN, self.NAN, 0.0, self.NAN]),
            "classification_confidence": np.array([self.NAN, self.NAN, 0.87, self.NAN]),
        }
        for key in drop:
            del data[key]
        return data

    def _event(self, **overrides):
        event = {
            "baseline_current": -16000.0,
            "baseline_stdev": 50.0,
            "unfolded_level": 400.0,
            "translocation_direction": "forward",
            "translocation_confidence": 1.0,
            "sequence": "1010",
            "bound_star": "long end",
        }
        event.update(overrides)
        return event

    def _run(self, event=None, sublevel=None):
        pf = _make_pf()
        pf.eventfitting_status = {0: True}
        pf.event_metadata = {0: {0: self._event() if event is None else event}}
        pf.sublevel_metadata = {
            0: {0: self._sublevel() if sublevel is None else sublevel}
        }
        return pf.get_plot_features(0, 0)

    def test_bound_star_shares_the_translocation_line(self):
        _, _, _, vlabel, _, _ = self._run()
        self.assertEqual(len(vlabel), 1)
        first_line = vlabel[0].split("\n")[0]
        self.assertIn("Forward translocation.", first_line)
        self.assertIn("Bound star: long end", first_line)

    def test_bound_star_omitted_when_absent(self):
        _, _, _, vlabel, _, _ = self._run(event=self._event(bound_star=None))
        self.assertNotIn("Bound star", vlabel[0])
        self.assertIn("Forward translocation.", vlabel[0])

    def test_bound_star_absent_key_does_not_raise(self):
        event = self._event()
        del event["bound_star"]
        _, _, _, vlabel, _, _ = self._run(event=event)
        self.assertNotIn("Bound star", vlabel[0])

    def test_missing_translocation_confidence_is_omitted_not_nan(self):
        _, _, _, vlabel, _, _ = self._run(
            event=self._event(translocation_confidence=None)
        )
        self.assertNotIn("Confidence", vlabel[0])
        self.assertNotIn("nan", vlabel[0])
        self.assertIn("Sequence: 1010", vlabel[0])

    def test_no_direction_yields_no_translocation_label(self):
        _, _, _, vlabel, _, _ = self._run(
            event=self._event(translocation_direction=None)
        )
        self.assertEqual(vlabel, [])

    def test_unclassified_peak_omits_class_and_confidence(self):
        _, _, _, _, _, plabel = self._run()
        # Peak #1 is the filter -1 peak: no classifier ever acted on it.
        unclassified = next(p for p in plabel if p.startswith("Peak #1"))
        self.assertIn("Filter: -1.0", unclassified)
        self.assertNotIn("Class", unclassified)
        self.assertNotIn("Confidence", unclassified)
        self.assertNotIn("nan", unclassified)

    def test_classified_peak_keeps_class_and_confidence(self):
        _, _, _, _, _, plabel = self._run()
        classified = next(p for p in plabel if p.startswith("Peak #2"))
        self.assertIn("Filter: 3.0", classified)
        self.assertIn("Class: 0.0", classified)
        self.assertIn("Confidence: 0.87", classified)

    def test_absent_classification_arrays_do_not_break_the_plot(self):
        # Classification never ran, so the arrays are missing entirely rather
        # than full of NaN. That must not take the whole figure down with it.
        _, _, _, _, _, plabel = self._run(
            sublevel=self._sublevel(drop=("classified", "classification_confidence"))
        )
        self.assertTrue(plabel)
        for entry in plabel:
            self.assertNotIn("Class", entry)
            self.assertNotIn("nan", entry)


# ---------------------------------------------------------------------------
# _classify_bound_star
# ---------------------------------------------------------------------------


def _star_event(
    filtered,
    prominence,
    direction,
    sequence="0000",
    max_blockage=None,
    unfolded_level=500.0,
    baseline_stdev=10.0,
    peak_width=None,
):
    """
    Build the (sublevel, event) metadata pair for one synthetic event.

    `filtered`, `prominence`, `max_blockage` and `peak_width` are per-sublevel
    and index-aligned, NaN on sublevels that are not peaks, exactly as
    _populate_sublevel_metadata builds them.

    Blockages default far clear of the floor - 2 × unfolded level + 3σ =
    1030 pA with these defaults and the fixture's Higher Filter Threshold of
    3 - so tests about position and prominence are not silently testing the
    depth criterion as well.

    `peak_width` defaults to **omitted**, not to a value, so that tests about
    position, prominence and depth are likewise not silently testing the
    widest-peak rule. Tests that mean to exercise that rule pass widths
    explicitly; one test pins the omitted case itself, since a database
    written before `peak_width` existed presents exactly that.
    """
    sublevel = {
        "filtered": np.array(filtered, dtype=float),
        "prominence": np.array(prominence, dtype=float),
        "max_blockage": np.array(
            [5000.0] * len(filtered) if max_blockage is None else max_blockage,
            dtype=float,
        ),
    }
    if peak_width is not None:
        sublevel["peak_width"] = np.array(peak_width, dtype=float)
    event = {
        "translocation_direction": direction,
        "sequence": sequence,
        "bound_star": None,
        "unfolded_level": unfolded_level,
        "baseline_stdev": baseline_stdev,
    }
    return sublevel, event


class TestClassifyBoundStar(unittest.TestCase):
    NAN = np.nan

    def _run(self, **cases):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {k: v[0] for k, v in cases.items()}}
        pf.event_metadata = {0: {k: v[1] for k, v in cases.items()}}
        pf._classify_bound_star([0])
        return pf

    def _label(self, pf, key):
        return pf.event_metadata[0][key]["bound_star"]

    def test_star_before_barcode_on_forward_event_is_long_end(self):
        # Forward means the pre-barcode arm is the long one, so a star before
        # the barcode is on the long arm.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
            )
        )
        self.assertEqual(self._label(pf, "ev"), "long end")

    def test_star_after_barcode_on_backward_event_is_long_end(self):
        # Backward puts the long arm after the barcode, so a star seen last in
        # the trace is on the same arm as the case above and must get the same
        # label. This pair is what makes the label an arm rather than a
        # position: opposite temporal positions, identical label.
        pf = self._run(
            ev=_star_event(
                [self.NAN, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 1.1, 1.0, 1.9, self.NAN],
                "backward",
            )
        )
        self.assertEqual(self._label(pf, "ev"), "long end")

    def test_star_before_barcode_on_backward_event_is_short_end(self):
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "backward",
            )
        )
        self.assertEqual(self._label(pf, "ev"), "short end")

    def test_most_prominent_candidate_decides(self):
        # Candidates either side of the barcode; the taller one at the end wins
        # and, on a backward event, reads as having gone through first.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 0.65, 1.10, 1.05, 1.08, 1.02, 1.90, self.NAN],
                "backward",
            )
        )
        self.assertEqual(self._label(pf, "ev"), "long end")
        self.assertEqual(pf._bound_star_results["multi_candidate"], 1)

    def test_equally_prominent_candidates_resolve_to_the_earlier_peak(self):
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 5.0, 1.0, 1.0, 5.0, self.NAN],
                "forward",
            )
        )
        self.assertEqual(self._label(pf, "ev"), "long end")

    def test_peak_inside_the_barcode_is_not_a_candidate(self):
        # A -1 peak between type-3 peaks has no first/last reading, so it is
        # ignored however prominent it is.
        pf = self._run(
            ev=_star_event(
                [self.NAN, 3.0, -1.0, 3.0, self.NAN],
                [self.NAN, 1.0, 9.9, 1.0, self.NAN],
                "forward",
            )
        )
        self.assertIsNone(self._label(pf, "ev"))
        self.assertEqual(pf._bound_star_results["no_star"], 1)

    def test_event_without_type3_peaks_gets_no_label(self):
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 1.0, self.NAN],
                [self.NAN, 2.0, 1.0, self.NAN],
                "forward",
                sequence="",
            )
        )
        self.assertIsNone(self._label(pf, "ev"))

    def test_star_without_a_direction_is_left_unlabelled_and_counted(self):
        # Events dropped by the percentile filter in
        # _classify_translocation_direction have no direction to correct
        # against, so they are reported separately rather than as "no star".
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                None,
            )
        )
        self.assertIsNone(self._label(pf, "ev"))
        self.assertEqual(pf._bound_star_results["unresolved_direction"], 1)
        self.assertEqual(pf._bound_star_results["no_star"], 0)

    def test_counts_cover_only_sequence_bearing_events(self):
        pf = self._run(
            with_seq=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
            ),
            without_seq=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
                sequence="",
            ),
        )
        results = pf._bound_star_results
        self.assertEqual(results["total_events"], 2)
        self.assertEqual(results["sequence_events"], 1)
        self.assertEqual(results["with_star"], 1)
        # The label itself is still written for the event with no sequence.
        self.assertEqual(self._label(pf, "without_seq"), "long end")

    def test_opposite_observations_agree_once_corrected(self):
        # A star seen first on a forward event and last on a backward one sit
        # on the same molecular end, and must come out with the same label.
        pf = self._run(
            fwd=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
            ),
            bwd=_star_event(
                [self.NAN, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 1.0, 1.0, 2.0, self.NAN],
                "backward",
            ),
        )
        results = pf._bound_star_results
        self.assertEqual(results["long_end"], 2)
        self.assertEqual(results["short_end"], 0)

    def test_peak_below_the_depth_floor_is_not_a_star(self):
        # Floor is 2 × unfolded level + 3σ = 1030; a 900 pA peak is a short
        # fold, not a bound star.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
                max_blockage=[self.NAN, 900.0, 400.0, 400.0, self.NAN],
            )
        )
        self.assertIsNone(self._label(pf, "ev"))
        self.assertEqual(pf._bound_star_results["no_star"], 1)
        self.assertEqual(pf._bound_star_results["no_height_reference"], 0)

    def test_peak_above_the_depth_floor_is_a_star(self):
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
                max_blockage=[self.NAN, 1031.0, 400.0, 400.0, self.NAN],
            )
        )
        self.assertEqual(self._label(pf, "ev"), "long end")

    def test_the_floor_follows_the_event_unfolded_level(self):
        # Identical peak, two events: the floor is per-event, so the same
        # blockage clears one unfolded level and not the other.
        pf = self._run(
            shallow=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
                max_blockage=[self.NAN, 1500.0, 400.0, 400.0, self.NAN],
                unfolded_level=500.0,
            ),
            deep=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
                max_blockage=[self.NAN, 1500.0, 400.0, 400.0, self.NAN],
                unfolded_level=1000.0,
            ),
        )
        self.assertEqual(self._label(pf, "shallow"), "long end")
        self.assertIsNone(self._label(pf, "deep"))

    def test_prominence_decides_only_among_peaks_clearing_the_floor(self):
        # The most prominent candidate is too shallow to be a star, so the
        # shorter-prominence peak that does clear the floor wins - and it sits
        # on the other side of the barcode, so the label turns on it.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 9.0, 1.0, 1.0, 2.0, self.NAN],
                "forward",
                max_blockage=[self.NAN, 900.0, 400.0, 400.0, 5000.0, self.NAN],
            )
        )
        self.assertEqual(self._label(pf, "ev"), "short end")
        # Only one candidate survived the floor, so nothing was collapsed.
        self.assertEqual(pf._bound_star_results["multi_candidate"], 0)

    def test_missing_unfolded_level_is_counted_apart_from_no_star(self):
        # Folding classification declined, so no event has an unfolded level
        # and none can be judged. That is not the same as having no star.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.8, 1.2, 1.0, self.NAN],
                "forward",
                unfolded_level=None,
            )
        )
        self.assertIsNone(self._label(pf, "ev"))
        self.assertEqual(pf._bound_star_results["no_height_reference"], 1)
        self.assertEqual(pf._bound_star_results["no_star"], 0)

    def test_no_candidates_outranks_a_missing_floor(self):
        # An event with no candidate peaks at all is starless regardless of
        # whether a floor could have been computed.
        pf = self._run(
            ev=_star_event(
                [self.NAN, 3.0, 3.0, self.NAN],
                [self.NAN, 1.2, 1.0, self.NAN],
                "forward",
                unfolded_level=None,
            )
        )
        self.assertEqual(pf._bound_star_results["no_star"], 1)
        self.assertEqual(pf._bound_star_results["no_height_reference"], 0)

    def test_per_sequence_buckets_split_by_sequence(self):
        pf = self._run(
            a_star=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
                sequence="1010",
            ),
            a_bare=_star_event(
                [self.NAN, 3.0, 3.0, self.NAN],
                [self.NAN, 1.0, 1.0, self.NAN],
                "forward",
                sequence="1010",
            ),
            b_star=_star_event(
                [self.NAN, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 1.0, 1.0, 2.0, self.NAN],
                "forward",
                sequence="0000",
            ),
        )
        per_sequence = pf._bound_star_results["per_sequence"]
        self.assertEqual(set(per_sequence), {"1010", "0000"})

        first = per_sequence["1010"]
        self.assertEqual(first["events"], 2)
        self.assertEqual(first["with_star"], 1)
        self.assertEqual(first["long_end"], 1)
        self.assertEqual(first["short_end"], 0)
        self.assertEqual(first["no_star"], 1)

        second = per_sequence["0000"]
        self.assertEqual(second["events"], 1)
        self.assertEqual(second["with_star"], 1)
        self.assertEqual(second["long_end"], 0)
        self.assertEqual(second["short_end"], 1)
        self.assertEqual(second["no_star"], 0)

    def test_per_sequence_buckets_reconcile_with_the_totals(self):
        pf = self._run(
            starred=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
                sequence="11",
            ),
            bare=_star_event(
                [self.NAN, 3.0, 3.0, self.NAN],
                [self.NAN, 1.0, 1.0, self.NAN],
                "forward",
                sequence="00",
            ),
            no_direction=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                None,
                sequence="00",
            ),
            # No sequence, so it must not appear in any bucket.
            unsequenced=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 2.0, 1.0, 1.0, self.NAN],
                "forward",
                sequence="",
            ),
        )
        results = pf._bound_star_results
        per_sequence = results["per_sequence"]
        self.assertEqual(set(per_sequence), {"11", "00"})
        for key in ("events", "with_star", "long_end", "short_end", "no_star"):
            total_key = "sequence_events" if key == "events" else key
            self.assertEqual(
                sum(row[key] for row in per_sequence.values()),
                results[total_key],
                f"{key} does not reconcile with the overall total",
            )
        for key in ("unresolved_direction", "no_height_reference"):
            self.assertEqual(
                sum(row[key] for row in per_sequence.values()),
                results[key],
            )
        # Each bucket's own columns account for every event in it.
        for row in per_sequence.values():
            self.assertEqual(
                row["with_star"]
                + row["no_star"]
                + row["unresolved_direction"]
                + row["no_height_reference"],
                row["events"],
            )

    def test_losing_candidates_keep_their_labels(self):
        # Only the winner is relabelled: the peaks the pass did not pick keep
        # their -1, so the peak-filtering statistics move by exactly one peak
        # per starred event.
        filtered = [self.NAN, -1.0, 3.0, 3.0, -1.0, self.NAN]
        pf = self._run(
            ev=_star_event(
                filtered,
                [self.NAN, 0.5, 1.0, 1.0, 4.0, self.NAN],
                "forward",
            )
        )
        # Index 4 is the most prominent candidate and lies after the barcode
        # on a forward event, so it is the short end: 4. Index 1 lost and is
        # untouched.
        np.testing.assert_array_equal(
            pf.sublevel_metadata[0]["ev"]["filtered"],
            np.array([self.NAN, -1.0, 3.0, 3.0, 4.0, self.NAN], dtype=float),
        )

    def test_star_label_names_the_end_it_is_bound_to(self):
        """
        The winning peak's own ``filtered`` is rewritten to 5 on the long arm
        and 4 on the short arm, matching the event's ``bound_star``.

        The four rows are the two trace positions crossed with the two
        directions. ``forward`` means the pre-barcode arm is the long one, so
        the arm the star sits on is "before" on a forward event and "after" on
        a backward one - which is why each trace position appears with both
        codes.
        """
        before = [self.NAN, -1.0, 3.0, 3.0, self.NAN]
        after = [self.NAN, 3.0, 3.0, -1.0, self.NAN]
        proms = [self.NAN, 4.0, 1.0, 4.0, self.NAN]
        for filtered, direction, star_idx, expected, end in (
            (before, "forward", 1, 5.0, "long end"),
            (before, "backward", 1, 4.0, "short end"),
            (after, "forward", 3, 4.0, "short end"),
            (after, "backward", 3, 5.0, "long end"),
        ):
            with self.subTest(direction=direction, star_idx=star_idx):
                pf = self._run(ev=_star_event(list(filtered), proms, direction))
                self.assertEqual(
                    pf.sublevel_metadata[0]["ev"]["filtered"][star_idx], expected
                )
                self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], end)

    def test_the_code_is_the_arm_and_not_the_position_in_the_trace(self):
        """
        The invariant behind types 4 and 5, stated on its own because it is the
        thing readers get wrong: the code names which arm of the construct the
        star is bound to and carries no information about where the star sits
        in the trace.

        Held two ways. Each trace position yields *both* codes depending on the
        direction, so position alone determines nothing; and each code is
        reached from *both* trace positions, so a code cannot be read back as a
        position. In particular a type-5 star is temporally last on a backward
        event, which is the case the old wording ("star translocates first")
        got wrong.
        """
        before = [self.NAN, -1.0, 3.0, 3.0, self.NAN]
        after = [self.NAN, 3.0, 3.0, -1.0, self.NAN]
        proms = [self.NAN, 4.0, 1.0, 4.0, self.NAN]

        codes = {}
        for position, filtered, star_idx in (
            ("before", before, 1),
            ("after", after, 3),
        ):
            for direction in ("forward", "backward"):
                pf = self._run(ev=_star_event(list(filtered), proms, direction))
                codes[(position, direction)] = pf.sublevel_metadata[0]["ev"][
                    "filtered"
                ][star_idx]

        for position in ("before", "after"):
            got = {codes[(position, d)] for d in ("forward", "backward")}
            self.assertEqual(
                got, {4.0, 5.0}, f"a star {position} the barcode fixed the code"
            )

        for code in (4.0, 5.0):
            positions = {
                position for (position, _), value in codes.items() if value == code
            }
            self.assertEqual(
                positions,
                {"before", "after"},
                f"type {code:.0f} is reachable from only one trace position",
            )

        # and the one that makes the temporal reading false outright
        self.assertEqual(codes[("after", "backward")], 5.0)

    def test_star_with_no_direction_keeps_its_minus_one(self):
        """
        The label is the arm, so a star whose arm cannot be resolved is not
        relabelled - an event with no translocation direction keeps -1.
        """
        filtered = [self.NAN, -1.0, 3.0, 3.0, self.NAN]
        pf = self._run(
            ev=_star_event(
                filtered,
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                None,
            )
        )
        np.testing.assert_array_equal(
            pf.sublevel_metadata[0]["ev"]["filtered"],
            np.array(filtered, dtype=float),
        )


# ---------------------------------------------------------------------------
# _classify_bound_star - the widest-peak rule
# ---------------------------------------------------------------------------


class TestBoundStarWidestPeakRule(unittest.TestCase):
    """
    A candidate that is the widest peak in its own event cannot be promoted.

    The depth floor tests only how deep a peak goes, never how long it lasts,
    so a carrier body or a long fold can clear it while being the wrong shape
    for a star. This rule filters the candidate pool rather than vetoing the
    winner, so a narrower candidate can still take the star.
    """

    NAN = np.nan

    def _run(self, **cases):
        pf = _make_pf()
        pf.sublevel_metadata = {0: {k: v[0] for k, v in cases.items()}}
        pf.event_metadata = {0: {k: v[1] for k, v in cases.items()}}
        pf._classify_bound_star([0])
        return pf

    def test_the_widest_peak_is_not_promoted(self):
        filtered = [self.NAN, -1.0, 3.0, 3.0, self.NAN]
        pf = self._run(
            ev=_star_event(
                filtered,
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 500.0, 100.0, 100.0, self.NAN],
            )
        )
        self.assertIsNone(pf.event_metadata[0]["ev"]["bound_star"])
        # and it keeps its -1 rather than becoming a 4 or a 5
        np.testing.assert_array_equal(
            pf.sublevel_metadata[0]["ev"]["filtered"],
            np.array(filtered, dtype=float),
        )

    def test_a_rejected_event_is_counted_apart_from_the_starless_ones(self):
        # it had a deep enough peak in the right place; that is a different
        # outcome from having no candidate at all
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 500.0, 100.0, 100.0, self.NAN],
            )
        )
        self.assertEqual(pf._bound_star_results["widest_peak"], 1)
        self.assertEqual(pf._bound_star_results["no_star"], 0)
        self.assertEqual(pf._bound_star_results["with_star"], 0)
        self.assertEqual(
            pf._bound_star_results["per_sequence"]["0000"]["widest_peak"], 1
        )

    def test_a_narrower_candidate_is_still_promoted(self):
        # the control: same geometry, but a type-3 peak is the widest
        filtered = [self.NAN, -1.0, 3.0, 3.0, self.NAN]
        pf = self._run(
            ev=_star_event(
                filtered,
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 100.0, 500.0, 100.0, self.NAN],
            )
        )
        self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], "long end")
        self.assertEqual(pf.sublevel_metadata[0]["ev"]["filtered"][1], 5.0)
        self.assertEqual(pf._bound_star_results["widest_peak"], 0)

    def test_the_rule_filters_the_pool_rather_than_vetoing_the_winner(self):
        # The more prominent candidate would have won on prominence alone, but
        # it is the event's widest peak. Dropping it hands the star to the
        # narrower candidate instead of losing it.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, -1.0, self.NAN],
                [self.NAN, 9.0, 1.0, 1.0, 2.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 900.0, 100.0, 100.0, 120.0, self.NAN],
            )
        )
        self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], "short end")
        filtered = pf.sublevel_metadata[0]["ev"]["filtered"]
        self.assertEqual(filtered[4], 4.0, "the narrow candidate should have won")
        self.assertEqual(filtered[1], -1.0, "the wide candidate keeps its -1")
        self.assertEqual(pf._bound_star_results["widest_peak"], 0)

    def test_peaks_tied_at_the_maximum_width_are_all_excluded(self):
        # the candidate is not uniquely widest, but it is AT the maximum
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 500.0, 500.0, 100.0, self.NAN],
            )
        )
        self.assertIsNone(pf.event_metadata[0]["ev"]["bound_star"])
        self.assertEqual(pf._bound_star_results["widest_peak"], 1)

    def test_a_candidate_with_no_width_of_its_own_is_left_alone(self):
        # it cannot be shown to be the widest, so the rule does not fire
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, self.NAN, 100.0, 100.0, self.NAN],
            )
        )
        self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], "long end")

    def test_absent_widths_skip_the_rule(self):
        # a database written before `peak_width` existed presents no widths at
        # all; the rule cannot be applied and must not block every star
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
            )
        )
        self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], "long end")
        self.assertEqual(pf._bound_star_results["widest_peak"], 0)

    def test_all_nan_widths_skip_the_rule(self):
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN] * 5,
            )
        )
        self.assertEqual(pf.event_metadata[0]["ev"]["bound_star"], "long end")

    def test_the_depth_floor_still_reports_first(self):
        # Ordering: an event with no unfolded level cannot be judged at all,
        # and that signal - it fires for a whole run when folding declines -
        # must not be masked by the width rule.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, self.NAN],
                "forward",
                unfolded_level=None,
                peak_width=[self.NAN, 500.0, 100.0, 100.0, self.NAN],
            )
        )
        self.assertEqual(pf._bound_star_results["no_height_reference"], 1)
        self.assertEqual(pf._bound_star_results["widest_peak"], 0)

    def test_a_peak_inside_the_barcode_does_not_shield_a_wide_candidate(self):
        # The maximum is taken over EVERY peak in the event, including ones
        # that are not candidates, so an interior peak counts toward it.
        pf = self._run(
            ev=_star_event(
                [self.NAN, -1.0, 3.0, -1.0, 3.0, self.NAN],
                [self.NAN, 4.0, 1.0, 1.0, 1.0, self.NAN],
                "forward",
                peak_width=[self.NAN, 500.0, 100.0, 300.0, 100.0, self.NAN],
            )
        )
        # 500 is still the maximum, so the candidate at index 1 is excluded
        self.assertIsNone(pf.event_metadata[0]["ev"]["bound_star"])
        self.assertEqual(pf._bound_star_results["widest_peak"], 1)


# ---------------------------------------------------------------------------
# _ClassificationWarningCollector
# ---------------------------------------------------------------------------


class TestClassificationWarningCollector(unittest.TestCase):
    """
    _post_process_events attaches a _ClassificationWarningCollector to
    self.logger for the duration of the classifier stages, so their
    WARNING-level messages can be surfaced in the saved report instead of
    living only in the log file. It is plain logging.Handler machinery with
    no PeakFinder state, so it is exercised directly against a throwaway
    logger rather than through _make_pf() and the full classification chain.
    """

    def setUp(self):
        self.logger = logging.getLogger("test._ClassificationWarningCollector")
        self.logger.setLevel(logging.DEBUG)
        self.collector = _ClassificationWarningCollector()
        self.logger.addHandler(self.collector)

    def tearDown(self):
        self.logger.removeHandler(self.collector)

    def test_captures_warning_level_messages(self):
        self.logger.warning("folding classification declined")
        self.assertEqual(self.collector.records, ["folding classification declined"])

    def test_ignores_info_and_debug(self):
        self.logger.debug("verbose detail")
        self.logger.info("starting post-processing")
        self.assertEqual(self.collector.records, [])

    def test_ignores_error_and_above(self):
        # Scoped to exactly WARNING, not "WARNING and up" - an ERROR-level
        # failure is already surfaced through _classification_results, so it
        # must not also be duplicated into the warnings section.
        self.logger.error("double-Gaussian fit failed")
        self.logger.critical("unrecoverable")
        self.assertEqual(self.collector.records, [])

    def test_preserves_order_and_duplicates(self):
        self.logger.warning("a")
        self.logger.warning("b")
        self.logger.warning("a")
        self.assertEqual(self.collector.records, ["a", "b", "a"])

    def test_message_is_formatted_without_level_or_logger_name(self):
        self.logger.warning("plain message %s", "with args")
        self.assertEqual(self.collector.records, ["plain message with args"])

    def test_removed_handler_stops_collecting(self):
        self.logger.removeHandler(self.collector)
        self.logger.warning("after removal")
        self.assertEqual(self.collector.records, [])
        # so tearDown's removeHandler on an already-removed handler is a
        # harmless no-op, matching what logging.Logger.removeHandler does
        self.logger.addHandler(self.collector)


if __name__ == "__main__":
    unittest.main()
