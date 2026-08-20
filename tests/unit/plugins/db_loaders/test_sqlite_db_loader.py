"""Unit tests for SQLiteDBLoader class."""

import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader


class TestSQLiteDBLoader:
    """Test suite for SQLiteDBLoader class."""

    @pytest.fixture
    def temp_db_path(self) -> Generator[Path, None, None]:
        """Create a temporary database file for testing."""
        # Create temp file without keeping it open (Windows compatibility)
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)  # Close file descriptor immediately
        db_path = Path(tmp_path)
        yield db_path
        # Clean up with retry for Windows
        import gc

        gc.collect()  # Force garbage collection to close any remaining connections
        for i in range(10):  # More retries
            try:
                if db_path.exists():
                    db_path.unlink()
                break
            except PermissionError:
                if i < 9:  # Don't sleep on last iteration
                    time.sleep(0.2)  # Longer wait
                else:
                    # If still locked after retries, log but don't fail
                    import warnings

                    warnings.warn(f"Could not delete {db_path} - file may be locked")

    @pytest.fixture
    def mock_db(self, temp_db_path: Path) -> Generator[Path, None, None]:
        """Create a mock database with expected schema."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Create schema
        cursor.executescript(
            """
            CREATE TABLE experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                samplerate REAL NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );

            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );

            CREATE TABLE data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                data_format TEXT NOT NULL,
                samplerate REAL NOT NULL,
                padding_before INTEGER NOT NULL,
                padding_after INTEGER NOT NULL,
                raw_data BLOB,
                filtered_data BLOB,
                fit_data BLOB,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE sublevels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
            );

            CREATE TABLE columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                table_name TEXT NOT NULL,
                units TEXT
            );

            CREATE TABLE event_counts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE (experiment_id, channel_id),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );

            -- Insert test data
            INSERT INTO experiments (name) VALUES ('test_experiment_1');
            INSERT INTO experiments (name) VALUES ('test_experiment_2');

            INSERT INTO channels (experiment_id, channel_id, samplerate)
            VALUES (1, 0, 10000.0);
            INSERT INTO channels (experiment_id, channel_id, samplerate)
            VALUES (1, 1, 10000.0);
            INSERT INTO channels (experiment_id, channel_id, samplerate)
            VALUES (2, 0, 5000.0);

            INSERT INTO events (event_id, experiment_id, channel_id)
            VALUES (0, 1, 0);
            INSERT INTO events (event_id, experiment_id, channel_id)
            VALUES (1, 1, 0);
            INSERT INTO events (event_id, experiment_id, channel_id)
            VALUES (0, 1, 1);

            INSERT INTO columns (name, table_name, units)
            VALUES ('dwell_time', 'events', 'ms');
            INSERT INTO columns (name, table_name, units)
            VALUES ('amplitude', 'events', 'pA');
            INSERT INTO columns (name, table_name, units)
            VALUES ('area', 'events', NULL);

            INSERT INTO event_counts (experiment_id, channel_id, event_count)
            VALUES (1, 0, 2);
            INSERT INTO event_counts (experiment_id, channel_id, event_count)
            VALUES (1, 1, 1);
            """
        )

        conn.commit()
        cursor.close()
        conn.close()

        yield temp_db_path

        # Explicit cleanup - ensure no connections remain
        import gc

        gc.collect()

    @pytest.fixture
    def settings(self, mock_db: Path) -> Dict[str, Dict[str, Any]]:
        """Create valid settings dictionary."""
        return {"Input File": {"Type": str, "Value": str(mock_db)}}

    @pytest.fixture
    def loader(self, settings: Dict[str, Dict[str, Any]]) -> SQLiteDBLoader:
        """Create SQLiteDBLoader instance."""
        with patch.object(SQLiteDBLoader, "_init"):
            loader_instance = SQLiteDBLoader(settings=settings)
        return loader_instance

    def test_init_with_valid_settings(self, mock_db: Path) -> None:
        """Test initialization with valid settings."""
        settings = {"Input File": {"Type": str, "Value": str(mock_db)}}
        loader = SQLiteDBLoader(settings=settings)
        assert loader.db_path == mock_db

    def test_init_with_invalid_settings(self, loader: SQLiteDBLoader) -> None:
        """Test initialization with invalid settings raises ValueError.

        Note: _validate_settings is called during __init__ but the loader fixture
        bypasses __init__ via __new__, so we test _validate_settings directly.
        """
        invalid_settings: Dict[str, Any] = {}
        with pytest.raises(ValueError, match="requires an Input File"):
            loader._validate_settings(invalid_settings)

    def test_init_with_missing_tables(self, temp_db_path: Path) -> None:
        """Test initialization with incomplete database schema."""
        # Create database with missing tables
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE experiments (id INTEGER PRIMARY KEY);")
        conn.commit()
        conn.close()

        settings = {"Input File": {"Type": str, "Value": str(temp_db_path)}}
        with pytest.raises(ValueError, match="Missing tables"):
            SQLiteDBLoader(settings=settings)

    def test_init_with_extra_tables(self, mock_db: Path) -> None:
        """Test initialization with extra tables in database."""
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE extra_table (id INTEGER PRIMARY KEY);")
        conn.commit()
        conn.close()

        settings = {"Input File": {"Type": str, "Value": str(mock_db)}}
        with pytest.raises(ValueError, match="Extra tables found"):
            SQLiteDBLoader(settings=settings)

    def test_get_llm_prompt(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test LLM prompt generation."""
        loader.db_path = mock_db
        prompt = loader.get_llm_prompt()

        assert prompt is not None
        assert "Tables:" in prompt
        assert "experiments" in prompt
        assert "events" in prompt
        assert "Schema:" in prompt

    def test_get_llm_prompt_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test LLM prompt generation with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        prompt = loader.get_llm_prompt()
        assert prompt is None

    def test_close_resources(self, loader: SQLiteDBLoader) -> None:
        """Test closing resources (should be no-op for SQLiteDBLoader)."""
        # Should not raise any exceptions
        loader.close_resources()
        loader.close_resources(channel=0)

    def test_reset_channel(self, loader: SQLiteDBLoader) -> None:
        """Test resetting channel (should be no-op for SQLiteDBLoader)."""
        # Should not raise any exceptions
        loader.reset_channel()
        loader.reset_channel(channel=0)

    def test_get_experiment_names_all(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving all experiment names."""
        loader.db_path = mock_db
        names = loader.get_experiment_names()

        assert names is not None
        assert len(names) == 2
        assert "test_experiment_1" in names
        assert "test_experiment_2" in names

    def test_get_experiment_names_by_id(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving experiment name by ID."""
        loader.db_path = mock_db
        names = loader.get_experiment_names(experiment_id=1)

        assert names is not None
        assert len(names) == 1
        assert names[0] == "test_experiment_1"

    def test_get_experiment_names_invalid_id(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving experiment name with invalid ID."""
        loader.db_path = mock_db
        names = loader.get_experiment_names(experiment_id=999)
        assert names is None

    def test_get_experiment_names_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting experiment names with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        names = loader.get_experiment_names()
        assert names is None

    def test_get_channels_by_experiment(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving channels for an experiment."""
        loader.db_path = mock_db
        channels = loader.get_channels_by_experiment("test_experiment_1")

        assert channels is not None
        assert len(channels) == 2
        assert 0 in channels
        assert 1 in channels

    def test_get_channels_by_experiment_not_found(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving channels for non-existent experiment."""
        loader.db_path = mock_db
        channels = loader.get_channels_by_experiment("nonexistent_experiment")
        assert channels is None

    def test_get_channels_by_experiment_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting channels with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        channels = loader.get_channels_by_experiment("test_experiment_1")
        assert channels is None

    def test_get_event_counts_all(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test getting total event count across all experiments."""
        loader.db_path = mock_db
        count = loader.get_event_counts_by_experiment_and_channel()
        assert count == 3

    def test_get_event_counts_by_experiment(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test getting event count for specific experiment."""
        loader.db_path = mock_db
        count = loader.get_event_counts_by_experiment_and_channel(
            experiment="test_experiment_1"
        )
        assert count == 3

    def test_get_event_counts_by_experiment_and_channel(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test getting event count for specific experiment and channel."""
        loader.db_path = mock_db
        count = loader.get_event_counts_by_experiment_and_channel(
            experiment="test_experiment_1", channel=0
        )
        assert count == 2

    def test_get_event_counts_no_events(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test getting event count when no events match criteria."""
        loader.db_path = mock_db
        count = loader.get_event_counts_by_experiment_and_channel(
            experiment="test_experiment_2", channel=0
        )
        assert count == 0

    def test_get_event_counts_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting event counts with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        count = loader.get_event_counts_by_experiment_and_channel()
        assert count is None

    def test_get_column_units(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test retrieving column units."""
        loader.db_path = mock_db
        units = loader.get_column_units("dwell_time")
        assert units == "ms"

    def test_get_column_units_null(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test retrieving column units when NULL."""
        loader.db_path = mock_db
        units = loader.get_column_units("area")
        assert units == ""

    def test_get_column_units_not_found(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving units for non-existent column."""
        loader.db_path = mock_db
        units = loader.get_column_units("nonexistent_column")
        assert units == ""

    def test_get_column_units_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting column units with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        units = loader.get_column_units("dwell_time")
        assert units is None

    def test_get_column_names_by_table(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving column names for a table."""
        loader.db_path = mock_db
        columns = loader.get_column_names_by_table("events")

        assert columns is not None
        assert "dwell_time" in columns
        assert "amplitude" in columns

    def test_get_column_names_all_tables(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving all column names."""
        loader.db_path = mock_db
        columns = loader.get_column_names_by_table()

        assert columns is not None
        assert len(columns) == 3

    def test_get_column_names_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting column names with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        columns = loader.get_column_names_by_table("events")
        assert columns is None

    def test_get_table_names(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test retrieving table names."""
        loader.db_path = mock_db
        tables = loader.get_table_names()

        assert tables is not None
        assert "experiments" in tables
        assert "events" in tables
        assert "channels" in tables
        assert "sqlite_sequence" not in tables

    def test_get_table_names_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting table names with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        tables = loader.get_table_names()
        assert tables is None

    def test_get_table_by_column(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test retrieving table name by column."""
        loader.db_path = mock_db
        table = loader.get_table_by_column("dwell_time")
        assert table == "events"

    def test_get_table_by_column_not_found(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving table for non-existent column."""
        loader.db_path = mock_db
        table = loader.get_table_by_column("nonexistent_column")
        assert table is None

    def test_get_table_by_column_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting table by column with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        table = loader.get_table_by_column("dwell_time")
        assert table is None

    def test_validate_filter_query_valid(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test validating a valid query."""
        loader.db_path = mock_db
        valid, error = loader.validate_filter_query("SELECT * FROM events")
        assert valid is True
        assert error == ""

    def test_validate_filter_query_invalid(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test validating an invalid query."""
        loader.db_path = mock_db
        valid, error = loader.validate_filter_query("SELECT * FROM nonexistent_table")
        assert valid is False
        assert "Invalid query" in error

    def test_validate_filter_query_syntax_error(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test validating a query with syntax error."""
        loader.db_path = mock_db
        valid, error = loader.validate_filter_query("SELECT * FORM events")
        assert valid is False
        assert "Invalid query" in error

    def test_alter_database_success(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test altering database with valid queries."""
        loader.db_path = mock_db
        queries = ["CREATE TABLE test_table (id INTEGER PRIMARY KEY);"]
        result = loader.alter_database(queries)
        assert result is True

        # Verify table was created
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table';"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_alter_database_error(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test altering database with invalid query."""
        loader.db_path = mock_db
        queries = ["INVALID SQL STATEMENT;"]
        with pytest.raises(sqlite3.Error):
            loader.alter_database(queries)

    def test_alter_database_rollback(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test database rollback on error."""
        loader.db_path = mock_db
        queries = [
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY);",
            "INVALID SQL;",
        ]
        with pytest.raises(sqlite3.Error):
            loader.alter_database(queries)

        # Verify table was not created (rollback successful)
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table';"
        )
        assert cursor.fetchone() is None
        conn.close()

    def test_add_columns_to_table_success(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns to table."""
        loader.db_path = mock_db

        df = pd.DataFrame({"id": [1, 2, 3], "new_column": [1.5, 2.5, 3.5]})
        units = ["nA"]

        result = loader.add_columns_to_table(df, units, "events")
        assert result is True

        # Verify column was added
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(events);")
        columns = [row[1] for row in cursor.fetchall()]
        assert "new_column" in columns
        conn.close()

    def test_add_columns_to_table_no_id_column(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns without id column."""
        loader.db_path = mock_db
        df = pd.DataFrame({"value": [1, 2, 3]})
        units = ["V"]

        result = loader.add_columns_to_table(df, units, "events")
        assert result is False

    def test_add_columns_to_table_no_new_columns(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns with only id column."""
        loader.db_path = mock_db
        df = pd.DataFrame({"id": [1, 2, 3]})
        units: List[Optional[str]] = []

        result = loader.add_columns_to_table(df, units, "events")
        assert result is False

    def test_add_columns_to_table_nonexistent_table(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns to non-existent table."""
        loader.db_path = mock_db
        df = pd.DataFrame({"id": [1, 2], "new_col": [1, 2]})
        units = ["m"]

        with pytest.raises(ValueError, match="does not exist"):
            loader.add_columns_to_table(df, units, "nonexistent_table")

    def test_add_columns_to_table_conflicting_columns(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns that already exist."""
        loader.db_path = mock_db
        df = pd.DataFrame({"id": [1, 2], "event_id": [10, 20]})
        units = ["units"]

        with pytest.raises(ValueError, match="already exist"):
            loader.add_columns_to_table(df, units, "events")

    def test_add_columns_to_table_null_units(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test adding columns with None units."""
        loader.db_path = mock_db
        df = pd.DataFrame({"id": [1, 2], "col_no_units": [5, 10]})
        units: List[Optional[str]] = [None]

        result = loader.add_columns_to_table(df, units, "events")
        assert result is True

    def test_get_samplerate_by_experiment_and_channel(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving sample rate."""
        loader.db_path = mock_db
        samplerate = loader.get_samplerate_by_experiment_and_channel(
            "test_experiment_1", 0
        )
        assert samplerate == 10000.0

    def test_get_samplerate_invalid_combination(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test retrieving sample rate for invalid combination."""
        loader.db_path = mock_db
        with pytest.raises(ValueError, match="Unable to extract samplerate"):
            loader.get_samplerate_by_experiment_and_channel("test_experiment_1", 999)

    def test_get_samplerate_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test getting sample rate with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        samplerate = loader.get_samplerate_by_experiment_and_channel(
            "test_experiment_1", 0
        )
        assert samplerate is None

    def test_get_empty_settings_standalone(self, loader: SQLiteDBLoader) -> None:
        """Test getting empty settings in standalone mode."""
        settings = loader.get_empty_settings(standalone=True)

        assert "Input File" in settings
        assert settings["Input File"]["Type"] is str
        assert "SQLite3 Files" in settings["Input File"]["Options"][0]

    def test_get_empty_settings_with_plugins(self, loader: SQLiteDBLoader) -> None:
        """Test getting empty settings with plugins."""
        plugins = {"TestPlugin": ["plugin1", "plugin2"]}
        settings = loader.get_empty_settings(
            globally_available_plugins=plugins, standalone=False
        )

        assert "Input File" in settings
        assert len(settings["Input File"]["Options"]) == 3

    def test_load_metadata_success(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test loading metadata with valid query."""
        loader.db_path = mock_db
        df = loader._load_metadata("SELECT * FROM experiments")

        assert df is not None
        assert len(df) == 2
        assert "name" in df.columns

    def test_load_metadata_empty_result(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test loading metadata with query returning no results."""
        loader.db_path = mock_db
        df = loader._load_metadata("SELECT * FROM experiments WHERE id = 999")
        assert df is None

    def test_load_metadata_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test loading metadata with database error."""
        loader.db_path = Path("/nonexistent/path.db")
        df = loader._load_metadata("SELECT * FROM experiments")
        assert df is None

    def test_load_metadata_generator_success(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test loading metadata using generator."""
        loader.db_path = mock_db
        gen = loader._load_metadata_generator("SELECT * FROM experiments")

        results = list(gen)
        assert len(results) == 2
        assert all(isinstance(row, pd.DataFrame) for row in results)

    def test_load_metadata_generator_empty(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test loading metadata generator with no results."""
        loader.db_path = mock_db
        gen = loader._load_metadata_generator(
            "SELECT * FROM experiments WHERE id = 999"
        )
        results = list(gen)
        assert len(results) == 0

    def test_load_event_data_success(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test loading event data."""
        loader.db_path = mock_db

        # Add event data to database
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        raw_data = np.array([1.0, 2.0, 3.0], dtype=np.float64).tobytes()
        cursor.execute(
            """
            INSERT INTO data (event_id, data_format, samplerate, padding_before,
                            padding_after, raw_data, filtered_data, fit_data)
            VALUES (1, 'float64', 10000.0, 10, 10, ?, ?, ?)
            """,
            (raw_data, raw_data, raw_data),
        )
        conn.commit()
        conn.close()

        query = """
            SELECT e.id, e.event_id, e.channel_id, e.experiment_id,
                   d.data_format, d.samplerate, d.padding_before, d.padding_after,
                   d.raw_data, d.filtered_data, d.fit_data
            FROM events e
            JOIN data d ON e.id = d.event_id
            LIMIT 1
        """

        gen = loader._load_event_data(query)
        result = next(gen)

        assert len(result) == 10
        db_id, exp_id, ch_id, ev_id, sr, pb, pa, raw, filt, fit = result
        assert isinstance(db_id, int)
        assert isinstance(raw, np.ndarray)
        assert len(raw) == 3

    def test_load_event_data_abort(self, loader: SQLiteDBLoader, mock_db: Path) -> None:
        """Test aborting event data generator."""
        loader.db_path = mock_db

        # Add event data
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        raw_data = np.array([1.0, 2.0], dtype=np.float64).tobytes()
        cursor.execute(
            """
            INSERT INTO data (event_id, data_format, samplerate, padding_before,
                            padding_after, raw_data, filtered_data, fit_data)
            VALUES (1, 'float64', 10000.0, 5, 5, ?, ?, ?)
            """,
            (raw_data, raw_data, raw_data),
        )
        conn.commit()
        conn.close()

        query = """
            SELECT e.id, e.event_id, e.channel_id, e.experiment_id,
                   d.data_format, d.samplerate, d.padding_before, d.padding_after,
                   d.raw_data, d.filtered_data, d.fit_data
            FROM events e
            JOIN data d ON e.id = d.event_id
        """

        gen = loader._load_event_data(query)
        next(gen)
        # Send abort signal
        try:
            gen.send(True)
        except StopIteration:
            pass  # Expected when generator is aborted

    def test_get_sqlite_type_integer(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for integer."""
        dtype = pd.Series([1, 2, 3]).dtype
        assert loader._get_sqlite_type(dtype) == "INTEGER"

    def test_get_sqlite_type_float(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for float."""
        dtype = pd.Series([1.0, 2.0, 3.0]).dtype
        assert loader._get_sqlite_type(dtype) == "REAL"

    def test_get_sqlite_type_string(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for string."""
        dtype = pd.Series(["a", "b", "c"]).dtype
        assert loader._get_sqlite_type(dtype) == "TEXT"

    def test_get_sqlite_type_bool(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for boolean."""
        dtype = pd.Series([True, False]).dtype
        assert loader._get_sqlite_type(dtype) == "INTEGER"

    def test_get_sqlite_type_datetime(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for datetime."""
        dtype = pd.to_datetime(pd.Series(["2021-01-01", "2021-01-02"])).dtype
        assert loader._get_sqlite_type(dtype) == "TEXT"

    def test_get_sqlite_type_object(self, loader: SQLiteDBLoader) -> None:
        """Test SQLite type mapping for object."""
        dtype = pd.Series([object(), object()]).dtype
        assert loader._get_sqlite_type(dtype) == "TEXT"

    def test_ensure_event_counts_creates_table(
        self, loader: SQLiteDBLoader, temp_db_path: Path
    ) -> None:
        """Test that _ensure_event_counts creates missing table."""
        # Create a fresh temp database (don't use mock_db which already has event_counts)
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        test_db_path = Path(tmp_path)

        try:
            # Create minimal database without event_counts
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE experiments (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY,
                    experiment_id INTEGER,
                    channel_id INTEGER,
                    event_id INTEGER
                );
                INSERT INTO experiments (id, name) VALUES (1, 'test');
                INSERT INTO events (id, experiment_id, channel_id, event_id)
                VALUES (1, 1, 0, 0), (2, 1, 0, 1);
                """
            )
            conn.commit()
            cursor.close()
            conn.close()

            loader.db_path = test_db_path
            loader._ensure_event_counts()

            # Verify table exists and is populated
            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM event_counts WHERE experiment_id=1 AND channel_id=0;"
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            assert result is not None
            assert result[3] == 2  # event_count should be 2
        finally:
            # Clean up
            import gc

            gc.collect()
            for _ in range(5):
                try:
                    if test_db_path.exists():
                        test_db_path.unlink()
                    break
                except PermissionError:
                    time.sleep(0.1)

    def test_ensure_event_counts_existing_table(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test that _ensure_event_counts handles existing table."""
        loader.db_path = mock_db
        # Should not raise any errors
        loader._ensure_event_counts()

        # Verify table still exists
        conn = sqlite3.connect(mock_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='event_counts';"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_validate_settings_missing_input_file(self, loader: SQLiteDBLoader) -> None:
        """Test settings validation with missing Input File."""
        invalid_settings: Dict[str, Any] = {}
        with pytest.raises(ValueError, match="requires an Input File"):
            loader._validate_settings(invalid_settings)

    def test_validate_settings_valid(
        self, loader: SQLiteDBLoader, mock_db: Path
    ) -> None:
        """Test settings validation with valid settings."""
        valid_settings = {"Input File": {"Value": str(mock_db)}}
        # Should not raise
        loader._validate_settings(valid_settings)

    def test_finalize_initialization_db_error(self, loader: SQLiteDBLoader) -> None:
        """Test finalization with database error."""
        loader.settings = {"Input File": {"Value": "/nonexistent/path.db"}}
        with pytest.raises(sqlite3.Error):
            loader._finalize_initialization()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
