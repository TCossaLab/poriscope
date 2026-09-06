"""
Characterization tests for the ``check_column_exists`` / ``set_column_exists`` relay.

Step 3e removes this pair from the bases as tab-specific leakage: both live on
``MetaController`` and ``MetaView``, where every tab inherits them, but only the
clustering tab uses them - to record which table already holds committed cluster
columns, so a second commit can warn instead of duplicating them.

The refactor-coverage audit reported both as ``RUNS ONLY``. They execute during the
clustering e2e flow, but no test named either, so nothing asserted that the
controller reaches the view or that the view stores what it is handed. Both are one
line, and one line is exactly what gets dropped unnoticed when a method is deleted
from a base and re-homed on a subclass.
"""

from typing import Dict, List, Optional

import pytest
from PySide6.QtWidgets import QBoxLayout

from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaView import MetaView

pytestmark = pytest.mark.characterization


class _ConcreteView(MetaView):
    """A concrete MetaView so the base's own setter is reachable."""

    def _init(self) -> None:
        """Satisfy the abstract hook."""

    def _set_control_area(self, layout: QBoxLayout) -> None:
        """Satisfy the abstract hook."""

    def _reset_actions(self, axis_type: str = "2d") -> None:
        """Satisfy the abstract hook."""

    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """Satisfy the abstract hook."""

    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """Satisfy the abstract hook."""


@pytest.fixture
def view() -> _ConcreteView:
    """
    A MetaView built without Qt.

    :return: the view
    :rtype: _ConcreteView
    """
    return _ConcreteView.__new__(_ConcreteView)


@pytest.fixture
def controller(mocker) -> MetaController:
    """
    A MetaController with a mock view, built without Qt.

    :param mocker: pytest-mock's fixture
    :type mocker: Any
    :return: the controller
    :rtype: MetaController
    """
    instance = MetaController.__new__(MetaController)  # type: ignore[type-abstract]
    instance.view = mocker.Mock()
    return instance


class TestSetColumnExists:
    """The view side: store whichever table was reported, including none."""

    def test_it_records_the_table_name(self, view: _ConcreteView) -> None:
        """The clustering tab reads this back before committing new columns."""
        view.set_column_exists("events")

        assert view.column_table == "events"

    def test_none_means_no_table_holds_them(self, view: _ConcreteView) -> None:
        """
        ``None`` is a real answer here, not a failure.

        It is what says the commit is safe to proceed, so a merge that treated it
        as "unknown" and skipped the assignment would silently re-enable duplicate
        commits.
        """
        view.set_column_exists(None)

        assert view.column_table is None

    def test_a_later_answer_replaces_an_earlier_one(self, view: _ConcreteView) -> None:
        """The value is per-query state, not accumulated."""
        view.set_column_exists("events")
        view.set_column_exists("sublevels")

        assert view.column_table == "sublevels"

    @pytest.mark.parametrize("value", ["events", "sublevels", None, ""])
    def test_it_stores_what_it_is_given_without_interpreting_it(
        self, view: _ConcreteView, value: Optional[str]
    ) -> None:
        """No normalisation, so an empty string stays distinguishable from None."""
        view.set_column_exists(value)

        assert view.column_table == value


class TestCheckColumnExists:
    """The controller side: a one-hop relay onto the view."""

    def test_it_forwards_the_table_name_to_the_view(
        self, controller: MetaController
    ) -> None:
        """The whole method. Step 3e moves it, and this is what must survive."""
        controller.check_column_exists("events")

        controller.view.set_column_exists.assert_called_once_with("events")

    def test_it_returns_none(self, controller: MetaController) -> None:
        """It is a notification, and the bus discards any return value."""
        assert controller.check_column_exists("events") is None


def test_the_relay_works_end_to_end(view: _ConcreteView, mocker) -> None:
    """
    Controller to view, with the real view rather than a mock on the far side.

    The two halves are tested separately above; this is the seam between them,
    which is what a re-homing gets wrong. It would fail if the controller called a
    differently named setter, which no single-sided test would notice.
    """
    controller = MetaController.__new__(MetaController)  # type: ignore[type-abstract]
    controller.view = view

    controller.check_column_exists("sublevels")

    assert view.column_table == "sublevels"
