"""
Editing, renaming and deleting data plugins through the real plugin controller.

What is real here: ``DataPluginController`` and ``DataPluginModel``, a
``SQLiteEventLoader`` over a synthetic events database, and a ``CUSUM`` fitter that
depends on it - so the dependency graph, settings validation and the history the
controller emits are the shipped ones. Plugins are created the way session restore
creates them, with their settings and key supplied.

What is not: the settings dialog. ``EditDialog`` stands in for it and behaves as
``DictDialog`` does - it edits the dict it was handed in place and returns that same
object - so the controller sees exactly what it would see from the real dialog.
"""

import copy
from typing import Any, Dict, Iterator, List, Optional, Tuple

import pytest

from poriscope.controllers.DataPluginController import DataPluginController
from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from tests.unit.plugins.conformance._recipes import EVENT_FITTER_SETTINGS

LOADER = "loader"
FITTER = "fitter"
STEP_SIZE = EVENT_FITTER_SETTINGS["CUSUM"]["Step Size"]


class EditDialog:
    """
    Stand-in for the plugin settings dialog.

    Writes the given values into the dict it is handed, as the user would by typing,
    and returns that same dict with the chosen name.
    """

    def __init__(
        self,
        values: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None,
        delete: bool = False,
    ) -> None:
        """
        :param values: the values to type in, by parameter name
        :type values: Optional[Dict[str, Any]]
        :param key: the name to give the plugin; None keeps the one offered
        :type key: Optional[str]
        :param delete: whether to press Delete instead of Apply
        :type delete: bool
        """
        self.values = values or {}
        self.key = key
        self.delete = delete

    def __call__(
        self, user_settings: dict, name: str, *args: Any, **kwargs: Any
    ) -> Tuple[dict, str, bool]:
        """
        :param user_settings: the settings the dialog was opened with
        :type user_settings: dict
        :param name: the name the dialog was opened with
        :type name: str
        :param args: the controller's remaining positional arguments, unused
        :type args: Any
        :param kwargs: the controller's keyword arguments, unused
        :type kwargs: Any
        :return: the edited settings, the name and whether Delete was pressed
        :rtype: Tuple[dict, str, bool]
        """
        for parameter, value in self.values.items():
            user_settings[parameter]["Value"] = value
        return user_settings, self.key or name, self.delete


class Recorder:
    """What the controller emitted: history entries and status-panel text."""

    def __init__(self, controller: DataPluginController) -> None:
        """
        :param controller: the controller to listen to
        :type controller: DataPluginController
        """
        self.history: List[Tuple[Dict[str, Any], str]] = []
        self.text: List[str] = []
        controller.update_plugin_history.connect(self._history)
        controller.add_text_to_display.connect(self._text)

    def _history(self, entry: Dict[str, Any], old_key: str) -> None:
        self.history.append((entry, old_key))

    def _text(self, text: str, source: str) -> None:
        self.text.append(text)


def loader_settings(events_db: str) -> Dict[str, Dict[str, Any]]:
    """
    The loader's settings as session history records them.

    :param events_db: the events database to load
    :type events_db: str
    :return: the settings
    :rtype: Dict[str, Dict[str, Any]]
    """
    settings = SQLiteEventLoader().get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = events_db
    return settings


def fitter_settings(loader_key: str) -> Dict[str, Dict[str, Any]]:
    """
    The fitter's settings as session history records them: its loader by name.

    :param loader_key: the name of the loader it fits events from
    :type loader_key: str
    :return: the settings
    :rtype: Dict[str, Dict[str, Any]]
    """
    settings = CUSUM().get_empty_settings(standalone=True)
    for parameter, value in EVENT_FITTER_SETTINGS["CUSUM"].items():
        settings[parameter]["Value"] = value
    settings["MetaEventLoader"] = {"Type": None, "Value": loader_key, "Options": None}
    return settings


@pytest.fixture
def controller(qapp, sample_events_db: str) -> Iterator[DataPluginController]:
    """
    A plugin controller holding a loader and a fitter that depends on it.

    :param qapp: the Qt application
    :param sample_events_db: a synthetic events database
    :type sample_events_db: str
    :return: the controller
    :rtype: Iterator[DataPluginController]
    """
    ctrl = DataPluginController(
        {
            "MetaEventLoader": {"SQLiteEventLoader": SQLiteEventLoader},
            "MetaEventFitter": {"CUSUM": CUSUM},
        },
        "",
        lambda metaclass, subclass: None,
    )
    assert ctrl.validate_and_instantiate_plugin(
        "MetaEventLoader", "SQLiteEventLoader", loader_settings(sample_events_db), LOADER
    )
    assert ctrl.validate_and_instantiate_plugin(
        "MetaEventFitter", "CUSUM", fitter_settings(LOADER), FITTER
    )
    yield ctrl
    ctrl.model.handle_exit()


def edit(
    ctrl: DataPluginController, metaclass: str, key: str, dialog: EditDialog
) -> None:
    """
    Open a plugin's edit dialog, as its menu entry does, and answer it.

    :param ctrl: the controller
    :type ctrl: DataPluginController
    :param metaclass: the plugin's metaclass
    :type metaclass: str
    :param key: the plugin's name
    :type key: str
    :param dialog: how the dialog is answered
    :type dialog: EditDialog
    """
    ctrl.view.get_user_settings = dialog
    ctrl.edit_plugin_settings(metaclass, key)


def fitter(ctrl: DataPluginController) -> CUSUM:
    """
    :param ctrl: the controller
    :type ctrl: DataPluginController
    :return: the live fitter
    :rtype: CUSUM
    """
    instance = ctrl.model.get_plugin_instance("MetaEventFitter", FITTER)
    assert isinstance(instance, CUSUM)
    return instance


class TestARefusedEditChangesNothing:
    """
    A plugin refuses settings it cannot work with - CUSUM refuses a zero step size.
    The refusal must leave the plugin exactly as it was, including what it reports
    as its settings, which is what the next edit dialog opens with and what the
    database writer records as provenance.
    """

    def test_the_plugin_reports_the_settings_it_runs_with(
        self, controller: DataPluginController
    ) -> None:
        before = fitter(controller).get_raw_settings()
        record = Recorder(controller)

        edit(
            controller,
            "MetaEventFitter",
            FITTER,
            EditDialog({"Step Size": 0.0}),
        )

        assert any("Step Size must be larger than 0" in t for t in record.text)
        assert fitter(controller).settings["Step Size"]["Value"] == STEP_SIZE
        assert fitter(controller).get_raw_settings() == before
        assert record.history == []

    def test_the_plugin_can_still_be_edited(
        self, controller: DataPluginController
    ) -> None:
        edit(controller, "MetaEventFitter", FITTER, EditDialog({"Step Size": 0.0}))

        edit(controller, "MetaEventFitter", FITTER, EditDialog({"Step Size": 50.0}))

        assert fitter(controller).settings["Step Size"]["Value"] == 50.0
        assert fitter(controller).get_raw_settings()["Step Size"]["Value"] == 50.0

    def test_the_plugin_can_still_be_deleted(
        self, controller: DataPluginController
    ) -> None:
        edit(controller, "MetaEventFitter", FITTER, EditDialog({"Step Size": 0.0}))

        edit(controller, "MetaEventFitter", FITTER, EditDialog(delete=True))

        assert controller.model.get_plugin_instance("MetaEventFitter", FITTER) is None
        loader = controller.model.get_plugin_instance("MetaEventLoader", LOADER)
        assert loader is not None
        assert loader.get_dependents() == set()

    def test_what_it_reports_can_be_copied(
        self, controller: DataPluginController
    ) -> None:
        """The edit dialog deep-copies what the plugin reports before showing it."""
        edit(controller, "MetaEventFitter", FITTER, EditDialog({"Step Size": 0.0}))

        copy.deepcopy(fitter(controller).get_raw_settings())

