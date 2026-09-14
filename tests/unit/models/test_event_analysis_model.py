"""
Unit-test suite for EventAnalysisModel.

``EventAnalysisModel`` was the last ``def _init(self): pass`` Model in the repository
- the shape section 01 of the refactor plan opens on. Step 4's first closeout branch
gave it its first real method, ``event_time_bases``, which builds the time axis the
event plot draws against.

**Why the axis belongs here.** It is a property of the samples and the rate they were
taken at, both of which the Model already owns; deriving it in the widget put
``np.arange`` on a ``QWidget`` and was the only computation keeping numpy in
``EventAnalysisView``. The same expression appears in three more Views and each will
come here by the same route. Pure styling - axis limits, tick formatting - stays in
the View by decision, see ``DECISIONS.md`` 2026-09-14.
"""

import numpy as np
import pytest

from poriscope.plugins.analysistabs.EventAnalysisModel import EventAnalysisModel
from poriscope.utils.MetaModel import MetaModel


@pytest.fixture
def model():
    """
    An EventAnalysisModel to compute with.

    :return: a constructed EventAnalysisModel
    :rtype: EventAnalysisModel
    """
    return EventAnalysisModel()


class TestConstruction:
    def test_instantiates_without_error(self, model):
        assert model is not None

    def test_is_instance_of_meta_model(self, model):
        assert isinstance(model, MetaModel)

    def test_init_returns_none(self, model):
        assert model._init() is None


class TestEventTimeBases:
    """
    One array per trace, index-aligned, in microseconds.

    An event contributes up to three traces - its filtered data, its fit and its raw
    trace - and they need not be the same length, which is why this is per trace
    rather than per event.
    """

    def test_one_array_per_trace(self, model):
        traces = [np.zeros(4), np.zeros(7), np.zeros(2)]

        assert [len(t) for t in model.event_time_bases(traces, 1e6)] == [4, 7, 2]

    def test_each_axis_matches_its_own_trace_length(self, model):
        """
        The traces need not agree in length, so a single shared axis would be wrong
        for all but one of them.
        """
        short, long = np.zeros(3), np.zeros(9)

        short_time, long_time = model.event_time_bases([short, long], 1e6)

        assert len(short_time) == 3
        assert len(long_time) == 9

    def test_the_axis_is_in_microseconds(self, model):
        """
        At 1 MHz one sample is one microsecond, so the axis counts samples exactly.

        Asserted against the rate rather than a recorded array: a golden would pass
        just as happily if the 1e6 conversion were dropped and the rate changed to
        match.
        """
        time = model.event_time_bases([np.zeros(5)], 1e6)[0]

        np.testing.assert_allclose(time, [0.0, 1.0, 2.0, 3.0, 4.0])

    def test_halving_the_rate_doubles_the_span(self, model):
        """The axis is real time, not sample index."""
        fast = model.event_time_bases([np.zeros(5)], 1e6)[0]
        slow = model.event_time_bases([np.zeros(5)], 5e5)[0]

        np.testing.assert_allclose(slow, fast * 2.0)

    def test_it_starts_at_zero(self, model):
        """Each event's axis is relative to that event, not to the recording."""
        time = model.event_time_bases([np.zeros(6)], 2.5e5)[0]

        assert time[0] == 0.0

    def test_a_samplerate_of_one_falls_back_to_sample_indices(self, model):
        """
        The Controller answers 1 when the loader cannot report a rate, so that the
        axis degrades to indices rather than failing. Scaled by 1e6 like any other
        rate, which is what makes the fallback visible as microseconds.
        """
        (time,) = model.event_time_bases([np.zeros(3)], 1)

        np.testing.assert_allclose(time, [0.0, 1e6, 2e6])

    def test_an_empty_trace_gives_an_empty_axis(self, model):
        (time,) = model.event_time_bases([np.zeros(0)], 1e6)

        assert len(time) == 0

    def test_no_traces_gives_no_axes(self, model):
        assert model.event_time_bases([], 1e6) == []
