"""
``ProteinView``'s event fetch says one thing about a failure, never two.

Found in the Step 4 closeout's manual Windows pass over the event-plot promotion.
The tab reported a refusal and then contradicted it::

    ProteinController: SQLiteDBLoader_1 has no experiment named x, so these events
                       cannot be scoped to it
    ProteinView:       No data available for event_id 10

and, with two channels in scope::

    ProteinView: Only a single channel can be used for plotting events
    ProteinView: No data available for event_id 10

The second line names the event as the problem in both cases, which is the one thing
that was not wrong. ``_fetch_event_data`` returned ``[]`` for a refusal and for an
empty result alike, so its callers could not tell them apart; it returns ``None`` for
a refusal now. The metadata tab never had the second line, which is why only this tab
showed it.

These tests pin the three outcomes at the caller and the refusal at the fetch itself.
"""

from unittest.mock import MagicMock, patch

import pytest

from poriscope.plugins.analysistabs.ProteinView import ProteinView
from tests.unit.views._qt_mocks import shadow_signals

PARAMS = {"db_loader": "ldr", "event_id": 10, "n_events": 1}


@pytest.fixture
def view():
    """
    A ProteinView with only what the event-plot handlers touch.

    Built with ``__new__`` so no widget tree is constructed; the handlers under test
    are the real ones. The cache and scope are set to agree with each other, so
    ``_rebuild_event_id_cache`` is not reached and the test is about the fetch.

    :return: the view under test
    :rtype: ProteinView
    """
    v = ProteinView.__new__(ProteinView)
    shadow_signals(v, ProteinView)
    v.proteincontrols = MagicMock()
    v.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": [0]}}
    v.filtered_event_ids = [10]
    v.current_sql_filter = ""
    v.current_experiment = "exp1"
    v.current_channel = 0
    v._last_event_action = None
    return v


def _messages(view):
    """
    Every line the view put on the status panel.

    :param view: the view to read the emitted messages off
    :type view: ProteinView
    :return: the message text of each emission, in order
    :rtype: list[str]
    """
    return [call.args[0] for call in view.add_text_to_display.emit.call_args_list]


class TestPlotEvents:
    """What the caller says about each of the fetch's three outcomes."""

    def test_a_refused_fetch_adds_no_second_message(self, view):
        with (
            patch.object(ProteinView, "get_selected_filters", return_value={}),
            patch.object(ProteinView, "_fetch_event_data", return_value=None),
            patch.object(ProteinView, "_update_event_plot") as draw,
        ):
            view._handle_plot_events(dict(PARAMS))

        assert _messages(view) == []
        draw.assert_not_called()

    def test_an_empty_fetch_is_reported(self, view):
        """
        The fetch ran and found nothing, which nobody else has said - so this is the
        one outcome the caller does speak about, and it names the event it asked for.
        """
        with (
            patch.object(ProteinView, "get_selected_filters", return_value={}),
            patch.object(ProteinView, "_fetch_event_data", return_value=[]),
            patch.object(ProteinView, "_update_event_plot") as draw,
        ):
            view._handle_plot_events(dict(PARAMS))

        assert any("No data available for event_id 10" in m for m in _messages(view))
        draw.assert_not_called()

    def test_events_that_arrive_are_drawn_in_silence(self, view):
        events = [{"event_id": 10}]
        with (
            patch.object(ProteinView, "get_selected_filters", return_value={}),
            patch.object(ProteinView, "_fetch_event_data", return_value=events),
            patch.object(ProteinView, "_update_event_plot") as draw,
        ):
            view._handle_plot_events(dict(PARAMS))

        assert _messages(view) == []
        draw.assert_called_once_with(events, use_raw=False)


class TestPlotHistogram:
    """The same contract on the other caller, which had the same two lines."""

    def test_a_refused_fetch_adds_no_second_message(self, view):
        with (
            patch.object(ProteinView, "get_selected_filters", return_value={}),
            patch.object(ProteinView, "_fetch_event_data", return_value=None),
            patch.object(ProteinView, "_update_event_histogram") as draw,
        ):
            view._handle_plot_histogram({**PARAMS, "bins": 50, "sizes": False})

        assert _messages(view) == []
        draw.assert_not_called()

    def test_an_empty_fetch_is_reported(self, view):
        with (
            patch.object(ProteinView, "get_selected_filters", return_value={}),
            patch.object(ProteinView, "_fetch_event_data", return_value=[]),
            patch.object(ProteinView, "_update_event_histogram") as draw,
        ):
            view._handle_plot_histogram({**PARAMS, "bins": 50, "sizes": False})

        assert any("No data available for event_id 10" in m for m in _messages(view))
        draw.assert_not_called()


class TestFetchRefusals:
    """The fetch's own guards return None, which is what keeps the caller quiet."""

    def test_two_channels_in_scope_is_refused_once(self, view):
        view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": [0, 1]}}

        with patch.object(ProteinView, "get_selected_filters", return_value={}):
            result = view._fetch_event_data({"db_loader": "ldr", "event_index": [10]})

        assert result is None
        assert _messages(view) == [
            "Only a single channel can be used for plotting events"
        ]

    def test_two_experiments_in_scope_is_refused_once(self, view):
        view.selected_experiment_and_channels_by_loader = {
            "ldr": {"exp1": [0], "exp2": [0]}
        }

        with patch.object(ProteinView, "get_selected_filters", return_value={}):
            result = view._fetch_event_data({"db_loader": "ldr", "event_index": [10]})

        assert result is None
        assert _messages(view) == [
            "Only a single experiment can be used for plotting events"
        ]

    def test_a_controller_that_hands_back_nothing_is_a_refusal(self, view):
        """
        The generator is set only once the Controller's whole chain has succeeded,
        and it reports which part did not - the experiment rename in the docstring
        above is this path. So None here means "already explained", not "no events".
        """
        view.plot_events_generator = None

        with patch.object(ProteinView, "get_selected_filters", return_value={}):
            result = view._fetch_event_data({"db_loader": "ldr", "event_index": [10]})

        assert result is None
        assert _messages(view) == []
