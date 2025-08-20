from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from poriscope.views.DataPluginView import DataPluginView

# ------------------- Fixtures ------------------- #


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """
    Ensure QApplication is running during tests.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def plugin_view():
    """Fixture to return a new instance of DataPluginView."""
    return DataPluginView()


# ------------------- Tests ------------------- #


@patch("poriscope.views.DataPluginView.DictDialog")
def test_get_user_settings_returns_expected_tuple(mock_dialog_class, plugin_view):
    """
    Test that get_user_settings correctly returns a tuple of (settings, key)
    from the dialog.
    """
    # Mock the dialog and its return value
    mock_dialog = MagicMock()
    mock_dialog.get_result.return_value = ({"param": "value"}, "plugin_key")
    mock_dialog_class.return_value = mock_dialog

    # Call the method
    result = plugin_view.get_user_settings(
        user_settings={"param": "old_value"},
        name="TestPlugin",
        data_server="DataServer1",
        editable=True,
        show_delete=True,
        editable_source_plugins=True,
        source_plugins=["source1", "source2"],
    )

    # Assert that get_result was called and correct result is returned
    mock_dialog.exec.assert_called_once()
    mock_dialog.get_result.assert_called_once()
    assert result == ({"param": "value"}, "plugin_key")


@patch("poriscope.views.DataPluginView.DictDialog")
def test_get_user_settings_dialog_initialization(mock_dialog_class, plugin_view):
    """
    Test that DictDialog is initialized with correct parameters.
    """
    # Provide input arguments
    user_settings = {"a": 1}
    name = "Sample"
    data_server = "DB"
    editable = False
    show_delete = True
    editable_source_plugins = True
    source_plugins = ["pluginA", "pluginB"]

    # Call the method
    plugin_view.get_user_settings(
        user_settings=user_settings,
        name=name,
        data_server=data_server,
        editable=editable,
        show_delete=show_delete,
        editable_source_plugins=editable_source_plugins,
        source_plugins=source_plugins,
    )

    # Assert the DictDialog was created with correct arguments
    mock_dialog_class.assert_called_once_with(
        user_settings,
        name,
        title="Plugin Settings",
        data_server=data_server,
        editable=editable,
        show_delete=show_delete,
        editable_source_plugins=editable_source_plugins,
        source_plugins=source_plugins,
    )


@patch("poriscope.views.DataPluginView.DictDialog")
def test_get_user_settings_defaults(mock_dialog_class, plugin_view):
    """
    Test that get_user_settings works with only required arguments (defaults).
    """
    # Mock result
    mock_dialog = MagicMock()
    mock_dialog.get_result.return_value = ({"test": 123}, "default_plugin")
    mock_dialog_class.return_value = mock_dialog

    # Call with minimal args
    result = plugin_view.get_user_settings(
        user_settings={}, name="DefaultPlugin", data_server="DefaultServer"
    )

    # Assert result is returned and dialog was used
    assert result == ({"test": 123}, "default_plugin")
    mock_dialog.exec.assert_called_once()
    mock_dialog.get_result.assert_called_once()
