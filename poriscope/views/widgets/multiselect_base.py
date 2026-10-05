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
# Kyle Briggs

"""
The half the two multi-select comboboxes share.

``MultiSelectComboBox`` and ``MultiSelectFilterComboBox`` are both a ``QComboBox`` whose
drop-down is replaced by a free-floating container holding a checkable ``QListWidget``.
Six methods were byte-identical between them - the popup geometry, the outside-click
teardown, the bulk item load and the display-text refresh - which is why a fix applied to
one of them could go missing from the other, and demonstrably did.

Those six live here. Everything about *what a row is* stays in the subclasses, because
that is the whole of the difference between them: the plain box holds a checkbox and a
label, while the filter box holds edit and delete buttons per row and carries the
callbacks they fire.
"""

import logging
from abc import abstractmethod
from typing import Iterable, List, Optional

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from poriscope.utils.QObjectABCMeta import QObjectABCMeta


class MultiSelectComboBoxBase(QComboBox, metaclass=QObjectABCMeta):
    """
    Shared behaviour for a combobox whose drop-down is a checkable list in a popup.

    A subclass owns its own ``__init__`` and builds the three widgets declared below;
    they are declared here rather than created here because the two subclasses build
    them differently - the plain box uses a frameless ``QWidget`` popup on Linux and a
    ``QDialog`` elsewhere, and the filter box uses a ``QDialog`` on every platform.

    ``logger`` is deliberately not declared here. Every call below goes through
    ``self.logger``, which resolves through the MRO to the subclass's own attribute, so
    each subclass keeps logging under its own module name.

    :ivar selectionChanged: emitted with the list of selected item labels whenever the checked set changes
    """

    selectionChanged = Signal(list)

    #: Built by the subclass: the checkable list the popup contains.
    listWidget: QListWidget
    #: Built by the subclass: the free-floating widget that stands in for the drop-down.
    containerWidget: QWidget
    #: Built by the subclass: the read-only line edit showing the current selection.
    _line_edit: QLineEdit
    #: Supplied by the subclass, so log records carry its module name.
    logger: logging.Logger

    # ------------------------------------------------------------------ shared

    def addItems(self, texts: Iterable[str]) -> None:
        """
        Replace the list's contents with ``texts``.

        ``itemChanged`` is disconnected across the rebuild so that populating N rows
        emits one selection change rather than N, and reconnected in a ``finally`` so a
        failure part-way through cannot leave the widget permanently deaf to edits.

        :param texts: the item labels to show, in order
        :type texts: Iterable[str]
        """
        try:
            self.listWidget.itemChanged.disconnect(
                self.handleItemChanged
            )  # Disconnect to prevent multiple triggers
            self.listWidget.clear()  # Clear all existing items
            for text in texts:
                self.addItem(text)

            self.handleItemChanged(None)  # refresh text + signal
        except Exception as e:
            self.logger.exception(f"Error while adding items: {e}")
        finally:
            self.listWidget.itemChanged.connect(
                self.handleItemChanged
            )  # Reconnect the signal

    def handleItemChanged(self, item: Optional[QListWidgetItem]) -> None:
        """
        Bring the display text, the select-all button and the signal back into step.

        :param item: the row whose check state changed, or None to refresh from scratch after a bulk load
        :type item: Optional[QListWidgetItem]
        """
        if item is None or item.checkState() in (Qt.Checked, Qt.Unchecked):
            selected_items = self.getSelectedItems()
            new_text = ", ".join(selected_items)
            self._line_edit.setText(new_text)
            if item is None or item.checkState() in (Qt.Checked, Qt.Unchecked):
                self.selectionChanged.emit(selected_items)
            self.updateSelectAllButton()  # Update without affecting individual selections

    def showPopup(self) -> None:
        """Centre the popup on the main window and start watching for clicks outside it."""
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
        self._set_outside_click_filter(True)

    def hidePopup(self) -> None:
        """Stop watching for outside clicks and hide the popup."""
        # Drop the filter before hiding: it is only meaningful while the popup
        # is up, and this is the single path every close goes through.
        self._set_outside_click_filter(False)
        # Hide the container widget when it should be closed
        self.containerWidget.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Toggle the popup, since the widget has no drop-down arrow of its own.

        :param event: the click Qt is delivering
        :type event: QMouseEvent
        """
        if self.containerWidget.isVisible():
            self.hidePopup()
        else:
            self.showPopup()
        super().mousePressEvent(event)

    def refreshDisplayText(self) -> None:
        """Rewrite the line edit from the current selection, without emitting anything."""
        self._line_edit.setText(", ".join(self.getSelectedItems()))

    # ------------------------------------------------- what a row is, per subclass

    @abstractmethod
    def addItem(self, text: str) -> None:
        """
        Append one row to the list.

        :param text: the label for the new row
        :type text: str
        """

    @abstractmethod
    def getSelectedItems(self) -> List[str]:
        """
        Report the labels of the checked rows, in list order.

        :return: the checked labels
        :rtype: List[str]
        """

    @abstractmethod
    def updateSelectAllButton(self) -> None:
        """Bring the select-all control into step with the current selection."""

    @abstractmethod
    def _set_outside_click_filter(self, active: bool) -> None:
        """
        Install or remove the application-wide filter that closes the popup.

        :param active: True while the popup is up, False once it is down
        :type active: bool
        """
