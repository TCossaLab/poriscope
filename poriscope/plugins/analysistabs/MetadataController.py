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
        Wire this tab's own three intents on top of the four the subset base wires.

        :return: None
        :rtype: None
        """
        super()._setup_connections()
        self.view.column_units_requested.connect(self.request_column_units)
        self.view.metadata_subset_requested.connect(self.load_metadata_subset)
        self.view.event_subset_requested.connect(self.load_event_subset)

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
    def relay_column_type(self, column_type: Optional[str]) -> None:
        """
        Relay the data type of a specified column to the view

        :param column_type: The data type of the column, or None if the loader could not resolve one.
        :type column_type: Optional[str]
        """
        self.view.set_column_type(column_type)

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

    @log(logger=logger)
    def relay_experiment_id(self, exp_id: Optional[int]) -> None:
        """
        Relay a resolved experiment id to the view.

        :param exp_id: Integer experiment id.
        :type exp_id: Optional[int]
        """
        self.view.relay_experiment_id(exp_id)
