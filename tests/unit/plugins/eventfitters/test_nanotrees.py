"""
Tests for NanoTrees.py pure functions and class internals.

import the real poriscope package (it's on the path), but instantiate
NanoTrees via __new__ so we bypass __init__ and the event-loader requirement.
All settings are injected directly onto the instance.
"""

import unittest

import numpy as np

# --- Pure functions and data structures (no class needed) ---
from poriscope.plugins.eventfitters.NanoTrees import (
    BigConfidenceBooster,
    HackyList,
    NanoTrees,
    SingleSublevel,
    Sublevels,
    _check_exceptional_sublevel,
    _check_one_sided_percent_parity,
    extractContiniousRegions,
    normalHeightRefresh,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sublevels(*specs):
    """specs: list of (start, end, height)"""
    s = Sublevels()
    for start, end, height in specs:
        sl = SingleSublevel(start, end, height)
        s.insert(sl)
    return s


def _make_nt():
    """
    Return a NanoTrees instance with all required attributes injected,
    bypassing __init__ entirely so no event loader is needed.
    """
    nt = object.__new__(NanoTrees)
    nt.sublevel_metadata = {}
    nt.eventfitting_status = {}
    nt.event_lengths = {}
    nt.eventloader = None
    nt.logger = NanoTrees.logger
    nt.settings = {
        "Smallest Significant Sublevel": {"Value": 600.0},
        "Time Scaling": {"Value": 1.1},
        "Exceptional Sublevel Sensitivity": {"Value": 0.3},
    }
    return nt


def _automation_settings(std=1.0, rise_time=5):
    """Build a realistic hyperparameter dict like _set_automation_hyperparameters."""
    nt = _make_nt()
    return nt._set_automation_hyperparameters(std, rise_time)


# ---------------------------------------------------------------------------
# SingleSublevel
# ---------------------------------------------------------------------------


class TestSingleSublevel(unittest.TestCase):
    def test_init_positional(self):
        sl = SingleSublevel(2, 10, 3.5)
        self.assertEqual(sl.start, 2)
        self.assertEqual(sl.end, 10)
        self.assertAlmostEqual(sl.height, 3.5)

    def test_update(self):
        sl = SingleSublevel(0)
        sl.update(8, 1.5)
        self.assertEqual(sl.end, 8)
        self.assertAlmostEqual(sl.height, 1.5)

    def test_width(self):
        sl = SingleSublevel(3, 7, 0.0)
        self.assertEqual(sl.width, 4)

    def test_fetch_data(self):
        data = list(range(20))
        sl = SingleSublevel(4, 9, 0.0)
        self.assertEqual(list(sl.fetchData(data)), [4, 5, 6, 7, 8])

    def test_str_and_repr(self):
        sl = SingleSublevel(1, 5, 2.0)
        self.assertIn("1", str(sl))
        self.assertEqual(str(sl), repr(sl))


# ---------------------------------------------------------------------------
# HackyList
# ---------------------------------------------------------------------------


class TestHackyList(unittest.TestCase):
    def test_is_list(self):
        hl = HackyList([1, 2, 3])
        self.assertIsInstance(hl, list)
        self.assertEqual(hl[1], 2)

    def test_arbitrary_attributes(self):
        hl = HackyList([10, 20])
        hl.heights = [1.0, 2.0]
        hl.extra = {"k": "v"}
        self.assertEqual(hl.heights, [1.0, 2.0])
        self.assertEqual(hl.extra["k"], "v")


# ---------------------------------------------------------------------------
# Sublevels
# ---------------------------------------------------------------------------


class TestSublevels(unittest.TestCase):
    def test_insert_and_len(self):
        s = _make_sublevels((0, 5, 1.0), (5, 10, 2.0))
        self.assertEqual(len(s.sublevels), 2)

    def test_str(self):
        s = _make_sublevels((0, 5, 1.0))
        self.assertIn("<", str(s))

    def test_size(self):
        s = _make_sublevels((0, 4, 0.0), (4, 10, 0.0))
        self.assertEqual(s.size, 10)

    def test_edges(self):
        s = _make_sublevels((0, 3, 0.0), (3, 7, 0.0))
        self.assertEqual(s.edges, [0, 3, 7])

    def test_heights(self):
        s = _make_sublevels((0, 3, 1.5), (3, 7, 2.5))
        self.assertEqual(s.heights, [1.5, 2.5])

    def test_combined_region(self):
        s = _make_sublevels((0, 3, 0.0), (3, 8, 0.0))
        self.assertEqual(s.combinedRegion(0), (0, 8))

    def test_merge(self):
        s = _make_sublevels((0, 3, 1.0), (3, 8, 2.0), (8, 12, 3.0))
        s.merge(0, 1.5)
        self.assertEqual(len(s.sublevels), 2)
        self.assertAlmostEqual(s.sublevels[0].height, 1.5)
        self.assertEqual(s.sublevels[0].end, 8)

    def test_denormalize(self):
        s = _make_sublevels((0, 5, 1.0), (5, 10, -1.0))
        s.denormalize(100.0, 10.0)
        self.assertAlmostEqual(s.sublevels[0].height, 110.0)
        self.assertAlmostEqual(s.sublevels[1].height, 90.0)

    def test_filter_empty_sublevels(self):
        s = _make_sublevels((0, 0, 0.0), (0, 5, 1.0))
        s.filterEmptySublevels()
        self.assertEqual(len(s.sublevels), 1)

    def test_embeded_structure(self):
        s = _make_sublevels((0, 5, 1.0), (5, 10, 2.0))
        emb = s.embeded
        self.assertIsInstance(emb, HackyList)
        self.assertEqual(emb[0], 0)
        self.assertEqual(emb[-1], 10)
        self.assertIs(emb.self.sublevels, s)


# ---------------------------------------------------------------------------
# extractContiniousRegions
# ---------------------------------------------------------------------------


class TestExtractContiniousRegions(unittest.TestCase):
    def test_empty(self):
        w, h = extractContiniousRegions([])
        self.assertEqual(w, [0])
        self.assertEqual(h, [0])

    def test_single(self):
        w, h = extractContiniousRegions([5])
        self.assertEqual(w, [1])

    def test_two(self):
        w, h = extractContiniousRegions([3, 7])
        self.assertEqual(w, [2])

    def test_monotone_increasing(self):
        data = [1, 2, 3, 4]
        w, h = extractContiniousRegions(data)
        self.assertEqual(sum(w), 4)

    def test_up_down_pattern(self):
        data = [1, 3, 2, 4, 1]
        w, h = extractContiniousRegions(data)
        self.assertEqual(sum(w), len(data))

    def test_total_width_invariant(self):
        import random

        data = [random.random() for _ in range(50)]
        w, h = extractContiniousRegions(data)
        self.assertEqual(sum(w), 50)


# ---------------------------------------------------------------------------
# _check_one_sided_percent_parity
# ---------------------------------------------------------------------------


class TestCheckOneSidedPercentParity(unittest.TestCase):
    def test_balanced_passes(self):
        segment = np.array([0.9, 1.1, 0.8, 1.2, 1.0, 1.0])
        ok, check = _check_one_sided_percent_parity(segment, 1.0, 0.5)
        self.assertTrue(ok)

    def test_lopsided_fails(self):
        segment = np.array([2.0, 2.1, 2.2, 2.3, 2.4])
        ok, check = _check_one_sided_percent_parity(segment, 0.0, 0.1)
        self.assertFalse(ok)

    def test_returns_float_check(self):
        segment = np.ones(10)
        _, check = _check_one_sided_percent_parity(segment, 0.5, 0.9)
        self.assertIsInstance(float(check), float)


# ---------------------------------------------------------------------------
# BigConfidenceBooster
# ---------------------------------------------------------------------------


class TestBigConfidenceBooster(unittest.TestCase):
    def test_short_sublevel_skipped(self):
        data = np.zeros(20)
        s = _make_sublevels((0, 3, 0.5))  # width=3 < min=10
        original = s.sublevels[0].height
        result = BigConfidenceBooster(data, s, 10, 0.4)
        self.assertAlmostEqual(result.sublevels[0].height, original)

    def test_balanced_sublevel_unchanged(self):
        data = np.array([0.9, 1.1] * 10, dtype=float)
        s = _make_sublevels((0, 20, 1.0))
        result = BigConfidenceBooster(data, s, 5, 0.4)
        self.assertAlmostEqual(result.sublevels[0].height, 1.0, places=1)

    def test_lopsided_sublevel_corrected(self):
        data = np.ones(20) * 5.0
        s = _make_sublevels((0, 20, 0.0))  # height=0 but data=5 → very lopsided
        result = BigConfidenceBooster(data, s, 5, 0.1)
        self.assertGreater(result.sublevels[0].height, 0.0)


# ---------------------------------------------------------------------------
# normalHeightRefresh
# ---------------------------------------------------------------------------


class TestNormalHeightRefresh(unittest.TestCase):
    def test_refreshes_all_heights(self):
        raw = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        s = _make_sublevels((0, 3, 99.0), (3, 6, 99.0))

        def height_fn(settings, data, previousHeight=None):
            return float(np.mean(data))

        result = normalHeightRefresh({}, s, raw, height_fn)
        self.assertAlmostEqual(result.sublevels[0].height, 2.0)
        self.assertAlmostEqual(result.sublevels[1].height, 5.0)


# ---------------------------------------------------------------------------
# _check_exceptional_sublevel
# ---------------------------------------------------------------------------


class TestCheckExceptionalSublevel(unittest.TestCase):
    def _base_args(self):
        return dict(
            minDataPointsToBeSubLevel=5,
            exceptionalPeak_MinHeightStdAboveAndBelow=2.0,
            exceptionalPeak_WidthLowerBound=0,
            exceptionalPeak_BaseDifferenceStdAtleast=0.1,
            exceptionalSlope_MinHeightStdOfMinDiff=1.5,
            exceptionalSlope_WidthLowerBound=0,
            baseline_mean=0.0,
            baseline_std=1.0,
        )

    def test_disabled_returns_false(self):
        """Both width bounds 0 → exceptional check disabled."""
        s = _make_sublevels((0, 10, 1.0))
        self.assertFalse(
            _check_exceptional_sublevel(s.sublevels[0], 0, s, **self._base_args())
        )

    def test_peak_exception_both_above(self):
        """
        Peak: curr above both neighbours, differences large enough, base differs enough.
        prev=0, curr=5, next=3 → hd1=5-0=5, hd2=5-3=2, hd1*hd2=10>0 ✓
        |hd1|=5>1.5, |hd2|=2>1.5 ✓, width=10>3 ✓, |next-prev|=3>0.01 ✓
        """
        s = _make_sublevels((0, 10, 0.0), (10, 20, 5.0), (20, 30, 3.0))
        args = self._base_args()
        args["exceptionalPeak_WidthLowerBound"] = 3
        args["exceptionalPeak_MinHeightStdAboveAndBelow"] = 1.5
        args["exceptionalPeak_BaseDifferenceStdAtleast"] = 0.01
        result = _check_exceptional_sublevel(s.sublevels[1], 1, s, **args)
        self.assertTrue(result)

    def test_slope_exception_detected(self):
        """
        Slope: curr sits between prev and next (hd1*hd2 < 0).
        prev=0, curr=3, next=6 → hd1=3, hd2=-3, product=-9<0 ✓
        min(|3|,|3|)=3 > 2.0 ✓, width=10>5 ✓
        """
        s = _make_sublevels((0, 10, 0.0), (10, 20, 3.0), (20, 30, 6.0))
        args = self._base_args()
        args["exceptionalSlope_WidthLowerBound"] = 5
        args["exceptionalSlope_MinHeightStdOfMinDiff"] = 2.0
        result = _check_exceptional_sublevel(s.sublevels[1], 1, s, **args)
        self.assertTrue(result)

    def test_peak_fails_if_opposite_sign(self):
        """hd1 and hd2 have opposite signs → not a peak."""
        s = _make_sublevels((0, 10, 0.0), (10, 20, 3.0), (20, 30, 6.0))
        args = self._base_args()
        args["exceptionalPeak_WidthLowerBound"] = 3
        args["exceptionalPeak_MinHeightStdAboveAndBelow"] = 1.0
        args["exceptionalPeak_BaseDifferenceStdAtleast"] = 0.01
        result = _check_exceptional_sublevel(s.sublevels[1], 1, s, **args)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# NanoTrees – _set_automation_hyperparameters
# ---------------------------------------------------------------------------


class TestSetAutomationHyperparameters(unittest.TestCase):
    def test_required_keys_present(self):
        nt = _make_nt()
        params = nt._set_automation_hyperparameters(2.0, 10)
        for key in [
            "p3_numberOfStdAboveAndBelow",
            "p3_confidenceBoost_oneSidedPercentParity",
            "p3_confidenceBoost_minDataPointsToBeBoosted",
            "p4_minDataPointsToBeSubLevel",
            "p4_numberOfStdAboveAndBelow",
            "p4_exceptionalPeak_WidthLowerBound",
            "p4_exceptionalSlope_WidthLowerBound",
            "p5_numberOfStdAboveAndBelow",
            "p6_baselineStdThreshold",
            "directionalThreshold",
            "shortSublevelDefinition",
        ]:
            self.assertIn(key, params)

    def test_std_propagates(self):
        nt = _make_nt()
        params = nt._set_automation_hyperparameters(3.0, 5)
        self.assertEqual(params["p3_numberOfStdAboveAndBelow"], 3.0)

    def test_p4_min_datapoints_is_int(self):
        nt = _make_nt()
        params = nt._set_automation_hyperparameters(1.0, 8)
        self.assertIsInstance(params["p4_minDataPointsToBeSubLevel"], int)

    def test_zero_sensitivity_disables_exceptional(self):
        nt = _make_nt()
        nt.settings["Exceptional Sublevel Sensitivity"]["Value"] = 0.0
        params = nt._set_automation_hyperparameters(1.0, 10)
        self.assertEqual(params["p4_exceptionalPeak_WidthLowerBound"], 0)
        self.assertEqual(params["p4_exceptionalSlope_WidthLowerBound"], 0)


# ---------------------------------------------------------------------------
# NanoTrees – l50_max_height
# ---------------------------------------------------------------------------


class TestL50MaxHeight(unittest.TestCase):
    def setUp(self):
        self.nt = _make_nt()
        self.settings = {"shortSublevelDefinition": 4}

    def test_long_sublevel_uses_mean_of_second_half(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        h = self.nt.l50_max_height(self.settings, data, previousHeight=None)
        self.assertAlmostEqual(h, np.mean([5.0, 6.0, 7.0, 8.0]))

    def test_short_positive_uses_max(self):
        data = np.array([0.5, 1.0, 1.5])  # len=3 < shortSublevelDefinition=4
        h = self.nt.l50_max_height(self.settings, data, previousHeight=0.0)
        self.assertAlmostEqual(h, 1.5)

    def test_short_negative_uses_min(self):
        data = np.array([-3.0, -2.0, -1.0])
        h = self.nt.l50_max_height(self.settings, data, previousHeight=0.0)
        self.assertAlmostEqual(h, -3.0)

    def test_short_no_previous_uses_mean_of_second_half(self):
        data = np.array([1.0, 2.0, 3.0])
        h = self.nt.l50_max_height(self.settings, data, previousHeight=None)
        self.assertAlmostEqual(h, np.mean([2.0, 3.0]))


# ---------------------------------------------------------------------------
# NanoTrees – get_rise_time / get_skip_region
# ---------------------------------------------------------------------------


class TestRiseTimeHelpers(unittest.TestCase):
    def setUp(self):
        self.nt = _make_nt()

    def test_get_rise_time_returns_int(self):
        data = np.array([1, 2, 1, 2, 3, 1, 2], dtype=float)
        rt = self.nt.get_rise_time(data)
        self.assertIsInstance(rt, int)
        self.assertGreater(rt, 0)

    def test_get_skip_region_returns_int(self):
        data = np.array([1, 2, 1, 2, 3, 1, 2], dtype=float)
        sr = self.nt.get_skip_region(data, quantile=0.95)
        self.assertIsInstance(sr, int)
        self.assertGreater(sr, 0)

    def test_get_skip_region_gte_rise_time(self):
        data = np.random.randn(100)
        rt = self.nt.get_rise_time(data)
        sr = self.nt.get_skip_region(data)
        self.assertGreaterEqual(sr, rt)


# ---------------------------------------------------------------------------
# NanoTrees – _pass3
# ---------------------------------------------------------------------------


class TestPass3(unittest.TestCase):
    def _s(self, std=0.5):
        return _automation_settings(std=std, rise_time=5)

    def test_single_flat_level(self):
        nt = _make_nt()
        data = np.ones(20) * 2.0
        sub = nt._pass3(self._s(), data)
        self.assertEqual(sum(s.width for s in sub.sublevels), 20)

    def test_two_distinct_levels(self):
        nt = _make_nt()
        data = np.concatenate([np.zeros(15), np.ones(15) * 5.0])
        sub = nt._pass3(self._s(), data)
        self.assertEqual(sum(s.width for s in sub.sublevels), 30)

    def test_total_width_preserved(self):
        nt = _make_nt()
        data = np.random.randn(40)
        sub = nt._pass3(self._s(), data)
        self.assertEqual(sum(s.width for s in sub.sublevels), 40)

    def test_raises_on_empty(self):
        nt = _make_nt()
        with self.assertRaises((ValueError, IndexError)):
            nt._pass3(self._s(), np.array([]))


# ---------------------------------------------------------------------------
# NanoTrees – _pass4
# ---------------------------------------------------------------------------


class TestPass4(unittest.TestCase):
    def _s(self):
        return _automation_settings(std=1.0, rise_time=3)

    def test_wide_sublevels_unchanged(self):
        nt = _make_nt()
        raw = np.concatenate([np.zeros(20), np.ones(20) * 5.0, np.zeros(20)])
        sub = _make_sublevels((0, 20, 0.0), (20, 40, 5.0), (40, 60, 0.0))
        result = nt._pass4(self._s(), sub, raw)
        self.assertEqual(len(result.sublevels), 3)

    def test_short_leading_removed(self):
        nt = _make_nt()
        raw = np.concatenate([np.zeros(2), np.ones(15) * 5.0, np.zeros(15)])
        sub = _make_sublevels((0, 2, 0.0), (2, 17, 5.0), (17, 32, 0.0))
        result = nt._pass4(self._s(), sub, raw)
        self.assertLess(len(result.sublevels), 3)

    def test_short_trailing_removed(self):
        nt = _make_nt()
        raw = np.concatenate([np.zeros(15), np.ones(15) * 5.0, np.zeros(2)])
        sub = _make_sublevels((0, 15, 0.0), (15, 30, 5.0), (30, 32, 0.0))
        result = nt._pass4(self._s(), sub, raw)
        self.assertLess(len(result.sublevels), 3)


# ---------------------------------------------------------------------------
# NanoTrees – _pass5
# ---------------------------------------------------------------------------


class TestPass5(unittest.TestCase):
    def _s(self):
        return _automation_settings(std=1.0, rise_time=5)

    def test_merges_close_heights(self):
        nt = _make_nt()
        raw = np.concatenate([np.ones(5), np.ones(5) * 1.05, np.ones(5) * 10.0])
        sub = _make_sublevels((0, 5, 1.0), (5, 10, 1.05), (10, 15, 10.0))
        result = nt._pass5(self._s(), sub, raw)
        self.assertLess(len(result.sublevels), 3)

    def test_preserves_distinct_heights(self):
        nt = _make_nt()
        raw = np.concatenate([np.zeros(10), np.ones(10) * 5.0, np.ones(10) * 10.0])
        sub = _make_sublevels((0, 10, 0.0), (10, 20, 5.0), (20, 30, 10.0))
        result = nt._pass5(self._s(), sub, raw)
        self.assertEqual(len(result.sublevels), 3)

    def test_two_sublevels_not_merged(self):
        """_pass5 stops merging if fewer than 3 sublevels remain."""
        nt = _make_nt()
        raw = np.concatenate([np.zeros(10), np.ones(10) * 5.0])
        sub = _make_sublevels((0, 10, 0.0), (10, 20, 5.0))
        result = nt._pass5(self._s(), sub, raw)
        self.assertEqual(len(result.sublevels), 2)


# ---------------------------------------------------------------------------
# NanoTrees – _pass6
# ---------------------------------------------------------------------------


class TestPass6(unittest.TestCase):
    def _s(self):
        return _automation_settings()

    def test_all_baseline_returns_single_zero_sublevel(self):
        nt = _make_nt()
        raw = np.zeros(20)
        sub = _make_sublevels((0, 10, 0.0), (10, 20, 0.0))
        result = nt._pass6(self._s(), sub, raw)
        self.assertEqual(len(result.sublevels), 1)
        self.assertAlmostEqual(result.sublevels[0].height, 0.0)

    def test_negative_event_is_preserved(self):
        nt = _make_nt()
        raw = np.zeros(30)
        sub = _make_sublevels((0, 5, 0.0), (5, 25, -5.0), (25, 30, 0.0))
        result = nt._pass6(self._s(), sub, raw)
        heights = [sl.height for sl in result.sublevels]
        self.assertIn(-5.0, heights)

    def test_positive_event_is_preserved(self):
        nt = _make_nt()
        raw = np.zeros(30)
        sub = _make_sublevels((0, 5, 0.0), (5, 25, 6.0), (25, 30, 0.0))
        result = nt._pass6(self._s(), sub, raw)
        heights = [sl.height for sl in result.sublevels]
        self.assertIn(6.0, heights)

    def test_output_edges_span_full_raw(self):
        nt = _make_nt()
        raw = np.zeros(30)
        sub = _make_sublevels((0, 5, 0.0), (5, 25, -5.0), (25, 30, 0.0))
        result = nt._pass6(self._s(), sub, raw)
        starts = [sl.start for sl in result.sublevels]
        ends = [sl.end for sl in result.sublevels]
        self.assertEqual(min(starts), 0)
        self.assertEqual(max(ends), 30)


# ---------------------------------------------------------------------------
# NanoTrees – _pass7
# ---------------------------------------------------------------------------


class TestPass7(unittest.TestCase):
    def _s(self):
        return _automation_settings()

    def test_does_not_crash(self):
        nt = _make_nt()
        raw = np.array([1.0, 2.0, 3.0, 2.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        sub = _make_sublevels((0, 5, 2.0), (5, 10, 4.0))
        result = nt._pass7(self._s(), sub, raw)
        self.assertIsNotNone(result)

    def test_total_width_nonzero(self):
        nt = _make_nt()
        raw = np.concatenate([np.zeros(10), np.ones(10) * 3.0])
        sub = _make_sublevels((0, 10, 0.0), (10, 20, 3.0))
        result = nt._pass7(self._s(), sub, raw)
        total = sum(sl.width for sl in result.sublevels)
        self.assertGreater(total, 0)

    def test_short_end_no_crash(self):
        """Sublevel ending at index < 2 should be skipped gracefully."""
        nt = _make_nt()
        raw = np.array([1.0, 2.0, 1.0, 2.0, 3.0], dtype=float)
        sub = _make_sublevels((0, 1, 1.0), (1, 5, 2.0))
        result = nt._pass7(self._s(), sub, raw)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# NanoTrees – _slope_height_adjust
# ---------------------------------------------------------------------------


class TestSlopeHeightAdjust(unittest.TestCase):
    def _s(self):
        return _automation_settings()

    def test_monotone_sublevel_adjusted(self):
        nt = _make_nt()
        raw = np.array([0.0] * 5 + [1.0, 2.0, 3.0, 4.0, 5.0] + [6.0] * 5, dtype=float)
        sub = _make_sublevels((0, 5, 0.0), (5, 10, 3.0), (10, 15, 6.0))
        result = nt._slope_height_adjust(self._s(), sub, raw)
        self.assertIsNotNone(result)

    def test_non_monotone_sublevel_not_adjusted(self):
        nt = _make_nt()
        raw = np.array([0.0] * 5 + [5.0] * 5 + [0.0] * 5, dtype=float)
        sub = _make_sublevels((0, 5, 0.0), (5, 10, 5.0), (10, 15, 0.0))
        original = sub.sublevels[1].height
        result = nt._slope_height_adjust(self._s(), sub, raw)
        self.assertAlmostEqual(result.sublevels[1].height, original)

    def test_single_sublevel_no_crash(self):
        nt = _make_nt()
        raw = np.ones(10, dtype=float)
        sub = _make_sublevels((0, 10, 1.0))
        result = nt._slope_height_adjust(self._s(), sub, raw)
        self.assertEqual(len(result.sublevels), 1)


# ---------------------------------------------------------------------------
# NanoTrees – _ml_automation
# ---------------------------------------------------------------------------


class TestMlAutomation(unittest.TestCase):
    def test_output_length_matches_input(self):
        nt = _make_nt()
        data = np.concatenate([np.zeros(15), np.ones(15) * 3.0, np.zeros(15)])
        result = nt._ml_automation(data, searchStart=3, searchEnd=8)
        self.assertEqual(len(result), len(data))

    def test_output_is_ndarray(self):
        nt = _make_nt()
        data = np.random.randn(50)
        result = nt._ml_automation(data, searchStart=3, searchEnd=7)
        self.assertIsInstance(result, np.ndarray)

    def test_knee_none_fallback(self):
        """Flat data makes knee hard to find — should not crash."""
        nt = _make_nt()
        data = np.ones(30)
        result = nt._ml_automation(data, searchStart=3, searchEnd=6)
        self.assertEqual(len(result), 30)


# ---------------------------------------------------------------------------
# NanoTrees – construct_fitted_event
# ---------------------------------------------------------------------------


class TestConstructFittedEvent(unittest.TestCase):
    def test_returns_none_when_no_sublevel_metadata(self):
        nt = _make_nt()
        self.assertIsNone(nt.construct_fitted_event(0, 0))

    def test_returns_none_for_wrong_channel(self):
        nt = _make_nt()
        nt.sublevel_metadata = {1: {}}
        nt.eventfitting_status = {1: True}
        self.assertIsNone(nt.construct_fitted_event(0, 0))

    def test_returns_none_fitting_not_complete(self):
        nt = _make_nt()
        nt.sublevel_metadata = {0: {}}
        nt.eventfitting_status = {0: False}
        self.assertIsNone(nt.construct_fitted_event(0, 0))

    def test_missing_event_id_returns_none(self):
        from unittest.mock import MagicMock

        nt = _make_nt()
        nt.sublevel_metadata = {0: {99: {}}}  # only index 99, not 0
        nt.eventfitting_status = {0: True}
        nt.event_lengths = {0: {0: 100}}
        nt.eventloader = MagicMock()
        nt.eventloader.get_samplerate.return_value = 1e6
        self.assertIsNone(nt.construct_fitted_event(0, 0))


# ---------------------------------------------------------------------------
# NanoTrees – _define_* metadata types and units
# ---------------------------------------------------------------------------


class TestDefineMetadata(unittest.TestCase):
    def setUp(self):
        self.nt = _make_nt()

    def test_event_metadata_types_all_float(self):
        t = self.nt._define_event_metadata_types()
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
        ]:
            self.assertIn(key, t)
            self.assertIs(t[key], float)

    def test_sublevel_metadata_types_all_float(self):
        t = self.nt._define_sublevel_metadata_types()
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
            self.assertIn(key, t)
            self.assertIs(t[key], float)

    def test_event_metadata_units(self):
        u = self.nt._define_event_metadata_units()
        self.assertEqual(u["duration"], "us")
        self.assertEqual(u["fitted_ecd"], "pC")
        self.assertEqual(u["max_blockage"], "pA")

    def test_sublevel_metadata_units(self):
        u = self.nt._define_sublevel_metadata_units()
        self.assertEqual(u["sublevel_current"], "pA")
        self.assertEqual(u["sublevel_duration"], "us")
        self.assertEqual(u["sublevel_raw_ecd"], "pC")


# ---------------------------------------------------------------------------
# NanoTrees – _populate_event_metadata
# ---------------------------------------------------------------------------


class TestPopulateEventMetadata(unittest.TestCase):
    def _meta(self):
        n = 5
        return {
            "sublevel_duration": np.ones(n) * 10.0,
            "sublevel_fitted_ecd": np.ones(n) * 0.1,
            "sublevel_raw_ecd": np.ones(n) * 0.09,
            "sublevel_blockage": np.array([0.0, 1.0, 2.0, 1.5, 0.0]),
            "sublevel_max_deviation": np.array([0.0, 1.5, 2.5, 1.0, 0.0]),
        }

    def test_all_keys_present(self):
        nt = _make_nt()
        result = nt._populate_event_metadata(np.zeros(50), 1e6, 0.0, 1.0, self._meta())
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
        ]:
            self.assertIn(key, result)

    def test_duration_sums_inner_sublevels(self):
        nt = _make_nt()
        result = nt._populate_event_metadata(np.zeros(50), 1e6, 0.0, 1.0, self._meta())
        self.assertAlmostEqual(result["duration"], 30.0)

    def test_max_blockage_correct(self):
        nt = _make_nt()
        result = nt._populate_event_metadata(np.zeros(50), 1e6, 0.0, 1.0, self._meta())
        self.assertAlmostEqual(result["max_blockage"], 2.0)

    def test_min_blockage_correct(self):
        nt = _make_nt()
        result = nt._populate_event_metadata(np.zeros(50), 1e6, 0.0, 1.0, self._meta())
        self.assertAlmostEqual(result["min_blockage"], 1.0)


# ---------------------------------------------------------------------------
# NanoTrees – noop overrides
# ---------------------------------------------------------------------------


class TestNoopOverrides(unittest.TestCase):
    def setUp(self):
        self.nt = _make_nt()

    def test_init_returns_none(self):
        self.assertIsNone(self.nt._init())

    def test_pre_process_returns_none(self):
        self.assertIsNone(self.nt._pre_process_events(0))

    def test_post_process_returns_none(self):
        self.assertIsNone(self.nt._post_process_events(0))

    def test_close_resources_returns_none(self):
        self.assertIsNone(self.nt.close_resources())

    def test_validate_settings_returns_none(self):
        self.assertIsNone(self.nt._validate_settings({}))


if __name__ == "__main__":
    unittest.main()
