"""
Build a real analysis-tab controller/view/model triad without driving the GUI.

This rung did not exist. Below it, the unit controller tests build controllers with
``__new__`` and mock every collaborator, so nothing crosses a real seam. Above it,
the e2e suites drive genuine clicks through menus and modal dialogs, which is
faithful but slow and full of automation scaffolding. The flows in this package
need the middle: real ``MainModel``/``MainView``/``MainController``, real tab
triad, real data plugins, and no clicking.

Two shortcuts past the GUI, and only two:

* The tab is created by calling ``MainController.instantiate_analysis_tab``
  directly, which is exactly what the menu action's signal reaches. Nothing is
  bypassed except the menu.
* Data plugins are registered by handing an already-configured instance to
  ``DataPluginController.model.register_plugin`` and then emitting the same
  ``update_available_plugins`` notification the real registration path emits.
  What is skipped is the settings dialog, not the wiring - the tab still learns
  about the plugin through the signal it normally learns from.

Everything after that is the application: the signal bus, the controller
mediation, the plugin lifecycle and the real database writes.

A ``QApplication`` is still required, because ``MainView`` is a real widget. The
package's ``conftest`` runs offscreen, as the rest of the suite does.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.views.main_view import MainView


@dataclass
class Triad:
    """One analysis tab, wired into a real application shell."""

    model: MainModel
    view: MainView
    controller: MainController
    tab_controller: Any
    tab_view: Any

    def register(self, instance: BaseDataPlugin, metaclass: str, key: str) -> None:
        """
        Register an already-configured data plugin and announce it to the tabs.

        The announcement matters: registering without it leaves the plugin usable
        over the bus but invisible in the tab's comboboxes, so a flow would then be
        testing a state the application never reaches.

        :param instance: a plugin with its settings already applied
        :type instance: BaseDataPlugin
        :param metaclass: the family the plugin belongs to, e.g. "MetaReader"
        :type metaclass: str
        :param key: the name the plugin is known by in the UI
        :type key: str
        :return: None
        :rtype: None
        """
        plugins = self.controller.data_plugin_controller
        plugins.model.register_plugin(instance, metaclass, key)
        plugins.update_available_plugins.emit(
            metaclass, plugins.model.get_instantiated_plugins_list()[metaclass]
        )

    def available(self, metaclass: str) -> List[str]:
        """
        The keys the tab can currently see for a family.

        :param metaclass: the family to look up
        :type metaclass: str
        :return: the registered keys
        :rtype: List[str]
        """
        listing: Dict[str, List[str]] = (
            self.controller.data_plugin_controller.model.get_instantiated_plugins_list()
        )
        return listing.get(metaclass, [])

    def close(self) -> None:
        """
        Tear the shell down the way closing the app would.

        :return: None
        :rtype: None
        """
        try:
            self.controller.data_plugin_controller.handle_exit()
        finally:
            self.view.close()


def build_triad(subclass: str, tmp_path: Path) -> Triad:
    """
    Construct the app shell and one analysis tab of the requested type.

    :param subclass: the tab controller to instantiate, e.g. "RawDataController"
    :type subclass: str
    :param tmp_path: a scratch directory to use as the app's data root
    :type tmp_path: Path
    :return: the assembled triad
    :rtype: Triad
    :raises KeyError: if the tab was not created, which means the controller
        subclass name is wrong or plugin discovery did not find it
    """
    model = MainModel(
        {
            "Parent Folder": str(tmp_path),
            "User Plugin Folder": str(tmp_path),
            "Log Level": 20,
        }
    )
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)

    controller.instantiate_analysis_tab(subclass)

    tab_controller = controller.analysis_tabs.get(subclass)
    if tab_controller is None:
        raise KeyError(
            f"{subclass} was not instantiated; available tabs are "
            f"{sorted(controller.analysis_tabs)}"
        )

    return Triad(
        model=model,
        view=view,
        controller=controller,
        tab_controller=tab_controller,
        tab_view=tab_controller.view,
    )
