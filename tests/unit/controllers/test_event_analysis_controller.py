"""
Tests for poriscope.plugins.analysistabs.EventAnalysisController.

Covers:
- _init creates view and model
- _setup_connections runs without error (empty)
- update_available_plugins logs debug and delegates to model and view
- set_event_filter delegates to view
- set_eventfitting_status delegates to view (True and False)
- update_plot_data delegates to view (data present, data absent)
- update_features (all features with matching labels, no labels, mismatched vlabels,
  mismatched hlabels, mismatched plabels, all None)
- update_plot_samplerate delegates to view
- update_channels delegates to view
- set_num_events_allowed delegates to view
- relay_eventfitting_status delegates to view (True and False)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.EventAnalysisController import (
    EventAnalysisController,
)

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked EventAnalysisView.

    :param mocker: Pytest-mock fixture.
    :return: Mocked event analysis view.
    """
    return mocker.Mock()


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> EventAnalysisController:
    """
    Construct an EventAnalysisController with view, model, and logger replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked event analysis view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: EventAnalysisController = EventAnalysisController.__new__(EventAnalysisController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    # Real MetaController signal, needed by any slot that reports a failure to the
    # status panel. Added when Step 4a gave this controller its first such slots.
    ctrl.add_text_to_display = mocker.Mock()
    ctrl.add_text_to_display.emit = mocker.Mock()
    return ctrl


# ----------------------- Step 4a -------------------------------------


class TestLoadEventPlot:
    """
    The eight bus round trips ``EventAnalysisView._handle_plot_events`` used to make,
    and the assembly that turned their answers into plot arguments.

    Moved here with the calls. The View-side pinning that preceded the conversion turned
    up three things this class exists to hold, none of which is visible at a call site:

    - **Three unpacking rules the bus applied implicitly** from each callee's declared
      return type. ``load_event`` returns a dict whose ``data`` key is the samples;
      ``get_fitted_event`` returns a bare array and must *not* be unwrapped;
      ``get_plot_features`` returns a six-tuple in the order
      (vertical, horizontal, points, vlabels, hlabels, plabels).
    - **The per-event alignment.** ``event_data`` and ``labels`` take one to three
      entries per event; the six feature lists take exactly one placeholder each, and an
      event's features go on its own. Breaking this attaches a fit's features to another
      event's subplot.
    - **``num_events`` counts events, not traces.**
    """

    @staticmethod
    def answers(controller: EventAnalysisController, **over) -> None:
        """
        Install one answer per plugin method, dispatched by name.

        A value that is an Exception is raised; a list is consumed one per call, for the
        per-event loop.

        :param controller: Controller under test.
        :param over: answers keyed by plugin method name.
        """
        table: dict = {
            "get_num_events": 99,
            "get_samplerate": 250000.0,
            "get_callable_filter": "a-callable",
            "get_eventfitting_status": False,
            "load_event": {"data": "samples"},
            "get_fitted_event": "fit",
            "get_plot_features": (None, None, None, None, None, None),
        }
        table.update(over)

        def dispatch(metaclass, key, method, *args):
            answer = table[method]
            if isinstance(answer, list):
                answer = answer.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

        controller.model.call.side_effect = dispatch

    @staticmethod
    def asked(controller: EventAnalysisController, method: str) -> list:
        """
        Every call() of one plugin method.

        :param controller: Controller under test.
        :param method: the plugin method name.
        :return: the matching call args tuples.
        """
        return [
            call.args
            for call in controller.model.call.call_args_list
            if call.args[2] == method
        ]

    @staticmethod
    def plotted(mock_view: MagicMock) -> tuple:
        """
        The arguments handed to the View's setter.

        :param mock_view: Mocked event analysis view.
        :return: the positional arguments of set_event_plot_data.
        """
        return mock_view.set_event_plot_data.call_args[0]

    # -- stopping early ---------------------------------------------------

    def test_an_unreadable_count_reports_and_stops(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        **A latent defect the conversion dissolved rather than fixed.**

        The View read ``self.num_events_allowed``, which ``_init`` never declared and
        only the bus callback assigned, so a first-ever failed dispatch raised
        AttributeError from outside every ``try`` - and ``handle_parameter_change`` has
        no handler either, so it escaped into Qt. The count is a local here, so the
        failure is reported and the plot simply does not happen.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, get_num_events=RuntimeError("boom"))

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", False)

        mock_view.set_event_plot_data.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_no_selected_events_asks_only_for_the_count(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The count is still asked, as the View did, but nothing is loaded.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller)

        controller.load_event_plot("ldr", "No Event Fitter", 0, [], "", False)

        assert len(self.asked(controller, "get_num_events")) == 1
        assert self.asked(controller, "load_event") == []
        mock_view.set_event_plot_data.assert_not_called()

    def test_out_of_bounds_indices_are_dropped_and_named(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The loader's count is the bound, and the dropped indices are reported.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_num_events=2,
            load_event=[{"data": "a"}, {"data": "b"}],
        )

        controller.load_event_plot("ldr", "No Event Fitter", 3, [0, 1, 2, 9], "", False)

        assert [args[4] for args in self.asked(controller, "load_event")] == [0, 1]
        message = controller.add_text_to_display.emit.call_args[0][0]
        assert "Channel 3 holds 2 events (0-1)" in message
        assert "events 2, 9" in message

    def test_a_wholly_out_of_range_selection_plots_nothing(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The specific message has already gone out, so the generic one must not follow.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, get_num_events=2)

        controller.load_event_plot("ldr", "No Event Fitter", 0, [5, 9], "", False)

        mock_view.set_event_plot_data.assert_not_called()

    # -- what each dispatch carries ---------------------------------------

    def test_the_count_and_samplerate_are_asked_of_the_loader_for_the_channel(
        self,
        controller: EventAnalysisController,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        Both take the channel - unlike the event *finder*'s no-argument samplerate.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        :param mocker: Pytest-mock fixture.
        """
        self.answers(controller, load_event=[{"data": "a"}])

        controller.load_event_plot("ldr", "No Event Fitter", 2, [0], "", False)

        assert self.asked(controller, "get_num_events") == [
            ("MetaEventLoader", "ldr", "get_num_events", 2)
        ]
        assert self.asked(controller, "get_samplerate") == [
            ("MetaEventLoader", "ldr", "get_samplerate", 2)
        ]
        mock_view.update_plot_samplerate.assert_called_once_with(250000.0)

    def test_an_unreadable_samplerate_falls_back_to_one(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The View's own guard could not fire, because the bus swallowed the failure.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_samplerate=RuntimeError("boom"),
            load_event=[{"data": "a"}],
        )

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", False)

        mock_view.update_plot_samplerate.assert_called_once_with(1)

    def test_each_event_is_loaded_with_the_channel_index_and_filter(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        ``load_event(channel, index, data_filter=None)``, written from the signature.

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        self.answers(controller, load_event=[{"data": "a"}, {"data": "b"}])

        controller.load_event_plot("ldr", "No Event Fitter", 2, [5, 6], "", False)

        assert self.asked(controller, "load_event") == [
            ("MetaEventLoader", "ldr", "load_event", 2, 5, None),
            ("MetaEventLoader", "ldr", "load_event", 2, 6, None),
        ]

    def test_the_loader_payload_is_unwrapped_before_it_reaches_the_view(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        ``load_event`` returns a dict and the ``data`` key is the samples.

        The bus passed the whole dict to ``update_plot_data``, which did the unwrap; a
        conversion that forgot it would hand the plot a dict.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, load_event=[{"data": "samples-0"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", False)

        assert self.plotted(mock_view)[0] == ["samples-0"]

    def test_a_named_filter_is_fetched_once_and_reaches_every_load(
        self, controller: EventAnalysisController
    ) -> None:
        """
        :param controller: Controller under test.
        """
        self.answers(controller, load_event=[{"data": "a"}, {"data": "b"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0, 1], "F1", False)

        assert len(self.asked(controller, "get_callable_filter")) == 1
        for args in self.asked(controller, "load_event"):
            assert args[5] == "a-callable"

    def test_an_empty_filter_key_fetches_no_callable(
        self, controller: EventAnalysisController
    ) -> None:
        """
        :param controller: Controller under test.
        """
        self.answers(controller, load_event=[{"data": "a"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", False)

        assert self.asked(controller, "get_callable_filter") == []

    # -- the raw overlay --------------------------------------------------

    def test_raw_is_not_loaded_without_a_filter(
        self, controller: EventAnalysisController
    ) -> None:
        """
        There is nothing to compare an unfiltered trace against.

        :param controller: Controller under test.
        """
        self.answers(controller, load_event=[{"data": "a"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", True)

        assert len(self.asked(controller, "load_event")) == 1

    def test_raw_is_loaded_unfiltered_alongside_the_filtered_trace(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The second load passes None where the first passed the callable, and the raw
        trace **shares its event's subplot** - two traces, two labels, one placeholder.

        This is the alignment a conversion is most likely to break.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, load_event=[{"data": "filtered"}, {"data": "raw"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "F1", True)

        loads = self.asked(controller, "load_event")
        assert [args[5] for args in loads] == ["a-callable", None]

        data, labels, num_events, vlines, hlines, points, *_ = self.plotted(mock_view)
        assert data == ["filtered", "raw"]
        assert labels == ["Event 0 Data", "Event 0 Raw"]
        assert num_events == 1
        assert len(vlines) == len(hlines) == len(points) == 1

    # -- the fit overlay --------------------------------------------------

    def test_no_event_fitter_asks_the_fitter_nothing(
        self, controller: EventAnalysisController
    ) -> None:
        """
        The placeholder is a real selection, not a fitter key.

        :param controller: Controller under test.
        """
        self.answers(controller, load_event=[{"data": "a"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "", False)

        assert self.asked(controller, "get_eventfitting_status") == []
        assert self.asked(controller, "get_fitted_event") == []

    def test_the_fitting_status_is_asked_once_not_once_per_event(
        self, controller: EventAnalysisController
    ) -> None:
        """
        **One call hoisted deliberately.** It takes only the channel, so the View asking
        it inside the event loop asked the same question once per event.

        :param controller: Controller under test.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "a"}, {"data": "b"}, {"data": "c"}],
            get_fitted_event=["f0", "f1", "f2"],
        )

        controller.load_event_plot("ldr", "ef1", 0, [0, 1, 2], "", False)

        assert self.asked(controller, "get_eventfitting_status") == [
            ("MetaEventFitter", "ef1", "get_eventfitting_status", 0)
        ]

    def test_an_unfitted_channel_loads_no_fit(
        self, controller: EventAnalysisController
    ) -> None:
        """
        The status gates both the fit and its features.

        :param controller: Controller under test.
        """
        self.answers(
            controller, get_eventfitting_status=False, load_event=[{"data": "a"}]
        )

        controller.load_event_plot("ldr", "ef1", 0, [0], "", False)

        assert self.asked(controller, "get_fitted_event") == []
        assert self.asked(controller, "get_plot_features") == []

    def test_a_fitted_event_appends_its_fit_without_unwrapping_it(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        ``get_fitted_event`` returns a bare array, unlike ``load_event``'s dict.

        Three entries in event_data would mean it had been unwrapped like the loader's.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "samples"}],
            get_fitted_event="the-fit",
        )

        controller.load_event_plot("ldr", "ef1", 0, [0], "", False)

        data, labels, num_events, vlines, *_ = self.plotted(mock_view)
        assert data == ["samples", "the-fit"]
        assert labels == ["Event 0 Data", "Event 0 Fit"]
        assert num_events == 1
        assert len(vlines) == 1

    def test_a_missing_fit_is_skipped_without_a_label(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        ``get_fitted_event`` declares an Optional return; None means nothing to draw.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "samples"}],
            get_fitted_event=None,
        )

        controller.load_event_plot("ldr", "ef1", 0, [0], "", False)

        data, labels, *_ = self.plotted(mock_view)
        assert data == ["samples"]
        assert labels == ["Event 0 Data"]

    def test_the_feature_tuple_is_unpacked_in_its_declared_order(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        ``get_plot_features`` returns (vertical, horizontal, points, vlabels, hlabels,
        plabels) - the order the bus splatted across ``update_features``' parameters, and
        the one thing here that no call site reveals.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "samples"}],
            get_fitted_event="the-fit",
            get_plot_features=([1.0], [2.0], [(3.0, 4.0)], ["v"], ["h"], ["p"]),
        )

        controller.load_event_plot("ldr", "ef1", 0, [0], "", False)

        _, _, _, vlines, hlines, points, vlabels, hlabels, plabels, _ = self.plotted(
            mock_view
        )
        assert vlines == [[1.0]]
        assert hlines == [[2.0]]
        assert points == [[(3.0, 4.0)]]
        assert (vlabels, hlabels, plabels) == ([["v"]], [["h"]], [["p"]])

    def test_unreadable_features_leave_the_placeholders_alone(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        **The other latent defect the conversion dissolved.**

        The View read six attributes ``_init`` never declared, so a first-ever failure
        raised AttributeError into the outer handler and abandoned the whole plot after
        loading the traces. The placeholders are locals here, so a failure costs that
        event its features and nothing else.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "samples"}],
            get_fitted_event="the-fit",
            get_plot_features=RuntimeError("boom"),
        )

        controller.load_event_plot("ldr", "ef1", 0, [0], "", False)

        data, _, _, vlines, *_ = self.plotted(mock_view)
        assert data == ["samples", "the-fit"]
        assert vlines == [None]

    # -- the loop's arithmetic --------------------------------------------

    def test_one_placeholder_per_event_across_several_events(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        Three events, each with data and a fit: six traces, three placeholders.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "d0"}, {"data": "d1"}, {"data": "d2"}],
            get_fitted_event=["f0", "f1", "f2"],
        )

        controller.load_event_plot("ldr", "ef1", 0, [0, 1, 2], "", False)

        data, labels, num_events, vlines, *_ = self.plotted(mock_view)
        assert data == ["d0", "f0", "d1", "f1", "d2", "f2"]
        assert num_events == 3
        assert len(vlines) == 3
        assert labels == [
            "Event 0 Data",
            "Event 0 Fit",
            "Event 1 Data",
            "Event 1 Fit",
            "Event 2 Data",
            "Event 2 Fit",
        ]

    def test_each_event_s_features_land_on_its_own_placeholder(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The invariant that matters most: features must not drift onto another subplot.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            get_eventfitting_status=True,
            load_event=[{"data": "d0"}, {"data": "d1"}],
            get_fitted_event=["f0", "f1"],
            get_plot_features=[
                ([1.0], None, None, ["v0"], None, None),
                ([2.0], None, None, ["v1"], None, None),
            ],
        )

        controller.load_event_plot("ldr", "ef1", 0, [0, 1], "", False)

        _, _, _, vlines, _, _, vlabels, *_ = self.plotted(mock_view)
        assert vlines == [[1.0], [2.0]]
        assert vlabels == [["v0"], ["v1"]]

    def test_an_event_with_no_data_is_dropped_without_a_placeholder(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        A failed load costs the event its trace, its label and its placeholder, so the
        surviving events keep their own features.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(
            controller,
            load_event=[{"data": "d0"}, RuntimeError("boom"), {"data": "d2"}],
        )

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0, 1, 2], "", False)

        data, labels, num_events, vlines, *_ = self.plotted(mock_view)
        assert data == ["d0", "d2"]
        assert labels == ["Event 0 Data", "Event 2 Data"]
        assert num_events == 2
        assert len(vlines) == 2

    def test_every_event_failing_hands_back_empty_lists(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The View reports it; the Controller does not decide how to say so.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, load_event=[None, None])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0, 1], "", False)

        assert self.plotted(mock_view)[0] == []

    def test_the_raw_flag_is_passed_through_to_the_view(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        ``_update_event_plot`` needs it to lay out the legend.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        self.answers(controller, load_event=[{"data": "filtered"}, {"data": "raw"}])

        controller.load_event_plot("ldr", "No Event Fitter", 0, [0], "F1", True)

        assert self.plotted(mock_view)[9] is True


class TestFittingLaunch:
    """
    The three bus round trips ``EventAnalysisView._start_eventfitter`` used to make.

    Split across two slots because the launch has a question for the user in the middle
    of it, exactly as RawData's event finding does. These invariants were pinned against
    the View before the conversion and moved here with the calls; two of the old ones
    would have gone on passing for the wrong reason instead of failing, since they
    asserted that something was *not* emitted.
    """

    def test_the_status_is_asked_per_channel_and_handed_back_with_the_filter(
        self,
        controller: EventAnalysisController,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        One call per channel, and the filter key travels through untouched.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = [True, False]

        controller.request_fitting_statuses("ef1", [0, 1], "MyFilter")

        assert controller.model.call.call_args_list == [
            mocker.call("MetaEventFitter", "ef1", "get_eventfitting_status", 0),
            mocker.call("MetaEventFitter", "ef1", "get_eventfitting_status", 1),
        ]
        mock_view.set_fitting_statuses.assert_called_once_with(
            "ef1", [(0, True), (1, False)], "MyFilter"
        )

    def test_a_channel_whose_status_cannot_be_read_is_dropped(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        **The stale read this half closes.** The View parked each answer on
        ``self.eventfitting_status``, which nothing cleared, so a swallowed failure left
        the *previous* channel's fitted-ness in place - and the "start over?" prompt was
        then shown, or skipped, for the wrong channel.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        controller.model.call.side_effect = [True, RuntimeError("boom"), False]

        controller.request_fitting_statuses("ef1", [0, 1, 2], "")

        assert mock_view.set_fitting_statuses.call_args[0][1] == [(0, True), (2, False)]
        controller.add_text_to_display.emit.assert_called_once()

    def test_the_status_is_coerced_to_a_bool(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        The View branches on it, so a truthy non-bool must not reach the prompt as-is.

        Asserted with ``is True`` and a non-int value: ``== True`` cannot see a missing
        ``bool()`` because ``1 == True`` in Python, which is how the equivalent RawData
        test passed against perturbed code.

        :param controller: Controller under test.
        :param mock_view: Mocked event analysis view.
        """
        controller.model.call.return_value = "fitted"

        controller.request_fitting_statuses("ef1", [0], "")

        handed_back = mock_view.set_fitting_statuses.call_args[0][1]
        assert handed_back == [(0, True)]
        assert handed_back[0][1] is True

    def test_fit_events_is_called_per_channel_with_the_real_signature(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        ``fit_events(channel, silent=False, data_filter=None, indices=None)``.

        ``silent`` and ``indices`` are passed explicitly because the View always did,
        even though both match their defaults - written from the signature rather than
        the old call site (rule 42).

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 2], "")

        assert controller.model.call.call_args_list == [
            mocker.call("MetaEventFitter", "ef1", "fit_events", 0, False, None, None),
            mocker.call("MetaEventFitter", "ef1", "fit_events", 2, False, None, None),
        ]

    def test_each_generator_is_registered_against_its_channel_and_fitter(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        What the bus used to carry as the return function's extra arguments.

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "")

        assert controller.model.set_generator.call_args_list == [
            mocker.call("gen0", 0, "ef1", "MetaEventFitter"),
            mocker.call("gen1", 1, "ef1", "MetaEventFitter"),
        ]

    def test_the_generators_run_once_for_the_fitter(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Registration and running stay separate steps, as through the bus.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "")

        controller.model.run_generators.assert_called_once_with("ef1")

    def test_a_named_filter_is_fetched_once_and_passed_to_every_channel(
        self, controller: EventAnalysisController
    ) -> None:
        """
        One fetch for the batch, through the helper now shared with RawData.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["a-callable", "gen0", "gen1"]

        controller.start_fitting("ef1", [0, 1], "MyFilter")

        fit_calls = [
            call.args
            for call in controller.model.call.call_args_list
            if call.args[2] == "fit_events"
        ]
        assert len(fit_calls) == 2
        for args in fit_calls:
            assert args[5] == "a-callable"

    def test_an_empty_filter_key_fetches_no_callable(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Replaces the old test that asserted the View did not emit get_callable_filter -
        which would have passed trivially once the View stopped emitting anything.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0"]

        controller.start_fitting("ef1", [0], "")

        assert not [
            call
            for call in controller.model.call.call_args_list
            if call.args[2] == "get_callable_filter"
        ]

    def test_a_channel_that_cannot_launch_is_skipped_and_the_rest_run(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Replaces the old test_index_error_logged_not_raised, whose assertion that
        ``run_generators`` was not called became trivially true.

        The behaviour is deliberately different: the View abandoned the whole batch, and
        losing one channel beats losing every channel's fit.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", RuntimeError("boom"), "gen2"]

        controller.start_fitting("ef1", [0, 1, 2], "")

        registered = [
            call.args[1] for call in controller.model.set_generator.call_args_list
        ]
        assert registered == [0, 2]
        controller.model.run_generators.assert_called_once_with("ef1")
        controller.add_text_to_display.emit.assert_called_once()


class TestRequestLoaderChannels:
    """
    The Step 4a replacement for a ``global_signal`` round trip, against MetaEventLoader.

    The direct analogue of ``RawDataController.request_reader_channels``: the View asked a
    loader for its channel list over the bus and the answer came back seven hops later
    through a return function named by string. It is one call now.
    """

    def test_it_asks_the_loader_through_the_model(
        self, controller: EventAnalysisController
    ) -> None:
        """By key, through the sanctioned API."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_loader_channels("SQLiteEventLoader_0")

        controller.model.call.assert_called_once_with(
            "MetaEventLoader", "SQLiteEventLoader_0", "get_channels"
        )

    def test_it_hands_the_channels_to_the_view(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """The result path, which populates the channel combobox."""
        controller.model.call.return_value = [0, 1, 2]

        controller.request_loader_channels("SQLiteEventLoader_0")

        mock_view.update_channels.assert_called_once_with([0, 1, 2])

    def test_a_failure_leaves_the_combobox_alone(
        self, controller: EventAnalysisController, mock_view: MagicMock
    ) -> None:
        """
        Not repopulated with nothing.

        Clearing it would look to the user like a loader with no channels, which is a
        different and more alarming thing than a loader that could not be read.
        """
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_loader_channels("gone")

        mock_view.update_channels.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_it_does_not_raise_out_of_the_slot(
        self, controller: EventAnalysisController
    ) -> None:
        """Qt invoked this from a signal; an exception must not escape into C++."""
        controller.model.call.side_effect = RuntimeError("loader failed")

        controller.request_loader_channels("SQLiteEventLoader_0")


class TestWriteEvents:
    """
    The write call, moved off the View with the tests that pinned it.

    Never an emit-then-read: ``write_events`` returns a generator and the bus passed it
    into ``set_generator`` as an argument, so there was no attribute to park it on.
    """

    def test_each_channel_is_written_and_its_generator_registered(
        self, controller: EventAnalysisController, mocker: MockerFixture
    ) -> None:
        """
        One call per channel, and the generator it returns goes to the Model.

        :param controller: Controller under test.
        :param mocker: Pytest-mock fixture.
        """
        controller.model.call.side_effect = ["gen0", "gen1"]

        controller.write_events("w1", [0, 1])

        assert controller.model.call.call_args_list == [
            mocker.call("MetaDatabaseWriter", "w1", "write_events", 0),
            mocker.call("MetaDatabaseWriter", "w1", "write_events", 1),
        ]
        assert controller.model.set_generator.call_args_list == [
            mocker.call("gen0", 0, "w1", "MetaDatabaseWriter"),
            mocker.call("gen1", 1, "w1", "MetaDatabaseWriter"),
        ]

    def test_the_generators_are_run_once_for_the_writer(
        self, controller: EventAnalysisController
    ) -> None:
        """
        Registration and running stay separate steps, as through the bus.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0"]

        controller.write_events("my_writer", [0])

        controller.model.run_generators.assert_called_once_with("my_writer")

    def test_no_channels_writes_nothing_but_still_runs(
        self, controller: EventAnalysisController
    ) -> None:
        """
        The old test asserted no write emit for an empty list; this is the same property.

        ``run_generators`` is still called unconditionally, as the View did.

        :param controller: Controller under test.
        """
        controller.write_events("w1", [])

        controller.model.call.assert_not_called()
        controller.model.run_generators.assert_called_once_with("w1")

    def test_a_channel_that_cannot_be_written_is_skipped_not_fatal(
        self, controller: EventAnalysisController
    ) -> None:
        """
        **The deliberate behaviour change**, matching RawData's commit path.

        The View's ``except (IndexError, ValueError)`` abandoned the whole batch and
        skipped ``run_generators``, and could not catch a plugin failure anyway because
        the bus swallowed those first. Losing one channel beats losing every channel's
        write, and an arbitrary writer exception must not escape a Qt slot.

        :param controller: Controller under test.
        """
        controller.model.call.side_effect = ["gen0", RuntimeError("boom"), "gen2"]

        controller.write_events("w1", [0, 1, 2])

        registered = [
            call.args[1] for call in controller.model.set_generator.call_args_list
        ]
        assert registered == [0, 2]
        controller.model.run_generators.assert_called_once_with("w1")
        controller.add_text_to_display.emit.assert_called_once()


# ----------------------- _init / _setup_connections ------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates EventAnalysisView and EventAnalysisModel.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls = mocker.patch(
        "poriscope.plugins.analysistabs.EventAnalysisController.EventAnalysisView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.plugins.analysistabs.EventAnalysisController.EventAnalysisModel"
    )

    ctrl: EventAnalysisController = EventAnalysisController.__new__(EventAnalysisController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_runs_without_error(
    controller: EventAnalysisController,
) -> None:
    """
    Verify that _setup_connections completes without raising.

    The method is intentionally empty so the only requirement is no exception.

    :param controller: Controller under test.
    """
    controller._setup_connections()  # should not raise


# ------------------- update_available_plugins ------------------------


def test_update_available_plugins_delegates_to_model_and_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the available plugins dict to both model and view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    plugins = {"MetaReader": ["R1", "R2"]}
    controller.update_available_plugins(plugins)
    controller.model.update_available_plugins.assert_called_once_with(plugins)
    mock_view.update_available_plugins.assert_called_once_with(plugins)


def test_update_available_plugins_logs_debug(
    controller: EventAnalysisController,
) -> None:
    """
    Log a debug message when the available plugins are updated.

    :param controller: Controller under test.
    """
    controller.update_available_plugins({"MetaReader": ["R1"]})
    controller.logger.debug.assert_called_once()  # type: ignore[attr-defined]


# ----------------------- set_event_filter ----------------------------


def test_set_event_filter_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Forward the data filter callable to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    :param mocker: Pytest-mock fixture.
    """
    data_filter = mocker.Mock()
    controller.set_event_filter(data_filter)
    mock_view.set_data_filter_function.assert_called_once_with(data_filter)


# ------------------ set_eventfitting_status --------------------------


def test_set_eventfitting_status_true_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a True event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_eventfitting_status(True)
    mock_view.set_eventfitting_status.assert_called_once_with(True)


def test_set_eventfitting_status_false_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a False event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_eventfitting_status(False)
    mock_view.set_eventfitting_status.assert_called_once_with(False)


# ----------------------- update_plot_data ----------------------------


def test_update_plot_data_delegates_data_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    data = {"x": [1, 2], "y": [3, 4]}
    controller.update_plot_data(data)
    mock_view.update_plot_data.assert_called_once_with(data)


def test_update_plot_data_delegates_none_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward None to the view when no data is provided.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_plot_data()
    mock_view.update_plot_data.assert_called_once_with(None)


# ----------------------- update_features ----------------------------


def test_update_features_forwards_all_args_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward all feature and label lists to the view when lengths match.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    vertical = [[1.0], [2.0]]
    horizontal = [[3.0], [4.0]]
    points = [[(0.5, 1.5)], [(1.5, 2.5)]]
    vlabels = ["v1", "v2"]
    hlabels = ["h1", "h2"]
    plabels = ["p1", "p2"]

    controller.update_features(
        vertical=vertical,
        horizontal=horizontal,
        points=points,
        vlabels=vlabels,
        hlabels=hlabels,
        plabels=plabels,
    )

    mock_view.update_plot_features.assert_called_once_with(
        vertical, horizontal, points, vlabels, hlabels, plabels
    )


def test_update_features_forwards_all_none_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward all None arguments to the view when no features are provided.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_features()
    mock_view.update_plot_features.assert_called_once_with(
        None, None, None, None, None, None
    )


def test_update_features_raises_on_mismatched_vlabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when vlabels length does not match vertical lines length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="vertical line"):
        controller.update_features(
            vertical=[[1.0], [2.0]],
            vlabels=["only_one_label"],
        )


def test_update_features_raises_on_mismatched_hlabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when hlabels length does not match horizontal lines length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="horizontal line"):
        controller.update_features(
            horizontal=[[1.0], [2.0]],
            hlabels=["only_one_label"],
        )


def test_update_features_raises_on_mismatched_plabels(
    controller: EventAnalysisController,
) -> None:
    """
    Raise ValueError when plabels length does not match points length.

    :param controller: Controller under test.
    """
    with pytest.raises(ValueError, match="point"):
        controller.update_features(
            points=[[(0.5, 1.5)], [(1.5, 2.5)]],
            plabels=["only_one_label"],
        )


def test_update_features_allows_no_labels(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Allow features without labels and forward them to the view without error.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    vertical = [[1.0], [2.0]]
    controller.update_features(vertical=vertical)
    mock_view.update_plot_features.assert_called_once_with(
        vertical, None, None, None, None, None
    )


# ------------------- update_plot_samplerate --------------------------


def test_update_plot_samplerate_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the sampling rate to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.update_plot_samplerate(50000.0)
    mock_view.update_plot_samplerate.assert_called_once_with(50000.0)


# ----------------------- update_channels ----------------------------


def test_update_channels_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the channels dict to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    channels = {"num_channels": 2}
    controller.update_channels(channels)
    mock_view.update_channels.assert_called_once_with(channels)


# ------------------- set_num_events_allowed --------------------------


def test_set_num_events_allowed_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Forward the maximum event count to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.set_num_events_allowed(1000)
    mock_view.set_num_events_allowed.assert_called_once_with(1000)


# ---------------- relay_eventfitting_status --------------------------


def test_relay_eventfitting_status_true_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a True event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.relay_eventfitting_status(True)
    mock_view.set_eventfitting_status.assert_called_once_with(True)


def test_relay_eventfitting_status_false_delegates_to_view(
    controller: EventAnalysisController,
    mock_view: MagicMock,
) -> None:
    """
    Relay a False event fitting status to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked event analysis view.
    """
    controller.relay_eventfitting_status(False)
    mock_view.set_eventfitting_status.assert_called_once_with(False)
