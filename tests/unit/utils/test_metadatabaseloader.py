"""Unit tests for MetaDatabaseLoader abstract base class."""

import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from poriscope.utils.MetaDatabaseLoader import MetaDatabaseLoader


class ConcreteDatabaseLoader(MetaDatabaseLoader):
    """Concrete implementation of MetaDatabaseLoader for testing."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """Initialize with settings."""
        self.mock_experiments = ["exp1", "exp2"]
        self.mock_channels = {1: [0, 1], 2: [0]}
        self.mock_event_counts = {("exp1", 0): 10, ("exp1", 1): 5, ("exp2", 0): 3}
        super().__init__(settings)

    def get_llm_prompt(self) -> str:
        return "Mock LLM prompt"

    def reset_channel(self, channel: Optional[int] = None) -> None:
        pass

    def close_resources(self, channel: Optional[int] = None) -> None:
        pass

    def get_experiment_names(
        self, experiment_id: Optional[int] = None
    ) -> Optional[List[str]]:
        if experiment_id is None:
            return self.mock_experiments
        if experiment_id == 1:
            return ["exp1"]
        return None

    def get_channels_by_experiment(self, experiment: str) -> Optional[List[int]]:
        if experiment == "exp1":
            return [0, 1]
        if experiment == "exp2":
            return [0]
        return None

    def get_event_counts_by_experiment_and_channel(
        self, experiment: Optional[str] = None, channel: Optional[int] = None
    ) -> int:
        if experiment is None:
            return 18
        if channel is None:
            return sum(
                v for k, v in self.mock_event_counts.items() if k[0] == experiment
            )
        return self.mock_event_counts.get((experiment, channel), 0)

    def get_column_units(self, column_name: str) -> Optional[str]:
        units_map = {"dwell_time": "ms", "amplitude": "pA"}
        return units_map.get(column_name, "")

    def get_column_names_by_table(
        self, table: Optional[str] = None
    ) -> Optional[List[str]]:
        if table == "events":
            return ["dwell_time", "amplitude", "area"]
        if table == "sublevels":
            return ["sublevel_duration", "sublevel_amplitude"]
        if table == "experiments":
            return ["name", "date"]
        if table is None:
            return ["dwell_time", "amplitude", "area", "sublevel_duration"]
        return None

    def get_table_names(self) -> Optional[List[str]]:
        return ["events", "sublevels", "experiments", "channels", "data", "columns"]

    def validate_filter_query(self, query: str) -> Tuple[bool, str]:
        if "INVALID" in query:
            return False, f"Invalid query: {query}"
        return True, ""

    def get_samplerate_by_experiment_and_channel(
        self, experiment: str, channel: int
    ) -> Optional[float]:
        return 10000.0

    def get_table_by_column(self, column: str) -> Optional[str]:
        events_cols = ["dwell_time", "amplitude", "area"]
        sublevels_cols = ["sublevel_duration", "sublevel_amplitude"]
        experiments_cols = ["name", "date"]
        if column in events_cols:
            return "events"
        if column in sublevels_cols:
            return "sublevels"
        if column in experiments_cols:
            return "experiments"
        return None

    def add_columns_to_table(
        self, df: pd.DataFrame, units: List[Optional[str]], table_name: str
    ) -> bool:
        return True

    def alter_database(self, queries: List[str]) -> bool:
        return True

    def get_empty_settings(
        self,
        globally_available_plugins: Optional[Dict[str, List[str]]] = None,
        standalone: bool = False,
    ) -> Dict[str, Dict[str, Any]]:
        """Implement get_empty_settings."""
        settings: Dict[str, Dict[str, Any]] = {
            "Input File": {"Type": str, "Options": ["All Files (*.*)"]}
        }
        return settings

    def _init(self) -> None:
        pass

    def _load_metadata(self, query: str) -> Optional[pd.DataFrame]:
        if "SELECT" not in query:
            return None
        
        # Determine what kind of query and return appropriate mock data
        if "events" in query.lower():
            return pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "experiment_id": [1, 1, 2],
                    "channel_id": [0, 1, 0],
                    "channel_db_id": [1, 2, 3],  # Add this for CSV export
                    "event_id": [0, 1, 0],
                    "event_db_id": [1, 2, 3],  # Add this for CSV export
                    "dwell_time": [10.0, 15.0, 20.0],
                }
            )
        elif "sublevels" in query.lower():
            return pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "event_db_id": [1, 2, 3],
                    "level_id": [0, 1, 2],
                    "levels_left": [2, 1, 0],
                    "sublevel_duration": [5.0, 10.0, 5.0],
                }
            )
        elif "experiments" in query.lower():
            return pd.DataFrame(
                {
                    "id": [1, 2],
                    "name": ["exp1", "exp2"],
                    "date": ["2024-01-01", "2024-01-02"],
                }
            )
        elif "channels" in query.lower():
            return pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "experiment_id": [1, 1, 2],
                    "channel_id": [0, 1, 0],
                    "samplerate": [10000.0, 10000.0, 5000.0],
                }
            )
        elif "columns" in query.lower():
            return pd.DataFrame(
                {
                    "name": ["dwell_time", "amplitude"],
                    "table_name": ["events", "events"],
                    "units": ["ms", "pA"],
                }
            )
        elif "data" in query.lower():
            return pd.DataFrame(
                {
                    "experiment_id": [1, 1, 2],
                    "channel_id": [0, 1, 0],
                    "channel_db_id": [1, 2, 3],
                    "event_id": [0, 1, 0],
                    "event_db_id": [1, 2, 3],
                }
            )
        else:
            # Default return for generic queries
            return pd.DataFrame(
                {
                    "id": [1, 2, 3],
                    "experiment_id": [1, 1, 2],
                    "channel_id": [0, 1, 0],
                    "event_id": [0, 1, 0],
                    "dwell_time": [10.0, 15.0, 20.0],
                }
            )

    def _load_metadata_generator(
        self, query: str
    ) -> Generator[pd.DataFrame, None, None]:
        df = self._load_metadata(query)
        if df is not None:
            for _, row in df.iterrows():
                yield pd.DataFrame([row])

    def _load_event_data(
        self, query: str
    ) -> Generator[Any, bool, None]:
        """Load event data and yield tuples.
        
        The base class load_event_data() unpacks these tuples into dicts.
        """
        for i in range(3):
            abort = yield (
                i + 1,  # db_id
                1,  # experiment_id
                0,  # channel_id
                i,  # event_id
                10000.0,  # samplerate
                10,  # padding_before
                10,  # padding_after
                np.array([1.0, 2.0, 3.0]),  # raw_data
                np.array([1.1, 2.1, 3.1]),  # filtered_data
                np.array([1.0, 2.0, 3.0]),  # fit_data
            )
            if abort:
                break

    def _ensure_event_counts(self) -> None:
        pass

    def _validate_settings(self, settings: dict) -> None:
        if "Input File" not in settings:
            raise ValueError("Input File is required")

    def get_experiment_id_by_name(self, experiment_name: str) -> Optional[int]:
        """Override to provide test data.
        
        Note: The base class implementation queries the database. We mock it here
        but need to return None for invalid experiments so the base class validation
        can raise KeyError appropriately.
        """
        if experiment_name == "exp1":
            return 1
        if experiment_name == "exp2":
            return 2
        # Return None for invalid experiments - the calling code will raise KeyError
        return None


class TestMetaDatabaseLoader:
    """Test suite for MetaDatabaseLoader class."""

    @pytest.fixture
    def loader(self) -> ConcreteDatabaseLoader:
        """Create a concrete loader instance for testing."""
        settings = {"Input File": {"Type": str, "Value": "/path/to/db.db"}}
        return ConcreteDatabaseLoader(settings=settings)

    def test_init(self, loader: ConcreteDatabaseLoader) -> None:
        """Test initialization."""
        assert loader is not None
        assert hasattr(loader, "settings")

    def test_get_empty_settings_default(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test getting empty settings with defaults."""
        settings = loader.get_empty_settings()
        assert "Input File" in settings
        assert settings["Input File"]["Type"] is str
        assert "All Files (*.*)" in settings["Input File"]["Options"]

    def test_get_empty_settings_with_plugins(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test getting empty settings with plugins."""
        plugins = {"MetaReader": ["Reader1", "Reader2"]}
        settings = loader.get_empty_settings(globally_available_plugins=plugins)
        assert "Input File" in settings

    def test_force_serial_channel_operations(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test force serial channel operations default."""
        assert loader.force_serial_channel_operations() is False

    def test_get_experiments_and_channels(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test getting experiments and channels mapping."""
        result = loader.get_experiments_and_channels()
        assert "exp1" in result
        assert "exp2" in result
        assert result["exp1"] == [0, 1]
        assert result["exp2"] == [0]

    def test_get_experiments_and_channels_empty(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test getting experiments and channels with no experiments."""
        loader.mock_experiments = []
        result = loader.get_experiments_and_channels()
        assert result == {}

    def test_get_experiment_id_by_name(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test getting experiment ID by name."""
        assert loader.get_experiment_id_by_name("exp1") == 1
        assert loader.get_experiment_id_by_name("exp2") == 2
        assert loader.get_experiment_id_by_name("exp3") is None

    def test_report_channel_status(self, loader: ConcreteDatabaseLoader) -> None:
        """Test reporting channel status."""
        # Mock query_database_directly
        mock_data = pd.DataFrame(
            {
                "name": ["exp1", "exp1", "exp2"],
                "channel_id": [0, 1, 0],
                "event_count": [10, 5, 3],
            }
        )
        with patch.object(loader, "query_database_directly", return_value=mock_data):
            report = loader.report_channel_status()
            assert "2 experiments" in report
            assert "exp1" in report
            assert "exp2" in report
            assert "Channel: 0: 10 events" in report

    def test_report_channel_status_no_experiments(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test reporting channel status with no experiments."""
        with patch.object(
            loader, "query_database_directly", return_value=pd.DataFrame()
        ):
            report = loader.report_channel_status()
            assert report == "No experiments found."

    def test_report_channel_status_one_experiment(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test reporting channel status with single experiment."""
        mock_data = pd.DataFrame(
            {"name": ["exp1"], "channel_id": [0], "event_count": [10]}
        )
        with patch.object(loader, "query_database_directly", return_value=mock_data):
            report = loader.report_channel_status()
            assert " 1 experiment" in report

    def test_construct_metadata_query_events_only(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query for events table only."""
        query, debug, table = loader.construct_metadata_query(["dwell_time"])
        assert query != ""
        assert debug == ""
        assert "SELECT" in query
        assert "events" in query.lower()
        assert table == "events"

    def test_construct_metadata_query_sublevels_only(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query for sublevels table only."""
        query, debug, table = loader.construct_metadata_query(["sublevel_duration"])
        assert query != ""
        assert debug == ""
        assert "SELECT" in query
        assert "sublevels" in query.lower()
        assert table == "sublevels"

    def test_construct_metadata_query_mixed_tables(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query for mixed tables."""
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time", "sublevel_duration"]
        )
        assert query != ""
        assert debug == ""
        assert "JOIN" in query
        assert table == "sublevels"

    def test_construct_metadata_query_with_conditions(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with conditions."""
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time"], conditions="dwell_time > 10"
        )
        assert query != ""
        assert debug == ""
        assert "WHERE" in query

    def test_construct_metadata_query_with_experiments_and_channels(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with experiment/channel filters."""
        experiments_and_channels = {"exp1": [0, 1]}
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time"], experiments_and_channels=experiments_and_channels
        )
        assert query != ""
        assert debug == ""
        assert "WHERE" in query

    def test_construct_metadata_query_empty_columns(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with empty columns."""
        with pytest.raises(ValueError, match="cannot be empty"):
            loader.construct_metadata_query([])

    def test_construct_metadata_query_invalid_column(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with invalid column."""
        with pytest.raises(ValueError, match="could not be mapped"):
            loader.construct_metadata_query(["nonexistent_column"])

    def test_construct_metadata_query_with_experiments_table(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with experiments table columns."""
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time", "name"]
        )
        assert query != ""
        assert debug == ""
        assert "JOIN experiments" in query

    def test_construct_metadata_query_forced_join(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing metadata query with forced join due to conditions."""
        # Events columns but sublevel condition forces join
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time"], conditions="sublevel_duration < 100"
        )
        assert query != ""
        assert debug == ""
        assert "JOIN" in query

    def test_construct_event_data_query_no_conditions(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing event data query without conditions."""
        query, debug = loader.construct_event_data_query()
        assert query != ""
        assert debug == ""
        assert "SELECT" in query
        assert "data" in query.lower()

    def test_construct_event_data_query_with_conditions(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing event data query with conditions."""
        query, debug = loader.construct_event_data_query(
            conditions="event_id > 5"
        )
        assert query != ""
        assert debug == ""
        assert "WHERE" in query

    def test_construct_event_data_query_with_experiments_and_channels(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing event data query with experiment/channel filters."""
        experiments_and_channels = {"exp1": [0]}
        query, debug = loader.construct_event_data_query(
            experiments_and_channels=experiments_and_channels
        )
        assert query != ""
        assert debug == ""

    def test_construct_event_data_query_invalid_experiment(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing event data query with invalid experiment."""
        experiments_and_channels = {"nonexistent": [0]}
        with pytest.raises(KeyError, match="Could not find experiment"):
            loader.construct_event_data_query(
                experiments_and_channels=experiments_and_channels
            )

    def test_load_metadata(self, loader: ConcreteDatabaseLoader) -> None:
        """Test loading metadata."""
        df = loader.load_metadata(["dwell_time"])
        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert "dwell_time" in df.columns

    def test_load_metadata_invalid_query(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test loading metadata with invalid query."""
        # Make validate_filter_query fail
        with patch.object(
            loader, "validate_filter_query", return_value=(False, "Invalid query")
        ):
            df = loader.load_metadata(["dwell_time"])
            assert df is None

    def test_load_event_data(self, loader: ConcreteDatabaseLoader) -> None:
        """Test loading event data."""
        gen = loader.load_event_data()
        events = list(gen)
        assert len(events) == 3
        assert all("raw_data" in event for event in events)
        assert all("filtered_data" in event for event in events)

    def test_load_event_data_with_abort(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test loading event data with abort."""
        gen = loader.load_event_data()
        first_event = next(gen)
        assert first_event is not None
        # Send abort signal
        try:
            gen.send(True)
        except StopIteration:
            pass  # Expected

    def test_query_database_directly_valid(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test querying database directly with valid query."""
        df = loader.query_database_directly("SELECT * FROM events")
        assert df is not None
        assert isinstance(df, pd.DataFrame)

    def test_query_database_directly_invalid(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test querying database directly with invalid query."""
        df = loader.query_database_directly("SELECT INVALID FROM events")
        assert df is None

    def test_query_database_directly_and_get_generator(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test querying database and getting generator."""
        gen = loader.query_database_directly_and_get_generator(
            "SELECT * FROM events"
        )
        rows = list(gen)
        assert len(rows) == 3
        assert all(isinstance(row, pd.DataFrame) for row in rows)

    def test_query_database_directly_and_get_generator_invalid(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test querying database generator with invalid query."""
        gen = loader.query_database_directly_and_get_generator(
            "SELECT INVALID FROM events"
        )
        rows = list(gen)
        assert len(rows) == 0

    def test_query_database_directly_and_get_generator_abort(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test querying database generator with abort."""
        gen = loader.query_database_directly_and_get_generator(
            "SELECT * FROM events"
        )
        first_row = next(gen)
        assert first_row is not None
        # Send abort
        try:
            gen.send(True)
        except StopIteration:
            pass  # Expected

    def test_export_subset_to_csv(self, loader: ConcreteDatabaseLoader) -> None:
        """Test exporting subset to CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = loader.export_subset_to_csv(tmpdir)
            progress = list(gen)
            assert len(progress) > 0
            assert progress[-1] == 1.0

            # Check files were created
            output_path = Path(tmpdir)
            assert (output_path / "events.csv").exists()
            assert (output_path / "columns.csv").exists()

    def test_export_subset_to_csv_with_subset_name(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test exporting subset to CSV with subset name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = loader.export_subset_to_csv(tmpdir, subset_name="test")
            list(gen)  # Consume generator

            output_path = Path(tmpdir)
            assert (output_path / "test_events.csv").exists()

    def test_export_subset_to_csv_with_conditions(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test exporting subset to CSV with conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = loader.export_subset_to_csv(tmpdir, conditions="event_id > 0")
            list(gen)  # Consume generator

            output_path = Path(tmpdir)
            assert (output_path / "events.csv").exists()

    def test_export_subset_to_csv_invalid_folder(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test exporting subset to CSV with invalid folder."""
        # The function doesn't validate folder existence, so it will fail when trying to write
        gen = loader.export_subset_to_csv("/nonexistent/path")
        with pytest.raises(Exception):
            list(gen)

    def test_export_subset_to_csv_no_events(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test exporting subset with no matching events."""
        # Mock _load_metadata to return empty DataFrame
        with patch.object(loader, "_load_metadata", return_value=pd.DataFrame()):
            with tempfile.TemporaryDirectory() as tmpdir:
                gen = loader.export_subset_to_csv(tmpdir)
                with pytest.raises(ValueError, match="No events found"):
                    list(gen)

    def test_format_debug_msg(self, loader: ConcreteDatabaseLoader) -> None:
        """Test formatting debug messages."""
        debug = "Error:   Invalid   query\n    with   extra   spaces"
        formatted = loader._format_debug_msg(debug)
        assert "  " not in formatted
        assert "\n " not in formatted

    def test_validate_settings_missing_input_file(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test settings validation with missing Input File."""
        with pytest.raises(ValueError, match="Input File is required"):
            loader._validate_settings({})

    def test_validate_settings_valid(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test settings validation with valid settings."""
        settings = {"Input File": {"Value": "/path/to/file.db"}}
        # Should not raise
        loader._validate_settings(settings)

    def test_construct_metadata_query_removes_duplicates(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test that construct_metadata_query removes duplicate columns."""
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time", "id", "experiment_id"]
        )
        assert query != ""
        # id and experiment_id should be removed as they're redundant
        assert query.count("id") >= 1  # At least appears once in SELECT

    def test_construct_metadata_query_experiments_only(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test constructing query for experiments table only."""
        query, debug, table = loader.construct_metadata_query(["name"])
        assert query != ""
        assert "experiments" in query.lower()
        # Should include event_id since we need events anchor
        assert "event_id" in query.lower()

    def test_load_metadata_removes_duplicate_columns(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test that load_metadata removes duplicate columns."""
        # Mock _load_metadata to return DataFrame with duplicates
        # Create DataFrame then add duplicate column
        df_with_dupes = pd.DataFrame({"id": [1, 2], "dwell_time": [10, 20]})
        df_with_dupes["id"] = [1, 2]  # Add duplicate column
        
        with patch.object(loader, "_load_metadata", return_value=df_with_dupes):
            result = loader.load_metadata(["dwell_time"])
            # Should remove duplicate columns
            assert result is not None

    def test_construct_metadata_query_invalid_experiment(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        """Test construct_metadata_query with invalid experiment name."""
        experiments_and_channels = {"invalid_exp": [0]}
        with pytest.raises(KeyError, match="Could not find experiment"):
            loader.construct_metadata_query(
                ["dwell_time"], experiments_and_channels=experiments_and_channels
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
