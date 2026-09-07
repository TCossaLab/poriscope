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
from typing import Any, Dict, Generator, List, Optional, override

import pandas as pd

from poriscope.plugins.analysistabs.ClusteringModel import ClusteringModel
from poriscope.plugins.analysistabs.ClusteringView import ClusteringView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class ClusteringController(MetaController):
    """
    Subclass of MetaController for managing clustering view-model logic.

    Handles queries, data relaying, and view updates.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        Initialize the clustering view and model components.
        """
        self.view = ClusteringView()
        self.model = ClusteringModel()

    @log(logger=logger)
    @override
    def _setup_connections(self) -> None:
        """
        Connect internal view signals to their corresponding controller slots.
        """
        self.view.cluster_requested.connect(self.cluster)
        self.view.column_names_requested.connect(self.request_column_names)
        self.view.column_units_requested.connect(self.request_column_units)
        self.view.cluster_column_check_requested.connect(self.check_cluster_column)
        self.view.cluster_commit_requested.connect(self.commit_clusters)

    @log(logger=logger)
    def cluster(
        self,
        frame: pd.DataFrame,
        exclude_cols: List[str],
        method: str,
        params: Dict[str, Any],
    ) -> None:
        """
        Cluster a frame the View has loaded, and hand the result back to it.

        Decision B's command path, the same shape as
        ``RawDataController.calculate_psd``: the View emits an intent, this slot calls
        the Model, and the result goes back through a setter on the View. Step 4c
        introduced it, when the clustering moved off the widget.

        A failure is reported on the status panel rather than raised, because nothing
        above this slot is a call site that could handle it - Qt invoked it from a
        signal.

        :param frame: the rows to cluster, already filtered and log-scaled
        :type frame: pd.DataFrame
        :param exclude_cols: columns to leave un-normalized
        :type exclude_cols: List[str]
        :param method: the clustering method the user chose
        :type method: str
        :param params: that method's already-parsed parameters
        :type params: Dict[str, Any]
        :return: None
        :rtype: None
        """
        try:
            clustered, labels, confidence = self.model.cluster(
                frame, exclude_cols, method, params
            )
        except (ValueError, KeyError, TypeError) as e:
            self.logger.error(f"Unable to cluster data: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to cluster data: {e}", self.__class__.__name__
            )
            return
        self.view.set_clustering_result(clustered, labels, confidence)

    @log(logger=logger)
    def relay_query(self, query: str, debug: str, table_name: str) -> None:
        """
        Relay the SQL query and target table to the view for display or execution.

        :param query: SQL query string to execute or preview.
        :type query: str
        :param debug: Optional debug message to display.
        :type debug: str
        :param table_name: Name of the database table being queried.
        :type table_name: str
        """
        if debug and not query:
            self.add_text_to_display.emit(debug, self.__class__.__name__)
        self.view.set_query(query, table_name)

    @log(logger=logger)
    def relay_event_data_generator(self, generator: Generator) -> None:
        """
        Send an event data generator object to the view for processing.

        :param generator: Generator yielding event data entries.
        :type generator: Generator
        """
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    def relay_plot_data(self, data: Any) -> None:
        """
        Relay processed clustering data to the view for plotting.

        :param data: Data structure containing plot information.
        :type data: Any
        """
        self.view.set_plot_data(data)

    @log(logger=logger)
    def relay_units(self, units: Dict[str, Optional[str]]) -> None:
        """
        Provide units associated with each column to the view.

        :param units: Dictionary mapping column names to units.
        :type units: Dict[str, Optional[str]]
        """
        self.view.set_units(units)

    @log(logger=logger)
    def check_cluster_column(self, loader: str) -> None:
        """
        Ask the database whether a clustering result is already stored.

        First of the commit path's two round trips; the View shows the overwrite
        confirmation when this comes back non-None.

        :param loader: the database loader's plugin key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            existing_table = self.model.find_cluster_column_table(loader)
        except Exception as e:
            self.logger.error(f"Unable to check for cluster columns: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to check for existing clustering data: {e}",
                self.__class__.__name__,
            )
            return
        self.view.on_cluster_column_checked(loader, existing_table)

    @log(logger=logger)
    def commit_clusters(
        self,
        loader: str,
        cluster_data: Any,
        table_name: str,
        drop_from_table: Optional[str],
    ) -> None:
        """
        Write the clustering result, dropping any existing one first.

        Second of the commit path's two round trips. **A failed drop stops the
        commit**, which is what the View's ``operation_success`` check did before Step
        4a - writing the new columns on top of a half-deleted old result would leave
        the database in a state the user has to repair by hand.

        :param loader: the database loader's plugin key
        :type loader: str
        :param cluster_data: the id, label and confidence columns to write
        :type cluster_data: Any
        :param table_name: the table to write them into
        :type table_name: str
        :param drop_from_table: the table to drop an existing result from, or None
        :type drop_from_table: Optional[str]
        :return: None
        :rtype: None
        """
        if drop_from_table is not None:
            try:
                dropped = self.model.drop_cluster_columns(loader, drop_from_table)
            except Exception as e:
                self.logger.error(f"Unable to delete clustering data: {repr(e)}")
                dropped = False
            if dropped is not True:
                self.add_text_to_display.emit(
                    "Unable to delete clustering data, you will have to clean it up manually",
                    self.__class__.__name__,
                )
                return

        try:
            status = self.model.commit_cluster_columns(loader, cluster_data, table_name)
        except Exception as e:
            self.logger.error(f"Unable to write clustering data: {repr(e)}")
            status = False

        self.display_write_status(status)
        self.view.on_clusters_committed(loader, bool(status))

    @log(logger=logger)
    def request_column_names(self, loader: str) -> None:
        """
        Fetch the loader's column names and hand them to the View.

        Step 4a: this replaces a ``global_signal`` round trip whose answer arrived
        seven hops later through a return function named by string. A failed lookup is
        reported on the status panel here rather than being logged inside
        ``_dispatch_to`` and leaving the View with the previous loader's columns.

        :param loader: the database loader's plugin key
        :type loader: str
        :return: None
        :rtype: None
        """
        try:
            column_names = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_names_by_table"
            )
        except Exception as e:
            self.logger.error(f"Failed to read column names from {loader}: {repr(e)}")
            self.add_text_to_display.emit(
                f"Unable to read columns from {loader}: {e}", self.__class__.__name__
            )
            return
        self.update_column_names(column_names)

    @log(logger=logger)
    def request_column_units(self, loader: str, column: str) -> None:
        """
        Fetch one column's unit string and hand it to the View.

        Same conversion as ``request_column_names``.

        :param loader: the database loader's plugin key
        :type loader: str
        :param column: the column whose unit is wanted
        :type column: str
        :return: None
        :rtype: None
        """
        try:
            column_units = self.model.call(
                "MetaDatabaseLoader", loader, "get_column_units", column
            )
        except Exception as e:
            self.logger.error(
                f"Failed to read units for {column} from {loader}: {repr(e)}"
            )
            return
        self.update_column_units(column_units, column)

    @log(logger=logger)
    def update_column_names(self, column_names: List[str]) -> None:
        """
        Update the view with a new list of column names from the database.

        :param column_names: List of column names to populate axis selection.
        :type column_names: List[str]
        """
        # Handle the column names fetched from the database
        if column_names:
            self.view.update_column_names(column_names)
            self.logger.info("Axis comboboxes updated with new column names.")
        else:
            self.logger.warning("No column names received to update.")

    @log(logger=logger)
    def update_column_units(self, column_units: Optional[str], axis: str) -> None:
        """
        Update unit labels for a given axis in the view.

        Despite the parameter names, this is a ``get_column_units`` callback: it
        receives the unit string for a single column (``None`` if the loader has
        none) followed by that column's name.

        :param column_units: Unit string for the column named by ``axis``, or None if the loader could not resolve one.
        :type column_units: Optional[str]
        :param axis: Name of the column whose unit was resolved.
        :type axis: str
        """
        # Handle the units fetched for the columns
        if column_units:
            self.view.update_column_units(column_units, axis)
            self.logger.info("Units labels updated with new data.")

    @log(logger=logger)
    def display_write_status(self, status: bool) -> None:
        """
        Notify the display panel whether clustering data was successfully written to the database.

        :param status: True if the write succeeded, False otherwise.
        :type status: bool
        """
        if status:
            self.add_text_to_display.emit(
                "Successfully wrote clustering data",
                self.__class__.__name__,
            )
        else:
            self.add_text_to_display.emit(
                "Failed to write clustering data",
                self.__class__.__name__,
            )
