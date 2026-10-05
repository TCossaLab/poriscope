"""
Behavioural conformance for every discovered ``MetaFilter``.

Filters are the one data-plugin family with no parent and no file: they take an
array and return one. That makes the contract narrow and worth stating exactly -
shape and dtype preserved, output finite, and the filter actually filtering rather
than handing the input straight back.

Neither filter was driven by any test before this module. ``BesselFilter`` appears in
``tests/integration/flows`` only to have its settings asserted, and the event-finding
flow there deliberately passes an identity function instead of the filter, so
``_apply_filter`` was never called on real data. ``WaveletFilter`` had no coverage at
all.
"""

from typing import List, Type

import numpy as np
import pytest

from poriscope.utils.MetaFilter import MetaFilter
from tests.unit.plugins.conformance._recipes import build_filter, discover_concrete

BASELINE_PA = 2000.0
NOISE_STD_PA = 15.0
EVENT_AMPLITUDE_PA = -400.0
TRACE_SAMPLES = 40_000

FILTERS: List[Type[MetaFilter]] = discover_concrete(MetaFilter)

filter_cases = pytest.mark.parametrize(
    "filter_cls", FILTERS, ids=[cls.__name__ for cls in FILTERS]
)


@pytest.fixture
def trace() -> np.ndarray:
    """
    A noisy baseline with one square blockage in the middle.

    Same baseline, noise and amplitude as every other fixture in the suite, sampled
    at ``FILTER_SAMPLERATE_HZ`` so a filter configured from the recipe sees data at
    the rate it was told about.

    :return: Signal in pA.
    :rtype: numpy.ndarray
    """
    rng = np.random.default_rng(seed=11)
    data = rng.normal(BASELINE_PA, NOISE_STD_PA, TRACE_SAMPLES)
    quarter = TRACE_SAMPLES // 4
    data[quarter : 2 * quarter] += EVENT_AMPLITUDE_PA
    return data


@pytest.mark.conformance
@filter_cases
def test_filter_preserves_shape_and_dtype(
    filter_cls: Type[MetaFilter], trace: np.ndarray
) -> None:
    """
    A filter returns a finite float64 array of the same shape it was given.

    Event finders hand chunks straight from a reader into the filter and index the
    result against the unfiltered trace, so a filter that changed length or dtype
    would corrupt every event boundary downstream.

    :param filter_cls: The filter class under test.
    :type filter_cls: Type[MetaFilter]
    :param trace: Synthetic signal to filter.
    :type trace: numpy.ndarray
    """
    plugin = build_filter(filter_cls)
    try:
        result = plugin.filter_data(trace.copy())

        assert isinstance(result, np.ndarray), f"returned {type(result).__name__}"
        assert result.shape == trace.shape, f"{trace.shape} became {result.shape}"
        assert result.dtype == np.float64, f"dtype is {result.dtype}"
        assert np.all(np.isfinite(result)), "filtered data contains inf or nan"
    finally:
        plugin.close_resources()


@pytest.mark.conformance
@filter_cases
def test_filter_actually_filters(
    filter_cls: Type[MetaFilter], trace: np.ndarray
) -> None:
    """
    A filter changes the data and leaves the blockage detectable.

    Two failure modes this rules out: a ``_apply_filter`` that returns its input
    unchanged, which would pass every shape check; and one so aggressive it flattens
    the signal, which would leave a finder nothing to find. The blockage is checked
    for surviving with most of its depth rather than for an exact value, since how
    much a filter smooths its edges is the filter's business.

    :param filter_cls: The filter class under test.
    :type filter_cls: Type[MetaFilter]
    :param trace: Synthetic signal to filter.
    :type trace: numpy.ndarray
    """
    plugin = build_filter(filter_cls)
    try:
        result = plugin.filter_data(trace.copy())

        assert not np.allclose(result, trace), "filter returned its input unchanged"

        quarter = TRACE_SAMPLES // 4
        blocked = result[quarter + 500 : 2 * quarter - 500].mean()
        baseline = result[2 * quarter + 500 :].mean()
        depth = baseline - blocked
        assert depth > abs(EVENT_AMPLITUDE_PA) * 0.5, (
            f"blockage depth collapsed to {depth:.1f} pA from a planted "
            f"{abs(EVENT_AMPLITUDE_PA):.1f} pA"
        )
    finally:
        plugin.close_resources()


@pytest.mark.conformance
@filter_cases
def test_callable_filter_matches_filter_data(
    filter_cls: Type[MetaFilter], trace: np.ndarray
) -> None:
    """
    ``get_callable_filter()`` returns something equivalent to ``filter_data``.

    Event finders and fitters take the callable, not the plugin, so the two paths
    have to agree - a subclass that overrode one and not the other would give
    different results depending on which entry point the caller used.

    :param filter_cls: The filter class under test.
    :type filter_cls: Type[MetaFilter]
    :param trace: Synthetic signal to filter.
    :type trace: numpy.ndarray
    """
    plugin = build_filter(filter_cls)
    try:
        callable_filter = plugin.get_callable_filter()
        assert callable(
            callable_filter
        ), "get_callable_filter did not return a callable"
        np.testing.assert_allclose(
            callable_filter(trace.copy()), plugin.filter_data(trace.copy())
        )
    finally:
        plugin.close_resources()


@pytest.mark.conformance
@filter_cases
def test_reset_and_close_are_safe(
    filter_cls: Type[MetaFilter], trace: np.ndarray
) -> None:
    """
    A filter survives reset and repeated close, and still filters afterwards.

    :param filter_cls: The filter class under test.
    :type filter_cls: Type[MetaFilter]
    :param trace: Synthetic signal to filter.
    :type trace: numpy.ndarray
    """
    plugin = build_filter(filter_cls)
    first = plugin.filter_data(trace.copy())
    plugin.reset_channel()
    np.testing.assert_allclose(
        plugin.filter_data(trace.copy()),
        first,
        err_msg="filtering is not repeatable across reset_channel",
    )
    plugin.close_resources()
    plugin.close_resources()


@pytest.mark.conformance
def test_at_least_one_filter_was_discovered() -> None:
    """
    Guard against the discovery walk silently finding nothing.

    Every check in this module is parametrised over ``FILTERS``; an empty list would
    make the whole file pass without running a single filter.
    """
    assert FILTERS, "no concrete MetaFilter subclasses were discovered"
