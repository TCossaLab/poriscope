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
from typing import TYPE_CHECKING, Callable, Optional

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

# This import cannot be made at module level. main_view.py imports both menu
# widgets in order to build the sidebar, so importing MainView back from here
# would close a cycle and fail at startup. TYPE_CHECKING is False at runtime,
# so the block below never executes and costs nothing; type checkers read it
# anyway, which is why the annotation on __init__'s main_view parameter is
# written as the string "MainView" - the name genuinely does not exist once
# the module is running. Do not "clean this up" into a plain import.
if TYPE_CHECKING:
    from poriscope.views.main_view import MainView


class IconMenuWidget(QWidget):
    rawDataToggled = Signal(bool)
    eventAnalysisToggled = Signal(bool)
    metadataToggled = Signal(bool)
    pluginsToggled = Signal(bool)
    helpToggled = Signal(bool)
    settingsToggled = Signal(bool)
    exitToggled = Signal(bool)
    menuToggled = Signal(bool)

    switchToRawData = Signal()
    switchToEventAnalysis = Signal()
    switchToMetadata = Signal()

    switchToPlugins = Signal()
    switchToHelp = Signal()
    switchToSettings = Signal()
    switchToExit = Signal()

    logger = logging.getLogger(__name__)

    def __init__(self, main_view: "MainView", parent: Optional[QWidget] = None) -> None:
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
    def setupUi(self) -> None:
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
        self.event_analysis_icon_button = self.createIconButton(
            layout,
            "event",
            os.path.join(self.icon_path, "stats-white.svg"),
            os.path.join(self.icon_path, "stats-black.svg"),
            25,
            self.handleEventAnalysis,
            "Event Analysis",
        )
        self.metadata_icon_button = self.createIconButton(
            layout,
            "metadata",
            os.path.join(self.icon_path, "database-white.svg"),
            os.path.join(self.icon_path, "database-black.svg"),
            25,
            self.handleMetadata,
            "Metadata",
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
    def createMenuButton(self, layout: QVBoxLayout) -> QPushButton:
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
        self,
        layout: QVBoxLayout,
        objectName: str,
        iconPathOff: str,
        iconPathOn: str,
        iconSize: int,
        handler: Callable[[], None],
        tooltip: str,
    ) -> QPushButton:
        button = QPushButton(self)
        button.setObjectName(f"{objectName}_iconButton")
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
    def createLogoButton(self, layout: QVBoxLayout) -> QPushButton:
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
    def connectSignals(self) -> None:
        self.raw_data_icon_button.clicked.connect(self.switchToRawData.emit)
        self.event_analysis_icon_button.clicked.connect(self.switchToEventAnalysis.emit)
        self.metadata_icon_button.clicked.connect(self.switchToMetadata.emit)
        self.add_icon_button.clicked.connect(self.switchToPlugins.emit)
        self.settings_icon_button.clicked.connect(self.switchToSettings.emit)
        self.help_icon_button.clicked.connect(self.switchToHelp.emit)
        self.exit_icon_button.clicked.connect(self.switchToExit.emit)

    @log(logger=logger)
    def emitSignal(self, buttonName: str, checked: bool) -> None:
        signals = {
            "menu": self.menuToggled,
            "data": self.rawDataToggled,
            "event": self.eventAnalysisToggled,
            "metadata": self.metadataToggled,
            "add": self.pluginsToggled,
            "help": self.helpToggled,
            "settings": self.settingsToggled,
            "exit": self.exitToggled,
        }
        if buttonName in signals:
            signals[buttonName].emit(checked)
        else:
            self.logger.warning(f"emitSignal: unrecognized buttonName {buttonName!r}")

    @log(logger=logger)
    def handleMenu(self) -> None:
        self.logger.info("Menu clicked")

    @log(logger=logger)
    def handleRawData(self) -> None:
        self.logger.info("Raw Data clicked")

    @log(logger=logger)
    def handleEventAnalysis(self) -> None:
        self.logger.info("Event Analysis clicked")

    @log(logger=logger)
    def handleMetadata(self) -> None:
        self.logger.info("Metadata clicked")

    @log(logger=logger)
    def handlePlugins(self) -> None:
        self.logger.info("Plugins clicked")

    @log(logger=logger)
    def handleHelp(self) -> None:
        self.switchToHelp.emit()

    @log(logger=logger)
    def handleSettings(self) -> None:
        self.switchToSettings.emit()

    @log(logger=logger)
    def handleExit(self) -> None:
        self.logger.info("Exit clicked")
        self.switchToExit.emit()
        QApplication.quit()

    # Slot methods to update button states
    @log(logger=logger)
    def setMenuChecked(self, checked: bool) -> None:
        self.menu_button.setChecked(checked)

    @log(logger=logger)
    def setRawDataChecked(self, checked: bool) -> None:
        self.raw_data_icon_button.setChecked(checked)

    @log(logger=logger)
    def setEventAnalysisChecked(self, checked: bool) -> None:
        self.event_analysis_icon_button.setChecked(checked)

    @log(logger=logger)
    def setMetadataChecked(self, checked: bool) -> None:
        self.metadata_icon_button.setChecked(checked)

    @log(logger=logger)
    def setPluginsChecked(self, checked: bool) -> None:
        self.add_icon_button.setChecked(checked)

    @log(logger=logger)
    def setHelpChecked(self, checked: bool) -> None:
        self.help_icon_button.setChecked(checked)

    @log(logger=logger)
    def setSettingsChecked(self, checked: bool) -> None:
        self.settings_icon_button.setChecked(checked)

    @log(logger=logger)
    def setExitChecked(self, checked: bool) -> None:
        self.exit_icon_button.setChecked(checked)

    @log(logger=logger)
    def uncheckAll(self) -> None:
        """
        Uncheck whichever sidebar icon button is currently highlighted, if any.

        These buttons are all ``autoExclusive`` and share this widget as their
        parent, so Qt treats them as one radio-button-style group: a plain
        ``setChecked(False)`` is a no-op on the sole checked member, since Qt
        refuses to leave an autoExclusive group with nothing checked once
        anything has been. Toggling ``autoExclusive`` off just long enough to
        release it is the standard workaround.
        """
        for button in (
            self.raw_data_icon_button,
            self.event_analysis_icon_button,
            self.metadata_icon_button,
            self.add_icon_button,
            self.help_icon_button,
            self.settings_icon_button,
            self.exit_icon_button,
        ):
            if button.isChecked():
                button.setAutoExclusive(False)
                button.setChecked(False)
                button.setAutoExclusive(True)

    @log(logger=logger)
    def setHelpUnchecked(self) -> None:
        self.help_icon_button.setChecked(False)
        self.help_icon_button.repaint()
        self.help_icon_button.setDown(False)

    @log(logger=logger)
    def uncheckMenuButton(self) -> None:
        self.menu_button.setChecked(False)
        self.logger.info("unchecked")
