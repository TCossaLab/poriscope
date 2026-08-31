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

    controller._history_lookup = mocker.Mock(
        return_value={"param": {"Value": 99}}
    )

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
    dsettings Options append/remove, update_plugin_history.emit(dhistory).

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
