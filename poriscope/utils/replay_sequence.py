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
One tab's replay of recorded actions, on the event loop.

A replay restores the state the recorded actions produced. The order and timing of the
steps are not part of that state: steps that do not depend on one another may run together,
or in a different order from the one they were recorded in, so that a restore takes no
longer than it must.

A ``result`` entry launches one plugin's run on one channel. Every run that nothing earlier
holds back is launched in the same turn of the event loop, as one click on several channels
launches them: a run waits only for an earlier run of its plugin on its channel, and for the
views drawn from that one. Every other entry keeps its recorded place among the entries
that are not runs, and one whose declaration names the run it is drawn from (``depends_on``)
waits for that run to end. Each is called on its own turn of the event loop, so the window
stays responsive and whatever it starts - a redraw, a background run - gets going first. A
run of the same plugin on the same channel that is already going is waited out, since
launching another would be refused. An entry that is not a run but starts background runs -
a view computed before it draws - ends once every run it started has ended, a turn of the
event loop later, so the tab has drawn before the next entry or "replay done"; runs that
were going before it are not its own. Such a step fails when the tab then says its work did
not finish (:py:meth:`~poriscope.utils.MetaController.MetaController.background_step_failure`).

When the replay ends, the panel shows the values of the last recorded step and the tab's
history lists the replayed entries in recorded order, whichever run ended first.

An entry fails when it raises, when its action returns ``False`` for a call that did
nothing (its declaration's ``skip_on_false``), or when its run did not finish or found
nothing. An entry that names no action of the tab, or whose values no longer fit it, is
reported and skipped, as a synchronous replay does.

From the first entry that fails, nothing new starts, and the user is asked at once whether
to go back or keep, with the runs still going left to go on; each later failure asks again.
**Keep** leaves what was replayed and lets those runs end; the next start with no entries
replays only the entries that were not. **Go back** stops the runs still going, then clears
the tab, resets each channel a replayed run filled, and replays the tab's history from
before the replay; if that fails too, the tab is left cleared, with no history.
"""

import functools
import inspect
import logging
from collections import OrderedDict
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)

import shiboken6
from PySide6.QtCore import QTimer

from poriscope.utils.LogDecorator import ACTION_DECLARATION_ATTR, ActionDeclaration
from poriscope.utils.ReplayGuard import (
    collect_errors,
    replaying,
    stop_collecting_errors,
)

if TYPE_CHECKING:
    # MetaController creates a ReplaySequence for every tab, so it imports this module.
    from poriscope.utils.MetaController import MetaController

logger = logging.getLogger(__name__)

#: A background run: the plugin's key and the channel it works on.
Run = Tuple[str, int]


class ReplaySequence:

    def __init__(self, controller: "MetaController") -> None:
        """
        :param controller: the tab whose actions are replayed; every step is scheduled with
            it as the timer's context, so a step left over once it is destroyed never runs
        :type controller: MetaController
        """
        self._controller = controller
        self._entries: List[Any] = []
        #: The positions of the entries that have been replayed, or reported and skipped.
        self._done: Set[int] = set()
        #: The positions that failed in this replay; nothing that waits for one starts.
        self._failed: Set[int] = set()
        #: What each entry launches and what it is drawn from, read once per entry.
        self._needs: Dict[int, Tuple[Optional[Run], Optional[Run]]] = {}
        #: Counts the starts and ends of this replay, so a turn scheduled before one does
        #: nothing after it.
        self._epoch = 0
        self._turn_pending = False
        self.running = False
        #: (plugin key, channel) of each run this replay launched and has not heard end,
        #: with the position of its entry.
        self.runs: Dict[Run, int] = {}
        #: (plugin key, channel) of each run that was already going when an entry would
        #: have launched it again, with the position of the entry waiting for it to end.
        self.waiting: Dict[Run, int] = {}
        #: The position of the step whose background runs the replay is waiting for.
        self._step_waiting: Optional[int] = None
        #: (plugin key, channel) of each background run the step it is on started and has
        #: not heard end yet, for a step that is not a result: a view computed before it
        #: draws, say.
        self.started_runs: Set[Run] = set()
        #: The position of the first entry the last replay failed at, None if none did.
        self.failed_at: Optional[int] = None
        #: Whether a step has failed, after which nothing new starts.
        self._stopped = False
        #: Whether the question a failure asks is open, and the failures waiting their turn.
        self._asking = False
        self._to_ask: List[Tuple[int, str]] = []
        #: Whether the user chose to go back and the runs still going are being stopped.
        self._back_pending = False
        #: The tab's history when the replay started, which going back replays.
        self._history_before: "OrderedDict[int, Any]" = OrderedDict()
        #: (metaclass, plugin key, channel) of each run the replay finished, which going
        #: back resets.
        self._finished_runs: List[Tuple[str, str, int]] = []
        self._going_back = False
        #: Whether the entries are the actions the tab was loaded with, which the autosave
        #: holds only once they have run.
        self.from_session = False
        #: Whether the restore dialog started this run, not the user.
        self.restore = False
        #: Whether the replay going back was one of the loaded actions.
        self._back_from_session = False
        #: The errors logged since the last step that ran with no run going, shown in the
        #: question a failure asks.
        self._step_errors: List[str] = []
        #: The history entries each position recorded, to put them in recorded order.
        self._recorded: Dict[int, List[Any]] = {}
        #: What each started position showed in the panel, to show it again in order.
        self._written: Dict[int, Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = {}
        #: Whether an entry started before an earlier one had been replayed.
        self._out_of_order = False

    def start(
        self,
        entries: Optional[Iterable[Any]] = None,
        from_session: bool = False,
        restore: bool = False,
    ) -> bool:
        """
        Start replaying new entries, or the entries the last replay did not finish.

        :param entries: recorded entries, ``{"action": name, "args": [...], "kwargs": {...}}``;
            None continues the last replay with the entries it stopped before or failed at
        :type entries: Optional[Iterable[Any]]
        :param from_session: the entries are the actions the tab was loaded with
        :type from_session: bool
        :param restore: the restore dialog started it; a start of its own, Replay
            Actions continuing it included, is the user's
        :type restore: bool
        :return: False if a replay is already running, or there is nothing left to continue
        :rtype: bool
        """
        if self.running:
            return False
        if entries is not None:
            self._entries = deepcopy(list(entries))
            self._done = set()
            self._needs = {}
            self._recorded = {}
            self._written = {}
            self._out_of_order = False
            self.from_session = from_session
            if not self._going_back:
                self._history_before = deepcopy(self._controller.tab_action_history)
                self._finished_runs = []
        elif not self.has_remaining():
            return False
        self._failed = set()
        self._stopped = False
        self._to_ask = []
        self._back_pending = False
        self._step_errors = []
        self.failed_at = None
        self.restore = restore
        self.running = True
        self._epoch += 1
        self._turn_pending = False
        collect_errors(self)
        self._controller.replay_state_changed.emit(False)
        self._schedule()
        return True

    def replay_available(self) -> bool:
        """
        Has this replay something Replay Actions would replay?

        Entries left to continue, or the tab's loaded actions, until they have been replayed
        to the end.

        :return: True if Replay Actions would start or continue a replay
        :rtype: bool
        """
        return self.has_remaining() or (
            self._controller.holds_session_actions()
            and not self.replayed_session_to_the_end()
        )

    def replayed_session_to_the_end(self) -> bool:
        """
        Did the last replay replay the tab's loaded actions to the end?

        :return: True once the loaded actions have all been replayed, until another replay
            starts, going back included
        :rtype: bool
        """
        return (
            self.from_session
            and not self.running
            and self.failed_at is None
            and not self.has_remaining()
        )

    def rewrite_entries(
        self, rewrite: Callable[[List[Any]], Tuple[List[Any], bool]]
    ) -> bool:
        """
        Apply a rewrite to the entries not replayed yet and to the history going back rebuilds.

        An entry a running replay has started is left alone, so the replay stays where it
        is; the entries already replayed are history already.

        :param rewrite: takes entries, gives back the rewritten ones and whether any changed
        :type rewrite: Callable[[List[Any]], Tuple[List[Any], bool]]
        :return: True if anything changed
        :rtype: bool
        """
        started = self._done | set(self.runs.values()) | set(self.waiting.values())
        if self._step_waiting is not None:
            started.add(self._step_waiting)
        entries: List[Any] = []
        moved: Dict[int, int] = {}
        later_changed = False
        for position, entry in enumerate(self._entries):
            if position in started:
                kept = [entry]
            else:
                kept, changed = rewrite([entry])
                later_changed = later_changed or changed
            if kept:
                moved[position] = len(entries)
                entries.extend(kept)
        if later_changed:
            self._entries = entries
            self._renumber(moved)
        before, before_changed = rewrite(list(self._history_before.values()))
        if before_changed:
            self._history_before = OrderedDict(enumerate(before))
        return later_changed or before_changed

    def _renumber(self, moved: Dict[int, int]) -> None:
        """
        Follow the entries to their new positions after some were dropped.

        :param moved: old position -> new position, for each entry kept
        :type moved: Dict[int, int]
        """
        self._done = {moved[p] for p in self._done if p in moved}
        self._failed = {moved[p] for p in self._failed if p in moved}
        self.runs = {run: moved[p] for run, p in self.runs.items()}
        self.waiting = {run: moved[p] for run, p in self.waiting.items()}
        if self._step_waiting is not None:
            self._step_waiting = moved[self._step_waiting]
        if self.failed_at is not None:
            self.failed_at = moved.get(self.failed_at)
        self._recorded = {moved[p]: e for p, e in self._recorded.items() if p in moved}
        self._written = {moved[p]: w for p, w in self._written.items() if p in moved}
        self._to_ask = [(moved[p], why) for p, why in self._to_ask if p in moved]
        self._needs = {}

    def take_error(self, text: str) -> bool:
        """
        Keep an error the step logged, for the question a failure asks, while running.

        :param text: the error's text
        :type text: str
        :return: True if taken: the replay is running and its tab still exists
        :rtype: bool
        """
        if not self.running or not shiboken6.isValid(self._controller):
            return False
        self._step_errors.append(text)
        return True

    def has_remaining(self) -> bool:
        """
        Are there entries the last replay did not replay?

        :return: True if a replay stopped or failed before every entry was replayed
        :rtype: bool
        """
        return len(self._done) < len(self._entries)

    def launched(self, key: str, channel: int) -> bool:
        """
        Is a run of this plugin on this channel one this replay launched and still waits for?

        :param key: the plugin's key
        :type key: str
        :param channel: the channel
        :type channel: int
        :return: True from the entry's launch until the replay has heard the run end
        :rtype: bool
        """
        return self.running and (key, channel) in self.runs

    def holds_panel_text(self) -> bool:
        """
        Should the tab's status-panel lines be held back until the replay ends?

        :return: True while the replay runs and no step of it has failed; once the question
            is asked, its lines are shown as they come
        :rtype: bool
        """
        return self.running and not self._stopped

    def stop(self, quitting: bool = False) -> None:
        """
        Stop the replay; the next :py:meth:`start` with no entries replays what it had not.

        :param quitting: True when the application is closing, when nothing is written
        :type quitting: bool
        """
        if self.running:
            self._end(None if quitting else "replay stopped")

    def on_run_finished(self, channel: int, key: str) -> None:
        """
        Hear that one plugin's run on one channel ended; the Model's ``run_finished``.

        Only a run the replay waits on matters. One it launched is replayed if it finished
        with results, and fails otherwise. One that was already going frees the entry that
        waited for it. If it was the last of the runs a step started, the step ends on the
        next turn of the event loop, once the tab has heard the run end too.

        :param channel: the channel the run worked on
        :type channel: int
        :param key: the plugin's key
        :type key: str
        """
        if not self.running:
            return
        run = (key, channel)
        if run in self.started_runs:
            self.started_runs.discard(run)
            if not self.started_runs:
                QTimer.singleShot(
                    0,
                    self._controller,
                    functools.partial(self._background_ended, self._epoch),
                )
            return
        if self.waiting.pop(run, None) is not None:
            self._schedule()
            return
        position = self.runs.pop(run, None)
        if position is None:
            return
        if self._controller._run_finished_channel(key, channel):
            metaclass = self._controller.model.reporter_metaclasses.get(key, "")
            self._finished_runs.append((metaclass, key, channel))
            self._done.add(position)
            self._schedule()
            return
        self._recorded.pop(position, None)
        self._fail(
            position,
            f"{key} did not leave a finished run with results on channel {channel}",
        )

    def _schedule(self) -> None:
        """Take a turn on a later turn of the event loop, unless one is already to come."""
        if self._turn_pending:
            return
        self._turn_pending = True
        QTimer.singleShot(
            0, self._controller, functools.partial(self._step, self._epoch)
        )

    def _step(self, epoch: int) -> None:
        """
        Take one turn: run the next step that is not a run if no run free to start comes
        before it, else launch every run that is free to start.

        :param epoch: the start of the replay this turn was scheduled in; a turn from
            before the replay ended or restarted does nothing
        :type epoch: int
        """
        if epoch != self._epoch:
            return
        self._turn_pending = False
        if self._stopped:
            self._end_if_idle()
            return
        free = self._free_runs()
        position = self._free_step()
        if position is not None and (not free or position < free[0][0]):
            self._run_step(position)
            return
        if free:
            for run_position, run in free:
                if not self._launch(run_position, run):
                    return
            self._schedule()
            return
        self._end_if_idle()

    def _needs_of(self, position: int) -> Tuple[Optional[Run], Optional[Run]]:
        """
        The run an entry launches and the run it is drawn from, without reporting anything.

        :param position: the entry's position
        :type position: int
        :return: the run a result launches, else None; the run a view's ``depends_on``
            names, else None. Both None for an entry that cannot be read
        :rtype: Tuple[Optional[Run], Optional[Run]]
        """
        if position not in self._needs:
            self._needs[position] = self._read_needs(self._entries[position])
        return self._needs[position]

    def _read_needs(self, entry: Any) -> Tuple[Optional[Run], Optional[Run]]:
        """
        Read what :py:meth:`_needs_of` answers from an entry and its action's declaration.

        :param entry: a recorded entry
        :type entry: Any
        :return: the run it launches, the run it is drawn from
        :rtype: Tuple[Optional[Run], Optional[Run]]
        """
        name = entry.get("action") if isinstance(entry, Mapping) else None
        method = (
            self._controller.action_registry().get(name)
            if isinstance(name, str)
            else None
        )
        if method is None:
            return None, None
        declaration: ActionDeclaration = getattr(method, ACTION_DECLARATION_ATTR)
        names = declaration.key if declaration.kind == "result" else ()
        try:
            bound = inspect.signature(method).bind(
                *(entry.get("args") or []), **(entry.get("kwargs") or {})
            )
        except TypeError:
            return None, None
        bound.apply_defaults()
        return (
            self._named_run(bound.arguments, names),
            self._named_run(bound.arguments, declaration.depends_on),
        )

    @staticmethod
    def _named_run(values: Mapping[str, Any], names: Tuple[str, ...]) -> Optional[Run]:
        """
        The run two of an action's parameters name, its plugin and then its channel.

        :param values: the entry's values, each under its parameter name
        :type values: Mapping[str, Any]
        :param names: the plugin parameter and the channel parameter, or none
        :type names: Tuple[str, ...]
        :return: (plugin key, channel), or None when no parameters are named
        :rtype: Optional[Run]
        """
        if len(names) != 2:
            return None
        return values[names[0]], values[names[1]]

    def _blocked(self, position: int) -> bool:
        """
        Must an entry wait for an earlier one that has not been replayed?

        A run waits for an earlier run of its plugin on its channel and for the views drawn
        from that one. Any other step waits for the earlier steps that are not runs, so they
        keep their order, and for the run it is drawn from.

        :param position: the entry's position
        :type position: int
        :return: True if an earlier entry it depends on is not done
        :rtype: bool
        """
        launches, drawn_from = self._needs_of(position)
        for earlier in range(position):
            if earlier in self._done:
                continue
            earlier_launches, earlier_drawn_from = self._needs_of(earlier)
            if launches is not None:
                if launches in (earlier_launches, earlier_drawn_from):
                    return True
            elif earlier_launches is None or earlier_launches == drawn_from:
                return True
        return False

    def _started(self, position: int) -> bool:
        """
        Has an entry been replayed, or is the replay waiting on it?

        :param position: the entry's position
        :type position: int
        :return: True if it is not to be started now
        :rtype: bool
        """
        return (
            position in self._done
            or position in self._failed
            or position == self._step_waiting
            or position in self.runs.values()
            or position in self.waiting.values()
        )

    def _free_runs(self) -> List[Tuple[int, Run]]:
        """
        The runs that can be launched now, in recorded order.

        :return: the position and the run of each result entry nothing earlier holds back
        :rtype: List[Tuple[int, Run]]
        """
        free: List[Tuple[int, Run]] = []
        for position in range(len(self._entries)):
            run = self._needs_of(position)[0]
            if (
                run is not None
                and not self._started(position)
                and not self._blocked(position)
            ):
                free.append((position, run))
        return free

    def _free_step(self) -> Optional[int]:
        """
        The position of the next step that is not a run, if it can run now.

        :return: the position, or None while the step before it or the run it is drawn
            from has not ended
        :rtype: Optional[int]
        """
        for position in range(len(self._entries)):
            if position in self._done or self._needs_of(position)[0] is not None:
                continue
            if self._started(position) or self._blocked(position):
                return None
            return position
        return None

    def _call(self, position: int) -> Optional[bool]:
        """
        Show an entry's values in the panel and call its action.

        :param position: the entry's position
        :type position: int
        :return: True if the call went through, False if it failed; None for an entry
            that cannot be replayed, which is reported and counts as replayed
        :rtype: Optional[bool]
        """
        resolved = self._controller.resolve_replayed_entry(self._entries[position])
        if resolved is None:
            self._done.add(position)
            return None
        method, args, kwargs = resolved
        declaration: ActionDeclaration = getattr(method, ACTION_DECLARATION_ATTR)
        if any(p not in self._done for p in range(position)):
            self._out_of_order = True
        self._written[position] = (declaration.name, tuple(args), kwargs)
        before = {id(entry) for entry in self._controller.tab_action_history.values()}
        try:
            with replaying():
                # The panel shows what the step ran with, so a restored tab shows the values
                # that produced its result and the next click starts from them.
                self._controller.view.write_back(declaration.name, tuple(args), kwargs)
                value = method(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Replaying {declaration.name} raised: {e!r}")
            self._fail(position, f"{declaration.name} raised {type(e).__name__}: {e}")
            return False
        if value is False and declaration.skip_on_false:
            self._fail(position, f"{declaration.name} did nothing")
            return False
        self._recorded[position] = [
            entry
            for entry in self._controller.tab_action_history.values()
            if id(entry) not in before
        ]
        return True

    def _launch(self, position: int, run: Run) -> bool:
        """
        Launch the run of a result entry, or wait out one already going on its channel.

        :param position: the entry's position
        :type position: int
        :param run: the run the entry launches
        :type run: Run
        :return: False if the launch failed, when the turn ends
        :rtype: bool
        """
        if self._run_going(run):
            self.waiting[run] = position
            return True
        called = self._call(position)
        if not called:
            return called is None
        self.runs[run] = position
        # The run is recorded once it ends, from the entry held for it meanwhile.
        held = self._controller._held().get(run)
        self._recorded[position] = [] if held is None else [held]
        return True

    def _run_step(self, position: int) -> None:
        """
        Run a step that is not a result, and wait for any background runs it starts.

        :param position: the entry's position
        :type position: int
        """
        if not self.runs:
            self._step_errors.clear()
        going_before = self._runs_going()
        called = self._call(position)
        if called is not None:
            if not called:
                return
            self.started_runs = self._runs_going() - going_before
            if self.started_runs:
                self._step_waiting = position
                return
            self._done.add(position)
        self._schedule()

    def _background_ended(self, epoch: int) -> None:
        """
        End a step whose background runs have all ended: fail it if the tab says the work did
        not finish, else go on to the next.

        :param epoch: the start of the replay this came from; one from before the replay
            ended or restarted does nothing
        :type epoch: int
        """
        if epoch != self._epoch or self._step_waiting is None:
            return
        position, self._step_waiting = self._step_waiting, None
        failure = self._controller.background_step_failure()
        if failure:
            self._fail(position, failure)
            return
        self._done.add(position)
        self._schedule()

    def _runs_going(self) -> Set[Run]:
        """
        The (plugin key, channel) of every background run of the tab going now.

        :return: the runs whose worker has started and not yet ended
        :rtype: Set[Run]
        """
        return {
            (key, channel)
            for key, channels in self._controller.model.thread_running.items()
            for channel, going in channels.items()
            if going
        }

    def _run_going(self, run: Run) -> bool:
        """
        Is a run of this plugin on this channel going, or ended without the tab hearing yet?

        :param run: (plugin key, channel)
        :type run: Run
        :return: True if launching it now would be refused or confused with that run
        :rtype: bool
        """
        key, channel = run
        model = self._controller.model
        return bool(model.thread_running.get(key, {}).get(channel)) or (
            run in self._controller._held()
        )

    def _fail(self, position: int, reason: str) -> None:
        """
        Take a failed entry: nothing new starts from now on, and the user is asked.

        The question is asked at once, with the runs still going left to go on; a failure
        while a question is open is asked about once that one is answered, and none is
        asked about once the user has chosen to go back. Going back that fails is not
        asked about: the tab is left cleared.

        :param position: the failed entry's position
        :type position: int
        :param reason: what went wrong with the entry
        :type reason: str
        """
        self._failed.add(position)
        self._stopped = True
        if self.failed_at is None:
            self.failed_at = position
        if self._back_pending:
            self._end_if_idle()
            return
        if self._going_back:
            step, total = position + 1, len(self._entries)
            self._say(
                f"going back stopped at step {step} of {total}: {reason}; the tab is "
                f"left cleared"
            )
            self._back_pending = True
            self._stop_runs()
            self._end_if_idle()
            return
        self._to_ask.append((position, reason))
        if not self._asking:
            self._ask()

    def _ask(self) -> None:
        """
        Ask about each failure waiting, one question at a time, then act on the answers.

        The panel line goes out first, so the tab's held lines - what the failed run
        reported - are on the panel before the question.
        """
        self._asking = True
        epoch = self._epoch
        name = self._controller.__class__.__name__
        while self._to_ask:
            position, reason = self._to_ask.pop(0)
            step, total = position + 1, len(self._entries)
            self._say(f"replay stopped at step {step} of {total}: {reason}")
            action = str(self._entries[position].get("action"))
            details = "\n".join(self._step_errors)
            self._step_errors.clear()
            choice = self._controller.view.ask_after_replay_failure(
                name, step, total, action, reason, details
            )
            if epoch != self._epoch or not shiboken6.isValid(self._controller):
                return
            if choice == "back":
                self._to_ask = []
                self._back_pending = True
                self._say("going back to before the replay")
                self._stop_runs()
        self._asking = False
        self._end_if_idle()

    def _stop_runs(self) -> None:
        """Tell every run this replay launched and still waits for to stop, as its ❌ does."""
        name = self._controller.__class__.__name__
        for key, channel in list(self.runs):
            self._controller.handle_kill_worker(name, f"{key}/{channel}")

    def _end_if_idle(self) -> None:
        """
        End the replay if nothing it started is still going and nothing more can start.

        Done when every entry was replayed. After a failure it ends once the runs going
        have: kept as it is, or cleared and replayed from before if the user went back.
        """
        if self._asking or self.runs or self._step_waiting is not None:
            return
        if self._back_pending:
            self._back_pending = False
            if self._going_back:
                self._entries = []
                self._done = set()
                self._out_of_order = False
                self._end(None)
                self._clear_tab()
                self._say_loaded_actions_not_autosaved()
            else:
                self._go_back()
            return
        if self._stopped:
            kept, total = len(self._done), len(self._entries)
            self._end(None)
            if self.from_session:
                self._say(
                    f"{kept} of {total} steps are kept; the other {total - kept} are "
                    f"not saved in the autosave. Replay Actions continues them now; "
                    + self._how_to_get_them_back()
                )
            return
        if self.waiting:
            return
        if not self.has_remaining():
            went_back = self._going_back
            self._end("back to before the replay" if went_back else "replay done")
            if went_back:
                self._say_loaded_actions_not_autosaved()

    def _go_back(self) -> None:
        """Clear the tab and replay its history from before the replay."""
        entries = list(self._history_before.values())
        self._back_from_session = self.from_session
        self._end(None, going_back=True)
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

    def _say_loaded_actions_not_autosaved(self) -> None:
        """After going back from a replay of the loaded actions, say the autosave lacks them."""
        if not self._back_from_session:
            return
        self._back_from_session = False
        self._say(
            "the loaded actions are not saved in the autosave. Replay Actions replays "
            "them now; " + self._how_to_get_them_back()
        )

    def _how_to_get_them_back(self) -> str:
        """
        How the loaded actions can be had again once the app is restarted or restored.

        :return: the end of a status-panel line
        :rtype: str
        """
        if self._controller.session_source:
            return (
                "after Restore Session or a restart, load the session file again to get "
                "them back."
            )
        return "they cannot be brought back after Restore Session or a restart."

    def _say(self, text: str) -> None:
        """
        Put a line on the status panel under the tab's name.

        :param text: the line
        :type text: str
        """
        self._controller.add_text_to_display.emit(
            text, self._controller.__class__.__name__
        )

    def _in_recorded_order(self) -> None:
        """
        Leave the panel and the history as a replay in recorded order leaves them.

        An entry that started before an earlier one showed its values and was recorded out
        of turn. The values are shown again in recorded order, and the entries the replay
        recorded change places among themselves; one recorded by hand meanwhile stays put.
        """
        if not self._out_of_order:
            return
        with replaying():
            for position in sorted(self._written):
                self._controller.view.write_back(*self._written[position])
            history = self._controller.tab_action_history
            placed = {
                id(entry): position
                for position, entries in self._recorded.items()
                for entry in entries
            }
            values = list(history.values())
            slots = [i for i, entry in enumerate(values) if id(entry) in placed]
            ordered = sorted(
                (values[i] for i in slots), key=lambda entry: placed[id(entry)]
            )
            if all(values[i] is entry for i, entry in zip(slots, ordered)):
                return
            for i, entry in zip(slots, ordered):
                values[i] = entry
            self._controller.tab_action_history = OrderedDict(enumerate(values))
            self._controller.update_tab_action_history.emit(
                self._controller.__class__.__name__,
                self._controller.tab_action_history,
            )

    def _end(self, text: Optional[str], going_back: bool = False) -> None:
        """
        End the replay, say whether it can be continued, and unless ``text`` is None, say how.

        :param text: what to say on the status panel, which shows it under the tab's name
        :type text: Optional[str]
        :param going_back: the tab is about to be cleared and replayed from before, so
            neither its history nor the Replay Actions button is touched
        :type going_back: bool
        """
        if not going_back and shiboken6.isValid(self._controller):
            self._in_recorded_order()
        self.running = False
        stop_collecting_errors(self)
        self.runs = {}
        self.waiting = {}
        self.started_runs = set()
        self._step_waiting = None
        self._asking = False
        self._going_back = False
        self._epoch += 1
        self._turn_pending = False
        if going_back:
            return
        self._controller.replay_state_changed.emit(self.replay_available())
        if text is not None:
            self._controller.add_text_to_display.emit(
                text, self._controller.__class__.__name__
            )
