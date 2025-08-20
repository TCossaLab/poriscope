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
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log


class HelpCentreMain(QWidget):
    logger = logging.getLogger(__name__)

    def __init__(self):
        super().__init__()
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "icons"
        )
        self.setupUi()

    @log(logger=logger)
    def setupUi(self):
        self.setObjectName("HelpCentreMain")
        self.setStyleSheet("padding: 20px;")

        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # Label
        self.help_centre_label = QLabel(self)
        self.help_centre_label.setObjectName("helpCentre_label")
        help_centre_font = QFont()
        help_centre_font.setPointSize(20)
        self.help_centre_label.setFont(help_centre_font)
        main_layout.addWidget(self.help_centre_label, alignment=Qt.AlignLeft)

        # Spacer item for top margin
        main_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # Create button layouts
        top_button_layout = QHBoxLayout()
        bottom_button_layout = QHBoxLayout()

        # Add buttons to the layouts with spacers for spacing
        top_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.getting_started_button = self.create_push_button(
            "gettingStarted_pushButton",
            12,
            "Getting Started",
            os.path.join(self.icon_path, "rocket-white.svg"),
            os.path.join(self.icon_path, "rocket-black.svg"),
            "black",
        )
        top_button_layout.addWidget(self.getting_started_button)
        top_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.documentation_button = self.create_push_button(
            "documentation_pushButton",
            12,
            "Documentation",
            os.path.join(self.icon_path, "documentation-black.png"),
            os.path.join(self.icon_path, "documentation-white.png"),
            "white",
        )
        top_button_layout.addWidget(self.documentation_button)
        top_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.adding_plugin_button = self.create_push_button(
            "addingPlugin_pushButton",
            12,
            "Adding A Plugin",
            os.path.join(self.icon_path, "plugin-white.png"),
            os.path.join(self.icon_path, "plugin-black.png"),
            "black",
        )
        top_button_layout.addWidget(self.adding_plugin_button)
        top_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        bottom_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.building_plugin_button = self.create_push_button(
            "buildingPlugin_pushButton",
            12,
            "Building A Plugin",
            os.path.join(self.icon_path, "building-black.png"),
            os.path.join(self.icon_path, "building-white.png"),
            "white",
        )
        bottom_button_layout.addWidget(self.building_plugin_button)
        bottom_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.error_codes_button = self.create_push_button(
            "errorCodes_pushButton",
            12,
            "Error Codes",
            os.path.join(self.icon_path, "error-white.png"),
            os.path.join(self.icon_path, "error-black.png"),
            "black",
        )
        bottom_button_layout.addWidget(self.error_codes_button)
        bottom_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )
        self.report_problem_button = self.create_push_button(
            "reportProblem_pushButton",
            12,
            "Report A Problem",
            os.path.join(self.icon_path, "report-black.png"),
            os.path.join(self.icon_path, "report-white.png"),
            "white",
        )
        bottom_button_layout.addWidget(self.report_problem_button)
        bottom_button_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # Add button layouts to the main layout
        main_layout.addLayout(top_button_layout)
        main_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        main_layout.addLayout(bottom_button_layout)
        main_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    @log(logger=logger)
    def create_push_button(
        self, object_name, font_size, text, icon_path, hover_icon_path, initial_color
    ):
        button = QPushButton(self)
        button.setObjectName(object_name)
        button_font = QFont()
        button_font.setPointSize(font_size)
        button.setFont(button_font)

        icon = QIcon(icon_path)
        button.setIcon(icon)
        button.setIconSize(QSize(64, 64))

        if initial_color == "black":
            style_sheet = "background-color: black; color: white; border-radius: 10px; border: 2px solid black; padding: 10px;"
        else:
            style_sheet = "background-color: white; color: black; border-radius: 10px; border: 2px solid black; padding: 10px;"

        button.setStyleSheet(style_sheet)
        button.setText(text)
        button.setFixedSize(271, 151)

        button.installEventFilter(self)
        button.hover_icon_path = hover_icon_path
        button.default_icon_path = icon_path
        button.initial_color = initial_color
        return button

    @log(logger=logger, debug_only=True)
    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton):
            if event.type() == QEvent.Enter:
                self.on_button_hover_enter(obj)
            elif event.type() == QEvent.Leave:
                self.on_button_hover_leave(obj)
        return super().eventFilter(obj, event)

    @log(logger=logger, debug_only=True)
    def on_button_hover_enter(self, button):
        button.setIcon(QIcon(button.hover_icon_path))
        if button.initial_color == "black":
            button.setStyleSheet(
                "background-color: white; color: black; border-radius: 10px; border: 2px solid black; padding: 10px;"
            )
        else:
            button.setStyleSheet(
                "background-color: black; color: white; border-radius: 10px; border: 2px solid black; padding: 10px;"
            )

    @log(logger=logger, debug_only=True)
    def on_button_hover_leave(self, button):
        button.setIcon(QIcon(button.default_icon_path))
        if button.initial_color == "black":
            button.setStyleSheet(
                "background-color: black; color: white; border-radius: 10px; border: 2px solid black; padding: 10px;"
            )
        else:
            button.setStyleSheet(
                "background-color: white; color: black; border-radius: 10px; border: 2px solid black; padding: 10px;"
            )

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("Form", "Help Centre", None))
        self.help_centre_label.setText(
            QCoreApplication.translate("Form", "Help Centre", None)
        )


class HelpCentre(QWidget):
    logger = logging.getLogger(__name__)

    def __init__(self):
        super().__init__()
        self.setupUi()
        self.setupViews()

    def setupUi(self):
        self.setObjectName("Form")
        self.resize(939, 588)
        self.setStyleSheet(
            "padding: 20px;"
        )  # Set overall background to white and add padding

        self.main_layout = QVBoxLayout(self)
        self.setLayout(self.main_layout)

        # Create a QStackedWidget for the views
        self.stacked_widget = QStackedWidget(self)
        self.main_layout.addWidget(self.stacked_widget)

    @log(logger=logger)
    def setupViews(self):
        # Import the views here
        from poriscope.views.adding_plugin import AddingPlugin
        from poriscope.views.building_plugin import BuildingPlugin
        from poriscope.views.documentation import Documentation
        from poriscope.views.error_codes import ErrorCodes
        from poriscope.views.getting_started import GettingStarted
        from poriscope.views.report_problem import ReportProblem

        # Create instances of the views
        self.help_centre_main_view = HelpCentreMain()
        self.getting_started_view = GettingStarted()
        self.documentation_view = Documentation()
        self.adding_plugin_view = AddingPlugin()
        self.building_plugin_view = BuildingPlugin()
        self.error_codes_view = ErrorCodes()
        self.report_problem_view = ReportProblem()

        # Add the views to the stacked widget
        self.stacked_widget.addWidget(
            self.help_centre_main_view
        )  # Add HelpCentreMain view
        self.stacked_widget.addWidget(self.getting_started_view)
        self.stacked_widget.addWidget(self.documentation_view)
        self.stacked_widget.addWidget(self.adding_plugin_view)
        self.stacked_widget.addWidget(self.building_plugin_view)
        self.stacked_widget.addWidget(self.error_codes_view)
        self.stacked_widget.addWidget(self.report_problem_view)

        # Connect buttons to their respective slots
        self.help_centre_main_view.getting_started_button.clicked.connect(
            lambda: self.display_view(1)
        )
        self.help_centre_main_view.documentation_button.clicked.connect(
            lambda: self.display_view(2)
        )
        self.help_centre_main_view.adding_plugin_button.clicked.connect(
            lambda: self.display_view(3)
        )
        self.help_centre_main_view.building_plugin_button.clicked.connect(
            lambda: self.display_view(4)
        )
        self.help_centre_main_view.error_codes_button.clicked.connect(
            lambda: self.display_view(5)
        )
        self.help_centre_main_view.report_problem_button.clicked.connect(
            lambda: self.display_view(6)
        )

        # Connect signals from Views to go back to the help centre
        self.adding_plugin_view.go_back_signal.connect(self.display_view)
        self.getting_started_view.go_back_signal.connect(self.display_view)
        self.documentation_view.go_back_signal.connect(self.display_view)
        self.building_plugin_view.go_back_signal.connect(self.display_view)
        self.error_codes_view.go_back_signal.connect(self.display_view)
        self.report_problem_view.go_back_signal.connect(self.display_view)

    def display_view(self, index):
        self.stacked_widget.setCurrentIndex(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HelpCentre()
    window.show()
    sys.exit(app.exec())
