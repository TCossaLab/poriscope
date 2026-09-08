# type: ignore
"""
Characterization tests for ``EventAnalysisView``'s half of the event-plotting path.

Before Step 4a this module pinned the whole of ``_handle_plot_events`` - 243 lines and
all eight of the tab's ``global_signal`` emits - because no test named it. The
conversion moved the calls and the assembly to ``EventAnalysisController``, and those
invariants moved with them to ``tests/unit/controllers/test_event_analysis_controller.py``.

**Eighteen of the twenty-four failed on conversion and five of the six survivors were
vacuous**, which is the ratio worth recording: they asserted ``view.calls == []`` or
``assert_not_called()``, both trivially true of a View that no longer emits or plots.
Only the ``KeyError`` pin survived on its own merits. Everything here now targets what
the View still owns: extracting and validating the parameters, emitting one typed
intent, and drawing what comes back.

The analysis that made the conversion correct is recorded in the commit that added this
file; the findings it turned up - three implicit unpacking rules, two Controller-side
return-function names that differ from their View methods, and the per-event feature
alignment - are asserted on the Controller side now, where the code lives.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from tests.unit.views._qt_mocks import mock_axes, mock_figure, shadow_signals

pytestmark = pytest.mark.characterization


@pytest.fixture
def view() -> EventAnalysisView:
    """
    An EventAnalysisView with no widget tree and its plot call observable.

    :return: the view under test
    :rtype: EventAnalysisView
    """
    instance = EventAnalysisView.__new__(EventAnalysisView)
    instance.figure = mock_figure()
    instance.axes = mock_axes()
    instance.canvas = MagicMock()
    instance.eventAnalysisControls = MagicMock()
    shadow_signals(instance, EventAnalysisView)
    instance.plot_data = None
    instance._update_event_plot = MagicMock()
    return instance


def params(**over) -> dict:
    """
    A parameter dict of the shape the controls panel emits.

    :param over: keys to override
    :type over: dict
    :return: the parameter dict
    :rtype: dict
    """
    base = {
        "loader": "loader",
        "eventfitter": "No Event Fitter",
        "filter": "No Filter",
        "channel": ["0"],
        "event_index": [0],
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# what the View refuses on its own
# ---------------------------------------------------------------------------


def test_a_missing_channel_key_escapes_as_a_keyerror(view):
    """
    Current behaviour, and the third instance of this defect in the tab layer.

    ``_extract_plot_event_parameters`` reaches ``parameters["channel"]`` directly while
    the guard beside it catches only ``(IndexError, ValueError)``, so a dict without that
    key raises ``KeyError`` past a handler advertising "Parameter extraction failed".
    RawData's ``_handle_plot_events`` has the identical shape. Latent, because the
    controls panel always supplies ``channel``.

    This is the one test in the original class that survived the conversion on its own
    merits rather than by going quiet.
    """
    with pytest.raises(KeyError):
        view._handle_plot_events({})

    view.event_plot_requested.emit.assert_not_called()


def test_a_non_numeric_channel_is_caught_and_requests_nothing(view):
    """The shape the guard does catch."""
    view._handle_plot_events(params(channel=["not-a-channel"]))

    view.event_plot_requested.emit.assert_not_called()
    view._update_event_plot.assert_not_called()


def test_multiple_channels_are_refused_before_asking(view):
    """
    ``validate_single_channel`` raises ValueError, which the same guard catches.

    Events from two channels cannot share a plot.
    """
    view._handle_plot_events(params(channel=["0", "1"]))

    view.event_plot_requested.emit.assert_not_called()


# ---------------------------------------------------------------------------
# the intent
# ---------------------------------------------------------------------------


def test_the_intent_carries_everything_the_controller_needs(view):
    """The channel arrives as a single int, not the one-element list it came in."""
    view._handle_plot_events(
        params(
            loader="ldr",
            eventfitter="ef1",
            channel=["3"],
            event_index=[5, 6],
            filter="F1",
            raw=True,
        )
    )

    view.event_plot_requested.emit.assert_called_once_with(
        "ldr", "ef1", 3, [5, 6], "F1", True
    )


def test_no_filter_is_carried_as_an_empty_key(view):
    """The Controller never has to know the placeholder's spelling."""
    view._handle_plot_events(params(filter="No Filter"))

    assert view.event_plot_requested.emit.call_args[0][4] == ""


def test_no_selected_events_is_carried_as_an_empty_list(view):
    """
    ``event_index`` is absent or None when nothing is selected.

    The intent is still emitted: the Controller asks the loader for its event count
    either way, which is the behaviour the pre-conversion code had.
    """
    view._handle_plot_events(params(event_index=None))

    assert view.event_plot_requested.emit.call_args[0][3] == []


def test_raw_defaults_to_false_when_absent(view):
    """The checkbox key is not always present in the parameter dict."""
    bare = params()
    bare.pop("raw", None)

    view._handle_plot_events(bare)

    assert view.event_plot_requested.emit.call_args[0][5] is False


# ---------------------------------------------------------------------------
# drawing the answer
# ---------------------------------------------------------------------------


def test_set_event_plot_data_reports_when_nothing_loaded(view):
    """The user is told, rather than shown an empty figure."""
    view.set_event_plot_data([], [], 0, [], [], [], [], [], [], False)

    view._update_event_plot.assert_not_called()
    view.add_text_to_display.emit.assert_called_once()


def test_set_event_plot_data_forwards_every_argument(view):
    """
    A thin pass-through: the Controller built the lists aligned, so this must not
    try to line them up again.

    Note ``event_data`` is longer than the feature lists here, which is the normal case
    once a fit is drawn - one to three traces per event against one placeholder each.
    """
    data = [np.full(4, 1.0), np.full(4, 7.0)]
    labels = ["Event 0 Data", "Event 0 Fit"]

    view.set_event_plot_data(
        data,
        labels,
        1,
        [[1.0]],
        [[2.0]],
        [[(3.0, 4.0)]],
        [["v"]],
        [["h"]],
        [["p"]],
        True,
    )

    args, kwargs = view._update_event_plot.call_args
    assert args[0] is data
    assert args[1] is labels
    assert args[2] == 1
    assert args[3:9] == ([[1.0]], [[2.0]], [[(3.0, 4.0)]], [["v"]], [["h"]], [["p"]])
    assert kwargs == {"use_raw": True}
