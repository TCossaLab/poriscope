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

from typing import Any, Dict, Optional, Sequence

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)


class MetaControls(QWidget):
    """
    Shared base for the control panels that sit above each analysis tab's plot.

    Every analysis tab owns a controls widget - ``ClusteringControls``,
    ``EventAnalysisControls``, ``MetadataControls``, ``ProteinControls`` and
    ``RawDataControls`` - which builds the tab's comboboxes, buttons and labels and
    turns user interaction into signals the tab's View connects to. Those five
    widgets were written by copy-paste and carried the same helpers verbatim; this
    base holds the shared half so there is one copy to fix.

    What a subclass inherits:

    - **Widget factories.** :meth:`createLabel`, :meth:`create_comboBox` and
      :meth:`createButton` build the three plain widgets every panel uses, with the
      font, size policy and translation call applied consistently.
    - **The placeholder guard.** :meth:`is_placeholder_item` and
      :meth:`toggle_info_button` keep a combobox's edit and delete buttons disabled
      until a real plugin is selected, reading the tab's own
      :attr:`placeholder_texts`.
    - **Signals.** ``actionTriggered`` carries a request into the tab's Controller as
      ``(submodel_name, action_name, args)``. ``add_processed``, ``edit_processed``
      and ``delete_processed`` carry plugin-management requests, and are emitted for
      the metaclass whose combobox the user acted on.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``. This base deliberately
      declares none, because every call in the family goes through ``self.logger``
      and resolves through the MRO - so a logger here would silently re-home every
      subclass's records to ``poriscope.utils.MetaControls``.
    - **Its own** :attr:`placeholder_texts`, or the placeholder guard above will read
      every combobox entry as a real selection.
    - ``setupUi``, ``connect_signals``, ``validate_inputs`` and ``collect_parameters``,
      which are genuinely per-tab and are called by the subclass's own ``__init__``.
    """

    actionTriggered = Signal(
        str, str, tuple
    )  # Signal to trigger an action in the controller (submodel_name, action_name, args)

    edit_processed = Signal(str, str)
    add_processed = Signal(str)
    delete_processed = Signal(str, str)

    #: Combobox texts that stand in for "nothing has been selected yet" on this tab -
    #: the placeholder each combobox shows before any plugin of its family exists.
    #: Every subclass sets its own. The empty default makes a panel that forgets to
    #: treat every entry as a real selection, which is how a panel with no
    #: placeholder text behaves anyway.
    placeholder_texts: Sequence[str] = ()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the shared state every controls panel needs.

        :param parent: Parent widget that owns these controls.
        :type parent: Optional[QWidget]
        """
        super().__init__(parent)
        self.active_popups: Dict[QComboBox, Any] = {}

    def is_placeholder_item(self, comboBox: QComboBox) -> bool:
        """
        Report whether the combobox's current text is this tab's "nothing here yet".

        :param comboBox: Combobox to inspect.
        :type comboBox: QComboBox
        :return: True when the selection is a placeholder rather than a real plugin.
        :rtype: bool
        """
        return comboBox.currentText() in self.placeholder_texts

    def toggle_info_button(self, button: QToolButton, comboBox: QComboBox) -> None:
        """
        Enable a combobox's edit or delete button only for a real selection.

        :param button: Button to enable or disable.
        :type button: QToolButton
        :param comboBox: Combobox the button acts on.
        :type comboBox: QComboBox
        """
        button.setEnabled(
            comboBox.count() > 0
            and comboBox.currentIndex() != -1
            and not self.is_placeholder_item(comboBox)
        )

    def show_plugin_edit_manager(self, comboBox: QComboBox, metaclass: str) -> None:
        """
        Ask the tab to open the plugin manager on the combobox's current selection.

        :param comboBox: Combobox whose current text names the plugin to edit.
        :type comboBox: QComboBox
        :param metaclass: Plugin family the combobox lists.
        :type metaclass: str
        """
        key = comboBox.currentText()
        self.edit_processed.emit(metaclass, key)

    def show_plugin_add_manager(self, comboBox: QComboBox, metaclass: str) -> None:
        """
        Ask the tab to open the plugin manager on a new plugin of this family.

        :param comboBox: Combobox the request came from; its selection is not read.
        :type comboBox: QComboBox
        :param metaclass: Plugin family to add to.
        :type metaclass: str
        """
        self.add_processed.emit(metaclass)

    def delete_plugin(self, comboBox: QComboBox, metaclass: str) -> None:
        """
        Ask the tab to delete the plugin the combobox currently names.

        :param comboBox: Combobox whose current text names the plugin to delete.
        :type comboBox: QComboBox
        :param metaclass: Plugin family the combobox lists.
        :type metaclass: str
        """
        key = comboBox.currentText()
        self.delete_processed.emit(metaclass, key)

    def clear_popup_reference(self, comboBox: QComboBox) -> None:
        """
        Forget a combobox's popup once it has closed.

        :param comboBox: Combobox whose popup has been dismissed.
        :type comboBox: QComboBox
        """
        if comboBox in self.active_popups:
            self.active_popups.pop(comboBox)

    def create_comboBox(self, parent: QWidget) -> QComboBox:
        """
        Build a combobox that expands to fill the width available to it.

        :param parent: Widget to parent the combobox to.
        :type parent: QWidget
        :return: The new combobox.
        :rtype: QComboBox
        """
        comboBox = QComboBox(parent)
        comboBox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return comboBox

    def createButton(
        self, parent: QWidget, text: str, bold: bool = False
    ) -> QPushButton:
        """
        Build a checkable push button carrying translated text.

        :param parent: Widget to parent the button to.
        :type parent: QWidget
        :param text: Untranslated button text.
        :type text: str
        :param bold: Whether to render the text bold.
        :type bold: bool
        :return: The new button.
        :rtype: QPushButton
        """
        button = QPushButton(parent)
        font = QFont()
        font.setBold(bold)
        font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        button.setFont(font)
        button.setText(QCoreApplication.translate("Form", text, None))
        button.setCheckable(True)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setStyleSheet("")  # Resetting to default style
        return button

    def createLabel(self, parent: QWidget, pointSize: int, text: str) -> QLabel:
        """
        Build a label carrying translated text at a size relative to ``pointSize``.

        :param parent: Widget to parent the label to.
        :type parent: QWidget
        :param pointSize: Nominal point size; the label is rendered six points smaller.
        :type pointSize: int
        :param text: Untranslated label text.
        :type text: str
        :return: The new label.
        :rtype: QLabel
        """
        label = QLabel(parent)
        font = QFont()
        font.setPointSize(pointSize - 6)
        label.setFont(font)
        label.setText(QCoreApplication.translate("Form", text, None))
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return label
