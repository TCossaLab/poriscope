"""
MetaConditioningLoader is a data-plugin family: the app finds its plugins, offers them in the
Data menu, the generator can start a new one, and scripts can import them.

A family is a closed list in several places at once (``MainModel.ALLOWED_BASE_CLASSES``, the
Data menu, ``poriscope.exposed``, ``scripts/new_plugin.py``); a plugin missing from any one of
them exists on disk and nowhere else. Each place is checked here against the shipped plugin.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List

import poriscope.exposed as exposed
from poriscope.models.main_model import MainModel
from poriscope.plugins.conditioningloaders.NIConditioningLoader import (
    NIConditioningLoader,
)
from poriscope.utils.MetaConditioningLoader import MetaConditioningLoader
from poriscope.views.main_view import MainView

REPO = Path(__file__).parents[4]


def _new_plugin_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "new_plugin_for_family_test", REPO / "scripts" / "new_plugin.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_family_is_recognised() -> None:
    assert MainModel.ALLOWED_BASE_CLASSES["MetaConditioningLoader"] is (
        MetaConditioningLoader
    )


def test_discovery_finds_the_shipped_loader(tmp_path: Path) -> None:
    model = MainModel(
        {
            "Parent Folder": str(tmp_path),
            "User Plugin Folder": str(tmp_path),
            "Log Level": 20,
        }
    )
    assert (
        "NIConditioningLoader"
        in model.get_available_plugins()["MetaConditioningLoader"]
    )


def _menu_entries(view: MainView, title: str) -> List[str]:
    for action in view.menuBar().actions():
        if action.text() == "Data":
            for sub in action.menu().actions():
                if sub.text() == title:
                    return [a.text() for a in sub.menu().actions()]
    return []


def test_the_data_menu_offers_it(qapp: Any) -> None:
    plugins: Dict[str, List[str]] = {
        family: [] for family in MainModel.ALLOWED_BASE_CLASSES
    }
    plugins["MetaConditioningLoader"] = ["NIConditioningLoader"]
    view = MainView(plugins)
    try:
        assert _menu_entries(view, "Load Conditioning Experiment") == [
            "NIConditioningLoader"
        ]
    finally:
        view.close()


def test_scripts_can_import_it() -> None:
    assert exposed.MetaConditioningLoader is MetaConditioningLoader
    assert exposed.NIConditioningLoader is NIConditioningLoader
    assert {"MetaConditioningLoader", "NIConditioningLoader"} <= set(exposed.__all__)


def test_the_generator_knows_its_folder() -> None:
    family = _new_plugin_module().FAMILIES["MetaConditioningLoader"]
    assert family.module == "poriscope.utils.MetaConditioningLoader"
    assert family.folder == "conditioningloaders"
