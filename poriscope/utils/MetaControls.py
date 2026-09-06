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

from typing import Any, Dict, Optional

from PySide6.QtCore import QCoreApplication, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QSizePolicy, QWidget


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
    - **Signals.** ``actionTriggered`` carries a request into the tab's Controller as
      ``(submodel_name, action_name, args)``. ``add_processed``, ``edit_processed``
      and ``delete_processed`` carry plugin-management requests, and are emitted for
      the metaclass whose combobox the user acted on.

    What a subclass owes it:

    - **Its own** ``logger = logging.getLogger(__name__)``. This base deliberately
      declares none, because every call in the family goes through ``self.logger``
      and resolves through the MRO - so a logger here would silently re-home every
      subclass's records to ``poriscope.utils.MetaControls``.
    - ``setupUi``, ``connect_signals``, ``validate_inputs`` and ``collect_parameters``,
      which are genuinely per-tab and are called by the subclass's own ``__init__``.
    """

    actionTriggered = Signal(
        str, str, tuple
    )  # Signal to trigger an action in the controller (submodel_name, action_name, args)

    edit_processed = Signal(str, str)
    add_processed = Signal(str)
    delete_processed = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the shared state every controls panel needs.

        :param parent: Parent widget that owns these controls.
        :type parent: Optional[QWidget]
        """
        super().__init__(parent)
        self.active_popups: Dict[QComboBox, Any] = {}

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
