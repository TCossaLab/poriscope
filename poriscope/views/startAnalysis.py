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

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log


class StartAnalysis(QWidget):
    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def __init__(self, parent=None):
        super(StartAnalysis, self).__init__(parent)

        # Main layout
        layout = QVBoxLayout(self)

        # Center button layout
        centerButtonLayout = QHBoxLayout()
        centerButtonLayout.addStretch()

        self.startAnalysisButton = QPushButton("Start Analysis", self)
        buttonSize = 100
        self.startAnalysisButton.setFixedSize(buttonSize, buttonSize)
        self.startAnalysisButton.setStyleSheet(
            "QPushButton {"
            "background-color: rgb(0, 0, 0);"
            "color: rgb(255, 255, 255);"
            "border-radius: 50px;"
            "font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "background-color: rgb(255, 255, 255);"
            "color: rgb(0, 0, 0);"
            "}"
        )
        centerButtonLayout.addWidget(self.startAnalysisButton)
        centerButtonLayout.addStretch()

        layout.addLayout(centerButtonLayout)

        # Time control layout
        timeControlLayout = QHBoxLayout()
        iconSize = QSize(30, 30)

        self.timeBackButton = QPushButton(
            QIcon(":/icons/rewind-10-seconds-back-icon-256x256-rbh4y9zd.png"), "", self
        )
        self.timeBackButton.setIconSize(iconSize)
        self.timeBackButton.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        timeControlLayout.addWidget(self.timeBackButton)

        timeLabel = QLabel("Time", self)
        timeLabel.setAlignment(Qt.AlignCenter)
        timeLabel.setStyleSheet(
            "font-size: 20px;padding:0px; background-color: transparent; border: none;border-radius:10px;"
        )
        timeControlLayout.addWidget(timeLabel)

        self.timeForwardButton = QPushButton(
            QIcon(":/icons/rewind-10-seconds-forward-icon-256x256-ddtx5gse.png"),
            "",
            self,
        )
        self.timeForwardButton.setIconSize(iconSize)
        self.timeForwardButton.setStyleSheet(
            "background-color: transparent; border: none;"
        )
        self.timeForwardButton.setCheckable(True)
        self.timeForwardButton.setAutoExclusive(True)
        timeControlLayout.addWidget(self.timeForwardButton)

        layout.addLayout(timeControlLayout)

        self.setLayout(layout)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = StartAnalysis()
    window.show()
    sys.exit(app.exec())
