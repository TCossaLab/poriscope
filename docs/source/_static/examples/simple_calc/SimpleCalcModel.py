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
from typing import List, Optional, override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class SimpleCalcModel(MetaModel):
    """
    A two-number calculator that keeps its last few results.

    This is its Model, which holds the tab's data and does its computation.
    """

    logger = logging.getLogger(__name__)

    #: How many results are kept before a calculation is refused.
    MAX_RESULTS = 5

    results: List[float]

    # public API
    @log(logger=logger)
    def compute(self, left: float, operator: str, right: float) -> Optional[float]:
        """
        Apply the operator to the two numbers and keep the result.

        :param left: The first number.
        :type left: float
        :param operator: ``"+"`` or ``"-"``.
        :type operator: str
        :param right: The second number.
        :type right: float
        :return: The result, or None when the limit is reached or the operator is unknown.
        :rtype: Optional[float]
        """
        if len(self.results) >= self.MAX_RESULTS:
            return None
        if operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        else:
            return None
        self.results.append(result)
        return result

    @log(logger=logger)
    def reset(self) -> None:
        """
        Forget every result.
        """
        self.results = []

    # private API, must be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Perform additional initialization specific to the algorithm being implemented.
        Must be implemented by subclasses.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        self.results = []
