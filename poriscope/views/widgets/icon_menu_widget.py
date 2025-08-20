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
# Alejandra Carolina González González

import logging
import os

from PySide6.QtCore import QRect, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log


class IconMenuWidget(QWidget):
    rawDataToggled = Signal(bool)
    statsToggled = Signal(bool)
    pluginsToggled = Signal(bool)
    helpToggled = Signal(bool)
    settingsToggled = Signal(bool)
    exitToggled = Signal(bool)
    menuToggled = Signal(bool)

    switchToRawData = Signal()
    switchToStatistics = Signal()

    switchToPlugins = Signal()
    switchToHelp = Signal()
    switchToSettings = Signal()
    switchUser = Signal()
    switchToExit = Signal()

    logger = logging.getLogger(__name__)

    def __init__(self, main_view, parent=None):
        super().__init__(parent)
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "configs", "icons"
        )
        self.setObjectName("iconMenuWidget")
        self.setGeometry(QRect(5, 6, 81, 741))
        self.setMinimumSize(QSize(65, 0))
        self.setMaximumSize(QSize(65, 741))
        self.setStyleSheet(
            """
            QWidget#iconMenuWidget {
                background-color: black;
                border-radius: 8px;
                padding: 10px;
            }
        """
        )
        self.setupUi()
        self.connectSignals()

        # Connect to main view's signal
        main_view.help_window_closed.connect(self.setHelpUnchecked)

    @log(logger=logger)
    def setupUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 30, 9, 30)
        layout.setSpacing(10)

        self.menu_button = self.createMenuButton(layout)

        layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.icon_menu_pushButton = self.createLogoButton(layout)

        layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.raw_data_icon_button = self.createIconButton(
            layout,
            "data",
            os.path.join(self.icon_path, "datapie-white.svg"),
            os.path.join(self.icon_path, "datapie-black.svg"),
            25,
            self.handleRawData,
            "Raw Data",
        )
        self.stats_icon_button = self.createIconButton(
            layout,
            "stats",
            os.path.join(self.icon_path, "stats-white.svg"),
            os.path.join(self.icon_path, "stats-black.svg"),
            25,
            self.handleStats,
            "Event Analysis",
        )
        self.add_icon_button = self.createIconButton(
            layout,
            "add",
            os.path.join(self.icon_path, "add-white.png"),
            os.path.join(self.icon_path, "add-black.png"),
            25,
            self.handlePlugins,
            "All Analysis Tabs",
        )

        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.help_icon_button = self.createIconButton(
            layout,
            "help",
            os.path.join(self.icon_path, "help-white.png"),
            os.path.join(self.icon_path, "help-252.png"),
            25,
            self.handleHelp,
            "Get help",
        )
        self.settings_icon_button = self.createIconButton(
            layout,
            "settings",
            os.path.join(self.icon_path, "settings-white.png"),
            os.path.join(self.icon_path, "settings-black.png"),
            25,
            self.handleSettings,
            "Settings",
        )
        self.exit_icon_button = self.createIconButton(
            layout,
            "exit",
            os.path.join(self.icon_path, "exit-white.svg"),
            os.path.join(self.icon_path, "exit-black.svg"),
            25,
            self.handleExit,
            "Exit application",
        )

        layout.addItem(QSpacerItem(20, 5, QSizePolicy.Minimum, QSizePolicy.Expanding))

    @log(logger=logger)
    def createMenuButton(self, layout):
        button = QPushButton(self)
        button.setObjectName("menu_iconButton")
        icon = QIcon()
        icon.addFile(
            os.path.join(self.icon_path, "hamburger-white.svg"),
            QSize(),
            QIcon.Normal,
            QIcon.Off,
        )
        button.setIcon(icon)
        button.setIconSize(QSize(25, 25))
        button.setCheckable(True)
        button.setAutoExclusive(False)
        button.clicked.connect(self.handleMenu)
        button.toggled.connect(lambda checked: self.emitSignal("menu", checked))
        button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: rgb(255, 255, 255);
                border-radius: 6px;
                border: 1px solid rgb(0, 0, 0);
                padding: 10px;
            }
            QPushButton:hover {
                background-color: rgba(235, 235, 235, 100);
            }
            QToolTip {
                background-color: #ffffff;
                color: #000000;
                padding: 3px;
            }
        """
        )
        button.setToolTip("Menu")
        layout.addWidget(button)
        return button

    @log(logger=logger)
    def createIconButton(
        self, layout, objectName, iconPathOff, iconPathOn, iconSize, handler, tooltip
    ):
        button = QPushButton(self)
        button.setObjectName(f"{objectName}_iconButton")
        # Ensure paths are properly combined into strings
        if isinstance(iconPathOff, tuple):
            iconPathOff = os.path.join(*iconPathOff)
        if isinstance(iconPathOn, tuple):
            iconPathOn = os.path.join(*iconPathOn)

        icon = QIcon()
        icon.addFile(iconPathOff, QSize(), QIcon.Normal, QIcon.Off)
        icon.addFile(iconPathOn, QSize(), QIcon.Normal, QIcon.On)
        button.setIcon(icon)
        button.setIconSize(QSize(iconSize, iconSize))
        button.setCheckable(True)
        button.setAutoExclusive(objectName != "menu")
        button.clicked.connect(handler)
        button.toggled.connect(lambda checked: self.emitSignal(objectName, checked))
        button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: rgb(255, 255, 255);
                border-radius: 6px;
                border: 1px solid rgb(0, 0, 0);
                padding: 10px;
            }
            QPushButton:hover {
                background-color: rgba(235, 235, 235, 100);
            }
            QPushButton:checked {
                background-color: rgb(235, 235, 235);
            }
            QPushButton:pressed {
                background-color: rgb(235, 235, 235);
            }
            QToolTip {
                background-color: #ffffff;
                color: #000000;
                padding: 3px;
            }
        """
        )
        button.setToolTip(tooltip)
        layout.addWidget(button)
        return button

    @log(logger=logger)
    def createLogoButton(self, layout):
        button = QPushButton(self)
        button.setObjectName("icon_menu_pushButton")
        icon = QIcon()
        icon_file = os.path.join(self.icon_path, "tcossalab.png")
        icon.addFile(icon_file, QSize(), QIcon.Normal, QIcon.Off)
        button.setIcon(icon)
        button.setIconSize(QSize(50, 50))
        button.setCheckable(True)
        button.setStyleSheet(
            """
            QPushButton { 
                background-color: transparent; 
                padding: 10px;
            }
            QPushButton:hover { }
            QPushButton:checked { }
            QPushButton:pressed { }
        """
        )
        layout.addWidget(button)
        return button

    @log(logger=logger)
    def connectSignals(self):
        self.raw_data_icon_button.clicked.connect(self.switchToRawData.emit)
        self.stats_icon_button.clicked.connect(self.switchToStatistics.emit)
        self.add_icon_button.clicked.connect(self.switchToPlugins.emit)
        self.settings_icon_button.clicked.connect(self.switchToSettings.emit)
        self.help_icon_button.clicked.connect(self.switchToHelp.emit)
        self.exit_icon_button.clicked.connect(self.switchToExit.emit)

    @log(logger=logger)
    def emitSignal(self, buttonName, checked):
        signals = {
            "menu": self.menuToggled,
            "data": self.rawDataToggled,
            "stats": self.statsToggled,
            "add": self.pluginsToggled,
            "help": self.helpToggled,
            "settings": self.settingsToggled,
            "exit": self.exitToggled,
        }
        if buttonName in signals:
            signals[buttonName].emit(checked)

    @log(logger=logger)
    def handleMenu(self):
        self.logger.info("Menu clicked")

    @log(logger=logger)
    def handleRawData(self):
        self.logger.info("Raw Data clicked")

    @log(logger=logger)
    def handleStats(self):
        self.logger.info("Event Analysis clicked")

    @log(logger=logger)
    def handlePlugins(self):
        self.logger.info("Plugins clicked")

    @log(logger=logger)
    def handleHelp(self):
        self.switchToHelp.emit()

    @log(logger=logger)
    def handleSettings(self):
        self.switchToSettings.emit()

    @log(logger=logger)
    def handleUser(self):
        self.switchUser.emit()
        self.logger.info("User clicked")

    @log(logger=logger)
    def handleLanguage(self):
        self.logger.info("Language settings clicked")

    @log(logger=logger)
    def handleTheme(self):
        self.logger.info("Theme settings clicked")

    @log(logger=logger)
    def handleExit(self):
        self.logger.info("Exit clicked")
        self.switchToExit.emit()
        QApplication.quit()

    # Slot methods to update button states
    @log(logger=logger)
    def setMenuChecked(self, checked):
        self.menu_button.setChecked(checked)

    @log(logger=logger)
    def setRawDataChecked(self, checked):
        self.raw_data_icon_button.setChecked(checked)

    @log(logger=logger)
    def setStatsChecked(self, checked):
        self.stats_icon_button.setChecked(checked)

    @log(logger=logger)
    def setPluginsChecked(self, checked):
        self.add_icon_button.setChecked(checked)

    @log(logger=logger)
    def setHelpChecked(self, checked):
        self.help_icon_button.setChecked(checked)

    @log(logger=logger)
    def setSettingsChecked(self, checked):
        self.settings_icon_button.setChecked(checked)

    @log(logger=logger)
    def setLanguageChecked(self, checked):
        self.language_icon_button.setChecked(checked)

    @log(logger=logger)
    def setThemeChecked(self, checked):
        self.theme_icon_button.setChecked(checked)

    @log(logger=logger)
    def setExitChecked(self, checked):
        self.exit_icon_button.setChecked(checked)

    @log(logger=logger)
    def setHelpUnchecked(self):
        self.help_icon_button.setChecked(False)
        self.help_icon_button.repaint()
        self.help_icon_button.setDown(False)

    @log(logger=logger)
    def uncheckMenuButton(self):
        self.menu_button.setChecked(False)
        self.logger.info("unchecked")
