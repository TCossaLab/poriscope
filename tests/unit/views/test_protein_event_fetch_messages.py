"""
``ProteinView``'s event-plot click says one thing about a refusal, never two.

Found in a manual Windows pass over the event-plot promotion.
The tab reported a refusal and then contradicted it::

    ProteinView: Only a single channel can be used for plotting events
    ProteinView: No data available for event_id 10

The second line named the event as the problem, which was the one thing that was not
wrong. The click now refuses before it asks for anything, and says nothing when it
asks; what the fetch says is ``ProteinController``'s, tested in
``tests/unit/controllers/test_protein_controller.py``.
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
    """The click resolves the Event ID and asks for exactly those events, or says why not."""

    def test_the_resolved_events_are_asked_for_in_silence(self, view):
        with patch.object(
            ProteinView, "get_selected_filters", return_value={"F": "SELECT 1"}
        ):
            view.current_sql_filter = "SELECT 1"
            view._handle_plot_events({**PARAMS, "raw": True})

        assert _messages(view) == []
        view.plot_events_requested.emit.assert_called_once_with(
            "ldr", [10], "exp1", 0, "F", "SELECT 1", True
        )

    def test_two_channels_in_scope_is_refused_before_anything_is_asked(self, view):
        view.selected_experiment_and_channels_by_loader = {"ldr": {"exp1": [0, 1]}}
        view._rebuild_event_id_cache = MagicMock()

        with patch.object(ProteinView, "get_selected_filters", return_value={}):
            view._handle_plot_events(dict(PARAMS))

        assert _messages(view) == [
            "Only a single channel can be used for plotting events"
        ]
        view._rebuild_event_id_cache.assert_not_called()
        view.plot_events_requested.emit.assert_not_called()
