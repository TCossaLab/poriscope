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
from typing import Dict, List, Optional, override

import pandas as pd
from PySide6.QtCore import Slot

from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class ProteinController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing protein view-model logic.

    Relays queries, event data, and filter/column metadata between the
    database backend and ProteinView.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the protein view and model.
        """
        self.view = ProteinView()
        self.model = ProteinModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Connect internal view signals to their corresponding controller slots.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.event_plot_data_requested.connect(self.load_event_plot_data)
        self.view.event_distribution_data_requested.connect(
            self.load_event_distribution_data
        )
        self.view.fit_commit_requested.connect(self.check_for_existing_fit_columns)
        self.view.fit_commit_confirmed.connect(self.commit_fits)

    @log(logger=logger)
    @Slot(str)
    def check_for_existing_fit_columns(self, loader: str) -> None:
        """
        Ask whether this database already holds fit columns, and tell the View.

        Phase one of a two-phase commit. ``_commit_fits`` interleaved a plugin call
        with a modal question for the user, which no single intent can express: the
        answer to "does this already exist?" decides whether the user is asked at all.
        ``RawDataController._start_eventfinder`` has the same shape for the same
        reason.

        The table name is the answer *and* the flag - ``None`` means no such column,
        so nothing needs overwriting.

        :param loader: the database loader plugin's key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            table_name = self.model.call(
                "MetaDatabaseLoader", loader, "get_table_by_column", "prolate_volume"
            )
        except Exception as e:
            self.logger.error(f"Failed to look for existing fit columns: {e!r}")
            self.add_text_to_display.emit(
                f"Could not check {loader} for existing fit data: {e}",
                self.__class__.__name__,
            )
            return

        self.view.confirm_fit_commit(loader, table_name)

    @log(logger=logger)
    @Slot(str, object, object, object)
    def commit_fits(
        self,
        loader: str,
        fit_data: pd.DataFrame,
        units: List[Optional[str]],
        overwrite_table: Optional[str],
    ) -> None:
        """
        Drop any fit columns being replaced, then write the new ones.

        Phase two, reached either straight away when the database holds no fit data or
        once the user has approved the overwrite. The user's decision travels as
        ``overwrite_table`` rather than being held on the View between the two halves,
        which is what ``_start_eventfinder``'s filter key does.

        The DROP and DELETE statements are built here rather than in the widget - a
        free Step 4b win, since they were the last SQL this method authored.

        :param loader: the database loader plugin's key
        :type loader: str
        :param fit_data: the fitted columns to write, keyed by event id
        :type fit_data: pd.DataFrame
        :param units: one unit per written column, ``None`` where dimensionless
        :type units: List[Optional[str]]
        :param overwrite_table: the table holding fit columns to drop first, or None
        :type overwrite_table: Optional[str]
        :return: None
        :rtype: None
        """
        if overwrite_table is not None:
            columns = [column for column in fit_data.columns if column != "id"]
            queries = [
                f"ALTER TABLE {overwrite_table} DROP COLUMN {column}"
                for column in columns
            ] + [f"DELETE FROM columns WHERE name = '{column}'" for column in columns]
            try:
                succeeded = self.model.call(
                    "MetaDatabaseLoader", loader, "alter_database", queries
                )
            except Exception as e:
                self.logger.error(f"Failed to drop the existing fit columns: {e!r}")
                self.add_text_to_display.emit(
                    f"Unable to delete fit data from {loader}, you will have to clean "
                    f"it up manually: {e}",
                    self.__class__.__name__,
                )
                return
            if succeeded is not True:
                self.add_text_to_display.emit(
                    "Unable to delete fit data, you will have to clean it up manually",
                    self.__class__.__name__,
                )
                return

        try:
            written = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "add_columns_to_table",
                fit_data,
                units,
                "events",
            )
        except Exception as e:
            self.logger.error(f"Failed to write the fit data: {e!r}")
            self.add_text_to_display.emit(
                f"Could not write the fit data to {loader}: {e}",
                self.__class__.__name__,
            )
            return

        self.display_write_status(bool(written))
        self.view.on_fit_commit_finished(loader)

    @log(logger=logger)
    @Slot(str, str, object)
    def load_event_distribution_data(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Build the query for one subset, load its events, and hand both to the View.

        Step 4a, replacing four emits across three View methods. Both distribution
        modes - individual and ensemble - run this same chain, so there is one slot
        rather than one per mode.

        **The ``_raw`` branch this replaced could never work**, which is why it is
        gone rather than converted. It handed a complete ``SELECT`` to
        ``load_event_data`` as its ``conditions`` argument, and that argument is a
        WHERE-clause body: the loader spliced it in after ``WHERE``, SQLite rejected
        the result as a syntax error, ``construct_event_data_query`` returned
        ``("", debug)`` and the generator yielded nothing. Measured against a real
        loader - the same filter as an ordinary WHERE body yields every event, and as
        a raw ``SELECT`` yields none. Raw filters are refused before a plot is
        attempted now; see ``MetaSubsetTabView._refuse_raw_filters``.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the scope the filter is built against
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        try:
            # Two values: construct_event_data_query is declared
            # -> Tuple[str, str] and reports a filter it cannot build as
            # ("", debug). call() does not splat it the way the bus did.
            query, debug = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_event_data_query",
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to build the event subset query: {e!r}")
            self.add_text_to_display.emit(
                f"Could not build the event query for this subset: {e}",
                self.__class__.__name__,
            )
            return
        if not query:
            self.add_text_to_display.emit(
                debug or "The event query for this subset could not be built",
                self.__class__.__name__,
            )
            return

        try:
            generator = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_event_data",
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to load the event subset: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load this event subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if generator is None:
            self.add_text_to_display.emit(
                "No events in dataset or unable to create event generator",
                self.__class__.__name__,
            )
            return

        # Set together, once the whole chain has succeeded: the View distinguishes
        # "not fetched" from "fetched and empty" by these two being untouched.
        self.view.set_event_query(query)
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    @Slot(str, list, object, object, object, str)
    def load_event_plot_data(
        self,
        loader: str,
        event_ids: List[int],
        exp: Optional[str],
        channel: Optional[int],
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
        action_label: str,
    ) -> None:
        """
        Resolve ``event_id`` values to database ids within scope and load those rows.

        Step 4a. This was three emits spread over two View methods - resolve the
        experiment name to an id, query the events table for the primary keys of those
        ``event_id`` values within that scope, then load exactly those rows - each
        answer parked on a View attribute and read back on the next statement. Nothing
        outside the chain read the intermediate answers, so it converts as one intent
        rather than three.

        ``event_id`` is unique only within an experiment and channel, so **an
        experiment that does not resolve stops the plot** rather than widening the
        query: an unscoped match returns whichever channel's row happens to share the
        number. The View's version appended the scope only when the lookup had
        succeeded, which is the same fault ``MetadataController`` was given this guard
        for on 2026-09-09.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the ``event_id`` values the navigation snapped to
        :type event_ids: List[int]
        :param exp: the experiment name in scope, or None
        :type exp: Optional[str]
        :param channel: the channel in scope, or None
        :type channel: Optional[int]
        :param experiments_and_channels: the scope ``load_event_data`` wants
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
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

        id_list = ",".join(str(eid) for eid in event_ids)
        where_parts = [f"event_id IN ({id_list})"]

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
            where_parts.append(f"experiment_id = {exp_id}")

        if channel is not None:
            where_parts.append(f"channel_id = {channel}")

        # event_id comes back alongside id because the caller re-sorts the rows into
        # the order it asked for them in, which it cannot do from the primary keys.
        query = f"SELECT id, event_id FROM events WHERE {' AND '.join(where_parts)}"
        try:
            id_result = self.model.call(
                "MetaDatabaseLoader", loader, "query_database_directly", query
            )
        except Exception as e:
            self.logger.error(f"Failed to resolve event ids for {event_ids}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not look up these events in {loader}: {e}",
                self.__class__.__name__,
            )
            return

        if id_result is None or id_result.empty:
            self.add_text_to_display.emit(
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return
        if "id" not in id_result.columns:
            self.logger.error(
                f"{loader} returned rows with no id column for query {query!r}"
            )
            return

        db_ids = ",".join(str(i) for i in id_result["id"].tolist())
        try:
            generator = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_event_data",
                f"e.id IN ({db_ids})",
                experiments_and_channels,
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
                f"No data available for the requested {action_label}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    def check_column_exists(self, table_name: Optional[str]) -> None:
        """
        Notify the view to check if a fit-data column exists in the given table.

        :param table_name: Name of the table containing the queried column, or None if the loader could not resolve one.
        :type table_name: Optional[str]
        """
        self.view.set_column_exists(table_name)

    @log(logger=logger)
    def alter_database_status(self, status: bool) -> None:
        """
        Inform the view whether database alteration was successful.

        :param status: Result of the database alteration operation.
        :type status: bool
        """
        self.view.set_alter_database_status(status)
