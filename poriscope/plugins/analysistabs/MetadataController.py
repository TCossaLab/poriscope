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

from typing_extensions import override

from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaController import MetaController


@inherit_docstrings
class MetadataController(MetaController):
    """
    Subclass of MetaController for managing metadata view-model logic.

    Relays plot data, query results, and column/unit updates to the view.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self):
        """
        Initialize the metadata view and model.
        """
        self.view = MetadataView()
        self.model = MetadataModel()

    @log(logger=logger)
    @override
    def _setup_connections(self):
        """
        Setup signal-slot connections between view and controller.

        This method is required to satisfy the abstract base class but may remain empty.
        """
        # Implement any required connections here
        # This function can remain empty if no additional setup is needed,
        # but it must exist to satisfy the abstract base class requirement.
        pass

    @log(logger=logger)
    def relay_table_by_column(self, table):
        """
        Relay a column-grouped table to the view.

        :param table: Dictionary representing a table organized by column.
        :type table: dict
        """
        self.view.set_table_by_column(table)

    @log(logger=logger)
    def relay_baseline_duration(self, duration):
        """
        Relay the computed baseline duration to the view.

        :param duration: Duration of the baseline in appropriate units.
        :type duration: float
        """
        self.view.set_baseline_duration(duration)

    @log(logger=logger)
    def set_exported_event_count(self, written):
        """
        Update the view with the number of events exported.

        :param written: Number of events successfully written to file.
        :type written: int
        """
        self.view.set_exported_event_count(written)

    @log(logger=logger)
    def relay_query(self, query, debug, table_name, *args):
        """
        Relay a query and optional debug message to the view, handling optional filter intents.

        :param query: SQL query string to display or execute.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        :param table_name: Name of the table associated with the query.
        :type table_name: str
        :param args: Optional intent string (e.g. 'validate_new_filter', 'validate_edited_filter').
        :type args: tuple
        """
        intent = args[0] if args else None

        if debug and not query:
            self.view.add_text_to_display.emit(debug, self.__class__.__name__)
            if intent in ("validate_new_filter", "validate_edited_filter"):
                self.view.clear_pending_filter_state()
            return

        self.view.set_query(query, table_name)

        if intent == "validate_new_filter":
            name = self.view._pending_filter_name
            filter_text = self.view._pending_filter_text

            if name is not None:
                self.view.subset_filters[name] = filter_text or ""

                if not filter_text:
                    self.view.add_text_to_display.emit(
                        f"Filter '{name}' uses all rows (no WHERE clause).",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{name}' added.", self.__class__.__name__
                )

                self.view.replace_filter_item(name)

        elif intent == "validate_edited_filter":
            old_name = self.view._pending_old_filter_name
            new_name = self.view._pending_filter_name
            new_filter = self.view._pending_filter_text

            if new_name is not None:
                if old_name is not None:
                    self.view.subset_filters.pop(old_name, None)
                self.view.subset_filters[new_name] = new_filter or ""

                if not new_filter:
                    self.view.add_text_to_display.emit(
                        f"Filter '{new_name}' uses all rows (no WHERE clause) -> FULL DATASET.",
                        self.__class__.__name__,
                    )

                self.view.add_text_to_display.emit(
                    f"Filter '{old_name}' updated to '{new_name}'.",
                    self.__class__.__name__,
                )

                self.view.update_filter_name(old_name, new_name)

        self.view.clear_pending_filter_state()

    @log(logger=logger)
    def relay_event_query(self, query, debug):
        """
        Relay an event-level query to the view.

        :param query: SQL query string for fetching event data.
        :type query: str
        :param debug: Debug message to display if query is empty.
        :type debug: str
        """
        if debug and not query:
            self.add_text_to_display.emit(debug, self.__class__.__name__)
        self.view.set_event_query(query)

    @log(logger=logger)
    def relay_event_data_generator(self, generator):
        """
        Relay a generator for event data overlays to the view.

        :param generator: Generator yielding event data for overlay purposes.
        :type generator: Generator
        """
        # for event overlays
        self.view.set_event_data_generator(generator)

    @log(logger=logger)
    def relay_event_plot_data_generator(self, generator):
        """
        Relay a generator for event plotting to the view.

        :param generator: Generator yielding event data for plotting.
        :type generator: Generator
        """
        # for plotting events
        self.view.set_event_plot_data_generator(generator)

    @log(logger=logger)
    def relay_plot_data(self, data):
        """
        Relay processed data to the view for plotting.

        :param data: Structured plot data.
        :type data: Any
        """
        self.view.set_plot_data(data)

    @log(logger=logger)
    def relay_units(self, units):
        """
        Provide column unit labels to the view.

        :param units: Dictionary mapping column names to units.
        :type units: dict
        """
        self.view.set_units(units)

    @log(logger=logger)
    def update_column_names(self, column_names):
        """
        Update the view with new column names.

        :param column_names: List of column names retrieved from the database.
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
        Update the view with unit labels for a specific axis.

        :param column_units: Dictionary of column names and their corresponding units.
        :type column_units: dict
        :param axis: Axis to apply the units to (e.g., 'x' or 'y').
        :type axis: str
        """
        # Handle the units fetched for the columns
        self.view.update_column_units(column_units, axis)

    @log(logger=logger)
    def get_experiment_names_for_tree(self, experiments: list[str], loader_name: str):
        """
        Provide a list of experiment names to the view for the tree display.

        :param experiments: List of experiment names fetched from the database.
        :type experiments: list[str]
        :param loader_name: Name of the data loader associated with the experiments.
        :type loader_name: str
        """
        # Handle experiments fetched from DB
        self.view.get_experiment_names_for_tree(experiments, loader_name)

    @log(logger=logger)
    def get_experiment_structure_ready(
        self, structure: dict[str, list[int]], loader_name: str
    ):
        """
        Pass experiment-to-channel mappings to the view in display-ready format.

        :param structure: Dictionary mapping experiment names to a list of channel IDs.
        :type structure: dict[str, list[int]]
        :param loader_name: Name of the data loader providing the structure.
        :type loader_name: str
        """
        self.logger.debug(
            f"Received full experiment-channel structure for {loader_name}: {structure}"
        )

        # Convert all channels to strings (for display)
        str_structure = {
            exp: [str(ch) for ch in ch_list] for exp, ch_list in structure.items()
        }

        # Store the original structure temporarily
        self.view.available_experiment_and_channels_by_loader[loader_name] = str_structure
        self.view.selected_experiment_and_channels_by_loader[loader_name] = str_structure.copy()
        
        # Check for conflicts across all loaders and apply disambiguation if needed
        self._apply_experiment_disambiguation()

    @log(logger=logger)
    def _apply_experiment_disambiguation(self):
        """
        Detect experiment name conflicts across loaders and request disambiguated names.
        """
        all_loaders = self.view.available_experiment_and_channels_by_loader
        
        if len(all_loaders) <= 1:
            # No conflicts possible with single loader
            return
            
        # Collect all experiment names by loader for conflict detection
        experiments_by_loader = {
            loader: list(experiments.keys()) 
            for loader, experiments in all_loaders.items()
        }
        
        # Find experiments with conflicts
        all_experiments = []
        for experiments in experiments_by_loader.values():
            all_experiments.extend(experiments)
            
        conflicts = set()
        for exp_name in set(all_experiments):
            count = sum(1 for experiments in experiments_by_loader.values() 
                       if exp_name in experiments)
            if count > 1:
                conflicts.add(exp_name)
        
        if not conflicts:
            # No conflicts found
            return
            
        self.logger.info(f"Experiment name conflicts detected: {conflicts}")
        
        # Request disambiguated names for each loader that has conflicting experiments
        for loader_name, experiments in experiments_by_loader.items():
            if any(exp in conflicts for exp in experiments):
                self.logger.debug(f"Requesting disambiguated names for loader: {loader_name}")
                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader_name, 
                    "get_disambiguated_experiment_names",
                    (experiments_by_loader,),
                    self.update_disambiguated_experiments, 
                    (loader_name,)
                )

    @log(logger=logger)
    def update_disambiguated_experiments(self, disambiguated_names: list[str], loader_name: str):
        """
        Update the experiment structure with disambiguated names from a loader.

        :param disambiguated_names: List of disambiguated experiment names 
        :type disambiguated_names: list[str]
        :param loader_name: Name of the data loader
        :type loader_name: str
        """
        self.logger.debug(f"Updating disambiguated experiments for {loader_name}: {disambiguated_names}")
        
        # Get the original structure
        original_structure = self.view.available_experiment_and_channels_by_loader.get(loader_name, {})
        original_names = list(original_structure.keys())
        
        if len(original_names) != len(disambiguated_names):
            self.logger.warning(f"Mismatch in experiment count for {loader_name}: {len(original_names)} vs {len(disambiguated_names)}")
            return
            
        # Create mapping from original to disambiguated names
        name_mapping = dict(zip(original_names, disambiguated_names))
        
        # Update the structure with new names
        updated_structure = {}
        for original_name, channels in original_structure.items():
            new_name = name_mapping.get(original_name, original_name)
            updated_structure[new_name] = channels
            
        # Update both available and selected structures
        self.view.available_experiment_and_channels_by_loader[loader_name] = updated_structure
        self.view.selected_experiment_and_channels_by_loader[loader_name] = updated_structure.copy()
        
        self.logger.info(f"Successfully updated {len(updated_structure)} experiments for {loader_name}")

    @log(logger=logger) 
    def update_disambiguated_experiments(self, disambiguated_names: list[str], loader_name: str):
        """
        Update experiment structure with disambiguated names to resolve conflicts.
        
        :param disambiguated_names: List of experiment names with disambiguation applied
        :type disambiguated_names: list[str]
        :param loader_name: Name of the loader providing the disambiguated names  
        :type loader_name: str
        """
        if loader_name not in self.view.available_experiment_and_channels_by_loader:
            return
            
        original_structure = self.view.available_experiment_and_channels_by_loader[loader_name]
        original_names = list(original_structure.keys())
        
        if len(disambiguated_names) != len(original_names):
            self.logger.error(f"Disambiguated names count mismatch for {loader_name}")
            return
            
        # Create new structure with disambiguated names
        new_structure = {}
        for original_name, disambiguated_name in zip(original_names, disambiguated_names):
            if original_name in original_structure:
                new_structure[disambiguated_name] = original_structure[original_name]
                
        # Update both available and selected structures
        self.view.available_experiment_and_channels_by_loader[loader_name] = new_structure
        self.view.selected_experiment_and_channels_by_loader[loader_name] = new_structure.copy()
        
        self.logger.debug(f"Updated {loader_name} with disambiguated experiments: {list(new_structure.keys())}")
