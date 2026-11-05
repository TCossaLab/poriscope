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
One tab's replay of recorded actions, one entry at a time on the event loop.

Each entry is called on its own turn of the event loop, so the window stays responsive and
whatever an entry starts - a redraw, a background run - gets going before the next entry.
A ``result`` entry launches one plugin's run on one channel; the replay waits for that run
to end (:py:meth:`ReplaySequence.on_run_finished`) and carries on only if the run left a
finished channel with results. A run of that plugin on that channel that is already going
is waited out first, since launching another would be refused.

A replay stops at the first entry that fails: one that raises, one whose action returns
``False`` for a call that did nothing (its declaration's ``skip_on_false``), or a run that
did not finish or found nothing. An entry that names no action of the tab, or whose values
no longer fit it, is reported and skipped, as a synchronous replay does.

When an entry fails the user is asked whether to go back or keep. **Keep** leaves what was
replayed; the next start with no entries continues from the failed entry. **Go back** clears
the tab, resets each channel a replayed run filled, and replays the tab's history from
before the replay; if that fails too, the tab is left cleared, with no history.
"""

import functools
import inspect
import logging
from collections import OrderedDict
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Tuple

from PySide6.QtCore import QTimer

from poriscope.utils.LogDecorator import ACTION_DECLARATION_ATTR, ActionDeclaration
from poriscope.utils.ReplayGuard import replaying

if TYPE_CHECKING:
    # MetaController creates a ReplaySequence for every tab, so it imports this module.
    from poriscope.utils.MetaController import MetaController

logger = logging.getLogger(__name__)


class ReplaySequence:

    def __init__(self, controller: "MetaController") -> None:
        """
        :param controller: the tab whose actions are replayed; every step is scheduled with
            it as the timer's context, so a step left over once it is destroyed never runs
        :type controller: MetaController
        """
        self._controller = controller
        self._entries: List[Any] = []
        self._index = 0
        self._generation = 0
        self._launched = False
        self.running = False
        #: (plugin key, channel) of the run this replay waits on: its own, once launched,
        #: or one already going that its next entry would launch again.
        self.waiting_for: Optional[Tuple[str, int]] = None
        #: The position of the entry the last replay failed at, None if it did not fail.
        self.failed_at: Optional[int] = None
        #: The tab's history when the replay started, which going back replays.
        self._history_before: "OrderedDict[int, Any]" = OrderedDict()
        #: (metaclass, plugin key, channel) of each run the replay finished, which going
        #: back resets.
        self._finished_runs: List[Tuple[str, str, int]] = []
        self._going_back = False

    def start(self, entries: Optional[Iterable[Any]] = None) -> bool:
        """
        Start replaying, from the first of new entries or from where the last replay ended.

        :param entries: recorded entries, ``{"action": name, "args": [...], "kwargs": {...}}``;
            None continues the last replay from the entry it stopped or failed at
        :type entries: Optional[Iterable[Any]]
        :return: False if a replay is already running, or there is nothing left to continue
        :rtype: bool
        """
        if self.running:
            return False
        if entries is not None:
            self._entries = deepcopy(list(entries))
            self._index = 0
            if not self._going_back:
                self._history_before = deepcopy(self._controller.tab_action_history)
                self._finished_runs = []
        elif not self.has_remaining():
            return False
        self.failed_at = None
        self.running = True
        self._schedule()
        return True

    def has_remaining(self) -> bool:
        """
        Are there entries the last replay did not get to?

        :return: True if a replay stopped or failed before its last entry
        :rtype: bool
        """
        return self._index < len(self._entries)

    def stop(self, quitting: bool = False) -> None:
        """
        Stop the replay; the next :py:meth:`start` with no entries begins at the entry it was on.

        :param quitting: True when the application is closing, when nothing is written
        :type quitting: bool
        """
        if self.running:
            self._end(None if quitting else "replay stopped")

    def on_run_finished(self, channel: int, key: str) -> None:
        """
        Hear that one plugin's run on one channel ended; the Model's ``run_finished``.

        Only the run the replay waits on matters. If it was the replay's own, the replay
        carries on when the run finished with results and fails otherwise; if it was a run
        that was already going, the entry that waited for it is launched now.

        :param channel: the channel the run worked on
        :type channel: int
        :param key: the plugin's key
        :type key: str
        """
        if not self.running or self.waiting_for != (key, channel):
            return
        self.waiting_for = None
        if not self._launched:
            self._schedule()
            return
        self._launched = False
        if not self._left_results(key, channel):
            self._fail(
                f"{key} did not leave a finished run with results on channel {channel}"
            )
            return
        metaclass = self._controller.model.reporter_metaclasses.get(key, "")
        self._finished_runs.append((metaclass, key, channel))
        self._index += 1
        self._schedule()

    def _schedule(self) -> None:
        """Run the next step on a later turn of the event loop; an earlier one is dropped."""
        self._generation += 1
        QTimer.singleShot(
            0, self._controller, functools.partial(self._step, self._generation)
        )

    def _step(self, generation: int) -> None:
        """
        Replay the entry the sequence is on.

        :param generation: the scheduling this step came from; a step from before the
            replay ended or restarted, or from before a later scheduling, does nothing
        :type generation: int
        """
        if generation != self._generation:
            return
        if not self.has_remaining():
            self._end(
                "back to before the replay" if self._going_back else "replay done"
            )
            return
        resolved = self._controller.resolve_replayed_entry(self._entries[self._index])
        if resolved is None:
            self._index += 1
            self._schedule()
            return
        method, args, kwargs = resolved
        declaration: ActionDeclaration = getattr(method, ACTION_DECLARATION_ATTR)
        run = self._run_of(declaration, method, args, kwargs)
        if run is not None and self._run_going(run):
            self.waiting_for = run
            return
        try:
            with replaying():
                value = method(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Replaying {declaration.name} raised: {e!r}")
            self._fail(f"{declaration.name} raised {type(e).__name__}: {e}")
            return
        if value is False and declaration.skip_on_false:
            self._fail(f"{declaration.name} did nothing")
            return
        if run is not None:
            self.waiting_for = run
            self._launched = True
            return
        self._index += 1
        self._schedule()

    @staticmethod
    def _run_of(
        declaration: ActionDeclaration, method: Any, args: List[Any], kwargs: Any
    ) -> Optional[Tuple[str, int]]:
        """
        The (plugin key, channel) a result entry launches; None for any other entry.

        :param declaration: the entry's action declaration
        :type declaration: ActionDeclaration
        :param method: the bound method the entry calls
        :type method: Any
        :param args: its positional values
        :type args: List[Any]
        :param kwargs: its keyword values
        :type kwargs: Any
        :return: the run, or None
        :rtype: Optional[Tuple[str, int]]
        """
        if declaration.kind != "result":
            return None
        bound = inspect.signature(method).bind(*args, **kwargs)
        bound.apply_defaults()
        plugin, channel = (bound.arguments[name] for name in declaration.key)
        return plugin, channel

    def _run_going(self, run: Tuple[str, int]) -> bool:
        """
        Is a run of this plugin on this channel going, or ended without the tab hearing yet?

        :param run: (plugin key, channel)
        :type run: Tuple[str, int]
        :return: True if launching it now would be refused or confused with that run
        :rtype: bool
        """
        key, channel = run
        model = self._controller.model
        return bool(model.thread_running.get(key, {}).get(channel)) or (
            run in self._controller._held()
        )

    def _left_results(self, key: str, channel: int) -> bool:
        """
        Did the run that just ended leave a finished channel with results?

        A finder marks a channel finished only when it found events. A fitter marks it
        finished even when no fit was good, so its count is read too.

        :param key: the plugin's key
        :type key: str
        :param channel: the channel
        :type channel: int
        :return: True if the replay can carry on
        :rtype: bool
        """
        if not self._controller._run_finished_channel(key, channel):
            return False
        model = self._controller.model
        metaclass = model.reporter_metaclasses.get(key)
        if metaclass != "MetaEventFitter":
            return True
        try:
            return bool(model.call(metaclass, key, "get_num_events", channel))
        except Exception as e:
            logger.warning(
                f"Unable to count the fits of {key} on channel {channel}: {e}"
            )
            return False

    def _fail(self, reason: str) -> None:
        """
        Stop the replay at the entry it is on, say why, and ask whether to go back or keep.

        The panel line goes out first, so the tab's held lines - what the failed run
        reported - are on the panel before the question. Going back that fails is not
        asked about again: the tab is left cleared.

        :param reason: what went wrong with the entry
        :type reason: str
        """
        self.failed_at = self._index
        step, total = self._index + 1, len(self._entries)
        if self._going_back:
            self._end(
                f"going back stopped at step {step} of {total}: {reason}; the tab is "
                f"left cleared"
            )
            self._clear_tab()
            self._entries = []
            self._index = 0
            return
        self._end(f"replay stopped at step {step} of {total}: {reason}")
        action = str(self._entries[self._index].get("action"))
        name = self._controller.__class__.__name__
        choice = self._controller.view.ask_after_replay_failure(
            name, step, total, action, reason
        )
        if choice == "back":
            self._go_back()

    def _go_back(self) -> None:
        """Clear the tab and replay its history from before the replay."""
        name = self._controller.__class__.__name__
        self._controller.add_text_to_display.emit(
            f"{name}: going back to before the replay", name
        )
        entries = list(self._history_before.values())
        self._clear_tab()
        self._going_back = True
        self.start(entries)

    def _clear_tab(self) -> None:
        """Clear the tab, reset the channels the replay filled, and empty its history."""
        controller = self._controller
        controller.clear_for_replay()
        for metaclass, key, channel in self._finished_runs:
            try:
                controller.model.call(metaclass, key, "reset_channel", channel)
            except Exception as e:
                logger.warning(f"Unable to reset {key} channel {channel}: {e}")
        self._finished_runs = []
        controller.tab_action_history = OrderedDict()
        controller.update_tab_action_history.emit(
            controller.__class__.__name__, controller.tab_action_history
        )

    def _end(self, text: Optional[str]) -> None:
        """
        End the replay and, unless ``text`` is None, say how on the status panel.

        :param text: what to say after the tab's name
        :type text: Optional[str]
        """
        self.running = False
        self.waiting_for = None
        self._launched = False
        self._going_back = False
        self._generation += 1
        if text is not None:
            name = self._controller.__class__.__name__
            self._controller.add_text_to_display.emit(f"{name}: {text}", name)
