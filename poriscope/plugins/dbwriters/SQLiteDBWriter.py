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

import logging
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaDatabaseWriter import MetaDatabaseWriter


@inherit_docstrings
class SQLiteDBWriter(MetaDatabaseWriter):
    """
    Abstract base class for database writer that will store metadata and data from fitted events for postprocessing later
    """

    logger = logging.getLogger(__name__)

    # public API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit. If channel is not None, handle only that channel, else close all of them.

        :param channel: channel ID
        :type channel: int
        """
        # conn = None
        cursor = None
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("SAVEPOINT reset_channel")
            experiment_name = self.settings["Experiment Name"]["Value"]
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            experiment_id = cursor.fetchone()
            if not experiment_id:
                raise RuntimeError(
                    f"Experiment '{experiment_name}' not found, unable to reset channel."
                )
            experiment_id = experiment_id[0]

            cursor.execute(
                "DELETE FROM channels WHERE experiment_id = ? AND channel_id = ?",
                (experiment_id, channel),
            )

            self.logger.info(
                f"Deleted (experiment_id={experiment_id}, channel_id={channel}) from channels."
            )

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.warning(
                f"Failed to delete (experiment_id={experiment_id}, channel_id={channel}): {e}, channel not reset"
            )
        else:
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def close_resources(self, channel=None) -> None:
        """
        Perform any actions necessary to gracefully close resources before app exit.
        If `channel` is not None, handle only that channel; otherwise, close all channels.

        :param channel: channel ID
        :type channel: int
        """
        if self.conn:
            self.logger.debug("Closing database connection.")
            self.conn.commit()  # Ensure all writes are committed
            self.conn.close()  # Close the connection to release the lock
        else:
            self.logger.debug("Database connection not open to close.")

    @log(logger=logger)
    @override
    def get_empty_settings(self, globally_available_plugins=None, standalone=False):
        """
        Get a dict populated with keys needed to initialize the filter if they are not set yet.
        This dict must have the following structure, but Min, Max, and Options can be skipped or explicitly set to None if they are not used.
        Value and Type are required. All values provided must be consistent with Type.
        EventFinder objects MUST include a MetaReader object in settings

        .. code-block:: python

          settings = {'Parameter 1': {'Type': <int, float, str, bool>,
                                           'Value': <value> or None,
                                           'Options': [<option_1>, <option_2>, ... ] or None,
                                           'Min': <min_value> or None,
                                           'Max': <max_value> or None
                                          },
                          ...
                          }

        :param globally_available_plugins: a dict containing all data plugins that exist to date, keyed by metaclass. Must include "MetaReader" as a key, with explicitly set Type MetaReader.
        :type globally_available_plugins: Mapping[str, List[str]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Mapping[str, Mapping[str, Union[int, float, str, list[Union[int,float,str,None], None]]]]
        """
        settings = super().get_empty_settings(globally_available_plugins, standalone)
        settings["Output File"]["Options"] = [
            "SQLite3 Files (*.sqlite3)",
            "Database Files (*.db)",
            "SQLite Files (*.sqlite)",
        ]
        settings["Experiment Name"] = {"Type": str}
        settings["Voltage"] = {"Type": float, "Units": "mV"}
        settings["Membrane Thickness"] = {"Type": float, "Units": "nm", "Min": 0}
        settings["Conductivity"] = {"Type": float, "Units": "S/m", "Min": 0}
        return settings

    # Public API continued, should implemented by subclasses, but has default behavior if it is not needed

    # private API, MUST be implemented by subclasses
    @log(logger=logger)
    @override
    def _init(self):
        """
        **Purpose:** Perform generic class construction operations.

        All data plugins have this function and must provide an implementation. This is called immediately at the start of class creation and is used to do whatever is required to set up your reader. Note that no app settings are available when this is called, so this function should be used only for generic class construction operations. Most readers simply ``pass`` this function.
        """
        self.conn = None
        self.cursor = None

    @log(logger=logger)
    @override
    def _write_event(
        self,
        channel,
        event_metadata,
        sublevel_metadata,
        event_data,
        raw_data,
        fit_data,
        abort=False,
        last_call=False,
    ):
        """
        Write a single event worth of data and metadata to the database. Do NOT commit.

        :param channel: identifier for the channel to write events from
        :type channel: int
        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: numpy.ndarray
        :param event_metadata: a dict of metadata associated to the event
        :type event_metadata: Mapping[str, Union[int, float, str, bool]]
        :param event_metadata: a dict of lists of metadata associated to sublevels within the event. You can assume they all have the same length.
        :type event_metadata: Mapping[str, List[Union[int, float, str, bool]]]
        :param event_data: the raw data for the event (not filtered)
        :type event_data: npt.NDArray[np.float64]
        :param raw_data: A numpy array of raw event data to be stored as binary in the database.
        :type raw_data: npt.NDArray[np.float64]
        :param fit_data: A numpy array of fitted event data to be stored as binary in the database.
        :type fit_data: npt.NDArray[np.float64]
        :param abort: True if an abort request was issued in the caller, perform cleanup as needed
        :type abort: Optional[bool]
        :param last_call: True if this is the last time the function will be called, commit to file and clean up as needed
        :type last_call: Optional[bool]

        :return: True on successful write, False on failure or ignore
        :rtype: bool
        """
        if abort is True:
            if self.conn:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.rollback()
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.conn:
                self.conn.close()
                self.conn = None
            return False
        try:
            success = False
            if self.conn is None:
                self.conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
                self.conn.execute("PRAGMA foreign_keys = ON;")
                self.cursor = self.conn.cursor()
                self.conn.execute("SAVEPOINT write_event")
            if self.conn is None or self.cursor is None:
                raise ValueError("Unable to open database connection in _write_event")
            # Get the experiment ID based on the experiment name
            experiment_name = self.settings["Experiment Name"]["Value"]
            self.cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )

            experiment_id = self.cursor.fetchone()
            if not experiment_id:
                raise RuntimeError(f"Experiment '{experiment_name}' not found.")
            experiment_id = experiment_id[0]

            self.cursor.execute(
                "SELECT id FROM channels WHERE experiment_id = ? AND channel_id = ?;",
                (experiment_id, channel),
            )
            channel_db_id = self.cursor.fetchone()
            if not channel_db_id:
                raise RuntimeError(
                    f"Channel {channel} for experiment {experiment_name} not found."
                )
            channel_db_id = channel_db_id[0]  # Extract the actual ID

            success = self._insert_event(
                self.cursor, event_metadata, experiment_id, channel_db_id
            )
            event_db_id = self.cursor.lastrowid

            if success:
                success = self._insert_sublevels(
                    self.cursor,
                    sublevel_metadata,
                    experiment_id,
                    channel_db_id,
                    event_db_id,
                )
            if success:
                success = self._insert_event_data(
                    self.cursor,
                    event_metadata,
                    event_data,
                    raw_data,
                    fit_data,
                    experiment_id,
                    channel_db_id,
                    event_db_id,
                )

        except sqlite3.Error as e:
            if self.conn:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.rollback()  # Rollback all changes if any operation fails
            self.logger.error(f"Failed to write event: {e}")
        except Exception as e:  # Fallback for truly unexpected errors
            if self.conn:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.rollback()
            self.logger.critical(f"Unexpected error writing event: {e}", exc_info=True)
        else:
            if self.conn and last_call is True:
                self.conn.commit()
        finally:
            if self.cursor and last_call is True:
                self.cursor.close()
                self.cursor = None
            if self.conn and last_call is True:
                self.conn.close()
                self.conn = None
            return success

    @log(logger=logger)
    @override
    def _write_experiment_metadata(self, channel=None) -> None:
        """
        Write any information you need to save about the experiment itself

        :param channel: int indicating which output to flush
        :type channel: int
        """
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            experiment_name = self.settings["Experiment Name"]["Value"]
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            existing_experiment = cursor.fetchone()

            if not existing_experiment:
                voltage = self.settings["Voltage"]["Value"]
                thickness = self.settings["Membrane Thickness"]["Value"]
                conductivity = self.settings["Conductivity"]["Value"]
                cursor.execute(
                    "INSERT INTO experiments (name, voltage, thickness, conductivity) VALUES (?, ?, ?, ?);",
                    (experiment_name, voltage, thickness, conductivity),
                )
            else:
                self.logger.info(f"Experiment already exists: {experiment_name}")
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.warning(
                f"Failed to delete (experiment_id={experiment_name}, channel_id={channel}): {e}, channel not reset"
            )
            raise
        else:
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _write_channel_metadata(self, channel: int) -> None:
        """
        Write any information you need to save about the channel

        :param channel: int indicating which output to flush
        :type channel: int
        """
        conn = None
        cursor = None
        experiment_name = self.settings["Experiment Name"]["Value"]
        samplerate = self.eventfitter.get_samplerate(channel)
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT id FROM experiments WHERE name = ?;", (experiment_name,)
            )
            experiment_id = cursor.fetchone()

            if not experiment_id:
                raise RuntimeError(
                    f"Unable to find an appropriate experiment names {experiment_name} while preparing to write to channel {channel}"
                )
            experiment_id = experiment_id[0]

            # Directly attempt to insert the channel
            cursor.execute(
                """INSERT OR IGNORE INTO channels (experiment_id, channel_id, samplerate) VALUES (?, ?, ?);""",
                (
                    experiment_id,
                    channel,
                    samplerate,
                ),
            )
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.warning(
                f"Failed to delete (experiment_id={experiment_id}, channel_id={channel}): {e}, channel not reset"
            )
            raise
        else:
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _validate_settings(self, settings):
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises ValueError: If the settings dict does not contain the correct information.
        """
        pass

    @log(logger=logger)
    @override
    def _initialize_database(self, channel: Optional[int] = None):
        """
        Do whatever you need to do to initialize the database file for a given channel before writing the first event

        :param channel: int indicating which output to flush
        :type channel: Optional[int]
        """

        table_creation_queries = [
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                voltage REAL NOT NULL,
                thickness REAL NOT NULL,
                conductivity REAL NOT NULL
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_experiment_name ON experiments(name);
            """,
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                samplerate REAL NOT NULL,
                UNIQUE (experiment_id, channel_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_channels_experiment_channel ON channels(experiment_id, channel_id);
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                start_time REAL NOT NULL,
                num_sublevels INTEGER NOT NULL,
                UNIQUE (experiment_id, channel_id, event_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sublevels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                event_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                level_id INTEGER NOT NULL,
                levels_left INTEGER NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (event_db_id) REFERENCES events(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_db_id INTEGER NOT NULL,
                event_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                data_format TEXT NOT NULL,
                filtered_data BLOB NOT NULL,
                raw_data BLOB NOT NULL,
                fit_data BLOB NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE,
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE,
                FOREIGN KEY (event_db_id) REFERENCES events(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL,
                units TEXT
            );
            """,
            """
            CREATE TRIGGER IF NOT EXISTS delete_childless_experiments
            AFTER DELETE ON channels
            BEGIN
                DELETE FROM experiments
                WHERE id NOT IN (SELECT DISTINCT experiment_id FROM channels);
            END;
            """,
            """
            CREATE TRIGGER IF NOT EXISTS delete_childless_channels
            AFTER DELETE ON events
            BEGIN
                DELETE FROM channels
                WHERE id NOT IN (SELECT DISTINCT channel_db_id FROM events);
            END;
            """,
        ]

        # Connect to the SQLite database (creates the file if it doesn't exist)
        conn = None
        cursor = None
        try:
            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")  # Start a transaction
            # Create tables if they do not exist
            for query in table_creation_queries:
                cursor.execute(query)

            event_metadata = self.eventfitter.get_event_metadata_types()
            sublevel_metadata = self.eventfitter.get_sublevel_metadata_types()
            event_metadata_units = self.eventfitter.get_event_metadata_units()
            sublevel_metadata_units = self.eventfitter.get_sublevel_metadata_units()
            pytype_to_sql_type = {
                int: "INTEGER",
                float: "REAL",
                str: "TEXT",
                bool: "INTEGER",
            }

            # Insert new column definitions into the columns table
            for name, units in event_metadata_units.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "events", units),
                )
            for name, units in sublevel_metadata_units.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "sublevels", units),
                )

            base_settings = self.get_empty_settings()
            experimental_metadata = {
                "voltage": base_settings["Voltage"]["Units"],
                "thickness": base_settings["Membrane Thickness"]["Units"],
                "conductivity": base_settings["Conductivity"]["Units"],
            }

            for name, units in experimental_metadata.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, "experiments", units),
                )

            # Alter events table
            for column_name, column_type in event_metadata.items():
                if column_type not in [int, float, str, bool]:
                    raise ValueError(
                        f"SQLite3 only supports int, float, str, bool datatypes for event metadata, but you sent {column_name} with type {column_type}"
                    )
                if not self._column_exists(cursor, "events", column_name):
                    cursor.execute(
                        f"ALTER TABLE events ADD COLUMN {column_name} {pytype_to_sql_type[column_type]};"
                    )

            # Alter sublevels table
            for column_name, column_type in sublevel_metadata.items():
                if column_type not in [int, float, str, bool]:
                    raise ValueError(
                        f"SQLite3 only supports int, float, str, bool datatypes for sublevel metadata, but you sent {column_name} with type {column_type}"
                    )
                if not self._column_exists(cursor, "sublevels", column_name):
                    cursor.execute(
                        f"ALTER TABLE sublevels ADD COLUMN {column_name} {pytype_to_sql_type[column_type]};"
                    )

        except (sqlite3.Error, RuntimeError, ValueError) as e:
            if conn is not None:
                conn.rollback()  # Rollback all changes if any operation fails
            self.logger.error(f"Failed to initialize database: {e}")
            raise
        except Exception as e:  # Fallback for truly unexpected errors
            if conn is not None:
                conn.rollback()
            self.logger.critical(f"Unexpected error: {e}", exc_info=True)
            raise
        else:
            if conn is not None:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed

    @log(logger=logger)
    def _insert_event(self, cursor, event_metadata, experiment_id, channel_db_id):
        """
        Insert event metadata into the 'events' table. Return True on success, False on failure.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param event_metadata: A dictionary of metadata associated with the event.
        :type event_metadata: Mapping[str, Union[int, float, str, bool]]
        :param experiment_id: The ID of the experiment for which the event is being logged.
        :type experiment_id: int

        :return: True on success, False on failure
        :rtype: bool
        """
        columns = ", ".join(event_metadata.keys()) + ", experiment_id, channel_db_id"
        values = ", ".join("? " for _ in event_metadata) + ", ?, ?"
        cursor.execute(
            f"INSERT OR IGNORE INTO events ({columns}) VALUES ({values});",
            (*event_metadata.values(), experiment_id, channel_db_id),
        )
        if cursor.rowcount == 0:  # Check if the insert was ignored
            return False
        return True

    @log(logger=logger)
    def _insert_sublevels(
        self, cursor, sublevel_metadata, experiment_id, channel_db_id, event_db_id
    ):
        """
        Insert sublevel metadata into the 'sublevels' table.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param sublevel_metadata: A dictionary of sublevel metadata, where each key corresponds to a list of values.
        :type sublevel_metadata: Mapping[str, List[Union[int, float, str, bool]]]
        :param experiment_id: The ID of the experiment for which the sublevels are being logged.
        :type experiment_id: int

        :return: True on success, False on failure
        :rtype: bool
        """

        def convert_value(value):  # helper function
            if isinstance(value, np.int64):  # Convert numpy int64 to native Python int
                return int(value)
            elif isinstance(
                value, np.float64
            ):  # Convert numpy float64 to native Python float
                return float(value)
            return value  # Leave other types as they are

        columns = (
            ", ".join(sublevel_metadata.keys())
            + ", experiment_id, channel_db_id, event_db_id"
        )
        values = ", ".join("?" for _ in sublevel_metadata) + ", ?, ?, ?"
        rows = zip(
            *(map(convert_value, sublevel_metadata[key]) for key in sublevel_metadata)
        )
        cursor.executemany(
            f"INSERT OR IGNORE INTO sublevels ({columns}) VALUES ({values});",
            [(*row, experiment_id, channel_db_id, event_db_id) for row in rows],
        )
        if cursor.rowcount < len(
            sublevel_metadata["event_id"]
        ):  # Check if any inserts were ignored
            return False
        return True

    @log(logger=logger)
    def _insert_event_data(
        self,
        cursor,
        event_metadata,
        event_data,
        raw_data,
        fit_data,
        experiment_id,
        channel_db_id,
        event_db_id,
    ):
        """
        Insert the event data into the 'data' table after converting it to the appropriate binary format.

        :param cursor: The SQLite cursor to execute the query.
        :type cursor: sqlite3.Cursor
        :param event_metadata: A dictionary of metadata associated with the event.
        :type event_metadata: Mapping[str, Union[int, float, str, bool]]
        :param event_data: A numpy array of filtered event data to be stored as binary in the database.
        :type event_data: np.ndarray
        :param raw_data: A numpy array of raw event data to be stored as binary in the database.
        :type raw_data: np.ndarray
        :param fit_data: A numpy array of fitted event data to be stored as binary in the database.
        :type fit_data: np.ndarray
        :param experiment_id: The ID of the experiment to which the data belongs.
        :type experiment_id: int
        :param channel: The channel ID to associate with the event data.
        :type channel: int

        :return: True on success, False on failure
        :rtype: bool
        """
        if not isinstance(event_data, np.ndarray) or event_data.dtype != np.float64:
            raise ValueError("event_data must be a numpy array of dtype np.float64")

        filtered_data_blob = event_data.astype("<f8").tobytes()
        raw_data_blob = raw_data.astype("<f8").tobytes()
        fit_data_blob = fit_data.astype("<f8").tobytes()
        data_format = "<f8"
        cursor.execute(
            """INSERT OR IGNORE INTO data (experiment_id, channel_id, channel_db_id, event_id, event_db_id, data_format, filtered_data, raw_data, fit_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                experiment_id,
                event_metadata["channel_id"],
                channel_db_id,
                event_metadata["event_id"],
                event_db_id,
                data_format,
                filtered_data_blob,
                raw_data_blob,
                fit_data_blob,
            ),
        )
        if cursor.rowcount == 0:  # Check if the insert was ignored
            return False
        return True

    @log(logger=logger)
    def _column_exists(self, cursor, table_name, column_name):
        """
        Check whether a given column exists in the specified database table.

        :param cursor: SQLite database cursor used to execute the query.
        :type cursor: sqlite3.Cursor
        :param table_name: Name of the table to inspect.
        :type table_name: str
        :param column_name: Name of the column to check for existence.
        :type column_name: str
        :return: True if the column exists, False otherwise.
        :rtype: bool
        """
        cursor.execute(f"PRAGMA table_info({table_name});")
        existing_columns = [
            row[1] for row in cursor.fetchall()
        ]  # Column names are in the second position
        return column_name in existing_columns
