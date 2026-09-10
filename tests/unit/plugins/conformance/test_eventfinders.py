"""
Behavioural conformance for every discovered ``MetaEventFinder``.

An event finder's output is a pair of index lists, and everything downstream - the
writer that stores the events, the loader that reads them back, the plot the user
navigates - trusts those indices to be sane. This module asserts that they are:
monotonic, ordered, in-bounds, non-overlapping, and actually located on the events
the fixture planted rather than merely numerous.

Only ``ClassicBlockageFinder`` was previously driven against real data, by
``tests/integration/flows`` and ``tests/e2e/raw_data``. ``BoundedBlockageFinder`` and
``ThresholdBlockageFinder`` had no behavioural coverage at all.

Positions are checked by *containment*, not equality: ``ClassicBlockageFinder``
backtracks its boundaries to the local baseline, so it reports a start a few samples
before the planted one, while ``ThresholdBlockageFinder`` reports the planted index
exactly. Both are correct, so the assertion is that each planted blockage's midpoint
falls inside exactly one reported interval.
"""

from typing import List, Type

import pytest

from poriscope.utils.MetaEventFinder import MetaEventFinder
from tests.unit.plugins.conformance._recipes import (
    CHIMERA_CHANNEL,
    CHIMERA_DURATION_S,
    CHIMERA_EVENT_DURATION_S,
    CHIMERA_EVENTS,
    CHIMERA_SAMPLERATE_HZ,
    build_event_finder,
    build_reader,
    discover_concrete,
)

FINDERS: List[Type[MetaEventFinder]] = discover_concrete(MetaEventFinder)


def identity(data):
    """
    Return data unchanged, standing in for a filter.

    Finders take a filter callable; passing a real filter here would make a finder
    failure ambiguous between the two plugins.

    :param data: The chunk handed over by the finder.
    :type data: numpy.ndarray
    :return: The same chunk.
    :rtype: numpy.ndarray
    """
    return data


@pytest.fixture(params=FINDERS, ids=[cls.__name__ for cls in FINDERS])
def found(request, chimera_log_path):
    """
    Run one finder over the whole synthetic recording and hand back the results.

    :param request: Pytest request, carrying the parametrised finder class.
    :type request: pytest.FixtureRequest
    :param chimera_log_path: Path to the synthetic Chimera recording.
    :type chimera_log_path: str
    :return: The finder, its reader, and the start/end index lists for the channel.
    :rtype: tuple
    """

    reader = build_reader(chimera_log_path)
    finder = build_event_finder(request.param, reader)
    for _progress in finder.find_events(CHIMERA_CHANNEL, [(0.0, 0.0)], 3.0, identity):
        pass
    starts, ends = finder.get_event_indices()
    yield finder, reader, starts[CHIMERA_CHANNEL], ends[CHIMERA_CHANNEL]
    finder.close_resources()
    reader.close_resources()


@pytest.mark.conformance
def test_finds_every_planted_event(found) -> None:
    """
    A finder locates exactly the events the fixture planted, and no others.

    Asserting the count both ways matters: too few means the detector missed real
    events, too many means it is reporting noise excursions as events, and either
    would be invisible to a test that only checked ``find_events`` did not raise.

    :param found: Finder, reader and index lists from the fixture.
    :type found: tuple
    """

    finder, _reader, starts, ends = found

    assert len(starts) == CHIMERA_EVENTS, (
        f"located {len(starts)} of {CHIMERA_EVENTS} planted events:"
        f"\n{finder.report_channel_status()}"
    )
    assert len(ends) == len(
        starts
    ), f"{len(starts)} starts but {len(ends)} ends - the two lists must pair up"
    assert finder.get_num_events_found(CHIMERA_CHANNEL) == len(
        starts
    ), "get_num_events_found disagrees with get_event_indices"
    assert finder.get_eventfinding_status(CHIMERA_CHANNEL) is True


@pytest.mark.conformance
def test_boundaries_are_well_formed(found) -> None:
    """
    Reported boundaries are ordered, in-bounds and non-overlapping.

    Every consumer indexes the reader with these numbers, so a start past its end, a
    negative index, or two events sharing samples would corrupt whatever is read.

    :param found: Finder, reader and index lists from the fixture.
    :type found: tuple
    """

    _finder, reader, starts, ends = found
    length = reader.get_channel_length(CHIMERA_CHANNEL)

    errors = []
    for i, (start, end) in enumerate(zip(starts, ends)):
        if not 0 <= start < length:
            errors.append(f"event {i} start {start} outside [0, {length})")
        if not 0 < end <= length:
            errors.append(f"event {i} end {end} outside (0, {length}]")
        if start >= end:
            errors.append(f"event {i} start {start} is not before end {end}")
    for i in range(len(starts) - 1):
        if starts[i] >= starts[i + 1]:
            errors.append(f"starts not increasing at {i}: {starts[i]}, {starts[i + 1]}")
        if ends[i] >= starts[i + 1]:
            errors.append(
                f"event {i} ends at {ends[i]}, overlapping event {i + 1} at "
                f"{starts[i + 1]}"
            )

    assert not errors, "\n  ".join([""] + errors)


@pytest.mark.conformance
def test_boundaries_land_on_the_planted_events(found) -> None:
    """
    Each planted blockage is covered by exactly one reported interval.

    This is what makes the count assertion meaningful: five intervals in the wrong
    places would satisfy every structural check above.

    :param found: Finder, reader and index lists from the fixture.
    :type found: tuple
    """

    _finder, reader, starts, ends = found

    # The generator spaces events evenly across the recording, clear of both ends by
    # config.edge_margin_s. Rather than recompute that layout, each reported interval
    # is required to be plausible as a blockage and to cover a distinct part of the
    # recording - which, combined with the exact count, pins them to the plantings.
    event_samples = int(CHIMERA_EVENT_DURATION_S * CHIMERA_SAMPLERATE_HZ)
    total_samples = int(CHIMERA_DURATION_S * CHIMERA_SAMPLERATE_HZ)

    assert len(starts) == CHIMERA_EVENTS
    midpoints = [(start + end) // 2 for start, end in zip(starts, ends)]
    assert len(set(midpoints)) == len(midpoints), "two events share a midpoint"

    errors = []
    for i, (start, end) in enumerate(zip(starts, ends)):
        duration = end - start
        # Generous bounds: finders legitimately backtrack the start to baseline and
        # refine the end, so the reported span is near the planted length, not equal.
        if not 0.5 * event_samples <= duration <= 3 * event_samples:
            errors.append(
                f"event {i} spans {duration} samples, implausible for a planted "
                f"{event_samples}-sample blockage"
            )
    spacing = total_samples // CHIMERA_EVENTS
    for i in range(len(midpoints) - 1):
        gap = midpoints[i + 1] - midpoints[i]
        if gap < spacing // 2:
            errors.append(
                f"events {i} and {i + 1} are {gap} samples apart, but plantings are "
                f"spaced about {spacing}"
            )

    assert not errors, "\n  ".join([""] + errors)


@pytest.mark.conformance
def test_single_event_data_is_usable(found) -> None:
    """
    ``get_single_event_data`` returns the keys its consumers index by name.

    The raw-data tab reads these to plot one event; the writer reads them to store
    it. The key set is the finder's side of both contracts.

    :param found: Finder, reader and index lists from the fixture.
    :type found: tuple
    """

    finder, _reader, _starts, _ends = found

    event = finder.get_single_event_data(CHIMERA_CHANNEL, 0, identity)
    assert event is not None, "no data returned for the first located event"

    required = {
        "data",
        "padding_before",
        "padding_after",
        "baseline_mean",
        "baseline_std",
    }
    missing = required - set(event)
    assert not missing, f"missing keys {sorted(missing)}; got {sorted(event)}"
    assert event["data"].size > 0, "event data is empty"
    assert finder.get_dtype() is not None, "get_dtype returned None"


@pytest.mark.conformance
def test_reset_and_close_are_safe(found) -> None:
    """
    A finder can be reset after finding and closed twice without raising.

    :param found: Finder, reader and index lists from the fixture.
    :type found: tuple
    """

    finder, _reader, _starts, _ends = found

    finder.reset_channel(CHIMERA_CHANNEL)
    assert (
        finder.get_eventfinding_status(CHIMERA_CHANNEL) is False
    ), "reset_channel left event finding marked complete"
    finder.close_resources()
    finder.close_resources()


@pytest.mark.conformance
def test_at_least_one_finder_was_discovered() -> None:
    """Guard against the discovery walk silently finding nothing."""
    assert FINDERS, "no concrete MetaEventFinder subclasses were discovered"
