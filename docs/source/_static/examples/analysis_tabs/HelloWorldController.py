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

from HelloWorldModel import HelloWorldModel
from HelloWorldView import HelloWorldView

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class HelloWorldController(MetaController):
    """
    TODO: describe what the HelloWorld tab does.

    This is its Controller, which owns the tab's logic and connects its View to its Model.
    """

    logger = logging.getLogger(__name__)

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
        self.view = HelloWorldView()
        self.model = HelloWorldModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Set up any local connections between the subordinate view and model
        """
        # TODO: implement _setup_connections
        pass
