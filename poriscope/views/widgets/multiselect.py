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
from typing import List, Optional

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.views.widgets.multiselect_base import MultiSelectComboBoxBase


class MultiSelectComboBox(MultiSelectComboBoxBase):
    logger = logging.getLogger(__name__)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.listWidget = QListWidget(self)
        self.listWidget.setAlternatingRowColors(True)
        self.listWidget.setSpacing(1)
        self.listWidget.setUniformItemSizes(True)
        self.listWidget.setSelectionMode(QAbstractItemView.MultiSelection)

        # Disable vertical scrollbar, enable horizontal scrollbar as needed
        self.listWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Adding a container widget to hold title and list
        if sys.platform == "linux":
            self.containerWidget = QWidget(None)
            self.containerWidget.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        else:
            self.containerWidget = QDialog(None)
            self.containerWidget.setWindowFlags(
                self.containerWidget.windowFlags() | Qt.Popup
            )
            self.containerWidget.setWindowTitle("Select Channel")

        if sys.platform != "linux":
            self.containerWidget.setStyleSheet(
                """
                QDialog {
                    border-radius: 10px;
                }
            """
            )

        # Create a layout for the container
        layout = QVBoxLayout(self.containerWidget)

        # Add select all button
        self.selectAllButton = QPushButton("Select All", self.containerWidget)
        self.selectAllButton.setCheckable(True)
        self.selectAllButton.setStyleSheet(
            """
            QPushButton {
                border: 1px solid ; 
                padding: 5px;
                border-radius: 5px;
            }
            QPushButton:checked {
                
            }
        """
        )
        self.selectAllButton.toggled.connect(self.selectAllToggle)
        layout.addWidget(self.selectAllButton)

        # Add the listWidget to the layout
        layout.addWidget(self.listWidget)

        # Handle item changes
        self.listWidget.itemChanged.connect(self.handleItemChanged)
        # self.listWidget.installEventFilter(self)  # Install an event filter on the list widget

        # Configure the embedded line edit
        self.setEditable(True)
        # lineEdit() only returns a widget once the combo is editable, which the
        # line above guarantees. Bind it here, where that invariant is actually
        # established, so the later uses do not each have to restate it.
        line_edit = self.lineEdit()
        if line_edit is None:  # pragma: no cover - unreachable while editable
            raise RuntimeError(
                "QComboBox.lineEdit() returned None despite setEditable(True)"
            )
        self._line_edit = line_edit
        self._line_edit.setReadOnly(True)
        self._line_edit.setPlaceholderText("Select channels...")
        self.setInsertPolicy(QComboBox.NoInsert)

    def addItem(self, text: str) -> None:
        item = QListWidgetItem(text, self.listWidget)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)

    def updateSelectAllButton(self) -> None:
        total = self.listWidget.count()
        checked = len(
            [
                item
                for item in (self.listWidget.item(i) for i in range(total))
                if item.checkState() == Qt.Checked
            ]
        )
        all_selected = checked == total
        none_selected = checked == 0

        self.selectAllButton.blockSignals(
            True
        )  # Block signals to avoid triggering toggle

        if all_selected:
            self.selectAllButton.setChecked(True)
            self.selectAllButton.setText("Deselect All")
        elif none_selected:
            self.selectAllButton.setChecked(False)
            self.selectAllButton.setText("Select All")
        else:
            # This handles the case where some but not all items are checked
            self.selectAllButton.setChecked(False)
            self.selectAllButton.setText("Select All")

        self.selectAllButton.blockSignals(False)  # Unblock signals

    def selectAllToggle(self, checked: bool) -> None:
        self.listWidget.blockSignals(True)  # Block signals on the entire list widget

        state = Qt.Checked if checked else Qt.Unchecked
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            item.setCheckState(state)  # Set the checked state for all items

        self.listWidget.blockSignals(False)  # Unblock signals

        # Manually trigger handleItemChanged to update UI and emit signal
        self.handleItemChanged(None)  # None indicates a bulk update

        # Log all currently checked items
        checked_items = [
            self.listWidget.item(i).text()
            for i in range(self.listWidget.count())
            if self.listWidget.item(i).checkState() == Qt.Checked
        ]
        self.logger.info(f"All checked items after toggle: {checked_items}")

    def getSelectedItems(self) -> List[str]:
        selected_items = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.Checked:
                selected_items.append(item.text())
        self.logger.info(f"Selected items: {selected_items}")
        return selected_items

    def selectItem(self, text: str, select: bool = True) -> None:
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.text() == text:
                item.setCheckState(Qt.Checked if select else Qt.Unchecked)
                break

    def _set_outside_click_filter(self, active: bool) -> None:
        """
        Install or remove the application-wide filter that closes the popup.

        The filter must sit on the application, not on ``containerWidget``. On
        Windows and macOS the container is built as a ``QDialog`` with
        ``Qt.Popup`` OR-ed into its flags, and ``Qt.Dialog | Qt.Popup``
        evaluates to ``Qt.Tool`` (window type is a value in the low byte, not
        a set of independent flags), so it is a tool window rather than a real
        popup and Qt's popup mouse grab never engages. Only the Linux branch,
        which *replaces* the flags, produces a genuine popup.

        It is installed only while the popup is open. Installing it in
        ``__init__`` instead is what previously leaked one filter per widget
        for the lifetime of the process, and let a filter outlive the C++
        object behind it.

        :param active: True to install the filter, False to remove it.
        :type active: bool
        """
        app = QApplication.instance()
        if app is None:
            return
        if active:
            app.installEventFilter(self)
        else:
            app.removeEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Close the popup when the user clicks outside it.

        :param obj: The object receiving the event; unused, since a click
            anywhere in the application is of interest.
        :type obj: QObject
        :param event: The event being delivered.
        :type event: QEvent
        :return: True if the event was consumed, False otherwise.
        :rtype: bool
        """
        if not self.containerWidget.isVisible():
            # Reached when the popup was closed by a path that does not run
            # hidePopup(). Drop the filter so it cannot outlive the popup.
            self._set_outside_click_filter(False)
            return False
        if event.type() == QEvent.MouseButtonPress:
            # Only hide if the click is outside the popup
            global_pos = event.globalPosition().toPoint()
            if not self.containerWidget.geometry().contains(global_pos):
                self.hidePopup()
                return True  # Event handled
        # QComboBox does not reimplement eventFilter, so the inherited
        # QObject::eventFilter is `return false` - which is all this needs to
        # be. Calling up into it requires a live C++ `self` and was the line
        # that raised "Internal C++ object already deleted" on a stale filter.
        return False
