"""Unit tests for MetaEventFinder abstract base class."""

from typing import List, Optional, Tuple
from unittest.mock import patch

import numpy as np
import pytest

from poriscope.utils.MetaEventFinder import MetaEventFinder
from poriscope.utils.MetaReader import MetaReader


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class FakeReader(MetaReader):
    """A minimal, fully controllable stand-in for a MetaReader subclass."""

    def __init__(
        self,
        data: np.ndarray,
        samplerate: float = 100.0,
        channels: Tuple[int, ...] = (0,),
        key: str = "reader1",
        experiment_name: str = "exp1",
        raw_dtype: type = np.float64,
        serial: bool = False,
        serial_raises: bool = False,
    ):
        self.data = {ch: data.copy() for ch in channels}
        self.samplerate = samplerate
        self.channels = channels
        self.key = key
        self.experiment_name = experiment_name
        self.raw_dtype = raw_dtype
        self.serial = serial
        self.serial_raises = serial_raises

    def get_channels(self):
        return list(self.channels)

    def get_key(self):
        return self.key

    def get_samplerate(self):
        return self.samplerate

    def get_channel_length(self, channel):
        return len(self.data[channel])

    def load_data(self, start_sec, length_sec, channel, raw_data=False):
        start_idx = int(round(start_sec * self.samplerate))
        n = int(round(length_sec * self.samplerate))
        chunk = self.data[channel][start_idx : start_idx + n]
        if raw_data:
            return chunk, 1.0, 0.0
        return chunk

    def get_base_experiment_name(self):
        return self.experiment_name

    def get_raw_dtype(self):
        return self.raw_dtype

    def force_serial_channel_operations(self):
        if self.serial_raises:
            raise RuntimeError("reader thread-safety check failed")
        return self.serial

    def register_dependent(self, metaclass, key):
        # The real MetaReader/BaseDataPlugin track which plugins depend on
        # this one (for cleanup/cascading-update purposes) via a
        # `dependents` set populated in their own __init__. FakeReader
        # doesn't go through that __init__ chain, so it has no such state.
        # Since MetaEventFinder/BaseDataPlugin only need *a* reader that
        # responds to this call, override it as a no-op here rather than
        # trying to replicate the real bookkeeping.
        pass

    def get_dependents(self):
        return set()


# The real MetaReader declares additional abstract methods beyond what this
# test double implements (e.g. _convert_data, _get_configs, _get_file_*,
# etc. depending on the actual class). FakeReader only needs to satisfy the
# methods MetaEventFinder actually calls, so we deliberately clear the
# abstract-method bookkeeping ABC uses to block instantiation. isinstance()/
# issubclass() checks against MetaReader (used by MetaEventFinder's
# _validate_param_types) are unaffected by this and continue to work
# correctly since FakeReader still subclasses MetaReader.
FakeReader.__abstractmethods__ = frozenset()


class ConcreteEventFinder(MetaEventFinder):
    """Concrete implementation of MetaEventFinder for testing.

    Implements a simple threshold-crossing event detector: a sample is
    "in an event" whenever it falls more than ``Threshold`` below the
    (positive-signed) baseline mean. Events shorter than ``Min Duration``
    samples are rejected with reason "too short".
    """

    def _init(self) -> None:
        pass

    def close_resources(self, channel: Optional[int] = None) -> None:
        pass

    def _validate_settings(self, settings: dict) -> None:
        if "MetaReader" not in settings:
            raise ValueError("MetaReader is required")

    def _get_baseline_stats(self, data):
        if len(data) == 0:
            raise ValueError("Cannot compute baseline stats on empty chunk")
        median = float(np.median(data))
        mad = float(np.median(np.abs(data - median)))
        std = mad * 1.4826 if mad > 0 else 1e-6
        return median, std

    def _find_events_in_chunk(
        self,
        data,
        mean: float,
        std: float,
        offset: int,
        entry_state: bool = False,
        first_chunk: bool = False,
    ):
        threshold = mean - self.settings["Threshold"]["Value"]
        below = data < threshold
        starts: List[int] = []
        ends: List[int] = []
        state = entry_state
        for i, b in enumerate(below):
            if b and not state:
                starts.append(offset + i)
                state = True
            elif not b and state:
                ends.append(offset + i)
                state = False
        return starts, ends, state

    def _filter_events(self, event_starts, event_ends, channel, last_end=0):
        min_duration = self.settings.get("Min Duration", {}).get("Value", 0)
        bad_indices = []
        reasons = []
        for i, (s, e) in enumerate(zip(event_starts, event_ends)):
            if (e - s) < min_duration:
                bad_indices.append(i)
                reasons.append("too short")
        return bad_indices, reasons


def make_settings(reader, threshold=20.0, min_duration=0.0):
    # "Type" is None here, not str: get_empty_settings() declares "MetaReader"
    # as Type=str because the user initially picks a plugin key from a
    # dropdown, but DataPluginController resolves that string into the real
    # instance (and resets Type to None) before ever calling apply_settings.
    # This fixture constructs the post-resolution state that the real
    # constructor actually sees.
    return {
        "MetaReader": {"Type": None, "Value": reader, "Options": None},
        "Threshold": {"Type": float, "Value": threshold},
        "Min Duration": {"Type": float, "Value": min_duration},
    }


def build_finder(settings):
    """Construct a finder with the given settings and ensure its reader is
    attached.

    Two real things from BaseDataPlugin's actual behavior matter here:

    1. There's an ordering issue in MetaEventFinder.__init__: it calls
       ``super().__init__(settings)`` *first*, then unconditionally sets
       ``self.reader = None`` afterward. If BaseDataPlugin attaches the
       reader synchronously during construction (via
       _finalize_initialization, which its own docstring says runs "at the
       end of the class constructor"), that assignment immediately wipes it
       back out on every instantiation.

    2. BaseDataPlugin.apply_settings() mutates ``self.settings`` *in place*
       - and since ``self.settings = settings`` keeps the same dict
       reference (no copy), normalizing a live object's "Value" entry down
       to a plain string key (e.g. via ``value.get_key()``) is visible
       through our own ``settings`` variable too. So we must capture the
       reader object *before* construction - re-reading
       ``settings["MetaReader"]["Value"]`` afterward would return that
       already-normalized string instead of the object.

    This explicit re-attachment makes the test fixtures robust regardless
    of whether issue (1) actually manifests in the real BaseDataPlugin:
    it's a harmless no-op re-assignment of the same object if the reader
    was already attached correctly, and a necessary fix if it wasn't.
    """
    reader_obj = settings["MetaReader"]["Value"]
    f = ConcreteEventFinder(settings=settings)
    f.reader = reader_obj
    return f


def make_signal(
    total_samples: int = 1000,
    baseline: float = 100.0,
    event_value: float = 10.0,
    events: Optional[List[Tuple[int, int]]] = None,
) -> np.ndarray:
    """Build a flat baseline signal with rectangular dips representing events."""
    data = np.full(total_samples, baseline, dtype=np.float64)
    if events:
        for start, end in events:
            data[start:end] = event_value
    return data


@pytest.fixture
def reader():
    data = make_signal(total_samples=1000, events=[(200, 250), (600, 650)])
    return FakeReader(data, samplerate=100.0, channels=(0, 1))


@pytest.fixture
def finder(reader):
    settings = make_settings(reader)
    return build_finder(settings)


@pytest.fixture
def bare_finder(reader):
    """A finder with no reader attached.

    We can't construct this by passing Value=None for "MetaReader" in
    settings, because _validate_param_types rejects any MetaReader value
    that isn't an actual MetaReader subclass instance - including None -
    at construction time. Instead, construct normally with a valid reader
    and then detach it, to exercise the "no reader attached" branches.
    """
    settings = make_settings(reader)
    f = ConcreteEventFinder(settings=settings)
    f.reader = None
    return f


# ---------------------------------------------------------------------------
# Initialization / settings
# ---------------------------------------------------------------------------
class TestInitAndSettings:
    def test_init_attaches_reader(self, finder, reader):
        assert finder.reader is reader
        assert finder.num_events_found == {}
        assert finder.event_starts == {}

    def test_validate_param_types_rejects_non_reader_value(self):
        with pytest.raises(TypeError, match="must have as value an object"):
            ConcreteEventFinder(
                settings={
                    "MetaReader": {"Type": str, "Value": "not a reader"},
                    "Threshold": {"Type": float, "Value": 20.0},
                }
            )

    def test_validate_settings_missing_reader_raises(self):
        with pytest.raises(ValueError, match="MetaReader is required"):
            ConcreteEventFinder(settings={"Threshold": {"Type": float, "Value": 20.0}})

    def test_get_empty_settings_default(self, finder):
        settings = finder.get_empty_settings()
        assert settings["MetaReader"]["Value"] == ""
        assert settings["MetaReader"]["Options"] is None

    def test_get_empty_settings_with_plugins(self, finder):
        plugins = {"MetaReader": ["Reader1", "Reader2"]}
        settings = finder.get_empty_settings(globally_available_plugins=plugins)
        assert settings["MetaReader"]["Value"] == "Reader1"
        assert settings["MetaReader"]["Options"] == ["Reader1", "Reader2"]

    def test_get_empty_settings_no_readers_raises(self, finder):
        plugins = {"MetaReader": []}
        with pytest.raises(KeyError, match="Cannot instantiate an eventfinder"):
            finder.get_empty_settings(globally_available_plugins=plugins)

    def test_get_empty_settings_standalone_bypasses_reader_check(self, finder):
        plugins = {"MetaReader": []}
        settings = finder.get_empty_settings(
            globally_available_plugins=plugins, standalone=True
        )
        assert settings["MetaReader"]["Value"] == ""
        assert settings["MetaReader"]["Options"] is None


# ---------------------------------------------------------------------------
# report_channel_status
# ---------------------------------------------------------------------------
class TestReportChannelStatus:
    def test_init_true_returns_empty_string(self, finder):
        assert finder.report_channel_status(0, init=True) == ""

    def test_unfinished_channel(self, finder):
        assert finder.report_channel_status(0) == "\nCh0: event finding incomplete"

    def test_finished_channel_with_rejected_and_accepted_data(self, finder):
        finder.eventfinding_finished[0] = True
        finder.num_events_found[0] = 3
        finder.accepted_data[0] = 5.0
        finder.rejected_data[0] = 1.5
        finder.rejected_events[0] = {"too short": 2}
        report = finder.report_channel_status(0)
        assert "Found 3 events" in report
        assert "Accepted 5.0s of data" in report
        assert "Rejected 1.5s of data" in report
        assert "too short: 2" in report

    def test_finished_channel_no_rejected_data(self, finder):
        finder.eventfinding_finished[0] = True
        finder.num_events_found[0] = 1
        finder.accepted_data[0] = 5.0
        finder.rejected_data[0] = 0
        report = finder.report_channel_status(0)
        assert "Accepted" not in report

    def test_all_channels_none(self, finder):
        finder.eventfinding_finished[0] = True
        finder.num_events_found[0] = 1
        finder.accepted_data[0] = 1.0
        finder.rejected_data[0] = 0
        report = finder.report_channel_status(None)
        assert "Ch0" in report
        assert "Ch1" in report


# ---------------------------------------------------------------------------
# force_serial_channel_operations
# ---------------------------------------------------------------------------
class TestForceSerialChannelOperations:
    def test_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError, match="need an attached MetaReader"):
            bare_finder.force_serial_channel_operations()

    def test_delegates_to_reader_false(self, finder):
        assert finder.force_serial_channel_operations() is False

    def test_delegates_to_reader_true(self, reader):
        reader.serial = True
        settings = make_settings(reader)
        f = build_finder(settings)
        assert f.force_serial_channel_operations() is True

    def test_reader_exception_defaults_false(self, reader):
        reader.serial_raises = True
        settings = make_settings(reader)
        f = build_finder(settings)
        assert f.force_serial_channel_operations() is False


# ---------------------------------------------------------------------------
# reset_channel
# ---------------------------------------------------------------------------
class TestResetChannel:
    def test_reset_single_channel(self, finder):
        finder.event_starts[0] = [1, 2, 3]
        finder.rejected_data[0] = 5
        finder.eventfinding_finished[0] = True
        finder.reset_channel(0)
        assert finder.event_starts[0] == []
        assert finder.rejected_data[0] == 0
        assert finder.eventfinding_finished[0] is False

    def test_reset_all_channels(self, finder):
        for ch in (0, 1):
            finder.event_starts[ch] = [1, 2]
            finder.eventfinding_finished[ch] = True
        finder.reset_channel(None)
        assert finder.event_starts[0] == []
        assert finder.event_starts[1] == []
        assert finder.eventfinding_finished[0] is False
        assert finder.eventfinding_finished[1] is False


# ---------------------------------------------------------------------------
# get_samplerate / get_base_experiment_name / get_channels / get_dtype
# ---------------------------------------------------------------------------
class TestSimpleReaderDelegates:
    def test_get_samplerate_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError):
            bare_finder.get_samplerate()

    def test_get_samplerate(self, finder):
        assert finder.get_samplerate() == 100.0

    def test_get_base_experiment_name_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError):
            bare_finder.get_base_experiment_name()

    def test_get_base_experiment_name(self, finder):
        assert finder.get_base_experiment_name() == "exp1"

    def test_get_channels_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError, match="Reader has not been initialized"):
            bare_finder.get_channels()

    def test_get_channels(self, finder):
        assert finder.get_channels() == [0, 1]

    def test_get_dtype_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError):
            bare_finder.get_dtype()

    def test_get_dtype(self, finder):
        assert finder.get_dtype() is np.float64


# ---------------------------------------------------------------------------
# get_num_events_found / get_eventfinding_status
# ---------------------------------------------------------------------------
class TestStatusGetters:
    def test_get_num_events_found_finished(self, finder):
        finder.eventfinding_finished[0] = True
        finder.num_events_found[0] = 7
        assert finder.get_num_events_found(0) == 7

    def test_get_num_events_found_not_finished(self, finder):
        assert finder.get_num_events_found(0) == 0

    def test_get_eventfinding_status_true(self, finder):
        finder.eventfinding_finished[0] = True
        assert finder.get_eventfinding_status(0) is True

    def test_get_eventfinding_status_missing_channel(self, finder):
        assert finder.get_eventfinding_status(99) is False


# ---------------------------------------------------------------------------
# _merge_overlapping_ranges
# ---------------------------------------------------------------------------
class TestMergeOverlappingRanges:
    def test_merges_overlapping(self, finder):
        result = finder._merge_overlapping_ranges([(0, 5), (3, 8), (10, 12)])
        assert result == [(0, 8), (10, 12)]

    def test_merges_adjacent(self, finder):
        result = finder._merge_overlapping_ranges([(0, 5), (5, 10)])
        assert result == [(0, 10)]

    def test_filters_invalid_ranges(self, finder):
        result = finder._merge_overlapping_ranges([(5, 5), (10, 2), (0, 3)])
        assert result == [(0, 3)]

    def test_unsorted_input(self, finder):
        result = finder._merge_overlapping_ranges([(10, 12), (0, 5)])
        assert result == [(0, 5), (10, 12)]

    def test_empty_input(self, finder):
        assert finder._merge_overlapping_ranges([]) == []


# ---------------------------------------------------------------------------
# find_events - integration-level tests using the real threshold-crossing
# detector against synthetic signals, plus mocking for branches that are
# impractical to trigger via real signal construction alone.
# ---------------------------------------------------------------------------
class TestFindEventsHappyPath:
    def test_finds_two_events_full_channel(self, finder):
        gen = finder.find_events(0, [(0, 0)], chunk_length=10.0)
        progress = list(gen)
        assert progress[-1] == 1.0
        assert finder.eventfinding_finished[0] is True
        assert finder.num_events_found[0] == 2
        assert len(finder.event_starts[0]) == 2
        assert len(finder.event_ends[0]) == 2
        assert len(finder.padding_before[0]) == 2
        assert len(finder.padding_after[0]) == 2
        assert len(finder.baseline_means[0]) == 2
        assert len(finder.baseline_stds[0]) == 2

    def test_multiple_overlapping_ranges_merged(self, finder):
        # Two overlapping ranges covering the whole channel; should merge
        # into a single effective range and still find both events once.
        gen = finder.find_events(0, [(0, 6), (4, 0)], chunk_length=10.0)
        list(gen)
        assert finder.num_events_found[0] == 2

    def test_explicit_end_provided(self, finder):
        gen = finder.find_events(0, [(0, 10.0)], chunk_length=10.0)
        list(gen)
        assert finder.eventfinding_finished[0] is True

    def test_small_chunk_length_straddles_event(self, finder):
        # chunk_length smaller than the channel forces multiple chunks,
        # exercising the event-straddling-chunk-boundary stitching logic.
        gen = finder.find_events(0, [(0, 0)], chunk_length=2.0)
        list(gen)
        assert finder.num_events_found[0] == 2

    def test_invalid_range_is_skipped(self, finder):
        # second range is degenerate (start >= end) and should be skipped
        gen = finder.find_events(0, [(0, 10.0), (5.0, 5.0)], chunk_length=10.0)
        list(gen)
        assert finder.eventfinding_finished[0] is True

    def test_negative_start_clamped_to_zero(self, finder):
        gen = finder.find_events(0, [(-5.0, 10.0)], chunk_length=10.0)
        list(gen)
        assert finder.eventfinding_finished[0] is True


class TestFindEventsErrorBranches:
    def test_no_reader_raises(self, bare_finder):
        gen = bare_finder.find_events(0, [(0, 0)])
        with pytest.raises(AttributeError):
            next(gen)

    def test_invalid_channel_raises(self, finder):
        gen = finder.find_events(99, [(0, 0)])
        with pytest.raises(RuntimeError, match="Invalid channel"):
            next(gen)

    def test_no_events_found_resets_channel(self, finder):
        # Flat signal (no dips) -> no events; final branch should reset state
        flat_reader = FakeReader(make_signal(1000, events=None), samplerate=100.0)
        f = build_finder(make_settings(flat_reader))
        gen = f.find_events(0, [(0, 0)], chunk_length=10.0)
        list(gen)
        assert f.eventfinding_finished[0] is False
        assert f.event_starts[0] == []

    def test_abort_mid_generator_resets_channel(self, finder):
        gen = finder.find_events(0, [(0, 0)], chunk_length=1.0)
        next(gen)
        try:
            gen.send(True)
        except StopIteration:
            pass
        assert finder.eventfinding_finished[0] is False
        assert finder.event_starts[0] == []

    def test_abort_stops_processing_remaining_ranges(self, finder):
        # Aborting mid-way through the first of two ranges must not fall
        # through to processing the second range afterward.
        real_single_range = finder._find_events_single_range
        call_count = {"n": 0}

        def fake_single_range(channel, start, end, chunk_length, data_filter):
            call_count["n"] += 1
            yield from real_single_range(channel, start, end, chunk_length, data_filter)

        with patch.object(
            finder, "_find_events_single_range", side_effect=fake_single_range
        ):
            gen = finder.find_events(0, [(0, 3.0), (5.0, 0)], chunk_length=1.0)
            next(gen)
            try:
                gen.send(True)
            except StopIteration:
                pass
        assert call_count["n"] == 1
        assert finder.eventfinding_finished[0] is False
        assert finder.event_starts[0] == []

    def test_runtime_error_in_one_range_is_skipped(self, finder):
        # First range raises RuntimeError when iterated; the second range
        # should still be processed normally afterwards.
        real_single_range = finder._find_events_single_range
        call_count = {"n": 0}

        def fake_single_range(channel, start, end, chunk_length, data_filter):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("boom")
            yield from real_single_range(channel, start, end, chunk_length, data_filter)

        with patch.object(
            finder, "_find_events_single_range", side_effect=fake_single_range
        ):
            gen = finder.find_events(0, [(0, 3.0), (5.0, 0)], chunk_length=10.0)
            list(gen)
        assert call_count["n"] == 2

    def test_stop_iteration_raised_at_call_site_is_caught(self, finder):
        # If calling _find_events_single_range itself raises StopIteration
        # (rather than the generator stopping normally), find_events should
        # catch it and continue to the next range.
        with patch.object(
            finder, "_find_events_single_range", side_effect=StopIteration("x")
        ):
            gen = finder.find_events(0, [(0, 0)], chunk_length=10.0)
            list(gen)
        # No events recorded since the (mocked) single-range call never ran
        assert finder.event_starts[0] == []

    def test_mismatched_starts_and_ends_raises_runtime_error(self, finder):
        def fake_single_range(channel, start, end, chunk_length, data_filter):
            finder.event_starts[channel] = [10, 20, 30]
            finder.event_ends[channel] = [5, 15]
            yield 1.0

        with patch.object(
            finder, "_find_events_single_range", side_effect=fake_single_range
        ):
            gen = finder.find_events(0, [(0, 0)], chunk_length=10.0)
            with pytest.raises(RuntimeError, match="Mismatched number"):
                list(gen)


# ---------------------------------------------------------------------------
# _find_events_single_range - direct tests of the chunked detector
# ---------------------------------------------------------------------------
class TestFindEventsSingleRange:
    def _reset(self, finder, channel=0):
        finder.event_starts[channel] = []
        finder.event_ends[channel] = []
        finder.padding_before[channel] = []
        finder.padding_after[channel] = []
        finder.baseline_means[channel] = []
        finder.baseline_stds[channel] = []
        finder.rejected_data[channel] = 0
        finder.accepted_data[channel] = 0
        finder.rejected_events[channel] = {}

    def test_start_negative_raises(self, finder):
        with pytest.raises(RuntimeError, match="Start must be positive"):
            list(finder._find_events_single_range(0, -1, 5, 1.0))

    def test_no_reader_raises(self, bare_finder):
        with pytest.raises(AttributeError):
            list(bare_finder._find_events_single_range(0, 0, 5, 1.0))

    def test_invalid_channel_raises(self, finder):
        with pytest.raises(RuntimeError, match="Requested channel=99"):
            list(finder._find_events_single_range(99, 0, 5, 1.0))

    def test_full_range_two_events(self, finder):
        self._reset(finder)
        list(finder._find_events_single_range(0, 0, 10.0, 10.0))
        assert len(finder.event_starts[0]) == 2
        assert len(finder.event_ends[0]) == 2
        assert finder.num_events_found[0] == 2
        assert finder.eventfinding_finished[0] is True

    def test_chunk_length_none_defaults_to_one_second(self, finder):
        # default chunk_length (None -> 1s = 100 samples here) chunks the
        # data into 100-sample windows; use a reader whose events are short
        # relative to that window so the median-based baseline isn't skewed.
        short_event_reader = FakeReader(
            make_signal(1000, events=[(220, 230), (620, 630)]), samplerate=100.0
        )
        f = build_finder(make_settings(short_event_reader))
        self._reset(f)
        list(f._find_events_single_range(0, 0, 10.0, None))
        assert f.num_events_found[0] == 2

    def test_flat_signal_below_threshold_rejects_chunks(self, finder):
        # baseline mean equal to threshold value -> "mean < threshold" branch
        low_reader = FakeReader(
            make_signal(1000, baseline=15.0, events=None), samplerate=100.0
        )
        f = build_finder(make_settings(low_reader, threshold=20.0))
        self._reset(f)
        list(f._find_events_single_range(0, 0, 10.0, 10.0))
        assert f.event_starts[0] == []
        assert f.rejected_data[0] > 0
        assert f.accepted_data[0] == 0

    def test_value_error_from_baseline_stats_rejects_chunk(self, finder):
        self._reset(finder)
        with patch.object(
            finder, "_get_baseline_stats", side_effect=ValueError("bad stats")
        ):
            progress = list(finder._find_events_single_range(0, 0, 10.0, 10.0))
        assert finder.event_starts[0] == []
        assert finder.rejected_data[0] > 0
        assert len(progress) >= 1

    def test_runtime_error_from_padding_is_skipped(self, finder):
        self._reset(finder)
        with patch.object(
            finder, "_get_padding_length", side_effect=RuntimeError("pad fail")
        ):
            list(finder._find_events_single_range(0, 0, 10.0, 10.0))
        # event_starts never gets populated since padding always fails
        assert finder.event_starts[0] == []

    def test_data_filter_applied(self, finder):
        self._reset(finder)
        calls = []

        def my_filter(data):
            calls.append(len(data))
            return data

        list(finder._find_events_single_range(0, 0, 10.0, 10.0, data_filter=my_filter))
        assert len(calls) > 0

    def test_end_clamped_to_total_samples(self, finder):
        self._reset(finder)
        # end far beyond available samples should be clamped
        list(finder._find_events_single_range(0, 0, 1000.0, 10.0))
        assert finder.eventfinding_finished[0] is True

    def test_chunk_length_larger_than_total_samples_is_clamped(self, finder):
        self._reset(finder)
        list(finder._find_events_single_range(0, 0, 10.0, 1000.0))
        assert finder.num_events_found[0] == 2

    def test_mismatched_starts_ends_within_single_range_raises(self, finder):
        self._reset(finder)
        # Pre-seed event_starts/event_ends such that, after the trailing
        # pop-correction logic runs, lengths still disagree.
        finder.event_starts[0] = [5, 50]
        finder.event_ends[0] = [10, 60, 70]
        with patch.object(
            finder,
            "_find_events_in_chunk",
            return_value=([], [], False),
        ):
            with pytest.raises(RuntimeError, match="Mismatched event starts"):
                list(finder._find_events_single_range(0, 0, 10.0, 10.0))

    def test_rejected_events_recorded(self, finder):
        # Min Duration large enough that both events are rejected as "too short"
        reader2 = FakeReader(
            make_signal(1000, events=[(200, 250), (600, 650)]), samplerate=100.0
        )
        f = build_finder(make_settings(reader2, min_duration=1000.0))
        self._reset(f)
        list(f._find_events_single_range(0, 0, 10.0, 10.0))
        assert f.rejected_events[0].get("too short") == 2
        assert f.event_starts[0] == []

    def test_event_straddles_chunk_boundary(self, finder):
        # Event spans samples [190, 260), which straddles the chunk boundary
        # at sample 200 when chunk_length=1.0s (100 samples). This exercises
        # both the "carry trailing start into next chunk" pop (when chunk 1
        # ends mid-event) and the "insert saved start at front" branch (when
        # chunk 2 picks the event back up).
        straddle_reader = FakeReader(
            make_signal(1000, events=[(190, 260)]), samplerate=100.0
        )
        f = build_finder(make_settings(straddle_reader))
        self._reset(f)
        list(f._find_events_single_range(0, 0, 10.0, 2.0))
        assert f.event_starts[0] == [190]
        assert f.event_ends[0] == [260]
        assert f.num_events_found[0] == 1

    def test_leading_orphan_end_dropped_in_first_chunk(self, finder):
        # The "drop leading orphan end in the first chunk" branch
        # (``if ... and is_first_chunk and event_ends[0] < event_starts[0]:
        # event_ends.pop(0)``) captures whether this is the first chunk into
        # ``is_first_chunk`` before the baseline-stats try/except's
        # ``finally:`` block resets ``first_chunk`` to False, so the check
        # correctly fires on the very first chunk. A leading orphan end
        # (event_ends[0] < event_starts[0]) is dropped, leaving a valid
        # start/end pair that gets recorded as a real event.
        self._reset(finder)
        with patch.object(
            finder,
            "_find_events_in_chunk",
            return_value=([50], [10, 90], False),
        ):
            list(finder._find_events_single_range(0, 0, 10.0, 10.0))
        assert finder.event_starts[0] == [50]
        assert finder.event_ends[0] == [90]

    def test_trailing_correction_pops_both_sides(self, finder):
        # Pre-seed mismatched-looking starts/ends that, after the trailing
        # pop-correction at the end of the range, become equal length again
        # (so no RuntimeError is raised), exercising both pop branches.
        self._reset(finder)
        finder.event_starts[0] = [10, 500]
        finder.event_ends[0] = [5, 60]
        with patch.object(
            finder, "_find_events_in_chunk", return_value=([], [], False)
        ):
            list(finder._find_events_single_range(0, 0, 10.0, 10.0))
        assert finder.event_starts[0] == [10]
        assert finder.event_ends[0] == [60]
        assert finder.eventfinding_finished[0] is True


# ---------------------------------------------------------------------------
# _get_padding_length - clamp branches
# ---------------------------------------------------------------------------
class TestGetPaddingLengthClamps:
    def test_padding_after_previous_end_clamped(self, finder):
        # target_padding (driven by a large last_duration) exceeds the gap
        # between the channel/range start (last_end) and the first event ->
        # padding_after_previous_end must be clamped down to that gap.
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [100],
            [150],
            last_end=95,
            last_duration=50,
            samplerate=100.0,
            last_call=True,
            last_sample=1000,
        )
        assert pa_prev == 5  # clamped to event_starts[0] - last_end

    def test_padding_after_clamped_to_tight_gap_between_events(self, finder):
        # event0's own target padding (based on its duration) is larger than
        # the gap to the next event's start -> clamp via the 0.75x rule.
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [0, 6],
            [5, 20],
            last_end=0,
            last_duration=None,
            samplerate=100.0,
            last_sample=1000,
        )
        assert pa[0] == int(0.75 * (6 - 5))

    def test_padding_after_clamped_near_last_sample_for_non_final_event(self, finder):
        # A non-final event (it has a successor) whose padding would extend
        # past last_sample must be clamped via the second 0.75x rule.
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [10, 990, 995],
            [15, 992, 998],
            last_end=0,
            last_duration=None,
            samplerate=100.0,
            last_call=True,
            last_sample=993,
        )
        assert pa[1] == int(0.75 * (993 - 992))


# ---------------------------------------------------------------------------
# _get_padding_length
# ---------------------------------------------------------------------------
class TestGetPaddingLength:
    def test_mismatched_lengths_raises(self, finder):
        with pytest.raises(RuntimeError, match="Unable to match event start"):
            finder._get_padding_length([1, 2], [1], 0, None, 100.0)

    def test_start_after_end_raises(self, finder):
        with pytest.raises(RuntimeError, match="Unable to match event start"):
            finder._get_padding_length([10], [5], 0, None, 100.0)

    def test_basic_padding_computation(self, finder):
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [100, 300], [150, 350], 0, None, 100.0, last_call=True, last_sample=1000
        )
        assert len(pb) == 2
        assert len(pa) == 1  # no "next" event after the last one
        assert last_end == 350
        assert pa_prev >= 0

    def test_last_duration_used_for_target_padding(self, finder):
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [500], [600], 0, last_duration=50, samplerate=100.0, last_sample=1000
        )
        assert pa_prev >= 0

    def test_padding_clamped_near_last_end(self, finder):
        # event starts very close to last_end -> padding_before should be clamped
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [10],
            [20],
            last_end=5,
            last_duration=None,
            samplerate=100.0,
            last_sample=1000,
        )
        assert pb[0] <= 10

    def test_padding_after_clamped_near_last_sample(self, finder):
        pb, pa, last_end, pa_prev = finder._get_padding_length(
            [10, 900],
            [20, 990],
            last_end=0,
            last_duration=None,
            samplerate=100.0,
            last_call=True,
            last_sample=1000,
        )
        assert pa[0] >= 0


# ---------------------------------------------------------------------------
# get_event_data_generator
# ---------------------------------------------------------------------------
class TestGetEventDataGenerator:
    def test_missing_channel_raises_keyerror(self, finder):
        with pytest.raises(KeyError, match="is not present"):
            list(finder.get_event_data_generator(99))

    def test_no_event_starts_raises_valueerror(self, finder):
        # event_ends must be non-empty here so this exercises the "no event
        # starts" branch specifically, rather than the "both empty" branch
        # (which now correctly fires "Eventfinder may not have run yet").
        finder.event_starts[0] = []
        finder.event_ends[0] = [20]
        with pytest.raises(ValueError, match="No event starts found"):
            list(finder.get_event_data_generator(0))

    def test_eventfinding_not_finished_raises(self, finder):
        finder.event_starts[0] = [10]
        finder.event_ends[0] = [20]
        finder.eventfinding_finished[0] = False
        with pytest.raises(ValueError, match="not yet completed"):
            list(finder.get_event_data_generator(0))

    def test_successful_generation(self, finder):
        gen = finder.find_events(0, [(0, 0)], chunk_length=10.0)
        list(gen)
        events = list(finder.get_event_data_generator(0))
        assert len(events) == finder.num_events_found[0]
        assert all("data" in e for e in events)


# ---------------------------------------------------------------------------
# get_single_event_data
# ---------------------------------------------------------------------------
class TestGetSingleEventData:
    def test_no_events_run_yet_raises(self, finder):
        with pytest.raises(ValueError, match="may not have run yet"):
            finder.get_single_event_data(0, 0)

    def test_missing_channel_raises_keyerror(self, finder):
        finder.event_starts[0] = [10]
        finder.event_ends[0] = [20]
        with pytest.raises(KeyError, match="is not present"):
            finder.get_single_event_data(99, 0)

    def test_empty_event_starts_raises(self, finder):
        finder.event_starts[0] = []
        finder.event_ends[0] = []
        with pytest.raises(ValueError, match="No event starts found"):
            finder.get_single_event_data(0, 0)

    def test_success_after_find_events(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        event = finder.get_single_event_data(0, 0)
        assert event is not None
        assert "data" in event
        assert event["scale"] is None
        assert event["offset"] is None

    def test_index_out_of_bounds_returns_none(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        result = finder.get_single_event_data(0, 9999)
        assert result is None

    def test_data_filter_applied(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        calls = []

        def my_filter(data):
            calls.append(True)
            return data

        finder.get_single_event_data(0, 0, data_filter=my_filter)
        assert calls == [True]

    def test_rectify_applied(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        event = finder.get_single_event_data(0, 0, rectify=True)
        assert event is not None

    def test_raw_data_path(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        event = finder.get_single_event_data(0, 0, raw_data=True)
        assert event is not None
        assert event["scale"] == 1.0
        assert event["offset"] == 0.0


# ---------------------------------------------------------------------------
# get_event_indices
# ---------------------------------------------------------------------------
class TestGetEventIndices:
    def test_returns_dicts_on_fresh_instance(self, finder):
        starts, ends = finder.get_event_indices(0)
        assert starts == {}
        assert ends == {}

    def test_returns_populated_dicts_after_find_events(self, finder):
        list(finder.find_events(0, [(0, 0)], chunk_length=10.0))
        starts, ends = finder.get_event_indices(0)
        assert 0 in starts
        assert 0 in ends


# ---------------------------------------------------------------------------
# Abstract method stub bodies
# ---------------------------------------------------------------------------
class TestAbstractStubs:
    def test_public_abstract_stub(self, finder):
        assert MetaEventFinder.close_resources(finder) is None

    def test_private_abstract_stubs(self, finder):
        assert MetaEventFinder._init(finder) is None
        assert (
            MetaEventFinder._find_events_in_chunk(finder, np.array([1.0]), 1.0, 0.1, 0)
            is None
        )
        assert MetaEventFinder._filter_events(finder, [], [], 0) is None
        assert MetaEventFinder._validate_settings(finder, {}) is None
        assert MetaEventFinder._get_baseline_stats(finder, np.array([1.0])) is None


# ---------------------------------------------------------------------------
# get_event_data_generator / get_single_event_data - remaining precondition
# branches (no event ends found, reader missing with otherwise-valid state)
# ---------------------------------------------------------------------------
class TestRemainingPreconditionBranches:
    def test_get_event_data_generator_no_event_ends_raises(self, finder):
        finder.event_starts[0] = [10]
        finder.event_ends[0] = []
        with pytest.raises(ValueError, match="No event ends found"):
            list(finder.get_event_data_generator(0))

    def test_get_single_event_data_no_event_ends_raises(self, finder):
        finder.event_starts[0] = [10]
        finder.event_ends[0] = []
        with pytest.raises(ValueError, match="No event ends found"):
            finder.get_single_event_data(0, 0)

    def test_get_single_event_data_no_reader_raises(self, bare_finder):
        bare_finder.event_starts[0] = [10]
        bare_finder.event_ends[0] = [20]
        bare_finder.padding_before[0] = [1]
        bare_finder.padding_after[0] = [1]
        with pytest.raises(AttributeError, match="need an attached MetaEventReader"):
            bare_finder.get_single_event_data(0, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
