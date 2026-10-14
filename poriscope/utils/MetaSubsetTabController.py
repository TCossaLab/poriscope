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
# Kyle Briggs

import logging
import re
from typing import (
    Any,
    Dict,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    override,
)

import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.axes import Axes
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaSubsetTabModel import MetaSubsetTabModel
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView

#: The three columns that together identify an event, and mean the same in every
#: table that carries them.
EVENT_KEY = ("experiment_id", "channel_id", "event_id")


PLACEHOLDER = re.compile(r"(?<![\w:]):(experiment_id|channel_id)\b", re.IGNORECASE)


class RawRun(NamedTuple):
    """
    What running a raw filter produced, and the experiment and channel it ran for.

    ``experiment_id`` and ``channel`` are the selected pair, or None when nothing single
    was selected; ``scoped`` says the query used both placeholders, so its rows belong
    to that pair.
    """

    rows: pd.DataFrame
    executed: str
    experiment_id: Optional[int]
    channel: Optional[int]
    label: str
    scoped: bool


def code_spans(sql: str) -> List[Tuple[int, int]]:
    """
    Find the stretches of a query that are SQL, not strings, quoted names or comments.

    :param sql: the user's query
    :type sql: str
    :return: ``(start, end)`` for each stretch of code, in order
    :rtype: List[Tuple[int, int]]
    """
    spans: List[Tuple[int, int]] = []
    start = 0
    i = 0
    while i < len(sql):
        skip_to = -1
        if sql.startswith("--", i):
            end = sql.find("\n", i)
            skip_to = len(sql) if end < 0 else end + 1
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            skip_to = len(sql) if end < 0 else end + 2
        elif sql[i] in "'\"`[":
            close = "]" if sql[i] == "[" else sql[i]
            end = sql.find(close, i + 1)
            skip_to = len(sql) if end < 0 else end + 1
        if skip_to < 0:
            i += 1
            continue
        if i > start:
            spans.append((start, i))
        start = i = skip_to
    if start < len(sql):
        spans.append((start, len(sql)))
    return spans


def scope_placeholders(sql: str) -> Set[str]:
    """
    Find which scope placeholders a query uses: ``:experiment_id``, ``:channel_id``.

    Only code counts; the same text inside a string or a comment is not a placeholder.

    :param sql: the user's query
    :type sql: str
    :return: the names used, lower case, without the colon
    :rtype: Set[str]
    """
    found: Set[str] = set()
    for start, end in code_spans(sql):
        found.update(m.group(1).lower() for m in PLACEHOLDER.finditer(sql[start:end]))
    return found


def bind_scope(sql: str, experiment_id: int, channel_id: int) -> str:
    """
    Put the selected experiment and channel into a query's placeholders.

    The values are whole numbers Poriscope looked up, never text from the user, so
    nothing can be injected through them. Text inside strings and comments is left as
    written.

    :param sql: the user's query
    :type sql: str
    :param experiment_id: the experiment's id in the database
    :type experiment_id: int
    :param channel_id: the channel number
    :type channel_id: int
    :return: the query with ``:experiment_id`` and ``:channel_id`` replaced
    :rtype: str
    """
    values = {
        "experiment_id": str(int(experiment_id)),
        "channel_id": str(int(channel_id)),
    }
    pieces: List[str] = []
    last = 0
    for start, end in code_spans(sql):
        pieces.append(sql[last:start])
        pieces.append(
            PLACEHOLDER.sub(lambda m: values[m.group(1).lower()], sql[start:end])
        )
        last = end
    pieces.append(sql[last:])
    return "".join(pieces)


#: Statements that change the database, or its settings. A filter only reads.
WRITING_WORDS = frozenset(
    {
        "insert",
        "update",
        "delete",
        "drop",
        "create",
        "alter",
        "attach",
        "detach",
        "pragma",
        "vacuum",
        "reindex",
        "analyze",
    }
)


def writing_keyword(sql: str) -> Optional[str]:
    """
    Find a keyword in a query that would change the database, if there is one.

    ``WITH x AS (SELECT 1) DELETE FROM events`` starts like a read and is a write: the
    guard that a raw filter starts with ``SELECT`` or ``WITH`` does not see it, and Python's
    SQLite module only opens a transaction for a statement that starts with ``INSERT``,
    ``UPDATE`` or ``DELETE``, so this one is committed. Reads the whole text outside
    strings, quoted names and comments, whole words only (``updated_at`` is a column,
    ``replace(...)`` a function).

    :param sql: the user's query
    :type sql: str
    :return: the first such keyword, lower case, or None
    :rtype: Optional[str]
    """
    for start, end in code_spans(sql):
        code = sql[start:end]
        for match in re.finditer(r"[A-Za-z_]\w*", code):
            word = match.group(0).lower()
            if word in WRITING_WORDS:
                return word
            if word == "replace" and re.match(r"\s+into\b", code[match.end() :], re.I):
                return "replace into"
    return None


def selected_pairs(
    experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
) -> List[Tuple[str, Optional[int]]]:
    """
    List the experiments and channels a selection names, one entry per channel.

    :param experiments_and_channels: the experiment and channel scope, or None
    :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
    :return: ``(experiment name, channel)`` pairs; the channel is None for a whole experiment
    :rtype: List[Tuple[str, Optional[int]]]
    """
    pairs: List[Tuple[str, Optional[int]]] = []
    for name, channels in (experiments_and_channels or {}).items():
        if name is None:
            continue
        chosen: List[Optional[int]] = [c for c in channels] if channels else [None]
        for channel in chosen:
            pairs.append((name, None if channel is None else int(channel)))
    return pairs


def relabelled_keys(sql: str) -> List[Tuple[str, str]]:
    """
    Find event key columns a query produces by renaming something else.

    ``level_id AS event_id`` says its values are events', and nothing can check that
    they were meant to be: when they happen to name real events they load without a
    word. Reads the text only - an alias without ``AS`` or a rename built any other way
    goes unseen - so it is a warning, never a refusal. A column that is the key itself,
    possibly qualified (``e.event_id AS event_id``), is not a rename.

    :param sql: the user's query
    :type sql: str
    :return: ``(expression, alias)`` for each key column labelled from another expression
    :rtype: List[Tuple[str, str]]
    """
    found: List[Tuple[str, str]] = []
    pattern = r"\bAS\s+[\"`\[]?(experiment_id|channel_id|event_id)[\"`\]]?(?!\w)"
    for match in re.finditer(pattern, sql, re.IGNORECASE):
        alias = match.group(1).lower()
        prefix = sql[: match.start()]
        depth = 0
        start = 0
        for i in range(len(prefix) - 1, -1, -1):
            char = prefix[i]
            if char == ")":
                depth += 1
            elif char == "(":
                if depth == 0:
                    start = i + 1
                    break
                depth -= 1
            elif depth == 0 and (
                char == ","
                or re.search(r"\b(SELECT|DISTINCT)\s*$", prefix[: i + 1], re.IGNORECASE)
            ):
                start = i + 1
                break
        expression = prefix[start:].strip()
        plain = rf"(?:[\w\"`\[\]]+\.)?[\"`\[]?{alias}[\"`\]]?"
        if not re.fullmatch(plain, expression, re.IGNORECASE):
            found.append((expression, alias))
    return found


class MetaSubsetTabController(MetaController):
    """
    Shared base for the Controllers of the two database-backed analysis tabs.

    MetadataController and ProteinController both drive a tab whose data
    comes from a MetaDatabaseLoader: the user picks an experiment and channels,
    builds a subset filter, and plots or exports the rows that come back. The two
    were written by copy-paste and carried seventeen methods verbatim between them;
    this base holds that shared half so there is one copy to fix.

    What a subclass inherits:

    - **Experiment state.** request_experiment_structure asks the loader and hands
      its answer to the View, which is the Model-to-View half of the mediation this
      layer exists for.
    - **Filter validation.** validate_filter and validate_raw_filter answer the
      View's two validation requests by calling the loader directly, so a filter the
      database refuses is reported through _refuse_filter rather than vanishing.
      relay_query receives the query the loader built - or the debug message explaining
      why it could not - and commits, renames or refuses the pending filter accordingly.
    - **Session state.** get_session_state and restore_session_state
      override MetaController's hooks so a tab's subset filters survive a
      save and reload.

    What a subclass owes it:

    - **Its own** logger = logging.getLogger(__name__), so that records made by
      the methods it defines itself stay attributed to its own module. Methods
      defined *here* log under this module, which is the same convention
      MetaView and MetaController already follow for their shared code.
    - **self.view and self.model**, built in its _init() as
      MetaController requires.

    :ivar logger: the module logger the shared methods below log under
    """

    logger = logging.getLogger(__name__)

    #: Redeclared with this tab's own types, so the type checker sees the methods
    #: the base View and Model do not have (see MetaController.view).
    view: MetaSubsetTabView
    model: MetaSubsetTabModel

    #: The last scope warning shown, so one query is not warned about once per channel.
    _last_scope_warning: str = ""

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Wire the eight requests both subset tabs share.

        A subclass with requests of its own overrides this and calls
        ``super()._setup_connections()`` first, so the shared ones are wired once here
        rather than repeated in each tab.

        :return: None
        :rtype: None
        """
        self.view.experiment_structure_requested.connect(
            self.request_experiment_structure
        )
        self.view.filter_validation_requested.connect(self.validate_filter)
        self.view.raw_filter_validation_requested.connect(self.validate_raw_filter)
        self.view.event_id_cache_requested.connect(self.load_event_id_cache)
        self.view.scatterplot_requested.connect(self.filter_scatterplot)
        self.view.filters_load_requested.connect(self.load_filters)
        self.view.filters_save_requested.connect(self.save_filters)
        self.view.event_plot_data_requested.connect(self.load_event_plot_data)

    @log(logger=logger)
    @Slot(str, list, object, object, object, str)
    def load_event_plot_data(
        self,
        loader: str,
        event_ids: List[int],
        exp: Optional[str],
        channel: Optional[int],
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        action_label: str,
    ) -> None:
        """
        Resolve ``event_id`` values to database ids within scope and load those rows.

        The whole chain runs here because only one place can run it end to end and say
        which part failed. It was three separate requests once, each answer parked on a
        View attribute and read back on the next statement; nothing outside the chain
        ever read the intermediate answers.

        **An experiment that does not resolve stops the plot** rather than widening the
        query. ``event_id`` is unique only within an experiment and channel, so an
        unscoped match returns whichever channel's row happens to share the number -
        which is the "plots the wrong subset" fault, not a harmless one.

        ``action_label`` names what the caller is plotting - events, histograms - and
        appears only in the messages, which is the whole of what the two tabs' copies
        of this method used to differ by.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the ``event_id`` values to plot, already snapped to the cache
        :type event_ids: List[int]
        :param exp: the experiment the events belong to, or None to leave it out of scope
        :type exp: Optional[str]
        :param channel: the channel the events belong to, or None for all channels
        :type channel: Optional[int]
        :param experiments_and_channels: the scope handed on to ``load_event_data``
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param action_label: what the caller is plotting, for its messages
        :type action_label: str
        :return: None
        :rtype: None
        """
        if not event_ids:
            self.add_text_to_display.emit(
                f"No events were requested, so there are no {action_label} to plot",
                self.__class__.__name__,
            )
            return

        exp_id = None
        if exp is not None:
            try:
                exp_id = self.model.call(
                    "MetaDatabaseLoader", loader, "get_experiment_id_by_name", exp
                )
            except Exception as e:
                self.logger.error(f"Failed to resolve experiment {exp}: {e!r}")
                self.add_text_to_display.emit(
                    f"Could not look up experiment {exp} in {loader}: {e}",
                    self.__class__.__name__,
                )
                return
            if exp_id is None:
                self.add_text_to_display.emit(
                    f"{loader} has no experiment named {exp}, so these {action_label} "
                    "cannot be scoped to it",
                    self.__class__.__name__,
                )
                return

        try:
            id_result = self.model.resolve_event_ids(loader, event_ids, exp_id, channel)
        except Exception as e:
            self.logger.error(f"Failed to resolve event ids for {event_ids}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not look up these events in {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if id_result is None or id_result.empty:
            self.add_text_to_display.emit(
                f"No data available for the requested {action_label}: {event_ids}",
                self.__class__.__name__,
            )
            return
        if "id" not in id_result.columns:
            # A populated result without the column it was asked for means the loader
            # did not honour its own contract, which is a different problem from an
            # empty subset and would raise on the read below. Reported rather than
            # logged alone: the View stays quiet on a refusal precisely because this
            # method explains every one of them, so a log-only branch here is a plot
            # that fails with nothing said.
            message = (
                f"{loader} returned rows with no id column for the requested "
                f"{action_label}: {event_ids}"
            )
            self.logger.error(
                f"{message} in experiment {exp} channel {channel}",
            )
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        db_ids = ",".join(str(i) for i in id_result["id"].tolist())
        try:
            generator = self.model.load_events_by_id(
                loader, db_ids, experiments_and_channels
            )
        except Exception as e:
            self.logger.error(f"Failed to load events {event_ids}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load these events from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if generator is None:
            self.add_text_to_display.emit(
                f"No data available for the requested {action_label}: {event_ids}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    @Slot(object, object, object, object, str)
    def filter_scatterplot(
        self,
        columns: Sequence[npt.NDArray[np.float64]],
        log_flags: Sequence[bool],
        ax: Axes,
        axis_labels: Sequence[str],
        dataset_label: str,
    ) -> None:
        """
        Filter and log-scale a scatterplot's columns, and hand them back to draw.

        The View asks, this slot calls the Model, and the answer goes back through
        a setter. Shared by both subset tabs, whose copies were identical: the
        drawing context arrives and departs unchanged, so this marshals and does not
        interpret it.

        :param columns: the raw x and y values
        :type columns: Sequence[npt.NDArray[np.float64]]
        :param log_flags: log-scale each column?
        :type log_flags: Sequence[bool]
        :param ax: the axis object the View will draw on
        :type ax: Axes
        :param axis_labels: the axis labels, already formatted
        :type axis_labels: Sequence[str]
        :param dataset_label: string to label the dataset
        :type dataset_label: str
        :return: None
        :rtype: None
        """
        try:
            filtered = self.model.logscale_and_filter_columns(
                *columns, log_flags=list(log_flags)
            )
        except (ValueError, TypeError, IndexError) as e:
            self.logger.error(f"Unable to filter the scatterplot: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to filter the scatterplot: {e}", self.__class__.__name__
            )
            return
        self.view.set_scatterplot(filtered, ax, axis_labels, dataset_label)

    @log(logger=logger)
    @Slot(str, str)
    def load_filters(self, path: str, loader: str) -> None:
        """
        Read a saved filter file and hand its contents to the View.

        A file that cannot be read, or that does not hold a JSON object, is reported
        here and nothing is handed back - so the tab's existing filters are left
        exactly as they were rather than half replaced.

        :param path: the file the user chose
        :type path: str
        :param loader: the loader the filters will be validated against
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            new_filters = self.model.load_filters(path)
        except (OSError, ValueError) as e:
            message = f"Failed to load filters from {path}: {e}"
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        self.view.set_loaded_filters(new_filters, loader)
        self.logger.info(f"Filters loaded from {path}")

    @log(logger=logger)
    @Slot(str, object)
    def save_filters(self, path: str, filters: Dict[str, str]) -> None:
        """
        Write the tab's filters to the file the user chose.

        A failure used to reach the log only, so a full disk or a read-only folder
        looked exactly like a successful save.

        :param path: the file the user chose
        :type path: str
        :param filters: the filters to write, keyed by name
        :type filters: Dict[str, str]
        :return: None
        :rtype: None
        """
        try:
            self.model.save_filters(path, filters)
        except OSError as e:
            message = f"Failed to save filters to {path}: {e}"
            self.logger.error(message)
            self.add_text_to_display.emit(message, self.__class__.__name__)
            return

        self.logger.info(f"Filters saved to {path}")

    @log(logger=logger)
    def _raw_failure_reason(self, loader: str, query: str) -> str:
        """
        Say why a raw query could not run, in the loader's own words.

        ``query_database_directly`` answers None for a query it could not run and
        logs the reason; the validator gives the same reason as text, which is what
        a SQL viewer would have shown, for example ``no such column: nope``.

        :param loader: the database loader plugin's key
        :type loader: str
        :param query: the SQL that failed
        :type query: str
        :return: the SQL error, or a pointer to the log if the validator has none
        :rtype: str
        """
        try:
            valid, debug = self.model.call(
                "MetaDatabaseLoader", loader, "validate_filter_query", query
            )
        except Exception:
            return "see the log for the SQL error"
        if valid or not debug:
            return "see the log for the SQL error"
        return str(debug).split("\n\n")[-1].strip()

    @log(logger=logger)
    def _warn_once(self, message: str) -> None:
        """
        Put a warning on the status panel unless it is the one shown last.

        A plot asks once per ticked channel with the same query, and the warning is
        about the query, so it is worth saying once.

        :param message: the warning
        :type message: str
        """
        if message == self._last_scope_warning:
            return
        self._last_scope_warning = message
        self.add_text_to_display.emit(message, self.__class__.__name__)

    @log(logger=logger)
    def _experiment_database_id(
        self, loader: str, experiment: str, subset_name: str
    ) -> Optional[int]:
        """
        Look up an experiment's id in the database from its name.

        Reports its own failure and answers with None.

        :param loader: the database loader plugin's key
        :type loader: str
        :param experiment: the experiment's name
        :type experiment: str
        :param subset_name: the filter's name, for the messages
        :type subset_name: str
        :return: the id, or None if it could not be found
        :rtype: Optional[int]
        """
        try:
            found = self.model.call(
                "MetaDatabaseLoader", loader, "get_experiment_id_by_name", experiment
            )
        except Exception as e:
            self.logger.error(f"Failed to resolve experiment {experiment}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not look up experiment {experiment} in {loader} for "
                f"{subset_name}: {e}",
                self.__class__.__name__,
            )
            return None
        if found is None:
            self.add_text_to_display.emit(
                f"{loader} has no experiment named {experiment}, so {subset_name} "
                "cannot be run for it",
                self.__class__.__name__,
            )
            return None
        return int(found)

    @log(logger=logger)
    def _warn_about_leaks(
        self, rows: pd.DataFrame, run_for: Tuple[int, int, str], subset_name: str
    ) -> None:
        """
        Warn that a result holds rows from other experiments or channels than the selected one.

        The query was given the selection but may not have used it everywhere - a
        placeholder in a subquery and not on the main table, say - so rows of other
        channels would be drawn under this one's name. Only possible to see when the
        result carries ``experiment_id`` or ``channel_id``; a warning, since the query
        may mean it.

        :param rows: the raw filter's result
        :type rows: pd.DataFrame
        :param run_for: the experiment id, the channel and the label the query ran for
        :type run_for: Tuple[int, int, str]
        :param subset_name: the filter's name, for the message
        :type subset_name: str
        """
        experiment, channel, label = run_for
        rows = rows.loc[:, ~rows.columns.duplicated()]
        lowered: Dict[str, Any] = {}
        for column in rows.columns:
            lowered.setdefault(str(column).lower(), column)
        elsewhere = pd.Series(False, index=rows.index)
        for name, wanted in (("experiment_id", experiment), ("channel_id", channel)):
            if name in lowered:
                values = pd.to_numeric(rows[lowered[name]], errors="coerce")
                elsewhere |= values.notna() & (values != wanted)
        other = int(elsewhere.sum())
        if other:
            self._warn_once(
                f"{other} of {len(rows)} rows of {subset_name}'s query are from other "
                f"experiments or channels than the one selected ({label}), so they are "
                "drawn under it. If you meant only this channel, put experiment_id = "
                ":experiment_id AND channel_id = :channel_id in the WHERE of the main "
                "table, not only in a subquery"
            )

    @log(logger=logger)
    def _run_raw_filter(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[RawRun]:
        """
        Run a raw ``SELECT`` for the selected experiment and channel.

        The query scopes itself: ``:experiment_id`` and ``:channel_id`` in it are
        replaced by the selected experiment's id and the channel, one selected channel
        at a time, so ``LIMIT``, aggregates and ``DISTINCT`` see only that channel's
        rows and nothing is applied to the result afterwards. A query that uses neither
        placeholder, or only one, is warned about, since it ignores the selection
        wholly or in part; one that uses them with nothing, or several channels,
        selected is refused. Only a ``SELECT`` is run - the loader's validator accepts
        any statement.

        Reports its own failure and answers with None.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the filter's complete ``SELECT``
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the filter's name, for the messages
        :type subset_name: str
        :return: the rows, the SQL that ran and the pair it ran for, or None
        :rtype: Optional[RawRun]
        """
        if not re.match(
            r"(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*(?:select|with)\b",
            sql_filter,
            re.IGNORECASE | re.DOTALL,
        ):
            # The loader's validator accepts any single statement, so a DELETE or an
            # UPDATE would run - and is only undone because the connection never
            # commits. A filter file can hold one without the dialog's own check.
            self.add_text_to_display.emit(
                f"{subset_name} is not a SELECT, so it was not run: a raw filter has to "
                "start with SELECT",
                self.__class__.__name__,
            )
            return None
        writes = writing_keyword(sql_filter)
        if writes is not None:
            self.add_text_to_display.emit(
                f"{subset_name} contains {writes.upper()}, so it was not run: a raw "
                "filter may only read the database",
                self.__class__.__name__,
            )
            return None
        used = scope_placeholders(sql_filter)
        pairs = selected_pairs(experiments_and_channels)
        single = len(pairs) == 1 and pairs[0][1] is not None
        query = sql_filter.strip().rstrip(";")
        experiment: Optional[int] = None
        channel: Optional[int] = None
        label = ""
        if single:
            name, channel = pairs[0]
            experiment = self._experiment_database_id(loader, name, subset_name)
            if experiment is None:
                return None
            label = f"{name} Ch {channel}"
        if used:
            if not pairs:
                self.add_text_to_display.emit(
                    f"{subset_name}'s query uses {', '.join(':' + n for n in sorted(used))}"
                    ", which come from the selection, and no experiment and channel is "
                    "selected",
                    self.__class__.__name__,
                )
                return None
            if experiment is None or channel is None:
                self.add_text_to_display.emit(
                    f"{subset_name}'s query uses {', '.join(':' + n for n in sorted(used))}"
                    ", so it runs for one experiment and one channel at a time; select "
                    "a single channel",
                    self.__class__.__name__,
                )
                return None
            query = bind_scope(query, experiment, channel)
            if used != {"experiment_id", "channel_id"}:
                missing = ({"experiment_id", "channel_id"} - used).pop()
                self._warn_once(
                    f"{subset_name}'s query uses :{next(iter(used))} but not :{missing}"
                    ", so the same rows are drawn for every "
                    f"{'channel of that experiment' if missing == 'channel_id' else 'experiment'}"
                    f". Add {missing} = :{missing} to its WHERE"
                )
        elif pairs:
            self._warn_once(
                f"{subset_name}'s query does not use :experiment_id or :channel_id, so "
                "it ignores the Scope selection and the same rows are drawn for every "
                "selected channel. Add experiment_id = :experiment_id AND channel_id = "
                ":channel_id to its WHERE"
            )
        try:
            rows = self.model.call(
                "MetaDatabaseLoader", loader, "query_database_directly", query
            )
        except Exception as e:
            self.logger.error(f"Failed to run the raw filter {subset_name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not run the raw filter {subset_name} on {loader}: {e}",
                self.__class__.__name__,
            )
            return None
        if rows is None:
            self.add_text_to_display.emit(
                f"Could not run the raw filter {subset_name}: "
                f"{self._raw_failure_reason(loader, query)}",
                self.__class__.__name__,
            )
            return None
        scoped = used == {"experiment_id", "channel_id"}
        if scoped and experiment is not None and channel is not None:
            self._warn_about_leaks(rows, (experiment, channel, label), subset_name)
        return RawRun(rows, query, experiment, channel, label, scoped)

    @log(logger=logger)
    def _ambiguous_raw_columns(
        self, rows: pd.DataFrame, needed: Sequence[str], subset_name: str
    ) -> bool:
        """
        Refuse a raw result that holds a column the plot needs under the same name twice.

        A join's ``SELECT *`` returns both tables' columns of the same name, and a lookup
        by name returns a table, not a column; SQLite renames the second to ``name:1``
        when the query is a subquery, and the plot would then read whichever table came
        first. A plot cannot choose, so the query has to say which one it means.
        Reports the refusal itself.

        :param rows: the raw filter's result
        :type rows: pd.DataFrame
        :param needed: the columns the plot reads
        :type needed: Sequence[str]
        :param subset_name: the filter's name, for the message
        :type subset_name: str
        :return: True if a needed column is duplicated, in which case the caller must stop
        :rtype: bool
        """
        names = [str(c) for c in rows.columns]
        duplicated = set()
        for name in names:
            sibling = re.fullmatch(r"(.+):\d+", name)
            if names.count(name) > 1:
                duplicated.add(name)
            elif sibling and sibling.group(1) in names:
                duplicated.add(sibling.group(1))
        clash = [c for c in needed if c in duplicated]
        if not clash:
            return False
        self.add_text_to_display.emit(
            f"{subset_name}'s query returns {', '.join(clash)} more than once, so the "
            "plot cannot tell which one it means. Name the one you want, for example "
            f"SELECT e.{clash[0]} AS {clash[0]}, ... and give the other a different name",
            self.__class__.__name__,
        )
        return True

    @log(logger=logger)
    def _raw_event_keys(
        self, run: RawRun, sql_filter: str, subset_name: str
    ) -> Optional[pd.DataFrame]:
        """
        Read the events a raw result names from their key, ``experiment_id``, ``channel_id``, ``event_id``.

        The three together identify an event in the database and mean the same thing
        in every table that carries them - a sublevel's are its parent event's - so a
        query that joins tables cannot name the wrong event by returning another table's
        value, as it can with ``id``, which means a different row in each. A query that
        used both placeholders needs to return only ``event_id``: its rows belong to the
        selected experiment and channel. Otherwise the result has to carry all three.
        Column names are matched without regard to case, as SQLite matches them; a join
        that returns one of them twice gives the same value twice, so the first is kept.

        A row with a ``NULL`` in the key names no event and is left out, and the panel
        says how many. A key column the query makes by renaming another expression is
        warned about, since nothing can check that it was meant.

        Reports its own refusal and answers with None.

        :param run: the raw filter's result and the pair it ran for
        :type run: RawRun
        :param sql_filter: the filter's complete ``SELECT``, read for renamed key columns
        :type sql_filter: str
        :param subset_name: the filter's name, for the message
        :type subset_name: str
        :return: one row per distinct event, with the three columns as integers, or None if the result cannot name its events
        :rtype: Optional[pd.DataFrame]
        """
        rows = run.rows.loc[:, ~run.rows.columns.duplicated()]
        lowered: Dict[str, Any] = {}
        for column in rows.columns:
            lowered.setdefault(str(column).lower(), column)
        if "event_id" not in lowered:
            self.add_text_to_display.emit(
                f"{subset_name}'s query does not return event_id, which identifies an "
                "event. Add it to the SELECT, for example SELECT event_id FROM events "
                "WHERE experiment_id = :experiment_id AND channel_id = :channel_id",
                self.__class__.__name__,
            )
            return None
        known: Dict[str, Any] = {}
        if run.scoped and run.experiment_id is not None and run.channel is not None:
            known = {"experiment_id": run.experiment_id, "channel_id": run.channel}
        parts: Dict[str, Any] = {}
        for name in EVENT_KEY:
            if name in lowered:
                parts[name] = rows[lowered[name]]
            elif name in known:
                parts[name] = pd.Series(known[name], index=rows.index)
        missing = [name for name in EVENT_KEY if name not in parts]
        if missing:
            self.add_text_to_display.emit(
                f"{subset_name}'s query does not return {', '.join(missing)}, and does "
                "not use :experiment_id and :channel_id, so its events cannot be "
                "placed. Use the two placeholders in its WHERE, or return the columns",
                self.__class__.__name__,
            )
            return None
        keys = pd.DataFrame({name: parts[name] for name in EVENT_KEY})
        for expression, alias in relabelled_keys(sql_filter):
            self.add_text_to_display.emit(
                f"{subset_name}'s query labels {expression!r} as {alias}, so the plot "
                f"takes it as the event's own {alias}. If it is not, the wrong events "
                "are plotted",
                self.__class__.__name__,
            )
        numbers = keys.apply(pd.to_numeric, errors="coerce")
        # A NULL is reported below; what is present but not a whole number - 1.5, or
        # text - cannot name an event, and truncating it would name another.
        fractional = (numbers.notna() & (numbers % 1 != 0)) | (
            keys.notna() & numbers.isna()
        )
        broken = int(fractional.any(axis=1).sum())
        if broken:
            example = keys[fractional.any(axis=1)].iloc[0].to_dict()
            self.add_text_to_display.emit(
                f"{broken} row(s) of {subset_name}'s query have an experiment_id, "
                "channel_id or event_id that is not a whole number, so they cannot "
                f"name an event, for example {example}",
                self.__class__.__name__,
            )
            return None
        keys = numbers
        unnamed = int(keys.isna().any(axis=1).sum())
        if unnamed:
            self.add_text_to_display.emit(
                f"{unnamed} row(s) of {subset_name}'s query have a NULL experiment_id, "
                "channel_id or event_id, so they name no event and were left out",
                self.__class__.__name__,
            )
        return keys.dropna().astype(int).drop_duplicates()

    @log(logger=logger)
    def _event_keys_exist(
        self, loader: str, keys: pd.DataFrame, subset_name: str
    ) -> bool:
        """
        Check that every event key a raw result names is an event in the database.

        Catches a column that is not an event's - a level number labelled ``event_id``,
        say - when its values name no event. A value that happens to name a real event
        cannot be told from one the user meant, and passes. Reports the refusal itself.

        :param loader: the database loader plugin's key
        :type loader: str
        :param keys: the distinct event keys, from :meth:`_raw_event_keys`
        :type keys: pd.DataFrame
        :param subset_name: the filter's name, for the message
        :type subset_name: str
        :return: True if every key is an event
        :rtype: bool
        """
        if keys.empty:
            return True
        values = ",".join(str(i) for i in keys["event_id"].unique())
        try:
            real = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "query_database_directly",
                "SELECT experiment_id, channel_id, event_id FROM events "
                f"WHERE event_id IN ({values})",
            )
        except Exception as e:
            self.logger.error(f"Failed to check the events of {subset_name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not check that {subset_name}'s query names events: {e}",
                self.__class__.__name__,
            )
            return False
        if real is None:
            self.add_text_to_display.emit(
                f"Could not check that {subset_name}'s query names events: see the "
                "log for the SQL error",
                self.__class__.__name__,
            )
            return False
        matched = keys.merge(
            real.astype(int), on=list(EVENT_KEY), how="left", indicator=True
        )
        unknown = int((matched["_merge"] != "both").sum())
        if not unknown:
            return True
        self.add_text_to_display.emit(
            f"{unknown} of the {len(keys)} (experiment_id, channel_id, event_id) values "
            f"in {subset_name}'s query are not an event in the database, so they would "
            "load the wrong events or none. event_id has to be the event's own, for "
            "example SELECT e.event_id AS event_id, ... FROM events e ...",
            self.__class__.__name__,
        )
        return False

    @log(logger=logger)
    def _raw_filter_conditions(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> Optional[Tuple[str, str]]:
        """
        Turn a raw ``SELECT`` into the WHERE-clause body that selects exactly its events.

        An event-data plot has to load traces, which only ``load_event_data`` can do, and
        that takes a WHERE-clause body spliced into its own fixed query. The raw filter
        runs for the selected experiment and channel by :meth:`_run_raw_filter`, and the
        events it names are found from their key, one condition per experiment and
        channel the result holds. A result that does not name its events is reported
        rather than guessed at, and what was selected is stated on the panel, so a key
        that names other events than the user meant is visible.

        Reports its own failure and answers with None.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the filter's complete ``SELECT``
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the filter's name, for the message
        :type subset_name: str
        :return: the condition selecting those events, and the SQL that ran, or None
        :rtype: Optional[Tuple[str, str]]
        """
        run = self._run_raw_filter(
            loader, sql_filter, experiments_and_channels, subset_name
        )
        if run is None:
            return None
        keys = self._raw_event_keys(run, sql_filter, subset_name)
        if keys is None:
            return None
        if keys.empty:
            self.add_text_to_display.emit(
                f"{subset_name}'s query returned no events, so there is nothing to plot",
                self.__class__.__name__,
            )
            return None
        if not self._event_keys_exist(loader, keys, subset_name):
            return None
        terms = []
        for (experiment, channel), group in keys.groupby(
            ["experiment_id", "channel_id"]
        ):
            ids = ",".join(str(i) for i in group["event_id"])
            terms.append(
                f"(e.experiment_id = {experiment} AND e.channel_id = {channel} "
                f"AND e.event_id IN ({ids}))"
            )
        pairs = len(terms)
        where = (
            run.label
            if pairs == 1 and run.label
            else f"{pairs} experiment/channel pair(s)"
        )
        self.add_text_to_display.emit(
            f"{subset_name}: {len(keys)} events on {where}, event_id "
            f"{keys['event_id'].min()}-{keys['event_id'].max()}",
            self.__class__.__name__,
        )
        return " OR ".join(terms), run.executed

    @log(logger=logger)
    def _load_raw_event_id_cache(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> None:
        """
        Fill the navigation cache from a raw ``SELECT``'s event keys.

        The query runs for the selected experiment and channel like every other raw
        filter, and the ``event_id`` values it names there are the cache. A row per
        sublevel would repeat each event, so each is listed once, and a query that
        ignored the selection is cut to the selected pair. Anything wrong is reported
        here and leaves the View's answer at None, which is what tells it nothing ran.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the filter's complete ``SELECT``
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the filter's name, for the messages
        :type subset_name: str
        :return: None
        :rtype: None
        """
        run = self._run_raw_filter(
            loader, sql_filter, experiments_and_channels, subset_name
        )
        if run is None:
            return
        keys = self._raw_event_keys(run, sql_filter, subset_name)
        if keys is None or not self._event_keys_exist(loader, keys, subset_name):
            return
        if run.experiment_id is not None and run.channel is not None:
            keys = keys[
                (keys["experiment_id"] == run.experiment_id)
                & (keys["channel_id"] == run.channel)
            ]
        self.view.set_event_id_rows(keys[["event_id"]].drop_duplicates())

    @log(logger=logger)
    @Slot(str, object, object, str)
    def load_event_id_cache(
        self,
        loader: str,
        conditions: Optional[str],
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]],
        subset_name: str,
    ) -> None:
        """
        Fetch the ``event_id`` values a subset holds, for the navigation cache.

        Shared by both subset tabs because ``_rebuild_event_id_cache`` is. A failed
        query leaves the View's answer at ``None``, which is what lets the caller tell
        "that did not run" from "the subset is empty" - leaving the previous call's rows
        in place would make the two indistinguishable and rebuild the cache from them.

        :param loader: the database loader plugin's key
        :type loader: str
        :param conditions: the subset filter, or None for every row
        :type conditions: Optional[str]
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :param subset_name: the selected filter's name, whose ``_raw`` suffix marks a raw filter
        :type subset_name: str
        :return: None
        :rtype: None
        """
        if subset_name.endswith("_raw"):
            self._load_raw_event_id_cache(
                loader, conditions or "", experiments_and_channels, subset_name
            )
            return

        try:
            rows = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_metadata",
                ["event_id"],
                conditions,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.warning(f"Failed to load the filtered event ids: {e!r}")
            self.add_text_to_display.emit(
                f"Could not read this subset's events from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if rows is None:
            # The loader logs why and answers None rather than raising; without this
            # the panel said nothing and the View's error was the only report.
            self.add_text_to_display.emit(
                f"Could not read this subset's events from {loader}: see the log "
                "for the SQL error",
                self.__class__.__name__,
            )
        self.view.set_event_id_rows(rows)

    @log(logger=logger)
    @Slot(str)
    def request_experiment_structure(self, loader_name: str) -> None:
        """
        Fetch a loader's experiment-and-channel structure and file it under its key.

        The loader key was the bus's ``ret_args`` here: the answer has to be filed under
        the loader it came from, and passing it forward explicitly is what replaces that.
        Channels are stringified for display, as they were.

        :param loader_name: the database loader plugin's key
        :type loader_name: str
        :return: None
        :rtype: None
        """
        try:
            structure = self.model.call(
                "MetaDatabaseLoader", loader_name, "get_experiments_and_channels"
            )
        except Exception as e:
            self.logger.error(
                f"Unable to read the experiment structure of {loader_name}: {repr(e)}"
            )
            self.add_text_to_display.emit(
                f"Unable to read the experiments in {loader_name}: {e}",
                self.__class__.__name__,
            )
            return
        self.logger.debug(
            f"Received full experiment-channel structure for {loader_name}: {structure}"
        )
        str_structure = {
            exp: [str(ch) for ch in ch_list] for exp, ch_list in structure.items()
        }
        self.view.available_experiment_and_channels_by_loader[loader_name] = (
            str_structure
        )
        self.view.selected_experiment_and_channels_by_loader[loader_name] = (
            self._reconcile_scope_selection(loader_name, str_structure)
        )

    @log(logger=logger)
    def _reconcile_scope_selection(
        self, loader_name: str, structure: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Keep the user's experiment and channel scope across a structure refresh.

        The structure is re-read whenever the loader changes or the selection tree is
        opened, and both sites used to overwrite the *selection* with the whole
        structure. Any refresh therefore widened a narrowed scope back to everything,
        silently: the tree was not open to show it, and only the heatmap and the event
        overlays check, so every other plot type simply drew more data than was asked
        for. Reported from a real run as a heatmap refusing a scope that looked right.

        An existing selection is kept and pruned to what the database still holds, so
        a remembered channel that has gone cannot scope a query to nothing. With no
        selection yet, everything is selected, which is the useful default and what
        both sites did unconditionally before.

        The channel lists are rebuilt rather than shared: ``dict.copy()`` is shallow,
        so the selection and the available structure held the *same* list objects, and
        narrowing one in place would have narrowed what the tree offers.

        :param loader_name: the key of the loader whose structure was read
        :type loader_name: str
        :param structure: every experiment and channel the loader now reports
        :type structure: Dict[str, List[str]]
        :return: the scope to store against this loader
        :rtype: Dict[str, List[str]]
        """
        existing = self.view.selected_experiment_and_channels_by_loader.get(loader_name)
        if existing:
            kept = {}
            for experiment, channels in existing.items():
                if experiment not in structure:
                    continue
                survivors = [
                    channel for channel in channels if channel in structure[experiment]
                ]
                if survivors:
                    kept[experiment] = survivors
            if kept:
                return kept
            self.logger.info(
                f"The remembered scope for {loader_name} no longer matches the "
                "database, so every experiment and channel is selected again"
            )
        return {
            experiment: list(channels) for experiment, channels in structure.items()
        }

    @log(logger=logger)
    @Slot(str, str, str, str, object)
    def validate_filter(
        self,
        loader: str,
        filter_text: str,
        intent: str,
        name: str,
        old_name: Optional[str],
    ) -> None:
        """
        Validate an assisted subset filter by asking the loader to build a query.

        A filter counts as valid if ``construct_metadata_query`` can *build* a query
        around it; the query itself is thrown away. The call is made here rather than
        from the widget because ``construct_metadata_query`` **raises** for a column it
        cannot map to a table, and a filter naming a column the database does not have
        has to reach the user rather than a log line.

        The columns are resolved here rather than passed in by the View, and only
        ``events`` columns are asked for. The View used to hand over a hardcoded
        ``["sublevel_current", "voltage", "duration"]`` - one column from each of the
        three tables, which forced the built query to join all three every time, even
        for a filter with no conditions at all. One events column yields exactly the
        joins the filter itself needs: none for ``duration < 300``, one for a filter
        that really does reference sublevels or experiments.

        :param loader: the database loader plugin's key
        :type loader: str
        :param filter_text: the filter expression to validate, without WHERE
        :type filter_text: str
        :param intent: ``validate_new_filter`` or ``validate_edited_filter``, passed
            through to ``relay_query`` to say what to do with the answer
        :type intent: str
        :param name: the name to commit the filter under, carried from the request
        :type name: str
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :return: None
        :rtype: None
        """
        try:
            columns = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_names_by_table", "events"
            )
        except Exception as e:
            self.logger.error(f"Failed to read the events columns of {loader}: {e!r}")
            self._refuse_filter(f"Unable to read the columns of {loader}: {e}")
            return

        if not columns:
            # Nothing to build a query around, so nothing can be validated. Refusing
            # is the honest answer: the hardcoded triple this replaces would have
            # "validated" against three columns that may not exist either.
            self.logger.error(f"{loader} reported no columns in its events table")
            self._refuse_filter(
                f"{loader} reports no columns in its events table, so the filter "
                "cannot be validated"
            )
            return

        try:
            query, debug, table_name = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                columns[:1],
                filter_text,
                None,
            )
        except Exception as e:
            # Previously swallowed by the dispatcher. ValueError for an unmappable
            # column, KeyError for an unknown experiment name.
            self.logger.error(f"Failed to validate filter {filter_text!r}: {e!r}")
            self._refuse_filter(f"The filter could not be validated: {e}")
            return

        self.relay_query(query, debug, table_name, intent, name, old_name, filter_text)

    @log(logger=logger)
    @Slot(str, str, str, object)
    def validate_raw_filter(
        self, loader: str, query: str, name: str, old_name: Optional[str]
    ) -> None:
        """
        Validate a raw subset filter, which the loader checks without building.

        A raw filter is a complete SELECT the loader runs verbatim, so it is checked
        with ``validate_filter_query`` rather than by constructing a query around it.
        As on the assisted path, the call is made here so that a failure reaches the
        user rather than a log line.

        The placeholders are given sample values, so a filter that uses them parses.
        The text is checked as written: ``validate_filter_query`` only plans the query,
        never runs it, so nothing is appended to make it cheap - a ``LIMIT 0`` added to
        a filter that ends in its own ``LIMIT`` made it a syntax error.

        :param loader: the database loader plugin's key
        :type loader: str
        :param query: the raw filter as the user wrote it, without a trailing semicolon
        :type query: str
        :param name: the name to commit the filter under, carried from the request
        :type name: str
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :return: None
        :rtype: None
        """
        try:
            valid, error_msg = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "validate_filter_query",
                bind_scope(query, 0, 0),
            )
        except Exception as e:
            self.logger.error(f"Failed to validate raw filter {query!r}: {e!r}")
            self.view.on_raw_filter_validated(False, str(e), name, old_name, query)
            return

        self.view.on_raw_filter_validated(valid, error_msg, name, old_name, query)

    @log(logger=logger)
    def _refuse_filter(self, message: str) -> None:
        """
        Report why a filter could not be validated.

        There is nothing to clear on the way out: the filter's name travels through the
        request and back rather than being parked on the View, so a refused name cannot
        be left behind for the next validation that succeeds to commit.

        :param message: what to tell the user
        :type message: str
        :return: None
        :rtype: None
        """
        self.add_text_to_display.emit(message, self.__class__.__name__)

    @log(logger=logger)
    def relay_query(
        self,
        query: str,
        debug: str,
        table_name: str,
        intent: Optional[str] = None,
        name: Optional[str] = None,
        old_name: Optional[str] = None,
        filter_text: Optional[str] = None,
    ) -> None:
        r"""
        Relay a query and optional debug message to the view, handling optional filter intents.

        One copy for both subset tabs, and it reaches into no View state:
        ``name``, ``old_name`` and ``filter_text`` arrive as arguments, carried from the
        request that asked for the validation, and committing the result goes through
        ``view.commit_filter`` rather than an assignment into the View's dict. Both
        matter for the same reason - a value held on the widget between asking and being
        answered is one the next request can read by mistake.

        :param query: SQL query string to display or execute.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        :param table_name: Name of the table associated with the query.
        :type table_name: str
        :param intent: 'validate_new_filter', 'validate_edited_filter', or None when
            the query is only being displayed
        :type intent: Optional[str]
        :param name: the name to commit the filter under, carried from the request
        :type name: Optional[str]
        :param old_name: on an edit, the name being replaced; None when adding
        :type old_name: Optional[str]
        :param filter_text: the expression to commit under ``name``, as the user
            wrote it; the query built around it is displayed, not stored
        :type filter_text: Optional[str]
        :return: None
        :rtype: None
        """

        if debug and not query:
            # Also on the display panel, not only in the modal: the dialog is
            # dismissed before the user gets back to the filter text, and the
            # message is often a set of instructions for correcting it.
            self.view.add_text_to_display.emit(debug, self.__class__.__name__)
            QMessageBox.warning(
                self.view,
                "Invalid Filter",
                f"The filter could not be validated:\n\n{debug}",
            )
            return

        self.view.set_query(query, table_name)

        if intent == "validate_new_filter":
            if name is not None:
                suffixed_name = (
                    f"{name}_assisted" if not name.endswith("_assisted") else name
                )
                self.view.commit_filter(suffixed_name, filter_text)

                if not filter_text:
                    self.view.add_text_to_display.emit(
                        f"Filter '{suffixed_name}' uses all rows (no WHERE clause).",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{suffixed_name}' added.", self.__class__.__name__
                )

                self.view.replace_filter_item(suffixed_name)

        elif intent == "validate_edited_filter":
            new_name = name
            new_filter = filter_text

            if new_name is not None:
                suffixed_new_name = (
                    f"{new_name}_assisted"
                    if not new_name.endswith("_assisted")
                    else new_name
                )
                self.view.commit_filter(suffixed_new_name, new_filter, old_name)

                if not new_filter:
                    self.view.add_text_to_display.emit(
                        f"Filter '{suffixed_new_name}' uses all rows (no WHERE clause) -> FULL DATASET.",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{old_name}' updated to '{suffixed_new_name}'.",
                    self.__class__.__name__,
                )

                # NOTE: old_name is Optional[str] because an *added* filter has no
                # name to replace, but show_edit_filter_dialog always sends one, so
                # it is never None on this branch. The guarantee travels through a
                # signal connection mypy cannot follow.
                self.view.update_filter_name(old_name, suffixed_new_name)  # type: ignore[arg-type]

    @log(logger=logger)
    @override
    def get_session_state(self) -> Dict[str, Any]:
        """
        Include the view's live subset filters in this tab's session history entry.

        :return: Extra state to serialize into this tab's session history entry.
        :rtype: Dict[str, Any]
        """
        return {"subset_filters": self.view.get_subset_filters()}

    @log(logger=logger)
    @override
    def restore_session_state(self, state: Dict[str, Any]) -> None:
        """
        Restore subset filters captured by :meth:`get_session_state` onto the view.

        :param state: This tab's session history entry, as previously written by
            :meth:`get_session_state`.
        :type state: Dict[str, Any]
        """
        subset_filters = state.get("subset_filters")
        if subset_filters:
            self.view.restore_subset_filters(subset_filters)
