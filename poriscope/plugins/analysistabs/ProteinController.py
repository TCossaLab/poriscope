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

    @log(logger=logger)
    def relay_query_result(self, result: Optional[pd.DataFrame]) -> None:
        """
        Relay a direct database query result to the view.
        Used by ProteinView._rebuild_event_id_cache to receive the list of filtered event_ids.

        :param result: DataFrame returned by query_database_directly, or None if the query failed.
        :type result: Optional[pd.DataFrame]
        """
        self.view.relay_query_result(result)
