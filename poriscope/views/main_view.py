# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs
# Alejandra Carolina González González

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from poriscope.constants import __VERSION__
from poriscope.plugins.analysistabs.utils.walkthrough import (
    IntroDialog,
    Overlay,
    StepDialog,
)
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.utils.LogDecorator import log
from poriscope.views.settings_window import SettingsWindow
from poriscope.views.widgets.icon_menu_widget import IconMenuWidget
from poriscope.views.widgets.text_menu_widget import IconTextMenuWidget


class MainView(QMainWindow, WalkthroughMixin):
    # Signals
    rawdata_toggled = Signal()
    instantiate_plugin = Signal(str, str)
    instantiate_analysis_tab = Signal(str)
    help_window_closed = Signal()
    save_session = Signal(str)
    load_session = Signal(object)
    update_logging_level = Signal(int)
    get_shared_data_server = Signal()
    get_user_plugin_location = Signal()
    update_data_server_location = Signal(str)
    update_user_plugin_location = Signal(str)
    clear_cache = Signal()
    kill_all_workers = Signal(str)
    update_thread_status = Signal(int, str, float)
    request_analysis_tabs = Signal()
    received_analysis_tabs = Signal(dict)

    logger = logging.getLogger(__name__)

    # Constructor and Initial Setup
    def __init__(self, available_plugins):
        super().__init__()
        self._init_walkthrough()
        self.setWindowTitle(f"Poriscope {__VERSION__}")
        self.setGeometry(100, 100, 1200, 650)
        self.setMinimumSize(QSize(800, 750))
        self.available_plugins = available_plugins
        self.pages = {}
        self.received_analysis_tabs.connect(self.populate_plugins_menu)
        self.icon_path = Path(Path(__file__).resolve().parent, "configs", "icons")
        self.setup_menubar()
        self._milestone_dialog = None
        self._expected_next_view = None
        self.setup_ui()
        self.figure = plt.Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toggle_in_progress = False
        self.child_windows = []
        self.help_window = None
        self.settings_window = None
        self._analysis_proxy: Optional[QWidget] = None
        self.setup_settings_window_connections()

    # UI Setup Methods
    @log(logger=logger)
    def setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        self.gridLayout = QGridLayout(central_widget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setSpacing(0)

        # Sidebar
        self.icon_menu_container = self.create_container(65, "black")
        self.icon_menu_widget = IconMenuWidget(self)
        self.icon_menu_container.layout().addWidget(self.icon_menu_widget)
        self.gridLayout.addWidget(self.icon_menu_container, 0, 0)

        self.text_menu_container = self.create_container(200, "white")
        self.text_menu_widget = IconTextMenuWidget(self)
        self.text_menu_container.layout().addWidget(self.text_menu_widget)
        self.gridLayout.addWidget(self.text_menu_container, 0, 1)

        # Text Display
        self.text_display_container = self.create_container(300)
        self.text_display_widget = QTextEdit(self)
        self.text_display_widget.setReadOnly(True)
        self.text_display_widget.setStyleSheet(
            """
            QTextEdit {
                background: transparent;
                border: none;
                font: 14px;
                padding: 5px;
                outline: none;
            }
        """
        )
        self.text_display_widget.setPlainText("")

        scroll_area = QScrollArea(self)
        scroll_area.setWidget(self.text_display_widget)
        scroll_area.setWidgetResizable(True)
        self.text_display_container.layout().addWidget(scroll_area)
        self.gridLayout.addWidget(self.text_display_container, 0, 3)

        # Ensure menu is visible
        self.text_menu_container.setVisible(False)
        self.icon_menu_container.setVisible(True)
        self.menuBar().setVisible(True)

        self.setup_stacked_widget(self.gridLayout)
        self.connect_signals()

    # Add custom logic to built-in Qt method resizeEvent -reason why setColumnStretch does not work
    @log(logger=logger)
    def resizeEvent(self, event):
        """
        Ensures that the text display container always takes 20% of the screen width.

        event : QResizeEvent

        The event containing the new and old window sizes. It is automatically created
        and dispatched by Qt's event system whenever a widget (such as a QMainWindow) is resized.
        """
        total_width = self.width()
        text_display_width = int(total_width * 0.2)  # 20% of total width
        self.text_display_container.setFixedWidth(
            text_display_width
        )  # Set width dynamically
        super().resizeEvent(event)  # ensur standard resizing behavior is not broken

    @log(logger=logger)
    @Slot(str, str)
    def add_text_to_display(self, text, source):
        """Method to dynamically add text to the QTextEdit and scroll to bottom"""
        if text:
            self.text_display_widget.append(f"{source}: {text}\n")  # Add new text
            cursor = self.text_display_widget.textCursor()  # Get current text cursor
            cursor.movePosition(
                QTextCursor.MoveOperation.End
            )  # Move cursor to the end of the text
            self.text_display_widget.setTextCursor(cursor)  # Set the cursor position
            self.text_display_widget.ensureCursorVisible()  # Ensure the cursor is visible (scroll down)

    # Signal Connection Setup
    @log(logger=logger)
    def connect_signals(self):
        icon_text_signals = [
            ("rawDataToggled", self.text_menu_widget.setRawDataChecked),
            ("statsToggled", self.text_menu_widget.setStatsChecked),
            ("pluginsToggled", self.text_menu_widget.setPluginsChecked),
            ("helpToggled", self.text_menu_widget.setHelpChecked),
            ("settingsToggled", self.text_menu_widget.setSettingsChecked),
            ("exitToggled", self.text_menu_widget.setExitChecked),
            ("menuToggled", self.toggle_menu_widgets),
        ]

        for signal, slot in icon_text_signals:
            getattr(self.icon_menu_widget, signal).connect(slot)
            getattr(self.text_menu_widget, signal).connect(slot)

        self.text_menu_widget.menuToggled.connect(
            lambda: QTimer.singleShot(100, self.icon_menu_widget.uncheckMenuButton)
        )

        page_switch_signals = [
            ("switchToRawData", self.on_raw_data_view_click),
            ("switchToStatistics", self.on_stats_click),
            ("switchToSettings", self.on_settings_button_click),
            ("switchToHelp", self.on_help_button_click),
            ("switchToPlugins", self.on_plugins_button_click),
        ]
        for signal, page in page_switch_signals:
            if isinstance(page, str):
                getattr(self.text_menu_widget, signal).connect(
                    lambda p=page: self.switch_to_page(p)
                )
                getattr(self.icon_menu_widget, signal).connect(
                    lambda p=page: self.switch_to_page(p)
                )
            else:
                getattr(self.text_menu_widget, signal).connect(page)
                getattr(self.icon_menu_widget, signal).connect(page)

        # Connect help window close event to emit signal
        self.help_window_closed.connect(self.icon_menu_widget.setHelpUnchecked)
        self.help_window_closed.connect(self.text_menu_widget.setHelpUnchecked)

    @log(logger=logger)
    def setup_settings_window_connections(self):
        self.settings_window = SettingsWindow()
        self.settings_window.get_shared_server_location.connect(self.get_data_server)
        self.settings_window.update_data_server_location.connect(
            self.update_data_server
        )
        self.settings_window.get_user_plugin_folder_location.connect(
            self.get_user_plugin_folder
        )
        self.settings_window.update_user_plugin_location.connect(
            self.update_user_plugin_folder
        )
        self.settings_window.update_log_level.connect(self.update_log_level)
        self.settings_window.clear_cache.connect(self.handle_clear_cache)

    # Event Handling Methods
    @log(logger=logger)
    @Slot()
    def handle_clear_cache(self):
        self.clear_cache.emit()

    @log(logger=logger)
    @Slot(int)
    def update_log_level(self, level):
        self.logger.debug("Emitting update_logging_level with new level: %s", level)
        self.update_logging_level.emit(level)

    @log(logger=logger)
    @Slot()
    def get_data_server(self):
        self.get_shared_data_server.emit()

    @log(logger=logger)
    @Slot()
    def get_user_plugin_folder(self):
        self.get_user_plugin_location.emit()

    @log(logger=logger)
    def set_data_server(self, data_server):
        if self.settings_window is not None:
            self.settings_window.set_data_server(data_server)
        else:
            raise AttributeError("Cannot set data server without a settings winddow!")

    @log(logger=logger)
    def set_user_plugin_location(self, user_plugin_loc):
        if self.settings_window is not None:
            self.settings_window.set_user_plugin_location(user_plugin_loc)
        else:
            raise AttributeError(
                "Cannot set user plugin folder without a settings winddow!"
            )

    @log(logger=logger)
    @Slot(str)
    def update_data_server(self, data_server):
        self.update_data_server_location.emit(data_server)

    @log(logger=logger)
    @Slot(str)
    def update_user_plugin_folder(self, user_plugin_loc):
        self.update_user_plugin_location.emit(user_plugin_loc)

    # Menus
    @Slot()
    def toggle_menu_widgets(self):
        if self.toggle_in_progress:
            return
        self.toggle_in_progress = True

        self.icon_menu_container.setVisible(not self.icon_menu_container.isVisible())
        self.text_menu_container.setVisible(not self.text_menu_container.isVisible())

        QTimer.singleShot(300, self.reset_toggle_flag)

    @log(logger=logger)
    def reset_toggle_flag(self):
        self.toggle_in_progress = False

    @log(logger=logger)
    def setup_menubar(self):
        self.menu = self.menuBar()
        file_menu = self.menu.addMenu("File")
        data_menu = self.menu.addMenu("Data")
        analysis_menu = self.menu.addMenu("Analysis")
        help_menu = self.menu.addMenu("Help")

        self.add_menu_action(
            file_menu, "Restore Session", self.on_restore_session_button_click
        )
        self.add_menu_action(
            file_menu, "Save Session", self.on_save_session_button_click
        )
        self.add_menu_action(
            file_menu, "Load Session", self.on_load_session_button_click
        )
        self.add_menu_action(file_menu, "Settings", self.on_settings_button_click)

        self.add_menu_action(help_menu, "Help", self.on_help_button_click)
        self.add_menu_action(help_menu, "Tutorial", self.show_walkthrough_intro)

        data_submenu = data_menu.addMenu("Load Timeseries")
        self.add_plugin_actions(
            data_submenu, "MetaReader", self.on_load_timeseries_button_click
        )

        data_submenu = data_menu.addMenu("Load Events")
        self.add_plugin_actions(
            data_submenu, "MetaEventLoader", self.on_load_events_button_click
        )

        data_submenu = data_menu.addMenu("Load Event Database")
        self.add_plugin_actions(
            data_submenu, "MetaDatabaseLoader", self.on_load_metadata_button_click
        )

        filter_submenu = analysis_menu.addMenu("New Filter")
        self.add_plugin_actions(
            filter_submenu, "MetaFilter", self.on_load_filter_button_click
        )

        writer_submenu = data_menu.addMenu("Load Writer")
        self.add_plugin_actions(
            writer_submenu, "MetaWriter", self.on_load_writer_button_click
        )

        db_writer_submenu = data_menu.addMenu("Load Database Writer")
        self.add_plugin_actions(
            db_writer_submenu, "MetaDatabaseWriter", self.on_load_db_writer_button_click
        )

        analysis_submenu = analysis_menu.addMenu("New Analysis Tab")
        self.add_plugin_actions(
            analysis_submenu, "MetaController", self.on_load_analysis_tab_button_click
        )

        eventfinder_submenu = analysis_menu.addMenu("New Event Finder")
        self.add_plugin_actions(
            eventfinder_submenu,
            "MetaEventFinder",
            self.on_load_eventfinder_button_click,
        )

        eventfitter_submenu = analysis_menu.addMenu("New Event Fitter")
        self.add_plugin_actions(
            eventfitter_submenu,
            "MetaEventFitter",
            self.on_load_eventfitter_button_click,
        )

        self.add_menu_action(
            analysis_menu, "Abort Analysis", self.on_abort_analysis_click
        )

    @log(logger=logger)
    def add_menu_action(self, menu, action_name, slot):
        action = QAction(
            QIcon(os.path.join(self.icon_path, "fire.png")), action_name, self
        )
        action.setStatusTip(action_name)
        action.triggered.connect(slot)
        menu.addAction(action)

    @log(logger=logger)
    def add_plugin_actions(self, menu, plugin_type, slot):
        for name in self.available_plugins[plugin_type]:
            action = QAction(
                QIcon(os.path.join(self.icon_path, "fire.png")), name, self
            )
            action.setStatusTip(f"Load a new {name}")
            action.triggered.connect(
                lambda checked=False, name=name: slot(subclass=name)
            )
            menu.addAction(action)

    # Widgets

    @log(logger=logger)
    def create_container(self, width, color=None):
        container = QWidget()
        if color is not None:
            container.setStyleSheet(f"background-color: {color}; border-radius: 8px;")
        container.setFixedWidth(width)
        container.setLayout(QVBoxLayout())
        container.layout().setContentsMargins(0, 0, 0, 0)
        return container

    # Button Actions
    @log(logger=logger)
    def on_help_button_click(self):
        if self.help_window is None:
            from poriscope.views.help import HelpCentre

            self.help_window = HelpCentre()
            self.help_window.show()
            self.help_window.closeEvent = self.on_help_window_closed

    @log(logger=logger)
    def on_help_window_closed(self, event):
        self.help_window = None
        self.help_window_closed.emit()
        event.accept()

    @log(logger=logger)
    def on_load_timeseries_button_click(self, subclass):
        self.logger.info(f"Loading timeseries for subclass: {subclass}")
        self.instantiate_plugin.emit("MetaReader", subclass)
        # self.instantiate_analysis_tab.emit(subclass)

    @log(logger=logger)
    def on_load_events_button_click(self, subclass):
        self.logger.info(f"Loading events for subclass: {subclass}")
        self.instantiate_plugin.emit("MetaEventLoader", subclass)
        # self.instantiate_analysis_tab.emit(subclass)

    @log(logger=logger)
    def on_load_metadata_button_click(self, subclass):
        self.logger.info(f"Loading events for subclass: {subclass}")
        self.instantiate_plugin.emit("MetaDatabaseLoader", subclass)
        # self.instantiate_analysis_tab.emit(subclass)

    @log(logger=logger)
    def on_load_eventfinder_button_click(self, subclass):
        self.logger.info("Loading eventfinder")
        self.instantiate_plugin.emit("MetaEventFinder", subclass)

    @log(logger=logger)
    def on_load_eventfitter_button_click(self, subclass):
        self.logger.info("Loading eventfitter")
        self.instantiate_plugin.emit("MetaEventFitter", subclass)

    @log(logger=logger)
    def on_save_session_button_click(self):
        save_file = self.get_save_file_name()
        if save_file is not None:
            self.save_session.emit(save_file)

    @log(logger=logger)
    def on_load_session_button_click(self):
        starting_loc = ""
        file_path = None
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", starting_loc, "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.load_session.emit(file_path)

    @log(logger=logger)
    def on_restore_session_button_click(self):
        self.load_session.emit(None)

    @log(logger=logger)
    def on_load_filter_button_click(self, subclass):
        self.logger.info("Loading filter {subclass}")
        self.instantiate_plugin.emit("MetaFilter", subclass)

    @log(logger=logger)
    def on_raw_data_view_click(self):
        self.on_load_analysis_tab_button_click("RawDataController")
        self.switch_to_page("RawDataView")

    @log(logger=logger)
    def on_stats_click(self):
        self.on_load_analysis_tab_button_click("EventAnalysisController")
        self.switch_to_page("EventAnalysisView")

    @log(logger=logger)
    def on_plugins_button_click(self):
        """Emit signal to request analysis tabs from MainController."""
        self.logger.info("Plugins button clicked - requesting analysis tabs.")
        self.request_analysis_tabs.emit()  # Ask MainController for the list of instantiated tabs
        self.logger.info("request_analysis_tabs signal emitted.")

    @log(logger=logger)
    def populate_plugins_menu(self, analysis_tabs):
        """Dynamically generates a dropdown menu when MainController responds."""
        self.logger.info(
            f"populate_plugins_menu called with {len(analysis_tabs)} analysis tabs."
        )

        menu = QMenu(self)

        if not analysis_tabs:
            self.logger.warning("No analysis tabs available.")
            no_tabs_action = QAction("No analysis tabs available", self)
            no_tabs_action.setEnabled(False)
            menu.addAction(no_tabs_action)
        else:
            for subclass, tab_instance in analysis_tabs.items():
                view_name = (
                    tab_instance.view.__class__.__name__
                )  # Get corresponding view name
                self.logger.debug(
                    f"Adding analysis tab to menu: {subclass} -> {view_name}"
                )

                action = QAction(subclass, self)
                action.triggered.connect(
                    lambda checked=False, p=view_name: self.handle_menu_click(p)
                )
                menu.addAction(action)

        button = self.sender()
        if button:
            menu_pos = button.mapToGlobal(
                button.rect().topLeft()
            )  # Start from the top left of the button
            horizontal_shift = 10  # Shift the menu to the right by 10 pixels
            menu_pos.setX(menu_pos.x() + horizontal_shift)  # Apply the horizontal shift

            vertical_shift = (
                button.rect().height() // 2
            )  # Adjust vertically to align with the middle of the button
            menu_height = (
                menu.sizeHint().height()
            )  # Get menu's height for further adjustments
            menu_pos.setY(
                menu_pos.y() + vertical_shift - (menu_height // 2)
            )  # Center the menu vertically relative to the button

            menu.exec(menu_pos)

    @log(logger=logger)
    def handle_menu_click(self, page_name):
        """Handles clicks on the menu items and switches to the correct view page."""
        self.logger.info(f"Menu item clicked: {page_name}")
        self.switch_to_page(page_name)

    @log(logger=logger)
    def on_settings_button_click(self):
        self.add_page("Settings", self.settings_window)
        self.switch_to_page("Settings")
        self.logger.info("Settings button pressed")

    @log(logger=logger)
    def on_load_writer_button_click(self, subclass):
        self.instantiate_plugin.emit("MetaWriter", subclass)

    @log(logger=logger)
    def on_load_db_writer_button_click(self, subclass):
        self.instantiate_plugin.emit("MetaDatabaseWriter", subclass)

    @log(logger=logger)
    def on_load_analysis_tab_button_click(self, subclass):
        self.instantiate_analysis_tab.emit(subclass)

    # Page management
    @log(logger=logger)
    def setup_stacked_widget(self, gridLayout):
        combined_widgets_frame = QFrame()
        combined_widgets_frame.setMinimumWidth(300)
        gridLayout.addWidget(combined_widgets_frame, 0, 2)

        combined_layout = QVBoxLayout(combined_widgets_frame)
        combined_layout.setContentsMargins(0, 0, 0, 0)
        combined_layout.setSpacing(0)

        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.stacked_widget_frame = QFrame()
        stacked_widget_layout = QVBoxLayout(self.stacked_widget_frame)
        # self.stacked_widget_frame.setStyleSheet("background-color: red;")
        stacked_widget_layout.setContentsMargins(10, 0, 10, 10)

        self.stackedWidget = QStackedWidget()
        stacked_widget_layout.addWidget(self.stackedWidget)
        stacked_widget_layout.setSpacing(0)

        self.page_title_label = QLabel("Home", self)
        self.page_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_title_label.setStyleSheet(
            """
            font-weight: bold;
            font-size: 12px;
            margin: 0px;
            padding: 0px;
        """
        )
        self.page_title_label.setFixedHeight(20)
        self.page_title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        container_layout.addWidget(self.page_title_label)

        container_layout.addWidget(self.stacked_widget_frame)
        combined_layout.addWidget(container_widget)

        # Ensure an initial valid page
        default_page = QLabel("", self)
        default_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_page("MainView", default_page)

        self.switch_to_page("MainView")

    @log(logger=logger)
    def add_page(self, page_name, widget_instance):
        page = QWidget()
        page.setObjectName(page_name)
        page_layout = QVBoxLayout(page)
        page.setLayout(page_layout)
        page.layout().setContentsMargins(0, 0, 0, 0)
        page.layout().addWidget(widget_instance)

        self.pages[page_name] = {
            "index": self.stackedWidget.addWidget(page),
            "widget": widget_instance,
        }
        self.switch_to_page(page_name)  # Switch to the newly added page
        self.logger.info(f"Leaving addPage for '{page_name}'")

    @log(logger=logger)
    def switch_to_page(self, page_name):
        """Switch to a different view while enforcing walkthrough and milestone constraints."""

        # Block switching if walkthrough is active and this is not the expected next step
        if getattr(self, "_walkthrough_active", False):
            if self._expected_next_view and page_name == self._expected_next_view:
                self.logger.info(
                    f"Walkthrough is active and switching to expected view: {page_name}"
                )
            else:
                self.logger.info(
                    f"Walkthrough is active. Page switch to '{page_name}' blocked."
                )
                return

        # Handle milestone enforcement
        if self._milestone_dialog is not None:
            if self._expected_next_view != page_name:
                self.logger.info(
                    f"Milestone active. Cannot switch to '{page_name}' (expected: '{self._expected_next_view}')."
                )
                return
            else:
                self.logger.info(f"Switching to expected milestone target: {page_name}")
                # Clean up milestone overlay if it exists
                try:
                    if (
                        hasattr(self._milestone_dialog, "overlay")
                        and self._milestone_dialog.overlay
                    ):
                        self._milestone_dialog.overlay.close()
                        self._milestone_dialog.overlay.deleteLater()
                except Exception as e:
                    self.logger.debug(f"Overlay cleanup error: {e}")

                # Clean up milestone dialog itself
                try:
                    self._milestone_dialog.close()
                    self._milestone_dialog.deleteLater()
                except Exception as e:
                    self.logger.debug(f"Milestone dialog cleanup error: {e}")

                self._milestone_dialog = None

                # Clean up any analysis highlight
                if (
                    hasattr(self, "_analysis_proxy")
                    and self._analysis_proxy is not None
                ):
                    self._analysis_proxy.hide()
                    self._analysis_proxy.deleteLater()
                    self._analysis_proxy = None

                self._expected_next_view = None

                # Delay walkthrough until after switch
                QTimer.singleShot(100, self.launch_walkthrough_if_needed)

        # Final page switch logic
        if page_name in self.pages:
            page_info = self.pages[page_name]
            self.stackedWidget.setCurrentIndex(page_info["index"])
            self.page_title_label.setText(page_name)
            self.logger.info(f"Switched to page: {page_name}")
        else:
            self.logger.warning(
                f"Attempted to switch to non-existent page: {page_name}"
            )

    @log(logger=logger)
    def on_abort_analysis_click(self):
        self.logger.info("Aborting Analysis")
        self.kill_all_workers.emit("RawDataController")

    @log(logger=logger)
    def closeEvent(self, event):
        # Close the help window if it is open
        if self.help_window is not None:
            self.help_window.close()

        # Call the base class implementation
        super().closeEvent(event)

    def get_save_file_name(
        self,
        starting_file_path="",
        title="Save Session",
        file_types="JSON Files (*.json);;All Files (*)",
    ):
        file_name, _ = QFileDialog.getSaveFileName(
            self, title, starting_file_path, file_types
        )
        return file_name

    @log(logger=logger)
    def display_data(self, data):
        self.rawDataWidget.display_data(data)

    @log(logger=logger)
    def on_file_loaded(self):
        pass

    def get_analysis_highlight(self) -> QWidget:
        if not hasattr(self, "analysis_action_ref"):
            self.analysis_action_ref = next(
                (a for a in self.menuBar().actions() if a.text() == "Analysis"), None
            )

        if not self.analysis_action_ref:
            return self.menuBar()

        rect = self.menuBar().actionGeometry(self.analysis_action_ref)
        local_pos = self.mapFromGlobal(self.menuBar().mapToGlobal(rect.topLeft()))

        self._analysis_proxy = QWidget(self)
        self._analysis_proxy.setGeometry(QRect(local_pos, rect.size()))
        self._analysis_proxy.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._analysis_proxy.setStyleSheet("background: rgba(0,0,0,0);")
        self._analysis_proxy.show()
        return self._analysis_proxy

    def get_walkthrough_steps(self):
        current_view = self.page_title_label.text()
        if current_view in self.pages:
            view_widget = self.pages[current_view]["widget"]
            if isinstance(view_widget, WalkthroughMixin):
                return view_widget.get_walkthrough_steps()
        return []

    def get_intro_text(self, view_name):
        step_mapping = {
            "MainView": "Welcome aboard! You're on the landing page. This tutorial will walk you through the whole process of Nanopore's Data Analysis.",
            "RawDataView": "You are currently in the Raw Data Tab. Here, you can load your data and perform baseline analysis to find events.",
            "EventAnalysisView": "You're in the Event Analysis Tab. This section allows you to view, evaluate and fit your events before saving them.",
            "MetadataView": "This is the Metadata Tab. Here, you can analyze your fitted data through different plot types and filters.",
            "ClusteringView": "You're currently in the Clustering Tab. Here you can group related events based on feature similarities to discover patterns and trace molecule backs.",
        }
        return step_mapping.get(view_name, "You're starting a guided tutorial.")

    def show_walkthrough_intro(self):
        if self._walkthrough_active:
            self.logger.info("Walkthrough is already active, skipping intro.")
            return  # Exit if the walkthrough is already active

        current_view = self.get_current_view()
        intro = IntroDialog(self, current_step=current_view)
        intro.start_walkthrough.connect(lambda: self._on_intro_finished(current_view))
        intro.exec()

    def _on_intro_finished(self, view_name):
        """
        Handle logic after the intro dialog is closed.
        """
        if view_name == "MainView":
            # Exceptionally show the first milestone
            self.logger.info("Intro finished on MainView — showing first milestone.")
            self.show_milestone_step("MainView")
        else:
            self.logger.info(
                f"Intro finished on {view_name} — launching walkthrough immediately."
            )
            self.launch_walkthrough_if_needed()

    def launch_walkthrough_if_needed(self):
        """Helper method to check the current view and launch walkthrough if eligible."""
        current_view = self.get_current_view()  # Get the current view dynamically

        # Dynamically check if the current view has the walkthrough feature
        if current_view in self.pages:
            view_widget = self.pages[current_view]["widget"]

            # Check if the current view widget is a subclass of WalkthroughMixin
            if isinstance(view_widget, WalkthroughMixin):
                if not self._walkthrough_active:
                    self.logger.info(f"Launching walkthrough for {current_view}.")
                    self._walkthrough_active = True
                    self._walkthrough_origin = current_view
                    view_widget.walkthrough_finished.connect(
                        self._reset_walkthrough_flag
                    )
                    view_widget.launch_walkthrough()
                else:
                    self.logger.info(
                        "Walkthrough already active. Ignoring new request."
                    )
            else:
                self.logger.info(
                    f"Current view {current_view} does not support walkthrough."
                )
        elif current_view != "MainView":
            self.logger.info(
                f"Current view {current_view} does not support walkthrough."
            )

    def get_current_view(self):
        return self.page_title_label.text()

    def _reset_walkthrough_flag(self, view_name, completed_successfully: bool):
        self.logger.info(
            f"Walkthrough finished for {view_name}, completed: {completed_successfully}"
        )
        self._walkthrough_active = False

        if completed_successfully:
            self.show_milestone_step(view_name)

    def on_view_switched(self, view_name):
        self._current_view = view_name

    def clear_milestone_dialog(self):
        """Safely clear the milestone dialog and its overlay."""
        dialog = self._milestone_dialog
        self._milestone_dialog = None  # Set to None first to avoid re-cleanup

        if dialog:
            try:
                if hasattr(dialog, "overlay") and dialog.overlay:
                    overlay = dialog.overlay
                    dialog.overlay = None  # Prevent re-cleanup
                    overlay.close()
                    overlay.deleteLater()
            except Exception as e:
                self.logger.debug(f"Overlay cleanup error: {e}")

            try:
                dialog.close()
                dialog.deleteLater()
            except Exception as e:
                self.logger.debug(f"Milestone dialog cleanup error: {e}")
        else:
            self.logger.debug("Milestone dialog was already None during cleanup.")

    def show_milestone_step(self, previous_view):
        """Show milestone StepDialog after a walkthrough finishes."""
        self.clear_milestone_dialog()
        milestone = self.get_milestone_step(previous_view)

        if milestone:
            label, desc, widget = milestone
            overlay = Overlay(self)
            overlay.show()

            self._milestone_dialog = StepDialog(
                self, steps=[(label, desc, widget)], overlay=overlay
            )

            def delayed_show():
                # self._reposition_step_dialog(self._milestone_dialog, [widget])
                if self._milestone_dialog is not None:
                    self._milestone_dialog.show()

            QTimer.singleShot(0, delayed_show)  # Delay .show() to next event loop

            self._milestone_dialog.finished.connect(self._on_milestone_closed)
            self._expected_next_view = self.get_expected_next_view(previous_view)
            self.logger.debug(
                f"Milestone shown for {previous_view}, expecting {self._expected_next_view} next"
            )

    @Slot()
    def _on_milestone_closed(self):
        """Called when the milestone dialog is closed manually (e.g., via 'Done' or 'X')."""
        self.logger.info("Milestone manually closed by user (X or Done clicked).")

        self.clear_milestone_dialog()
        self._expected_next_view = None
        self._walkthrough_active = False

    def get_expected_next_view(self, previous_view):
        expected_transitions = {
            "MainView": "RawDataView",
            "RawDataView": "EventAnalysisView",
            "EventAnalysisView": "MetadataView",
            "MetadataView": "ClusteringView",
        }
        return expected_transitions.get(previous_view)

    def get_milestone_step(self, view_name):
        """Return the label, description, and highlight widget for the given view."""

        milestone_map = {
            "MainView": (
                "New Analysis Tab",
                "Click on 'Analysis' → 'New Analysis Tab' → 'RawDataController' to continue.",
                lambda: [self.get_analysis_highlight()],
            ),
            "RawDataView": (
                "Ready to analyze your events ?",
                "Click on 'Analysis' → 'New Analysis Tab' → 'EventAnalysisController' to continue.",
                lambda: [self.get_analysis_highlight()],
            ),
            "EventAnalysisView": (
                "Let's proceed to visualize your data !",
                "Click on 'Analysis' → 'New Analysis Tab' → 'MetadataController' to continue.",
                lambda: [self.get_analysis_highlight()],
            ),
            "MetadataView": (
                "Now, let's cluster!",
                "Click on 'Analysis' → 'New Analysis Tab' → 'ClusteringController' to continue.",
                lambda: [self.get_analysis_highlight()],
            ),
        }

        step = milestone_map.get(view_name)
        if step:
            label, desc, widget_lambda = step
            return label, desc, widget_lambda()[0]

        return None


# If the widget needs to be run standalone for testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    available_plugins: Dict[str, List[Optional[str]]] = {
        "MetaFilter": [],
        "MetaEventFinder": [],
        "MetaWriter": [],
    }
    main_view = MainView(available_plugins)
    main_view.show()
    sys.exit(app.exec())
