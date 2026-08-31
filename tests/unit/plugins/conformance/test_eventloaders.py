"""
Behavioural conformance for every discovered ``MetaEventLoader``.

An event loader is the boundary between a stored events database and every analysis
that reads one, and its contract is unusually explicit: the ``get_event_generator``
docstring on ``MetaEventLoader`` spells out the exact dict keys an event must carry.
This module checks a loader actually produces them, over a real database.

``SQLiteEventLoader`` is used as a parent by ``tests/integration/flows`` and
``tests/e2e/event_analysis``, but only ever incidentally - nothing asserted on what it
returns, so a loader handing back the wrong padding or sample rate would have surfaced
as a confusing fitter failure rather than as a loader failure.
"""

from typing import List, Type

import numpy as np
import pytest

from poriscope.utils.MetaEventLoader import MetaEventLoader
from tests.unit.plugins.conformance._recipes import (
    EVENTS_CHANNEL,
    EVENTS_COUNT,
    EVENTS_SAMPLERATE_HZ,
    build_any_event_loader,
    discover_concrete,
)

LOADERS: List[Type[MetaEventLoader]] = discover_concrete(MetaEventLoader)

# The keys MetaEventLoader.get_event_generator's docstring requires of every event.
REQUIRED_EVENT_KEYS = frozenset(
    {
        "data",
        "absolute_start",
        "padding_before",
        "padding_after",
        "baseline_mean",
        "baseline_std",
    }
)


@pytest.fixture(params=LOADERS, ids=[cls.__name__ for cls in LOADERS])
def loader(request, events_db_path):
    """
    Build the loader under test over the shared events database.

    :param request: Pytest request, carrying the parametrised loader class.
    :type request: pytest.FixtureRequest
    :param events_db_path: Path to the shared synthetic events database.
    :type events_db_path: str
    :return: A configured loader.
    :rtype: MetaEventLoader
    """
    instance = build_any_event_loader(request.param, events_db_path)
    yield instance
    instance.close_resources()


@pytest.mark.conformance
def test_reports_the_database_contents(loader: MetaEventLoader) -> None:
    """
    A loader agrees with the database about channels, event count and sample rate.

    These three drive the channel selector, the event navigator's bounds and every
    duration a fitter computes, so a loader that guessed any of them would corrupt
    analysis without failing.

    :param loader: The configured loader under test.
    :type loader: MetaEventLoader
    """
    channels = loader.get_channels()
    assert EVENTS_CHANNEL in channels, f"expected channel {EVENTS_CHANNEL}: {channels}"
    assert loader.get_num_events(EVENTS_CHANNEL) == EVENTS_COUNT
    assert loader.get_samplerate(EVENTS_CHANNEL) == pytest.approx(EVENTS_SAMPLERATE_HZ)

    indices = loader.get_valid_indices(EVENTS_CHANNEL)
    assert (
        len(indices) == EVENTS_COUNT
    ), f"{len(indices)} valid indices for {EVENTS_COUNT} events"
    assert len(set(indices)) == len(indices), "valid indices contain duplicates"


@pytest.mark.conformance
def test_loaded_event_carries_the_documented_keys(loader: MetaEventLoader) -> None:
    """
    ``load_event`` returns every key the base class documents, with usable values.

    Fitters index this dict by name - ``padding_before`` in particular decides where
    a fitter believes the blockage starts - so a missing or misnamed key is a
    downstream crash, and a wrong one is silently wrong science.

    :param loader: The configured loader under test.
    :type loader: MetaEventLoader
    """
    event = loader.load_event(EVENTS_CHANNEL, 0, None)

    missing = REQUIRED_EVENT_KEYS - set(event)
    assert not missing, f"missing keys {sorted(missing)}; got {sorted(event)}"

    data = event["data"]
    assert isinstance(data, np.ndarray), f"data is {type(data).__name__}"
    assert data.dtype == np.float64, f"data dtype is {data.dtype}"
    assert data.size > 0, "event data is empty"

    padding = int(event["padding_before"]) + int(event["padding_after"])
    assert (
        padding < data.size
    ), f"padding {padding} does not leave room for a blockage in {data.size} samples"
    assert float(event["baseline_std"]) > 0.0, "baseline_std is not positive"


@pytest.mark.conformance
def test_generator_yields_every_event(loader: MetaEventLoader) -> None:
    """
    ``get_event_generator`` walks the whole channel and applies the filter it is given.

    The generator is what a fitter actually consumes, so it has to agree with
    ``get_num_events``; a generator that stopped early would silently shorten every
    analysis.

    :param loader: The configured loader under test.
    :type loader: MetaEventLoader
    """
    calls = []

    def spy(data):
        """Record that the filter was invoked, and pass the data through."""
        calls.append(data.size)
        return data

    events = list(loader.get_event_generator(EVENTS_CHANNEL, spy))

    assert (
        len(events) == EVENTS_COUNT
    ), f"generator yielded {len(events)} of {EVENTS_COUNT} events"
    assert (
        len(calls) >= EVENTS_COUNT
    ), "the data_filter was not applied to every yielded event"
    for i, event in enumerate(events):
        missing = REQUIRED_EVENT_KEYS - set(event)
        assert not missing, f"event {i} missing keys {sorted(missing)}"


@pytest.mark.conformance
def test_reset_and_close_are_safe(loader: MetaEventLoader) -> None:
    """
    A loader survives reset and repeated close, and still reads afterwards.

    :param loader: The configured loader under test.
    :type loader: MetaEventLoader
    """
    first = loader.load_event(EVENTS_CHANNEL, 0, None)["data"]
    loader.reset_channel(EVENTS_CHANNEL)
    np.testing.assert_allclose(
        loader.load_event(EVENTS_CHANNEL, 0, None)["data"],
        first,
        err_msg="loading is not repeatable across reset_channel",
    )
    loader.close_resources()
    loader.close_resources()


@pytest.mark.conformance
def test_at_least_one_loader_was_discovered() -> None:
    """Guard against the discovery walk silently finding nothing."""
    assert LOADERS, "no concrete MetaEventLoader subclasses were discovered"
