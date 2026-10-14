"""
Every analysis tab shipped with Poriscope names its triad ``<Name>Controller``,
``<Name>Model`` and ``<Name>View``.

``MainView.on_load_analysis_tab_button_click`` relies on it: it must name the page a tab
will open before the tab exists, and a controller builds its view inside ``__init__``, so
the only name available then is ``<Name>View``. A tab that breaks the convention would be
checked against the wrong page name while a walkthrough milestone is active.
"""

import importlib
import pkgutil
from typing import List, Type, get_type_hints

import pytest

import poriscope.plugins as plugins_pkg
from poriscope.utils.MetaController import MetaController

for _finder, _modname, _ispkg in pkgutil.walk_packages(
    plugins_pkg.__path__, prefix=f"{plugins_pkg.__name__}."
):
    importlib.import_module(_modname)


def _shipped_tab_controllers(base: Type = MetaController) -> List[Type]:
    """
    Collect every analysis-tab controller defined under ``poriscope.plugins``.

    Intermediate bases such as ``MetaSubsetTabController`` live in ``poriscope.utils``
    and test doubles live outside the package, so the module filter leaves only tabs.

    :param base: The class whose subclasses are collected.
    :return: The controllers, sorted by name.
    """
    found = set()
    for subclass in base.__subclasses__():
        if subclass.__module__.startswith("poriscope.plugins."):
            found.add(subclass)
        found.update(_shipped_tab_controllers(subclass))
    return sorted(found, key=lambda cls: cls.__name__)


_TABS = _shipped_tab_controllers()


def test_the_shipped_tabs_were_found() -> None:
    assert len(_TABS) >= 5, f"expected the five shipped tabs, found {_TABS}"


@pytest.mark.parametrize("controller", _TABS, ids=[cls.__name__ for cls in _TABS])
def test_tab_triad_is_named_after_its_controller(controller: Type) -> None:
    name = controller.__name__
    assert name.endswith("Controller"), f"{name} must end in 'Controller'"
    stem = name.removesuffix("Controller")
    hints = get_type_hints(controller)
    for role in ("View", "Model"):
        declared = hints[role.lower()].__name__
        assert declared == stem + role, (
            f"{name} declares {role.lower()}: {declared}, expected {stem + role}. "
            "MainView.on_load_analysis_tab_button_click guesses a tab's page name "
            "as <Name>View, so the controller's View must follow the convention."
        )
