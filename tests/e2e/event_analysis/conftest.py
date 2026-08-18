"""
Pytest fixtures providing synthetic events databases as test data for the
Event Analysis e2e suite.

Each fixture writes a real .sqlite3 events database to a temporary
directory and returns a description of what was written, including the
exact planted parameters of every event (baseline, noise, amplitude,
padding). Tests can therefore assert against known ground truth rather
than depending on a checked-in real database with empirically-discovered
(and format-specific) fit outcomes.

Generation happens per test, so nothing is checked into the repository
and there is no shared state between tests.

The generator itself (generate_events_database) lives in
tests/synthetic_data/, shared infrastructure rather than duplicated per
suite -- see tests/synthetic_data/synthetic_events_db.py for the schema
this writes and what's been confirmed against the real
SQLiteEventLoader.

These fixtures use the same baseline/noise/amplitude shape as
tests/e2e/raw_data/conftest.py's Chimera fixtures (2000 pA baseline,
15 pA noise, -400 pA events), since a fitter needs the same clean signal
a finder does. They do not attempt to guarantee any particular fit
outcome (e.g. "CUSUM finds exactly N good fits"): that depends on
CUSUM's own fitting algorithm, which is a separate concern from the
loader-level ground truth (event count, sample rate, per-event data)
these fixtures exist to provide.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from tests.synthetic_data.synthetic_events_db import (
    SyntheticEventsDatabase,
    generate_events_database,
)

DEFAULT_BASELINE_PA = 2000.0
DEFAULT_NOISE_STD_PA = 15.0
DEFAULT_EVENT_AMPLITUDE_PA = -400.0


# ==========================================================================
# Events-database fixtures
# ==========================================================================


@pytest.fixture
def synthetic_events_database(tmp_path) -> SyntheticEventsDatabase:
    """
    A single-channel events database with 25 events on channel 0.

    Matches the shape event_analysis e2e tests currently assume of the
    real fixture DB (25 events, channel 0): same event count, same
    baseline/noise/amplitude shape used by the raw-data fixtures (see
    tests/e2e/raw_data/conftest.py), at 500 kHz.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Database describing the file written and the events planted
        in it.
    :rtype: SyntheticEventsDatabase
    """
    return generate_events_database(
        tmp_path / "synthetic_events.sqlite3",
        channel_id=0,
        num_events=25,
        samplerate=500_000.0,
        baseline_mean_pA=DEFAULT_BASELINE_PA,
        baseline_std_pA=DEFAULT_NOISE_STD_PA,
        event_amplitude_pA=DEFAULT_EVENT_AMPLITUDE_PA,
    )


@pytest.fixture
def make_synthetic_events_database(tmp_path):
    """
    Build events databases with custom parameters.

    Use when a test needs something the default fixture doesn't provide
    (a different event count, a different channel, parameters chosen to
    push a fitter toward rejecting events)::

        def test_fitter_rejects_bad_params(make_synthetic_events_database):
            db = make_synthetic_events_database(num_events=5)

    Every keyword argument of generate_events_database() can be
    overridden; unset ones fall back to this module's defaults. Each call
    writes to its own file, so a test may create several databases
    without them colliding.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: A factory accepting any keyword argument of
        generate_events_database().
    :rtype: Callable[..., SyntheticEventsDatabase]
    """

    def _make(**overrides: Any) -> SyntheticEventsDatabase:
        n_prior = len(list(tmp_path.glob("synthetic_events_*.sqlite3")))
        out_path = tmp_path / f"synthetic_events_{n_prior}.sqlite3"
        params: Dict[str, Any] = dict(
            channel_id=0,
            num_events=25,
            samplerate=500_000.0,
            baseline_mean_pA=DEFAULT_BASELINE_PA,
            baseline_std_pA=DEFAULT_NOISE_STD_PA,
            event_amplitude_pA=DEFAULT_EVENT_AMPLITUDE_PA,
        )
        params.update(overrides)
        return generate_events_database(out_path, **params)

    return _make