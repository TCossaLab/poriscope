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

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SelectionTree(QWidget):
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.selection_by_loader: Dict[str, Dict[str, List[str]]] = {}

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setCheckable(True)
        self.select_all_button.setStyleSheet(
            """
            QPushButton {
                border: 1px solid; 
                padding: 5px;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: lightgray;
            }
        """
        )
        self.select_all_button.toggled.connect(self.on_select_all_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.select_all_button)
        layout.addWidget(self.tree)

    def populate_tree(
        self,
        structure: dict[str, list[str]],
        loader_name: str,
        selected: Optional[dict[str, list[str]]] = None,
    ):
        # Use provided selection or default to cached or full select
        if selected is not None:
            selected_items = selected
        else:
            if loader_name not in self.selection_by_loader:
                selected_items = {
                    parent: list(children) for parent, children in structure.items()
                }
                self.selection_by_loader[loader_name] = selected_items
            else:
                selected_items = self.selection_by_loader[loader_name]

        self.tree.clear()

        for parent_name, children in structure.items():
            parent_item = QTreeWidgetItem([parent_name])
            parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)

            child_checked_states = []

            for child_name in children:
                child_item = QTreeWidgetItem([child_name])
                child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)

                is_checked = (
                    parent_name in selected_items
                    and child_name in selected_items[parent_name]
                )
                child_item.setCheckState(0, Qt.Checked if is_checked else Qt.Unchecked)
                child_checked_states.append(is_checked)

                parent_item.addChild(child_item)

            if all(child_checked_states):
                parent_item.setCheckState(0, Qt.Checked)
            elif any(child_checked_states):
                parent_item.setCheckState(0, Qt.PartiallyChecked)
            else:
                parent_item.setCheckState(0, Qt.Unchecked)

            self.tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(True)

        self.update_select_all_button()

    def on_item_changed(self, item, column):
        self.tree.blockSignals(True)

        if item.childCount() > 0:
            state = item.checkState(0)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, state)
        else:
            parent = item.parent()
            if parent:
                checked = sum(
                    parent.child(i).checkState(0) == Qt.Checked
                    for i in range(parent.childCount())
                )
                if checked == parent.childCount():
                    parent.setCheckState(0, Qt.Checked)
                elif checked == 0:
                    parent.setCheckState(0, Qt.Unchecked)
                else:
                    parent.setCheckState(0, Qt.PartiallyChecked)

        self.tree.blockSignals(False)
        self.update_select_all_button()

    def on_select_all_toggled(self, checked: bool):
        self.tree.blockSignals(True)
        state = Qt.Checked if checked else Qt.Unchecked

        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            parent.setCheckState(0, state)
            for j in range(parent.childCount()):
                parent.child(j).setCheckState(0, state)

        self.tree.blockSignals(False)
        self.update_select_all_button()

    def update_select_all_button(self):
        total = 0
        checked = 0
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                total += 1
                if parent.child(j).checkState(0) == Qt.Checked:
                    checked += 1

        if total == 0:
            self.select_all_button.setChecked(False)
            self.select_all_button.setText("Select All")
        elif checked == total:
            self.select_all_button.blockSignals(True)
            self.select_all_button.setChecked(True)
            self.select_all_button.setText("Deselect All")
            self.select_all_button.blockSignals(False)
        elif checked == 0:
            self.select_all_button.blockSignals(True)
            self.select_all_button.setChecked(False)
            self.select_all_button.setText("Select All")
            self.select_all_button.blockSignals(False)
        else:
            self.select_all_button.blockSignals(True)
            self.select_all_button.setChecked(False)
            self.select_all_button.setText("Select All")
            self.select_all_button.blockSignals(False)

    def get_selected(self) -> dict[str, list[str]]:
        selected = {}
        for i in range(self.tree.topLevelItemCount()):
            exp_item = self.tree.topLevelItem(i)
            exp_name = exp_item.text(0)

            selected_channels = []
            for j in range(exp_item.childCount()):
                ch_item = exp_item.child(j)
                if ch_item.checkState(0) == Qt.Checked:
                    selected_channels.append(ch_item.text(0))

            if selected_channels:
                selected[exp_name] = selected_channels

        return selected

    def show_dialog(
        self,
        structure: dict[str, list[str]],
        loader_name: str,
        title: str = "Select Channels",
        selected: Optional[dict[str, list[str]]] = None,
    ) -> dict[str, list[str]]:
        dialog = QDialog()
        dialog.setWindowFlags(Qt.Popup)
        dialog.setStyleSheet("QDialog { border-radius: 10px; }")
        dialog.setWindowTitle(title)

        # Create a new instance to avoid reparenting self
        selection_widget = SelectionTree()
        selection_widget.selection_by_loader = (
            self.selection_by_loader
        )  # share current state
        selection_widget.populate_tree(structure, loader_name, selected)

        layout = QVBoxLayout(dialog)
        layout.addWidget(selection_widget)
        dialog.setLayout(layout)

        # Center popup
        popup_width, popup_height = 300, 400
        window = QApplication.activeWindow()
        if window:
            center_x = window.geometry().center().x()
            center_y = window.geometry().center().y()
            x = center_x - popup_width // 2
            y = center_y - popup_height // 2
            dialog.setGeometry(x, y, popup_width, popup_height)

        dialog.exec()

        # Save selection state
        self.selection_by_loader[loader_name] = selection_widget.get_selected()
        return self.selection_by_loader[loader_name]
