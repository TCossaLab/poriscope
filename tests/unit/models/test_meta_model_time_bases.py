"""
``MetaModel.time_bases`` - the plot time axis, on the Model side.

This moved off the Views. The axis is a property of the samples and
the rate they were taken at, both of which the Model owns, and it is *data* rather than
styling: it is the x-coordinate of every point drawn, it goes into ``_update_cache``, and
the user exports it to CSV. Axis limits, which never leave the View, stayed there - see
``DECISIONS.md`` 2026-09-14 for the line and why "derived from the data" turned out to be
the wrong test for drawing it.

It began as ``EventAnalysisModel.event_time_bases`` and was promoted here when the RawData
branch found the second caller. ``scale`` and ``offset`` exist because the same derivation
serves two axes that differ only in units and origin - an event plot wants microseconds
from the start of the event, a trace plot wants seconds from the start of the recording -
and four of the five tabs plot event traces this way.

These tests came with the method rather than being written after it, so their passing here
is the evidence the promotion changed nothing.
"""

from typing import override

import numpy as np
import pytest

from poriscope.utils.MetaModel import MetaModel


class _ConcreteModel(MetaModel):
    """A minimal concrete MetaModel, since the base is abstract."""

    @override
    def _init(self) -> None:
        pass


@pytest.fixture
def model():
    """
    A concrete MetaModel to build axes with.

    :return: the model under test
    :rtype: _ConcreteModel
    """
    return _ConcreteModel()


class TestTimeBases:
    """One array per trace, index-aligned, scaled and offset as asked."""

    def test_one_array_per_trace(self, model):
        traces = [np.zeros(4), np.zeros(7), np.zeros(2)]

        assert [len(t) for t in model.time_bases(traces, 1e6)] == [4, 7, 2]

    def test_each_axis_matches_its_own_trace_length(self, model):
        """
        The traces need not agree in length - an event contributes its data, its fit
        and its raw trace - so a single shared axis would be wrong for all but one.
        """
        short, long = np.zeros(3), np.zeros(9)

        short_time, long_time = model.time_bases([short, long], 1e6)

        assert len(short_time) == 3
        assert len(long_time) == 9

    def test_the_default_axis_is_in_seconds(self, model):
        """At 1 MHz, without a scale, one sample is one microsecond of a second."""
        (time,) = model.time_bases([np.zeros(5)], 1e6)

        np.testing.assert_allclose(time, [0.0, 1e-6, 2e-6, 3e-6, 4e-6])

    def test_a_microsecond_scale_gives_sample_counts_at_one_megahertz(self, model):
        """
        The event plots ask for ``scale=1e6``. Asserted against the rate rather than a
        recorded array: a golden would pass just as happily if the scale were dropped
        and the rate changed to match.
        """
        (time,) = model.time_bases([np.zeros(5)], 1e6, scale=1e6)

        np.testing.assert_allclose(time, [0.0, 1.0, 2.0, 3.0, 4.0])

    def test_halving_the_rate_doubles_the_span(self, model):
        """The axis is real time, not sample index."""
        fast = model.time_bases([np.zeros(5)], 1e6, scale=1e6)[0]
        slow = model.time_bases([np.zeros(5)], 5e5, scale=1e6)[0]

        np.testing.assert_allclose(slow, fast * 2.0)

    def test_without_an_offset_it_starts_at_zero(self, model):
        """Each event's axis is relative to that event, not to the recording."""
        (time,) = model.time_bases([np.zeros(6)], 2.5e5, scale=1e6)

        assert time[0] == 0.0

    def test_an_offset_places_the_axis_in_the_recording(self, model):
        """
        The trace plot asks for this: the user chose a start time, and the axis has to
        read as that part of the file rather than as a fresh window.
        """
        (time,) = model.time_bases([np.zeros(4)], 1e3, offset=7.5)

        np.testing.assert_allclose(time, [7.5, 7.501, 7.502, 7.503])

    def test_the_offset_is_applied_after_the_scale(self, model):
        """
        Order matters and is not obvious: an offset added before scaling would be
        multiplied by it, putting a trace plot's start time out by a factor of 1e6 if
        the two were ever combined.
        """
        (time,) = model.time_bases([np.zeros(3)], 1e6, scale=1e6, offset=10.0)

        np.testing.assert_allclose(time, [10.0, 11.0, 12.0])

    def test_a_samplerate_of_one_falls_back_to_sample_indices(self, model):
        """
        The Controller answers 1 when the reader cannot report a rate, so the axis
        degrades to indices rather than failing.
        """
        (time,) = model.time_bases([np.zeros(3)], 1)

        np.testing.assert_allclose(time, [0.0, 1.0, 2.0])

    def test_an_empty_trace_gives_an_empty_axis(self, model):
        (time,) = model.time_bases([np.zeros(0)], 1e6)

        assert len(time) == 0

    def test_no_traces_gives_no_axes(self, model):
        assert model.time_bases([], 1e6) == []
