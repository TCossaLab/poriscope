"""
Characterization tests for the ``check_column_exists`` / ``set_column_exists`` relay.

Step 3e removed this pair from the bases as tab-specific leakage. Both lived on
``ProteinController`` and ``MetaView``, where every tab inherited them, and they now live
on ``ProteinController`` and ``ProteinView`` - which are the only things that use them,
to record which table already holds committed fit-data columns so a second commit can
warn instead of duplicating them.

**The plan said "clustering", and that was the wrong tab.** The clustering tab has its
own separate pair, ``ClusteringController.check_cluster_column_exists`` ->
``ClusteringView.set_cluster_column_exists``, writing a different attribute. Nothing
here ever ran for clustering. Measured when 3e was implemented, 2026-09-06.

The refactor-coverage audit reported both as ``RUNS ONLY``. They execute during an e2e
flow, but no test named either, so nothing asserted that the controller reaches the view
or that the view stores what it is handed. Both are one line, and one line is exactly
what gets dropped unnoticed when a method is deleted from a base and re-homed on a
subclass - which is what these now hold in their new home.
"""

from typing import Optional

import pytest

from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.ProteinView import ProteinView

pytestmark = pytest.mark.characterization


@pytest.fixture
def view() -> ProteinView:
    """
    A ProteinView built without Qt, so its own setter is reachable.

    ``__new__`` rather than the constructor: the setter under test touches one
    attribute and nothing else, and building the real widget would drag in the whole
    tab.

    :return: the view
    :rtype: ProteinView
    """
    return ProteinView.__new__(ProteinView)


@pytest.fixture
def controller(mocker) -> ProteinController:
    """
    A ProteinController with a mock view, built without Qt.

    :param mocker: pytest-mock's fixture
    :type mocker: Any
    :return: the controller
    :rtype: ProteinController
    """
    instance = ProteinController.__new__(ProteinController)
    instance.view = mocker.Mock()
    return instance


class TestSetColumnExists:
    """The view side: store whichever table was reported, including none."""

    def test_it_records_the_table_name(self, view: ProteinView) -> None:
        """The protein tab reads this back before committing new columns."""
        view.set_column_exists("events")

        assert view.column_table == "events"

    def test_none_means_no_table_holds_them(self, view: ProteinView) -> None:
        """
        ``None`` is a real answer here, not a failure.

        It is what says the commit is safe to proceed, so a merge that treated it
        as "unknown" and skipped the assignment would silently re-enable duplicate
        commits.
        """
        view.set_column_exists(None)

        assert view.column_table is None

    def test_a_later_answer_replaces_an_earlier_one(self, view: ProteinView) -> None:
        """The value is per-query state, not accumulated."""
        view.set_column_exists("events")
        view.set_column_exists("sublevels")

        assert view.column_table == "sublevels"

    @pytest.mark.parametrize("value", ["events", "sublevels", None, ""])
    def test_it_stores_what_it_is_given_without_interpreting_it(
        self, view: ProteinView, value: Optional[str]
    ) -> None:
        """No normalisation, so an empty string stays distinguishable from None."""
        view.set_column_exists(value)

        assert view.column_table == value


class TestCheckColumnExists:
    """The controller side: a one-hop relay onto the view."""

    def test_it_forwards_the_table_name_to_the_view(
        self, controller: ProteinController
    ) -> None:
        """The whole method. Step 3e re-homed it, and this is what survived."""
        controller.check_column_exists("events")

        controller.view.set_column_exists.assert_called_once_with("events")

    def test_it_returns_none(self, controller: ProteinController) -> None:
        """It is a notification, and the bus discards any return value."""
        assert controller.check_column_exists("events") is None


def test_the_relay_works_end_to_end(view: ProteinView, mocker) -> None:
    """
    Controller to view, with the real view rather than a mock on the far side.

    The two halves are tested separately above; this is the seam between them,
    which is what a re-homing gets wrong. It would fail if the controller called a
    differently named setter, which no single-sided test would notice.
    """
    controller = ProteinController.__new__(ProteinController)
    controller.view = view

    controller.check_column_exists("sublevels")

    assert view.column_table == "sublevels"
