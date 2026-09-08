"""
Characterization tests for ``RawDataView``'s baseline and Gaussian-fit numerics.

These three methods had **no test anywhere in the repository**, despite
``test_raw_data_view.py``'s module docstring listing ``_get_baseline_stats`` in its
coverage roster - that line is stale, and correcting it is part of this change. The
``_get_baseline_stats`` tests that do exist are for ``MetaEventFinder``'s method of
the same name, which is a different implementation.

``_gaussian_fit`` is the most numerically intricate method in the five analysis-tab
Views: a contiguous threshold mask, standardisation, a 3x3 weighted-log moment
matrix, ``np.linalg.inv``, then de-standardisation. Its own source comments call
that last step "THE CRITICAL MATH FIX". Step 4c moves all of this to the Model, and
until now nothing would have noticed if the numbers changed on the way.

The parameter sweep is pinned with ``pytest-regressions``' ``num_regression``,
which is where that dependency earns its place: a dozen fits x three recovered
parameters is a real array golden, and any drift in the linear algebra shows up as
a diff. The guards and the round-trip properties are asserted explicitly, because a
golden file for a three-element tuple is less legible than the literal.
"""

from unittest.mock import MagicMock

import numpy as np
import numpy.typing as npt
import pytest
from PySide6.QtWidgets import QMessageBox

from poriscope.plugins.analysistabs.RawDataView import RawDataView
from tests.unit.views._qt_mocks import mock_figure, shadow_signals

pytestmark = pytest.mark.characterization


@pytest.fixture
def view() -> RawDataView:
    """
    Build a RawDataView without constructing any Qt widget.

    ``__new__`` skips the widget tree entirely. The three methods under test read
    nothing off ``self`` but the logger, which is a class attribute and is
    deliberately **not** mocked - replacing it blinds ``caplog``, which is the trap
    ``_qt_mocks.py``'s docstring warns about and which the older
    ``test_raw_data_view.py`` fixture falls into.

    :return: a RawDataView with its signals shadowed and nothing else built
    :rtype: RawDataView
    """
    instance = RawDataView.__new__(RawDataView)
    shadow_signals(instance, RawDataView)
    return instance


def gaussian_curve(
    amplitude: float, mean: float, sigma: float, points: int = 201, span: float = 4.0
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """
    Build a clean Gaussian sampled over +/- ``span`` standard deviations.

    :param amplitude: peak height
    :type amplitude: float
    :param mean: centre of the distribution
    :type mean: float
    :param sigma: standard deviation
    :type sigma: float
    :param points: number of samples
    :type points: int
    :param span: half-width of the sampled window, in standard deviations
    :type span: float
    :return: the bin centres and the curve values
    :rtype: tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]
    """
    centres = np.linspace(mean - span * sigma, mean + span * sigma, points)
    values = amplitude * np.exp(-((centres - mean) ** 2) / (2 * sigma**2))
    return centres, values


class TestStartEventfinder:
    """
    The View half of the event-finding launch after Step 4a: ask, prompt, ask again.

    This class pinned all three bus round trips before the conversion - the filter
    callable, the per-channel status, and the per-channel ``find_events``. The plugin
    calls now live in ``tests/unit/controllers/test_raw_data_controller.py`` against
    ``request_eventfinding_statuses`` and ``start_eventfinding``. **Rewritten rather than
    deleted**, and all eleven failed outright rather than going quiet, which is the
    better outcome of the two: nothing here was left asserting something trivially true.

    One test is gone rather than moved. ``test_the_filter_is_cleared_before_it_is_fetched``
    pinned the clear-before-emit mitigation, and that mitigation existed only because the
    bus could fail silently and leave the previous run's callable in place. ``call()``
    raises, so there is nothing left to clear and nothing left to pin - which is the whole
    point of the step.

    What stays is what the View still owns: coercing the channel argument, prompting
    before redoing a finished channel, and turning stored time limits into ranges.
    """

    @pytest.fixture
    def wired(self, view: RawDataView):
        """
        A view with its two launch intents and its stored time limits observable.

        :param view: the bare view
        :type view: RawDataView
        :return: the view, ready to record
        :rtype: RawDataView
        """
        view.analysis_time_limits = {}
        return view

    @staticmethod
    def limits(view: RawDataView, finder: str, channel: int, spec: dict) -> None:
        """
        Install one channel's time limits.

        :param view: the view
        :type view: RawDataView
        :param finder: the eventfinder key
        :type finder: str
        :param channel: the channel number
        :type channel: int
        :param spec: the limit dict for that channel
        :type spec: dict
        :return: None
        :rtype: None
        """
        view.analysis_time_limits.setdefault(finder, {})[channel] = spec

    @staticmethod
    def approved(view: RawDataView) -> list:
        """
        The (channel, ranges) pairs the View asked to launch.

        :param view: the view
        :type view: RawDataView
        :return: the payload of the launch intent
        :rtype: list
        """
        return view.eventfinding_requested.emit.call_args[0][1]

    # -- the first half: asking for statuses -----------------------------

    def test_a_bare_channel_is_coerced_to_a_list(self, wired: RawDataView) -> None:
        """Callers pass either shape, and a bare int must not be iterated as one."""
        wired._start_eventfinder("finder", "No Filter", 0)

        wired.eventfinding_statuses_requested.emit.assert_called_once_with(
            "finder", [0], ""
        )

    def test_no_filter_is_carried_as_an_empty_key(self, wired: RawDataView) -> None:
        """The Controller never has to know the placeholder's spelling."""
        wired._start_eventfinder("finder", "No Filter", [0])

        assert wired.eventfinding_statuses_requested.emit.call_args[0][2] == ""

    def test_a_named_filter_is_carried_by_key(self, wired: RawDataView) -> None:
        """Fetching the callable is the Controller's job; naming it is the View's."""
        wired._start_eventfinder("finder", "F1", [0, 1])

        wired.eventfinding_statuses_requested.emit.assert_called_once_with(
            "finder", [0, 1], "F1"
        )

    # -- the prompt ------------------------------------------------------

    def test_an_unfinished_channel_is_approved_without_asking(
        self, wired: RawDataView, mocker
    ) -> None:
        """No prompt where there is nothing to overwrite."""
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})
        question = mocker.patch(
            "poriscope.plugins.analysistabs.RawDataView.QMessageBox.question"
        )

        wired.set_eventfinding_statuses("finder", [(0, False)], "")

        question.assert_not_called()
        assert [channel for channel, _ in self.approved(wired)] == [0]

    def test_declining_the_overwrite_prompt_skips_only_that_channel(
        self, wired: RawDataView, mocker
    ) -> None:
        """
        An already-finished channel asks before redoing it, and No means skip.

        The other channels still run, which is what a coarser guard would get wrong by
        abandoning the whole batch.
        """
        for channel in (0, 1):
            self.limits(wired, "finder", channel, {"start": 0.0, "end": 0.0})
        mocker.patch(
            "poriscope.plugins.analysistabs.RawDataView.QMessageBox.question",
            side_effect=[QMessageBox.No, QMessageBox.Yes],
        )

        wired.set_eventfinding_statuses("finder", [(0, True), (1, True)], "")

        assert [channel for channel, _ in self.approved(wired)] == [1]

    def test_declining_every_channel_launches_nothing(
        self, wired: RawDataView, mocker
    ) -> None:
        """An empty approval list is not a launch."""
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})
        mocker.patch(
            "poriscope.plugins.analysistabs.RawDataView.QMessageBox.question",
            return_value=QMessageBox.No,
        )

        wired.set_eventfinding_statuses("finder", [(0, True)], "")

        wired.eventfinding_requested.emit.assert_not_called()

    def test_the_filter_key_is_carried_through_to_the_launch(
        self, wired: RawDataView
    ) -> None:
        """
        The Controller hands it back rather than the View holding it between halves.

        One less piece of state that could go stale across a round trip.
        """
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})

        wired.set_eventfinding_statuses("finder", [(0, False)], "F1")

        assert wired.eventfinding_requested.emit.call_args[0][2] == "F1"

    # -- turning stored limits into ranges -------------------------------

    def test_explicit_ranges_are_used_and_copied(self, wired: RawDataView) -> None:
        """A copy, so the finder cannot mutate the tab's stored limits."""
        stored = [(1.0, 2.0), (3.0, 4.0)]
        self.limits(wired, "finder", 0, {"ranges": stored})

        wired.set_eventfinding_statuses("finder", [(0, False)], "")

        sent = self.approved(wired)[0][1]
        assert sent == stored
        assert sent is not stored

    def test_start_and_end_become_a_single_range(self, wired: RawDataView) -> None:
        """The common case: one span per channel."""
        self.limits(wired, "finder", 0, {"start": 1.5, "end": 3.0})

        wired.set_eventfinding_statuses("finder", [(0, False)], "")

        assert self.approved(wired)[0][1] == [(1.5, 3.0)]

    def test_a_falsy_end_becomes_zero_meaning_end_of_signal(
        self, wired: RawDataView
    ) -> None:
        """``None`` and ``0`` both mean "to the end", which the finder resolves."""
        self.limits(wired, "finder", 0, {"start": 2.0, "end": None})

        wired.set_eventfinding_statuses("finder", [(0, False)], "")

        assert self.approved(wired)[0][1] == [(2.0, 0.0)]

    def test_a_missing_channel_limit_stops_before_launching_anything(
        self, wired: RawDataView
    ) -> None:
        """
        A configuration gap launches nothing, as before - but reports rather than raises.

        It used to raise ``KeyError`` out of the tab, which was survivable while the call
        chain began at a Qt signal on the View. This method is now called from the
        Controller's slot, where an escaping exception would reach Qt, so it is reported
        on the status panel instead. Nothing launches either way, which is the property
        that matters.
        """
        wired.analysis_time_limits = {"finder": {}}

        wired.set_eventfinding_statuses("finder", [(0, False)], "")

        wired.eventfinding_requested.emit.assert_not_called()
        wired.add_text_to_display.emit.assert_called_once()

    def test_one_bad_channel_stops_the_whole_batch(self, wired: RawDataView) -> None:
        """
        Deliberately all-or-nothing, as it was.

        The old code emitted ``find_events`` per channel and only reached
        ``run_generators`` if every channel got that far, so a gap part way through left
        nothing running. Returning here preserves that.
        """
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})

        wired.set_eventfinding_statuses("finder", [(0, False), (1, False)], "")

        wired.eventfinding_requested.emit.assert_not_called()


class TestUpdatePsd:
    """
    The PSD axis-limit arithmetic, a Step 4c target the exit review found unpinned.

    ``update_psd`` executed under the raw-data e2e flow but no test named it, so
    nothing asserted the limits it computes. They are not cosmetic: the x limit is
    derived from where the RMS curve reaches 99.9% of its final value, and both y
    limits are snapped to half-decades, which is what keeps a noise spectrum
    readable rather than dominated by one spike.
    """

    @pytest.fixture
    def psd_view(self, view: RawDataView):
        """
        A view with a figure that really tracks the axes added to it.

        :param view: the bare view
        :type view: RawDataView
        :return: the view, ready to plot a PSD
        :rtype: RawDataView
        """
        view.figure = mock_figure()
        view.canvas = MagicMock()
        view.toolbar = MagicMock()
        view._clear_cache()
        return view

    def test_one_subplot_per_channel(self, psd_view: RawDataView) -> None:
        """The grid is sized by _factors, so three channels still get three axes."""
        frequency = np.logspace(0, 5, 200)
        psd = [np.full(200, 1e-3) + 1e-5 for _ in range(3)]
        rms = [np.linspace(1.0, 10.0, 200) for _ in range(3)]

        psd_view.update_psd(psd, rms, frequency, [0, 1, 2])

        assert psd_view.figure.add_subplot.call_count == 3

    def test_the_x_limit_is_the_decade_above_the_rms_plateau(
        self, psd_view: RawDataView
    ) -> None:
        """
        The upper x limit comes from where RMS reaches 99.9% of its final value,
        rounded up to the next decade - so a spectrum sampled to 100 kHz whose
        noise plateaus early is not plotted mostly empty.
        """
        frequency = np.logspace(0, 5, 200)
        rms = np.concatenate([np.linspace(1.0, 10.0, 100), np.full(100, 10.0)])
        psd = np.full(200, 1e-3)

        psd_view.update_psd([psd], [rms], frequency, [0])

        ax = psd_view.figure.get_axes()[0]
        _, upper = ax.set_xlim.call_args.args
        assert upper == pytest.approx(10 ** np.ceil(np.log10(frequency[100])))

    def test_the_y_limits_snap_to_half_decades(self, psd_view: RawDataView) -> None:
        """
        Both are rounded to the nearest half power of ten, outward.

        A limit of exactly the data's min and max would clip the curve against the
        axes; the half-decade snap is what leaves it legible.
        """
        frequency = np.logspace(0, 5, 200)
        psd = np.full(200, 2.5e-4)
        psd[50] = 7.5e-2
        rms = np.linspace(1.0, 10.0, 200)

        psd_view.update_psd([psd], [rms], frequency, [0])

        ax = psd_view.figure.get_axes()[0]
        lower, upper = ax.set_ylim.call_args.args
        assert lower == pytest.approx(10 ** (np.floor(np.log10(2.5e-4) * 2) / 2))
        assert upper == pytest.approx(10 ** (np.ceil(np.log10(7.5e-2) * 2) / 2))

    def test_the_figure_is_cleared_before_replotting(
        self, psd_view: RawDataView
    ) -> None:
        """
        Otherwise a second PSD run would stack axes on top of the first.

        Pinned because Step 4c moves the computation out but must leave the canvas
        lifecycle behind, and a clear that moved with it would leak axes.
        """
        frequency = np.logspace(0, 5, 100)
        psd = [np.full(100, 1e-3)]
        rms = [np.linspace(1.0, 10.0, 100)]

        psd_view.update_psd(psd, rms, frequency, [0])
        psd_view.update_psd(psd, rms, frequency, [0])

        assert psd_view.figure.clear.call_count == 2
        assert len(psd_view.figure.get_axes()) == 1


class TestHandlePlotEvents:
    """
    The View half of the event-plotting path after Step 4a: ask, then draw.

    This class pinned all five bus round trips before the conversion - the finder's
    status and event count, the filter callable, the samplerate, and one load per event.
    Those assertions now live in ``tests/unit/controllers/test_raw_data_controller.py``
    against ``load_event_plot_data``, because that is where the calls went. **Rewritten
    rather than deleted**: ten of the fifteen failed outright when the emits vanished,
    and the other five would have gone on passing *vacuously* - asserting that no bus
    call was made, which is trivially true of a method that no longer makes any. A test
    that survives a refactor by becoming empty is the failure mode worth designing
    against.

    What stays here is what the View still owns: refusing what it can refuse, emitting a
    typed intent, and drawing the answer.
    """

    @pytest.fixture
    def wired(self, view: RawDataView):
        """
        A view with its intent signal and plot call observable.

        :param view: the bare view
        :type view: RawDataView
        :return: the view, ready to record
        :rtype: RawDataView
        """
        view._update_event_plot = MagicMock()
        return view

    @staticmethod
    def params(**over) -> dict:
        """
        A parameter dict of the shape the controls panel emits.

        :param over: keys to override
        :type over: dict
        :return: the parameter dict
        :rtype: dict
        """
        base = {
            "eventfinder": "finder",
            "filter": "No Filter",
            "channel": ["0"],
            "event_index": [0, 1],
        }
        base.update(over)
        return base

    # -- what the View refuses on its own --------------------------------

    def test_a_missing_channel_key_is_reported_not_raised(
        self, wired: RawDataView
    ) -> None:
        """
        Fixed 2026-09-08, having been pinned as a defect first.

        This one was the worse of the pair: the read sat outside every ``try`` and
        ``handle_parameter_change`` has no handler, so the ``KeyError`` escaped the tab
        into Qt. ``MetaEventTabView._channels_from`` now reports it as ``ValueError``,
        which this method's existing guard already catches.
        """
        wired._handle_plot_events({})

        wired.event_plot_requested.emit.assert_not_called()

    def test_extraction_failure_requests_nothing(self, wired: RawDataView) -> None:
        """A non-numeric channel is the shape the guard does catch."""
        wired._handle_plot_events(self.params(channel=["not-a-channel"]))

        wired.event_plot_requested.emit.assert_not_called()
        wired._update_event_plot.assert_not_called()

    def test_multiple_channels_are_refused_before_asking(
        self, wired: RawDataView
    ) -> None:
        """Events from two channels cannot share a plot, and it stops here."""
        wired._handle_plot_events(self.params(channel=["0", "1"]))

        wired.event_plot_requested.emit.assert_not_called()
        wired._update_event_plot.assert_not_called()

    # -- the intent ------------------------------------------------------

    def test_the_intent_carries_the_finder_channel_events_and_filter(
        self, wired: RawDataView
    ) -> None:
        """The channel arrives as a single int, not the one-element list it came in."""
        wired._handle_plot_events(
            self.params(channel=["3"], event_index=[5, 6], filter="F1")
        )

        wired.event_plot_requested.emit.assert_called_once_with(
            "finder", 3, [5, 6], "F1"
        )

    def test_no_filter_is_carried_as_an_empty_key(self, wired: RawDataView) -> None:
        """The three spellings of "none" collapse before they leave the View."""
        wired._handle_plot_events(self.params(filter="No Filter"))

        assert wired.event_plot_requested.emit.call_args[0][3] == ""

    def test_no_selected_events_is_carried_as_an_empty_list(
        self, wired: RawDataView
    ) -> None:
        """
        ``event_index`` is absent or None when nothing is selected.

        The Controller still asks the finder for its status and count in that case, which
        is the behaviour the pre-conversion code had, so the intent is emitted rather
        than suppressed here.
        """
        wired._handle_plot_events(self.params(event_index=None))

        assert wired.event_plot_requested.emit.call_args[0][2] == []

    # -- drawing the answer ----------------------------------------------

    def test_set_event_plot_data_reports_when_nothing_loaded(
        self, wired: RawDataView
    ) -> None:
        """The user is told, rather than being shown an empty figure."""
        wired.set_event_plot_data([], [])

        wired._update_event_plot.assert_not_called()
        wired.add_text_to_display.emit.assert_called_once()

    def test_set_event_plot_data_draws_traces_against_their_indices(
        self, wired: RawDataView
    ) -> None:
        """
        The alignment that matters: each trace is labelled with the index beside it.

        The Controller drops an event it could not load and drops its index with it, so
        the View draws whatever pair it is handed without pruning anything.
        """
        data = [np.full(4, 1.0), np.full(4, 3.0)]

        wired.set_event_plot_data(data, [0, 2])

        drawn_data, drawn_indices = wired._update_event_plot.call_args[0]
        assert list(drawn_indices) == [0, 2]
        assert [float(entry[0]) for entry in drawn_data] == [1.0, 3.0]
