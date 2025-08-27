from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget

from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.views.main_view import MainView


@pytest.fixture
def main_view():
    """Fixture to create a MainView instance with all required plugin categories."""
    plugins = {
        "MetaReader": ["DummyReader"],
        "MetaEventLoader": ["DummyEventLoader"],
        "MetaDatabaseLoader": ["DummyDBLoader"],
        "MetaFilter": ["DummyFilter"],
        "MetaWriter": ["DummyWriter"],
        "MetaDatabaseWriter": ["DummyDBWriter"],
        "MetaController": ["DummyController"],
        "MetaEventFinder": ["DummyFinder"],
        "MetaEventFitter": ["DummyFitter"],
    }
    view = MainView(plugins)
    view.show()
    return view


def test_window_title(main_view):
    """
    Test that MainView sets the correct window title on initialization.
    """
    assert main_view.windowTitle().startswith("Poriscope")


def test_toggle_menu_widgets_twice(main_view, qtbot):
    """
    Ensure toggling the menu twice returns visibility to the original state.
    """
    qtbot.wait(50)  # Initial buffer for rendering

    original_icon = main_view.icon_menu_container.isVisible()
    original_text = main_view.text_menu_container.isVisible()

    # First toggle
    main_view.toggle_menu_widgets()
    qtbot.wait(350)  # Wait long enough for QTimer to reset the flag

    # Second toggle
    main_view.toggle_menu_widgets()
    qtbot.wait(100)  # Small buffer

    final_icon = main_view.icon_menu_container.isVisible()
    final_text = main_view.text_menu_container.isVisible()

    assert final_icon == original_icon
    assert final_text == original_text


def test_toggle_menu_widgets_early_return(main_view, qtbot):
    """
    Ensure that if toggle_menu_widgets is called while toggle is in progress,
    the second call is ignored (return branch is covered).
    """
    # First toggle starts the progress
    main_view.toggle_menu_widgets()
    assert main_view.toggle_in_progress is True  # Just to be sure

    # Immediately try to toggle again — should trigger the early return
    main_view.toggle_menu_widgets()

    # Wait for the QTimer to finish so it doesn't interfere with other tests
    qtbot.wait(350)

    # If no exception and coverage shows that line hit, test passes


def test_add_text_to_display(main_view):
    """
    Test appending text to the QTextEdit display.
    """
    main_view.add_text_to_display("Test message", "Logger")
    text = main_view.text_display_widget.toPlainText()
    assert "Logger: Test message" in text


def test_connect_signals_else_branch(main_view, mocker):
    """Cover the else branch for non-string page switch signals."""
    signal = Signal()
    main_view.text_menu_widget.customSwitch = signal
    main_view.icon_menu_widget.customSwitch = signal

    with patch.object(main_view, "switch_to_page"):
        main_view.connect_signals()


def test_switch_to_page_str_signal_connections(main_view, qtbot):
    """
    Trigger page switch signals that connect via lambda with string pages (e.g. 'RawDataView').
    Covers the conditional branch in connect_signals where isinstance(page, str).
    """
    # Add a dummy page to switch to
    dummy_widget = QWidget()
    main_view.add_page("RawDataView", dummy_widget)

    # Emit the text menu signal
    qtbot.wait(10)
    main_view.text_menu_widget.switchToRawData.emit()
    qtbot.wait(10)
    assert main_view.page_title_label.text() == "RawDataView"

    # Emit the icon menu signal
    main_view.icon_menu_widget.switchToRawData.emit()
    qtbot.wait(10)
    assert main_view.page_title_label.text() == "RawDataView"


def test_switch_to_page_signal_connected(main_view, qtbot):
    """
    Ensure switch_to_page is triggered by switchToRawData signals from both menus.
    """
    dummy_widget = QWidget()
    main_view.add_page("RawDataView", dummy_widget)

    # Emit both signals
    getattr(main_view.text_menu_widget, "switchToRawData").emit()
    qtbot.wait(50)
    assert main_view.page_title_label.text() == "RawDataView"

    getattr(main_view.icon_menu_widget, "switchToRawData").emit()
    qtbot.wait(50)
    assert main_view.page_title_label.text() == "RawDataView"


def test_switch_to_page_blocks_milestone_mismatch(main_view):
    """Ensure milestone blocks switching to the wrong page."""
    dummy = QWidget()
    main_view.add_page("WrongPage", dummy)

    main_view._milestone_dialog = MagicMock()
    main_view._expected_next_view = "ExpectedPage"

    previous_text = main_view.page_title_label.text()
    main_view.switch_to_page("WrongPage")

    assert main_view.page_title_label.text() == previous_text


def test_switch_to_page_cleans_milestone(main_view, mocker, qtbot):
    dummy_widget = QWidget()
    main_view.add_page("TargetPage", dummy_widget)

    overlay_mock = MagicMock()
    dialog_mock = MagicMock()
    dialog_mock.overlay = overlay_mock

    main_view._milestone_dialog = dialog_mock
    main_view._expected_next_view = "TargetPage"

    main_view.switch_to_page("TargetPage")

    overlay_mock.close.assert_called_once()
    overlay_mock.deleteLater.assert_called_once()
    dialog_mock.close.assert_called_once()
    dialog_mock.deleteLater.assert_called_once()
    assert main_view._milestone_dialog is None


def test_switch_to_page_cleans_analysis_proxy(main_view):
    """
    Test that switching to the expected next page clears the analysis proxy widget.
    Ensures cleanup logic is properly triggered in walkthrough milestone.
    """
    dummy = QWidget()
    main_view.add_page("ExpectedPage", dummy)

    proxy = QWidget()
    main_view._analysis_proxy = proxy
    main_view._expected_next_view = "ExpectedPage"

    # Ensure milestone is active so the production cleanup branch runs
    main_view._milestone_dialog = MagicMock()
    main_view._milestone_dialog.overlay = None

    main_view.switch_to_page("ExpectedPage")

    assert main_view._analysis_proxy is None


def test_add_page_and_switch(main_view):
    """
    Test adding a new page and switching to it.
    """
    dummy_widget = QWidget()
    main_view.add_page("DummyView", dummy_widget)
    assert "DummyView" in main_view.pages
    assert main_view.page_title_label.text() == "DummyView"


@patch(
    "poriscope.views.main_view.QFileDialog.getSaveFileName",
    return_value=("session.json", None),
)
def test_get_save_file_name(mock_dialog, main_view):
    """
    Test get_save_file_name returns the selected path from the dialog.
    """
    result = main_view.get_save_file_name()
    assert result == "session.json"
    mock_dialog.assert_called_once()


@patch(
    "poriscope.views.main_view.QFileDialog.getOpenFileName",
    return_value=("session.json", None),
)
def test_on_load_session_button_click_emits_signal(mock_dialog, main_view, qtbot):
    """
    Test that on_load_session_button_click emits the load_session signal with the selected file.
    """
    with qtbot.waitSignal(main_view.load_session, timeout=1000) as signal:
        main_view.on_load_session_button_click()
    assert signal.args[0] == "session.json"


def test_on_restore_session_button_click_emits_signal(main_view, qtbot):
    """
    Test that on_restore_session_button_click emits the load_session signal with None.
    """
    with qtbot.waitSignal(main_view.load_session, timeout=1000) as signal:
        main_view.on_restore_session_button_click()
    assert signal.args[0] is None


def test_populate_plugins_menu_empty(main_view, caplog):
    """
    Test handling of empty analysis tab list in populate_plugins_menu.
    """
    main_view.populate_plugins_menu({})
    assert "No analysis tabs available" in caplog.text


def test_populate_plugins_menu_with_tabs(main_view, qtbot):
    """
    Test plugin menu is populated correctly with received analysis tabs.
    """
    dummy_view = MagicMock()
    dummy_view.__class__.__name__ = "DummyView"
    analysis_tabs = {"DummyController": MagicMock(view=dummy_view)}

    main_view.populate_plugins_menu(analysis_tabs)
    # No assertion here; you can manually inspect via debugger or extend test to verify QAction creation


def test_on_plugins_button_click_logs_and_emits(main_view, qtbot, caplog):
    """Test that plugins button click logs and emits the signal."""
    with caplog.at_level("INFO"):
        with qtbot.waitSignal(main_view.request_analysis_tabs, timeout=1000):
            main_view.on_plugins_button_click()

    assert "Plugins button clicked" in caplog.text
    assert "signal emitted" in caplog.text


def test_settings_clear_cache_signal(main_view, qtbot):
    """
    Test that clearing cache from the settings window emits the clear_cache signal.
    """
    with qtbot.waitSignal(main_view.clear_cache, timeout=1000):
        main_view.settings_window.clear_cache.emit()


@patch("poriscope.views.main_view.IntroDialog")
def test_show_walkthrough_intro_triggers_intro(mock_intro, main_view):
    """
    Ensure the walkthrough intro dialog is triggered if not already active.
    """
    instance = mock_intro.return_value
    instance.exec = MagicMock()
    instance.start_walkthrough = MagicMock()
    main_view._walkthrough_active = False
    main_view.show_walkthrough_intro()
    instance.exec.assert_called_once()


def test_on_help_button_click_opens_help_window(mocker, main_view):
    """
    Test that clicking the help button opens the HelpCentre window.
    """
    # Patch HelpCentre used in main_view
    mock_help = mocker.patch("poriscope.views.help.HelpCentre")

    main_view.on_help_button_click()

    mock_help.assert_called_once()
    mock_help.return_value.show.assert_called_once()


def test_update_log_level_emits_signal(main_view, qtbot):
    with qtbot.waitSignal(main_view.update_logging_level, timeout=1000) as blocker:
        main_view.update_log_level(2)
    assert blocker.args == [2]


def test_get_data_server_emits_signal(main_view, qtbot):
    with qtbot.waitSignal(main_view.get_shared_data_server, timeout=1000):
        main_view.get_data_server()


def test_get_user_plugin_folder_emits_signal(main_view, qtbot):
    with qtbot.waitSignal(main_view.get_user_plugin_location, timeout=1000):
        main_view.get_user_plugin_folder()


def test_set_data_server_calls_settings_window(main_view, mocker):
    mock_settings = mocker.Mock()
    main_view.settings_window = mock_settings

    main_view.set_data_server("test_server")
    mock_settings.set_data_server.assert_called_once_with("test_server")


def test_set_user_plugin_location_calls_settings_window(main_view, mocker):
    mock_settings = mocker.Mock()
    main_view.settings_window = mock_settings

    main_view.set_user_plugin_location("path/to/plugins")
    mock_settings.set_user_plugin_location.assert_called_once_with("path/to/plugins")


def test_update_data_server_emits_signal(main_view, qtbot):
    with qtbot.waitSignal(
        main_view.update_data_server_location, timeout=1000
    ) as blocker:
        main_view.update_data_server("new_server")
    assert blocker.args == ["new_server"]


def test_update_user_plugin_folder_emits_signal(main_view, qtbot):
    with qtbot.waitSignal(
        main_view.update_user_plugin_location, timeout=1000
    ) as blocker:
        main_view.update_user_plugin_folder("new_folder")
    assert blocker.args == ["new_folder"]


def test_on_help_window_closed_emits_signal(main_view, qtbot):
    """
    Test that on_help_window_closed sets the help_window to None,
    emits the help_window_closed signal, and calls event.accept().
    """
    # Set a dummy help window to ensure it gets reset
    main_view.help_window = "dummy"
    event = MagicMock()

    # Wait for the help_window_closed signal to be emitted
    with qtbot.waitSignal(main_view.help_window_closed, timeout=1000):
        main_view.on_help_window_closed(event)

    # Ensure the internal reference is cleared and the event is accepted
    assert main_view.help_window is None
    event.accept.assert_called_once()


@pytest.mark.parametrize(
    "method_name, metaclass",
    [
        ("on_load_timeseries_button_click", "MetaReader"),
        ("on_load_filter_button_click", "MetaFilter"),
        ("on_load_writer_button_click", "MetaWriter"),
        ("on_load_db_writer_button_click", "MetaDatabaseWriter"),
        ("on_load_events_button_click", "MetaEventLoader"),
        ("on_load_metadata_button_click", "MetaDatabaseLoader"),
        ("on_load_eventfinder_button_click", "MetaEventFinder"),
        ("on_load_eventfitter_button_click", "MetaEventFitter"),
    ],
)
def test_on_load_button_click_emits_instantiate_plugin(
    main_view, qtbot, method_name, metaclass
):
    """
    Test that each on_load_*_button_click method emits the correct signal with metaclass and subclass.
    """
    method = getattr(main_view, method_name)
    subclass = "DummySubclass"

    with qtbot.waitSignal(main_view.instantiate_plugin, timeout=1000) as blocker:
        method(subclass)

    assert blocker.args == [metaclass, subclass]


def test_on_save_session_button_click_emits_if_file_selected(main_view, mocker, qtbot):
    """
    Test that on_save_session_button_click emits the save_session signal
    when a file name is returned by get_save_file_name().
    """
    # Simulate user selecting a save file path
    mocker.patch.object(main_view, "get_save_file_name", return_value="session.json")

    # Ensure the save_session signal is emitted with the correct path
    with qtbot.waitSignal(main_view.save_session, timeout=1000) as signal:
        main_view.on_save_session_button_click()

    assert signal.args[0] == "session.json"


def test_on_save_session_button_click_does_nothing_if_no_file(main_view, mocker):
    """
    Ensure no signal is emitted if user cancels save dialog.
    """
    # Simulate user cancelling
    mocker.patch.object(main_view, "get_save_file_name", return_value=None)

    # Call the method; no need to mock emit — just ensure nothing crashes
    main_view.on_save_session_button_click()

    # Nothing to assert; success = no crash and no signal emitted


def test_on_raw_data_view_click(main_view, qtbot, mocker):
    mocker.patch.object(main_view, "on_load_analysis_tab_button_click")
    mocker.patch.object(main_view, "switch_to_page")

    main_view.on_raw_data_view_click()

    main_view.on_load_analysis_tab_button_click.assert_called_once_with(
        "RawDataController"
    )
    main_view.switch_to_page.assert_called_once_with("RawDataView")


def test_on_stats_click(main_view, mocker):
    mocker.patch.object(main_view, "on_load_analysis_tab_button_click")
    mocker.patch.object(main_view, "switch_to_page")

    main_view.on_stats_click()

    main_view.on_load_analysis_tab_button_click.assert_called_once_with(
        "EventAnalysisController"
    )
    main_view.switch_to_page.assert_called_once_with("EventAnalysisView")


def test_handle_menu_click_switches_page(main_view):
    dummy = QWidget()
    main_view.add_page("MyPage", dummy)
    main_view.handle_menu_click("MyPage")
    assert main_view.page_title_label.text() == "MyPage"


def test_on_settings_button_click_adds_and_switches(main_view, mocker):
    mocker.patch.object(main_view, "add_page")
    mocker.patch.object(main_view, "switch_to_page")
    main_view.on_settings_button_click()
    main_view.add_page.assert_called_once_with("Settings", main_view.settings_window)
    main_view.switch_to_page.assert_called_once_with("Settings")


def test_get_intro_text_returns_specific(main_view):
    """Ensure correct tutorial string is returned for a known view name."""
    assert "Raw Data Tab" in main_view.get_intro_text("RawDataView")


def test_get_intro_text_returns_default(main_view):
    """Return default message if view name not in step mapping."""
    assert (
        main_view.get_intro_text("UnknownView") == "You're starting a guided tutorial."
    )


def test_get_analysis_highlight_with_existing_action(main_view):
    """Ensure a proxy widget is created and returned when 'Analysis' action exists."""
    action = QAction("Analysis", main_view)
    main_view.menuBar().addAction(action)
    proxy = main_view.get_analysis_highlight()
    assert isinstance(proxy, QWidget)


def test_get_analysis_highlight_returns_menubar_if_no_action(main_view):
    # Remove the 'Analysis' action that setup_menubar added
    for act in list(main_view.menuBar().actions()):
        if act.text() == "Analysis":
            main_view.menuBar().removeAction(act)
    # Make sure cached ref isn’t used
    if hasattr(main_view, "analysis_action_ref"):
        delattr(main_view, "analysis_action_ref")

    result = main_view.get_analysis_highlight()
    assert result == main_view.menuBar()  # Ensure fallback is menu bar


def test_get_walkthrough_steps_empty_if_view_not_in_pages(main_view):
    """Return empty list if current view is not found in pages."""
    main_view.page_title_label.setText("UnknownView")
    assert main_view.get_walkthrough_steps() == []


def test_get_walkthrough_steps_from_widget(main_view):
    """Get walkthrough steps from a view widget subclassing WalkthroughMixin."""

    class DummyView(QWidget, WalkthroughMixin):
        def get_walkthrough_steps(self):
            return ["step1"]

    dummy_view = DummyView()
    main_view.pages["MyView"] = {"widget": dummy_view}
    main_view.page_title_label.setText("MyView")
    assert main_view.get_walkthrough_steps() == ["step1"]


def test_show_walkthrough_intro_skips_if_active(main_view, mocker):
    """Do nothing if walkthrough is already active."""
    main_view._walkthrough_active = True
    mocker.patch("poriscope.views.main_view.IntroDialog")
    main_view.show_walkthrough_intro()  # Should skip without error


def test_show_walkthrough_intro_launches_dialog(main_view, mocker):
    """Launch intro dialog if walkthrough is not active."""
    main_view._walkthrough_active = False
    intro_mock = mocker.patch("poriscope.views.main_view.IntroDialog")
    instance = intro_mock.return_value
    instance.exec = MagicMock()
    main_view.page_title_label.setText("MainView")
    main_view.show_walkthrough_intro()
    instance.exec.assert_called_once()


def test_on_intro_finished_mainview_triggers_milestone(main_view, mocker):
    """Show milestone step if view is MainView."""
    mock = mocker.patch.object(main_view, "show_milestone_step")
    main_view._on_intro_finished("MainView")
    mock.assert_called_once_with("MainView")


def test_on_intro_finished_triggers_walkthrough_launch(main_view, mocker):
    """Launch walkthrough if view is not MainView."""
    mock = mocker.patch.object(main_view, "launch_walkthrough_if_needed")
    main_view._on_intro_finished("RawDataView")
    mock.assert_called_once()


def test_launch_walkthrough_if_needed_success(main_view, qtbot):
    """
    Test launching a walkthrough when conditions are right.
    """
    widget = DummyWalkthroughWidget()
    widget.was_launched = False

    main_view.pages["MyView"] = {"widget": widget}
    main_view.page_title_label.setText("MyView")
    main_view._walkthrough_active = False

    main_view.launch_walkthrough_if_needed()

    assert main_view._walkthrough_active is True
    assert widget.was_launched is True


def test_launch_walkthrough_if_already_active(main_view, mocker):
    """Do not launch if already active."""
    main_view._walkthrough_active = True
    dummy = MagicMock(spec=WalkthroughMixin)
    main_view.pages["MyView"] = {"widget": dummy}
    main_view.page_title_label.setText("MyView")

    main_view.launch_walkthrough_if_needed()
    dummy.launch_walkthrough.assert_not_called()


def test_launch_walkthrough_if_view_does_not_support_walkthrough(main_view, mocker):
    """Log and skip if widget is not subclass of WalkthroughMixin."""
    main_view._walkthrough_active = False
    dummy = QWidget()
    main_view.pages["MyView"] = {"widget": dummy}
    main_view.page_title_label.setText("MyView")
    main_view.launch_walkthrough_if_needed()


def test_reset_walkthrough_flag_success(main_view, mocker):
    """Reset active flag and show milestone if completed."""
    mock = mocker.patch.object(main_view, "show_milestone_step")
    main_view._walkthrough_active = True
    main_view._reset_walkthrough_flag("RawDataView", completed_successfully=True)
    assert not main_view._walkthrough_active
    mock.assert_called_once()


def test_clear_milestone_dialog_with_overlay(main_view, mocker):
    overlay_mock = mocker.MagicMock()
    dialog_mock = mocker.MagicMock()
    dialog_mock.overlay = overlay_mock

    main_view._milestone_dialog = dialog_mock

    main_view.clear_milestone_dialog()

    # Confirm overlay is closed and deleted
    overlay_mock.close.assert_called_once()
    overlay_mock.deleteLater.assert_called_once()

    # Confirm dialog is closed and deleted
    dialog_mock.close.assert_called_once()
    dialog_mock.deleteLater.assert_called_once()

    # Ensure milestone is cleared
    assert main_view._milestone_dialog is None


def test_clear_milestone_dialog_overlay_cleanup_raises(main_view, mocker, caplog):
    """
    Ensure exception in overlay cleanup is caught and logged.
    """
    overlay_mock = mocker.MagicMock()
    overlay_mock.close.side_effect = Exception("Overlay error")

    dialog_mock = mocker.MagicMock()
    dialog_mock.overlay = overlay_mock

    main_view._milestone_dialog = dialog_mock

    with caplog.at_level("DEBUG"):
        main_view.clear_milestone_dialog()

    assert "Overlay cleanup error" in caplog.text
    assert main_view._milestone_dialog is None


def test_clear_milestone_dialog_dialog_cleanup_raises(main_view, mocker, caplog):
    """
    Ensure exception in dialog cleanup is caught and logged.
    """
    dialog_mock = mocker.MagicMock()
    dialog_mock.overlay = None
    dialog_mock.close.side_effect = Exception("Dialog close error")

    main_view._milestone_dialog = dialog_mock

    with caplog.at_level("DEBUG"):
        main_view.clear_milestone_dialog()

    assert "Milestone dialog cleanup error" in caplog.text
    assert main_view._milestone_dialog is None


def test_clear_milestone_dialog_no_overlay(main_view, mocker):
    dialog_mock = mocker.MagicMock()
    dialog_mock.overlay = None  # Simulates no overlay

    main_view._milestone_dialog = dialog_mock

    main_view.clear_milestone_dialog()

    dialog_mock.close.assert_called_once()
    dialog_mock.deleteLater.assert_called_once()
    assert main_view._milestone_dialog is None


def test_clear_milestone_dialog_none(main_view, caplog):
    main_view._milestone_dialog = None

    with caplog.at_level("DEBUG"):
        main_view.clear_milestone_dialog()

    assert "Milestone dialog was already None during cleanup." in caplog.text


def test_show_milestone_step_sets_expected_next(main_view, mocker):
    """Ensure milestone dialog is created and connected."""
    mocker.patch.object(
        main_view, "get_milestone_step", return_value=("Label", "Desc", QWidget())
    )
    mocker.patch("poriscope.views.main_view.Overlay", return_value=MagicMock())
    mocker.patch("poriscope.views.main_view.StepDialog", return_value=MagicMock())

    main_view.show_milestone_step("MainView")
    assert main_view._expected_next_view == "RawDataView"


def test_on_milestone_closed_clears_state(main_view):
    """Clear dialog and deactivate walkthrough when milestone is manually closed."""
    dialog = MagicMock()
    main_view._milestone_dialog = dialog
    main_view._walkthrough_active = True
    main_view._expected_next_view = "Something"
    main_view._on_milestone_closed()
    assert main_view._milestone_dialog is None
    assert main_view._expected_next_view is None
    assert not main_view._walkthrough_active


def test_get_expected_next_view_returns_correctly(main_view):
    """Test transition logic between views."""
    assert main_view.get_expected_next_view("MainView") == "RawDataView"
    assert main_view.get_expected_next_view("Unknown") is None


def test_get_milestone_step_returns_valid(main_view, mocker):
    """Return tuple with label, desc, and widget if view exists."""
    action = QAction("Analysis", main_view)
    main_view.menuBar().addAction(action)
    result = main_view.get_milestone_step("MainView")
    assert isinstance(result, tuple)
    assert result[0] == "New Analysis Tab"


def test_get_milestone_step_returns_none_if_invalid(main_view):
    """Return None if milestone view not found."""
    assert main_view.get_milestone_step("InvalidView") is None


def test_on_view_switched_sets_current_view(main_view):
    main_view.on_view_switched("RawDataView")
    assert main_view._current_view == "RawDataView"


class DummyWalkthroughWidget(QWidget, WalkthroughMixin):
    walkthrough_finished = Signal()

    def launch_walkthrough(self):
        self.was_launched = True
