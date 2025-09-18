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
# Kyle Briggs
# Alejandra Carolina González González

import logging
import re
from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt
import pandas as pd

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log

Numeric = Union[int, float, np.number]


@inherit_docstrings
class MetaDatabaseLoader(BaseDataPlugin):
    """
    What you get by inheriting from MetaDatabaseLoader
    --------------------------------------------------

    :ref:`MetaDatabaseLoader` is the base class for loading the data written by a :ref:`MetaDatabaseWriter` subclass instance or any other method that produces an equivalent format.

    Poriscope ships with :ref:`SQLiteDBLoader`, a subclass of :ref:`MetaDatabaseLoader` that reads data written by the :ref:`SQLiteDBWriter` subclass. While additional subclasses can read almost any format you desire, we strongly encourage standardization around this format. Think twice before creating additional subclasses of this base class. It is not sufficient to write just a :ref:`MetaEventLoader` subclass. In addition to this base class, you will also need a paired :ref:`MetaDatabaseWriter` subclass to write data in your target format.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, settings: Optional[dict] = None):
        """
        Initialize and set up the plugin, if settings are available at this stage
        """
        super().__init__(settings)

    # public API, MUST be implemented by subclasses
    @abstractmethod
    def get_llm_prompt(self) -> str:
        """
        :return: a prompt that gives an LLM context for the database and  how to query it
        :rtype: str

        **Purpose:** Return a prompt that will tell the LLM the structure of the database to be queried to assist users in accessing the data written in your format
        """
        pass

    @abstractmethod
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Reset the state of a specific channel for a new operation or run.

        This is called any time an operation on a channel needs to be cleaned up or reset for a new run. If channel is not None, handle only that channel, else reset all of them. In most cases for MetaDatabaseLoaders there is no need to reset and you can simplt ``pass``.
        """
        pass

    @abstractmethod
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        :param channel: channel ID
        :type channel: Optional[int]

        **Purpose:** Clean up any open file handles or memory on app exit.

        This is called during app exit or plugin deletion to ensure proper cleanup of resources that could otherwise leak. Do this for all channels if no channel is specified, otherwise limit your closure to the specified channel. If no such operation is needed, it suffices to ``pass``.
        """
        pass

    @abstractmethod
    def get_experiment_names(
        self, experiment_id: Optional[int] = None
    ) -> Optional[List[str]]:
        """
        :param experiment_id: the id of the experiment for which to fetch the name
        :type experiment_id: Optional[int]

        :return: List of experiment names, or None on failure
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve a list of all unique experiment names registered in the database, or a singleton list if an id is given.
        """
        pass

    def get_disambiguated_experiment_names(
        self, all_experiments_by_loader: Optional[dict] = None
    ) -> Optional[List[str]]:
        """
        Get experiment names with database identifiers added when conflicts exist.

        :param all_experiments_by_loader: Dict mapping loader names to their experiment lists
        :type all_experiments_by_loader: Optional[dict]

        :return: List of disambiguated experiment names, defaults to original names
        :rtype: Optional[List[str]]
        """
        # Default implementation returns original names (no disambiguation)
        return self.get_experiment_names()

    @abstractmethod
    def get_channels_by_experiment(self, experiment: str) -> Optional[List[int]]:
        """
        :param experiment: The name of the experiment.
        :type experiment: str
        :return: List of channel IDs.
        :rtype: Optional[List[int]]

        **Purpose:** Retrieve a list of all channel identifiers (the identifier, not the primary key of the channels table) associated with a given experiment name or None on failure
        """
        pass

    @abstractmethod
    def get_event_counts_by_experiment_and_channel(
        self, experiment: Optional[str] = None, channel: Optional[int] = None
    ) -> int:
        """
        :param experiment: The name of the experiment.
        :type experiment: Optional[str]
        :param channel: The index of the channel
        :type channel: Optional[int]

        :return: event count matching the conditions
        :rtype: int

        **Purpose:**  Return the number of events in the database matching the experiment name and channel identifier.

        If no channel name is provided, count across all channels for that experiment.
        If no experiment is provided, ignore channel and return the number of events in the entire database
        """
        pass

    @abstractmethod
    def get_column_units(self, column_name: str) -> Optional[str]:
        """
        :param column_name: The name of the column.
        :type column_name: str
        :return: The units of the column.
        :rtype: Optional[str]

        **Purpose:** Retrieve the units associated with a specific column name or None on failure
        """
        pass

    @abstractmethod
    def get_column_names_by_table(
        self, table: Optional[str] = None
    ) -> Optional[List[str]]:
        """
        :param table: The name of the table.
        :type table: Optional[str]
        :return: List of column names.
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve the column names available in a specified table, all columns in the database is table is not specified, or None on failure
        """
        pass

    @abstractmethod
    def get_table_names(self) -> Optional[List[str]]:
        """
        :return: List of table names.
        :rtype: Optional[List[str]]

        **Purpose:** Retrieve the names of available tables in the database or None on failure.
        """
        pass

    @abstractmethod
    def validate_filter_query(self, query: str) -> Tuple[bool, str]:
        """
        :param query: The SQL query string.
        :type query: str
        :return: ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not
        :rtype:  Tuple[bool, str]

        **Purpose:** Validate a SQL query without executing it.

        Return ``True, ""`` if the query is valid, and ``False, "[[helpful explanation]]"`` if it is not
        """
        pass

    @abstractmethod
    def get_samplerate_by_experiment_and_channel(
        self, experiment: str, channel: int
    ) -> Optional[float]:
        """
        :param experiment: The name of the experiment in the database.
        :type experiment: str
        :param channel: The channel id to get sampling rate for.
        :type channel: int
        :return: sampling rate for the specific expreiment-channel combination, or None on failure
        :rtype: Optional[float]

        **Purpose:** Retrieve the sampling rate for a given experiment and channel id, or None on failure
        """
        pass

    @abstractmethod
    def get_table_by_column(self, column: str) -> Optional[str]:
        """
        :param column: The name of the column.
        :type column: str

        :return: List of table names.
        :rtype: List[str]

        **Purpose:** Retrieve the names of the table in which the given column is found, or None on failure
        """
        pass

    @abstractmethod
    def add_columns_to_table(
        self, df: pd.DataFrame, units: List[Optional[str]], table_name: str
    ) -> bool:
        """
        :param df: A pandas DataFrame. Must contain an 'id' column corresponding to the primary key of the target table, and one or more additional columns to be added.
        :type df: pd.DataFrame
        :param units: A list of strings specifying units for the new columns to be added. Must have length equal to the number of new cols, but can contain None values
        :type units: List[Optional[str]]
        :param table_name: The name of the SQLite table to modify. This table must already exist in the databse.
        :type table_name: str

        :return: True on success, False otherwise
        :rtype: bool

        :raises ValueError: If the DataFrame does not contain an 'id' column or if the specified table does not exist.
        :raises IOError: If any write-related error occurs

        **Purpose:** Adds new columns from a pandas DataFrame to an existing SQLite table

        Create new columns in the specified table and populate them with the procided data, matching on the 'id' column against the primary id in the target table
        """
        pass

    @abstractmethod
    def alter_database(self, queries: List[str]) -> bool:
        """
        :param queries: a list of queries to  run on the database
        :type queries: List[str]

        :return: True if the operation succeeded, False otherwise
        :rtype: bool

        **Purpose:** Run a given list of queries on the database. There is no validation here, use it sparingly.
        """
        pass

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    @abstractmethod
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone=False,
    ) -> Dict[str, Dict[str, Any]]:
        """
        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Optional[ Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]

        **Purpose:** Provide a list of settings details to users to assist in instantiating an instance of your :ref:`MetaWriter` subclass.

        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.

        .. code-block:: python

           settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        Several parameter keywords are reserved: these are

        'Input File'
        'Output File'
        'Folder'

        These must have Type str and will cause the GUI to generate widgets to allow selection of these elements when used

        This function must implement returning of a dictionary of settings required to initialize the filter, in the specified format. Values in this dictionary can be accessed downstream through the ``self.settings`` class variable. This structure is a nested dictionary that supplies both values and a variety of information about those values, used by poriscope to perform sanity and consistency checking at instantiation.

        While this function is technically not abstract in :ref:`MetaEventLoader`, which already has an implementation of this function that ensures that settings will have the required ``Input File`` key available to users, in most cases you will need to override it to add any other settings required by your subclass or to specify which files types are allowed. If you need additional settings, which you almost certainly do, you **MUST** call ``super().get_empty_settings(globally_available_plugins, standalone)`` **before** any additional code that you add. For example, your implementation could look like this, to limit it to sqlite files:

        .. code:: python

            settings = super().get_empty_settings(globally_available_plugins, standalone)
            settings["Input File"]["Options"] = [
                                    "SQLite3 Files (*.sqlite3)",
                                    "Database Files (*.db)",
                                    "SQLite Files (*.sqlite)",
                                    ]
            return settings

        which will ensure that your have the ``Input File`` key and limit visible options to sqlite3 files. By default, it will accept any file type as output, hence the specification of the ``Options`` key for the relevant plugin in the example above.
        """
        settings: Dict[str, Dict[str, Any]] = {
            "Input File": {"Type": str, "Options": ["All Files (*.*)"]}
        }
        return settings

    @log(logger=logger)
    def force_serial_channel_operations(self) -> bool:
        """
        :return: True if only one channel can run at a time, False otherwise
        :rtype: bool

        **Purpose:** Indicate whether operations on different channels must be serialized (not run in parallel).
        """
        return False

    @log(logger=logger)
    def get_experiments_and_channels(self) -> Dict[str, Optional[List[int]]]:
        """
        Retrieve a mapping of experiment names to their associated channel lists.

        Calls `get_experiment_names()` to fetch all experiment identifiers,
        then maps each experiment to its corresponding list of channels using `get_channels_by_experiment()`.

        :return: Dictionary mapping experiment names to lists of channel indices.
        :rtype: dict[str, Optional[list[int]]]
        """
        experiments = self.get_experiment_names()
        if not experiments:
            return {}
        return {exp: self.get_channels_by_experiment(exp) for exp in experiments}

    @log(logger=logger)
    def get_experiment_id_by_name(self, experiment_name: str) -> Optional[int]:
        """
        Retrieve experiment ID by name, handling both original and disambiguated experiment names.

        :param experiment_name: the name of the experiment to find (can include database suffix)
        :type experiment_name: str

        :return: Experiment ID, or None if not found
        :rtype: Optional[int]
        """
        if experiment_name:
            try:
                # Handle disambiguated names like "experiment_name (database.sqlite)"
                original_name = experiment_name
                if " (" in experiment_name and experiment_name.endswith(")"):
                    # Extract original name without database suffix
                    original_name = experiment_name.split(" (")[0]
                
                query = f"SELECT id FROM experiments WHERE name = '{original_name}' LIMIT 1"
                result = self.query_database_directly(query)
                if result is not None:
                    return result.at[0, "id"]
                else:
                    return None
            except Exception as e:
                self.logger.info(f"Database query failed: {e}")
                raise
        return None

    @log(logger=logger)
    def get_database_identifier(self) -> str:
        """
        Get a unique identifier for this database to use in disambiguated experiment names.
        
        :return: A short identifier for the database (filename without extension)
        :rtype: str
        """
        # This is overridden in SQLiteDBLoader to use the actual filename
        return "db"

    @log(logger=logger)
    def export_subset_to_csv(
        self,
        output_folder: str,
        subset_name: str = "",
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Generator[float, None, None]:
        """
        Return a generator that shows progress toward outputting a csv version of the subset of the database satisfying the conditions, including both data and metadata

        :param output_folder: The folder to which the subset should be printed. This is assumed to exist already and will raise an error if it does not.
        :type output_folder: str

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param conditions: Optional string to append to filenames in the subset
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a float between 0 and 1 representing progress toward completion
        :rtype: float

        :raises: IOError if output_folder does not already exist
        :raises: ValueError if the SQL string is invalid
        """

        def tuple_builder(id_list):
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Normalize experiment names to IDs if necessary
        experiment_ids = None
        if experiments_and_channels is not None:
            # Get experiment IDs, but filter out None values and corresponding channel filters
            experiment_ids = []
            channel_filters = []
            for exp, channels in experiments_and_channels.items():
                exp_id = self.get_experiment_id_by_name(exp)
                if exp_id is not None:
                    experiment_ids.append(exp_id)
                    channel_filters.append(channels)
                else:
                    self.logger.warning(f"Could not find experiment ID for experiment name: '{exp}'")
            
            # If no valid experiment IDs found, set to None to avoid empty lists
            if not experiment_ids:
                experiment_ids = None
                channel_filters = None
            else:
                channel_filters = channel_filters  # Already set above
            for exp_name, exp_id in zip(
                experiments_and_channels.keys(), experiment_ids
            ):
                if exp_id is None:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")

        base_conditions = []

        if conditions:
            base_conditions.append(conditions)

        experiment_conditions = []
        if experiment_ids is not None:
            for exp_id, channel_list in zip(experiment_ids, channel_filters):
                if channel_list:
                    condition = f"(experiment_id = {exp_id} AND channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"(experiment_id = {exp_id})"
                experiment_conditions.append(condition)

        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        # Build complete conditions string 
        full_conditions = ' AND '.join(base_conditions) if base_conditions else None
        
        # Use the smart cross-table query construction to get event IDs that satisfy the conditions
        # This handles cross-table filtering (e.g., filtering events by sublevels columns)
        try:
            # Get event IDs using cross-table aware query construction
            id_query, debug_msg, table_name = self.construct_metadata_query(
                columns=["voltage"],  # Use a placeholder column - we just want the IDs
                conditions=full_conditions,
                experiments_and_channels=experiments_and_channels
            )
            
            if debug_msg:
                raise ValueError(f"Failed to construct filtering query: {debug_msg}")
            
            # Execute the cross-table query to get filtered results
            filtered_results = self._load_metadata(id_query)
            if filtered_results is None or len(filtered_results) == 0:
                raise ValueError("No events found matching subset criteria")
            
            # Extract event IDs from the results
            if 'event_id' in filtered_results.columns:
                event_ids = list(filtered_results['event_id'].values.astype(int))
            else:
                # Fallback - use the id column and assume it's event IDs
                event_ids = list(filtered_results['id'].values.astype(int))
            
            # Now get full events data for these specific event IDs
            events_query = f"SELECT e.* FROM events e WHERE e.event_id IN {tuple_builder(event_ids)}"
            
        except Exception as e:
            # Fallback to original simple query if cross-table construction fails
            self.logger.warning(f"Cross-table query construction failed, using simple events query: {e}")
            condition_clause = (
                f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
            )
            events_query = f"SELECT * FROM events {condition_clause}"
        
        valid, debug = self.validate_filter_query(events_query)
        if debug:
            raise ValueError(
                f"Malformed events query:\n\n{self._format_debug_msg(debug)}"
            )
        events = self._load_metadata(events_query)
        if events is None or len(events) == 0:
            raise ValueError("No events found matching subset criteria")

        event_ids = [int(eid) for eid in events["id"].values.astype(int)]
        sublevels_query = f"SELECT sub.* FROM sublevels sub WHERE sub.event_db_id IN {tuple_builder(event_ids)}"
        valid, debug = self.validate_filter_query(sublevels_query)
        if debug:
            raise ValueError(
                f"Malformed sublevels query:\n\n{self._format_debug_msg(debug)}"
            )
        sublevels = self._load_metadata(sublevels_query)
        if sublevels is None:
            raise ValueError("Failed to load sublevels data.")

        unique_exp_ids = [int(exp_id) for exp_id in np.unique(events["experiment_id"])]
        experiment_query = f"SELECT exp.* FROM experiments exp WHERE exp.id IN {tuple_builder(unique_exp_ids)}"
        valid, debug = self.validate_filter_query(experiment_query)
        if debug:
            raise ValueError(
                f"Malformed experiments query:\n\n{self._format_debug_msg(debug)}"
            )
        experiments = self.query_database_directly(experiment_query)
        if experiments is None:
            raise ValueError("Failed to load experiments table.")

        channel_ids = [int(cid) for cid in events["channel_db_id"].values.astype(int)]
        channel_query = (
            f"SELECT ch.* FROM channels ch WHERE ch.id IN {tuple_builder(channel_ids)}"
        )
        valid, debug = self.validate_filter_query(channel_query)
        if debug:
            raise ValueError(
                f"Malformed channels query:\n\n{self._format_debug_msg(debug)}"
            )
        channels = self.query_database_directly(channel_query)
        if channels is None:
            raise ValueError("Failed to load channels table.")

        columns_query = "SELECT cols.* FROM columns cols"
        valid, debug = self.validate_filter_query(columns_query)
        if debug:
            raise ValueError(
                f"Malformed columns query:\n\n{self._format_debug_msg(debug)}"
            )
        columns = self.query_database_directly(columns_query)
        if columns is None:
            raise ValueError("Failed to load columns table.")

        data_query = f"SELECT d.experiment_id, d.channel_id, d.channel_db_id, d.event_id, d.event_db_id FROM data d WHERE d.event_db_id IN {tuple_builder(event_ids)}"
        valid, debug = self.validate_filter_query(data_query)
        if debug:
            raise ValueError(
                f"Malformed data query:\n\n{self._format_debug_msg(debug)}"
            )
        data = self.query_database_directly(data_query)
        if data is None:
            raise ValueError("Failed to load data table.")

        append = f"{subset_name}_" if subset_name else ""

        columns.to_csv(Path(output_folder, f"{append}columns.csv"), index=False)
        channels.to_csv(Path(output_folder, f"{append}channels.csv"), index=False)
        experiments.to_csv(Path(output_folder, f"{append}experiments.csv"), index=False)
        events.to_csv(Path(output_folder, f"{append}events.csv"), index=False)
        sublevels.to_csv(Path(output_folder, f"{append}sublevels.csv"), index=False)

        filenames = [f"{append}event_{event_id}.csv" for event_id in event_ids]
        data["filename"] = filenames
        data.to_csv(Path(output_folder, f"{append}data.csv"), index=False)

        event_data_generator = self.load_event_data(
            f"event_db_id IN {tuple_builder(event_ids)}", experiments_and_channels
        )

        num_events = len(events)
        for i, (filename, event_data) in enumerate(
            zip(filenames, event_data_generator)
        ):
            df = pd.DataFrame(
                {
                    "raw_data": event_data["raw_data"],
                    "filtered_data": event_data["filtered_data"],
                    "fit_data": event_data["fit_data"],
                }
            )
            df.to_csv(Path(output_folder, filename), index=False)
            yield i / num_events
        yield 1.0

    @log(logger=logger)
    def report_channel_status(self, channel: Optional[int] = None, init=False) -> str:
        """
        Return a string detailing any pertinent information about the status of analysis conducted on a given channel

        :param channel: channel ID
        :type channel: Optional[int]
        :param init: is the function being called as part of plugin initialization? Default False
        :type init: bool

        :return: the status of the channel as a string
        :rtype: str
        """
        experiments = self.get_experiment_names()
        if not experiments:
            return "No experiments found."

        channels = [
            self.get_channels_by_experiment(experiment) for experiment in experiments
        ]
        num_events = {
            exp: {
                ch: self.get_event_counts_by_experiment_and_channel(exp, ch)
                for ch in chs
            }
            for exp, chs in zip(experiments, channels)
            if chs is not None
        }

        report = (
            f" {len(experiments)} experiment\n"
            if len(experiments) == 1
            else f"{len(experiments)} experiments\n"
        )
        for experiment, val in num_events.items():
            report += f"{experiment}:\n"
            for ch, num in val.items():
                report += f"Channel: {ch}: {num} events\n"
        return report.rstrip("\n")

    @log(logger=logger)
    def construct_metadata_query(
        self,
        columns: List[str],
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Tuple[str, str, str]:
        """
        Construct metadata queries with automatic cross-table filtering support.
        
        The query construction automatically analyzes both the selected columns AND the filter conditions
        to determine which tables need to be included. This enables powerful cross-table filtering,
        such as plotting peak_height (events) filtered by unfolded_level (sublevels).
        
        The method will create the minimal required query structure:

        **Single table queries** (when all data comes from one table):

        .. code-block:: sql

            SELECT e.id, e.experiment_id, e.channel_id, e.event_id, [[events_columns]]
            FROM events e
            WHERE [[conditions]]

        **Two-table JOIN queries** (when data spans two tables):

        .. code-block:: sql

            SELECT s.id, e.experiment_id, e.channel_id, e.event_id, [[events_columns]], [[sublevels_columns]]
            FROM events e
            JOIN sublevels s ON e.id = s.event_db_id
            WHERE [[conditions]]

        **Three-table JOIN queries** (when experiments metadata is also needed):

        .. code-block:: sql

            SELECT s.id, e.experiment_id, e.channel_id, e.event_id, [[events_columns]], [[sublevels_columns]], [[experiments_columns]]
            FROM events e
            JOIN sublevels s ON e.id = s.event_db_id
            JOIN experiments exp ON exp.id = e.experiment_id
            WHERE [[conditions]]

        **Cross-table filtering examples:**
        
        - Plot voltage (events) filtered by filtered status (sublevels)
        - Histogram of peak_height (events) where unfolded_level > 0.5 (sublevels)  
        - Any events/sublevels data from specific experiment_name (experiments)

        The system automatically detects table requirements from conditions like:
        - Explicit aliases: ``s.filtered != 0``, ``e.voltage > -100``
        - Implicit columns: ``filtered != 0`` (looks up that filtered is in sublevels table)
        - Mixed references: ``voltage > -100 AND filtered = 1`` (events + sublevels)

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a valid SQL query and an empty string, or an empty string and a debug message, and the table name of the affected id column
        :rtype: Tuple[str, str, str]
        """

        def tuple_builder(id_list):
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Validate input
        if not columns:
            raise ValueError("list of columns cannot be empty")

        # Identify table sources for each column
        tables = [self.get_table_by_column(col) for col in columns]
        if any(table is None for table in tables):
            invalid_columns = [
                col for col, table in zip(columns, tables) if table is None
            ]
            raise ValueError(
                f"The following columns could not be mapped to tables: {', '.join(invalid_columns)}"
            )

        events_columns = [col for col, tbl in zip(columns, tables) if tbl == "events"]
        sublevels_columns = [
            col for col, tbl in zip(columns, tables) if tbl == "sublevels"
        ]
        experiments_columns = [
            col for col, tbl in zip(columns, tables) if tbl == "experiments"
        ]
        
        # Analyze conditions to identify which tables are referenced
        conditions_require_events = False
        conditions_require_sublevels = False
        conditions_require_experiments = False
        
        if conditions:
            import re
            # Find all column references in conditions (e.g., "e.voltage", "s.filtered", "voltage")
            column_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*\.)?([a-zA-Z_][a-zA-Z0-9_]*)\b', conditions)
            
            for prefix, col_name in column_refs:
                # Skip SQL keywords and operators
                if col_name.lower() in ('and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'between', 'like'):
                    continue
                
                # Check explicit table prefixes first
                if prefix == 'e.':
                    conditions_require_events = True
                elif prefix == 's.':
                    conditions_require_sublevels = True
                elif prefix == 'exp.':
                    conditions_require_experiments = True
                else:
                    # No explicit prefix, so look up which table this column belongs to
                    col_table = self.get_table_by_column(col_name)
                    if col_table == "events":
                        conditions_require_events = True
                    elif col_table == "sublevels":
                        conditions_require_sublevels = True
                    elif col_table == "experiments":
                        conditions_require_experiments = True

        # Normalize experiment names to IDs if necessary
        experiments = None
        if experiments_and_channels is not None:
            experiments = []
            channels = []
            for exp_name, channel_list in experiments_and_channels.items():
                exp_id = self.get_experiment_id_by_name(exp_name)
                if exp_id is not None:
                    experiments.append(exp_id)
                    channels.append(channel_list)
                else:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")
                    
            # If no valid experiments found, set to None
            if not experiments:
                experiments = None
                channels = None

        ####
        base_conditions = []

        # General conditions (AND logic)
        if conditions:
            base_conditions.append(conditions)

        # Experiment/channel conditions (OR logic between each)
        experiment_conditions = []
        if experiments is not None:
            # Determine which table alias to use for experiment_id/channel_id
            # Prefer 'e.' when events are involved, otherwise use 's.'
            needs_events = bool(events_columns) or conditions_require_events
            needs_sublevels = bool(sublevels_columns) or conditions_require_sublevels
            
            if needs_events:
                table_prefix = "e."
            elif needs_sublevels:
                table_prefix = "s."
            else:
                table_prefix = ""
                
            for exp, channel_list in zip(experiments, channels):
                if channel_list:
                    condition = f"{table_prefix}experiment_id = {exp} AND {table_prefix}channel_id IN {tuple_builder(channel_list)}"
                else:
                    condition = f"{table_prefix}experiment_id = {exp}"
                experiment_conditions.append(condition)

        # Combine all into final WHERE clause
        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        condition_clause = (
            f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
        )

        # Remove redundant columns
        redundant_cols = {
            "id",
            "experiment_id",
            "channel_id",
            "event_id",
            "s.id",
            "e.experiment_id",
            "e.channel_id",
            "e.event_id",
        }
        columns = [col for col in columns if col not in redundant_cols]

        # Determine query type based on both selected columns AND conditions requirements
        # If conditions require additional tables, we need to include them in JOINs
        needs_events = bool(events_columns) or conditions_require_events
        needs_sublevels = bool(sublevels_columns) or conditions_require_sublevels
        needs_experiments = bool(experiments_columns) or conditions_require_experiments
        
        # Determine query type and build it
        if needs_events and not needs_sublevels and not needs_experiments:
            # Events-only query (but may include JOINs if conditions require other tables)
            events_str = ", ".join([f"e.{col}" for col in events_columns]) if events_columns else ""
            select_parts = ["e.id, e.experiment_id, e.channel_id, e.event_id"]
            if events_str:
                select_parts.append(events_str)
            
            query = f"""SELECT {', '.join(select_parts)}
                        FROM events e
                        {condition_clause}"""
            table_name = "events"

        elif needs_sublevels and not needs_events and not needs_experiments:
            # Sublevels-only query 
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns]) if sublevels_columns else ""
            select_parts = ["s.id, s.experiment_id, s.channel_id, s.event_id"]
            if sublevels_str:
                select_parts.append(sublevels_str)
                
            query = f"""SELECT {', '.join(select_parts)}
                        FROM sublevels s
                        {condition_clause}"""
            table_name = "sublevels"

        elif needs_events and needs_sublevels and not needs_experiments:
            # Events + Sublevels JOIN
            events_str = ", ".join([f"e.{col}" for col in events_columns]) if events_columns else ""
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns]) if sublevels_columns else ""
            
            select_parts = ["s.id, e.experiment_id, e.channel_id, e.event_id"]
            if events_str:
                select_parts.append(events_str)
            if sublevels_str:
                select_parts.append(sublevels_str)
            
            query = f"""SELECT {', '.join(select_parts)}
                        FROM events e
                        JOIN sublevels s
                        ON e.id = s.event_db_id
                        {condition_clause}"""
            table_name = "sublevels"
            
        elif needs_events and not needs_sublevels and needs_experiments:
            # Events + Experiments JOIN
            events_str = ", ".join([f"e.{col}" for col in events_columns]) if events_columns else ""
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns]) if experiments_columns else ""
            
            select_parts = ["e.id, e.experiment_id, e.channel_id, e.event_id"]
            if events_str:
                select_parts.append(events_str)
            if experiments_str:
                select_parts.append(experiments_str)
                
            query = f"""SELECT {', '.join(select_parts)}
                        FROM events e
                        JOIN experiments exp
                        ON exp.id = e.experiment_id
                        {condition_clause}"""
            table_name = "events"

        elif not needs_events and needs_sublevels and needs_experiments:
            # Sublevels + Experiments JOIN
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns]) if sublevels_columns else ""
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns]) if experiments_columns else ""
            
            select_parts = ["s.id, s.experiment_id, s.channel_id, s.event_id"]
            if sublevels_str:
                select_parts.append(sublevels_str)
            if experiments_str:
                select_parts.append(experiments_str)
                
            query = f"""SELECT {', '.join(select_parts)}
                        FROM sublevels s
                        JOIN experiments exp
                        ON exp.id = s.experiment_id
                        {condition_clause}"""
            table_name = "sublevels"

        elif needs_events and needs_sublevels and needs_experiments:
            # Three-way JOIN: Events + Sublevels + Experiments
            events_str = ", ".join([f"e.{col}" for col in events_columns]) if events_columns else ""
            sublevels_str = ", ".join([f"s.{col}" for col in sublevels_columns]) if sublevels_columns else ""
            experiments_str = ", ".join([f"exp.{col}" for col in experiments_columns]) if experiments_columns else ""
            
            select_parts = ["s.id, e.experiment_id, e.channel_id, e.event_id"]
            if events_str:
                select_parts.append(events_str)
            if sublevels_str:
                select_parts.append(sublevels_str)
            if experiments_str:
                select_parts.append(experiments_str)
                
            query = f"""SELECT {', '.join(select_parts)}
                        FROM events e
                        JOIN sublevels s
                        ON e.id = s.event_db_id
                        JOIN experiments exp
                        ON exp.id = e.experiment_id
                        {condition_clause}"""
            table_name = "sublevels"
        else:
            raise ValueError(
                "No valid table columns specified or conditions found: You must select at least one column or have conditions that reference events, sublevels, or experiments tables"
            )

        # Validate query
        valid, debug = self.validate_filter_query(query)
        if valid:
            return query, "", table_name
        else:
            return "", self._format_debug_msg(debug), table_name

    @log(logger=logger)
    def construct_event_data_query(
        self,
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Tuple[str, str]:
        """
        Construct a query that will get all event data matching a set of conditions

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: a valid SQL query and an empty string, or an empty string and a debug message
        :rtype: Tuple[str, str]
        """

        def tuple_builder(id_list):
            if not id_list:
                raise ValueError("Unable to build tuple from empty list")
            filtered_ids = [str(i) for i in id_list if i is not None]
            if not filtered_ids:
                raise ValueError(
                    "Unable to build tuple from list with only None values"
                )
            return f"({','.join(filtered_ids)})"

        # Normalize experiment names to IDs if necessary
        experiments = None
        if experiments_and_channels is not None:
            experiments = []
            channels = []
            for exp_name, channel_list in experiments_and_channels.items():
                exp_id = self.get_experiment_id_by_name(exp_name)
                if exp_id is not None:
                    experiments.append(exp_id)
                    channels.append(channel_list)
                else:
                    raise KeyError(f"Could not find experiment ID(s) for: {exp_name}")
                    
            # If no valid experiments found, set to None
            if not experiments:
                experiments = None
                channels = None

        ####
        base_conditions = []

        # General conditions (AND logic) with cross-table support
        if conditions:
            # Check if conditions need cross-table filtering
            needs_events = self._check_events_columns(conditions)
            needs_sublevels = self._check_sublevels_columns(conditions) 
            needs_experiments = self._check_experiments_columns(conditions)
            
            # Event data queries always work with events and sublevels tables
            # If experiments table is needed, ensure it's available in the existing JOIN
            condition_with_alias = self._add_table_aliases(conditions)
            base_conditions.append(condition_with_alias)

        # Experiment/channel conditions (OR logic between each)
        experiment_conditions = []
        if experiments is not None:
            for exp, channel_list in zip(experiments, channels):
                if channel_list:
                    condition = f"(e.experiment_id = {exp} AND e.channel_id IN {tuple_builder(channel_list)})"
                else:
                    condition = f"(e.experiment_id = {exp})"
                experiment_conditions.append(condition)

        # Combine all into final WHERE clause
        if experiment_conditions:
            base_conditions.append(f"({' OR '.join(experiment_conditions)})")

        subquery_clause = (
            f"WHERE {' AND '.join(base_conditions)}" if base_conditions else ""
        )

        # Main query prefix
        start_clause = """
            SELECT
                d.id,
                d.event_id,
                d.channel_id,
                d.experiment_id,
                d.data_format,
                c.samplerate,
                pb.sublevel_duration AS padding_before,
                pa.sublevel_duration AS padding_after,
                d.raw_data,
                d.filtered_data,
                d.fit_data
            FROM data d
            JOIN channels c ON c.id = d.channel_db_id
            LEFT JOIN (
                SELECT event_db_id, sublevel_duration
                FROM sublevels
                WHERE level_id = 0
            ) pb ON pb.event_db_id = d.event_db_id
            LEFT JOIN (
                SELECT event_db_id, sublevel_duration
                FROM sublevels
                WHERE levels_left = 0
            ) pa ON pa.event_db_id = d.event_db_id
            WHERE d.event_db_id IN (
                SELECT DISTINCT event_db_id
                FROM events e
                JOIN sublevels s
                ON e.id = s.event_db_id
                JOIN experiments exp
                ON exp.id = e.experiment_id
                {subquery_clause}
            )
        """.format(
            subquery_clause=subquery_clause
        )

        # Validate and return
        valid, debug = self.validate_filter_query(start_clause)
        if valid:
            return start_clause.strip(), ""
        else:
            return "", self._format_debug_msg(debug)

    @log(logger=logger)
    def load_metadata(
        self,
        columns: List[str],
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> pd.DataFrame:
        """
        Fetch specified columns from the metadata database given a query

        Will always include experiment_id, channel_id, and event_id in the dataframe in addition to requested columns.

        :param columns: List of column names to retrieve.
        :type columns: List[str]
        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]
        :return: pandas dataframe containing retrieved data
        :rtype: pd.DataFrame
        """
        query, debug, table = self.construct_metadata_query(
            columns, conditions, experiments_and_channels
        )
        if query:
            df = self._load_metadata(query)
            if df is not None:
                df = df.loc[:, ~df.columns.duplicated()]
            return df
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )
            return None

    @log(logger=logger)
    def load_event_data(
        self,
        conditions: Optional[str] = None,
        experiments_and_channels: Optional[Dict[str, Optional[List[int]]]] = None,
    ) -> Generator[
        Dict[
            str,
            Union[
                int,
                int,
                int,
                int,
                float,
                int,
                int,
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
            ],
        ],
        bool,
        None,
    ]:
        """
        Load data and return a generator that gives a one-row dataframe corresponding one row returned by query
        Make sure you exhaust or explicitly abort the generator, or else connections will remain open
        You can assume that the query was generated by self.construct_event_data_query() and will have 10 colums:
        event_id, channel_id, experiment_id, data_format, baseline, stdev, padding_before, padding_after, samplerate, data
        where data is a bytes object to be interpreted using data_format

        :param conditions: Optional filter condition for query.
        :type conditions: Optional[str]
        :param expeirments_and_channels: a dict of experiment names as keys as lists of channels to include as values. Can be None, and individual channel lists can be None to include all channels for that experiment
        :type experiments_and_channels: Optional[Dict[str, Optional[List[int]]]]

        :return: a generator that returns primary database id, experiment_id, channel_id, event_id, samplerate, padding_before, padding_after, samplerate, and a numpy array with event data
        :rtype: Generator[Tuple[int, int, int, int, float, int, int, npt.NDArray[np.float64]], bool,  None]
        """
        query, debug = self.construct_event_data_query(
            conditions, experiments_and_channels
        )
        if query:
            event_generator = self._load_event_data(query)
            abort = False
            for event in event_generator:
                (
                    db_id,
                    experiment_id,
                    channel_id,
                    event_id,
                    samplerate,
                    padding_before,
                    padding_after,
                    raw_data,
                    filtered_data,
                    fit_data,
                ) = event
                abort = yield {
                    "id": db_id,
                    "event_id": event_id,
                    "channel_id": channel_id,
                    "experiment_id": experiment_id,
                    "samplerate": samplerate,
                    "padding_before": padding_before,
                    "padding_after": padding_after,
                    "raw_data": raw_data,
                    "filtered_data": filtered_data,
                    "fit_data": fit_data,
                }
                abort = bool(abort)
                if abort is True:
                    break
            if abort is True:
                self.logger.info("Generator aborted")
                return
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )

    @log(logger=logger)
    def query_database_directly(self, query: str) -> Optional[pd.DataFrame]:
        """
        Run a given query on the DB after basic validation.

        :param query: query to  run on the database
        :type query: str

        :return: List of numpy arrays containing retrieved data.
        :rtype: Optional[pd.DataFrame]
        """
        valid, debug = self.validate_filter_query(query)
        if valid and not debug:
            return self._load_metadata(query)
        else:
            self.logger.warning(
                f"Unable to output subset due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )
            return None

    @log(logger=logger)
    def query_database_directly_and_get_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, bool, None]:
        """
        Run a given querry on the DB after basic validation and return a generator that feeds out one row at a time

        :param query: query to  run on the database
        :type query: str

        :return: A generator that feeds out onne row at a time in the form of a single-line dataframe
        :rtype: Generator[pd.DataFrame, bool, None]
        """
        valid, debug = self.validate_filter_query(query)
        if valid and not debug:
            metadata_generator = self._load_metadata_generator(query)
            if metadata_generator is not None:
                abort = False
                for event in metadata_generator:
                    event = event.loc[:, ~event.columns.duplicated()]
                    abort = yield event
                    abort = bool(abort)
                    if abort is True:
                        break
                if abort is True:
                    self.logger.info("Generator aborted")
                    return
            else:
                self.logger.warning(
                    "Unable to get events from subset generator that returned None"
                )
                return
        else:
            self.logger.warning(
                f"Unable to get subset generator due to malformed query string\n\n{self._format_debug_msg(debug)}"
            )

    # private API, MUST be implemented by subclasses
    @abstractmethod
    def _init(self) -> None:
        """
        **Purpose:** Perform generic class construction operations.

        This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        pass

    @abstractmethod
    def _load_metadata(self, query: str) -> Optional[pd.DataFrame]:
        """
        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str

        :return: A dataframe containing the requested event data as columns or None on failure
        :rtype: Optional[pd.DataFrame]

        **Purpose:** Load and return the data specified by a valid SQL query, or None on failure

        The data should be formatted as a pandas Dataframe object
        """
        pass

    @abstractmethod
    def _load_metadata_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, None, None]:
        """
        :param query: query to  run on the database
        :type query: str

        :return: A generator that feeds out onne row at a time in the form of a single-line dataframe
        :rtype: Generator[pd.DataFrame, None, None]

        **Purpose:** Load and yield the data specified by a valid SQL query one row at a time. Useful in cases where :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata` returns too much data for memory.

        Data should be formatted as a pandas dataframe in line with :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader._load_metadata`. Make sure you exhaust the generator when done with it, or else database connections will remain open.
        """
        pass

    @abstractmethod
    def _load_event_data(self, query: str) -> Generator[
        Dict[
            str,
            Union[
                int,
                int,
                int,
                int,
                float,
                int,
                int,
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
            ],
        ],
        bool,
        None,
    ]:
        """
        Load data and return a generator that gives a one-row dataframe corresponding one row returned by query
        Make sure you exhaust the generator, or else connections will remain open
        You can assume that the query was generated by self.construct_event_data_query() and will have 5 colums:
        event_id, channel_id, experiment_id, data_format, data, baseline, stdev, padding_before, padding_after, data
        where data is a bytes object to be interpreted using data_format

        :param query: a valid SQL query, checked in the calling function for validity
        :type query: str

        :return: a generator that returns a dict with id, event_id, channel_id, experiment_id, samplerate, padding_before, padding_after, and numpy array with event data for raw, filtered, and fitted data
        :rtype: Generator[Dict[str, Union[int, int, int, int, float, int, int, npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]], bool,  None]
        """
        pass

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def _finalize_initialization(self):
        """
        **Purpose:** Apply application-specific settings to the plugin, if needed.

        If additional initialization operations are required beyond the defaults provided in :ref:`BaseDataPlugin` or :ref:`MetaDatabaseLoader` that must occur after settings have been applied to the reader instance, you can override this function to add those operations.
        """
        pass

    @log(logger=logger)
    def _format_debug_msg(self, debug: str) -> str:
        """
        Strip out newlines and unnecessary whitespace from SQL queries for printing

        :param debug: a string containing an error message and an SQL string for correction
        :type debug: str

        :return: the input string with whitepsace removed and newlines in it to format for export
        :rtype: str
        """
        debug = re.sub(r"[ \t]+", " ", debug)
        return re.sub(r"\n[ \t]+", "\n", debug)

    def _check_events_columns(self, conditions: str) -> bool:
        """Check if conditions reference events table columns"""
        import re
        if not conditions:
            return False
        
        # Check for explicit events table prefix
        if re.search(r'\be\.', conditions):
            return True
            
        # Check for column names that belong to events table
        column_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', conditions)
        for col_name in column_refs:
            # Skip SQL keywords
            if col_name.lower() in ('and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'between', 'like'):
                continue
            col_table = self.get_table_by_column(col_name)
            if col_table == "events":
                return True
        return False

    def _check_sublevels_columns(self, conditions: str) -> bool:
        """Check if conditions reference sublevels table columns"""
        import re
        if not conditions:
            return False
            
        # Check for explicit sublevels table prefix
        if re.search(r'\bs\.', conditions):
            return True
            
        # Check for column names that belong to sublevels table
        column_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', conditions)
        for col_name in column_refs:
            # Skip SQL keywords
            if col_name.lower() in ('and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'between', 'like'):
                continue
            col_table = self.get_table_by_column(col_name)
            if col_table == "sublevels":
                return True
        return False

    def _check_experiments_columns(self, conditions: str) -> bool:
        """Check if conditions reference experiments table columns"""
        import re
        if not conditions:
            return False
            
        # Check for explicit experiments table prefix
        if re.search(r'\bexp\.', conditions):
            return True
            
        # Check for column names that belong to experiments table
        column_refs = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', conditions)
        for col_name in column_refs:
            # Skip SQL keywords
            if col_name.lower() in ('and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'between', 'like'):
                continue
            col_table = self.get_table_by_column(col_name)
            if col_table == "experiments":
                return True
        return False

    def _add_table_aliases(self, conditions: str) -> str:
        """Add proper table aliases to column references in conditions"""
        import re
        if not conditions:
            return conditions
            
        # Find all column references and add appropriate table prefixes
        def replace_column(match):
            col_name = match.group(1)
            # Skip if already has a table prefix
            if '.' in col_name:
                return col_name
            # Skip SQL keywords
            if col_name.lower() in ('and', 'or', 'not', 'in', 'is', 'null', 'true', 'false', 'between', 'like'):
                return col_name
                
            # Determine which table this column belongs to
            col_table = self.get_table_by_column(col_name)
            if col_table == "events":
                return f"e.{col_name}"
            elif col_table == "sublevels":
                return f"s.{col_name}"
            elif col_table == "experiments":
                return f"exp.{col_name}"
            else:
                return col_name  # Unknown column, leave as-is
                
        # Replace column names with table-prefixed versions
        # Pattern matches word boundaries to avoid partial matches
        return re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', replace_column, conditions)

    @abstractmethod
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    # Utility functions, specific to subclasses as needed
