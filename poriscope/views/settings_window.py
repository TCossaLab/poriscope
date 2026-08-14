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

from PySide6.QtCore import QCoreApplication, QMetaObject, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleFactory,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from poriscope.configs.utils import get_themed_icon_path, is_dark_mode
from poriscope.constants import __VERSION__
from poriscope.utils.LogDecorator import log


class _NoFocusRectDelegate(QStyledItemDelegate):
    """
    Item delegate that strips the State_HasFocus flag before painting.

    QComboBox popups paint a focus rectangle around the current-index
    item using QStyle::State_HasFocus, independent of the view's actual
    keyboard focus state and immune to stylesheet :focus rules. This is
    baked into native/Fusion style painting itself, so the only reliable
    way to suppress it is to clear the flag before delegating to the
    normal paint logic.
    """

    def paint(self, painter, option, index):
        option.state &= ~QStyle.StateFlag.State_HasFocus
        super().paint(painter, option, index)


class Theme:
    """
    Resolved color palette for the current OS light/dark mode.

    Centralizing these means every widget factory method below reads
    from one place, so a future palette tweak (or a live theme-switch
    feature) only has to change this class instead of every stylesheet
    string scattered through the file.
    """

    def __init__(self, dark: bool):
        self.dark = dark
        if dark:
            self.bg = "#1E1E1E"
            self.surface = "#2B2B2B"
            self.border = "#444444"
            self.text = "#E8E8E8"
            self.text_secondary = "#A0A0A0"
            self.hover = "#3A3A3A"
            self.selected_bg = "#264F78"
            self.selected_text = "#8AB4F8"
            self.divider = "#3A3A3A"
            self.tab_selected = "#FFFFFF"
        else:
            self.bg = "#FFFFFF"
            self.surface = "#FFFFFF"
            self.border = "#D0D0D0"
            self.text = "#333333"
            self.text_secondary = "#666666"
            self.hover = "#F0F0F0"
            self.selected_bg = "#E8F0FE"
            self.selected_text = "#1A73E8"
            self.divider = "#A0A0A0"
            self.tab_selected = "#000000"


class SettingsWindow(QWidget):
    logger = logging.getLogger(__name__)
    update_data_server_location = Signal(str)
    update_user_plugin_location = Signal(str)
    get_shared_server_location = Signal()
    get_user_plugin_folder_location = Signal()
    update_log_level = Signal(int)
    clear_cache = Signal()

    def __init__(self):
        super().__init__()
        self.theme = Theme(is_dark_mode())
        # Values are populated externally via set_data_server() /
        # set_user_plugin_location(); default to "" so the folder-picker
        # dialogs below never crash on an unset attribute before that
        # happens.
        self.data_server = ""
        self.user_plugin_location = ""
        self._current_tab_index = 0
        self.setupUi()

        # Stylesheets are static strings baked in at build time, so they
        # don't react to the OS theme changing mid-session on their own
        # (and switching tabs doesn't help either -- QTabWidget just
        # shows/hides already-built widgets, it doesn't rebuild them).
        # Re-check on every palette change and rebuild if the resolved
        # theme actually flipped.
        app = QApplication.instance()
        if app is not None:
            app.paletteChanged.connect(self._on_palette_changed)

    @log(logger=logger)
    def _on_palette_changed(self, _palette=None):
        new_dark = is_dark_mode()
        if new_dark == self.theme.dark:
            return
        self.logger.info(f"OS theme changed (dark={new_dark}); rebuilding Settings UI")
        self.theme = Theme(new_dark)
        self._current_tab_index = self.tabWidget.currentIndex()
        self._clear_layout(self.layout())
        self.setupUi()

    @staticmethod
    def _clear_layout(layout):
        """Recursively delete every widget/sub-layout from a layout so it
        can be rebuilt from scratch, rather than erroring on a second
        QVBoxLayout(self) call while one is already installed."""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                child_layout = item.layout()
                if child_layout is not None:
                    SettingsWindow._clear_layout(child_layout)

    @log(logger=logger)
    def setupUi(self):
        self.setObjectName("Form")
        self.resize(915, 900)
        # Only cascade text color here, not background. The original
        # design intentionally left the window background unset so it
        # inherits the native system palette -- the same grey MainView's
        # chrome uses -- rather than forcing a stark white card. Only
        # the interactive controls (combobox, line edit, buttons, list
        # widget) get an explicit surface color below, for contrast
        # against that background.
        self.setStyleSheet(
            f"""
            QWidget {{
                color: {self.theme.text};
            }}
            QToolTip {{
                background-color: #2B2B2B;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px 9px;
            }}
            """
        )

        main_layout = self.layout() or QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.settingsLabel = self.create_label(self, "Settings", 24, bold=True)
        main_layout.addWidget(self.settingsLabel, alignment=Qt.AlignLeft)

        self.tabWidget = QTabWidget(self)
        self.tabWidget.setFont(QFont("", -1, QFont.Bold))
        self.tabWidget.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
                margin: 10px;
            }}
            QTabBar::tab {{
                padding: 10px;
                margin: 0px;
                border: none;
                border-bottom: 2px solid {self.theme.border};
                font-size: 16px;
                font-family: Arial, Helvetica, sans-serif;
                color: {self.theme.text};
                background: transparent;
            }}
            QTabBar::tab:selected {{
                border-bottom: 2px solid {self.theme.tab_selected};
                font-weight: bold;
            }}
            QTabBar::tab:hover {{
                border-bottom: 2px solid {self.theme.tab_selected};
                font-weight: bold;
            }}
            """
        )
        main_layout.addWidget(self.tabWidget)

        self.tab_general = self.create_tab(self.tabWidget, "General")
        self.generalVerticalLayout = QVBoxLayout(self.tab_general)
        self.add_general_tab_contents(self.tab_general, self.generalVerticalLayout)

        self.tab_advancedSettings = self.create_tab(self.tabWidget, "Advanced Settings")
        self.advancedSettingsVerticalLayout = QVBoxLayout(self.tab_advancedSettings)
        self.add_advanced_settings_tab_contents(
            self.tab_advancedSettings, self.advancedSettingsVerticalLayout
        )

        self.tab_about = self.create_tab(self.tabWidget, "About")
        self.aboutVerticalLayout = QVBoxLayout(self.tab_about)
        self.add_about_tab_contents(self.tab_about, self.aboutVerticalLayout)

        self.retranslateUi()
        self.tabWidget.setCurrentIndex(self._current_tab_index)
        QMetaObject.connectSlotsByName(self)

    # ------------------------------------------------------------------
    # Widget factories
    # ------------------------------------------------------------------

    @log(logger=logger)
    def create_label(self, parent, text, font_size, bold=False):
        label = QLabel(parent)
        label.setText(QCoreApplication.translate("Form", text, None))
        font = QFont()
        font.setPointSize(font_size)
        font.setBold(bold)
        label.setFont(font)
        label.setStyleSheet(f"color: {self.theme.text}; background: transparent;")
        return label

    @log(logger=logger)
    def create_tab(self, tabWidget, tab_name):
        tab = QWidget()
        tabWidget.addTab(tab, QCoreApplication.translate("Form", tab_name, None))
        return tab

    @log(logger=logger)
    def create_combo_box(self, parent, items, max_width=None):
        comboBox = QComboBox(parent)
        for item in items:
            comboBox.addItem(QCoreApplication.translate("Form", item, None))

        if max_width:
            comboBox.setMaximumWidth(max_width)
        comboBox.setMinimumWidth(200)

        arrow_path = get_themed_icon_path("arrowdown-black.png")
        if arrow_path:
            arrow_path = arrow_path.replace("\\", "/")

        comboBox.setStyleSheet(
            f"""
            QComboBox {{
                border: 1px solid {self.theme.border};
                border-radius: 6px;
                padding: 5px 10px;
                background: {self.theme.surface};
                color: {self.theme.text};
                min-height: 28px;
            }}
            QComboBox:disabled {{
                color: {self.theme.text_secondary};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_path}");
                width: 12px;
                height: 12px;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                border: 1px solid {self.theme.border};
                background: {self.theme.surface};
                color: {self.theme.text};
                padding: 4px;
                outline: 0px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 6px 10px;
                min-height: 22px;
                border-radius: 4px;
                border: none;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: {self.theme.hover};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: {self.theme.selected_bg};
                color: {self.theme.selected_text};
            }}
            QComboBox QAbstractItemView::item:selected:hover {{
                background: {self.theme.selected_bg};
                color: {self.theme.selected_text};
            }}
            """
        )

        # The popup list needs Fusion so hover/selected colors above are
        # actually respected -- native Windows-style popups ignore parts
        # of the stylesheet. The custom delegate then strips the
        # State_HasFocus flag Qt paints on the current-index item, which
        # otherwise shows as a boxed outline no stylesheet rule can
        # suppress.
        comboBox.view().setStyle(QStyleFactory.create("Fusion"))
        comboBox.setItemDelegate(_NoFocusRectDelegate(comboBox))

        return comboBox

    @log(logger=logger)
    def create_checkable_list_widget(self, parent, items):
        listWidget = QListWidget(parent)
        for item in items:
            list_item = QListWidgetItem(QCoreApplication.translate("Form", item, None))
            list_item.setFlags(list_item.flags() | Qt.ItemIsUserCheckable)
            list_item.setCheckState(Qt.Unchecked)
            listWidget.addItem(list_item)

        listWidget.setStyleSheet(
            f"""
            QListWidget {{
                border: 1px solid {self.theme.border};
                border-radius: 10px;
                padding: 5px 10px;
                background: {self.theme.surface};
                color: {self.theme.text};
                min-height: 30px;
                min-width: 200px;
            }}
            QListWidget::item {{
                padding: 5px 10px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background: {self.theme.hover};
            }}
            QListWidget::item:selected {{
                background: {self.theme.selected_bg};
                color: {self.theme.selected_text};
            }}
            QListWidget::item:selected:hover {{
                background: {self.theme.selected_bg};
                color: {self.theme.selected_text};
            }}
            """
        )
        return listWidget

    @log(logger=logger)
    def create_check_box(self, parent):
        checkBox = QCheckBox(parent)
        checkBox.setStyleSheet(
            """
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
            }
            """
        )
        return checkBox

    @log(logger=logger)
    def create_line_edit(self, parent, max_width=None):
        lineEdit = QLineEdit(parent)
        if max_width:
            lineEdit.setMaximumWidth(max_width)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHeightForWidth(lineEdit.sizePolicy().hasHeightForWidth())
        lineEdit.setSizePolicy(sizePolicy)
        lineEdit.setStyleSheet(
            f"""
            QLineEdit {{
                border: 1px solid {self.theme.border};
                border-radius: 6px;
                padding: 5px 10px;
                background: {self.theme.surface};
                color: {self.theme.text};
                min-height: 28px;
                min-width: 200px;
            }}
            """
        )
        return lineEdit

    @log(logger=logger)
    def create_push_button(
        self,
        parent,
        text,
        background_color,
        text_color,
        max_width=None,
        border_color=None,
    ):
        pushButton = QPushButton(parent)
        pushButton.setText(QCoreApplication.translate("Form", text, None))
        if max_width:
            pushButton.setMaximumWidth(max_width)
        pushButton.setCursor(Qt.PointingHandCursor)
        border_rule = f"1px solid {border_color}" if border_color else "none"
        pushButton.setStyleSheet(
            f"""
            QPushButton {{
                background: {background_color};
                color: {text_color};
                border: {border_rule};
                border-radius: 6px;
                padding: 5px 15px;
                min-width: 100px;
                min-height: 30px;
            }}
            QPushButton:hover {{
                background: {self.theme.hover if self.theme.dark else "#333333"};
                color: {self.theme.text if self.theme.dark else "#FFFFFF"};
                border: {border_rule};
            }}
            QPushButton:pressed {{
                background: #999999;
                color: #FFFFFF;
                border: {border_rule};
            }}
            """
        )
        return pushButton

    @log(logger=logger)
    def create_secondary_button(self, parent, text, max_width=None):
        """
        Folder-picker action button (Change Data Server Location / Change
        User Plugin Location).

        Light mode: solid black, inverting to white on hover.
        Dark mode: the theme's surface/border styling, unchanged.

        Styled directly rather than through create_push_button since the
        hover behavior (invert, not darken) differs from every other
        button in this window. The border color and width stay identical
        across normal/hover/pressed states in both branches -- a mismatch
        there is what caused a stale black repaint artifact to linger
        after the cursor left the button.
        """
        pushButton = QPushButton(parent)
        pushButton.setText(QCoreApplication.translate("Form", text, None))
        if max_width:
            pushButton.setMaximumWidth(max_width)
        pushButton.setCursor(Qt.PointingHandCursor)

        if self.theme.dark:
            pushButton.setStyleSheet(
                f"""
                QPushButton {{
                    background: {self.theme.surface};
                    color: {self.theme.text};
                    border: 1px solid #777777;
                    border-radius: 6px;
                    padding: 5px 15px;
                    min-width: 100px;
                    min-height: 30px;
                }}
                QPushButton:hover {{
                    background: {self.theme.hover};
                    color: {self.theme.text};
                    border: 1px solid #777777;
                }}
                QPushButton:pressed {{
                    background: #444444;
                    color: {self.theme.text};
                    border: 1px solid #777777;
                }}
                """
            )
        else:
            pushButton.setStyleSheet(
                """
                QPushButton {
                    background: #000000;
                    color: #FFFFFF;
                    border: 1px solid #000000;
                    border-radius: 6px;
                    padding: 5px 15px;
                    min-width: 100px;
                    min-height: 30px;
                }
                QPushButton:hover {
                    background: #FFFFFF;
                    color: #000000;
                    border: 1px solid #000000;
                }
                QPushButton:pressed {
                    background: #DDDDDD;
                    color: #000000;
                    border: 1px solid #000000;
                }
                """
            )

        return pushButton

    @log(logger=logger)
    def create_section_layout(self, widget):
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.addWidget(widget)
        return container

    def add_horizontal_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(
            f"min-height: 1px; max-height: 1px; background-color: {self.theme.divider}; border: none;"
        )
        return line

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    @log(logger=logger)
    def add_general_tab_contents(self, parent_widget, layout):
        layout.setSpacing(0)

        general_label = self.create_label(parent_widget, "General", 14)
        description_label = self.create_label(
            parent_widget,
            "Configure the overall preferences for your application experience",
            10,
        )
        general_layout = QVBoxLayout()
        general_layout.addWidget(general_label)
        general_layout.addWidget(description_label)
        general_widget = QWidget()
        general_widget.setLayout(general_layout)
        layout.addWidget(self.create_section_layout(general_widget))

        layout_language = QHBoxLayout()
        layout_language.addWidget(self.create_label(parent_widget, "Language", 10))
        layout_language.addWidget(
            self.create_combo_box(
                parent_widget, ["English"], max_width=self.width() // 3
            ),
            alignment=Qt.AlignLeft,
        )
        language_widget = QWidget()
        language_widget.setLayout(layout_language)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(language_widget))

        self.update_data_server_button = self.create_secondary_button(
            parent_widget, "Change Data Server Location"
        )
        self.update_data_server_button.setToolTip("Select a folder")
        self.update_data_server_button.clicked.connect(self.update_data_server)

        layout_dataServerLocation = QHBoxLayout()
        layout_dataServerLocation.addWidget(
            self.create_label(parent_widget, "Set Data Server", 10)
        )
        layout_dataServerLocation.addWidget(self.update_data_server_button)

        self.update_user_plugin_button = self.create_secondary_button(
            parent_widget, "Change User Plugin Location"
        )
        self.update_user_plugin_button.setToolTip("Select a folder")
        self.update_user_plugin_button.clicked.connect(self.update_user_plugin_folder)

        layout_userPluginLocation = QHBoxLayout()
        layout_userPluginLocation.addWidget(
            self.create_label(parent_widget, "Set User Plugin Folder", 10)
        )
        layout_userPluginLocation.addWidget(self.update_user_plugin_button)

        shared_service_layout = QVBoxLayout()
        shared_service_layout.addLayout(layout_dataServerLocation)
        shared_service_layout.addLayout(layout_userPluginLocation)
        shared_service_widget = QWidget()
        shared_service_widget.setLayout(shared_service_layout)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(shared_service_widget))
        layout.addWidget(self.add_horizontal_line())

    @log(logger=logger)
    def add_advanced_settings_tab_contents(self, parent_widget, layout):
        layout.setSpacing(0)

        advanced_settings_label = self.create_label(
            parent_widget, "Advanced Settings", 14
        )
        description_label = self.create_label(
            parent_widget,
            "Adjust detailed settings and configurations for advanced users and developers",
            10,
        )
        advanced_settings_layout = QVBoxLayout()
        advanced_settings_layout.addWidget(advanced_settings_label)
        advanced_settings_layout.addWidget(description_label)
        advanced_settings_widget = QWidget()
        advanced_settings_widget.setLayout(advanced_settings_layout)
        layout.addWidget(self.create_section_layout(advanced_settings_widget))

        layout_loggingLevel = QHBoxLayout()
        layout_loggingLevel.addWidget(
            self.create_label(parent_widget, "Logging Level", 10)
        )
        self.logging_level_combobox = self.create_combo_box(
            parent_widget,
            ["None", "Debug", "Info", "Warning", "Error", "Critical"],
            max_width=self.width() // 3,
        )
        layout_loggingLevel.addWidget(
            self.logging_level_combobox, alignment=Qt.AlignLeft
        )
        self.logging_level_combobox.currentIndexChanged.connect(
            self.update_logging_level
        )

        logging_level_widget = QWidget()
        logging_level_widget.setLayout(layout_loggingLevel)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(logging_level_widget))

        layout_clearCache = QHBoxLayout()
        layout_clearCache.addWidget(self.create_label(parent_widget, "Clear Cache", 10))
        self.clear_cache_button = self.create_push_button(
            parent_widget,
            "Clear Cache",
            "rgb(255, 107, 107)",
            "#FFFFFF",
            max_width=self.width() // 3,
        )
        self.clear_cache_button.clicked.connect(self.handle_clear_cache)
        layout_clearCache.addWidget(self.clear_cache_button, alignment=Qt.AlignLeft)

        clear_cache_widget = QWidget()
        clear_cache_widget.setLayout(layout_clearCache)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(clear_cache_widget))

        layout_resetSettings = QHBoxLayout()
        layout_resetSettings.addWidget(
            self.create_label(parent_widget, "Reset to Default Settings", 10)
        )
        self.reset_settings_button = self.create_push_button(
            parent_widget,
            "Reset Settings",
            "rgb(255, 107, 107)",
            "#FFFFFF",
            max_width=self.width() // 3,
        )
        layout_resetSettings.addWidget(
            self.reset_settings_button, alignment=Qt.AlignLeft
        )

        reset_settings_widget = QWidget()
        reset_settings_widget.setLayout(layout_resetSettings)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(reset_settings_widget))
        layout.addWidget(self.add_horizontal_line())

    @log(logger=logger)
    def add_about_tab_contents(self, parent_widget, layout):
        layout.setSpacing(0)

        about_label = self.create_label(parent_widget, "About", 14)
        description_label = self.create_label(
            parent_widget,
            "Learn more about this application, its version, developers, and licensing information",
            10,
        )
        about_layout = QVBoxLayout()
        about_layout.addWidget(about_label)
        about_layout.addWidget(description_label)
        about_widget = QWidget()
        about_widget.setLayout(about_layout)
        layout.addWidget(self.create_section_layout(about_widget))

        layout_versionInfo = QVBoxLayout()
        layout_versionInfo.addWidget(
            self.create_label(parent_widget, "Application Version", 10)
        )
        layout_versionInfo.addWidget(
            self.create_label(parent_widget, f"Version {__VERSION__}", 10)
        )
        version_info_widget = QWidget()
        version_info_widget.setLayout(layout_versionInfo)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(version_info_widget))

        layout_developerInformation = QVBoxLayout()
        layout_developerInformation.addWidget(
            self.create_label(parent_widget, "Developer Information", 10)
        )
        layout_developerInformation.addWidget(
            self.create_label(
                parent_widget, "Kyle Briggs & Alejandra Carolina González González", 10
            )
        )
        developer_info_widget = QWidget()
        developer_info_widget.setLayout(layout_developerInformation)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(developer_info_widget))

    # ------------------------------------------------------------------
    # Slots / actions
    # ------------------------------------------------------------------

    def handle_clear_cache(self):
        self.clear_cache.emit()

    @log(logger=logger)
    def update_data_server(self):
        self.get_shared_server_location.emit()
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder", self.data_server
        )
        if folder_path:
            self.update_data_server_location.emit(folder_path)

    @log(logger=logger)
    def update_user_plugin_folder(self):
        self.get_user_plugin_folder_location.emit()
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder", self.user_plugin_location
        )
        if folder_path:
            self.update_user_plugin_location.emit(folder_path)

    @log(logger=logger)
    def set_data_server(self, data_server):
        self.data_server = data_server

    @log(logger=logger)
    def set_user_plugin_location(self, user_plugin_loc):
        self.user_plugin_location = user_plugin_loc

    @Slot(int)
    def update_logging_level(self, index):
        level = {
            0: logging.NOTSET,
            1: logging.DEBUG,
            2: logging.INFO,
            3: logging.WARNING,
            4: logging.ERROR,
            5: logging.CRITICAL,
        }.get(index, logging.NOTSET)
        self.update_log_level.emit(level)

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("Form", "Settings", None))

    def main(self):
        import sys

        app = QApplication(sys.argv)
        SettingsWindow().show()
        sys.exit(app.exec())


if __name__ == "__main__":
    SettingsWindow().main()
