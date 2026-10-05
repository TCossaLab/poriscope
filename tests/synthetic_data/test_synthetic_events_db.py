"""
Self-tests for the synthetic events database generator.

The generator is the ground truth every fitter accuracy test compares against, so its
description of what it planted has to match what it wrote. These tests read the traces
back out of the database it produced and check them against ``planted_sublevels()``, the
stored ``baseline_std`` and the Bessel rise time, with the noise turned down to nothing
where an exact layout check is wanted.
"""

import sqlite3
from pathlib import Path
from typing import List

import numpy as np
import pytest
from scipy.signal import bessel, sosfreqz

from tests.synthetic_data.synthetic_events_db import (
    RAW_DATA_DTYPE,
    SyntheticDbEvent,
    generate_events_database,
)

SAMPLERATE = 500_000.0
BASELINE = 2000.0
AMPLITUDE = -400.0
STEPS = [0.0, -150.0, -300.0]
PADDING = 100


def _traces(db_path: Path) -> List[np.ndarray]:
    """
    Read every stored event trace back out of a generated database, in event order.

    :param db_path: the database the generator wrote
    :type db_path: Path
    :return: one float64 trace per event
    :rtype: List[numpy.ndarray]
    """
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT raw_data FROM events ORDER BY event_id").fetchall()
    finally:
        conn.close()
    return [np.frombuffer(row[0], dtype=RAW_DATA_DTYPE) for row in rows]


def test_a_flat_blockage_is_one_planted_sublevel() -> None:
    """Without a staircase, ``planted_sublevels`` is the whole blockage at one level."""
    event = SyntheticDbEvent(
        event_id=0,
        absolute_start=0,
        padding_before=PADDING,
        padding_after=PADDING,
        event_length=250,
        baseline_mean=BASELINE,
        baseline_std=15.0,
        amplitude=AMPLITUDE,
    )
    assert event.planted_sublevels() == [(PADDING, 250, BASELINE + AMPLITUDE)]


@pytest.mark.parametrize("event_length", [250, 60, 7])
def test_planted_sublevels_match_the_written_staircase(
    tmp_path: Path, event_length: int
) -> None:
    """
    Each planted sublevel's samples hold exactly its level when the noise is zero.

    The remainder rule (the last step absorbs ``event_length % n``) is what makes 250 and
    7 interesting: 83/83/84 and 2/2/3.
    """
    db = generate_events_database(
        tmp_path / "staircase.sqlite",
        samplerate=SAMPLERATE,
        baseline_mean_pA=BASELINE,
        baseline_std_pA=0.0,
        event_amplitude_pA=AMPLITUDE,
        event_length_samples=event_length,
        padding_samples=PADDING,
        num_events=3,
        sublevel_amplitudes_pA=STEPS,
    )
    for trace, event in zip(_traces(db.db_path), db[0].events, strict=True):
        planted = event.planted_sublevels()
        assert sum(width for _, width, _ in planted) == event_length
        assert planted[0][0] == PADDING
        for start, width, level in planted:
            np.testing.assert_allclose(trace[start : start + width], level)
        # The paddings sit at the baseline.
        np.testing.assert_allclose(trace[:PADDING], BASELINE)
        np.testing.assert_allclose(trace[PADDING + event_length :], BASELINE)
        assert event.sublevel_offsets_pA == STEPS
        assert event.bessel_cutoff_hz is None
        assert event.baseline_std == 0.0


def test_a_bessel_pass_gives_the_edges_a_rise_time_without_moving_them(
    tmp_path: Path,
) -> None:
    """
    With a cutoff, each edge rises over several samples and crosses 50% at the planted
    boundary, and the stored sigma is the one left after filtering.

    A 10-90% rise time is about 0.34 / f_3dB. The plugin builds a phase-normalised
    Bessel, whose -3 dB point sits well below the nominal cutoff (about 26.5 kHz for a
    50 kHz setting at 8 poles), so the expectation is derived from the filter's own
    response rather than from the nominal cutoff: roughly 6 samples at 500 kHz, against
    zero for a perfect step.
    """
    cutoff = 50_000.0
    sos = bessel(8, 2.0 * cutoff / SAMPLERATE, output="sos")
    w, h = sosfreqz(sos, worN=8192)
    f_3db = float((w / np.pi * SAMPLERATE / 2)[np.argmax(np.abs(h) < 1 / np.sqrt(2))])
    expected = 0.34 / f_3db * SAMPLERATE
    db = generate_events_database(
        tmp_path / "filtered.sqlite",
        samplerate=SAMPLERATE,
        baseline_mean_pA=BASELINE,
        baseline_std_pA=0.0,
        event_amplitude_pA=AMPLITUDE,
        event_length_samples=250,
        padding_samples=PADDING,
        num_events=2,
        bessel_cutoff_hz=cutoff,
    )
    trace = _traces(db.db_path)[0]
    event = db[0].events[0]
    assert event.bessel_cutoff_hz == cutoff
    (start, width, level) = event.planted_sublevels()[0]

    # Plateau: the middle of the blockage sits at the planted level. The filter's
    # settling tail is still about 0.015 pA twenty samples in, so the bound is 0.1 pA
    # against a 400 pA step.
    np.testing.assert_allclose(trace[start + 20 : start + width - 20], level, atol=0.1)

    # Falling edge: 10% and 90% of the way from baseline to level.
    drop = BASELINE - level
    ten = BASELINE - 0.1 * drop
    ninety = BASELINE - 0.9 * drop
    half = BASELINE - 0.5 * drop
    edge = trace[start - 20 : start + 20]
    first_below_ten = int(np.argmax(edge < ten))
    first_below_ninety = int(np.argmax(edge < ninety))
    rise_samples = first_below_ninety - first_below_ten
    assert 0.5 * expected <= rise_samples <= 2.0 * expected, (rise_samples, expected)

    # The 50% crossing is at the planted boundary, give or take a sample: zero-phase.
    half_index = (start - 20) + int(np.argmax(edge < half))
    assert abs(half_index - start) <= 1, (half_index, start)


def test_the_stored_sigma_is_the_filtered_one(tmp_path: Path) -> None:
    """``baseline_std`` records what a fitter will measure on the stored trace."""
    cutoff = 50_000.0
    drawn = 15.0
    db = generate_events_database(
        tmp_path / "filtered_noise.sqlite",
        samplerate=SAMPLERATE,
        baseline_mean_pA=BASELINE,
        baseline_std_pA=drawn,
        event_amplitude_pA=AMPLITUDE,
        event_length_samples=250,
        padding_samples=400,
        num_events=10,
        bessel_cutoff_hz=cutoff,
    )
    stored = db[0].events[0].baseline_std
    assert 0.0 < stored < drawn, stored  # a low-pass removes noise power
    # The paddings of the stored traces, pooled, have that sigma. The 40 samples
    # next to each blockage edge are left out: the zero-phase pass smears the
    # 400 pA step a few samples into the padding, and those samples would dominate
    # a standard deviation that is meant to measure noise.
    traces = _traces(db.db_path)
    paddings = np.concatenate([t[:360] for t in traces] + [t[-360:] for t in traces])
    assert np.std(paddings) == pytest.approx(stored, rel=0.05)

    # Without a cutoff the stored sigma is the drawn one, unchanged.
    sharp = generate_events_database(
        tmp_path / "sharp_noise.sqlite",
        samplerate=SAMPLERATE,
        baseline_std_pA=drawn,
        num_events=1,
    )
    assert sharp[0].events[0].baseline_std == drawn
