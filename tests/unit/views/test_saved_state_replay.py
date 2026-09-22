"""
Replaying a saved action history and a saved session - both user data.

Saved action files and saved sessions are both user data, and moving a decorated
method breaks replay. Nothing tested that. The Step 2 exit review found there was
**no checked-in ``.json`` fixture anywhere in ``tests/``**, and that
``update_actions_from_json`` was only ever asserted against a *mock* view - so the
replay mechanism itself had no coverage, only its call site.

Both fixtures in ``saved_state/`` are real files of the shape the app writes, read
from disk rather than synthesised by the tests that consume them.
``metadata_action_history.json`` deliberately contains an entry naming a method that
no longer exists, because that is exactly what a 1.x history becomes once Steps 3
and 4 move things. ``session_1x.json`` is a whole saved session - three tabs, seven
data plugins, a renamed plugin key and a populated subset filter - with its file
paths scrubbed and nothing else changed.

**The finding this pins is uncomfortable and is recorded, not fixed:** a saved
action whose method has moved is *silently skipped*. ``update_actions_from_json``
does ``getattr(self, name, None)`` and calls it only if truthy, so a user reloading
a history after the refactor gets a partial replay with no error, no log line and no
indication that anything was dropped. Recording a declared action name instead of
``func.__name__`` is what addresses it; that was Step 7's until 2026-09-22, when it
was deferred to its own design step and moved to ``future_fixes.md``. This test
makes sure the decision is taken rather than discovered.
"""

import json
from pathlib import Path
from types import MethodType
from typing import Any, Dict

import pytest

from poriscope.models.main_model import MainModel
from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView
from poriscope.utils.plugin_schemas import discover_plugin_classes
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization

REPO_ROOT = Path(__file__).resolve().parents[3]
SAVED = Path(__file__).parent / "saved_state" / "metadata_action_history.json"
SESSION = Path(__file__).parent / "saved_state" / "session_1x.json"


@pytest.fixture
def session() -> Dict[str, Any]:
    """
    Provide a real saved session, read from disk.

    :return: the session file's contents
    :rtype: Dict[str, Any]
    """
    return json.loads(SESSION.read_text(encoding="utf-8"))


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
        between sessions while an in-memory test passed.

        The view's ``get_subset_filters`` is the real one bound onto the mock, not a
        stub: Step 4d routed the controller through it instead of reading the dict
        directly, and a stub would answer with whatever it was told rather than with
        what the method does.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()
        controller.view.subset_filters = {"mine": "duration > 5", "other": "amp < 2"}
        controller.view.get_subset_filters = MethodType(
            MetadataView.get_subset_filters, controller.view
        )

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
        change under the saver's feet before it reached disk. Step 4d moved the copy
        itself into ``MetaSubsetTabView.get_subset_filters``, which is why the real
        method is bound onto the mock here rather than stubbed.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()
        live = {"mine": "duration > 5"}
        controller.view.subset_filters = live
        controller.view.get_subset_filters = MethodType(
            MetadataView.get_subset_filters, controller.view
        )

        state = controller.get_session_state()
        live["added_later"] = "amp < 2"

        assert state["subset_filters"] == {"mine": "duration > 5"}


class TestARealSavedSession:
    """
    A whole session file the application actually wrote, loaded the way it loads one.

    The round-trip tests above build their state in memory from one tab. This one starts
    from a file a user saved - three analysis tabs and seven data plugins across six
    families, including a renamed plugin key and settings whose ``Type`` was written as a
    string because JSON cannot hold a type. Paths in it are scrubbed; nothing else is.

    What it pins is 1.x compatibility, which is the question Step 7 asks: a session saved
    before the refactor names classes by string, and if the refactor renamed or removed
    one, the entry is dropped on load. ``load_session`` reports how many entries it could
    not restore, so a silent loss is not the risk - an *unnoticed* one is.
    """

    def test_the_fixture_is_the_shape_the_app_writes(self, session: Dict[str, Any]):
        """
        Read from disk rather than synthesised, so it cannot drift into a shape the app
        never produces. Every entry is keyed by plugin key and carries the two fields
        ``load_session`` reads before anything else.
        """
        assert session, "the fixture is empty"
        for key, entry in session.items():
            assert "metaclass" in entry, key
            assert "subclass" in entry, key

    def test_every_class_it_names_still_exists(self, session: Dict[str, Any]):
        """
        The actual 1.x compatibility question.

        ``load_session`` instantiates by class name, so a class this version renamed or
        removed is an entry the user silently loses. Asserting it here means the refactor
        cannot rename one without a test saying so - and the fixture covers six plugin
        families plus three tabs, which is most of the surface a real session touches.
        """
        available = set(discover_plugin_classes())
        tabs = {
            path.stem
            for path in Path(REPO_ROOT, "poriscope", "plugins", "analysistabs").glob(
                "*.py"
            )
        }
        missing = []
        for key, entry in session.items():
            subclass = entry["subclass"]
            if subclass not in available and subclass not in tabs:
                missing.append(f"{key} -> {subclass}")
        assert (
            not missing
        ), f"a saved session names classes this version lost: {missing}"

    def test_a_renamed_plugin_key_is_carried_by_key_not_by_class(
        self, session: Dict[str, Any]
    ):
        """
        The fixture holds a reader the user renamed to ``testrename``.

        Keys are user-chosen and classes are not, which is why the entry carries both.
        Restoring by key alone would lose the class; by class alone would lose the name
        the user gave it and every dependent setting that refers to it.
        """
        assert session["testrename"]["subclass"] == "ChimeraReader20240501"
        dependents = [
            key
            for key, entry in session.items()
            for setting in entry.get("settings", {}).values()
            if setting.get("Value") == "testrename"
        ]
        assert dependents, "nothing in the fixture depends on the renamed reader"

    def test_loading_it_restores_types_without_touching_values(self, tmp_path: Path):
        """
        The defect 2.0.0 fixed, exercised against a real file rather than a synthetic one.

        Session JSON cannot hold a type, so ``Type`` is written as a name and restored
        from it. Restoring on the string alone turned any setting whose *value* happened
        to read ``"float"`` into the type itself - a plugin configured with
        ``Event Type: float`` came back broken. Only the ``Type`` key is restored now.
        """
        model = MainModel.__new__(MainModel)
        loaded = json.loads(SESSION.read_text(encoding="utf-8"))
        model.replace_class_names_with_classes(loaded)

        checked = 0
        for entry in loaded.values():
            for name, setting in entry.get("settings", {}).items():
                declared = setting.get("Type")
                if declared is not None:
                    assert isinstance(declared, type), f"{name} Type is {declared!r}"
                    checked += 1
                value = setting.get("Value")
                assert not isinstance(value, type), f"{name} Value became a type"
        assert checked, "the fixture declares no types, so this asserts nothing"

    def test_the_subset_tab_entry_carries_its_filters(self, session: Dict[str, Any]):
        """
        ``MetaSubsetTabController.get_session_state`` writes this key, and 4d changed how
        it is read - through ``view.get_subset_filters()`` rather than by reaching into
        ``view.subset_filters``. The key has to survive that, and a real file is what says
        whether it did.
        """
        metadata = session["MetadataController"]
        assert metadata["subset_filters"] == {"test_filter_assisted": "duration < 300"}

    def test_a_saved_filter_is_restored_onto_the_view(
        self, session: Dict[str, Any], mocker
    ):
        """
        The real restore body, against the value a real saved session carries.

        ``restore_subset_filters`` is bound onto the mock rather than stubbed, so what
        runs is the promoted implementation on ``MetaSubsetTabView`` - the one copy both
        subset tabs share since 4d. A stub would answer with whatever it was told; this
        answers with what the method does, which is the whole question for a file written
        before the promotion.
        """
        controller = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
        controller.view = mocker.Mock()
        controller.view.subset_filters = {}
        controller.view.restore_subset_filters = MethodType(
            MetaSubsetTabView.restore_subset_filters, controller.view
        )

        controller.restore_session_state(session["MetadataController"])

        assert controller.view.subset_filters == {
            "test_filter_assisted": "duration < 300"
        }
        combo = controller.view._subset_controls.filter_comboBox
        combo.addItem.assert_called_once_with("test_filter_assisted")
        combo.selectItem.assert_called_once_with("test_filter_assisted", select=True)
