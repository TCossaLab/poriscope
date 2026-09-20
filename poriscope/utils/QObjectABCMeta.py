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
The metaclass that makes ``@abstractmethod`` work on a Qt class.

PySide6 does not honour abstractness on its own. A naive
``class Foo(QWidget, abc.ABC)`` cannot even be defined - Python raises a metaclass
conflict, because Shiboken gives every wrapped Qt type its own metaclass - and a class
built from a metaclass that merely inherits both still **instantiates while abstract
methods remain**, measured on PySide6 6.9.0. ``__call__`` below is the workaround: it is
what actually refuses, and it is the reason this module exists.

**One class serves both QObject and QWidget**, because ``type(QObject)`` and
``type(QWidget)`` are the same object - ``Shiboken.ObjectType`` - so the two metaclasses
this project used to carry were built from identical ingredients and were already
interchangeable. The ``QWidgetABCMeta`` name they were split under is gone; widget bases
such as :class:`poriscope.utils.MetaView.MetaView` declare this one.
"""

import abc
from typing import Any

from PySide6.QtCore import QObject


class QObjectABCMeta(abc.ABCMeta, type(QObject)):  # type: ignore[misc]
    def __call__(cls, *args: Any, **kw: Any) -> Any:
        # Load-bearing, and the whole point of the class: ABCMeta computes
        # __abstractmethods__ correctly here, but Shiboken's instantiation path does
        # not consult it, so without this an abstract subclass builds happily.
        if cls.__abstractmethods__:
            raise TypeError(
                f"Can't instantiate abstract class {cls.__name__} without an implementation for abstract methods {set(cls.__abstractmethods__)}"
            )
        return super().__call__(*args, **kw)
