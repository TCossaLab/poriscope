"""
The Bessel filter against a reference implementation.

``BesselFilter`` builds its filter in the ``(b, a)`` form and runs ``filtfilt``, guarded by
a magic constant (``_validate_settings:95`` refuses any pole with modulus at or above
0.975) because that form goes numerically unstable at low normalised cutoffs. scipy's
second-order-sections form, ``bessel(..., output="sos")`` with ``sosfiltfilt``, is the
reference here: at the conformance settings the two must agree, and the low cutoffs the
guard refuses today must be accepted and agree too once 2.1 step 3 moves the plugin to the
sos form. No filter golden existed before; the reference is computed in the test rather
than stored, so there is nothing to regenerate.

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
#: not identically, and the difference decays within a few hundred samples.
EDGE = 400
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


def assert_matches_reference(filtered: np.ndarray, reference: np.ndarray) -> None:
    """
    Compare a plugin output with the reference, interior tightly and edges loosely.

    :param filtered: the plugin's output
    :type filtered: numpy.ndarray
    :param reference: the sos reference
    :type reference: numpy.ndarray
    """
    interior = slice(EDGE, -EDGE)
    worst = float(np.max(np.abs(filtered[interior] - reference[interior])))
    assert worst <= INTERIOR_ATOL_PA, f"interior disagreement {worst:.3g} pA"
    edges = np.r_[
        np.abs(filtered[:EDGE] - reference[:EDGE]),
        np.abs(filtered[-EDGE:] - reference[-EDGE:]),
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
    assert_matches_reference(filtered, reference)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BesselFilter._validate_settings:95 refuses any cutoff whose (b, a) poles reach "
        "0.975 in modulus - 25 kHz at 4.17 MHz among them - because that form is "
        "unstable there; the sos form is not, and step 3 adopts it"
    ),
)
def test_a_low_cutoff_the_guard_refuses_is_accepted_and_matches_the_reference(
    trace: np.ndarray,
) -> None:
    """A 25 kHz Bessel over a 4.17 MHz recording is an ordinary request and must work."""
    samplerate, cutoff, poles = 4_170_000.0, 25_000.0, 8
    plugin = build_bessel_filter(samplerate, cutoff, poles)
    try:
        filtered = plugin.filter_data(trace.copy())
    finally:
        plugin.close_resources()
    assert_matches_reference(filtered, sos_reference(trace, samplerate, cutoff, poles))
