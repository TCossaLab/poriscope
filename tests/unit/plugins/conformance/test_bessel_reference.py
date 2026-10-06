"""
The Bessel filter against a reference implementation.

Until 2.1 ``BesselFilter`` built its filter in the ``(b, a)`` form and ran ``filtfilt``,
guarded by a magic constant (any pole with modulus at or above 0.975 was refused) because
that form goes numerically unstable at low normalised cutoffs. It now builds second-order
sections and runs ``sosfiltfilt``; scipy's own ``bessel(..., output="sos")`` with
``sosfiltfilt`` is the reference here, computed in the test rather than stored. At the
conformance settings the plugin must match it, and a low cutoff the old guard refused
(25 kHz at 4.17 MHz) must be accepted and match it too. The plugin keeps its own median
padding, so its ends differ from the reference's odd extension as before.

Both filters are zero-phase and both pad: the plugin pads with the medians of its first
and last ``3 * order`` samples over ``10 * order`` samples, ``sosfiltfilt`` with scipy's
default odd extension, so the first and last few hundred samples are compared separately
with a looser bound.
"""

import numpy as np
import pytest
from scipy.signal import bessel, sosfiltfilt

from poriscope.plugins.filters.BesselFilter import BesselFilter
from tests.synthetic_data.synthetic_events_db import build_bessel_filter
from tests.unit.plugins.conformance._recipes import FILTER_SETTINGS, build_filter

pytestmark = pytest.mark.conformance

BASELINE_PA = 2000.0
NOISE_STD_PA = 15.0
EVENT_AMPLITUDE_PA = -400.0
TRACE_SAMPLES = 40_000
#: Samples at each end excluded from the tight comparison: both implementations pad, but
#: not identically, and the difference decays over a few cutoff periods - about six, measured
#: 2026-10-06 at 25 kHz over 4.17 MHz (167 samples per period: 1.7e-4 pA still at 400
#: samples, 7e-9 pA from 1,000). The exclusion therefore scales with the cutoff and never
#: drops below the 400 samples that cover the conformance settings.
EDGE_MIN = 400
EDGE_CUTOFF_PERIODS = 6
#: Interior agreement bound, in picoamps. Measured 2026-10-05 at the conformance settings:
#: the two forms agree to better than 1e-6 pA away from the ends, so a drift shows as a
#: number rather than a surprise.
INTERIOR_ATOL_PA = 1e-6
#: The ends are where the padding strategies differ: median constant padding against
#: scipy's odd extension, on a trace with 15 pA of noise. Measured 26.1 pA at worst on
#: 2026-10-05; the bound is a gross-breakage check, not a pin on the padding.
EDGE_ATOL_PA = 50.0


@pytest.fixture
def trace() -> np.ndarray:
    """
    The conformance filter trace: a noisy baseline with one 400 pA blockage in the middle.

    :return: the trace, in picoamps
    :rtype: numpy.ndarray
    """
    rng = np.random.default_rng(seed=11)
    data = rng.normal(BASELINE_PA, NOISE_STD_PA, TRACE_SAMPLES)
    data[10_000:20_000] += EVENT_AMPLITUDE_PA
    return data


def sos_reference(
    data: np.ndarray, samplerate: float, cutoff: float, poles: int
) -> np.ndarray:
    """
    Filter with scipy's second-order-sections Bessel, zero-phase.

    :param data: the trace
    :type data: numpy.ndarray
    :param samplerate: in hertz
    :type samplerate: float
    :param cutoff: in hertz
    :type cutoff: float
    :param poles: filter order
    :type poles: int
    :return: the filtered trace
    :rtype: numpy.ndarray
    """
    return sosfiltfilt(bessel(poles, 2.0 * cutoff / samplerate, output="sos"), data)


def edge_samples(samplerate: float, cutoff: float) -> int:
    """
    How many samples at each end the padding transient can occupy.

    :param samplerate: in hertz
    :type samplerate: float
    :param cutoff: in hertz
    :type cutoff: float
    :return: the exclusion, in samples
    :rtype: int
    """
    return max(EDGE_MIN, int(EDGE_CUTOFF_PERIODS * samplerate / cutoff))


def assert_matches_reference(
    filtered: np.ndarray, reference: np.ndarray, edge: int
) -> None:
    """
    Compare a plugin output with the reference, interior tightly and edges loosely.

    :param filtered: the plugin's output
    :type filtered: numpy.ndarray
    :param reference: the sos reference
    :type reference: numpy.ndarray
    :param edge: samples at each end compared loosely, from :func:`edge_samples`
    :type edge: int
    """
    interior = slice(edge, -edge)
    worst = float(np.max(np.abs(filtered[interior] - reference[interior])))
    assert worst <= INTERIOR_ATOL_PA, f"interior disagreement {worst:.3g} pA"
    edges = np.r_[
        np.abs(filtered[:edge] - reference[:edge]),
        np.abs(filtered[-edge:] - reference[-edge:]),
    ]
    assert (
        float(np.max(edges)) <= EDGE_ATOL_PA
    ), f"edge disagreement {np.max(edges):.3g} pA"


def test_the_shipped_filter_matches_the_sos_reference_at_the_conformance_settings(
    trace: np.ndarray,
) -> None:
    """At 200 kHz over 4 MHz with 8 poles, the two forms are the same filter."""
    settings = FILTER_SETTINGS["BesselFilter"]
    plugin = build_filter(BesselFilter)
    try:
        filtered = plugin.filter_data(trace.copy())
    finally:
        plugin.close_resources()
    reference = sos_reference(
        trace, settings["Samplerate"], settings["Cutoff"], settings["Poles"]
    )
    assert_matches_reference(
        filtered, reference, edge_samples(settings["Samplerate"], settings["Cutoff"])
    )


def test_a_low_cutoff_the_old_guard_refused_is_accepted_and_matches_the_reference(
    trace: np.ndarray,
) -> None:
    """A 25 kHz Bessel over a 4.17 MHz recording is an ordinary request and must work."""
    samplerate, cutoff, poles = 4_170_000.0, 25_000.0, 8
    plugin = build_bessel_filter(samplerate, cutoff, poles)
    try:
        filtered = plugin.filter_data(trace.copy())
    finally:
        plugin.close_resources()
    assert_matches_reference(
        filtered,
        sos_reference(trace, samplerate, cutoff, poles),
        edge_samples(samplerate, cutoff),
    )
