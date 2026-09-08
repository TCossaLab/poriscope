# type: ignore
"""
Characterization tests for ``EventAnalysisView._handle_plot_events``.

At 243 lines this is the largest single method Step 4a still has to convert, and it
carries all eight of the tab's remaining ``global_signal`` emits. It is driven by the
event-analysis e2e click flow but **no test names it**, so none of its branching or its
assembly arithmetic was asserted - the same shape as RawData's equivalent, which turned
out to hide four unguarded stale reads.

Analysing it before writing anything turned up five things that reading it casually
would not, every one of which the conversion has to get right.

**1. Only two of the eight emits are stale reads, not four or more.** This method is
*better* guarded than RawData's was. ``data_filter`` and ``eventfitting_status`` are
cleared immediately before their emits. ``plot_data`` and the six feature attributes are
cleared immediately *after* each read, which leaves them ``None`` at the next emit, so a
swallowed dispatch is correctly seen as "no data" rather than as the previous event's.
What is unguarded is ``num_events_allowed`` - which bounds which event indices are
plotted - and ``plot_samplerate``.

**2. The bus applies three different unpacking rules here, all implicitly.**
``MainController._unpack_result`` splats a tuple return across the callback's parameters
and passes anything else whole, decided by the callee's *declared* return type. In this
one method that means ``load_event`` returns a ``Dict`` and is passed whole to
``update_plot_data``, which unwraps ``data["data"]``; ``get_fitted_event`` returns an
``Optional[NDArray]`` and is passed whole to the same method, which must *not* unwrap it;
and ``get_plot_features`` returns a six-``Tuple`` which is **splatted** across
``update_features``' six parameters. A conversion that treated these alike would be
wrong three ways.

**3. Two return-function names do not match their View methods.** The bus resolves the
return function on the *Controller*: ``set_event_filter`` forwards to
``MetaEventTabView.set_data_filter_function``, and ``update_features`` forwards to
``EventAnalysisView.update_plot_features``. The stub below carries that mapping, because
calling ``getattr(view, return_fn)`` would raise ``AttributeError`` into the method's own
handler and look like a code fault rather than a test fault - which is exactly how the
RawData equivalent misled once already.

**4. Two attributes are read without ever being declared.** ``EventAnalysisView._init``
is ``pass``, and ``num_events_allowed`` and the six feature attributes are assigned
*only* by their bus callbacks. So on a freshly built tab whose first dispatch fails,
reading them raises ``AttributeError``. For the features that lands inside the outer
handler and reports "Unable to plot event data"; for ``num_events_allowed`` the read sits
outside every ``try``, and ``handle_parameter_change`` has no handler either, so **it
escapes into Qt**. Both are pinned as current behaviour and queued rather than fixed
here, to keep this a pinning commit.

**5. The assembly arithmetic is the subtle part.** ``data_list`` and ``label_list`` take
one to three entries per event - "Data", then optionally "Raw", then optionally "Fit" -
while the six feature lists take exactly **one placeholder per event**, and features are
written to the last placeholder. So ``data_list`` is routinely longer than
``vertical_lines``, and ``num_events`` counts events rather than traces. Getting that
alignment wrong would mis-attach a fit's features to the wrong subplot, which no gate
would notice.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from tests.unit.views._qt_mocks import mock_axes, mock_figure, shadow_signals

pytestmark = pytest.mark.characterization

FAILS = object()

#: The bus names its return function on the Controller, and two of them differ from the
#: View method they forward to. Measured, not guessed.
RETURN_ON_VIEW = {
    "set_event_filter": "set_data_filter_function",
    "update_features": "update_plot_features",
}

#: Callees whose declared return type is a tuple, which ``_unpack_result`` splats across
#: the callback's parameters rather than passing whole.
SPLATTED = {"get_plot_features"}


@pytest.fixture
def view() -> EventAnalysisView:
    """
    An EventAnalysisView with no widget tree, wired to record and answer bus calls.

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


def wire(view: EventAnalysisView, **answers) -> EventAnalysisView:
    """
    Stub the bus the way ``_dispatch_to`` really behaves.

    A dispatch delivers its answer through the return function named in the emit,
    splatting it where the callee declares a tuple return; a *failed* dispatch delivers
    nothing at all, which is the case the emit-then-read pattern gets wrong and which a
    bare ``Mock`` cannot express. An answer given as a list is consumed one per call, for
    the per-event loop.

    :param view: the view to wire
    :type view: EventAnalysisView
    :param answers: answers keyed by plugin method name
    :type answers: dict
    :return: the same view, with ``calls`` recording every dispatch
    :rtype: EventAnalysisView
    """
    view.calls = []
    table = dict(answers)

    def deliver(metaclass, key, method, args, return_fn, extra):
        view.calls.append((metaclass, key, method, args, return_fn, extra))
        answer = table.get(method, FAILS)
        if isinstance(answer, list):
            answer = answer.pop(0) if answer else FAILS
        if answer is FAILS:
            return
        target = getattr(view, RETURN_ON_VIEW.get(return_fn, return_fn))
        if method in SPLATTED:
            target(*answer)
        else:
            target(answer)

    view.global_signal.emit.side_effect = deliver
    return view


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


def event(value: float) -> dict:
    """
    The dict shape ``load_event`` really returns.

    :param value: the value to fill the array with
    :type value: float
    :return: an event-data dict
    :rtype: dict
    """
    return {"data": np.full(4, value), "samplerate": 250000.0}


def features(vertical=None, horizontal=None, points=None) -> tuple:
    """
    The six-tuple ``get_plot_features`` really returns, in its declared order.

    :param vertical: vertical line positions
    :param horizontal: horizontal line positions
    :param points: labelled points
    :return: (vertical, horizontal, points, vlabels, hlabels, plabels)
    :rtype: tuple
    """
    return (
        vertical,
        horizontal,
        points,
        ["v"] if vertical else None,
        ["h"] if horizontal else None,
        ["p"] if points else None,
    )


def asked(view: EventAnalysisView, method: str) -> list:
    """
    Every dispatch of one plugin method.

    :param view: the wired view
    :type view: EventAnalysisView
    :param method: the plugin method name
    :type method: str
    :return: the matching recorded calls
    :rtype: list
    """
    return [call for call in view.calls if call[2] == method]


def plotted(view: EventAnalysisView) -> tuple:
    """
    The positional arguments the method handed to ``_update_event_plot``.

    :param view: the wired view
    :type view: EventAnalysisView
    :return: (data, labels, num_events, vlines, hlines, points, vlabels, hlabels, plabels)
    :rtype: tuple
    """
    return view._update_event_plot.call_args[0]


# ---------------------------------------------------------------------------
# the branches that stop early
# ---------------------------------------------------------------------------


def test_a_missing_channel_key_escapes_as_a_keyerror(view):
    """
    Current behaviour, and the third instance of this defect in the tab layer.

    ``_extract_plot_event_parameters`` reaches ``parameters["channel"]`` directly while
    the guard beside it catches only ``(IndexError, ValueError)``, so a dict without that
    key raises ``KeyError`` past a handler advertising "Parameter extraction failed".
    RawData's ``_handle_plot_events`` has the identical shape. Latent, because the
    controls panel always supplies ``channel``. Pinned as-is; queued.
    """
    wire(view)

    with pytest.raises(KeyError):
        view._handle_plot_events({})

    assert view.calls == []
    view._update_event_plot.assert_not_called()


def test_extraction_failure_asks_nothing(view):
    """A non-numeric channel is the shape the guard does catch."""
    wire(view)

    view._handle_plot_events(params(channel=["not-a-channel"]))

    assert view.calls == []
    view._update_event_plot.assert_not_called()


def test_multiple_channels_are_refused_before_any_dispatch(view):
    """``validate_single_channel`` raises ValueError, which the guard catches."""
    wire(view)

    view._handle_plot_events(params(channel=["0", "1"]))

    assert view.calls == []
    view._update_event_plot.assert_not_called()


def test_no_selected_events_asks_only_for_the_count(view):
    """Nothing to plot, so the filter, samplerate and loads are never reached."""
    wire(view, get_num_events=5)

    view._handle_plot_events(params(event_index=[]))

    assert [call[2] for call in view.calls] == ["get_num_events"]
    view._update_event_plot.assert_not_called()


def test_every_event_failing_reports_rather_than_plotting(view):
    """The user is told, rather than shown an empty figure."""
    wire(view, get_num_events=5, load_event=[FAILS, FAILS])

    view._handle_plot_events(params(event_index=[0, 1]))

    view._update_event_plot.assert_not_called()
    view.add_text_to_display.emit.assert_called_once()


# ---------------------------------------------------------------------------
# what each dispatch carries
# ---------------------------------------------------------------------------


def test_the_count_is_asked_of_the_loader_for_the_channel(view):
    """First question, and it takes the channel as an int in a one-element tuple."""
    wire(view, get_num_events=5, load_event=[event(1.0)])

    view._handle_plot_events(params(channel=["3"]))

    call = asked(view, "get_num_events")[0]
    assert (call[0], call[1], call[3]) == ("MetaEventLoader", "loader", (3,))


def test_out_of_bounds_indices_are_dropped_against_the_reported_count(view):
    """The loader's count is the bound, and indices at or above it go."""
    wire(view, get_num_events=2, load_event=[event(1.0), event(2.0)])

    view._handle_plot_events(params(event_index=[0, 1, 2, 9]))

    assert [call[3][1] for call in asked(view, "load_event")] == [0, 1]


def test_no_filter_asks_for_no_callable(view):
    """"No Filter" is a real selection, so the filter plugin is not consulted."""
    wire(view, get_num_events=5, load_event=[event(1.0)])

    view._handle_plot_events(params(filter="No Filter"))

    assert asked(view, "get_callable_filter") == []


def test_a_named_filter_is_fetched_once_and_reaches_every_load(view):
    """One fetch, then the same callable on each load."""
    wire(
        view,
        get_num_events=5,
        get_callable_filter="a-callable",
        load_event=[event(1.0), event(2.0)],
    )

    view._handle_plot_events(params(filter="F1", event_index=[0, 1]))

    assert len(asked(view, "get_callable_filter")) == 1
    for call in asked(view, "load_event"):
        assert call[3][2] == "a-callable"


def test_the_samplerate_is_asked_of_the_loader_with_the_channel(view):
    """
    Unlike the event finder's no-argument version, the loader's takes the channel.

    Worth pinning because the two are easy to conflate when converting both tabs.
    """
    wire(view, get_num_events=5, get_samplerate=250000.0, load_event=[event(1.0)])

    view._handle_plot_events(params(channel=["2"]))

    call = asked(view, "get_samplerate")[0]
    assert (call[0], call[3]) == ("MetaEventLoader", (2,))
    assert view.plot_samplerate == 250000.0


def test_each_event_is_loaded_with_the_channel_index_and_filter(view):
    """``load_event(channel, index, data_filter=None)``, written from the signature."""
    wire(view, get_num_events=9, load_event=[event(1.0), event(2.0)])

    view._handle_plot_events(params(channel=["2"], event_index=[5, 6]))

    assert [call[3] for call in asked(view, "load_event")] == [
        (2, 5, None),
        (2, 6, None),
    ]


# ---------------------------------------------------------------------------
# the raw overlay
# ---------------------------------------------------------------------------


def test_raw_is_not_loaded_without_a_filter(view):
    """There is nothing to compare an unfiltered trace against."""
    wire(view, get_num_events=5, load_event=[event(1.0)])

    view._handle_plot_events(params(raw=True))

    assert len(asked(view, "load_event")) == 1


def test_raw_is_loaded_unfiltered_alongside_the_filtered_trace(view):
    """
    The second load passes ``None`` where the first passed the callable.

    That is what makes it the raw trace rather than a duplicate of the filtered one.
    """
    wire(
        view,
        get_num_events=5,
        get_callable_filter="a-callable",
        load_event=[event(1.0), event(9.0)],
    )

    view._handle_plot_events(params(filter="F1", raw=True))

    loads = asked(view, "load_event")
    assert [call[3][2] for call in loads] == ["a-callable", None]


def test_the_raw_trace_shares_its_event_s_subplot(view):
    """
    Two traces, two labels, **one** feature placeholder, and num_events of 1.

    This is the alignment that matters: the feature lists are indexed per *event*, not
    per trace, so a conversion that appended a placeholder for the raw trace would
    silently shift every later event's features onto the wrong subplot.
    """
    wire(
        view,
        get_num_events=5,
        get_callable_filter="a-callable",
        load_event=[event(1.0), event(9.0)],
    )

    view._handle_plot_events(params(filter="F1", raw=True))

    data, labels, num_events, vlines, hlines, points, *_ = plotted(view)
    assert len(data) == 2
    assert labels == ["Event 0 Data", "Event 0 Raw"]
    assert num_events == 1
    assert len(vlines) == len(hlines) == len(points) == 1


# ---------------------------------------------------------------------------
# the fit overlay
# ---------------------------------------------------------------------------


def test_no_event_fitter_asks_the_fitter_nothing(view):
    """The placeholder is a real selection, not a fitter key."""
    wire(view, get_num_events=5, load_event=[event(1.0)])

    view._handle_plot_events(params(eventfitter="No Event Fitter"))

    assert asked(view, "get_eventfitting_status") == []
    assert asked(view, "get_fitted_event") == []


def test_an_unfitted_channel_loads_no_fit(view):
    """The status gates both the fit and its features."""
    wire(
        view,
        get_num_events=5,
        load_event=[event(1.0)],
        get_eventfitting_status=False,
    )

    view._handle_plot_events(params(eventfitter="ef1"))

    assert len(asked(view, "get_eventfitting_status")) == 1
    assert asked(view, "get_fitted_event") == []
    assert asked(view, "get_plot_features") == []


def test_a_fitted_event_appends_its_fit_as_a_third_trace(view):
    """
    Data, then Fit - and still one feature placeholder for the event.

    ``get_fitted_event`` returns a bare array rather than a dict, so it must not be
    unwrapped the way ``load_event``'s answer is.
    """
    wire(
        view,
        get_num_events=5,
        load_event=[event(1.0)],
        get_eventfitting_status=True,
        get_fitted_event=np.full(4, 7.0),
        get_plot_features=features(),
    )

    view._handle_plot_events(params(eventfitter="ef1"))

    data, labels, num_events, vlines, *_ = plotted(view)
    assert labels == ["Event 0 Data", "Event 0 Fit"]
    assert [float(trace[0]) for trace in data] == [1.0, 7.0]
    assert num_events == 1
    assert len(vlines) == 1


def test_the_features_land_on_the_event_s_own_placeholder(view):
    """
    The six-tuple is splatted across ``update_features``' parameters by the bus, and
    each kind is written to the last placeholder - the one belonging to this event.
    """
    wire(
        view,
        get_num_events=5,
        load_event=[event(1.0)],
        get_eventfitting_status=True,
        get_fitted_event=np.full(4, 7.0),
        get_plot_features=features(vertical=[1.0], horizontal=[2.0], points=[(3.0, 4.0)]),
    )

    view._handle_plot_events(params(eventfitter="ef1"))

    _, _, _, vlines, hlines, points, vlabels, hlabels, plabels = plotted(view)[:9]
    assert vlines == [[1.0]]
    assert hlines == [[2.0]]
    assert points == [[(3.0, 4.0)]]
    assert (vlabels, hlabels, plabels) == ([["v"]], [["h"]], [["p"]])


def test_an_event_without_features_keeps_its_none_placeholder(view):
    """
    A fitter that supplies no features leaves the placeholder as None.

    The placeholder is still there, so the per-event indexing holds.
    """
    wire(
        view,
        get_num_events=5,
        load_event=[event(1.0)],
        get_eventfitting_status=True,
        get_fitted_event=np.full(4, 7.0),
        get_plot_features=features(),
    )

    view._handle_plot_events(params(eventfitter="ef1"))

    _, _, _, vlines, hlines, points, *_ = plotted(view)
    assert vlines == [None]
    assert hlines == [None]
    assert points == [None]


# ---------------------------------------------------------------------------
# the loop's own arithmetic
# ---------------------------------------------------------------------------


def test_one_placeholder_per_event_across_several_events(view):
    """
    Three events, each with data and a fit: six traces, three placeholders.

    The invariant a conversion is most likely to break.
    """
    wire(
        view,
        get_num_events=9,
        load_event=[event(1.0), event(2.0), event(3.0)],
        get_eventfitting_status=True,
        get_fitted_event=[np.full(4, 7.0), np.full(4, 8.0), np.full(4, 9.0)],
        get_plot_features=[features(), features(), features()],
    )

    view._handle_plot_events(params(eventfitter="ef1", event_index=[0, 1, 2]))

    data, labels, num_events, vlines, *_ = plotted(view)
    assert len(data) == 6
    assert len(vlines) == 3
    assert num_events == 3
    assert labels == [
        "Event 0 Data",
        "Event 0 Fit",
        "Event 1 Data",
        "Event 1 Fit",
        "Event 2 Data",
        "Event 2 Fit",
    ]


def test_an_event_with_no_data_is_dropped_without_a_placeholder(view):
    """
    A failed load skips the event entirely - no trace, no label, no placeholder.

    The surviving events keep their own features, which is what the alignment is for.
    """
    wire(
        view,
        get_num_events=9,
        load_event=[event(1.0), FAILS, event(3.0)],
    )

    view._handle_plot_events(params(event_index=[0, 1, 2]))

    data, labels, num_events, vlines, *_ = plotted(view)
    assert labels == ["Event 0 Data", "Event 2 Data"]
    assert [float(trace[0]) for trace in data] == [1.0, 3.0]
    assert num_events == 2
    assert len(vlines) == 2


def test_use_raw_is_passed_through_to_the_plot(view):
    """The checkbox state reaches the plotting call, not just the loads."""
    wire(
        view,
        get_num_events=5,
        get_callable_filter="a-callable",
        load_event=[event(1.0), event(9.0)],
    )

    view._handle_plot_events(params(filter="F1", raw=True))

    assert view._update_event_plot.call_args[1]["use_raw"] is True


# ---------------------------------------------------------------------------
# two latent defects, pinned as current behaviour and queued
# ---------------------------------------------------------------------------


def test_an_unreadable_count_escapes_as_an_attributeerror(view):
    """
    Current behaviour, and the more serious of the two: it reaches Qt.

    ``_init`` is ``pass`` and ``num_events_allowed`` is assigned only by the bus
    callback, so a freshly built tab whose first ``get_num_events`` dispatch fails reads
    an attribute that does not exist. The read sits outside every ``try``, and
    ``handle_parameter_change`` has no handler either, so it escapes the tab entirely.
    Pinned as-is; queued in ``future_fixes.md``.
    """
    wire(view)  # get_num_events answers FAILS

    with pytest.raises(AttributeError):
        view._handle_plot_events(params(event_index=[0]))


def test_unreadable_features_abandon_the_plot(view):
    """
    Current behaviour, and the milder of the two: it is swallowed.

    The six feature attributes are likewise assigned only by their callback, and the
    read is inside the outer handler, so a first-ever failure reports "Unable to plot
    event data" and draws nothing - having already loaded the traces. Pinned as-is.
    """
    wire(
        view,
        get_num_events=5,
        load_event=[event(1.0)],
        get_eventfitting_status=True,
        get_fitted_event=np.full(4, 7.0),
    )  # get_plot_features answers FAILS

    view._handle_plot_events(params(eventfitter="ef1"))

    view._update_event_plot.assert_not_called()
