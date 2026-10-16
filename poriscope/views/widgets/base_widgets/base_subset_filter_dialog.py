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
from typing import Collection, Optional

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from poriscope.configs.utils import get_icon

#: The info icon beside the mode buttons, tinted for the current theme like the add, edit
#: and delete buttons. Rendered large and scaled down, so it stays sharp on a high-resolution
#: screen.
INFO_ICON = "info-circle.svg"
INFO_ICON_RENDER_SIZE = 64
INFO_ICON_SIZE = 16

#: Grey example shown in the empty filter box, by mode.
ASSISTED_EXAMPLE = "duration > 150"
RAW_EXAMPLE = (
    "SELECT event_id, duration FROM events WHERE duration > 150 "
    "AND experiment_id = :experiment_id AND channel_id = :channel_id"
)
#: Said at the end of the grey example: Tab in the empty box inserts it.
TAB_HINT = "   (press Tab to insert)"
ASSISTED_PLACEHOLDER = f"e.g. {ASSISTED_EXAMPLE}{TAB_HINT}"
RAW_PLACEHOLDER = f"e.g. {RAW_EXAMPLE}{TAB_HINT}"

#: What the info mark beside the mode buttons says when hovered, by mode.
ASSISTED_INFO = (
    "<p>Write only the <b>condition</b>, for example <b>duration &gt; 150</b>. "
    "Poriscope adds the experiment and channel scope and chooses the columns for "
    "you.</p>"
    "<p>For more details, see <b>Help</b> → <b>Help</b> → <b>Documentation</b>, "
    "then <b>User Guide</b> → <b>Filtering and Querying</b> → "
    "<b>Assisted SQL filters</b>.</p>"
)
RAW_INFO = (
    "<p>To follow the <b>Scope selection</b>, add <b>WHERE experiment_id = "
    ":experiment_id AND channel_id = :channel_id</b>. Without it, the filter ignores "
    "the Scope selection.</p>"
    "<p>Start with <b>SELECT event_id, ...</b> so Plot Events and event plots work, "
    "unless the query uses DISTINCT, GROUP BY or UNION.</p>"
    "<p>For more details, see <b>Help</b> → <b>Help</b> → <b>Documentation</b>, "
    "then <b>User Guide</b> → <b>Filtering and Querying</b> → "
    "<b>Raw SQL filters</b>.</p>"
)


class BaseSubsetFilterDialog(QDialog):
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        existing_names: Collection[str],
        default_name: str = "",
        default_filter: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.existing_names = existing_names
        self.name: Optional[str] = None
        self.filter_text: Optional[str] = None
        self.is_raw: bool = False
        self.default_name = default_name
        self.default_filter = default_filter

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.name_input = QLineEdit(self.default_name)
        layout.addWidget(QLabel("Subset:"))
        layout.addWidget(self.name_input)

        # Mode selection: Assisted builds the query automatically,
        # Raw SQL passes the filter text directly to the database
        mode_layout = QHBoxLayout()
        self.assisted_radio = QRadioButton("Assisted SQL")
        self.raw_radio = QRadioButton("Raw SQL")
        self.assisted_radio.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.assisted_radio)
        self.mode_group.addButton(self.raw_radio)

        # One info icon after each mode, and only the chosen mode's is shown, so the icon
        # sits beside the mode it explains. They keep their space when hidden, so the
        # radio buttons do not move when the mode changes.
        self.assisted_info = self._info_icon(ASSISTED_INFO)
        self.raw_info = self._info_icon(RAW_INFO)
        mode_layout.addWidget(self.assisted_radio)
        mode_layout.addWidget(self.assisted_info)
        mode_layout.addWidget(self.raw_radio)
        mode_layout.addWidget(self.raw_info)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Pre-select mode based on existing suffix when editing,
        # and lock the radio buttons so mode cannot be changed after creation
        if self.default_name.endswith("_raw"):
            self.raw_radio.setChecked(True)
            self.assisted_radio.setEnabled(False)
            self.raw_radio.setEnabled(False)
        elif self.default_name.endswith("_assisted"):
            self.assisted_radio.setChecked(True)
            self.assisted_radio.setEnabled(False)
            self.raw_radio.setEnabled(False)

        self.filter_input = QTextEdit()
        self.filter_input.setPlainText(self.default_filter)
        self.filter_input.installEventFilter(self)
        self.raw_radio.toggled.connect(self._show_mode_hints)
        self._show_mode_hints(self.raw_radio.isChecked())
        layout.addWidget(QLabel("Filter:"))
        layout.addWidget(self.filter_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.try_accept)
        self.button_box.rejected.connect(self.reject)

    def _info_icon(self, tooltip: str) -> QLabel:
        """
        Build an info icon that says ``tooltip`` when hovered and keeps its space when hidden.

        :param tooltip: the text to show
        :type tooltip: str
        :return: the icon label
        :rtype: QLabel
        """
        icon = QLabel()
        icon.setPixmap(
            get_icon(INFO_ICON, size=INFO_ICON_RENDER_SIZE).pixmap(
                QSize(INFO_ICON_SIZE, INFO_ICON_SIZE), self.devicePixelRatioF()
            )
        )
        icon.setToolTip(tooltip)
        icon.setCursor(Qt.WhatsThisCursor)
        policy = icon.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        icon.setSizePolicy(policy)
        return icon

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Fill the empty filter box with the chosen mode's example when Tab is pressed.

        The grey example is only a hint, so Tab accepts it, as a terminal accepts a
        suggestion. With text in the box, Tab does what it always did.

        :param watched: the object the event is for
        :type watched: QObject
        :param event: the event
        :type event: QEvent
        :return: True if the event was handled here
        :rtype: bool
        """
        if (
            watched is self.filter_input
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Tab
            and not self.filter_input.toPlainText()
        ):
            self.filter_input.setPlainText(
                RAW_EXAMPLE if self.raw_radio.isChecked() else ASSISTED_EXAMPLE
            )
            self.filter_input.moveCursor(QTextCursor.MoveOperation.End)
            return True
        return super().eventFilter(watched, event)

    def _show_mode_hints(self, raw: bool) -> None:
        """
        Show the example and the info icon that belong to the chosen mode.

        :param raw: True when Raw SQL is chosen
        :type raw: bool
        """
        self.raw_info.setVisible(raw)
        self.assisted_info.setVisible(not raw)
        self.filter_input.setPlaceholderText(
            RAW_PLACEHOLDER if raw else ASSISTED_PLACEHOLDER
        )

    def try_accept(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing Name", "Please enter a name for the subset."
            )
            return

        if name != self.default_name and name in self.existing_names:
            reply = QMessageBox.question(
                self,
                "Subset Already Exists",
                f"A subset named '{name}' already exists.\n\nWould you like to override it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.name = name
        self.filter_text = self.filter_input.toPlainText().strip()
        self.is_raw = self.raw_radio.isChecked()
        self.accept()
