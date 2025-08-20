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

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log


class IconTextMenuWidget(QWidget):
    rawDataToggled = Signal(bool)
    statsToggled = Signal(bool)
    pluginsToggled = Signal(bool)
    helpToggled = Signal(bool)
    settingsToggled = Signal(bool)
    exitToggled = Signal(bool)
    menuToggled = Signal()

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
        self.setObjectName("iconTextMenuWidget")
        self.setGeometry(QRect(92, 6, 188, 741))
        self.setMaximumSize(QSize(16777215, 741))
        self.setStyleSheet(
            """
            QWidget {
                background-color: white;
                color: black;
                border-radius: 8px;
                padding: 10px;
            }
        """
        )
        self.setupUi()

        self.raw_data_text_button.clicked.connect(self.switchToRawData.emit)
        self.stats_text_button.clicked.connect(self.switchToStatistics.emit)
        self.plugins_text_button.clicked.connect(self.switchToPlugins.emit)
        self.settings_text_button.clicked.connect(self.switchToSettings.emit)
        self.help_text_button.clicked.connect(self.switchToHelp.emit)
        self.exit_text_button.clicked.connect(self.switchToExit.emit)

        # Connect to main view's signal
        main_view.help_window_closed.connect(self.setHelpUnchecked)

    @log(logger=logger)
    def setupUi(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 30, 9, 30)
        layout.setSpacing(10)

        self.menu_button = self.createMenuButton()
        layout.addWidget(self.menu_button, alignment=Qt.AlignLeft)

        layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding))

        logo_layout = QHBoxLayout()
        self.icon_menu_pushButton = self.createLogoButton()
        logo_layout.addStretch()
        logo_layout.addWidget(self.icon_menu_pushButton)
        logo_layout.addStretch()
        layout.addLayout(logo_layout)

        layout.addItem(QSpacerItem(20, 15, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.raw_data_text_button = self.createTextButton(
            layout,
            "raw_data_text_button",
            "    Raw Data",
            os.path.join(self.icon_path, "datapie-black.svg"),
            25,
            "data",
        )
        self.stats_text_button = self.createTextButton(
            layout,
            "stats_text_button",
            "    Event Analysis",
            os.path.join(self.icon_path, "stats-black.svg"),
            25,
            "stats",
        )
        self.plugins_text_button = self.createTextButton(
            layout,
            "plugins_text_button",
            "    Add",
            os.path.join(self.icon_path, "add-black.png"),
            25,
            "add",
        )

        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.help_text_button = self.createTextButton(
            layout,
            "help_text_button",
            "    Help",
            os.path.join(self.icon_path, "help-black.png"),
            25,
            "help",
        )
        self.settings_text_button = self.createTextButton(
            layout,
            "settings_text_button",
            "    Settings",
            os.path.join(self.icon_path, "settings-black.png"),
            25,
            "settings",
        )
        self.exit_text_button = self.createTextButton(
            layout,
            "exit_text_button",
            "     Exit",
            os.path.join(self.icon_path, "exit-black.svg"),
            25,
            "exit",
        )

        layout.addItem(QSpacerItem(20, 5, QSizePolicy.Minimum, QSizePolicy.Expanding))

    @log(logger=logger)
    def createMenuButton(self):
        button = QPushButton(self)
        button.setObjectName("menu_button")
        icon = QIcon()
        icon.addFile(
            os.path.join(self.icon_path, "hamburger-black.svg"),
            QSize(),
            QIcon.Normal,
            QIcon.Off,
        )
        button.setIcon(icon)
        button.setIconSize(QSize(25, 25))
        button.setCheckable(True)
        button.clicked.connect(self.menu_button_clicked)
        button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: rgb(0, 0, 0);
                border-radius: 6px;
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
        """
        )
        return button

    @log(logger=logger)
    def menu_button_clicked(self):
        self.menuToggled.emit()
        QTimer.singleShot(100, self.uncheckMenuButton)
        print("text_menu_button_clicked")
        QTimer.singleShot(100, self.uncheckMenuButton)  # Add delay
        self.logger.info("text_menu_button_clicked")

    @log(logger=logger)
    def createLogoButton(self):
        button = QPushButton(self)
        button.setObjectName("icon_menu_pushButton")
        icon = QIcon(os.path.join(self.icon_path, "TCossaLab-black.png"))
        button.setIcon(icon)
        button.setIconSize(QSize(70, 70))
        button.setCheckable(True)
        button.setFixedWidth(80)
        button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0;
            }
            QPushButton:hover { background-color: rgba(255,255,255,20); }
            QPushButton:pressed { background-color: rgba(255,255,255,40); }
        """
        )

        return button

    @log(logger=logger)
    def createTextButton(
        self, layout, objectName, text, iconPath, iconSize, buttonName
    ):
        button = QPushButton(text, self)
        button.setObjectName(objectName)
        button.setFont(QFont("MS Shell Dlg 2", 10))
        button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border-radius: 8px;
                text-align: left;
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
        """
        )
        icon = QIcon(iconPath)
        button.setIcon(icon)
        button.setIconSize(QSize(iconSize, iconSize))
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.toggled.connect(lambda checked: self.emitSignal(buttonName, checked))

        layout.addWidget(button)
        return button

    @log(logger=logger)
    def emitSignal(self, buttonName, checked):
        signals = {
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
    def setRawDataChecked(self, checked):
        self.raw_data_text_button.setChecked(checked)

    @log(logger=logger)
    def setStatsChecked(self, checked):
        self.stats_text_button.setChecked(checked)

    @log(logger=logger)
    def setPluginsChecked(self, checked):
        self.plugins_text_button.setChecked(checked)

    @log(logger=logger)
    def setHelpChecked(self, checked):
        self.help_text_button.setChecked(checked)

    def setSettingsChecked(self, checked):
        self.settings_text_button.setChecked(checked)

    @log(logger=logger)
    def setLanguageChecked(self, checked):
        self.language_text_button.setChecked(checked)

    @log(logger=logger)
    def setThemeChecked(self, checked):
        self.theme_text_button.setChecked(checked)

    @log(logger=logger)
    def setExitChecked(self, checked):
        self.exit_text_button.setChecked(checked)

    def setHelpUnchecked(self):
        self.help_text_button.setChecked(False)
        self.help_text_button.repaint()
        self.help_text_button.setDown(False)

    @log(logger=logger)
    def uncheckMenuButton(self):
        self.menu_button.setChecked(False)
        self.logger.info("unchecked")
