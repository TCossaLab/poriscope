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

"""
A tripwire that refuses a widget read while a saved action is being replayed.

A recorded action must be a pure function of its recorded arguments: a replay has to
reproduce what the user did, not press the button again against whatever the panel shows
now. :py:meth:`~poriscope.utils.MetaController.MetaController.replay` runs inside
:py:func:`replaying`, and the helpers that read a controls panel call
:py:func:`forbid_while_replaying` first, so a recorded action that reaches one fails loudly
instead of quietly using today's widget values.

This is a module, not a flag on the View, because five of the seven helpers are the
panels' own ``collect_parameters``, and a panel holds no reference to a View or a
Controller. The switch is a ``contextvars`` variable: it is set only for the code running
inside the ``with`` block, and a worker thread starts without it.

It cannot see a direct ``.text()`` or ``.currentText()`` call on a widget; the static test
``test_recorded_actions_read_no_widgets`` is what covers those.
"""

import contextlib
import contextvars
from typing import Iterator, List

_replaying: contextvars.ContextVar[int] = contextvars.ContextVar(
    "poriscope_replaying", default=0
)


class ReplayWidgetReadError(RuntimeError):
    """A recorded action read a widget while it was being replayed."""


@contextlib.contextmanager
def replaying() -> Iterator[None]:
    """Mark the code inside the ``with`` block as replaying a saved action; nests."""
    token = _replaying.set(_replaying.get() + 1)
    try:
        yield
    finally:
        _replaying.reset(token)


#: The lists each running replay collects errors into, while it runs; the window's thread
#: alone touches it.
_error_collectors: List[List[str]] = []


def collect_errors(collector: List[str]) -> None:
    """
    Collect into this list every error a dialog would show, until told to stop.

    A running replay collects them, so its own question can say what its step reported
    instead of each error opening a dialog. Call it on the window's thread.

    :param collector: the list to append each error's text to
    :type collector: List[str]
    """
    if not any(existing is collector for existing in _error_collectors):
        _error_collectors.append(collector)


def stop_collecting_errors(collector: List[str]) -> None:
    """
    Stop collecting errors into this list.

    :param collector: a list passed to :py:func:`collect_errors`
    :type collector: List[str]
    """
    _error_collectors[:] = [
        existing for existing in _error_collectors if existing is not collector
    ]


def hold_back_error(text: str) -> bool:
    """
    Hand an error to every running replay instead of a dialog, if any replay is running.

    An error logged by a worker thread cannot be told apart by replay, so each running
    replay gets it. Call it on the window's thread.

    :param text: the error's text
    :type text: str
    :return: True if a replay took it, so no dialog should show it
    :rtype: bool
    """
    for collector in _error_collectors:
        collector.append(text)
    return bool(_error_collectors)


def is_replaying() -> bool:
    """
    Is a saved action being replayed?

    For a step that would ask the user something: a replay is not answered by the user, so
    it reports instead of asking.

    :return: True inside :py:func:`replaying`
    :rtype: bool
    """
    return bool(_replaying.get())


def forbid_while_replaying(name: str) -> None:
    """
    Raise if a saved action is being replayed; the first statement of a widget-reading helper.

    :param name: the helper that is about to read a widget, named in the error
    :type name: str
    :raises ReplayWidgetReadError: if called inside :py:func:`replaying`
    """
    if _replaying.get():
        raise ReplayWidgetReadError(
            f"{name} reads a widget, and a recorded action is being replayed: a replayed "
            f"action must take what it needs from its recorded arguments, not from the panel"
        )
