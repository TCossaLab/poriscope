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

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController


@inherit_docstrings
class MetadataController(MetaSubsetTabController):
    """
    Subclass of MetaSubsetTabController for managing metadata view-model logic.

    Relays plot data, query results, and column/unit updates to the view.
    """

    logger = logging.getLogger(__name__)

    #: The last SQL echoed to the status panel, so that replotting the same subset
    #: does not repeat it. Not persisted: it is display state, and a fresh session
    #: showing the query once more is the right behaviour.
    _last_echoed_query: str = ""

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the metadata view and model.
        """
        self.view = MetadataView()
        self.model = MetadataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Wire this tab's own seven intents on top of the four the subset base wires.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.column_units_requested.connect(self.request_column_units)
        self.view.column_type_requested.connect(self.request_column_type)
        self.view.metadata_subset_requested.connect(self.load_metadata_subset)
        self.view.event_subset_requested.connect(self.load_event_subset)
        self.view.event_plot_data_requested.connect(self.load_event_plot_data)
        self.view.plot_features_requested.connect(self.request_plot_features)
        self.view.csv_subset_export_requested.connect(self.export_csv_subset)

    @log(logger=logger)
    @Slot(str, list, str, object)
    def load_metadata_subset(
        self,
        loader: str,
        columns: List[str],
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Fetch one metadata subset - query, rows and units - and hand it to the View.

        Step 4a replaced three ``global_signal`` emits that ``_overlay_plot`` made in
        sequence, reading each answer back off an attribute on the next statement.
        Two of those attributes were never cleared first, so a dispatch that failed
        was indistinguishable from one that succeeded: ``self.query`` kept the
        previous subset's query and passed the ``== ""`` guard, and ``self.units``
        kept the previous column's units and was appended to the list, labelling the
        axis wrongly. The View clears all three now and this method sets them only
        once every part has been fetched, so a partial failure is visible as such.

        This is also where the SQL the user sees comes from: the query echoed to the
        status panel is **the one that runs**, not the smaller one that validated the
        filter, and it is echoed only when it differs from the last one shown.

        :param loader: the database loader plugin's key
        :type loader: str
        :param columns: the columns this plot type needs, in axis order
        :type columns: List[str]
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        try:
            query, debug, table_name = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "construct_metadata_query",
                columns,
                sql_filter,
                experiments_and_channels,
            )
        except Exception as e:
            # Previously swallowed by the dispatcher, which left the View reading the
            # previous subset's query back and plotting it under this subset's label.
            self.logger.error(f"Failed to build the subset query: {e!r}")
            self.add_text_to_display.emit(
                f"Could not build the query for this subset: {e}",
                self.__class__.__name__,
            )
            return

        if not query:
            self.add_text_to_display.emit(
                debug or "The subset query could not be built",
                self.__class__.__name__,
            )
            return

        try:
            plot_data = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "load_metadata",
                columns,
                sql_filter,
                experiments_and_channels,
            )
            units = [
                self.model.call(
                    "MetaDatabaseLoader", loader, "get_column_units", column
                )
                for column in columns
            ]
        except Exception as e:
            self.logger.error(f"Failed to load the subset: {e!r}")
            self.add_text_to_display.emit(
                f"Could not load this subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        # Set together, after everything succeeded: the View's guards distinguish
        # "not fetched" from "fetched and empty", and a half-set bundle would break
        # that distinction.
        self.view.set_query(query, table_name)
        self.view.update_plot_data(plot_data)
        self.view.set_column_units(units)
        self._echo_applied_query(query, table_name)

    @log(logger=logger)
    @Slot(str, str, object)
    def load_event_subset(
        self,
        loader: str,
        sql_filter: str,
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Fetch one event-data subset - query and generator - and hand it to the View.

        The same conversion as ``load_metadata_subset``, for the event-data plots.
        Both of its answers were unguarded reads before Step 4a: a failed
        ``load_event_data`` left the previous subset's generator in place and the
        tab replotted that subset's events under this one's label.

        :param loader: the database loader plugin's key
        :type loader: str
        :param sql_filter: the subset filter's WHERE-clause body, empty for all rows
        :type sql_filter: str
        :param experiments_and_channels: the experiment and channel scope, or None
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
        try:
            query = self.model.call(
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
                "The event query for this subset could not be built",
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

        self.view.set_event_query(query)
        self.view.set_event_data_generator(generator)
        self._echo_applied_query(query, "events")

    @log(logger=logger)
    def _echo_applied_query(self, query: str, table_name: str) -> None:
        """
        Put the query that actually ran on the status panel, once per distinct query.

        What the panel used to show was the *validation* query built when the filter
        was created, which is a different query from the one that pulls the subset -
        it was built from a fixed three-column guess, so it joined all three metadata
        tables whatever the filter referenced. This shows the real one, whose joins
        are whatever the filter and the chosen axes actually need: one table,
        two or three.

        Deduplicated because a single plot builds one query per experiment and
        channel in scope and replotting is common, so echoing every one would bury
        the panel. Only a query that differs from the last one shown is echoed.

        :param query: the SQL that was run
        :type query: str
        :param table_name: the table its id column belongs to
        :type table_name: str
        :return: None
        :rtype: None
        """
        stripped = query.strip()
        if stripped == self._last_echoed_query:
            return
        self._last_echoed_query = stripped
        self.add_text_to_display.emit(
            f"SQL ({table_name}):\n{stripped}", self.__class__.__name__
        )

    @log(logger=logger)
    @Slot(str, str)
    def request_column_type(self, loader: str, column: str) -> None:
        """
        Fetch one column's declared type, for the categorical-histogram guard.

        Step 4a. The View clears the answer before asking, so a lookup that failed
        leaves it ``None`` and the guard refuses the plot - which is what the bus
        produced by accident, and is now what it produces on purpose.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column whose type is wanted
        :type column: str
        :return: None
        :rtype: None
        """
        try:
            column_type = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_type", column
            )
        except Exception as e:
            self.logger.error(f"Failed to read the type of column {column}: {e!r}")
            return
        self.view.set_column_type(column_type)

    @log(logger=logger)
    @Slot(str, list, object, object, object)
    def load_event_plot_data(
        self,
        loader: str,
        event_ids: List[int],
        exp: Optional[str],
        channel: Optional[int],
        experiments_and_channels: Optional[Dict[str, List[Optional[int]]]],
    ) -> None:
        """
        Load the full data of specific events, named by their ``event_id`` values.

        Step 4a replaced a three-emit chain the View ran a statement at a time:
        resolve the experiment name to an id, query the events table for the primary
        keys of those event_ids within the experiment and channel, then load exactly
        those rows. Each answer was parked on an attribute and read back on the next
        line, and each read was guarded only by having cleared the attribute first.

        The scoping is the reason the middle query exists at all: ``event_id`` is
        unique only within a channel, so an unscoped match picks up rows from other
        channels that happen to share one.

        **One behaviour change.** An experiment name that does not resolve now stops
        the plot and says so. Before, the bus swallowed the failure, the id came back
        ``None``, and the query ran *unscoped* - which is the same "plots the wrong
        subset" class of fault Step 4a's earlier commits fixed, silently returning
        another channel's events under this channel's label.

        :param loader: the database loader plugin's key
        :type loader: str
        :param event_ids: the event_id values to plot, already snapped to the cache
        :type event_ids: List[int]
        :param exp: the experiment the events belong to, or None to leave it out of scope
        :type exp: Optional[str]
        :param channel: the channel the events belong to, or None for all channels
        :type channel: Optional[int]
        :param experiments_and_channels: the scope handed on to ``load_event_data``
        :type experiments_and_channels: Optional[Dict[str, List[Optional[int]]]]
        :return: None
        :rtype: None
        """
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
                    f"{loader} has no experiment named {exp}, so these events cannot "
                    "be scoped to it",
                    self.__class__.__name__,
                )
                return
            where_parts.append(f"experiment_id = {exp_id}")

        if channel is not None:
            where_parts.append(f"channel_id = {channel}")

        query = f"SELECT id FROM events WHERE {' AND '.join(where_parts)}"
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
                f"No data available for plotting with indices in the specified range {event_ids}",
                self.__class__.__name__,
            )
            return
        if "id" not in id_result.columns:
            # A populated result without the column it was asked for means the loader
            # did not honour its own contract, which is a different problem from an
            # empty subset and would raise on the read below.
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
                f"No data available for plotting with indices in the specified range {event_ids}",
                self.__class__.__name__,
            )
            return

        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    @Slot(str, int, int, int)
    def request_plot_features(
        self, loader: str, experiment_id: int, channel_id: int, event_id: int
    ) -> None:
        """
        Fetch one event's fitted features and hand them to the View.

        Step 4a. Emitted once per event on the plot path, so a failure is logged and
        the event is plotted without features, as it was before - the View clears the
        six feature attributes before each request and reads them back after, so an
        event whose lookup failed gets none rather than the previous event's.

        ``update_features``' label-length validation is called here rather than
        inlined, and its ``ValueError`` is caught for the same reason the bus caught
        it: one fitter returning mismatched labels should not abandon the plot.

        :param loader: the database loader plugin's key
        :type loader: str
        :param experiment_id: the event's experiment id
        :type experiment_id: int
        :param channel_id: the event's channel id
        :type channel_id: int
        :param event_id: the event's id within that channel
        :type event_id: int
        :return: None
        :rtype: None
        """
        try:
            features = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "get_plot_features",
                experiment_id,
                channel_id,
                event_id,
            )
            self.update_features(*features)
        except Exception as e:
            self.logger.error(
                f"Features for event {event_id} in channel {channel_id} of "
                f"experiment {experiment_id} could not be loaded, skipping: {e!r}"
            )

    @log(logger=logger)
    @Slot(str, str, str, object, object, int)
    def export_csv_subset(
        self,
        loader: str,
        folder: str,
        name: str,
        subset_filter: Optional[str],
        experiments_and_channels: Optional[Dict[str, List[str]]],
        export_index: int,
    ) -> None:
        """
        Start writing one filtered subset to CSV in a worker thread.

        Step 4a, and the second emit in this step that was not an emit-then-read: the
        plugin returns a progress generator and the bus passed it straight into
        ``set_generator``, with the export's index, the loader key and the metaclass
        travelling as the bus's ``ret_args``. ``RawDataController.commit_events`` is
        the same shape.

        The View's index only advances for an export that was staged, which is what
        ``on_subset_export_started`` says, so a failed export does not consume a name.

        :param loader: the database loader plugin's key
        :type loader: str
        :param folder: the folder to write the subset into
        :type folder: str
        :param name: the name to append to the exported filenames
        :type name: str
        :param subset_filter: the single selected filter, or None for the whole dataset
        :type subset_filter: Optional[str]
        :param experiments_and_channels: the experiment and channel scope
        :type experiments_and_channels: Optional[Dict[str, List[str]]]
        :param export_index: the index this export's worker is keyed under
        :type export_index: int
        :return: None
        :rtype: None
        """
        try:
            generator = self.model.call(
                "MetaDatabaseLoader",
                loader,
                "export_subset_to_csv",
                folder,
                name,
                subset_filter,
                experiments_and_channels,
            )
        except Exception as e:
            self.logger.error(f"Failed to export subset {name}: {e!r}")
            self.add_text_to_display.emit(
                f"Could not export this subset from {loader}: {e}",
                self.__class__.__name__,
            )
            return

        self.model.set_generator(generator, export_index, loader, "MetaDatabaseLoader")
        self.model.run_generators(loader)
        self.view.on_subset_export_started()

    @log(logger=logger)
    @Slot(str, str, str)
    def request_column_units(self, loader: str, column: str, axis: str) -> None:
        """
        Fetch one column's units and apply them to one axis label.

        Step 4a. The axis travels with the request and back out again, which is what the
        bus carried in its ``ret_args``. This is Metadata's alone: ``update_units`` moved
        down from ``MetaSubsetTabView`` in the same commit, because the protein tab has no
        units label to write to.

        :param loader: the database loader plugin's key
        :type loader: str
        :param column: the column whose units are wanted
        :type column: str
        :param axis: the axis whose label they belong to
        :type axis: str
        :return: None
        :rtype: None
        """
        try:
            column_units = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_units", column
            )
        except Exception as e:
            self.logger.error(f"Failed to request units for column {column}: {repr(e)}")
            return
        self.view.update_column_units(column_units, axis)

    @log(logger=logger)
    def update_features(
        self,
        vertical: Optional[list[float]] = None,
        horizontal: Optional[list[float]] = None,
        points: Optional[list[tuple[float, float]]] = None,
        vlabels: Optional[list[str]] = None,
        hlabels: Optional[list[str]] = None,
        plabels: Optional[list[str]] = None,
    ) -> None:
        """
        Update the plot with visual annotations including vertical lines, horizontal lines, and point markers.

        Validates that each visual feature has a corresponding label (or explicit None) if labels are provided.

        :param vertical: Vertical line positions for the event being plotted.
        :type vertical: Optional[list[float]]
        :param horizontal: Horizontal line positions for the event being plotted.
        :type horizontal: Optional[list[float]]
        :param points: (x, y) point coordinates for the event being plotted.
        :type points: Optional[list[tuple[float, float]]]
        :param vlabels: Labels for the vertical lines.
        :type vlabels: Optional[list[str]]
        :param hlabels: Labels for the horizontal lines.
        :type hlabels: Optional[list[str]]
        :param plabels: Labels for the point markers.
        :type plabels: Optional[list[str]]
        :raises ValueError: If a label list is provided and its length does not match the corresponding feature list.
        """
        if (
            vertical is not None
            and vlabels is not None
            and len(vlabels) != len(vertical)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every vertical line feature, or no labels at all"
            )
        if (
            horizontal is not None
            and hlabels is not None
            and len(hlabels) != len(horizontal)
        ):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every horizontal line feature, or no labels at all"
            )
        if points is not None and plabels is not None and len(points) != len(plabels):
            raise ValueError(
                "There must be a label (which can be explicitly None) for every point feature, or no labels at all"
            )
        self.view.update_plot_features(
            vertical, horizontal, points, vlabels, hlabels, plabels
        )

    @log(logger=logger)
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        Relay the result of a direct DB query to the view.

        :param result: DataFrame returned by query_database_directly.
        :type result: Optional[pd.DataFrame]
        """
        self.view.relay_query_result(result)
