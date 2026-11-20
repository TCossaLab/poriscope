"""
Synthetic two-level events whose baseline padding is correlated, for the Protein tab.

The Protein tab counts an event's independent measurements as its sample count divided by
the correlation length of the noise in its leading padding. Only the padding is measured,
so these events correlate the padding (white noise through a boxcar, rescaled to keep its
per-sample amplitude) and leave the event itself white, which keeps the two-level histogram
clean enough to fit. With the default 200-sample boxcar over a 1,000-sample padding the
measured correlation length is 27 to 140 samples across seeds 0-19: a 100-sample event
holds at most 3.7 independent measurements and a 3,000-sample one at least 21, and both
fit as two populations at 30 or 60 bins.
"""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

SAMPLERATE = 1_000_000
BASELINE = 1000.0


def two_level_event_with_correlated_padding(
    event_id: int = 1,
    n_event: int = 100,
    padding: int = 1000,
    width: int = 200,
    low: float = 0.25,
    high: float = 0.55,
    noise: float = 8.0,
    rng_seed: int = 0,
) -> Dict[str, Any]:
    """
    One event blocking the pore at two levels, half its samples at each, between correlated paddings.

    :param event_id: the event's id
    :type event_id: int
    :param n_event: the samples between the paddings
    :type n_event: int
    :param padding: the samples of baseline either side, which at 1 MHz is also microseconds
    :type padding: int
    :param width: the boxcar the padding noise is smoothed with, in samples; 1 leaves it white
    :type width: int
    :param low: the smaller fractional blockage
    :type low: float
    :param high: the larger fractional blockage
    :type high: float
    :param noise: the noise amplitude in picoamps
    :type noise: float
    :param rng_seed: the seed for the synthetic noise
    :type rng_seed: int
    :return: one event payload, shaped as ``load_event_data`` yields them
    :rtype: Dict[str, Any]
    """
    rng = np.random.default_rng(rng_seed)
    white = rng.normal(0, noise, 2 * padding + 2 * width)
    smooth = np.convolve(white, np.ones(width) / width, "same") * np.sqrt(width)
    pad_noise = smooth[width : width + 2 * padding]

    trace = np.empty(n_event + 2 * padding)
    trace[:padding] = BASELINE + pad_noise[:padding]
    trace[-padding:] = BASELINE + pad_noise[padding:]
    half = n_event // 2
    body = np.empty(n_event)
    body[:half] = BASELINE * (1 - low)
    body[half:] = BASELINE * (1 - high)
    trace[padding:-padding] = body + rng.normal(0, noise, n_event)
    return {
        "id": event_id,
        "event_id": event_id,
        "experiment_id": 1,
        "channel_id": 0,
        "raw_data": trace.copy(),
        "filtered_data": trace.copy(),
        "samplerate": SAMPLERATE,
        "padding_before": padding * 1e6 / SAMPLERATE,
        "padding_after": padding * 1e6 / SAMPLERATE,
    }
