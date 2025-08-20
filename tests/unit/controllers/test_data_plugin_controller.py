import copy
from unittest.mock import MagicMock

import pytest

from poriscope.controllers.DataPluginController import DataPluginController

# ------------------- Fixtures ------------------- #


@pytest.fixture
def mock_model(mocker):
    """
    Provides a fully mocked DataPluginModel with safe defaults for use in controller tests.
    """
    model = mocker.Mock()
    model.get_available_metaclasses.return_value = ["MetaReader", "MetaFilter"]
    model.get_instantiated_plugins_list.return_value = {
        "MetaReader": [],
        "MetaFilter": [],
    }
    model.get_plugin_instance.return_value.get_parents.return_value = []
    model.get_plugin_instance.return_value.get_dependents.return_value = []
    return model


@pytest.fixture
def controller(mocker, mock_model):
    """
    Instantiates a DataPluginController with mocked model and view.
    Replaces PySide6 Signals with MagicMock so that `.emit` can be asserted.
    """
    mocker.patch(
        "poriscope.controllers.DataPluginController.DataPluginModel",
        return_value=mock_model,
    )
    mock_view = mocker.patch(
        "poriscope.controllers.DataPluginController.DataPluginView"
    ).return_value

    ctrl = DataPluginController(available_plugin_classes={}, data_server="/tmp")
    ctrl.model = mock_model
    ctrl.view = mock_view

    # Override Qt signals with MagicMock so `.emit` is mockable
    ctrl.update_available_plugins = MagicMock()
    ctrl.update_plugin_history = MagicMock()
    ctrl.get_settings_from_history = MagicMock()
    ctrl.add_text_to_display = MagicMock()

    return ctrl


# ------------------- Tests ------------------- #


def test_edit_plugin_settings_with_valid_plugin(controller, mocker):
    """
    Should call edit_plugin if get_raw_settings works on the plugin.
    """
    plugin = mocker.Mock()
    plugin.get_raw_settings.return_value = {"some": {"Value": 1}}
    controller.model.get_plugin_instance.return_value = plugin
    controller.edit_plugin = mocker.Mock()

    controller.edit_plugin_settings("MetaReader", "Plugin1")

    controller.edit_plugin.assert_called_once()


def test_edit_plugin_settings_applies_new_settings(controller, mocker):
    """
    Should call apply_settings with updated settings if user modifies them in the dialog.
    """

    # Fake updated settings returned by the dialog
    updated_settings = {"Folder": {"Value": "new_path", "Type": str, "Options": None}}

    # Setup plugin mock
    plugin = mocker.Mock()
    plugin.get_raw_settings.return_value = copy.deepcopy(updated_settings)
    plugin.get_parents.return_value = []
    plugin.get_dependents.return_value = []
    plugin.get_key.return_value = "Plugin1"
    plugin.apply_settings = mocker.Mock()

    controller.model.get_plugin_instance.return_value = plugin
    controller.model.get_available_metaclasses.return_value = []
    controller.model.get_instantiated_plugins_list.return_value = {
        "MetaReader": ["Plugin1"]
    }
    controller.view.get_user_settings = mocker.Mock(
        return_value=(updated_settings, "Plugin1")
    )

    # Act
    controller.edit_plugin_settings("MetaReader", "Plugin1")

    # Assert
    plugin.apply_settings.assert_called_once_with(updated_settings)


def test_edit_plugin_updates_plugin_and_dependents(controller, mocker):
    """
    Test that editing a plugin with dependents updates their parent references
    and the raw settings to reflect the new plugin key. Also confirm that
    history is emitted for both the main and dependent plugins.
    """

    # Main plugin being edited
    plugin = mocker.Mock()
    plugin.get_parents.return_value = []
    plugin.get_dependents.return_value = [("MetaFilter", "Dep1")]
    plugin.get_key.return_value = "OldKey"
    plugin.__class__.__name__ = "MyPlugin"

    # Dependent plugin
    dep_plugin = mocker.Mock()
    dep_plugin.get_key.return_value = "Dep1"
    dep_plugin.__class__.__name__ = "DepPlugin"

    # Shared mutable dict for settings
    shared_settings = {"MetaReader": {"Value": "OldKey", "Options": ["OldKey"]}}
    dep_plugin.get_raw_settings.return_value = shared_settings

    # Plugin lookup logic
    controller.model.get_plugin_instance.side_effect = lambda m, k: (
        plugin if k == "OldKey" else dep_plugin
    )

    # Simulated UI return value
    controller.view.get_user_settings.return_value = (
        {"MetaReader": {"Value": "NewKey"}},
        "NewKey",
    )

    # Mock plugin list return values
    controller.model.get_available_metaclasses.return_value = ["MetaReader"]
    controller.model.get_instantiated_plugins_list.return_value = {
        "MetaReader": ["OldKey"]
    }

    # Call the method
    controller.edit_plugin("MetaReader", "OldKey", {"MetaReader": {"Value": "NewKey"}})

    # Parent update calls
    dep_plugin.unregister_parent.assert_called_once_with("MetaReader", "OldKey")
    dep_plugin.register_parent.assert_called_once_with("MetaReader", "NewKey")

    # Updated value in the settings
    assert shared_settings["MetaReader"]["Value"] == "NewKey"

    # Check both emit calls to update_plugin_history
    expected_history_calls = [
        mocker.call(
            {
                "key": "Dep1",
                "metaclass": "MetaFilter",
                "subclass": "DepPlugin",
                "settings": shared_settings,
            },
            "",
        ),
        mocker.call(
            {
                "key": "NewKey",
                "metaclass": "MetaReader",
                "subclass": "MyPlugin",
                "settings": {"MetaReader": {"Value": "NewKey"}},
            },
            "OldKey",
        ),
    ]
    controller.update_plugin_history.emit.assert_has_calls(
        expected_history_calls, any_order=True
    )
    assert controller.update_plugin_history.emit.call_count == 3

    # Check plugin list update
    controller.update_available_plugins.emit.assert_called_once()


def test_delete_plugin_with_no_dependents(controller, mocker):
    """
    Plugin with no dependents should be deleted successfully and
    UI notified via signals.
    """
    plugin = mocker.Mock()
    plugin.get_dependents.return_value = []
    plugin.get_parents.return_value = []
    controller.model.get_plugin_instance.return_value = plugin

    controller.delete_plugin("MetaReader", "Plugin1")

    controller.update_available_plugins.emit.assert_called_once()
    controller.add_text_to_display.emit.assert_called_once()


def test_delete_plugin_with_dependents(controller, mocker):
    """
    Plugin with dependents should not be deleted, and message should be logged.
    """
    plugin = mocker.Mock()
    plugin.get_dependents.return_value = [("MetaFilter", "Dep1")]
    controller.model.get_plugin_instance.return_value = plugin

    controller.delete_plugin("MetaReader", "Plugin1")

    controller.add_text_to_display.emit.assert_called()


def test_handle_exit(controller):
    """
    Should call the model's shutdown method when exiting.
    """
    controller.handle_exit()
    controller.model.handle_exit.assert_called_once()


def test_get_plugin_instance(controller):
    """
    Should return correct plugin instance from model.
    """
    controller.get_plugin_instance("MetaReader", "MyReader")
    controller.model.get_plugin_instance.assert_called_once_with(
        "MetaReader", "MyReader"
    )


def test_validate_and_instantiate_plugin_with_provided_settings(controller, mocker):
    """
    Plugin should be created and registered when settings are provided explicitly.
    """
    temp_plugin = mocker.Mock()
    controller.model.get_temp_instance.return_value = temp_plugin
    controller.model.get_available_metaclasses.return_value = []
    controller.model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

    #  Return real dict for get_empty_settings
    temp_plugin.get_empty_settings.return_value = {
        "param": {"Value": None},
        "Folder": {"Value": None},
    }

    # Ensure plugin can apply settings
    temp_plugin.apply_settings = mocker.Mock()
    temp_plugin.set_key = mocker.Mock()
    temp_plugin.report_channel_status.return_value = "Status"

    # Set historical settings
    controller.historical_settings = {"param": {"Value": 999}}

    # Simulate dialog return
    controller.view.get_user_settings.return_value = (
        {"param": {"Value": 1}, "Folder": {"Value": "/tmp"}},
        "MyReader_0",
    )

    # Mock plugin registration
    controller.model.register_plugin = mocker.Mock()

    # Run test
    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader", subclass="MyReader", settings=None, key=None
    )

    # Assert plugin was registered
    controller.model.register_plugin.assert_called_once()


def test_validate_and_instantiate_plugin_with_user_input(controller, mocker):
    """
    Should collect user settings via dialog and instantiate plugin with valid inputs.
    """

    # Create a mock plugin and configure expected behavior
    temp_plugin = mocker.Mock()
    temp_plugin.get_empty_settings.return_value = {
        "param": {"Value": None},
        "Folder": {"Value": None},
    }
    temp_plugin.set_key = mocker.Mock()
    temp_plugin.apply_settings = mocker.Mock()
    temp_plugin.report_channel_status.return_value = "Status"

    # Simulate available metaclasses and plugins
    controller.model.get_temp_instance.return_value = temp_plugin
    controller.model.get_available_metaclasses.return_value = []
    controller.model.get_instantiated_plugins_list.return_value = {"MetaReader": []}

    # Return valid settings from dialog
    controller.view.get_user_settings.return_value = (
        {"param": {"Value": 1}, "Folder": {"Value": "/tmp"}},
        "MyReader_0",
    )

    # Simulate prefill with historical settings
    controller.historical_settings = {
        "param": {"Value": 999},
        "Folder": {"Value": None},
    }

    # Mock final registration step
    controller.model.register_plugin = mocker.Mock()

    # Run the method under test
    controller.validate_and_instantiate_plugin(
        metaclass="MetaReader", subclass="MyReader", settings=None, key=None
    )

    # Ensure plugin registration happened
    controller.model.register_plugin.assert_called_once()


def test_validate_and_instantiate_plugin_with_invalid_temp_instance(controller, mocker):
    """
    If instantiation fails, should log error and not raise.
    """
    controller.model.get_temp_instance.side_effect = Exception("fail")
    controller.validate_and_instantiate_plugin("MetaReader", "BrokenSubclass")
    # No crash expected


def test_set_settings(controller):
    """
    Should update historical settings on controller.
    """
    controller.set_settings({"a": 1})
    assert controller.historical_settings == {"a": 1}


def test_update_data_server_location(controller):
    """
    Should update internal reference to data server location.
    """
    controller.update_data_server_location("/new/server")
    assert controller.data_server == "/new/server"


def test_get_instantiated_plugins_list(controller):
    """
    Should return list of instantiated plugins per metaclass.
    """
    controller.get_instantiated_plugins_list()
    controller.model.get_instantiated_plugins_list.assert_called_once()


def test_get_available_metaclasses(controller):
    """
    Should return available plugin categories (metaclasses).
    """
    controller.get_available_metaclasses()
    controller.model.get_available_metaclasses.assert_called_once()
