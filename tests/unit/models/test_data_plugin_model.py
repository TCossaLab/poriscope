from unittest.mock import MagicMock

import pytest

from poriscope.models.DataPluginModel import DataPluginModel


# ------------------- Fixtures ------------------- #
@pytest.fixture
def dummy_plugin():
    """Fixture to return a dummy plugin with required methods."""
    plugin = MagicMock()
    plugin.get_raw_settings.return_value = {"param": "value"}
    plugin.close_resources = MagicMock()
    plugin.apply_settings = MagicMock()
    return plugin


@pytest.fixture
def plugin_model(dummy_plugin):
    """Fixture to return a DataPluginModel with one metaclass and one subclass."""
    metaclass = "MetaExample"
    subclass = "ExamplePlugin"
    return DataPluginModel({metaclass: {subclass: lambda: dummy_plugin}})


# ------------------- Tests ------------------- #


def test_register_plugin(plugin_model, dummy_plugin):
    """
    Test registering a plugin instance under a metaclass and key.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "my_plugin")
    assert "my_plugin" in plugin_model.plugins["MetaExample"]


def test_register_plugin_duplicate_key_logs_error(plugin_model, dummy_plugin, caplog):
    """
    Test that attempting to register a plugin with a duplicate key logs an error.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "plugin1")
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "plugin1")  # duplicate
    assert "already exists" in caplog.text


def test_register_plugin_invalid_metaclass_raises_keyerror(plugin_model, dummy_plugin):
    """
    Test that registering a plugin with an invalid metaclass results in failure.
    """
    with pytest.raises(KeyError):
        plugin_model.register_plugin(dummy_plugin, "InvalidMeta", "key")


def test_update_plugin_key_invalid_metaclass_raises_keyerror(plugin_model):
    """
    Test that updating a plugin key with an invalid metaclass results in failure.
    """
    with pytest.raises(KeyError):
        plugin_model.update_plugin_key("InvalidMeta", "new", "old")


def test_update_plugin_key(plugin_model, dummy_plugin):
    """
    Test that updating a plugin's key correctly moves the instance.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "old_key")
    plugin_model.update_plugin_key("MetaExample", "new_key", "old_key")
    assert "new_key" in plugin_model.plugins["MetaExample"]
    assert "old_key" not in plugin_model.plugins["MetaExample"]


def test_get_temp_instance(plugin_model):
    """
    Test retrieving a temporary plugin instance using get_temp_instance.
    """
    instance = plugin_model.get_temp_instance("MetaExample", "ExamplePlugin")
    assert instance is not None


def test_get_instantiated_plugins_list(plugin_model, dummy_plugin):
    """
    Test retrieving a list of instantiated plugin keys for each metaclass.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "abc")
    plugins_list = plugin_model.get_instantiated_plugins_list()
    assert plugins_list["MetaExample"] == ["abc"]


def test_get_available_metaclasses(plugin_model):
    """
    Test that available metaclasses are correctly returned.
    """
    metaclasses = plugin_model.get_available_metaclasses()
    assert metaclasses == ["MetaExample"]


def test_unregister_plugin_success(plugin_model, dummy_plugin):
    """
    Test that a plugin is properly unregistered and its resources closed.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "to_remove")
    plugin_model.unregister_plugin("MetaExample", "to_remove")
    assert "to_remove" not in plugin_model.plugins["MetaExample"]
    dummy_plugin.close_resources.assert_called_once()


def test_unregister_plugin_not_found_raises_keyerror(plugin_model):
    """
    Test that trying to unregister a non-existent plugin raises KeyError.
    """
    with pytest.raises(KeyError):
        plugin_model.unregister_plugin("MetaExample", "not_exist")


def test_handle_exit_closes_all_resources(plugin_model, dummy_plugin):
    """
    Test that handle_exit closes all plugin resources.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "key1")
    plugin_model.handle_exit()
    dummy_plugin.close_resources.assert_called_once()


def test_apply_settings_delegates_correctly(plugin_model, dummy_plugin):
    """
    Test that apply_settings correctly delegates to the plugin's method.
    """
    plugin_model.apply_settings(dummy_plugin, {"param": "value"})
    dummy_plugin.apply_settings.assert_called_once_with({"param": "value"})


def test_get_plugin_instance(plugin_model, dummy_plugin):
    """
    Test retrieving a previously registered plugin instance.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "abc")
    instance = plugin_model.get_plugin_instance("MetaExample", "abc")
    assert instance == dummy_plugin


def test_get_plugin_details_success(plugin_model, dummy_plugin):
    """
    Test retrieving settings for an instantiated plugin.
    """
    plugin_model.register_plugin(dummy_plugin, "MetaExample", "abc")
    settings = plugin_model.get_plugin_details("MetaExample", "abc")
    assert settings == {"param": "value"}


def test_get_plugin_details_not_found_returns_none(plugin_model, caplog):
    """
    Test that requesting plugin details for an unknown key returns None.
    """
    result = plugin_model.get_plugin_details("MetaExample", "missing")
    assert result is None
    assert "No plugin instance found" in caplog.text
