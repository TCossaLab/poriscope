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
from typing import override

from PySide6.QtCore import Slot
from SimpleCalcModel import SimpleCalcModel
from SimpleCalcView import SimpleCalcView

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class SimpleCalcController(MetaController):
    """
    A two-number calculator that plots its results.

    This is its Controller, which owns the tab's logic and connects its View to its Model.
    """

    logger = logging.getLogger(__name__)

    #: Declared with this tab's own types so the type checker sees
    #: the methods its View and Model add to the bases.
    view: SimpleCalcView
    model: SimpleCalcModel

    # public API
    @log(logger=logger)
    @Slot(float, str, float)
    @register_action("calculate", kind="additive", figure="results", skip_on_false=True)
    def calculate(self, left: float, operator: str, right: float) -> bool:
        """
        Compute one result and show every result so far.

        Recorded, so Save Session and Replay Actions rebuild the results. A refused
        calculation returns False and is not recorded.

        :param left: The first number.
        :type left: float
        :param operator: ``"+"`` or ``"-"``.
        :type operator: str
        :param right: The second number.
        :type right: float
        :return: False when the Model refused the calculation, True otherwise.
        :rtype: bool
        """
        if self.model.compute(left, operator, right) is None:
            self.add_text_to_display.emit(
                f"Calculation refused: at most {self.model.MAX_RESULTS} results; press Reset",
                self.__class__.__name__,
            )
            return False
        self.view.show_results(self.model.results)
        return True

    @log(logger=logger)
    @Slot()
    @register_action("reset", kind="reset", figure="results")
    def reset(self) -> None:
        """
        Forget every result and clear the plot.

        Recorded as a reset, so a saved session keeps only the calculations after it.
        """
        self.model.reset()
        self.view.show_results(self.model.results)

    @log(logger=logger)
    @override
    def clear_for_replay(self) -> None:
        """
        Forget the results as well as the figure, recording nothing, before a replay rebuilds them.
        """
        self.model.reset()
        self.view.show_results(self.model.results)

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Build this tab's View and Model, and do any other setup the tab needs.

        Assigning both ``self.view`` and ``self.model`` is required rather than
        conventional: the constructor calls this and then immediately connects the two to
        each other, so leaving either unset raises ``AttributeError`` before the tab
        exists. kwargs given to the base constructor are available as attributes by the
        time this runs.
        """
        self.view = SimpleCalcView()
        self.model = SimpleCalcModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Set up any local connections between the subordinate view and model
        """
        self.view.calculate_requested.connect(self.calculate)
        self.view.reset_requested.connect(self.reset)
