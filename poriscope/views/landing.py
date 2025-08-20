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

import json
import logging
import os
import sys
from pathlib import Path

from platformdirs import user_data_dir
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.utils.LogDecorator import log

# Add the root of the project to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
# Ensure you have compiled your resources with the rcc tool and imported them correctly.


class CircularButton(QPushButton):
    logger = logging.getLogger(__name__)

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "icons"
        )

        self.pixmap = pixmap
        self.setFixedSize(150, 150)
        self.setIcon(QIcon(self.pixmap))
        self.setIconSize(QSize(150, 150))
        self.setStyleSheet(
            """
            QPushButton {
                border: none;
                border-radius: 75px;
            }
        """
        )
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor(0, 0, 0, 0))
        self.shadow.setOffset(0, 0)
        self.setGraphicsEffect(self.shadow)

    @log(logger=logger, debug_only=True)
    def enterEvent(self, event):
        self.shadow.setBlurRadius(20)
        self.shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow)
        super().enterEvent(event)

    @log(logger=logger, debug_only=True)
    def leaveEvent(self, event):
        self.shadow.setBlurRadius(0)
        self.shadow.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(self.shadow)
        super().leaveEvent(event)

    @log(logger=logger, debug_only=True)
    def paintEvent(self, event):
        painter = QPainter(self)
        path = QPainterPath()
        path.addEllipse(0, 0, self.width(), self.height())
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self.width(), self.height(), self.pixmap)


class AddUserDialog(QDialog):
    logger = logging.getLogger(__name__)

    @log(logger=logger)
    def __init__(self, parent=None):
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "icons"
        )
        super().__init__(parent)
        self.initUI()

    @log(logger=logger)
    def initUI(self):
        self.layout = QVBoxLayout(self)

        self.firstNameEdit = QLineEdit(self)
        self.firstNameEdit.setPlaceholderText("First Name")
        self.layout.addWidget(self.firstNameEdit)

        self.lastNameEdit = QLineEdit(self)
        self.lastNameEdit.setPlaceholderText("Last Name")
        self.layout.addWidget(self.lastNameEdit)

        self.imagePathEdit = QLineEdit(self)
        self.imagePathEdit.setPlaceholderText("Image Path (optional)")
        self.layout.addWidget(self.imagePathEdit)

        browseButton = QPushButton("Browse", self)
        browseButton.clicked.connect(self.browseImage)
        self.layout.addWidget(browseButton)

        addButton = QPushButton("Add User", self)
        addButton.clicked.connect(self.accept)
        self.layout.addWidget(addButton)

        self.setWindowTitle("Add User")

    @log(logger=logger)
    def browseImage(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Image Files (*.png *.jpg *.bmp)"
        )
        if file_name:
            self.imagePathEdit.setText(file_name)

    @log(logger=logger)
    def getUserDetails(self):
        return {
            "first_name": self.firstNameEdit.text().strip(),
            "last_name": self.lastNameEdit.text().strip(),
            "image_path": self.imagePathEdit.text().strip(),
        }


class Landing(QWidget):
    logger = logging.getLogger(__name__)
    userSelected = Signal(str, str, str)  # Signal to emit first name and last name

    def __init__(self):
        super().__init__()
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "..", "configs", "icons"
        )
        self.users_file = self.get_user_file_path()
        self.users = self.read_users()  # Read users at initialization
        self.initUI()

    @log(logger=logger)
    def initUI(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 70)

        question_label = QLabel("Who is Analyzing?", self)
        question_label.setAlignment(Qt.AlignCenter)
        question_label.setStyleSheet("font-size: 24px;")
        self.main_layout.addWidget(question_label)

        self.h_layout = QHBoxLayout()
        self.h_layout.setSpacing(50)

        for user in self.users:  # Iterate over users read from file
            full_name = f"{user['first_name']} {user['last_name']}"
            image_path = (
                user["image_path"]
                if user["image_path"]
                else (os.path.join(self.icon_path, "person.png"))
            )
            self.addUser(full_name, image_path)

        self.main_layout.addLayout(self.h_layout)

        self.addUserButton = CircularButton(
            QPixmap(os.path.join(self.icon_path, "Add.png")), self
        )
        self.addUserButton.clicked.connect(self.openAddUserDialog)

        v_layout = QVBoxLayout()
        v_layout.setAlignment(Qt.AlignCenter)
        v_layout.addWidget(self.addUserButton)

        add_user_label = QLabel("Add User", self)
        add_user_label.setAlignment(Qt.AlignCenter)
        v_layout.addWidget(add_user_label)

        self.main_layout.addLayout(v_layout)

        self.setWindowTitle("Analyzer Selector")
        self.setGeometry(100, 100, 800, 600)

    def get_user_file_path(self):
        local_app_data_path = user_data_dir()
        folder = Path(local_app_data_path, "Nanolyzer", "session")
        file_path = Path(folder, "users.json")
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        return file_path

    def read_users(self):
        try:
            with open(self.users_file, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def write_users(self, users):
        with open(self.users_file, "w") as file:
            json.dump(users, file, indent=4)

    def openAddUserDialog(self):
        dialog = AddUserDialog(self)
        if dialog.exec():
            user_details = dialog.getUserDetails()
            first_name = user_details["first_name"]
            last_name = user_details["last_name"]
            full_name = f"{first_name} {last_name}"
            image_path = user_details["image_path"]
            self.addUser(full_name, image_path)

            # Reading current users, adding the new user, and writing back
            users = self.read_users()
            users.append(user_details)
            self.write_users(users)

    @log(logger=logger)
    def addUser(self, name, image_path):
        v_layout = QVBoxLayout()
        v_layout.setAlignment(Qt.AlignCenter)

        pixmap = QPixmap(
            image_path if image_path else os.path.join(self.icon_path, "person.png")
        )
        pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        img_button = CircularButton(pixmap, self)
        img_button.clicked.connect(
            lambda: self.on_user_selected(name, image_path)
        )  # Pass image path as well
        v_layout.addWidget(img_button)

        name_label = QLabel(name, self)
        name_label.setAlignment(Qt.AlignCenter)
        v_layout.addWidget(name_label)

        self.h_layout.addLayout(v_layout)

    @log(logger=logger)
    def on_user_selected(self, full_name, image_path):
        parts = full_name.split(maxsplit=1)
        if len(parts) == 2:
            first_name, last_name = parts
        else:
            first_name = parts[0]
            last_name = ""  # Handle case where there is no last name

        # Emit the signal with first name, last name, and image path
        self.userSelected.emit(first_name, last_name, image_path)
