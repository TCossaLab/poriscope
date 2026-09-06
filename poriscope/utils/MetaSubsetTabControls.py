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
# Kyle Briggs

import logging
from typing import Any, List, Sequence

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QComboBox, QLineEdit, QToolButton, QWidget

from poriscope.configs.utils import get_icon
from poriscope.utils.MetaControls import MetaControls
from poriscope.views.widgets.multiselect_filter import MultiSelectFilterComboBox


class MetaSubsetTabControls(MetaControls):
    """
    Shared base for the control panels of the two subset-filtering analysis tabs.

    ``MetadataControls`` and ``ProteinControls`` build the same row of widgets above
    their tab's plot: a database-loader combobox, a multi-select filter combobox with
    its edit, add and delete buttons, and a bins field that switches between integer
    and float validation. The two were written by copy-paste and carried ten methods
    verbatim between them; this base holds that shared half so there is one copy to
    fix.

    It extends ``MetaControls`` rather than replacing it - the widget factories, the
    icon buttons and the placeholder guard all still come from there.

    What a subclass inherits, on top of everything ``MetaControls`` gives it:

    - **The filter combobox.** ``update_filters`` and ``get_selected_filter_names``
      read and repopulate it, and ``delete_filter_by_name`` and
      ``show_filter_info_dialog_single`` turn a click on one of its rows into a
      signal.
    - **The three filter buttons.** ``create_filter_info_button``,
      ``create_add_filter_button`` and ``create_filter_delete_button`` build the
      pencil, plus and trash buttons beside that combobox.
    - **The loader combobox.** ``update_loaders`` keeps it in step with the database
      loaders instantiated elsewhere in the app.
    - **Signals.** ``edit_filter_requested`` carries ``(filter_name, loader_name)``
      and ``delete_filter_requested`` carries a filter name, both into the tab's View.
    - **``placeholder_texts``**, which is ``("No Event Database",)`` for both tabs.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``, as ``MetaControls``
      already requires.
    - **A ``setupUi`` that builds** ``db_loader_comboBox``, ``filter_comboBox``,
      ``bins_lineEdit``, ``int_validator`` and ``float_validator``. They are declared
      below but not created here, because each tab lays its panel out differently.

    :ivar logger: the module logger the shared methods below log under
    """

    edit_filter_requested = Signal(str, str)
    delete_filter_requested = Signal(str)

    logger = logging.getLogger(__name__)

    #: Both subset tabs read their rows from a database loader, so the combobox
    #: placeholder is the same in each.
    placeholder_texts: Sequence[str] = ("No Event Database",)

    #: Built by each subclass's ``setupUi``, which lays its panel out differently.
    #: Declared here so the shared methods below have a contract to read.
    bins_lineEdit: QLineEdit
    db_loader_comboBox: QComboBox
    filter_comboBox: MultiSelectFilterComboBox
    float_validator: QRegularExpressionValidator
    int_validator: QRegularExpressionValidator

    def _on_sizes_checkbox_toggled(self, checked: bool) -> None:
        if checked:
            self.bins_lineEdit.setValidator(self.float_validator)
            self.bins_lineEdit.setPlaceholderText("e.g. 1.2, 3.5, 4.0")
        else:
            self.bins_lineEdit.setValidator(self.int_validator)
            self.bins_lineEdit.setPlaceholderText("e.g. 10 or 5,10,15")

    def create_filter_info_button(
        self, parent: QWidget, comboBox: MultiSelectFilterComboBox, tooltip: str
    ) -> QToolButton:
        button = QToolButton(parent)
        button.setIcon(get_icon("pencil-square.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton { border: none; background: transparent; }"
            "QToolTip { border: 1px solid palette(mid); background-color: palette(base); color: palette(text); padding: 2px; }"
        )
        button.setToolTip(tooltip)
        return button

    def create_add_filter_button(
        self, parent: QWidget, comboBox: MultiSelectFilterComboBox, tooltip: str
    ) -> QToolButton:
        button = QToolButton(parent)
        button.setIcon(get_icon("plus-square.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton { border: none; background: transparent; }"
            "QToolTip { border: 1px solid palette(mid); background-color: palette(base); color: palette(text); padding: 2px; }"
        )
        button.setToolTip(tooltip)
        return button

    def create_filter_delete_button(
        self, parent: QWidget, comboBox: MultiSelectFilterComboBox, tooltip: str
    ) -> QToolButton:
        button = QToolButton(parent)
        button.setIcon(get_icon("trash.svg"))
        button.setIconSize(QSize(16, 16))
        button.setStyleSheet(
            "QToolButton { border: none; background: transparent; }"
            "QToolTip { border: 1px solid palette(mid); background-color: palette(base); color: palette(text); padding: 2px; }"
        )
        button.setToolTip(tooltip)
        return button

    def show_filter_info_dialog_single(self, name: str) -> None:
        loader = self.db_loader_comboBox.currentText()
        self.edit_filter_requested.emit(name, loader)

    def delete_filter_by_name(self, name: str) -> None:
        self.delete_filter_requested.emit(name)

    def retranslateUi(self) -> None:
        pass

    def get_selected_filter_names(self) -> List[str]:
        return self.filter_comboBox.getSelectedItems()

    def update_loaders(self, loaders: list[str]) -> None:
        self.logger.info(f"Updating loaders: {loaders}")

        # Store current selection
        current_selection = self.db_loader_comboBox.currentText()
        self.db_loader_comboBox.clear()

        display_loaders = loaders if loaders else ["No Event Database"]
        self.db_loader_comboBox.addItems(display_loaders)

        # Restore selection if it still exists
        if current_selection in display_loaders:
            self.db_loader_comboBox.setCurrentText(current_selection)
        else:
            self.db_loader_comboBox.setCurrentIndex(0)

    def update_filters(self, filters: Sequence[Any]) -> None:
        self.logger.info(f"Updating channels to {filters}")

        # Store the current selection(s)
        current_selections = self.filter_comboBox.getSelectedItems()

        self.filter_comboBox.clear()
        self.filter_comboBox.addItems([str(i) for i in filters])

        # Restore selections if they still exist
        for selection in current_selections:
            if selection in [str(i) for i in filters]:
                self.filter_comboBox.selectItem(selection)
