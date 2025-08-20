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

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class MultiSelectComboBox(QComboBox):
    selectionChanged = Signal(list)  # Signal to emit when the selection changes
    logger = logging.getLogger(__name__)

    def __init__(self, parent=None):
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
        self.containerWidget = QDialog(None)
        self.containerWidget.setWindowFlags(
            Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.containerWidget.setWindowTitle("Select Channel")
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
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select channels...")
        self.setInsertPolicy(QComboBox.NoInsert)

        QApplication.instance().installEventFilter(self)

    def addItem(self, text, userData=None):
        item = QListWidgetItem(text, self.listWidget)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)

    def addItems(self, texts):
        try:
            self.listWidget.itemChanged.disconnect(
                self.handleItemChanged
            )  # Disconnect to prevent multiple triggers
            self.listWidget.clear()  # Clear all existing items
            for text in texts:
                self.addItem(text)
        except Exception as e:
            self.logger.exception(f"Error while adding items: {e}")
        finally:
            self.listWidget.itemChanged.connect(
                self.handleItemChanged
            )  # Reconnect the signal

    def handleItemChanged(self, item):
        if item is None or item.checkState() in (Qt.Checked, Qt.Unchecked):
            selected_items = self.getSelectedItems()
            new_text = ", ".join(selected_items)
            self.lineEdit().setText(new_text)
            if item is None or item.checkState() in (Qt.Checked, Qt.Unchecked):
                self.selectionChanged.emit(selected_items)
            self.updateSelectAllButton()  # Update without affecting individual selections

    def updateSelectAllButton(self):
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

    def selectAllToggle(self, checked):
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

    def getSelectedItems(self):
        selected_items = []
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.checkState() == Qt.Checked:
                selected_items.append(item.text())
        self.logger.info(f"Selected items: {selected_items}")
        return selected_items

    def selectItem(self, text, select=True):
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            if item.text() == text:
                item.setCheckState(Qt.Checked if select else Qt.Unchecked)
                break

    def showPopup(self):
        window = self.window()  # Get the main window of the application
        window_geom = window.geometry()  # Get the geometry of the main window

        popup_width = 300  # Width of the popup
        popup_height = 400  # Height of the popup

        # Calculate the center of the window
        window_center_x = window_geom.x() + window_geom.width() // 2
        window_center_y = window_geom.y() + window_geom.height() // 2

        # Calculate the top-left corner of the popup to center it on the window
        popup_x = window_center_x - popup_width // 2
        popup_y = window_center_y - popup_height // 2

        # Set the container geometry and show
        self.containerWidget.setGeometry(
            QRect(popup_x, popup_y, popup_width, popup_height)
        )
        self.containerWidget.show()

    def hidePopup(self):
        # Hide the container widget when it should be closed
        self.containerWidget.hide()

    def mousePressEvent(self, event):
        if self.containerWidget.isVisible():
            self.hidePopup()
        else:
            self.showPopup()
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            # Only hide if the popup is visible and the click is outside it
            if self.containerWidget.isVisible():
                if not self.containerWidget.geometry().contains(event.globalPos()):
                    self.hidePopup()
                    return True  # Event handled
        return super().eventFilter(obj, event)

    def refreshDisplayText(self):
        self.lineEdit().setText(", ".join(self.getSelectedItems()))
