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


from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QWidget

"""
Walkthrough module for the Poriscope tutorial system.

Contains:
- IntroDialog: An introduction dialog that launches the tutorial.
- Overlay: A transparent overlay that highlights target widgets.
- StepDialog: A dialog that walks the user through key features step-by-step.
- start_walkthrough: Function to initialize and start the walkthrough.
"""


class IntroDialog(QDialog):
    """
    Welcome dialog to start the Poriscope walkthrough tutorial.

    :param parent: Parent widget, typically the main window.
    :type parent: QWidget
    :param current_step: Identifier for the current step (used to customize intro).
    :type current_step: str
    """

    start_walkthrough = Signal()

    def __init__(self, parent=None, current_step="MainView"):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        if parent:
            self.setGeometry(parent.geometry())

        palette = self.palette()
        bg_color = palette.color(QPalette.Window)
        text_color = palette.color(QPalette.WindowText)

        intro_text = self.parent().get_intro_text(current_step)

        self.frame = QFrame(self)
        self.frame.setFixedSize(520, 440)
        self.frame.move(
            (self.width() - self.frame.width()) // 2,
            (self.height() - self.frame.height()) // 2,
        )
        self.frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_color.name()};
                border-radius: 16px;
                border: 1px solid {text_color.name()};
            }}
        """
        )

        self.title = QLabel("Welcome to Poriscope's Tutorial", self.frame)
        self.title.setStyleSheet("border: none; background: none;")
        self.title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self.title.setGeometry(30, 20, 460, 30)
        self.title.setAlignment(Qt.AlignCenter)

        self.body = QLabel(self.frame)
        self.body.setFont(QFont("Segoe UI", 9))
        self.body.setWordWrap(True)
        self.body.setGeometry(30, 60, 460, 300)
        self.body.setStyleSheet("border: none;")
        self.body.setText(
            f"{intro_text}<br><br>"
            "You can launch this tutorial at any time, and it will start from the analysis step you are currently in – "
            "or walk you from the beginning if you just landed!<br><br>"
            "Analysis Steps: 1) Raw Data, 2) Event Analysis, 3) Metadata, 4) Clustering<br><br>"
            "You can exit at any point by clicking the ✕ on the top-right corner of the popups.<br><br>"
            "<b>Make sure you’ve followed the instructions before clicking Next – this is your opportunity to learn by doing.</b><br><br>"
            "Note: At the end of each 'analysis step', you can perform the action and automatically continue, or click 'Done' to exit early."
        )

        self.start_button = QPushButton("Let's get started !", self.frame)
        font = QFont("Segoe UI", 10)
        font.setBold(True)
        self.start_button.setFont(font)
        self.start_button.setGeometry(170, 390, 180, 34)
        self.start_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {text_color.name()};
                color: {bg_color.name()};
                font-size: 10pt;
                border-radius: 8px;
                border: 1px solid {text_color.name()};
            }}
            QPushButton:hover {{
                background-color: {bg_color.name()};
                color: {text_color.name()};
                border: 1px solid {text_color.name()};
            }}
        """
        )
        self.start_button.clicked.connect(self.emit_start)

    def paintEvent(self, event):
        """
        Paint a semi-transparent dark background behind the intro dialog.

        :param event: The paint event.
        :type event: QPaintEvent
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 130))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

    def emit_start(self):
        """
        Emit the signal to start the walkthrough and close the dialog.
        """
        self.start_walkthrough.emit()
        self.close()


class Overlay(QWidget):
    """
    Dark transparent overlay that highlights widgets during the walkthrough.

    :param parent: Parent widget over which the overlay is displayed.
    :type parent: QWidget
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.target_widgets = []

        parent.installEventFilter(self)
        self.setGeometry(parent.rect())

    def highlight(self, widgets):
        """
        Set the target widgets to be highlighted by the overlay.

        :param widgets: A widget or list of widgets to highlight.
        :type widgets: QWidget | list[QWidget]
        """
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        self.target_widgets = widgets
        self.update()

    def eventFilter(self, watched, event):
        """
        Update overlay geometry if the parent is resized or moved.

        :param watched: The object being watched.
        :type watched: QObject
        :param event: The triggered event.
        :type event: QEvent
        :return: True if the event is handled, False otherwise.
        :rtype: bool
        """
        if watched == self.parent() and event.type() in {QEvent.Resize, QEvent.Move}:
            self.setGeometry(self.parent().rect())
            self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        """
        Paint the dimmed background and highlight outlines around target widgets.

        :param event: The paint event.
        :type event: QPaintEvent
        """
        if not self.target_widgets:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Uniform overlay opacity
        opacity = 130
        painter.setBrush(QColor(0, 0, 0, opacity))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        # Determine pen color based on theme
        bg_color = self.palette().color(QPalette.Window)
        brightness = (
            0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()
        )
        pen_color = QColor("white") if brightness < 128 else QColor("black")

        painter.setPen(QPen(pen_color, 3))
        painter.setBrush(Qt.transparent)

        for widget in self.target_widgets:
            global_pos = widget.mapToGlobal(QPoint(0, 0))
            local_top_left = self.mapFromGlobal(global_pos)
            rect = QRect(local_top_left, widget.size()).adjusted(-4, -4, 4, 4)
            painter.drawRoundedRect(rect, 8, 8)


class StepDialog(QDialog):
    """Dialog that guides the user through steps using popups and an overlay."""

    done_signal = Signal()

    def __init__(self, parent, steps, overlay):
        """
        Initialize the step-by-step tutorial dialog.

        :param parent: Parent widget.
        :type parent: QWidget
        :param steps: List of (title, message, widget) tuples representing each step.
        :type steps: list[tuple[str, str, QWidget]]
        :param overlay: Overlay widget to highlight target areas.
        :type overlay: Overlay
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setVisible(False)
        self.steps = steps
        self.overlay = overlay
        self.current = 0
        self.target_widget = None
        self._last_pos = None
        self._was_completed = False

        palette = self.palette()
        bg_color = palette.color(QPalette.Window)
        text_color = palette.color(QPalette.WindowText)

        self.setFixedSize(320, 160)
        self.frame = QFrame(self)
        self.frame.setGeometry(0, 0, 320, 160)
        self.frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_color.name()};
                border-radius: 12px;
                border: 1px solid {text_color.name()};
            }}
        """
        )

        self.title = QLabel(self.frame)
        self.title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.title.setGeometry(20, 15, 280, 25)
        self.title.setStyleSheet("border: none; background: transparent;")

        self.message = QLabel(self.frame)
        self.message.setFont(QFont("Segoe UI", 9))
        self.message.setWordWrap(True)
        self.message.setGeometry(20, 45, 280, 60)
        self.message.setStyleSheet("border: none; background: transparent;")

        self.step_label = QLabel(self.frame)
        self.step_label.setGeometry(20, 115, 60, 20)
        self.step_label.setFont(QFont("Segoe UI", 9))
        self.step_label.setStyleSheet("border: none; background: transparent;")

        self.back_btn = QPushButton("Back", self.frame)
        self.back_btn.setGeometry(120, 110, 80, 30)
        self.back_btn.clicked.connect(self.prev_step)

        self.next_btn = QPushButton("Next", self.frame)
        self.next_btn.setGeometry(210, 110, 80, 30)
        self.next_btn.clicked.connect(self.next_step)

        for btn in (self.back_btn, self.next_btn):
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {text_color.name()};
                    color: {bg_color.name()};
                    padding: 6px;
                    border-radius: 6px;
                    border: 1px solid {text_color.name()};
                }}
                QPushButton:hover {{
                    background-color: {bg_color.name()};
                    color: {text_color.name()};
                    border: 1px solid {text_color.name()};
                }}
            """
            )

        self.close_btn = QPushButton("✕", self.frame)
        self.close_btn.setGeometry(290, 5, 20, 20)
        self.close_btn.setToolTip("Exit walkthrough")
        self.close_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {text_color.name()};
                border: none;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                color: red;
            }}
        """
        )
        self.close_btn.clicked.connect(self.force_close)

        self.reposition_timer = QTimer(self)
        self.reposition_timer.timeout.connect(self.reposition)
        self.reposition_timer.start(300)

        self.update_step()

    def _reposition_now(self):
        widgets = self.target_widget
        if not widgets:
            return

        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]

        widget = widgets[0]
        global_pos = widget.mapToGlobal(widget.rect().topRight())
        screen_geometry = self.screen().availableGeometry()

        new_x = min(global_pos.x() + 30, screen_geometry.right() - self.width() - 10)
        new_y = min(global_pos.y(), screen_geometry.bottom() - self.height() - 10)
        new_pos = QPoint(new_x, new_y)

        if self._last_pos != new_pos:
            self._last_pos = new_pos
            self.move(new_pos)

        if not self.isVisible():
            self.setVisible(True)

    def reposition(self):
        """
        Recalculate the dialog position and move it near the target widget.
        """
        self._reposition_now()

    def update_step(self):
        """
        Update the dialog to reflect the current tutorial step.
        """
        title, message, widget = self.steps[self.current]
        self.target_widget = widget
        self.title.setText(title)
        self.message.setText(message)
        self.step_label.setText(f"{self.current + 1}/{len(self.steps)}")
        self.back_btn.setVisible(self.current > 0)
        self.next_btn.setText("Done" if self.current == len(self.steps) - 1 else "Next")

        self.overlay.highlight(widget)
        self.overlay.setGeometry(self.parent().rect())
        self.overlay.update()

        self.setVisible(False)
        QTimer.singleShot(0, self._reposition_and_show)

    def _reposition_and_show(self):
        self._reposition_now()

    def next_step(self):
        """
        Advance to the next step. Closes the dialog if it's the last step.
        """
        if self.current < len(self.steps) - 1:
            self.current += 1
            self.update_step()
        else:
            self._was_completed = True
            self.reposition_timer.stop()
            self.overlay.hide()
            self.overlay.deleteLater()
            self.done_signal.emit()
            self.close()

    def prev_step(self):
        """
        Go back to the previous step.
        """
        if self.current > 0:
            self.current -= 1
            self.update_step()

    def force_close(self):
        """
        Forcefully close the walkthrough and clean up overlay.
        """
        self.reposition_timer.stop()
        self.overlay.hide()
        self.overlay.deleteLater()
        self.done_signal.emit()
        self.close()


def start_walkthrough(parent, steps):
    """
    Launch the StepDialog walkthrough with a given list of steps.

    :param parent: The parent widget to attach the walkthrough to.
    :type parent: QWidget
    :param steps: List of (title, message, widget) tuples describing the steps.
    :type steps: list[tuple[str, str, QWidget]]
    :return: The initialized StepDialog instance.
    :rtype: StepDialog
    """
    overlay = None

    try:
        overlay = Overlay(parent)
        overlay.show()
    except Exception:
        overlay = None

    try:
        dialog = StepDialog(parent, steps, overlay)
        dialog.show()
        return dialog
    except Exception:
        return QDialog(parent)  # Fallback dialog to avoid returning None
