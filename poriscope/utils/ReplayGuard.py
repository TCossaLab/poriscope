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
import weakref
from typing import Any, Iterator, Protocol

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


# Something that may take an error a dialog would show: a running replay.
class ErrorCollector(Protocol):
    def take_error(self, text: str) -> bool:
        """
        Take an error, if still collecting.

        :param text: the error's text
        :type text: str
        :return: True if it was taken, so no dialog should show it
        :rtype: bool
        """
        ...


#: The replays that collect errors while they run, held weakly so a replay that is gone
#: collects nothing; the window's thread alone touches it.
_error_collectors: "weakref.WeakSet[Any]" = weakref.WeakSet()


def collect_errors(collector: ErrorCollector) -> None:
    """
    Offer every error a dialog would show to this collector, until told to stop.

    A running replay collects them, so its own question can say what its step reported
    instead of each error opening a dialog. Call it on the window's thread.

    :param collector: what takes each error, a running replay
    :type collector: ErrorCollector
    """
    _error_collectors.add(collector)


def stop_collecting_errors(collector: ErrorCollector) -> None:
    """
    Stop offering errors to this collector.

    :param collector: something passed to :py:func:`collect_errors`
    :type collector: ErrorCollector
    """
    _error_collectors.discard(collector)


def hold_back_error(text: str) -> bool:
    """
    Hand an error to every replay still collecting instead of a dialog, if any takes it.

    An error logged by a worker thread cannot be told apart by replay, so each collecting
    replay gets it. A collector decides for itself whether it still collects, so one that
    was never told to stop holds nothing back once it no longer runs. Call it on the
    window's thread.

    :param text: the error's text
    :type text: str
    :return: True if a replay took it, so no dialog should show it
    :rtype: bool
    """
    taken = [collector.take_error(text) for collector in list(_error_collectors)]
    return any(taken)


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
