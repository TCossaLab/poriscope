"""
Tests for ``poriscope.utils.ReplayGuard``, the tripwire that refuses a widget read during replay.

A recorded action must be a pure function of its recorded arguments, so while a replay runs
the seven helpers that read the controls panels raise instead of answering. Five of them are
the panels' own ``collect_parameters``, which hold no reference to a View or Controller, which
is why the switch lives in a module they can all import.
"""

import ast
import inspect
import textwrap
import threading
from typing import Any, Callable, List
from unittest.mock import MagicMock

import pytest

from poriscope.plugins.analysistabs.utils.clusteringcontrols import ClusteringControls
from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.utils.MetaEventTabView import MetaEventTabView
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView
from poriscope.utils.ReplayGuard import (
    ReplayWidgetReadError,
    forbid_while_replaying,
    replaying,
)

GUARDED: List[Callable[..., Any]] = [
    MetaSubsetTabView.get_selected_filters,
    MetaEventTabView._get_event_index_text,
    RawDataControls.collect_parameters,
    EventAnalysisControls.collect_parameters,
    ClusteringControls.collect_parameters,
    MetadataControls.collect_parameters,
    ProteinControls.collect_parameters,
]


def _ids(function: Callable[..., Any]) -> str:
    return function.__qualname__


class TestTheSwitch:
    def test_it_answers_outside_a_replay(self) -> None:
        forbid_while_replaying("anything")

    def test_it_raises_inside_a_replay_and_names_the_read(self) -> None:
        with replaying():
            with pytest.raises(ReplayWidgetReadError, match="get_selected_filters"):
                forbid_while_replaying("get_selected_filters")

    def test_it_is_an_error_a_caller_can_tell_from_others(self) -> None:
        assert issubclass(ReplayWidgetReadError, RuntimeError)

    def test_nesting_keeps_it_on_until_the_outer_replay_ends(self) -> None:
        with replaying():
            with replaying():
                pass
            with pytest.raises(ReplayWidgetReadError):
                forbid_while_replaying("x")
        forbid_while_replaying("x")

    def test_it_is_switched_off_again_when_the_replay_raises(self) -> None:
        with pytest.raises(ValueError):
            with replaying():
                raise ValueError("a recorded action failed")
        forbid_while_replaying("x")

    def test_a_worker_thread_does_not_see_it(self) -> None:
        """The GUI thread replays; a worker that reads a panel would be a different bug."""
        seen: List[BaseException] = []

        def read() -> None:
            try:
                forbid_while_replaying("from a worker")
            except (
                BaseException
            ) as error:  # noqa: BLE001 - the thread must report, not die
                seen.append(error)

        with replaying():
            thread = threading.Thread(target=read)
            thread.start()
            thread.join()

        assert seen == []


class TestTheSevenHelpers:
    @pytest.mark.parametrize("helper", GUARDED, ids=_ids)
    def test_each_helper_asks_the_guard_before_anything_else(
        self, helper: Callable[..., Any]
    ) -> None:
        """
        The first statement after the docstring is the guard call.

        Pinned by source, because five of the helpers need a whole panel to call and a
        helper that read a widget before asking would pass any test that only watches the
        raise. Dropping the call, or moving it below a read, fails here.
        """
        tree = ast.parse(textwrap.dedent(inspect.getsource(helper)))
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)
        body = function.body
        if isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]  # the docstring
        first = body[0]
        assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
        assert getattr(first.value.func, "id", None) == "forbid_while_replaying"

    @pytest.mark.parametrize("helper", GUARDED, ids=_ids)
    def test_each_helper_raises_during_a_replay(
        self, helper: Callable[..., Any]
    ) -> None:
        fake_self = MagicMock()
        with replaying():
            with pytest.raises(ReplayWidgetReadError):
                helper(fake_self)

    def test_get_selected_filters_still_answers_outside_a_replay(self) -> None:
        fake_self = MagicMock()
        fake_self.subset_filters = {"a": "x > 1"}
        fake_self._subset_controls.filter_comboBox.getSelectedItems.return_value = ["a"]

        assert MetaSubsetTabView.get_selected_filters(fake_self) == {"a": "x > 1"}

    def test_the_event_index_text_still_answers_outside_a_replay(self) -> None:
        fake_self = MagicMock()
        fake_self._event_controls.event_index_lineEdit.text.return_value = " 7 "

        assert MetaEventTabView._get_event_index_text(fake_self) == "7"
