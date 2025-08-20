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

from PySide6.QtCore import Slot
from typing_extensions import override

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
    def _init(self):
        """
        Initialize the clustering view and model components.
        """
        self.view = ClusteringView()
        self.model = ClusteringModel()

    @log(logger=logger)
    def display_write_status(self, status):
        """
        Emit a message indicating whether clustering data was successfully written.

        :param status: True if write was successful, False otherwise.
        :type status: bool
        """
        if status is True:
            self.add_text_to_display.emit(
                "Successfully wrote clustering data", self.__class__.__name__
            )
        else:
            self.add_text_to_display.emit(
                "Failed to write clustering data", self.__class__.__name__
            )

    @log(logger=logger)
    def check_cluster_column_exists(self, table_name):
        """
        Notify the view to check if a cluster column exists in the given table.

        :param table_name: Name of the table to check.
        :type table_name: str
        """
        self.view.set_cluster_column_exists(table_name)

    @log(logger=logger)
    def alter_database_status(self, status):
        """
        Inform the view whether database alteration was successful.

        :param status: Result of the database alteration operation.
        :type status: bool
        """
        self.view.set_alter_database_status(status)

    @log(logger=logger)
    @override
    def _setup_connections(self):
        """
        Connect internal view signals to their corresponding controller slots.
        """
        self.view.request_plugin_refresh.connect(self.refresh_plugin_list)

    @log(logger=logger)
    def relay_query(self, query, debug, table_name):
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
    def relay_event_data_generator(self, generator):
        """
        Send an event data generator object to the view for processing.

        :param generator: Generator yielding event data entries.
        :type generator: Generator
        """
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    def relay_plot_data(self, data):
        """
        Relay processed clustering data to the view for plotting.

        :param data: Data structure containing plot information.
        :type data: Any
        """
        self.view.set_plot_data(data)

    @log(logger=logger)
    def relay_units(self, units):
        """
        Provide units associated with each column to the view.

        :param units: Dictionary mapping column names to units.
        :type units: dict
        """
        self.view.set_units(units)

    @log(logger=logger)
    def update_column_names(self, column_names):
        """
        Update the view with a new list of column names from the database.

        :param column_names: List of column names to populate axis selection.
        :type column_names: list[str]
        """
        # Handle the column names fetched from the database
        if column_names:
            self.view.update_column_names(column_names)
            self.logger.info("Axis comboboxes updated with new column names.")
        else:
            self.logger.warning("No column names received to update.")

    @log(logger=logger)
    def update_column_units(self, column_units, axis):
        """
        Update unit labels for a given axis in the view.

        :param column_units: Mapping of column names to units.
        :type column_units: dict
        :param axis: Axis to update ('x' or 'y').
        :type axis: str
        """
        # Handle the units fetched for the columns
        if column_units:
            self.view.update_column_units(column_units, axis)
            self.logger.info("Units labels updated with new data.")

    @log(logger=logger)
    def update_plugins(self, plugin_list):
        """
        Slot to receive updated plugin list from MetaDatabaseLoader and emit update_available_plugins.

        :param plugin_list: List of available plugin keys for MetaDatabaseLoader.
        :type plugin_list: list
        """
        self.update_available_plugins.emit("MetaDatabaseLoader", plugin_list)

    @Slot()
    def refresh_plugin_list(self):
        """
        Trigger a global signal to refresh the list of available database plugins.
        """
        loader = self.view.clusteringcontrols.get_current_loader()
        if loader:
            self.global_signal.emit(
                "MetaDatabaseLoader", loader, "list_plugins", (), "update_plugins", ()
            )
