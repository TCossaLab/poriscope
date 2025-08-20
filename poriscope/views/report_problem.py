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
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log

# Add the root of the project to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


class ReportProblem(QWidget):
    logger = logging.getLogger(__name__)
    go_back_signal = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.setMinimumSize(QSize(800, 600))

    @log(logger=logger)
    def init_ui(self):

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(25, 0, 25, 0)

        # White content container
        content_container = QWidget()
        content_container.setStyleSheet(
            """
            border-radius: 15px;
            padding: 20px;
            margin: 10px;
        """
        )
        content_layout = QVBoxLayout(content_container)
        content_layout.setSpacing(10)

        # Back Button
        back_button_layout = QHBoxLayout()
        self.back_button = QPushButton("← Help Centre")
        self.back_button.setStyleSheet(
            "text-align: left; font-size: 18px; border: none;"
        )
        self.back_button.clicked.connect(self.go_back)
        back_button_layout.addWidget(self.back_button)
        back_button_layout.setAlignment(Qt.AlignLeft)
        content_layout.addLayout(back_button_layout)

        # Main Title
        title = QLabel("<p style='text-align:justify;'>Report Problem</p>")
        title.setFont(QFont("Arial", 24))
        title.setStyleSheet("margin-top: 0; margin-bottom: 10px; padding: 0;")
        title.setTextFormat(Qt.RichText)
        content_layout.addWidget(title)

        # Description
        description = QLabel(
            "<p style='text-align:justify;'>If you are interested in enhancing your Nanolyzer experience, you are in the right place! To learn more about adding plugins, select an option from the list below:</p>"
        )
        description.setFont(QFont("Arial", 12))
        description.setWordWrap(True)
        description.setStyleSheet("margin-top: 0; margin-bottom: 10px; padding: 0;")
        description.setTextFormat(Qt.RichText)
        content_layout.addWidget(description)

        # Links
        links_layout = QVBoxLayout()
        links_layout.setSpacing(0)
        self.link_dict = {
            "What are Plugins?": None,
            "What’s included in a Plugin?": None,
            "How do I add a Plugin?": None,
        }
        for link_text in self.link_dict.keys():
            link_label = QLabel(
                f"<a href='{link_text}' style='text-align:justify;'>{link_text}</a>"
            )
            link_label.setOpenExternalLinks(False)
            link_label.setTextFormat(Qt.RichText)
            link_label.setFont(QFont("Arial", 12))
            link_label.setStyleSheet("margin-top: 0; margin-bottom: 10px; padding: 0;")
            link_label.linkActivated.connect(self.handle_link_click)
            links_layout.addWidget(link_label)
        content_layout.addLayout(links_layout)

        # Sections
        self.sections_layout = QVBoxLayout()
        self.sections_layout.setSpacing(0)

        sections = [
            (
                "What are Plugins?",
                "<p style='text-align:justify;'>Plugins are additional modules that extend the functionality of Nanolyzer. They allow you to customize and enhance the capabilities of the app, providing specialized tools and features to perform your specific analysis tasks. From data visualization to advanced analytics, plugins help you get the most out of your nanopore sequencing data.</p>",
                [],
            ),
            (
                "What’s included in a Plugin?",
                "<p style='text-align:justify;'>Each plugin is designed to offer unique functionalities tailored to your specific analysis needs. Plugins can include:</p><ul style='text-align:justify;'><li>Data readers for different file formats</li><li>Specialized algorithms for data processing and analysis</li><li>Visualization tools for better data interpretation</li><li>Integration with external databases and tools</li></ul><p style='text-align:justify;'>As a base all plugins follow the MVC (Model-View-Controller) structure. For details on the MVC design pattern, please refer to the <a href='Building a Plugin'>Building a Plugin</a> section in the <a href='Help Centre'>Help Centre</a>.</p>",
                [],
            ),
            (
                "How do I add a Plugin?",
                "<p style='text-align:justify;'>Adding a plugin to your Nanolyzer App is simple. Follow these steps to get started:</p><ol style='text-align:justify;'><li>Go to the Plugin Manager in your Nanolyzer App.</li><li>Browse the available plugins or search for a specific one.</li><li>Select the plugin you want to add and click 'Install.'</li><li>Follow the on-screen instructions to complete the installation process.</li></ol>",
                [
                    (
                        "Where are Plugins available?",
                        "<p style='text-align:justify;'>Users can build their own plugins as long as they comply with the MVC structure and reference existing methods properly. Refer to the <a href='Documentation'>Documentation</a> for a list of existing methods and guidelines on building compatible plugins.</p>",
                    ),
                    (
                        "How much does a Plugin cost?",
                        "<p style='text-align:justify;'>There is no cost incurred for plugins. Users can build their own plugins and manually add them to the app as long as they comply with the MVC structure and reference existing methods properly. For specific guidelines, please refer to our <a href='Documentation'>Documentation</a>.</p>",
                    ),
                ],
            ),
        ]

        for main_section_title, main_section_description, subsections in sections:
            main_section_layout = QVBoxLayout()
            main_section_layout.setSpacing(0)
            main_section_label = QLabel(
                f"<p style='text-align:justify;'>{main_section_title}</p>"
            )
            main_section_label.setFont(QFont("Arial", 16, QFont.Bold))
            main_section_label.setStyleSheet(
                "margin-top: 0; margin-bottom: 10px; padding: 0;"
            )
            main_section_label.setTextFormat(Qt.RichText)
            main_section_layout.addWidget(main_section_label)

            main_section_description_label = QLabel(main_section_description)
            main_section_description_label.setFont(QFont("Arial", 12))
            main_section_description_label.setWordWrap(True)
            main_section_description_label.setStyleSheet(
                "margin-top: 0; margin-bottom: 35px; padding: 0;"
            )
            main_section_description_label.setTextFormat(Qt.RichText)
            main_section_layout.addWidget(main_section_description_label)

            for subsection_title, subsection_content in subsections:
                subsection_layout = QVBoxLayout()
                subsection_layout.setSpacing(0)
                subsection_label = QLabel(
                    f"<p style='text-align:justify;'>{subsection_title}</p>"
                )
                subsection_label.setFont(QFont("Arial", 14, QFont.Bold))
                subsection_label.setStyleSheet(
                    "margin-top: 0; margin-bottom: 10px; padding: 0;"
                )
                subsection_label.setTextFormat(Qt.RichText)
                subsection_layout.addWidget(subsection_label)

                subsection_content_label = QLabel(subsection_content)
                subsection_content_label.setFont(QFont("Arial", 12))
                subsection_content_label.setWordWrap(True)
                subsection_content_label.setStyleSheet(
                    "margin-top: 0; margin-bottom: 25px; padding: 0;"
                )
                subsection_content_label.setTextFormat(Qt.RichText)
                subsection_layout.addWidget(subsection_content_label)

                main_section_layout.addLayout(subsection_layout)

            self.sections_layout.addLayout(main_section_layout)
            self.link_dict[main_section_title] = main_section_label

        content_layout.addLayout(self.sections_layout)

        # Adding content container to main layout
        layout.addWidget(content_container)

        # Adding layout to scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setLayout(layout)
        self.scroll_area.setWidget(scroll_content)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll_area)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(30, 10, 30, 10)
        footer_layout.setSpacing(10)

        footer_label = QLabel(
            "<p style='text-align:justify;'>Did this article answer your question?</p>"
        )
        footer_label.setFont(QFont("Arial", 14))
        footer_label.setTextFormat(Qt.RichText)
        footer_layout.addWidget(footer_label)

        yes_button = QPushButton("Yes")
        yes_button.setFont(QFont("Arial", 14))
        yes_button.setStyleSheet(
            """
            padding: 10px 20px;
        
            border: 1px solid #dcdcdc;
            border-radius: 5px;
        """
        )
        no_button = QPushButton("No")
        no_button.setFont(QFont("Arial", 14))
        no_button.setStyleSheet(
            """
            padding: 10px 20px;
            border: 1px solid #dcdcdc;
            border-radius: 5px;
        """
        )
        footer_layout.addWidget(yes_button)
        footer_layout.addWidget(no_button)

        footer_container = QWidget()
        footer_container.setLayout(footer_layout)

        main_layout.addWidget(footer_container)

        self.setLayout(main_layout)

    @log(logger=logger)
    def go_back(self):
        self.go_back_signal.emit(
            0
        )  # Emit the signal with the index of the Help Centre main view
        print("Back button clicked")

    @log(logger=logger)
    def handle_link_click(self, link):
        if link == "Building a Plugin":
            self.open_building_plugin_page()
        elif link == "Help Centre":
            self.go_back()
        else:
            section_widget = self.link_dict.get(link)
            if section_widget:
                self.scroll_area.ensureWidgetVisible(section_widget)

    @log(logger=logger)
    def open_building_plugin_page(self):
        self.go_back_signal.emit(
            4
        )  # Emit the signal with the index of the Building Plugin view
        print("Building a Plugin link clicked")


if __name__ == "__main__":
    app = QApplication([])
    window = ReportProblem()
    window.show()
    app.exec()
