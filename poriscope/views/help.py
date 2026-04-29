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
import webbrowser

from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QRectF, Qt
from PySide6.QtGui import QCursor, QFont, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log

_ICON_PX = 64  # logical icon size
_RENDER_PX = _ICON_PX * 2  # render at 2× for crisp display


class LinkCard(QFrame):
    """
    Clickable card that opens a URL on click.

    initial_bg='black'  -> resting: black bg / white text; hover: white bg / black text.
    initial_bg='white'  -> resting: white bg / black text; hover: black bg / white text.

    Supply two icon paths so the icon colour matches the card bg at all times.
    """

    def __init__(
        self,
        title: str,
        url: str,
        icon_path_normal: str,
        icon_path_hover: str,
        initial_bg: str = "black",
        parent=None,
    ):
        super().__init__(parent)
        self._url = url
        self._initial_bg = initial_bg
        self._icon_path_normal = icon_path_normal
        self._icon_path_hover = icon_path_hover

        self.setFixedHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        row = QHBoxLayout(self)
        row.setContentsMargins(24, 18, 24, 18)
        row.setSpacing(18)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_PX, _ICON_PX)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        row.addWidget(self._icon_label)

        col = QVBoxLayout()
        col.setSpacing(6)

        self._title_label = QLabel(title)
        self._title_label.setFont(QFont("Arial", 13, QFont.Bold))
        self._title_label.setWordWrap(True)
        self._title_label.setStyleSheet("background: transparent; border: none;")

        self._url_label = QLabel(url)
        self._url_label.setFont(QFont("Arial", 9))
        self._url_label.setWordWrap(True)
        self._url_label.setStyleSheet("background: transparent; border: none;")

        col.addWidget(self._title_label)
        col.addWidget(self._url_label)
        col.addStretch()
        row.addLayout(col)

        self._refresh(hovered=False)
        self.installEventFilter(self)

    def _load_icon(self, path: str):
        if not path or not os.path.exists(path):
            return

        ext = os.path.splitext(path)[1].lower()

        if ext == ".svg":
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                return
            image = QImage(_RENDER_PX, _RENDER_PX, QImage.Format_ARGB32)
            image.fill(0)  # transparent
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, _RENDER_PX, _RENDER_PX))
            painter.end()
            pixmap = QPixmap.fromImage(image)
        else:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                return
            pixmap = pixmap.scaled(
                _RENDER_PX, _RENDER_PX,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )

        # Scale down to logical size but mark as high-DPI so Qt renders crisp
        pixmap.setDevicePixelRatio(2.0)
        self._icon_label.setPixmap(pixmap)

    def _refresh(self, hovered: bool):
        if self._initial_bg == "black":
            bg     = "white" if hovered else "black"
            fg     = "black" if hovered else "white"
            url_fg = "#333"  if hovered else "#ccc"
        else:
            bg     = "black" if hovered else "white"
            fg     = "white" if hovered else "black"
            url_fg = "#ccc"  if hovered else "#555"

        icon = self._icon_path_hover if hovered else self._icon_path_normal

        self.setStyleSheet(
            f"LinkCard {{ background-color: {bg}; border-radius: 12px;"
            f" border: 2px solid black; }}"
        )
        self._title_label.setStyleSheet(
            f"background: transparent; border: none; color: {fg};"
        )
        self._url_label.setStyleSheet(
            f"background: transparent; border: none; color: {url_fg};"
            " text-decoration: underline;"
        )
        self._load_icon(icon)

    def eventFilter(self, obj, event):
        if obj is self:
            if event.type() == QEvent.Enter:
                self._refresh(hovered=True)
            elif event.type() == QEvent.Leave:
                self._refresh(hovered=False)
            elif event.type() == QEvent.MouseButtonRelease:
                webbrowser.open(self._url)
        return super().eventFilter(obj, event)


class HelpCentre(QWidget):
    logger = logging.getLogger(__name__)

    def __init__(self):
        super().__init__()
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "icons"
        )
        self.setupUi()

    @log(logger=logger)
    def setupUi(self):
        self.setMinimumSize(900, 400)
        self.resize(1100, 400)
        self.setStyleSheet("HelpCentre { padding: 20px; }")

        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # Title
        self.help_centre_label = QLabel(self)
        self.help_centre_label.setObjectName("helpCentre_label")
        title_font = QFont()
        title_font.setPointSize(20)
        self.help_centre_label.setFont(title_font)
        main_layout.addWidget(self.help_centre_label, alignment=Qt.AlignLeft)

        main_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        # Cards
        # 1 (Getting Started):    black bg -> hovers white
        # 2 (Documentation):      white bg -> hovers black
        # 3 (Report a Problem):   black bg -> hovers white
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.getting_started_card = LinkCard(
            title="Tutorial Series",
            url="https://youtube.com/@tcossalab?si=A8Wy8yHOXiwSXu5F",
            icon_path_normal=os.path.join(self.icon_path, "rocket-white.svg"),
            icon_path_hover=os.path.join(self.icon_path, "rocket-black.svg"),
            initial_bg="black",
        )
        self.tutorial_card = LinkCard(
            title="Documentation",
            url="https://tcossalab.github.io/poriscope/",
            icon_path_normal=os.path.join(self.icon_path, "documentation-black.png"),
            icon_path_hover=os.path.join(self.icon_path, "documentation-white.png"),
            initial_bg="white",
        )
        self.report_card = LinkCard(
            title="Report a Problem",
            url="https://github.com/TCossaLab/poriscope/issues/new/choose",
            icon_path_normal=os.path.join(self.icon_path, "report-white.png"),
            icon_path_hover=os.path.join(self.icon_path, "report-black.png"),
            initial_bg="black",
        )
        cards_layout.addWidget(self.getting_started_card, stretch=1)
        cards_layout.addWidget(self.tutorial_card, stretch=1)
        cards_layout.addWidget(self.report_card, stretch=1)
        main_layout.addLayout(cards_layout)

        main_layout.addSpacerItem(
            QSpacerItem(0, 12, QSizePolicy.Minimum, QSizePolicy.Fixed)
        )

        self.paper_card = LinkCard(
            title="Poriscope: A Configurable Pipeline for Nanopore Data Analysis",
            url="https://openresearchsoftware.metajnl.com/articles/10.5334/jors.703",
            icon_path_normal="",
            icon_path_hover="",
            initial_bg="white",
        )
        self.paper_card.setFixedHeight(80)
        main_layout.addWidget(self.paper_card)

        main_layout.addSpacerItem(
            QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )

        self.retranslateUi()
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("Form", "Help Centre", None))
        self.help_centre_label.setText(
            QCoreApplication.translate("Form", "Help Centre", None)
        )




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HelpCentre()
    window.show()
    sys.exit(app.exec())