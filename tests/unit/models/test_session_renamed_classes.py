"""
A saved session that names a plugin class since renamed or merged still restores.

A session names each plugin by its class. ``ChimeraReader20240101`` and
``ChimeraReader20240501`` became one reader, ``ChimeraReaderVC400``, so a session saved by
Poriscope 2.0, or by a build from before the rename, names a class that no longer exists.
Where a session is read, the model swaps such a name for the class that now does its job
and says so; nothing else about the entry changes.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from poriscope.models.main_model import SESSION_FORMAT_VERSION, MainModel

OLD_NAMES = ("ChimeraReader20240101", "ChimeraReader20240501")
LAYOUTS = ("3.0", "2.0")


@pytest.fixture
def main_model() -> MainModel:
    """
    A model that has discovered the shipped plugins.

    :return: the model
    """
    return MainModel(
        {
            "User Plugin Folder": "/mock/path/to/plugins",
            "Parent Folder": "/mock/data/server/location",
        }
    )


def session_naming(reader_class: str, layout: str) -> Dict[str, Any]:
    """
    A session holding a reader of the named class and a finder that depends on it.

    :param reader_class: the class name the reader's entry carries
    :param layout: "3.0" for this version's layout, "2.0" for the map of entries 2.0 wrote
    :return: the file's contents
    """
    reader = {
        "metaclass": "MetaReader",
        "subclass": reader_class,
        "settings": {"Input File": {"Type": "str", "Value": "recording.log"}},
    }
    finder = {
        "metaclass": "MetaEventFinder",
        "subclass": "ClassicBlockageFinder",
        "settings": {"MetaReader": {"Type": None, "Value": "mine", "Options": None}},
    }
    if layout == "2.0":
        return {"mine": reader, "finder": finder}
    return {
        "format_version": SESSION_FORMAT_VERSION,
        "poriscope_version": "3.0.0",
        "last_tab": "",
        "plugins": [{"key": "mine", **reader}, {"key": "finder", **finder}],
        "tabs": {},
    }


def saved(tmp_path: Path, content: Dict[str, Any]) -> Path:
    path = tmp_path / "session.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("old_name", OLD_NAMES)
def test_an_old_chimera_reader_name_loads_as_the_vc400_reader(
    main_model: MainModel, tmp_path: Path, old_name: str, layout: str
) -> None:
    loaded = main_model.load_session(saved(tmp_path, session_naming(old_name, layout)))

    history = loaded.plugin_history
    assert history["mine"]["subclass"] == "ChimeraReaderVC400"
    assert "ChimeraReaderVC400" in main_model.get_plugin_classes("MetaReader")
    # Nothing else about the entry moves: its key, its settings, its place before
    # the finder that names it.
    assert history["mine"]["settings"]["Input File"]["Value"] == "recording.log"
    assert history["finder"]["settings"]["MetaReader"]["Value"] == "mine"
    assert list(history) == ["mine", "finder"]


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("old_name", OLD_NAMES)
def test_the_load_says_which_plugin_changed_class(
    main_model: MainModel, tmp_path: Path, old_name: str, layout: str
) -> None:
    loaded = main_model.load_session(saved(tmp_path, session_naming(old_name, layout)))

    assert len(loaded.notes) == 1
    for word in ("mine", old_name, "ChimeraReaderVC400"):
        assert word in loaded.notes[0]


def test_a_session_naming_the_current_class_loads_without_a_note(
    main_model: MainModel, tmp_path: Path
) -> None:
    loaded = main_model.load_session(
        saved(tmp_path, session_naming("ChimeraReaderVC400", "3.0"))
    )

    assert loaded.plugin_history["mine"]["subclass"] == "ChimeraReaderVC400"
    assert loaded.notes == ()


def test_a_plugin_still_installed_under_an_old_name_keeps_it(
    main_model: MainModel, tmp_path: Path
) -> None:
    """A user's own copy of a removed reader, in their plugin folder, is theirs to use."""
    main_model.available_plugin_classes["MetaReader"]["ChimeraReader20240101"] = object

    loaded = main_model.load_session(
        saved(tmp_path, session_naming("ChimeraReader20240101", "3.0"))
    )

    assert loaded.plugin_history["mine"]["subclass"] == "ChimeraReader20240101"
    assert loaded.notes == ()


def test_only_a_plugin_entry_is_renamed(main_model: MainModel, tmp_path: Path) -> None:
    """A plugin the user happened to key with an old class name keeps its key."""
    content = session_naming("ChimeraReaderVC400", "3.0")
    content["plugins"][0]["key"] = "ChimeraReader20240501"
    content["plugins"][1]["settings"]["MetaReader"]["Value"] = "ChimeraReader20240501"

    loaded = main_model.load_session(saved(tmp_path, content))

    assert list(loaded.plugin_history) == ["ChimeraReader20240501", "finder"]
    finder = loaded.plugin_history["finder"]
    assert finder["settings"]["MetaReader"]["Value"] == "ChimeraReader20240501"
    assert loaded.notes == ()
