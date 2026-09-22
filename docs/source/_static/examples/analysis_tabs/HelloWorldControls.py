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
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import QVBoxLayout, QWidget

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.MetaControls import MetaControls


@inherit_docstrings
class HelloWorldControls(MetaControls):
    """
    TODO: describe the controls the HelloWorld tab needs.

    Built and placed by ``MetaView._set_control_area``, which also connects the
    four signals every controls panel carries.
    """

    logger = logging.getLogger(__name__)

    #: What a combobox of this tab's shows while it has nothing real to offer yet. The
    #: base's placeholder guard reads it to keep a plugin's edit and delete buttons
    #: disabled until a real selection is made, so leaving it empty makes every entry
    #: look like a real one.
    placeholder_texts: Tuple[str, ...] = ()

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
        # TODO: replace this button with the controls your tab needs
        layout = QVBoxLayout(self)
        self.helloworld_button = self.createButton(self, "DO SOMETHING")
        layout.addWidget(self.helloworld_button)

    def connect_signals(self) -> None:
        """
        Connect this panel's widgets to the handlers that turn them into requests.
        """
        self.helloworld_button.clicked.connect(self._on_action_requested)

    def _on_action_requested(self) -> None:
        """
        Turn a button press into a request for the tab's Controller.

        ``actionTriggered`` is the signal that carries work out of this panel.
        ``MetaView._set_control_area`` connects it to the View's
        ``handle_parameter_change``, so the action name given here is the string that
        method has to recognise.
        """
        self.actionTriggered.emit(
            self.__class__.__name__, "do_something", (self.collect_parameters(),)
        )

    def validate_inputs(self) -> None:
        """
        Enable or disable this panel's widgets for the state it is now in.

        Called once at the end of construction and again whenever a selection changes, so
        a control the tab cannot honour yet is never offered.
        """
        # TODO: enable and disable your controls to match what is selected

    def collect_parameters(self) -> Dict[str, Any]:
        """
        Read this panel's widgets into the arguments a request needs.

        Read here and sent with the signal rather than read by the Controller afterwards,
        because a request has to carry what was on screen when it was made.

        :return: The values the requested action needs.
        :rtype: Dict[str, Any]
        """
        # TODO: read your controls into the dict your Controller expects
        return {}
