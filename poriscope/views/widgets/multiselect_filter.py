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

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from poriscope.configs.utils import get_icon


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
        self.edit_filter = lambda name: None
        self.delete_filter = lambda name: None

        # Disable vertical scrollbar, enable horizontal scrollbar as needed
        self.listWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Adding a container widget to hold title and list
        self.containerWidget = QDialog(None)
        self.containerWidget.setWindowFlags(
            Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.containerWidget.setWindowTitle("Select Filter")
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
        # self.listWidget.installEventFilter(self)  # Install an event filter on the list widget
        self.listWidget.itemChanged.connect(self.handleItemChanged)

        # Configure the embedded line edit
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select filters...")
        self.setInsertPolicy(QComboBox.NoInsert)

        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if self.containerWidget.isVisible():
                # Check if the click was outside the dialog
                if not self.containerWidget.geometry().contains(event.globalPos()):
                    self.logger.debug("Clicked outside containerWidget - closing")
                    self.containerWidget.close()
        return super().eventFilter(obj, event)

    def addItem(self, name, userData=None):
        item_widget = QWidget()
        layout = QHBoxLayout(item_widget)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(4)

        checkbox = QCheckBox(name)
        checkbox.stateChanged.connect(lambda _: self.handleItemChanged(None))
        layout.addWidget(checkbox)

        # Edit button
        edit_button = QToolButton()
        edit_button.setIcon(get_icon("edit.png"))
        edit_button.setIconSize(QSize(16, 16))
        edit_button.setStyleSheet("border: none; background: transparent;")
        edit_button.clicked.connect(lambda _, t=name: self._handle_internal_edit(t))
        layout.addWidget(edit_button)

        # Delete button
        delete_button = QToolButton()
        delete_button.setIcon(get_icon("trash.svg"))
        delete_button.setIconSize(QSize(16, 16))
        delete_button.setStyleSheet("border: none; background: transparent;")
        delete_button.clicked.connect(lambda _, t=name: self.delete_filter(t))
        layout.addWidget(delete_button)

        item = QListWidgetItem()
        item.setSizeHint(item_widget.sizeHint())
        item.setData(Qt.UserRole, name)

        self.listWidget.addItem(item)
        self.listWidget.setItemWidget(item, item_widget)

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
        checked = 0
        for i in range(total):
            widget = self.listWidget.itemWidget(self.listWidget.item(i))
            checkbox = widget.findChild(QCheckBox) if widget else None
            if checkbox and checkbox.isChecked():
                checked += 1
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
            widget = self.listWidget.itemWidget(item)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(state == Qt.Checked)

        self.listWidget.blockSignals(False)  # Unblock signals

        # Manually trigger handleItemChanged to update UI and emit signal
        self.handleItemChanged(None)  # None indicates a bulk update

        # Log all currently checked items
        checked_items = []
        for i in range(self.listWidget.count()):
            widget = self.listWidget.itemWidget(self.listWidget.item(i))
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    checked_items.append(checkbox.text())

        self.logger.info(f"All checked items after toggle: {checked_items}")

    def getSelectedItems(self):
        selected = []
        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            widget = self.listWidget.itemWidget(item)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    key = item.data(Qt.UserRole)
                    selected.append(key)
        self.logger.info(f"Selected items: {selected}")
        return selected

    def selectItem(self, text, select=True):
        for index in range(self.listWidget.count()):
            item = self.listWidget.item(index)
            widget = self.listWidget.itemWidget(item)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.text() == text:
                    checkbox.setChecked(select)
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

    def refreshDisplayText(self):
        self.lineEdit().setText(", ".join(self.getSelectedItems()))

    def _edit_button_clicked(self, checkbox):
        name = checkbox.text()
        if hasattr(self, "on_edit_filter"):
            self.on_edit_filter(name)
        else:
            self.logger.warning("No edit handler connected.")

    def _delete_button_clicked(self, checkbox):
        checkbox.text()

        for i in range(self.listWidget.count()):
            item = self.listWidget.item(i)
            widget = self.listWidget.itemWidget(item)
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb and cb is checkbox:
                    self.listWidget.takeItem(i)
                    break

        self.refreshDisplayText()

    def _handle_internal_edit(self, name):
        self.hidePopup()

        def open_dialog_then_reopen():
            self.edit_filter(name)
            QTimer.singleShot(0, self.showPopup)  # Reopen after edit

        QTimer.singleShot(0, open_dialog_then_reopen)

    def clear_selection_list(self):
        """
        Clear all filter items and reset the text display.
        """
        self.listWidget.clear()
        self.lineEdit().clear()
        self.selectAllButton.setChecked(False)
        self.selectAllButton.setText("Select All")
