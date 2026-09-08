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
    The event-finding launch path, a Step 4a target the audit found unpinned.

    It executes in the raw-data e2e flow but nothing named it, so none of its
    branching was asserted: the filter round trip, the already-complete
    confirmation, the two shapes of time limit, or the per-channel bundling of
    ``find_events``. Step 4a rewrites every emit here into a Model call, so what
    each emit carries is what has to survive.

    The bus is stubbed the way the real dispatcher behaves - setting the attribute
    named by the emit's return-function argument - rather than as a silent mock.
    """

    @pytest.fixture
    def wired(self, view: RawDataView):
        """
        A view wired so bus emits are recorded and deliver their side effects.

        :param view: the bare view
        :type view: RawDataView
        :return: the view, with ``calls`` recording every emitted dispatch
        :rtype: RawDataView
        """
        view.analysis_time_limits = {}
        view.eventfinding_status = False
        view.calls = []

        def deliver(metaclass, key, method, args, return_fn, extra):
            view.calls.append((metaclass, key, method, args, return_fn, extra))
            if return_fn == "set_event_filter":
                view.data_filter = "a-callable"

        view.global_signal.emit.side_effect = deliver
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
    def find_calls(view: RawDataView) -> list:
        """
        Every find_events dispatch the view emitted.

        :param view: the view
        :type view: RawDataView
        :return: the matching recorded calls
        :rtype: list
        """
        return [call for call in view.calls if call[2] == "find_events"]

    def test_a_bare_channel_is_coerced_to_a_list(self, wired: RawDataView) -> None:
        """Callers pass either shape, and a bare int must not be iterated as one."""
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})

        wired._start_eventfinder("finder", "No Filter", 0)

        assert len(self.find_calls(wired)) == 1
        assert self.find_calls(wired)[0][3][0] == 0

    def test_no_filter_skips_the_filter_round_trip(self, wired: RawDataView) -> None:
        """The literal placeholder is not a plugin name and must not be resolved."""
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})

        wired._start_eventfinder("finder", "No Filter", [0])

        assert not [call for call in wired.calls if call[0] == "MetaFilter"]
        assert wired.data_filter is None

    def test_a_named_filter_is_fetched_and_passed_to_find_events(
        self, wired: RawDataView
    ) -> None:
        """The resolved callable travels as the fourth find_events argument."""
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})

        wired._start_eventfinder("finder", "my-filter", [0])

        assert [call for call in wired.calls if call[0] == "MetaFilter"]
        assert self.find_calls(wired)[0][3][3] == "a-callable"

    def test_the_filter_is_cleared_before_it_is_fetched(
        self, wired: RawDataView
    ) -> None:
        """
        The stale-read guard: a failed dispatch must not reuse the previous run's
        filter callable against this run's data.
        """
        wired.data_filter = "stale"
        self.limits(wired, "finder", 0, {"start": 0.0, "end": 0.0})
        wired.global_signal.emit.side_effect = None

        wired._start_eventfinder("finder", "my-filter", [0])

        assert wired.data_filter is None

    def test_explicit_ranges_are_used_and_copied(self, wired: RawDataView) -> None:
        """
        A copy, so a later edit to the stored limits cannot mutate a queued run.

        The source comment says so explicitly, and it is the kind of detail that
        disappears silently when a method is re-homed.
        """
        stored = [(1.0, 2.0), (5.0, 6.0)]
        self.limits(wired, "finder", 0, {"ranges": stored})

        wired._start_eventfinder("finder", "No Filter", [0])

        passed = self.find_calls(wired)[0][3][1]
        assert passed == stored
        assert passed is not stored

    def test_start_and_end_become_a_single_range(self, wired: RawDataView) -> None:
        """The other limit shape, for a finder configured without explicit ranges."""
        self.limits(wired, "finder", 0, {"start": 3.0, "end": 9.0})

        wired._start_eventfinder("finder", "No Filter", [0])

        assert self.find_calls(wired)[0][3][1] == [(3.0, 9.0)]

    def test_a_falsy_end_becomes_zero_meaning_end_of_signal(
        self, wired: RawDataView
    ) -> None:
        """
        ``end or 0.0`` collapses None and 0 alike, and 0 means "to the end".

        The same convention the Time Range dialog uses; 1.9.0 fixed a bug where
        the two disagreed, so the agreement is worth holding.
        """
        self.limits(wired, "finder", 0, {"start": 3.0, "end": None})

        wired._start_eventfinder("finder", "No Filter", [0])

        assert self.find_calls(wired)[0][3][1] == [(3.0, 0.0)]

    def test_one_find_events_per_channel_then_one_run_generators(
        self, wired: RawDataView
    ) -> None:
        """
        The bundling contract: N channels give N dispatches and a single run.

        Emitting run_generators inside the loop would start the workers before
        every channel had been queued.
        """
        for channel in (0, 1, 2):
            self.limits(wired, "finder", channel, {"start": 0.0, "end": 0.0})

        wired._start_eventfinder("finder", "No Filter", [0, 1, 2])

        assert [call[3][0] for call in self.find_calls(wired)] == [0, 1, 2]
        wired.run_generators.emit.assert_called_once_with("finder")

    def test_the_return_args_carry_the_channel_and_finder(
        self, wired: RawDataView
    ) -> None:
        """set_generator needs both in order to file the generator it is handed."""
        self.limits(wired, "finder", 4, {"start": 0.0, "end": 0.0})

        wired._start_eventfinder("finder", "No Filter", [4])

        call = self.find_calls(wired)[0]
        assert call[4] == "set_generator"
        assert call[5] == (4, "finder", "MetaEventFinder")

    def test_declining_the_overwrite_prompt_skips_only_that_channel(
        self, wired: RawDataView, mocker
    ) -> None:
        """
        An already-finished channel asks before redoing it, and No means skip.

        The other channels still run, which is what a coarser guard would get
        wrong by abandoning the whole batch.
        """
        for channel in (0, 1):
            self.limits(wired, "finder", channel, {"start": 0.0, "end": 0.0})
        wired.eventfinding_status = True
        mocker.patch(
            "poriscope.plugins.analysistabs.RawDataView.QMessageBox.question",
            side_effect=[QMessageBox.No, QMessageBox.Yes],
        )

        wired._start_eventfinder("finder", "No Filter", [0, 1])

        assert [call[3][0] for call in self.find_calls(wired)] == [1]

    def test_a_missing_channel_limit_stops_before_launching_anything(
        self, wired: RawDataView
    ) -> None:
        """
        A configuration gap raises rather than launching a partial batch.

        ``run_generators`` sits inside the same try block, so nothing starts -
        the safe outcome, and easy to break by hoisting that emit out during the
        move to the Model.
        """
        wired.analysis_time_limits = {"finder": {}}

        with pytest.raises(KeyError):
            wired._start_eventfinder("finder", "No Filter", [0])

        wired.run_generators.emit.assert_not_called()


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
    The event-plotting path, a Step 4a target that no test had ever entered.

    Every reference to ``_handle_plot_events`` in ``test_raw_data_view.py`` *replaces*
    it with a ``Mock`` to assert that dispatch reaches it, so none of its 125 lines
    were asserted; ``RawDataView._load_event_data`` was named by no test at all, and
    the audit's hand-typed ``MOVED`` list did not carry either of them. The raw-data
    e2e click flow executes both, which is what makes their behaviour worth pinning
    before it moves rather than discovering it afterwards.

    Pinned here is what must **survive** the conversion: which plugin methods are
    asked, in what order, with what arguments, and every branch that stops early.
    Four stale-read behaviours are deliberately *not* pinned, because the conversion
    changes them on purpose - ``get_eventfinding_status``, ``get_num_events_found``,
    ``get_samplerate`` and ``get_single_event_data`` all park their answers on
    attributes written only on success and never cleared before the emit, so a
    swallowed dispatch failure leaves the previous value in place. Those assertions
    belong to the commit that fixes them.

    The bus is stubbed the way the real dispatcher behaves, per the class above: a
    dispatch delivers its answer through the return function named in the emit, and a
    *failed* dispatch delivers nothing at all, which a bare ``Mock`` cannot express.
    """

    FAILS = object()

    #: The bus names its return function on the **Controller**, and one of them does not
    #: match its View-side counterpart: ``set_event_filter`` is a RawDataController
    #: method that forwards to ``MetaEventTabView.set_data_filter_function``. Recorded
    #: here because the conversion has to route that answer somewhere, and the name in
    #: the emit is not the name on the View.
    RETURN_ON_VIEW = {"set_event_filter": "set_data_filter_function"}

    @pytest.fixture
    def wired(self, view: RawDataView):
        """
        A view whose bus emits record themselves and deliver real side effects.

        ``answers`` is keyed by plugin method name. A value of :attr:`FAILS` stands for
        a dispatch that failed and therefore called no return function; a list is
        consumed one answer per call, for the per-event loop.

        :param view: the bare view
        :type view: RawDataView
        :return: the view, with ``calls`` and ``answers`` attached
        :rtype: RawDataView
        """
        view.plot_data = None
        view.eventfinding_status = True
        view.num_events_allowed = 10
        view.data_filter = None
        view.plot_samplerate = 1
        view.calls = []
        view.answers = {
            "get_eventfinding_status": True,
            "get_num_events_found": 10,
            "get_callable_filter": "a-callable",
            "get_samplerate": 250000.0,
            "get_single_event_data": None,
        }
        view._update_event_plot = MagicMock()

        def deliver(metaclass, key, method, args, return_fn, extra):
            view.calls.append((metaclass, key, method, args, return_fn, extra))
            answer = view.answers.get(method, self.FAILS)
            if isinstance(answer, list):
                answer = answer.pop(0) if answer else self.FAILS
            if answer is self.FAILS:
                return
            getattr(view, self.RETURN_ON_VIEW.get(return_fn, return_fn))(answer)

        view.global_signal.emit.side_effect = deliver
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

    @staticmethod
    def asked(view: RawDataView, method: str) -> list:
        """
        Every dispatch of one plugin method.

        :param view: the wired view
        :type view: RawDataView
        :param method: the plugin method name
        :type method: str
        :return: the matching recorded calls
        :rtype: list
        """
        return [call for call in view.calls if call[2] == method]

    def event_data(self, samples: float) -> dict:
        """
        The dict shape ``get_single_event_data`` really returns.

        Its declared return type is ``Optional[Dict[str, ...]]``, which is why
        ``update_plot_data`` carries a ``data["data"]`` branch. A stub handing back a
        bare array would let a conversion that forgets to unwrap pass.

        :param samples: the value to fill the array with
        :type samples: float
        :return: an event-data dict
        :rtype: dict
        """
        return {"data": np.full(4, samples), "samplerate": 250000.0}

    # -- the branches that stop early ------------------------------------

    def test_a_missing_channel_key_escapes_as_a_keyerror(
        self, wired: RawDataView
    ) -> None:
        """
        Current behaviour, and a latent defect: only ``ValueError`` is caught.

        ``_extract_plot_event_parameters`` reaches ``parameters["channel"]`` directly, so
        a dict without that key raises ``KeyError`` straight out of the method while the
        guard beside it advertises "Parameter extraction failed". Latent rather than live,
        because the controls panel always supplies ``channel``. Pinned as-is rather than
        fixed here, to keep this a pinning commit; queued in ``future_fixes.md``.
        """
        with pytest.raises(KeyError):
            wired._handle_plot_events({})

        assert wired.calls == []
        wired._update_event_plot.assert_not_called()

    def test_extraction_failure_asks_nothing(self, wired: RawDataView) -> None:
        """A non-numeric channel is the shape the guard does catch."""
        wired._handle_plot_events(self.params(channel=["not-a-channel"]))

        assert wired.calls == []
        wired._update_event_plot.assert_not_called()

    def test_multiple_channels_are_refused_before_any_dispatch(
        self, wired: RawDataView
    ) -> None:
        """Events from two channels cannot share a plot, and it stops before the bus."""
        wired._handle_plot_events(self.params(channel=["0", "1"]))

        assert wired.calls == []
        wired._update_event_plot.assert_not_called()

    def test_unfinished_eventfinding_stops_after_the_status_check(
        self, wired: RawDataView
    ) -> None:
        """The status is the first thing asked, and a False answer ends it."""
        wired.answers["get_eventfinding_status"] = False

        wired._handle_plot_events(self.params())

        assert [call[2] for call in wired.calls] == ["get_eventfinding_status"]
        wired._update_event_plot.assert_not_called()

    def test_zero_events_found_stops_after_the_count(self, wired: RawDataView) -> None:
        """Nothing to plot, and the filter and samplerate are never asked for."""
        wired.answers["get_num_events_found"] = 0

        wired._handle_plot_events(self.params())

        assert [call[2] for call in wired.calls] == [
            "get_eventfinding_status",
            "get_num_events_found",
        ]
        wired._update_event_plot.assert_not_called()

    def test_an_empty_event_list_asks_only_the_two_status_questions(
        self, wired: RawDataView
    ) -> None:
        """No indices selected is not an error, and loads nothing."""
        wired._handle_plot_events(self.params(event_index=[]))

        assert [call[2] for call in wired.calls] == [
            "get_eventfinding_status",
            "get_num_events_found",
        ]
        wired._update_event_plot.assert_not_called()

    # -- what each dispatch carries --------------------------------------

    def test_the_status_and_count_are_asked_for_the_selected_channel(
        self, wired: RawDataView
    ) -> None:
        """Both take the channel, as an int, in a one-element tuple."""
        wired.answers["get_single_event_data"] = [self.event_data(1.0)] * 2

        wired._handle_plot_events(self.params(channel=["3"]))

        assert self.asked(wired, "get_eventfinding_status")[0][3] == (3,)
        assert self.asked(wired, "get_num_events_found")[0][3] == (3,)

    def test_no_filter_asks_for_no_callable(self, wired: RawDataView) -> None:
        """The "No Filter" selection is real, so the filter plugin is not consulted."""
        wired.answers["get_single_event_data"] = [self.event_data(1.0)] * 2

        wired._handle_plot_events(self.params(filter="No Filter"))

        assert self.asked(wired, "get_callable_filter") == []

    def test_a_named_filter_is_fetched_and_reaches_the_event_load(
        self, wired: RawDataView
    ) -> None:
        """The callable is fetched once and passed into every event load."""
        wired.answers["get_single_event_data"] = [self.event_data(1.0)] * 2

        wired._handle_plot_events(self.params(filter="F1"))

        fetched = self.asked(wired, "get_callable_filter")
        assert len(fetched) == 1
        assert fetched[0][1] == "F1"
        for call in self.asked(wired, "get_single_event_data"):
            assert call[3][2] == "a-callable"

    def test_each_event_is_loaded_with_the_documented_argument_shape(
        self, wired: RawDataView
    ) -> None:
        """
        ``get_single_event_data(channel, index, data_filter=None, rectify=False, ...)``.

        The fourth positional is **rectify**, not ``raw_data`` - the emit's argument
        tuple says only ``False``, and the method has two boolean parameters. Pinned
        against the real signature so the conversion cannot quietly re-aim it.
        """
        wired.answers["get_single_event_data"] = [
            self.event_data(1.0),
            self.event_data(2.0),
        ]

        wired._handle_plot_events(self.params(channel=["2"], event_index=[5, 6]))

        loads = self.asked(wired, "get_single_event_data")
        assert [call[3] for call in loads] == [
            (2, 5, None, False),
            (2, 6, None, False),
        ]

    def test_the_samplerate_is_asked_once_from_the_eventfinder(
        self, wired: RawDataView
    ) -> None:
        """Not from the reader, and not once per event."""
        wired.answers["get_single_event_data"] = [self.event_data(1.0)] * 2

        wired._handle_plot_events(self.params())

        rate = self.asked(wired, "get_samplerate")
        assert len(rate) == 1
        assert rate[0][0] == "MetaEventFinder"
        assert wired.plot_samplerate == 250000.0

    # -- the loop's own behaviour ----------------------------------------

    def test_loaded_events_are_unwrapped_and_plotted_with_their_indices(
        self, wired: RawDataView
    ) -> None:
        """
        The dict's ``data`` key is what gets plotted, not the dict.

        ``update_plot_data`` performs the unwrap today; the conversion has to keep
        doing it somewhere, and a stub returning a bare array would not notice.
        """
        wired.answers["get_single_event_data"] = [
            self.event_data(1.0),
            self.event_data(2.0),
        ]

        wired._handle_plot_events(self.params(event_index=[0, 1]))

        data_list, indices = wired._update_event_plot.call_args[0]
        assert list(indices) == [0, 1]
        assert [float(entry[0]) for entry in data_list] == [1.0, 2.0]

    def test_out_of_bounds_indices_are_dropped_against_the_reported_count(
        self, wired: RawDataView
    ) -> None:
        """The finder's count is the bound, and indices at or above it go."""
        wired.answers["get_num_events_found"] = 2
        wired.answers["get_single_event_data"] = [
            self.event_data(1.0),
            self.event_data(2.0),
        ]

        wired._handle_plot_events(self.params(event_index=[0, 1, 2, 7]))

        assert [call[3][1] for call in self.asked(wired, "get_single_event_data")] == [
            0,
            1,
        ]
        assert list(wired._update_event_plot.call_args[0][1]) == [0, 1]

    def test_an_event_that_returns_no_data_is_dropped_from_the_indices(
        self, wired: RawDataView
    ) -> None:
        """
        A ``None`` answer skips that event, and its index goes with it.

        This is the alignment that matters: the plot labels each trace with the index
        beside it, so a dropped event must not shift the rest.
        """
        wired.answers["get_single_event_data"] = [
            self.event_data(1.0),
            None,
            self.event_data(3.0),
        ]

        wired._handle_plot_events(self.params(event_index=[0, 1, 2]))

        data_list, indices = wired._update_event_plot.call_args[0]
        assert list(indices) == [0, 2]
        assert [float(entry[0]) for entry in data_list] == [1.0, 3.0]

    def test_every_event_failing_plots_nothing(self, wired: RawDataView) -> None:
        """The user is told, rather than being shown an empty figure."""
        wired.answers["get_single_event_data"] = [None, None]

        wired._handle_plot_events(self.params(event_index=[0, 1]))

        wired._update_event_plot.assert_not_called()
