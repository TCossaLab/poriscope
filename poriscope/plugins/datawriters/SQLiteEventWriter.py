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
from typing import Any, Dict, List, Optional

import numpy as np
import numpy.typing as npt
from typing_extensions import override

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaWriter import MetaWriter


@inherit_docstrings
class SQLiteEventWriter(MetaWriter):
    """
    Save events into a single file with baseline between them discarded
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        """
        called at the start of base class initialization
        """
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    @override
    def _finalize_initialization(self) -> None:
        """
        Apply the provided paramters and intialize any internal structures needed
        Should Raise if initialization fails.

        This function is called at the end of the class constructor to perform additional initialization specific to the algorithm being implemented.
        kwargs provided to the base class constructor are available as class attributes.
        """
        self.eventfinder = self.settings["MetaEventFinder"]["Value"]
        self.samplerate = self.eventfinder.get_samplerate()
        self.channel_db_id: Dict[int, Any] = {}

    @log(logger=logger)
    @override
    def _initialize_database(self, channel: int) -> None:
        """
        Open a database or file handle for writing events - this function will be called from every channel in the reader

        :param channel: the channel for which to initialize the database
        :type channel: int
        :raises ValueError: if the output file path is not set in settings
        :raises RuntimeError: if database initialization fails at the SQL level
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs during initialization
        """
        table_creation_queries = [
            """
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                voltage REAL NOT NULL,
                thickness REAL NOT NULL,
                conductivity REAL NOT NULL,
                samplerate REAL NOT NULL,
                data_format TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_db_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                absolute_start INTEGER NOT NULL,
                padding_before INTEGER NOT NULL,
                padding_after INTEGER NOT NULL,
                baseline_mean REAL NOT NULL,
                baseline_std REAL NOT NULL,
                raw_data BLOB NOT NULL,
                UNIQUE (channel_id, event_id),
                FOREIGN KEY (channel_db_id) REFERENCES channels(id) ON DELETE CASCADE
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
            CREATE TRIGGER IF NOT EXISTS delete_childless_channels
            AFTER DELETE ON events
            BEGIN
                DELETE FROM channels
                WHERE id NOT IN (SELECT DISTINCT channel_db_id FROM events);
            END;
            """,
        ]

        conn = None
        cursor = None
        try:
            if (
                not self.settings
                or "Output File" not in self.settings
                or self.settings["Output File"].get("Value") is None
            ):
                raise ValueError("Output file path not set in settings.")

            conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")  # Start a transaction
            # Create tables if they do not exist
            for query in table_creation_queries:
                cursor.execute(query)

            base_settings = self.get_empty_settings()
            metadata = {
                "voltage": (base_settings["Voltage"]["Units"], "channels"),
                "thickness": (base_settings["Membrane Thickness"]["Units"], "channels"),
                "conductivity": (base_settings["Conductivity"]["Units"], "channels"),
                "samplerate": ("Hz", "channels"),
                "absolute_start": ("Index", "events"),
                "padding_before": ("Index", "events"),
                "padding_after": ("Index", "events"),
                "baseline_mean": ("pA", "events"),
                "baseline_std": ("pA", "events"),
                "raw_data": ("pA", "events"),
            }
            for name, (units, table) in metadata.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO columns (name, table_name, units) VALUES (?, ?, ?);",
                    (name, table, units),
                )

        except (sqlite3.Error, RuntimeError, ValueError) as e:
            if conn:
                conn.rollback()  # Rollback all changes if any operation fails
            self.logger.error(f"Failed to initialize database: {e}")
            raise
        except Exception as e:  # Fallback for truly unexpected errors
            if conn:
                conn.rollback()
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @override
    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
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
        :type globally_available_plugins: Optional[Dict[str, List[str]]]
        :param standalone: False if this is called as part of a GUI, True otherwise. Default False
        :type standalone: bool
        :return: the dict that must be filled in to initialize the filter
        :rtype: Dict[str, Dict[str, Any]]
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

    @log(logger=logger)
    @override
    def reset_channel(self, channel: Optional[int] = None) -> None:
        """
        Permanently delete the given channel's row (and, via cascading foreign keys,
        its associated event rows) from the database, so a subsequent write starts
        from a clean slate. This is destructive, not a resource-cleanup step.

        :param channel: channel ID. Note that `channel=None` does not reset all
            channels; SQL `channel_id = NULL` never matches, so no rows are deleted.
        :type channel: Optional[int]
        :raises ValueError: if settings have not been initialized or the output
            file path is not set in settings
        """
        conn: Optional[sqlite3.Connection] = None
        cursor: Optional[sqlite3.Cursor] = None

        if self.settings is None:
            raise ValueError("Settings have not been initialized.")

        settings: dict[str, dict[str, Any]] = self.settings
        output_file_setting = settings.get("Output File")

        if (
            not isinstance(output_file_setting, dict)
            or output_file_setting.get("Value") is None
        ):
            raise ValueError("Output file path is not set in settings.")

        try:
            conn = sqlite3.connect(Path(output_file_setting["Value"]))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("SAVEPOINT reset_channel")

            cursor.execute(
                "DELETE FROM channels WHERE channel_id = ?",
                (channel,),
            )

            self.logger.info(f"Deleted channel_id={channel} from channels.")
        except sqlite3.Error as e:
            if conn is not None:
                conn.execute("ROLLBACK TO SAVEPOINT reset_channel")
                conn.rollback()
            self.logger.error(
                f"Failed to delete channel_id={channel}: {e}, channel not reset"
            )
        else:
            if conn is not None:
                conn.execute("RELEASE SAVEPOINT reset_channel")
                conn.commit()
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()

    @log(logger=logger)
    @override
    def close_resources(self, channel: Optional[int] = None) -> None:
        """
        Do whatever needs doing to gracefully shut down on app exit

        :param channel: channel ID
        :type channel: Optional[int]
        """
        if self.cursor:
            try:
                self.cursor.close()
                self.logger.info("SQLiteEventWriter: cursor closed.")
            except Exception as e:
                self.logger.info(f"Failed to close cursor cleanly: {e}")
            self.cursor = None

        if self.conn:
            try:
                self.conn.commit()
                self.conn.close()
                self.logger.info("SQLiteEventWriter: connection closed.")
            except Exception as e:
                self.logger.info(f"Failed to close connection cleanly: {e}")
            self.conn = None

    @log(logger=logger)
    def get_output_file_name(self) -> Path:
        """
        get the name of the output file
        """
        return Path(self.settings["Output File"]["Value"])

    # private API, MUST be implemented by subclasses

    @log(logger=logger)
    @override
    def _write_channel_metadata(self, channel: int) -> None:
        """
        Write any information you need to save about the channel.

        :param channel: int indicating which output to flush
        :type channel: int
        :raises ValueError: if settings are not initialized or required settings are missing
        :raises RuntimeError: if the channel's database ID cannot be determined after insertion
        :raises sqlite3.Error: if a database operation fails
        """
        conn: Optional[sqlite3.Connection] = None
        cursor: Optional[sqlite3.Cursor] = None

        if self.settings is None:
            raise ValueError("Expected settings to be initialized.")

        settings: dict[str, dict[str, Any]] = self.settings

        # Ensure all required settings are present and valid
        required_keys = [
            "Experiment Name",
            "Voltage",
            "Membrane Thickness",
            "Conductivity",
            "Output File",
        ]
        for key in required_keys:
            if (
                key not in settings
                or not isinstance(settings[key], dict)
                or settings[key].get("Value") is None
            ):
                raise ValueError(f"Missing or invalid setting: {key}")

        experiment_name = settings["Experiment Name"]["Value"]
        voltage = settings["Voltage"]["Value"]
        thickness = settings["Membrane Thickness"]["Value"]
        conductivity = settings["Conductivity"]["Value"]
        output_file = settings["Output File"]["Value"]
        samplerate = self.eventfinder.get_samplerate()

        try:
            conn = sqlite3.connect(Path(output_file))
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")

            cursor.execute(
                """INSERT OR IGNORE INTO channels 
                (name, channel_id, voltage, thickness, conductivity, samplerate, data_format) 
                VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (
                    experiment_name,
                    channel,
                    voltage,
                    thickness,
                    conductivity,
                    samplerate,
                    self.output_dtype,
                ),
            )

            if cursor.lastrowid != 0:
                self.channel_db_id[channel] = cursor.lastrowid
                self.logger.info(
                    f"Inserted new channel {channel} for experiment '{experiment_name}' with DB ID: {self.channel_db_id[channel]}"
                )
            else:
                cursor.execute(
                    "SELECT id FROM channels WHERE channel_id = ?;", (channel,)
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    self.channel_db_id[channel] = existing_row[0]
                    self.logger.info(
                        f"Channel {channel} already exists, using existing DB ID: {self.channel_db_id[channel]}"
                    )
                else:
                    raise RuntimeError(
                        f"Failed to get DB ID for channel {channel} after INSERT OR IGNORE."
                    )

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            self.logger.error(
                f"Failed to write channel metadata for '{experiment_name}' on channel {channel}: {e}"
            )
            raise
        else:
            if conn:
                conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @log(logger=logger)
    @override
    def _write_data(
        self,
        data: npt.NDArray[np.number],
        channel: int,
        index: int,
        scale: Optional[float] = None,
        offset: Optional[float] = None,
        start_sample: Optional[int] = 0,
        padding_before: Optional[int] = 0,
        padding_after: Optional[int] = None,
        baseline_mean: Optional[float] = None,
        baseline_std: Optional[float] = None,
        raw_data: bool = False,
        abort: Optional[bool] = False,
        last_call: Optional[bool] = False,
    ) -> bool:
        """
        Append data and metadata to the active file handle.

        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: npt.NDArray[np.number]
        :param channel: Int indicating the channel from which it was acquired.
        :type channel: int
        :param index: event index
        :type index: int
        :param scale: Float indicating scaling between provided data type and encoded form for storage, default None.
        :type scale: Optional[float]
        :param offset: Float indicating offset between provided data type and encoded form for storage, default None.
        :type offset: Optional[float]
        :param start_sample: Integer index of the starting point of the provided array relative to the start of the experimental run, default 0.
        :type start_sample: Optional[int]
        :param padding_before: the length of the padding before the actual event start
        :type padding_before: Optional[int]
        :param padding_after: the length of the padding after the actual event end
        :type padding_after: Optional[int]
        :param baseline_mean: The local baseline, if available
        :type baseline_mean: Optional[float]
        :param baseline_std: the local standard deviation, if available
        :type baseline_std: Optional[float]
        :param raw_data: True means to simply write data as-is to file, False indicates to first rescale it. Default False.
        :type raw_data: bool
        :param abort: If True, roll back and close the active connection without writing, default False.
        :type abort: Optional[bool]
        :param last_call: If True, close the shared connection after this write, default False.
        :type last_call: Optional[bool]

        :return: success of the write operation.
        :rtype: bool
        :raises ValueError: if a database connection cannot be opened, or if start_sample, padding_before, or padding_after is None
        :raises sqlite3.Error: if a database operation fails
        :raises Exception: if an unexpected error occurs during the write
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

        if start_sample is None or padding_before is None or padding_after is None:
            raise ValueError(
                f"start_sample, padding_before, and padding_after must all be provided to write an event (got start_sample={start_sample}, padding_before={padding_before}, padding_after={padding_after})"
            )

        try:
            success = False
            if self.conn is None:
                self.conn = sqlite3.connect(Path(self.settings["Output File"]["Value"]))
                self.conn.execute("PRAGMA foreign_keys = ON;")
                self.cursor = self.conn.cursor()
                self.conn.execute("SAVEPOINT write_event")
            if self.conn is None or self.cursor is None:
                raise ValueError("Unable to open database connection in _write_data")

            data_blob = data.astype(self.output_dtype).tobytes()

            self.cursor.execute(
                """INSERT OR IGNORE INTO events (
                    channel_id, channel_db_id, event_id,
                    absolute_start, padding_before, padding_after,
                    baseline_mean, baseline_std, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    channel,
                    self.channel_db_id[channel],
                    index,
                    int(start_sample),
                    int(padding_before),
                    int(padding_after),
                    baseline_mean,
                    baseline_std,
                    data_blob,
                ),
            )
            success = self.cursor.rowcount == 1

        except sqlite3.Error as e:
            if self.conn:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.rollback()  # Rollback all changes if any operation fails
            raise e
        except Exception as e:  # Fallback for truly unexpected errors
            if self.conn:
                self.conn.execute("ROLLBACK TO SAVEPOINT write_event")
                self.conn.rollback()
            raise e
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
    def _validate_settings(self, settings: dict) -> None:
        """
        Validate that the settings dict contains the correct information for use by the subclass.

        :param settings: Parameters for event detection.
        :type settings: dict
        :raises KeyError: If the settings dict does not contain the correct information.
        """
        if "MetaEventFinder" not in settings.keys():
            raise KeyError(
                """settings must include a 'MetaEventFinder' key with value equal to the key of the vent finder from which to pull event data"""
            )

    # private API continued, should implemented by subclasses, but has default behavior if it is not needed
    @log(logger=logger)
    def _rescale_data_to_adc(
        self,
        data: np.ndarray,
        scale: Optional[float] = None,
        offset: Optional[float] = None,
        raw_data: bool = False,
        dtype: type = np.uint16,
        adc_min: int = np.iinfo(np.int16).min,
        adc_max: int = np.iinfo(np.int16).max,
    ) -> tuple[npt.NDArray[np.number], Optional[float], Optional[float]]:
        """
        Not used by this writer

        :param data: 1D numpy array of data to write to the active file in the specified channel.
        :type data: np.ndarray
        :param scale: Scaling between provided data type and encoded form for storage. If None, scale is calculated based on the data to maximally use the available adc range.
        :type scale: Optional[float]
        :param offset: Offset between provided data type and encoded form for storage. If None, offset is calculated based on the data to maximally use the available adc range.
        :type offset: Optional[float]
        :param raw_data: True means to simply write data as-is to file, False indicates to first rescale it. Default False.
        :type raw_data: bool
        :param dtype: Numpy dtype to use for storage. Defaults to 16-bit signed int.
        :type dtype: type
        :param adc_min: Integer encoding the minimum adc code for the adc conversion.
        :type adc_min: int
        :param adc_max: Integer encoding the maximum adc code for the adc conversion.
        :type adc_max: int

        :return: Rescaled data as numpy array, scale factor, and offset.
        :rtype: tuple[npt.NDArray[np.number], Optional[float], Optional[float]]
        """
        return data, scale, offset

    @log(logger=logger)
    @override
    def _set_output_dtype(self) -> str:
        """
        set the output dtype - should be a numpy numeric type:

        self.output_dtype = '<u2'
        """
        return "<f8"

    # private API continued, can be implemented by subclasses, but default behavior is suitable for most use cases

    # Utility functions, specific to subclasses as needed
