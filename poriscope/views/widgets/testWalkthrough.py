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

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QWidget,
)


class Overlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(parent.rect())
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target_widget = None
        self.highlight_rect = None

    def highlight(self, widget):
        if widget:
            global_top_left = widget.mapToGlobal(QPoint(0, 0))
            local_pos = self.mapFromGlobal(global_top_left)
            self.highlight_rect = QRect(local_pos, widget.size()).adjusted(-4, -4, 4, 4)
        else:
            self.highlight_rect = None
        self.update()

    def paintEvent(self, event):
        if not self.highlight_rect:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dim the background
        painter.setBrush(QColor(0, 0, 0, 160))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        # Black border around highlighted widget
        painter.setBrush(Qt.transparent)
        painter.setPen(QPen(QColor("black"), 4))
        painter.drawRoundedRect(self.highlight_rect, 8, 8)


class StepDialog(QDialog):
    def __init__(self, parent, steps, overlay):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.steps = steps
        self.overlay = overlay
        self.current = 0

        self.setFixedSize(320, 160)
        self.frame = QFrame(self)
        self.frame.setGeometry(0, 0, 320, 160)
        self.frame.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid black;
            }
        """
        )

        self.title = QLabel(self.frame)
        self.title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title.setGeometry(20, 15, 280, 25)
        self.title.setStyleSheet("border: none;")

        self.message = QLabel(self.frame)
        self.message.setFont(QFont("Segoe UI", 9))
        self.message.setWordWrap(True)
        self.message.setGeometry(20, 45, 280, 60)
        self.message.setStyleSheet("border: none;")

        self.step_label = QLabel(self.frame)
        self.step_label.setGeometry(20, 115, 60, 20)
        self.step_label.setStyleSheet("border: none; color: gray; font-size: 9pt;")

        # Shared style for buttons
        button_style = """
        QPushButton {
            background-color: black;
            color: white;
            padding: 6px;
            border-radius: 6px;
            border: 1px solid black;
        }
        QPushButton:hover {
            background-color: white;
            color: black;
            border: 1px solid black;
        }
        """

        self.back_btn = QPushButton("Back", self.frame)
        self.back_btn.setGeometry(120, 110, 60, 30)
        self.back_btn.clicked.connect(self.prev_step)
        self.back_btn.setStyleSheet(button_style)

        self.next_btn = QPushButton("Next", self.frame)
        self.next_btn.setGeometry(200, 110, 80, 30)
        self.next_btn.clicked.connect(self.next_step)
        self.next_btn.setStyleSheet(button_style)

        self.update_step()

    def update_step(self):
        title, message, widget = self.steps[self.current]
        self.title.setText(title)
        self.message.setText(message)
        self.step_label.setText(f"{self.current + 1}/{len(self.steps)}")
        self.back_btn.setEnabled(self.current > 0)
        self.next_btn.setText("Done" if self.current == len(self.steps) - 1 else "Next")

        self.overlay.highlight(widget)

        # Move dialog next to the widget
        global_pos = widget.mapToGlobal(widget.rect().topRight())
        self.move(global_pos + QPoint(30, 0))

    def next_step(self):
        if self.current < len(self.steps) - 1:
            self.current += 1
            self.update_step()
        else:
            self.overlay.hide()
            self.close()

    def prev_step(self):
        if self.current > 0:
            self.current -= 1
            self.update_step()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walkthrough with Dropdown")
        self.setFixedSize(800, 600)

        self.btn1 = QPushButton("Step 1: Event", self)
        self.btn1.setGeometry(50, 80, 160, 40)

        self.dropdown = QComboBox(self)
        self.dropdown.setGeometry(250, 200, 160, 40)
        self.dropdown.addItems(["Option 1", "Option 2", "Option 3"])

        self.btn3 = QPushButton("Step 3: Start", self)
        self.btn3.setGeometry(50, 300, 160, 40)

        self.launch_btn = QPushButton("Launch Walkthrough", self)
        self.launch_btn.setGeometry(50, 400, 200, 40)
        self.launch_btn.clicked.connect(self.start_walkthrough)

    def start_walkthrough(self):
        steps = [
            ("Let’s Get Started!", "Click here to select an event.", self.btn1),
            (
                "Pick an Option",
                "Click the dropdown, then choose 'Option 2'.",
                self.dropdown,
            ),
            ("Ready to Go!", "Start your analysis here.", self.btn3),
        ]
        self.overlay = Overlay(self)
        self.overlay.show()
        self.dialog = StepDialog(self, steps, self.overlay)
        self.dialog.show()


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
