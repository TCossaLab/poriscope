import logging
from unittest.mock import MagicMock, call

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.MetaView import MetaView


@pytest.fixture(scope="session")
def app():
    """Ensure that only one QApplication is created for all tests."""
    return QApplication([])


@pytest.fixture(scope="function", autouse=True)
def mock_logging():
    """Mock the logging setup for tests."""
    if not hasattr(logging.root, "pid"):
        logging.root.pid = 0
    if not hasattr(logging.root, "indent"):
        logging.root.indent = 0
    if not hasattr(logging.root, "tab_spaces"):
        logging.root.tab_spaces = 4
    if not hasattr(logging.root, "show_once"):
        logging.root.show_once = False

    yield  # Run the test


@pytest.fixture
def raw_data_view(app):
    """Create an instance of RawDataView for each test and mock methods."""
    view = RawDataView()
    view._setup_ui()
    view.rawdatacontrols = MagicMock()
    view.logger = MagicMock()
    view.figure = MagicMock()
    view.canvas = MagicMock()
    return view


def test_plugin_inheritance(raw_data_view):
    assert isinstance(
        raw_data_view, MetaView
    )  # pytest supports the use of plain assert statements for asserting test conditions


def test_update_plot_1d_data(raw_data_view):
    raw_data_view.figure.add_subplot = MagicMock(
        return_value=MagicMock()
    )  # Ensure update_plot is tested in isolation from real implementation details of adding a subplot to a figure.
    data = np.array([1, 2, 3])
    raw_data_view.update_plot(data)
    raw_data_view.figure.add_subplot.return_value.plot.assert_called_once_with(data)
    raw_data_view.canvas.draw.assert_called_once()
    raw_data_view.logger.info.assert_called_with(
        "Display signal received", extra=raw_data_view.logger.root.extra
    )


def test_update_plot_data(raw_data_view):
    data = np.array([1, 2, 3])
    raw_data_view.update_plot_data(data)
    np.testing.assert_array_equal(raw_data_view.plot_data, data)


def test_update_available_plugins_success(raw_data_view):
    available_plugins = {
        "MetaReader": ["Reader1", "Reader2"],
        "MetaFilter": ["Filter1"],
    }
    raw_data_view.update_available_plugins(available_plugins)
    assert raw_data_view.available_plugins == available_plugins
    raw_data_view.rawdatacontrols.update_readers.assert_called_once_with(
        ["Reader1", "Reader2"]
    )
    raw_data_view.rawdatacontrols.update_filters.assert_called_once_with(["Filter1"])
    raw_data_view.logger.info.assert_has_calls(
        [
            call(
                f"View updated: {available_plugins}",
                extra=raw_data_view.logger.root.extra,
            ),
            call(
                "ComboBoxes updated with available readers and filters",
                extra=raw_data_view.logger.root.extra,
            ),
        ],
        any_order=True,
    )


def test_update_available_plugins_failure(raw_data_view):
    available_plugins = {"MetaReader": ["Reader1"], "MetaFilter": ["Filter1"]}
    raw_data_view.rawdatacontrols.update_filters.side_effect = Exception(
        "Test error"
    )  # simulate error/execption, see how well method handles it
    raw_data_view.update_available_plugins(available_plugins)
    raw_data_view.logger.info.assert_called_with(
        "Updating ComboBoxes failed: Test error", extra=raw_data_view.logger.root.extra
    )
    assert raw_data_view.available_plugins == available_plugins


def test_handle_other_actions_invoked(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
    }
    raw_data_view._handle_other_actions = MagicMock()
    raw_data_view.handle_parameter_change(
        "MetaReader", "some_other_action", (parameters,)
    )
    raw_data_view._handle_other_actions.assert_called_once_with(
        "some_other_action", parameters
    )


def test_handle_parameter_change_load_data(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "TestFilter",
    }
    raw_data_view.plot_data = np.array([1, 2, 3])
    raw_data_view._handle_load_data_and_update_plot = MagicMock()
    raw_data_view.handle_parameter_change(
        "MetaReader", "load_data_and_update_plot", (parameters,)
    )
    raw_data_view._handle_load_data_and_update_plot.assert_called_once_with(parameters)


def test_handle_load_data_invalid_parameters(raw_data_view):
    parameters = {
        "reader": None,
        "channel": "",
        "start_time": "",
        "length": "",
        "filter": "TestFilter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        side_effect=ValueError("Test Error")
    )
    raw_data_view.logger.error = MagicMock()
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view.logger.error.assert_called_once_with(
        "Parameter extraction failed: Test Error", extra=raw_data_view.logger.root.extra
    )


def test_handle_load_data_and_update_plot(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "TestFilter",
    }
    expected_data = np.array([1, 2, 3])
    raw_data_view.plot_data = expected_data
    raw_data_view._extract_plot_parameters = MagicMock(
        return_value=("TestReader", 1, 0.0, 100.0)
    )
    raw_data_view._validate_plot_parameters = MagicMock(return_value=True)
    raw_data_view._load_data = MagicMock()
    raw_data_view._apply_filter = MagicMock()
    raw_data_view.update_plot = MagicMock()
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view._extract_plot_parameters.assert_called_once_with(parameters)
    raw_data_view._validate_plot_parameters.assert_called_once_with(
        "TestReader", 1, 0.0, 100.0
    )
    raw_data_view._load_data.assert_called_once_with("TestReader", 1, 0.0, 100.0)
    raw_data_view._apply_filter.assert_called_once_with("TestFilter")
    raw_data_view.update_plot.assert_called_once_with(expected_data)


def test_handle_load_data_and_update_plot_invalid_params(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": None,
        "start_time": None,
        "length": None,
        "filter": "No Filter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        return_value=("TestReader", None, None, None)
    )
    raw_data_view._validate_plot_parameters = MagicMock(return_value=False)
    raw_data_view.logger.error = MagicMock()
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view.logger.error.assert_called_once_with(
        "Invalid parameters for plotting data", extra=raw_data_view.logger.root.extra
    )


def test_handle_load_data_and_update_plot_no_data(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "TestFilter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        return_value=("TestReader", 1, 0.0, 100.0)
    )
    raw_data_view._validate_plot_parameters = MagicMock(return_value=True)
    raw_data_view._load_data = MagicMock()
    raw_data_view._apply_filter = MagicMock()
    raw_data_view.update_plot = MagicMock()
    raw_data_view.plot_data = None
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view.update_plot.assert_not_called()
    raw_data_view.logger.error.assert_not_called()


def test_extract_plot_parameters(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
    }
    reader, channel, start, length = raw_data_view._extract_plot_parameters(parameters)
    assert reader == "TestReader"
    assert channel == 1
    assert start == 0.0
    assert length == 100.0


def test_validate_plot_parameters_valid(raw_data_view):
    result = raw_data_view._validate_plot_parameters("TestReader", 1, 0.0, 100.0)
    assert result is True


def test_validate_plot_parameters_invalid(raw_data_view):
    result = raw_data_view._validate_plot_parameters("TestReader", None, 0.0, 100.0)
    assert result is False


def test_load_data(raw_data_view):
    raw_data_view.global_signal = MagicMock()
    raw_data_view._load_data("TestReader", 1, 0.0, 100.0)
    raw_data_view.global_signal.emit.assert_called_once_with(
        "MetaReader", "TestReader", "load_data", (0.0, 100.0, 1), "update_plot_data"
    )


def test_load_data_exception_handling(raw_data_view):
    raw_data_view.global_signal = MagicMock()
    raw_data_view.logger.error = MagicMock()
    raw_data_view.global_signal.emit.side_effect = IndexError("Test IndexError")
    raw_data_view._load_data("TestReader", 1, 0.0, 100.0)
    raw_data_view.logger.error.assert_called_once_with(
        "Unable to retrieve requested data: Test IndexError",
        extra=raw_data_view.logger.root.extra,
    )


def test_apply_filter(raw_data_view):
    raw_data_view.global_signal = MagicMock()
    raw_data_view.plot_data = np.array([1, 2, 3])
    raw_data_view._apply_filter("TestFilter")
    raw_data_view.global_signal.emit.assert_called_once_with(
        "MetaFilter",
        "TestFilter",
        "filter_data",
        (raw_data_view.plot_data,),
        "update_plot_data",
    )


def test_apply_filter_exception_handling(raw_data_view):
    raw_data_view.global_signal = MagicMock()
    raw_data_view.logger.error = MagicMock()
    raw_data_view.global_signal.emit.side_effect = Exception("Test Exception")
    raw_data_view._apply_filter("TestFilter")
    raw_data_view.logger.error.assert_called_once_with(
        "Unable to filter data with TestFilter", extra=raw_data_view.logger.root.extra
    )


def test_handle_load_data_and_update_plot_apply_filter(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "TestFilter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        return_value=("TestReader", 1, 0.0, 100.0)
    )
    raw_data_view._validate_plot_parameters = MagicMock(return_value=True)
    raw_data_view._load_data = MagicMock()
    raw_data_view._apply_filter = MagicMock()
    raw_data_view.update_plot = MagicMock()
    raw_data_view.plot_data = np.array([1, 2, 3])
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view._apply_filter.assert_called_once_with("TestFilter")
    raw_data_view.update_plot.assert_called_once_with(raw_data_view.plot_data)


def test_handle_load_data_and_update_plot_success(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "No Filter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        return_value=("TestReader", 1, 0.0, 100.0)
    )
    raw_data_view._validate_plot_parameters = MagicMock(return_value=True)
    raw_data_view._load_data = MagicMock()
    raw_data_view._apply_filter = MagicMock()
    raw_data_view.update_plot = MagicMock()
    raw_data_view.plot_data = np.array([1, 2, 3])
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view._load_data.assert_called_once_with("TestReader", 1, 0.0, 100.0)
    raw_data_view._apply_filter.assert_not_called()
    raw_data_view.update_plot.assert_called_once_with(raw_data_view.plot_data)


def test_handle_load_data_and_update_plot_parameter_extraction_failure(raw_data_view):
    parameters = {
        "reader": "TestReader",
        "channel": "1",
        "start_time": "0",
        "length": "100",
        "filter": "No Filter",
    }
    raw_data_view._extract_plot_parameters = MagicMock(
        side_effect=ValueError("Test Error")
    )
    raw_data_view.logger.error = MagicMock()
    raw_data_view._handle_load_data_and_update_plot(parameters)
    raw_data_view.logger.error.assert_called_once_with(
        "Parameter extraction failed: Test Error", extra=raw_data_view.logger.root.extra
    )


def test_handle_other_actions_with_reader(raw_data_view):
    parameters = {"reader": "TestReader"}
    raw_data_view.global_signal = MagicMock()
    raw_data_view._handle_other_actions("some_action", parameters)
    raw_data_view.global_signal.emit.assert_called_once_with(
        "MetaReader", "TestReader", "get_num_channels", (), "update_channels"
    )


def test_handle_other_actions_without_reader(raw_data_view):
    parameters = {"reader": None}
    raw_data_view.global_signal = MagicMock()
    raw_data_view._handle_other_actions("some_action", parameters)
    raw_data_view.global_signal.emit.assert_not_called()


def test_global_signal_emission(raw_data_view, qtbot):
    with qtbot.waitSignal(raw_data_view.global_signal, timeout=1000) as blocker:
        raw_data_view.emit_global_signal(
            "MetaReader", "TestReader", "load_data", (0, 1, 1), "update_plot_data"
        )
    assert blocker.signal_triggered


def test_update_channels_valid_input(raw_data_view):
    num_channels = 5
    raw_data_view.update_channels(num_channels)
    raw_data_view.rawdatacontrols.update_channels.assert_called_once_with(num_channels)
    raw_data_view.logger.info.assert_called_once_with(
        "Updated channels in RawDataControls through RawDataView",
        extra=raw_data_view.logger.root.extra,
    )


@pytest.mark.parametrize(
    "num_channels", [0, 100, 200]
)  # decorator to runsame test function multiple times with different values.
def test_update_channels_boundary_values(raw_data_view, num_channels):
    raw_data_view.update_channels(num_channels)
    raw_data_view.rawdatacontrols.update_channels.assert_called_once_with(num_channels)
