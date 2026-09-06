"""
Replaying a saved action history and a saved session - both user data.

Step 7 records that saved ``.json`` action files are user data and that moving a
decorated method breaks replay. Nothing tested that. The Step 2 exit review found
there was **no checked-in ``.json`` fixture anywhere in ``tests/``**, and that
``update_actions_from_json`` was only ever asserted against a *mock* view - so the
replay mechanism itself had no coverage, only its call site.

The fixture in ``saved_state/`` is a real file of the shape the app writes, read
from disk rather than synthesised by the test that consumes it. It deliberately
contains an entry naming a method that no longer exists, because that is exactly
what a 1.x history becomes once Steps 3 and 4 move things.

**The finding this pins is uncomfortable and is recorded, not fixed:** a saved
action whose method has moved is *silently skipped*. ``update_actions_from_json``
does ``getattr(self, name, None)`` and calls it only if truthy, so a user reloading
a history after the refactor gets a partial replay with no error, no log line and no
indication that anything was dropped. Step 7's "keep them as thin View façades, or
ship a name-migration map" is what addresses it; this test makes sure the decision
is taken rather than discovered.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization

SAVED = Path(__file__).parent / "saved_state" / "metadata_action_history.json"


@pytest.fixture
def history() -> Dict[str, Dict[str, Any]]:
    """
    The saved action history, read from the checked-in file.

    :return: the parsed history
    :rtype: Dict[str, Dict[str, Any]]
    """
    return json.loads(SAVED.read_text(encoding="utf-8"))


@pytest.fixture
def view() -> MetadataView:
    """
    A MetadataView built without Qt.

    :return: the view
    :rtype: MetadataView
    """
    instance = MetadataView.__new__(MetadataView)
    shadow_signals(instance, MetadataView)
    return instance


class TestReplayingASavedActionHistory:
    """What happens when a user reloads a history file."""

    def test_the_fixture_is_a_real_saved_file(
        self, history: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Read from disk, not built in the test.

        The point of the fixture is to be the shape the app actually writes; a
        dict literal in the test would only prove the test agrees with itself.
        """
        assert SAVED.is_file()
        assert set(history) == {"0", "1", "2"}
        assert all("function" in entry for entry in history.values())

    def test_each_stored_action_is_replayed_with_its_arguments(
        self, view: MetadataView, history: Dict[str, Dict[str, Any]], mocker
    ) -> None:
        """
        The mechanism: look the name up on the View and call it as saved.

        Both surviving entries must fire, with exactly the arguments the file
        records - a replay that dropped the args would silently reset the tab to
        defaults rather than to what the user saved.
        """
        reset = mocker.patch.object(view, "_reset_actions")
        columns = mocker.patch.object(view, "update_available_columns")

        view.update_actions_from_json(history)

        reset.assert_called_once_with("2d")
        columns.assert_called_once_with("loader")

    def test_an_action_whose_method_has_moved_is_silently_skipped(
        self, view: MetadataView, history: Dict[str, Dict[str, Any]], mocker
    ) -> None:
        """
        **The Step 7 risk, pinned as current behaviour.**

        The third entry names a method the View does not have, which is what every
        saved history becomes once Steps 3 and 4 move a decorated method. Replay
        neither raises nor logs - it just does less than the user asked for. If
        this test ever starts failing because the replay reports the miss, that is
        an improvement and the test should be updated to match.
        """
        mocker.patch.object(view, "_reset_actions")
        mocker.patch.object(view, "update_available_columns")

        view.update_actions_from_json(history)  # must not raise

        assert not hasattr(view, "_method_that_no_longer_exists")

    def test_replay_order_follows_the_file(
        self, view: MetadataView, history: Dict[str, Dict[str, Any]], mocker
    ) -> None:
        """
        Actions are replayed in the order stored, which is what makes a history a
        history rather than a set - resetting after populating would undo it.
        """
        calls = []
        mocker.patch.object(
            view, "_reset_actions", side_effect=lambda *a: calls.append("reset")
        )
        mocker.patch.object(
            view,
            "update_available_columns",
            side_effect=lambda *a: calls.append("columns"),
        )

        view.update_actions_from_json(history)

        assert calls == ["reset", "columns"]

    def test_a_decorated_method_is_reachable_by_its_recorded_name(
        self, view: MetadataView
    ) -> None:
        """
        ``@register_action`` records ``func.__name__``, and replay looks that up.

        ``_reset_actions`` is decorated, so the decorator must not rename it -
        ``functools.wraps`` is what keeps this true, and losing it would break
        every saved history without touching any test that mocks the method.
        """
        assert getattr(view, "_reset_actions", None) is not None
        assert view._reset_actions.__name__ == "_reset_actions"


class TestSessionStateRoundTrip:
    """A tab's session entry must survive being written and read back."""

    def test_subset_filters_survive_a_json_round_trip(
        self, tmp_path: Path, mocker
    ) -> None:
        """
        Written to a file and restored from it, rather than passed in memory.

        Session state is persisted as JSON, so anything that does not survive
        ``json.dumps``/``loads`` - a tuple, a set, a numpy scalar - would be lost
        between sessions while an in-memory test passed. Step 4d moves this state
        to the Model, so the round trip is what must be preserved.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()
        controller.view.subset_filters = {"mine": "duration > 5", "other": "amp < 2"}

        state = controller.get_session_state()
        path = tmp_path / "session.json"
        path.write_text(json.dumps(state), encoding="utf-8")
        restored = json.loads(path.read_text(encoding="utf-8"))

        controller.restore_session_state(restored)

        controller.view.restore_subset_filters.assert_called_once_with(
            {"mine": "duration > 5", "other": "amp < 2"}
        )

    def test_an_empty_filter_set_restores_nothing_rather_than_clearing(
        self, mocker
    ) -> None:
        """
        A session saved with no filters leaves whatever the tab already has.

        Pinned because the guard is a truthiness check: making it ``is not None``
        would start clearing filters on restore, which loses user work silently.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()

        controller.restore_session_state({"subset_filters": {}})

        controller.view.restore_subset_filters.assert_not_called()

    def test_the_state_is_a_copy_not_the_live_mapping(self, mocker) -> None:
        """
        ``get_session_state`` copies, so a later edit cannot rewrite saved history.

        Without the copy the session entry would alias the view's live dict and
        change under the saver's feet before it reached disk.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()
        live = {"mine": "duration > 5"}
        controller.view.subset_filters = live

        state = controller.get_session_state()
        live["added_later"] = "amp < 2"

        assert state["subset_filters"] == {"mine": "duration > 5"}
