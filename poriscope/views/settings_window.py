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
from PySide6.QtGui import QFont, QPainter, QPixmap
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
    QSpacerItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log


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
        self.setupUi()

    @log(logger=logger)
    def setupUi(self):
        self.setObjectName("Form")
        self.resize(915, 900)  # Initial size
        self.setStyleSheet("margin:0")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        self.settingsLabel = self.create_label(self, "Settings", 24, bold=True)
        main_layout.addWidget(self.settingsLabel, alignment=Qt.AlignLeft)

        self.tabWidget = QTabWidget(self)
        self.tabWidget.setFont(QFont("", -1, QFont.Bold))
        self.tabWidget.setStyleSheet(
            """
            QTabWidget::pane {
                border: none; 
                margin:10px;
            }
            QTabBar::tab {
                padding: 10px; 
                margin: 0px; 
                border: none; 
                border-bottom: 2px solid #D0D0D0;
                font-size: 16px; 
                
            }
            QTabBar::tab:selected {
                border-bottom: 2px solid #000000;
                font-weight: bold;  
            }
            QTabBar::tab:hover {
                border-bottom: 2px solid #000000;
                font-weight: bold;  
            }
            QTabBar::tab {
                font-family: Arial, Helvetica, sans-serif;  /* Set a font family known for good rendering */
                text-rendering: optimizeLegibility;  /* Enable optimized text rendering */
            }
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
        self.tabWidget.setCurrentIndex(0)
        QMetaObject.connectSlotsByName(self)

    @log(logger=logger)
    def create_label(self, parent, text, font_size, bold=False, circular_image=False):
        label = QLabel(parent)
        label.setText(QCoreApplication.translate("Form", text, None))
        font = QFont()
        font.setPointSize(font_size)
        font.setBold(bold)
        label.setFont(font)

        if circular_image:
            path = "/mnt/data/image.png"  # Path to the uploaded image
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    50, 50, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
                mask = QPixmap(50, 50)
                mask.fill(Qt.transparent)
                painter = QPainter(mask)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(Qt.white)
                painter.drawEllipse(0, 0, 50, 50)
                painter.end()
                pixmap.setMask(mask.createMaskFromColor(Qt.transparent, Qt.MaskInColor))
                label.setPixmap(pixmap)

        return label

    @log(logger=logger)
    def create_circle_label(self, parent, diameter, background_color):
        label = QLabel(parent)
        label.setFixedSize(diameter, diameter)
        label.setStyleSheet(
            f"background-color: {background_color}; border-radius: {diameter // 2}px;"
        )
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

        comboBox.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #D0D0D0;
                border-radius: 15px;
                padding: 5px 15px;
                background: #FFFFFF;
                color: #333333;
                min-height: 30px;
                min-width: 200px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border: none;
            }
            QComboBox::down-arrow {
                width: 20px;
                height: 20px;
                image: url(":/icons/arrowdown-black.png");
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #D0D0D0;
                border-radius: 15px;
                background: #FFFFFF;
                color: #333333;
                selection-background-color: #F5F5F5;
                padding: 5px;
                outline: 0px;
            }
            QComboBox QAbstractItemView::item {
                padding: 5px 15px;
                min-height: 20px;
                min-width: 20px;
                border: none;
                background: #FFFFFF;
                color: #333333;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #F5F5F5;
                color: #333333;
                border-radius: 15px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #E5E5E5;
                color: #333333;
                border-radius: 15px;
            }
        """
        )

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
            """
            QListWidget {
                border: 1px solid #D0D0D0;
                border-radius: 15px;
                padding: 5px 15px;
                background: #FFFFFF;
                color: #333333;
                min-height: 30px;
                min-width: 200px;
            }
            QListWidget::item {
                padding: 5px 15px;
            }
            QListWidget::item:selected {
                background: #F5F5F5;
                color: #333333;
                border-radius: 15px;
            }
            QListWidget::item:hover {
                background: #E5E5E5;
                color: #333333;
                border-radius: 15px;
            }
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
    def create_styled_check_box(self, parent, object_name):
        checkBox = QCheckBox(parent)
        checkBox.setObjectName(object_name)
        checkBox.setStyleSheet(
            """
        QCheckBox::indicator {
            width: 50px;
            height: 50px;
        }
        QCheckBox::indicator:checked {
            image: url(":/icons/toggle-on.png");
        }
        QCheckBox::indicator:unchecked {
            image: url(":/icons/toggle-off.png");
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
            """
            QLineEdit {
                border: 1px solid #D0D0D0;
                border-radius: 15px;
                padding: 5px 15px;
                background: #FFFFFF;
                color: #333333;
                min-height: 30px;
                min-width: 200px;
            }
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
        is_circle=False,
        image_path=None,
        max_width=None,
    ):
        pushButton = QPushButton(parent)
        pushButton.setText(QCoreApplication.translate("Form", text, None))
        if max_width:
            pushButton.setMaximumWidth(max_width)
        border_radius = "15px" if not is_circle else "25px"
        style_sheet = f"""
            QPushButton {{
                background: {background_color};
                color: {text_color};
                border: none;
                border-radius: {border_radius};
                padding: 5px 15px;
                min-width: 100px;
                min-height: 30px;
            }}
        """
        if is_circle:
            style_sheet += """
                max-width: 50px;
                max-height: 50px;
            """
            if image_path:
                style_sheet += f"""
                    background-image: url({image_path});
                    background-repeat: no-repeat;
                    background-position: center;
                """
        style_sheet += """
            QPushButton:hover {
                background: #333333;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background: #999999;
                color: #FFFFFF;
            }
        """
        pushButton.setStyleSheet(style_sheet)
        return pushButton

    @log(logger=logger)
    def create_section_layout(self, widget, color):
        container = QWidget()
        container.setStyleSheet(f"background-color: {color};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        container_layout.addWidget(widget)
        return container

    @log(logger=logger)
    def add_general_tab_contents(self, parent_widget, layout):
        layout.setSpacing(0)  # Adjust the spacing between the main sections

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
        layout.addWidget(self.create_section_layout(general_widget, ""))

        layout_language = QHBoxLayout()
        layout_language.addWidget(self.create_label(parent_widget, "Language", 10))
        layout_language.addWidget(
            self.create_combo_box(
                parent_widget, ["English", "Español"], max_width=self.width() // 3
            ),
            alignment=Qt.AlignLeft,
        )

        language_widget = QWidget()
        language_widget.setLayout(layout_language)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(language_widget, ""))

        self.update_data_server_button = QPushButton("Change Data Server Location")
        self.update_data_server_button.setToolTip("Select a folder")
        self.update_data_server_button.clicked.connect(self.update_data_server)

        layout_dataServerLocation = QHBoxLayout()
        layout_dataServerLocation.addWidget(
            self.create_label(parent_widget, "Set Data Server", 10)
        )
        layout_dataServerLocation.addWidget(self.update_data_server_button)

        self.update_user_plugin_button = QPushButton("Change User Plugin Location")
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
        layout.addWidget(self.create_section_layout(shared_service_widget, ""))

        # Setting up buttons with connections
        layout_buttons = QHBoxLayout()
        layout_buttons.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )

        buttons_widget = QWidget()
        buttons_widget.setLayout(layout_buttons)

        layout.addWidget(self.add_horizontal_line())

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
        layout.addWidget(self.create_section_layout(advanced_settings_widget, ""))

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

        # Connect the combobox to a method that updates the logging level
        self.logging_level_combobox.currentIndexChanged.connect(
            self.update_logging_level
        )

        logging_level_widget = QWidget()
        logging_level_widget.setLayout(layout_loggingLevel)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(logging_level_widget, ""))

        # Clear Cache button
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
        layout.addWidget(self.create_section_layout(clear_cache_widget, ""))

        layout_resetSettings = QHBoxLayout()
        layout_resetSettings.addWidget(
            self.create_label(parent_widget, "Reset to Default Settings", 10)
        )
        layout_resetSettings.addWidget(
            self.create_push_button(
                parent_widget,
                "Reset Settings",
                "rgb(255, 107, 107)",
                "#FFFFFF",
                max_width=self.width() // 3,
            ),
            alignment=Qt.AlignLeft,
        )

        reset_settings_widget = QWidget()
        reset_settings_widget.setLayout(layout_resetSettings)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(reset_settings_widget, ""))

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
        layout.addWidget(self.create_section_layout(about_widget, ""))

        layout_versionInfo = QVBoxLayout()
        layout_versionInfo.addWidget(
            self.create_label(parent_widget, "Application Version", 10)
        )
        layout_versionInfo.addWidget(
            self.create_label(parent_widget, "Version 1.0.2", 10)
        )

        version_info_widget = QWidget()
        version_info_widget.setLayout(layout_versionInfo)

        layout.addWidget(self.add_horizontal_line())
        layout.addWidget(self.create_section_layout(version_info_widget, ""))

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
        layout.addWidget(self.create_section_layout(developer_info_widget, ""))

    def add_horizontal_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(
            "min-height: 1px; max-height: 1px; background-color: #a0a0a0; border: none;"
        )
        return line

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
        SettingsWindow()
        sys.exit(app.exec())


if __name__ == "__main__":
    SettingsWindow().main()
