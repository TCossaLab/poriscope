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
# Poriscope contributors

import logging
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QGridLayout, QLineEdit, QWidget

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.MetaControls import MetaControls


@inherit_docstrings
class SimpleCalcControls(MetaControls):
    """
    Two number fields, an operator, and the buttons that add a calculation or reset.

    Built and placed by ``MetaView._set_control_area``, which also connects the
    four signals every controls panel carries.
    """

    logger = logging.getLogger(__name__)

    #: What a combobox of this tab's shows while it has nothing real to offer yet. The
    #: base's placeholder guard reads it to keep a plugin's edit and delete buttons
    #: disabled until a real selection is made, so leaving it empty makes every entry
    #: look like a real one.
    placeholder_texts: Tuple[str, ...] = ()

    #: The operators the Model knows how to apply.
    OPERATORS: Tuple[str, ...] = ("+", "-")

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Build the panel, wire it up, and settle the state of its widgets.

        :param parent: Widget that owns this panel.
        :type parent: Optional[QWidget]
        """
        super().__init__(parent)
        self.setupUi()
        self.connect_signals()
        self.validate_inputs()

    def setupUi(self) -> None:
        """
        Lay out this panel's widgets.

        The base builds the plain ones for you with the font and sizing already applied:
        ``createLabel``, ``create_comboBox`` and ``createButton``, plus
        ``create_info_button``, ``create_add_button`` and ``create_delete_button`` for the
        pencil, plus and trash buttons that sit beside a plugin combobox.
        """
        layout = QGridLayout(self)
        self.left_lineEdit = QLineEdit(self)
        self.left_lineEdit.setPlaceholderText("Value")
        self.left_lineEdit.setValidator(QDoubleValidator(self.left_lineEdit))
        self.operator_comboBox = self.create_comboBox(self)
        self.operator_comboBox.addItems(list(self.OPERATORS))
        self.right_lineEdit = QLineEdit(self)
        self.right_lineEdit.setPlaceholderText("Value")
        self.right_lineEdit.setValidator(QDoubleValidator(self.right_lineEdit))
        self.calculate_button = self.createButton(self, "Add Calculation", bold=True)
        self.reset_button = self.createButton(self, "Reset")
        self.results_label = self.createLabel(self, 16, "Results:")

        layout.addWidget(self.left_lineEdit, 0, 0)
        layout.addWidget(self.operator_comboBox, 0, 1)
        layout.addWidget(self.right_lineEdit, 0, 2)
        layout.addWidget(self.calculate_button, 0, 3)
        layout.addWidget(self.results_label, 1, 0, 1, 3)
        layout.addWidget(self.reset_button, 1, 3)

    def connect_signals(self) -> None:
        """
        Connect this panel's widgets to the handlers that turn them into requests.
        """
        self.calculate_button.clicked.connect(self._on_calculate_requested)
        self.reset_button.clicked.connect(self._on_reset_requested)
        self.left_lineEdit.textChanged.connect(self.validate_inputs)
        self.right_lineEdit.textChanged.connect(self.validate_inputs)

    def _on_calculate_requested(self) -> None:
        """
        Turn a press of Add Calculation into a request for the tab's Controller.

        ``actionTriggered`` is the signal that carries work out of this panel.
        ``MetaView._set_control_area`` connects it to the View's
        ``handle_parameter_change``, so the action name given here is the string that
        method has to recognise.
        """
        self.calculate_button.setChecked(False)
        self.actionTriggered.emit(
            self.__class__.__name__, "calculate", (self.collect_parameters(),)
        )

    def _on_reset_requested(self) -> None:
        """
        Turn a press of Reset into a request for the tab's Controller.
        """
        self.reset_button.setChecked(False)
        self.actionTriggered.emit(self.__class__.__name__, "reset", ({},))

    def validate_inputs(self) -> None:
        """
        Enable or disable this panel's widgets for the state it is now in.

        Called once at the end of construction and again whenever a selection changes, so
        a control the tab cannot honour yet is never offered.
        """
        self.calculate_button.setEnabled(
            self.left_lineEdit.hasAcceptableInput()
            and self.right_lineEdit.hasAcceptableInput()
        )

    def collect_parameters(self) -> Dict[str, Any]:
        """
        Read this panel's widgets into the arguments a request needs.

        Read here and sent with the signal rather than read by the Controller afterwards,
        because a request has to carry what was on screen when it was made.

        :return: The values the requested action needs.
        :rtype: Dict[str, Any]
        """
        return {
            "left": float(self.left_lineEdit.text()),
            "operator": self.operator_comboBox.currentText(),
            "right": float(self.right_lineEdit.text()),
        }

    def set_values(self, left: float, operator: str, right: float) -> None:
        """
        Show a calculation's numbers and operator in the panel, emitting nothing.

        :param left: The first number.
        :type left: float
        :param operator: The operator, one of ``OPERATORS``.
        :type operator: str
        :param right: The second number.
        :type right: float
        """
        self.left_lineEdit.setText(str(left))
        self.operator_comboBox.setCurrentText(operator)
        self.right_lineEdit.setText(str(right))

    def set_results(self, results: List[float]) -> None:
        """
        List the results so far under the number fields.

        :param results: Every result since the last reset, oldest first.
        :type results: List[float]
        """
        shown = "  ".join(f"[ {result:g} ]" for result in results)
        self.results_label.setText(f"Results: {shown}")
