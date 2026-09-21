"""
Tests for poriscope.controllers.DataPluginController.

Covers:
- __init__ wires view, model, data_server, plugin_manager
- edit_plugin_settings (plugin found with settings, plugin found no get_raw_settings, plugin not found)
- delete_plugin (no dependents success, has dependents blocked, instance not found)
- handle_exit delegates to model
- get_plugin_instance delegates to model
- validate_and_instantiate_plugin (full success with provided key+settings, temp_instance
  creation error, key collision, apply_settings error, register_plugin error,
  empty settings early return, plugin reference resolution error)
- update_data_server_location updates data_server attribute
- get_instantiated_plugins_list delegates to model
- get_available_metaclasses delegates to model
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from poriscope.controllers.DataPluginController import DataPluginController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_model(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked DataPluginModel.

    :param mocker: Pytest-mock fixture.
    :return: Mocked data plugin model.
    """
    model: MagicMock = mocker.Mock()
    model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}
    model.get_available_metaclasses.return_value = []
    return model


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked DataPluginView.

    :param mocker: Pytest-mock fixture.
    :return: Mocked data plugin view.
    """
    return mocker.Mock()


@pytest.fixture
def controller(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> DataPluginController:
    """
    Construct a DataPluginController with view, model, and signals replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: DataPluginController = DataPluginController.__new__(DataPluginController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mock_model
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.data_server = "/tmp/data"
    ctrl.plugin_manager = None
    ctrl._history_lookup = mocker.Mock(return_value=None)

    for sig in [
        "update_available_plugins",
        "update_plugin_history",
        "add_text_to_display",
    ]:
        mock_sig = mocker.Mock()
        mock_sig.emit = mocker.Mock()
        setattr(ctrl, sig, mock_sig)

    return ctrl


# --------------------------- __init__ --------------------------------


def test_init_sets_view_model_and_data_server(mocker: MockerFixture) -> None:
    """
    Verify __init__ creates view and model and stores data_server.

    :param mocker: Pytest-mock fixture.
    """
    mocker.patch("poriscope.controllers.DataPluginController.DataPluginView")
    mocker.patch("poriscope.controllers.DataPluginController.DataPluginModel")
    mocker.patch("poriscope.controllers.DataPluginController.QObject.__init__")

    ctrl = DataPluginController.__new__(DataPluginController)  # type: ignore[type-abstract]
    with patch.object(DataPluginController, "__init__", lambda self, a, b, c: None):
        pass

    # Verify via direct construction with patched dependencies
    mock_view_cls = mocker.patch(
        "poriscope.controllers.DataPluginController.DataPluginView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.controllers.DataPluginController.DataPluginModel"
    )
    history_lookup = mocker.Mock(return_value=None)

    with patch("poriscope.controllers.DataPluginController.QObject.__init__"):
        ctrl = DataPluginController.__new__(DataPluginController)  # type: ignore[type-abstract]
        DataPluginController.__init__(  # type: ignore[misc]
            ctrl, {"MetaReader": {}}, "/data", history_lookup
        )

    assert ctrl.data_server == "/data"
    assert ctrl.plugin_manager is None
    assert ctrl._history_lookup is history_lookup
    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once_with({"MetaReader": {}})


# -------------------- edit_plugin_settings ---------------------------


def test_edit_plugin_settings_calls_edit_plugin_when_settings_retrieved(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Retrieve raw settings from the plugin and call edit_plugin when plugin exists.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = mocker.Mock()
    plugin.get_raw_settings.return_value = {"param": {"Value": 1}}
    mock_model.get_plugin_instance.return_value = plugin

    controller.edit_plugin = mocker.Mock()  # type: ignore[method-assign]
    controller.edit_plugin_settings("MetaReader", "my_reader")

    controller.edit_plugin.assert_called_once_with(  # type: ignore[attr-defined]
        "MetaReader", "my_reader", {"param": {"Value": 1}}
    )


def test_edit_plugin_settings_logs_warning_when_get_raw_settings_raises(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log a warning when get_raw_settings raises AttributeError.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = mocker.Mock()
    plugin.get_raw_settings.side_effect = AttributeError("no settings")
    mock_model.get_plugin_instance.return_value = plugin

    controller.edit_plugin = mocker.Mock()  # type: ignore[method-assign]
    controller.edit_plugin_settings("MetaReader", "my_reader")

    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]
    controller.edit_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_edit_plugin_settings_does_nothing_when_plugin_not_found(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Do nothing when the plugin instance is not found in the model.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    mock_model.get_plugin_instance.return_value = None
    controller.edit_plugin = mocker.Mock()  # type: ignore[method-assign]

    controller.edit_plugin_settings("MetaReader", "missing_key")

    controller.edit_plugin.assert_not_called()  # type: ignore[attr-defined]


# ------------------------ delete_plugin ------------------------------


def test_delete_plugin_removes_plugin_when_no_dependents(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Unregister the plugin and emit update signals when it has no dependents.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    instance = mocker.Mock()
    instance.get_dependents.return_value = []
    instance.get_parents.return_value = []
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    controller.delete_plugin("MetaReader", "r1")

    mock_model.unregister_plugin.assert_called_once_with("MetaReader", "r1")  # type: ignore[attr-defined]
    controller.update_available_plugins.emit.assert_called_once()
    controller.add_text_to_display.emit.assert_called_once()


def test_delete_plugin_unregisters_from_parents_before_deletion(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Unregister the plugin as a dependent from each parent before deleting.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    instance = mocker.Mock()
    instance.get_dependents.return_value = []
    instance.get_parents.return_value = [("MetaLoader", "loader1")]
    parent_instance = mocker.Mock()
    mock_model.get_plugin_instance.side_effect = lambda mc, k: (
        instance if k == "r1" else parent_instance
    )
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    controller.delete_plugin("MetaReader", "r1")

    parent_instance.unregister_dependent.assert_called_once_with("MetaReader", "r1")


def test_delete_plugin_logs_and_emits_when_has_dependents(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log an info message and emit add_text_to_display when the plugin has dependents.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    instance = mocker.Mock()
    instance.get_dependents.return_value = [("MetaWriter", "w1")]
    mock_model.get_plugin_instance.return_value = instance

    controller.delete_plugin("MetaReader", "r1")

    mock_model.unregister_plugin.assert_not_called()  # type: ignore[attr-defined]
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]
    controller.add_text_to_display.emit.assert_called_once()


def test_delete_plugin_logs_warning_when_instance_not_found(
    controller: DataPluginController,
    mock_model: MagicMock,
) -> None:
    """
    Log a warning and return early when the plugin instance is not found.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    """
    mock_model.get_plugin_instance.return_value = None

    controller.delete_plugin("MetaReader", "missing")

    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]
    mock_model.unregister_plugin.assert_not_called()  # type: ignore[attr-defined]


# ------------------------ handle_exit --------------------------------


def test_handle_exit_delegates_to_model(
    controller: DataPluginController,
    mock_model: MagicMock,
) -> None:
    """
    Forward the exit call to the model.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    """
    controller.handle_exit()
    mock_model.handle_exit.assert_called_once()


# -------------------- get_plugin_instance ----------------------------


def test_get_plugin_instance_returns_model_result(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Return the plugin instance from the model.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = mocker.Mock()
    mock_model.get_plugin_instance.return_value = plugin

    result = controller.get_plugin_instance("MetaReader", "r1")

    mock_model.get_plugin_instance.assert_called_once_with("MetaReader", "r1")
    assert result is plugin


# -------------- validate_and_instantiate_plugin ----------------------


def _make_plugin(mocker: MockerFixture, key: str = "r1") -> MagicMock:
    """
    Build a minimal plugin mock suitable for validate_and_instantiate_plugin tests.

    :param mocker: Pytest-mock fixture.
    :param key: Plugin key to return from get_key.
    :return: Mocked plugin instance.
    """
    plugin = mocker.Mock()
    plugin.get_key.return_value = key
    plugin.report_channel_status.return_value = "ok"
    return plugin


def test_validate_and_instantiate_plugin_success_with_provided_settings(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Register a plugin and emit history when settings and key are provided upfront.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}
    settings = {"param": {"Value": 1}}

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=settings,
        key="r1",
    )

    mock_model.register_plugin.assert_called_once_with(plugin, "MetaReader", "r1")
    controller.update_available_plugins.emit.assert_called_once()
    controller.update_plugin_history.emit.assert_called_once()


def test_validate_and_instantiate_plugin_logs_error_on_temp_instance_failure(
    controller: DataPluginController,
    mock_model: MagicMock,
) -> None:
    """
    Log an error and return early when creating a temporary instance raises.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    """
    mock_model.get_temp_instance.side_effect = RuntimeError("bad class")

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader", subclass="BadReader", settings={}, key="r1"
    )

    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_validate_and_instantiate_plugin_returns_early_on_key_collision(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log a warning and return early when the plugin key already exists.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker, key="r1")
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    # Key collision: "r1" already registered under MetaReader
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader", subclass="MyReader", settings={"p": 1}, key="r1"
    )

    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]
    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_validate_and_instantiate_plugin_logs_error_on_apply_settings_failure(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when apply_settings raises.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    plugin.apply_settings.side_effect = RuntimeError("bad settings")
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={"param": {"Value": 1}},
        key="r1",
    )

    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_validate_and_instantiate_plugin_logs_error_on_register_failure(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log an error and return early when register_plugin raises.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}
    mock_model.register_plugin.side_effect = RuntimeError("register failed")

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={"param": {"Value": 1}},
        key="r1",
    )

    controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
    controller.update_plugin_history.emit.assert_not_called()


def test_validate_and_instantiate_plugin_returns_early_on_empty_settings(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Return early without registering when settings resolves to an empty dict.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={},
        key="r1",
    )

    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_validate_and_instantiate_plugin_logs_exception_on_plugin_reference_error(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log an exception and return early when resolving plugin references in settings fails.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    # Mark one settings key as a metaclass so the reference resolution runs
    mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}
    # Trigger failure inside the reference resolution loop
    mock_model.get_plugin_instance.side_effect = RuntimeError("lookup failed")

    settings = {"MetaLoader": {"Value": "loader1", "Options": None}}
    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=settings,
        key="r1",
    )

    controller.logger.exception.assert_called_once()  # type: ignore[attr-defined]
    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


# ------------------ update_data_server_location ----------------------


def test_update_data_server_location_updates_attribute(
    controller: DataPluginController,
) -> None:
    """
    Update the data_server attribute with the new path.

    :param controller: Controller under test.
    """
    controller.update_data_server_location("/new/data/path")
    assert controller.data_server == "/new/data/path"


# ---------------- get_instantiated_plugins_list ----------------------


def test_get_instantiated_plugins_list_delegates_to_model(
    controller: DataPluginController,
    mock_model: MagicMock,
) -> None:
    """
    Return the instantiated plugins list from the model.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    """
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

    result = controller.get_instantiated_plugins_list()

    assert result == {"MetaReader": ["r1"]}
    mock_model.get_instantiated_plugins_list.assert_called_once()


# ------------------- get_available_metaclasses -----------------------


def test_get_available_metaclasses_delegates_to_model(
    controller: DataPluginController,
    mock_model: MagicMock,
) -> None:
    """
    Return the available metaclasses list from the model.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    """
    mock_model.get_available_metaclasses.return_value = ["MetaReader", "MetaWriter"]

    result = controller.get_available_metaclasses()

    assert result == ["MetaReader", "MetaWriter"]
    mock_model.get_available_metaclasses.assert_called_once()


# ----------- validate_and_instantiate_plugin (settings=None path) ----


def test_validate_and_instantiate_plugin_populates_from_historical_settings(
    controller: DataPluginController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Copy Value fields from the history lookup's result into the empty settings dict.

    Covers the ``for setting_key, val in historical_settings.items()`` loop and
    the ``settings[setting_key]["Value"] = val.get("Value")`` line, which only
    execute when settings is None and the history lookup returns a result.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    # get_empty_settings returns a dict with a param key
    empty = {"param": {"Value": None}}
    plugin.get_empty_settings.return_value = empty

    controller._history_lookup = mocker.Mock(return_value={"param": {"Value": 99}})

    # view returns a valid result so the method proceeds
    mock_view.get_user_settings.return_value = ({"param": {"Value": 99}}, "r1", False)

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=None,
        key=None,
    )

    call_settings = mock_view.get_user_settings.call_args[0][0]
    assert call_settings["param"]["Value"] == 99


def test_validate_and_instantiate_plugin_defaults_folder_to_data_server(
    controller: DataPluginController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Set settings["Folder"]["Value"] to data_server when it is None.

    Covers the branch:
        if "Folder" in settings and settings["Folder"].get("Value") is None:
            settings["Folder"]["Value"] = self.data_server

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    empty = {"Folder": {"Value": None}}
    plugin.get_empty_settings.return_value = empty

    controller._history_lookup = mocker.Mock(return_value=None)

    mock_view.get_user_settings.return_value = (
        {"Folder": {"Value": "/tmp/data"}},
        "r1",
        False,
    )

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=None,
        key=None,
    )

    assert empty["Folder"]["Value"] == controller.data_server


def test_validate_and_instantiate_plugin_returns_early_when_user_cancels(
    controller: DataPluginController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Return early when the dialog reports no settings and no key.

    Covers the ``if result is None or result[0] is None: return`` branch
    that fires when the user cancels the settings dialog.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    plugin.get_empty_settings.return_value = {"param": {"Value": None}}
    controller._history_lookup = mocker.Mock(return_value=None)

    mock_view.get_user_settings.return_value = (None, None, False)

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=None,
        key=None,
    )

    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_validate_and_instantiate_plugin_returns_early_when_result_first_none(
    controller: DataPluginController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Return early when the dialog reports a key but no settings.

    Covers the ``result[0] is None`` sub-case of the cancel branch.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    plugin.get_empty_settings.return_value = {"param": {"Value": None}}
    controller._history_lookup = mocker.Mock(return_value=None)

    mock_view.get_user_settings.return_value = (None, "r1", False)

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=None,
        key=None,
    )

    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


# ------------------------- edit_plugin -------------------------------


def _make_edit_plugin_controller(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> DataPluginController:
    """
    Build a controller with signals and a fully mocked instance for edit_plugin tests.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: DataPluginController = DataPluginController.__new__(DataPluginController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mock_model
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.data_server = "/tmp/data"
    ctrl.plugin_manager = None
    ctrl._history_lookup = mocker.Mock(return_value=None)
    for sig in [
        "update_available_plugins",
        "update_plugin_history",
        "add_text_to_display",
    ]:
        mock_sig = mocker.Mock()
        mock_sig.emit = mocker.Mock()
        setattr(ctrl, sig, mock_sig)
    return ctrl


def test_edit_plugin_returns_early_when_user_cancels(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Return early when the dialog is cancelled or dismissed.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = (None, None, False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    mock_model.unregister_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_edit_plugin_deletes_plugin_when_result_is_delete_and_no_dependents(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Unregister the plugin when deletion is requested and no dependents exist.

    The delete branch is self-contained: the ``if key != old_key`` rename check,
    and everything else that reads ``old_key``, lives inside the sibling ``else``
    arm, so the method returns normally once the delete has been performed.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}
    mock_view.get_user_settings.return_value = (None, None, True)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    mock_model.unregister_plugin.assert_called_once_with("MetaReader", "r1")  # type: ignore[attr-defined]
    ctrl.update_available_plugins.emit.assert_called_once()


def test_edit_plugin_blocks_delete_when_has_dependents(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log info and emit message when delete is requested but dependents exist.

    The plugin stays registered and its parent links are restored. As in the
    no-dependents test, the delete branch returns without ever reading
    ``old_key``.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = [("MetaWriter", "w1")]
    instance.report_channel_status.return_value = "ok"
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = (None, None, True)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    mock_model.unregister_plugin.assert_not_called()  # type: ignore[attr-defined]
    ctrl.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_edit_plugin_applies_settings_and_emits_history_on_success(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Apply new settings and emit update signals when key is unchanged.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r1", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    instance.apply_settings.assert_called_once()
    ctrl.update_plugin_history.emit.assert_called()


def test_edit_plugin_logs_info_on_apply_settings_failure(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Log info and return early when apply_settings raises during edit.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.apply_settings.side_effect = RuntimeError("bad apply")
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r1", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    ctrl.logger.info.assert_called_once()  # type: ignore[attr-defined]
    ctrl.add_text_to_display.emit.assert_called_once()


# ---- edit_plugin: settings_key in available_metaclasses (lines 88-91) ----


def test_edit_plugin_updates_app_settings_for_metaclass_keys(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover lines 88-91: when a settings key matches an available metaclass,
    set its Type to str and populate Options from the instantiated plugins list.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
    mock_model.get_instantiated_plugins_list.return_value = {
        "MetaReader": ["r1"],
        "MetaLoader": ["loader1"],
    }
    settings = {"MetaLoader": {"Type": None, "Options": None, "Value": "loader1"}}

    # Capture app_settings at call time before the post-call mutation
    # (the resolution loop sets Type=None on the same dict object,
    # so call_args would reflect the mutated state if checked after the fact)
    captured: dict = {}

    def capture_and_return(app_settings, *args, **kwargs):
        captured["Type"] = app_settings["MetaLoader"]["Type"]
        captured["Options"] = app_settings["MetaLoader"]["Options"]
        return (settings, "r1", False)

    mock_view.get_user_settings.side_effect = capture_and_return

    ctrl.edit_plugin("MetaReader", "r1", settings)

    mock_view.get_user_settings.assert_called_once()
    assert captured["Type"] is str
    assert captured["Options"] == ["loader1"]


# ---- edit_plugin: parents unregister loop (lines 110-111) ----


def test_edit_plugin_unregisters_from_parents(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover lines 110-111: unregister from each parent before editing.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = [("MetaLoader", "loader1")]
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"
    parent_instance = mocker.Mock()
    mock_model.get_plugin_instance.side_effect = lambda mc, k: (
        instance if k == "r1" else parent_instance
    )
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r1", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    parent_instance.unregister_dependent.assert_called_once_with("MetaReader", "r1")


# ---- edit_plugin: key rename path (lines 120-170) ----


def test_edit_plugin_rename_key_updates_dependents_and_emits(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover the key-rename path: update dependents, set new key, emit signals.

    Lines covered: collision check loop, dependent re-registration loop,
    instance.set_key, model.update_plugin_key, update_available_plugins.emit,
    add_text_to_display.emit, update_plugin_history.emit(history, old_key).

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    instance.set_key.assert_called_once_with("r2")
    mock_model.update_plugin_key.assert_called_once_with("MetaReader", "r2", "r1")
    ctrl.update_available_plugins.emit.assert_called_once()
    assert ctrl.update_plugin_history.emit.call_count == 2


def test_edit_plugin_rename_collision_logs_warning_and_returns(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover the key collision warning branch inside the rename path.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1", "r2"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    ctrl.logger.warning.assert_called_once()  # type: ignore[attr-defined]
    ctrl.add_text_to_display.emit.assert_called_once()
    mock_model.update_plugin_key.assert_not_called()  # type: ignore[attr-defined]


def test_edit_plugin_rename_with_dependents_updates_them(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover the dependent re-registration loop during a key rename.

    Lines: dinstance.unregister_parent, register_parent, update_raw_settings,
    replace_raw_settings_option, update_plugin_history.emit(dhistory).

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = [("MetaWriter", "w1")]
    instance.report_channel_status.return_value = "ok"

    dinstance = mocker.Mock()
    dinstance.get_key.return_value = "w1"
    dinstance.__class__.__name__ = "SQLiteWriter"
    dinstance.get_raw_settings.return_value = {
        "MetaReader": {"Value": "r1", "Options": ["r1"]}
    }

    mock_model.get_plugin_instance.side_effect = lambda mc, k: (
        instance if k == "r1" else dinstance
    )
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    dinstance.unregister_parent.assert_called_once_with("MetaReader", "r1")
    dinstance.register_parent.assert_called_once_with("MetaReader", "r2")
    dinstance.update_raw_settings.assert_called_once_with("MetaReader", "r2")


def test_edit_plugin_set_key_exception_logs_and_returns(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover the except Exception block around instance.set_key and the loop.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.set_key.side_effect = RuntimeError("key error")
    mock_model.get_plugin_instance.return_value = instance
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({"param": {"Value": 2}}, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", {"param": {"Value": 1}})

    ctrl.logger.exception.assert_called_once()  # type: ignore[attr-defined]
    ctrl.add_text_to_display.emit.assert_called_once()
    mock_model.update_plugin_key.assert_not_called()  # type: ignore[attr-defined]


# ---- validate_and_instantiate_plugin: except Exception (lines 56-73) ----


def test_validate_and_instantiate_plugin_logs_exception_on_key_setup_error(
    controller: DataPluginController,
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover lines 56-73: the except Exception block around key/settings setup
    when settings is None and set_key raises.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    plugin = _make_plugin(mocker)
    plugin.set_key.side_effect = RuntimeError("set_key failed")
    mock_model.get_temp_instance.return_value = plugin
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

    plugin.get_empty_settings.return_value = {"param": {"Value": None}}
    controller._history_lookup = mocker.Mock(return_value=None)

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings=None,
        key="r1",
    )

    controller.logger.exception.assert_called_once()  # type: ignore[attr-defined]
    mock_model.register_plugin.assert_not_called()  # type: ignore[attr-defined]


def test_edit_plugin_rename_resolves_metaclass_references_in_app_settings(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Cover the inner ``if settings_key in get_available_metaclasses()`` block
    inside the rename try block.

    When a settings key is an available metaclass, the rename path replaces
    its Value with the actual plugin instance and clears Type and Options.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = []
    instance.get_dependents.return_value = []
    instance.report_channel_status.return_value = "ok"

    loader_instance = mocker.Mock()
    mock_model.get_plugin_instance.side_effect = lambda mc, k: (
        instance if k in ("r1", "r2") else loader_instance
    )
    mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
    mock_model.get_instantiated_plugins_list.return_value = {
        "MetaReader": ["r1"],
        "MetaLoader": ["loader1"],
    }

    settings = {"MetaLoader": {"Value": "loader1", "Type": str, "Options": ["loader1"]}}
    mock_view.get_user_settings.return_value = (settings, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", settings)

    instance.apply_settings.assert_called_once()
    applied = instance.apply_settings.call_args[0][0]
    assert applied["MetaLoader"]["Value"] is loader_instance
    assert applied["MetaLoader"]["Type"] is None
    assert applied["MetaLoader"]["Options"] is None


class _FakePlugin:
    """A plugin whose dependency edges can be wired by hand."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.deps: list = []
        self.parents: list = []

    def get_dependents(self) -> list:
        return list(self.deps)

    def get_parents(self) -> list:
        return list(self.parents)

    def unregister_dependent(self, metaclass: str, key: str) -> None:
        self.deps = [d for d in self.deps if d[1] != key]


def _wire_store(controller: DataPluginController, store: dict) -> None:
    """
    Point the controller's mocked model at an in-memory plugin store.

    get_instantiated_plugins_list keeps every metaclass key with an empty list
    once drained, matching the real DataPluginModel - delete_plugin indexes that
    dict by metaclass after deleting, so a fake that dropped drained keys would
    raise KeyError where the real one does not.
    """
    controller.model.get_instantiated_plugins_list.side_effect = lambda: {
        m: list(d) for m, d in store.items()
    }
    controller.model.get_plugin_instance.side_effect = lambda m, k: store.get(
        m, {}
    ).get(k)
    controller.model.unregister_plugin.side_effect = lambda m, k: store[m].pop(k, None)


class TestDeleteAllPlugins:
    """
    Bulk teardown for Reset Session.

    delete_plugin refuses any plugin that still has dependents, so ordering is
    the whole problem: a single pass in arbitrary order leaves most of a
    dependency graph behind.
    """

    def test_drains_a_dependency_chain(self, controller):
        reader, finder, writer = _FakePlugin("r"), _FakePlugin("f"), _FakePlugin("w")
        reader.deps = [("MetaEventFinder", "f")]
        finder.deps = [("MetaWriter", "w")]
        finder.parents = [("MetaReader", "r")]
        writer.parents = [("MetaEventFinder", "f")]
        store = {
            "MetaReader": {"r": reader},
            "MetaEventFinder": {"f": finder},
            "MetaWriter": {"w": writer},
        }
        _wire_store(controller, store)

        survivors = controller.delete_all_plugins()

        assert survivors == []
        assert all(not plugins for plugins in store.values())

    def test_reports_a_graph_it_cannot_drain(self, controller):
        # A cycle can never present a dependent-free plugin. The loop must stop
        # and name the survivors rather than spin forever or claim success.
        a, b = _FakePlugin("a"), _FakePlugin("b")
        a.deps = [("M", "b")]
        b.deps = [("M", "a")]
        store = {"M": {"a": a, "b": b}}
        _wire_store(controller, store)

        survivors = controller.delete_all_plugins()

        assert sorted(survivors) == ["a", "b"]

    def test_reports_a_key_with_no_instance_behind_it(self, controller):
        # A missing instance reports no dependents, so it looks deletable every
        # round, while delete_plugin declines it and leaves the key in place. A
        # guard watching for "nothing looks deletable" would spin forever here,
        # so the loop has to measure what was actually removed.
        store = {"MetaReader": {"ghost": None}}
        _wire_store(controller, store)

        survivors = controller.delete_all_plugins()

        assert survivors == ["ghost"]

    def test_is_a_no_op_when_nothing_is_instantiated(self, controller):
        store: dict = {"MetaReader": {}}
        _wire_store(controller, store)

        assert controller.delete_all_plugins() == []


# ------------- 5c.1 characterization net ----------------------------------
#
# Step 5c.2 replaces edit_plugin's five report-then-rollback blocks with one
# helper, and 5c.3 splits the method along its seams. These pin the three paths
# that no test reached, so a restructuring that changes one of them fails here
# rather than in the app. The rollback block below is the one that matters most:
# it is one of the five 5c.2 will extract, and it had no test at all.


def test_edit_plugin_warns_and_returns_when_the_instance_is_missing(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    An unknown key is reported and nothing else happens - no dialog is opened.

    This is edit_plugin's first guard, and 5c.3 lifts it into a fetch-and-guard
    helper. The assertion that ``get_user_settings`` is never called is what
    makes the test fail if the guard is dropped rather than moved.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    mock_model.get_plugin_instance.return_value = None

    ctrl.edit_plugin("MetaReader", "gone", {})

    ctrl.logger.warning.assert_called_once()
    message = ctrl.logger.warning.call_args[0][0]
    assert "gone" in message and "MetaReader" in message
    mock_view.get_user_settings.assert_not_called()


def test_edit_plugin_reports_a_dependent_with_no_instance_and_keeps_going(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    A registered dependent with no live instance is reported, and the rename still completes.

    This is the ``RuntimeError`` the docstring documents as never reaching the
    caller. The handler is per-dependent and deliberately does *not* roll back,
    so the rename must still finish - asserting ``set_key`` ran is what
    distinguishes "reported and continued" from "reported and aborted".

    5c.3 moves this loop into a rename helper, and the guard is easy to lose on
    the way because the line after it fails anyway, just less legibly.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = set()
    instance.get_dependents.return_value = [("MetaFitter", "d1")]
    instance.report_channel_status.return_value = "ok"

    # The dependent resolves to nothing, which is what raises inside the loop.
    mock_model.get_plugin_instance.side_effect = lambda mc, k: (
        instance if mc == "MetaReader" else None
    )
    mock_model.get_available_metaclasses.return_value = []
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
    mock_view.get_user_settings.return_value = ({}, "r2", False)

    ctrl.edit_plugin("MetaReader", "r1", {})

    ctrl.logger.error.assert_called_once()
    reported = ctrl.logger.error.call_args[0][0]
    assert "d1" in reported and "MetaFitter" in reported
    # The guard's own message, not merely "something went wrong with d1". Without
    # the explicit raise the very next line dereferences None and the same handler
    # reports an AttributeError that still names the dependent, so asserting the
    # text is what makes this test see the guard rather than its absence.
    assert "No plugin instance found for MetaFitter:d1" in reported
    assert any(
        "d1" in call.args[0] for call in ctrl.add_text_to_display.emit.call_args_list
    )
    instance.set_key.assert_called_once_with("r2")


def test_edit_plugin_rolls_back_parent_links_when_reference_resolution_fails(
    mock_model: MagicMock,
    mock_view: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    A failure resolving plugin references reports, restores the parent links and returns.

    edit_plugin unregisters the plugin from its parents up front and re-registers
    them on every abort. This is one of the five report-then-rollback blocks
    5c.2 folds into a single helper, and the only one no test reached - so the
    restore was free to disappear in that edit unnoticed.

    ``apply_settings`` must not run: that is what says the method returned rather
    than carrying on with half-resolved settings.

    :param mock_model: Mocked data plugin model.
    :param mock_view: Mocked data plugin view.
    :param mocker: Pytest-mock fixture.
    """
    ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
    instance = mocker.Mock()
    instance.get_key.return_value = "r1"
    instance.get_parents.return_value = {("MetaWriter", "w1")}
    instance.get_dependents.return_value = []
    parent = mocker.Mock()

    def _get_plugin_instance(metaclass, key):
        if metaclass == "MetaReader":
            return instance
        if metaclass == "MetaWriter":
            return parent
        raise RuntimeError("reference lookup exploded")

    mock_model.get_plugin_instance.side_effect = _get_plugin_instance
    mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
    mock_model.get_instantiated_plugins_list.return_value = {
        "MetaReader": ["r1"],
        "MetaLoader": ["loader1"],
    }
    settings = {"MetaLoader": {"Value": "loader1", "Type": str, "Options": ["loader1"]}}
    # Same key back from the dialog, so the rename branch is skipped and the
    # failure lands in the reference-resolution block specifically.
    mock_view.get_user_settings.return_value = (settings, "r1", False)

    ctrl.edit_plugin("MetaReader", "r1", settings)

    ctrl.logger.exception.assert_called_once()
    assert (
        "Unable to resolve plugin references" in ctrl.logger.exception.call_args[0][0]
    )
    assert any(
        "Unable to resolve plugin references" in call.args[0]
        for call in ctrl.add_text_to_display.emit.call_args_list
    )
    parent.register_dependent.assert_called_once_with("MetaReader", "r1")
    instance.apply_settings.assert_not_called()


def test_validate_and_instantiate_plugin_reports_when_no_key_was_supplied_or_chosen(
    controller: DataPluginController,
    mock_model: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Settings supplied with no key is reported, not allowed through as a keyless plugin.

    Reached by handing in settings - which skips the dialog that would otherwise
    choose a key - while leaving ``key`` at None. The raise is the method's own,
    caught by its own handler, and 5c.4 moves that handler into the shared
    reporting helper.

    :param controller: Controller under test.
    :param mock_model: Mocked data plugin model.
    :param mocker: Pytest-mock fixture.
    """
    temp_instance = mocker.Mock()
    mock_model.get_temp_instance.return_value = temp_instance
    mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader",
        subclass="MyReader",
        settings={"param": {"Value": 1}},
        key=None,
    )

    controller.logger.exception.assert_called_once()
    assert (
        "No plugin key was provided or chosen"
        in controller.logger.exception.call_args[0][0]
    )
    temp_instance.set_key.assert_not_called()
    mock_model.register_plugin.assert_not_called()


# ------------- 5c.2: _report_and_restore ----------------------------------
#
# Driven directly, not only through edit_plugin. The refactor-coverage audit
# names it in its MOVED table, and its criterion is both executed *and* targeted:
# a method reached only in passing through a caller runs, but nothing asserts
# what it did.


class TestReportAndRestore:
    """The one helper the five abandoned-edit paths now share."""

    def test_reports_through_the_logger_method_it_is_given(
        self,
        mock_model: MagicMock,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        Severity travels as the bound method, so ``exception`` still means ``exception``.

        Passing a level and rebuilding the call would have turned
        ``logger.exception`` into ``logger.log(ERROR, ..., exc_info=True)`` and
        lost the plain reading at every call site.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_plugin_instance.return_value = None

        ctrl._report_and_restore(
            ctrl.logger.warning, "something to say", "MetaReader", "r1", set()
        )

        ctrl.logger.warning.assert_called_once_with("something to say")
        ctrl.logger.info.assert_not_called()
        ctrl.logger.exception.assert_not_called()

    def test_shows_the_logged_message_on_the_panel_by_default(
        self,
        mock_model: MagicMock,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        Four of the five call sites log and display the same text, so that is the default.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_plugin_instance.return_value = None

        ctrl._report_and_restore(
            ctrl.logger.info, "the same either way", "MetaReader", "r1", set()
        )

        ctrl.add_text_to_display.emit.assert_called_once_with(
            "the same either way", "DataPluginController"
        )

    def test_shows_a_different_message_on_the_panel_when_given_one(
        self,
        mock_model: MagicMock,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        The rename collision is the fifth: the log states the fault, the panel says what to do.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_plugin_instance.return_value = None

        ctrl._report_and_restore(
            ctrl.logger.warning,
            "Cannot rename plugin to 'r2' because it already exists",
            "MetaReader",
            "r1",
            set(),
            display_message="Please choose a different name.",
        )

        ctrl.logger.warning.assert_called_once_with(
            "Cannot rename plugin to 'r2' because it already exists"
        )
        ctrl.add_text_to_display.emit.assert_called_once_with(
            "Please choose a different name.", "DataPluginController"
        )

    def test_re_registers_the_plugin_on_every_parent(
        self,
        mock_model: MagicMock,
        mock_view: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        The restore is the whole reason the helper exists, so it is asserted directly.

        ``edit_plugin`` unregisters the plugin from its parents before it starts;
        an abandoned edit that does not put them back leaves a parent that no
        longer knows about its child.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        first, second = mocker.Mock(), mocker.Mock()
        mock_model.get_plugin_instance.side_effect = lambda mc, k: (
            first if k == "w1" else second
        )

        ctrl._report_and_restore(
            ctrl.logger.info,
            "gave up",
            "MetaReader",
            "r1",
            {("MetaWriter", "w1"), ("MetaLoader", "l1")},
        )

        first.register_dependent.assert_called_once_with("MetaReader", "r1")
        second.register_dependent.assert_called_once_with("MetaReader", "r1")


def _raise(exc: Exception) -> None:
    """
    Raise from inside a lambda, which cannot contain a raise statement.

    :param exc: the exception to raise
    :type exc: Exception
    :raises Exception: always, the exception passed in
    """
    raise exc


# ------------- 5c.3: edit_plugin's extracted helpers -----------------------
#
# Each of these is named in the refactor-coverage audit's MOVED table, whose
# criterion is executed *and* targeted. edit_plugin's own tests already run them
# all; these are what assert their behaviour directly, so a later change to one
# fails at the helper rather than somewhere downstream of a 72-line caller.


class TestCoercePluginReferencesToKeys:
    """Plugin objects become names the dialog can render as a dropdown."""

    def test_retypes_a_metaclass_setting_and_lists_the_choices(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        A setting keyed by a metaclass gets ``str`` and the instantiated keys.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_instantiated_plugins_list.return_value = {
            "MetaLoader": ["l1", "l2"]
        }
        app_settings = {"MetaLoader": {"Value": "l1", "Type": None, "Options": None}}

        ctrl._coerce_plugin_references_to_keys(app_settings)

        assert app_settings["MetaLoader"]["Type"] is str
        assert app_settings["MetaLoader"]["Options"] == ["l1", "l2"]

    def test_leaves_an_ordinary_setting_untouched(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Only metaclass-keyed settings are plugin references.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        app_settings = {"Threshold": {"Value": 3, "Type": float, "Options": None}}

        ctrl._coerce_plugin_references_to_keys(app_settings)

        assert app_settings == {
            "Threshold": {"Value": 3, "Type": float, "Options": None}
        }


class TestCompleteRequestedDeletion:
    """Delete when nothing depends on it, report and restore when something does."""

    def test_unregisters_a_plugin_with_no_dependents(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The history entry is an empty dict; the key being removed is the second argument.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

        ctrl._complete_requested_deletion("MetaReader", "r1", instance, set(), [])

        mock_model.unregister_plugin.assert_called_once_with("MetaReader", "r1")
        ctrl.update_plugin_history.emit.assert_called_once_with({}, "r1")

    def test_refuses_and_restores_when_something_depends_on_it(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Deleting would leave the dependent pointing at nothing, so it is reported.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        parent = mocker.Mock()
        mock_model.get_plugin_instance.return_value = parent

        ctrl._complete_requested_deletion(
            "MetaReader", "r1", instance, {("MetaWriter", "w1")}, [("MetaFitter", "d1")]
        )

        mock_model.unregister_plugin.assert_not_called()
        ctrl.logger.info.assert_called_once()
        assert "d1" in ctrl.logger.info.call_args[0][0]
        parent.register_dependent.assert_called_once_with("MetaReader", "r1")


class TestRenamePlugin:
    """The rename, its collision guard, and its failure path."""

    def test_refuses_a_name_taken_under_any_metaclass(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Plugin names are unique across every metaclass, not just within one.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        mock_model.get_plugin_instance.return_value = None
        # The clash is under a *different* metaclass than the plugin being renamed.
        mock_model.get_instantiated_plugins_list.return_value = {
            "MetaReader": ["r1"],
            "MetaWriter": ["taken"],
        }

        assert (
            ctrl._rename_plugin("MetaReader", "taken", "r1", instance, set(), [], {})
            is False
        )
        instance.set_key.assert_not_called()
        ctrl.logger.warning.assert_called_once()

    def test_reports_and_gives_up_when_set_key_fails(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        A plugin that refuses its new key leaves the rename abandoned, not half-done.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        instance.set_key.side_effect = ValueError("no")
        mock_model.get_plugin_instance.return_value = None
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

        assert (
            ctrl._rename_plugin("MetaReader", "r2", "r1", instance, set(), [], {})
            is False
        )
        mock_model.update_plugin_key.assert_not_called()
        ctrl.logger.exception.assert_called_once()

    def test_records_the_new_key_against_the_old_one_on_success(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        History is emitted with the *old* key, which is how the rename is recorded.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        instance.report_channel_status.return_value = "ok"
        mock_model.get_plugin_instance.return_value = None
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

        assert (
            ctrl._rename_plugin("MetaReader", "r2", "r1", instance, set(), [], {"p": 1})
            is True
        )
        instance.set_key.assert_called_once_with("r2")
        mock_model.update_plugin_key.assert_called_once_with("MetaReader", "r2", "r1")
        emitted, previous = ctrl.update_plugin_history.emit.call_args[0]
        assert previous == "r1"
        assert emitted["key"] == "r2" and emitted["settings"] == {"p": 1}


class TestUpdateDependentsAfterRename:
    """Each dependent is repointed on its own, and one failure does not stop the rest."""

    def test_repoints_a_dependent_at_the_new_key(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The dependent is updated first and only then snapshotted into history.

        ``get_raw_settings`` returns a copy, so writing through what it hands back
        would update history while leaving the plugin's own values untouched.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        dependent = mocker.Mock()
        dependent.get_key.return_value = "d1"
        dependent.get_raw_settings.return_value = {"after": True}
        mock_model.get_plugin_instance.return_value = dependent

        ctrl._update_dependents_after_rename(
            "MetaReader", "r1", "r2", [("MetaFitter", "d1")]
        )

        dependent.unregister_parent.assert_called_once_with("MetaReader", "r1")
        dependent.register_parent.assert_called_once_with("MetaReader", "r2")
        dependent.update_raw_settings.assert_called_once_with("MetaReader", "r2")
        dependent.replace_raw_settings_option.assert_called_once_with(
            "MetaReader", "r1", "r2"
        )
        emitted, previous = ctrl.update_plugin_history.emit.call_args[0]
        assert previous == "" and emitted["settings"] == {"after": True}

    def test_one_broken_dependent_does_not_stop_the_others(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The plugin is renamed either way, so giving up halfway leaves more stale, not fewer.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        good = mocker.Mock()
        good.get_key.return_value = "d2"
        good.get_raw_settings.return_value = {}
        mock_model.get_plugin_instance.side_effect = lambda mc, k: (
            None if k == "d1" else good
        )

        ctrl._update_dependents_after_rename(
            "MetaReader", "r1", "r2", [("MetaFitter", "d1"), ("MetaFitter", "d2")]
        )

        ctrl.logger.error.assert_called_once()
        assert "No plugin instance found for MetaFitter:d1" in (
            ctrl.logger.error.call_args[0][0]
        )
        good.register_parent.assert_called_once_with("MetaReader", "r2")


class TestResolvePluginReferences:
    """Names chosen in the dialog become live objects again."""

    def test_swaps_the_name_for_the_instance_and_clears_the_choices(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The inverse of the coercion: the plugin wants an object, not a rendered choice.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        loader = mocker.Mock()
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_plugin_instance.return_value = loader
        app_settings = {"MetaLoader": {"Value": "l1", "Type": str, "Options": ["l1"]}}

        assert (
            ctrl._resolve_plugin_references(
                app_settings, "MetaReader", "r1", mocker.Mock(), set()
            )
            is True
        )
        assert app_settings["MetaLoader"]["Value"] is loader
        assert app_settings["MetaLoader"]["Type"] is None
        assert app_settings["MetaLoader"]["Options"] is None

    def test_reports_and_restores_when_a_reference_cannot_be_resolved(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The parent links this edit already undid are put back before giving up.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        parent = mocker.Mock()
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_plugin_instance.side_effect = lambda mc, k: (
            parent if mc == "MetaWriter" else _raise(RuntimeError("boom"))
        )
        app_settings = {"MetaLoader": {"Value": "l1", "Type": str, "Options": ["l1"]}}

        assert (
            ctrl._resolve_plugin_references(
                app_settings, "MetaReader", "r1", instance, {("MetaWriter", "w1")}
            )
            is False
        )
        ctrl.logger.exception.assert_called_once()
        parent.register_dependent.assert_called_once_with("MetaReader", "r1")


class TestApplyEditedSettings:
    """The step that makes the edit real."""

    def test_records_history_and_confirms_on_success(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        History carries the *raw* settings, with plugin references still as names.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()

        ctrl._apply_edited_settings(
            {"resolved": True}, "MetaReader", "r1", instance, set(), {"raw": True}
        )

        instance.apply_settings.assert_called_once_with({"resolved": True})
        emitted, previous = ctrl.update_plugin_history.emit.call_args[0]
        assert previous == "" and emitted["settings"] == {"raw": True}
        assert any(
            "Settings updated successfully for r1" in call.args[0]
            for call in ctrl.add_text_to_display.emit.call_args_list
        )

    def test_reports_restores_and_records_nothing_on_failure(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        A rejected settings dict must not reach history, or a restart would replay it.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        instance = mocker.Mock()
        instance.get_key.return_value = "r1"
        instance.apply_settings.side_effect = ValueError("bad settings")
        parent = mocker.Mock()
        mock_model.get_plugin_instance.return_value = parent

        ctrl._apply_edited_settings(
            {"resolved": True},
            "MetaReader",
            "r1",
            instance,
            {("MetaWriter", "w1")},
            {"raw": True},
        )

        ctrl.update_plugin_history.emit.assert_not_called()
        ctrl.logger.info.assert_called_once()
        parent.register_dependent.assert_called_once_with("MetaReader", "r1")


# ------------- 5c.4: validate_and_instantiate_plugin's helpers -------------
#
# As with 5c.3, each is in the refactor-coverage audit's MOVED table and so has
# to be targeted directly rather than merely run through its caller.


class TestReport:
    """The half that creating and editing a plugin share."""

    def test_says_the_same_thing_to_the_log_and_the_panel(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Creating a plugin has no parent links to undo, so it reports without restoring.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)

        ctrl._report(ctrl.logger.error, "it went wrong")

        ctrl.logger.error.assert_called_once_with("it went wrong")
        ctrl.add_text_to_display.emit.assert_called_once_with(
            "it went wrong", "DataPluginController"
        )

    def test_shows_a_different_message_on_the_panel_when_given_one(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The log states the fault; the panel can instead say what to do about it.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)

        ctrl._report(ctrl.logger.warning, "name taken", display_message="pick another")

        ctrl.logger.warning.assert_called_once_with("name taken")
        ctrl.add_text_to_display.emit.assert_called_once_with(
            "pick another", "DataPluginController"
        )

    def test_does_not_restore_anything(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The difference from ``_report_and_restore``, asserted rather than assumed.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        restore = mocker.patch.object(ctrl, "_restore_parent_dependent_links")

        ctrl._report(ctrl.logger.info, "just saying")

        restore.assert_not_called()


class TestSwapPluginNamesForInstances:
    """The loop editing and creating share."""

    def test_swaps_the_name_and_clears_the_rendered_choice(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The plugin wants an object; Type and Options existed only for the dialog.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        loader = mocker.Mock()
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_plugin_instance.return_value = loader
        app_settings = {
            "MetaLoader": {"Value": "l1", "Type": str, "Options": ["l1"]},
            "Threshold": {"Value": 3, "Type": float, "Options": None},
        }

        ctrl._swap_plugin_names_for_instances(app_settings)

        assert app_settings["MetaLoader"]["Value"] is loader
        assert app_settings["MetaLoader"]["Type"] is None
        assert app_settings["Threshold"] == {
            "Value": 3,
            "Type": float,
            "Options": None,
        }

    def test_raises_rather_than_reporting(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Raising is what lets the two callers report it differently.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_plugin_instance.side_effect = RuntimeError("gone")

        with pytest.raises(RuntimeError):
            ctrl._swap_plugin_names_for_instances(
                {"MetaLoader": {"Value": "l1", "Type": str, "Options": ["l1"]}}
            )
        ctrl.logger.exception.assert_not_called()


class TestMakeTempInstance:
    """The first step, and the one a stale session trips."""

    def test_returns_the_instance_the_model_builds(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        built = mocker.Mock()
        mock_model.get_temp_instance.return_value = built

        assert ctrl._make_temp_instance("MetaReader", "MyReader") is built

    def test_reports_and_returns_none_when_the_class_is_missing(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        A session naming a plugin class this version no longer ships stops here.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_temp_instance.side_effect = KeyError("ABF2Reader")

        assert ctrl._make_temp_instance("MetaReader", "ABF2Reader") is None
        ctrl.logger.error.assert_called_once()
        assert "MetaReader.ABF2Reader" in ctrl.logger.error.call_args[0][0]


class TestKeyIsUnused:
    """Plugin names are unique across every metaclass, not within one."""

    def test_accepts_a_free_name(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

        assert ctrl._key_is_unused("r2") is True
        ctrl.logger.warning.assert_not_called()

    def test_rejects_a_name_held_under_another_metaclass(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        The panel is told what to do; the log is told what happened.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_instantiated_plugins_list.return_value = {
            "MetaReader": [],
            "MetaWriter": ["taken"],
        }

        assert ctrl._key_is_unused("taken") is False
        assert "Please use a unique name" in ctrl.logger.warning.call_args[0][0]
        assert (
            "Please choose a different name"
            in ctrl.add_text_to_display.emit.call_args[0][0]
        )


class TestSettingsFromNewPluginDialog:
    """What the dialog is pre-filled with before the user sees it."""

    def test_prefills_from_history_and_defaults_the_folder(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        A Folder with no value falls back to the data server, not to blank.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        temp.get_empty_settings.return_value = {
            "Folder": {"Value": None},
            "Threshold": {"Value": None},
        }
        ctrl._history_lookup = mocker.Mock(return_value={"Threshold": {"Value": 7}})
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}
        mock_view.get_user_settings.return_value = ({"ok": True}, "MyReader_1", False)

        settings, key = ctrl._settings_from_new_plugin_dialog(
            "MetaReader", "MyReader", temp
        )

        offered = mock_view.get_user_settings.call_args[0][0]
        assert offered["Threshold"]["Value"] == 7
        assert offered["Folder"]["Value"] == "/tmp/data"
        # The offered name counts existing plugins of this metaclass.
        assert mock_view.get_user_settings.call_args[0][1] == "MyReader_1"
        assert (settings, key) == ({"ok": True}, "MyReader_1")

    def test_passes_a_cancelled_dialog_straight_back(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        temp.get_empty_settings.return_value = {}
        ctrl._history_lookup = mocker.Mock(return_value=None)
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": []}
        mock_view.get_user_settings.return_value = (None, None, False)

        assert ctrl._settings_from_new_plugin_dialog("MetaReader", "R", temp) == (
            None,
            None,
        )


class TestPrepareNewPluginSettings:
    """Settling the settings and the name, from either source."""

    def test_keeps_settings_supplied_by_the_caller(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Session restore supplies both, which is what skips the dialog entirely.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

        assert ctrl._prepare_new_plugin_settings(
            "MetaReader", "R", temp, {"a": 1}, "r1"
        ) == ({"a": 1}, "r1")
        mock_view.get_user_settings.assert_not_called()
        temp.set_key.assert_called_with("r1")

    def test_gives_up_when_the_name_is_taken(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": ["r1"]}

        assert (
            ctrl._prepare_new_plugin_settings("MetaReader", "R", temp, {"a": 1}, "r1")
            is None
        )

    def test_reports_when_no_key_was_supplied_or_chosen(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Settings with no key would otherwise make a plugin nothing can refer to.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

        assert (
            ctrl._prepare_new_plugin_settings("MetaReader", "R", temp, {"a": 1}, None)
            is None
        )
        assert (
            "No plugin key was provided or chosen"
            in ctrl.logger.exception.call_args[0][0]
        )


class TestNewPluginSteps:
    """The three remaining steps, each of which reports and stops."""

    def test_resolve_reports_with_the_creation_wording(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Creating says "unable to fetch other plugins"; editing says "resolve references".

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        mock_model.get_available_metaclasses.return_value = ["MetaLoader"]
        mock_model.get_plugin_instance.side_effect = RuntimeError("gone")

        assert (
            ctrl._resolve_new_plugin_references(
                {"MetaLoader": {"Value": "l1", "Type": str, "Options": []}},
                "MetaReader",
                "R",
                "r1",
            )
            is False
        )
        assert (
            "inability to fetch other plugins" in ctrl.logger.exception.call_args[0][0]
        )

    def test_apply_reports_and_stops_on_a_rejected_settings_dict(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        temp.apply_settings.side_effect = ValueError("wrong parent type")

        assert (
            ctrl._apply_new_plugin_settings(temp, {}, "MetaReader", "R", "r1") is False
        )
        assert "wrong parent type" in ctrl.logger.error.call_args[0][0]

    def test_register_hands_the_finished_plugin_to_the_model(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        Before this the plugin is private to the method; after it, the app can see it.

        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()

        assert ctrl._register_new_plugin(temp, "MetaReader", "R", "r1") is True
        mock_model.register_plugin.assert_called_once_with(temp, "MetaReader", "r1")

    def test_register_reports_and_stops_when_the_model_refuses(
        self, mock_model: MagicMock, mock_view: MagicMock, mocker: MockerFixture
    ) -> None:
        """
        :param mock_model: Mocked data plugin model.
        :param mock_view: Mocked data plugin view.
        :param mocker: Pytest-mock fixture.
        """
        ctrl = _make_edit_plugin_controller(mock_model, mock_view, mocker)
        temp = mocker.Mock()
        mock_model.register_plugin.side_effect = RuntimeError("no room")

        assert ctrl._register_new_plugin(temp, "MetaReader", "R", "r1") is False
        assert "Unable to register new plugin instance r1" in (
            ctrl.logger.error.call_args[0][0]
        )


# ------------- 5c.4: validate_and_instantiate_plugin's return value --------
#
# Session restore needs to know whether each entry landed. It used to return
# None either way, so the restore loop counted nothing and the summary announced
# success over a screenful of errors.


class TestValidateAndInstantiateReturnValue:
    """True only when the plugin actually reached the model."""

    def test_returns_true_when_the_plugin_is_registered(
        self,
        controller: DataPluginController,
        mock_model: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        :param controller: Controller under test.
        :param mock_model: Mocked data plugin model.
        :param mocker: Pytest-mock fixture.
        """
        plugin = _make_plugin(mocker)
        mock_model.get_temp_instance.return_value = plugin
        mock_model.get_available_metaclasses.return_value = []
        mock_model.get_instantiated_plugins_list.return_value = {"MetaReader": {}}

        assert (
            controller.validate_and_instantiate_plugin(
                metaclass="MetaReader",
                subclass="MyReader",
                settings={"param": {"Value": 1}},
                key="r1",
            )
            is True
        )

    def test_returns_false_when_the_plugin_class_is_missing(
        self,
        controller: DataPluginController,
        mock_model: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        The stale-session case, which is the one that made this return value necessary.

        :param controller: Controller under test.
        :param mock_model: Mocked data plugin model.
        :param mocker: Pytest-mock fixture.
        """
        mock_model.get_temp_instance.side_effect = KeyError("not installed")

        assert (
            controller.validate_and_instantiate_plugin(
                metaclass="MetaReader",
                subclass="ABF2Reader",
                settings={"param": {"Value": 1}},
                key="r1",
            )
            is False
        )

    def test_returns_false_when_applying_the_settings_fails(
        self,
        controller: DataPluginController,
        mock_model: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """
        The cascade case: a plugin whose parent never instantiated fails here.

        :param controller: Controller under test.
        :param mock_model: Mocked data plugin model.
        :param mocker: Pytest-mock fixture.
        """
        plugin = _make_plugin(mocker)
        plugin.apply_settings.side_effect = ValueError(
            "MetaReader key must have as value an object that inherits from MetaReader"
        )
        mock_model.get_temp_instance.return_value = plugin
        mock_model.get_available_metaclasses.return_value = []
        mock_model.get_instantiated_plugins_list.return_value = {"MetaEventFinder": {}}

        assert (
            controller.validate_and_instantiate_plugin(
                metaclass="MetaEventFinder",
                subclass="ClassicBlockageFinder",
                settings={"param": {"Value": 1}},
                key="f1",
            )
            is False
        )
        mock_model.register_plugin.assert_not_called()
