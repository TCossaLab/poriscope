"""Unit tests for MetaDatabaseLoader abstract base class."""

import sqlite3
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

    def get_column_type(self, column_name) -> Optional[str]:
        return "REAL"

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

    def _load_event_data(self, query: str) -> Generator[Any, bool, None]:
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

    def test_get_empty_settings_default(self, loader: ConcreteDatabaseLoader) -> None:
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

    def test_get_experiments_and_channels(self, loader: ConcreteDatabaseLoader) -> None:
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

    def test_get_experiment_id_by_name(self, loader: ConcreteDatabaseLoader) -> None:
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
        query, debug, table = loader.construct_metadata_query(["dwell_time", "name"])
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
        query, debug = loader.construct_event_data_query(conditions="event_id > 5")
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

    def test_load_metadata_invalid_query(self, loader: ConcreteDatabaseLoader) -> None:
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

    def test_load_event_data_with_abort(self, loader: ConcreteDatabaseLoader) -> None:
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
        gen = loader.query_database_directly_and_get_generator("SELECT * FROM events")
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
        gen = loader.query_database_directly_and_get_generator("SELECT * FROM events")
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

    def test_validate_settings_valid(self, loader: ConcreteDatabaseLoader) -> None:
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


# ===========================================================================
# Additional coverage-focused tests below (abstract stub bodies, default
# implementations, and remaining branch combinations not exercised above).
# ===========================================================================


@pytest.fixture
def loader() -> ConcreteDatabaseLoader:
    settings = {"Input File": {"Type": str, "Value": "/path/to/db.db"}}
    return ConcreteDatabaseLoader(settings=settings)


# ---------------------------------------------------------------------------
# Abstract method stub bodies (the bare ``pass`` lines on MetaDatabaseLoader
# itself). These are never executed through the concrete subclass because the
# subclass always overrides them, so we invoke the unbound base implementation
# directly to exercise those lines.
# ---------------------------------------------------------------------------
class TestAbstractStubs:
    def test_public_abstract_stub_bodies(self, loader: ConcreteDatabaseLoader) -> None:
        assert MetaDatabaseLoader.get_llm_prompt(loader) is None
        assert MetaDatabaseLoader.reset_channel(loader) is None
        assert MetaDatabaseLoader.reset_channel(loader, channel=1) is None
        assert MetaDatabaseLoader.close_resources(loader) is None
        assert MetaDatabaseLoader.close_resources(loader, channel=1) is None
        assert MetaDatabaseLoader.get_experiment_names(loader) is None
        assert MetaDatabaseLoader.get_experiment_names(loader, experiment_id=1) is None
        assert MetaDatabaseLoader.get_channels_by_experiment(loader, "exp1") is None
        assert (
            MetaDatabaseLoader.get_event_counts_by_experiment_and_channel(loader)
            is None
        )
        assert MetaDatabaseLoader.get_column_units(loader, "dwell_time") is None
        assert MetaDatabaseLoader.get_column_type(loader, "dwell_time") is None
        assert MetaDatabaseLoader.get_column_names_by_table(loader) is None
        assert MetaDatabaseLoader.get_table_names(loader) is None
        assert MetaDatabaseLoader.validate_filter_query(loader, "SELECT 1") is None
        assert (
            MetaDatabaseLoader.get_samplerate_by_experiment_and_channel(
                loader, "exp1", 0
            )
            is None
        )
        assert MetaDatabaseLoader.get_table_by_column(loader, "dwell_time") is None
        assert (
            MetaDatabaseLoader.add_columns_to_table(
                loader, pd.DataFrame(), [], "events"
            )
            is None
        )
        assert MetaDatabaseLoader.alter_database(loader, []) is None

    def test_private_abstract_stub_bodies(self, loader: ConcreteDatabaseLoader) -> None:
        assert MetaDatabaseLoader._init(loader) is None
        assert MetaDatabaseLoader._load_metadata(loader, "SELECT 1") is None
        assert MetaDatabaseLoader._load_metadata_generator(loader, "SELECT 1") is None
        assert MetaDatabaseLoader._load_event_data(loader, "SELECT 1") is None
        assert MetaDatabaseLoader._ensure_event_counts(loader) is None
        assert MetaDatabaseLoader._validate_settings(loader, {}) is None


# ---------------------------------------------------------------------------
# get_plot_features default implementation
# ---------------------------------------------------------------------------
class TestGetPlotFeatures:
    def test_default_returns_all_none(self, loader: ConcreteDatabaseLoader) -> None:
        result = loader.get_plot_features(1, 0, 0)
        assert result == (None, None, None, None, None, None)


# ---------------------------------------------------------------------------
# get_experiment_id_by_name - base class implementation (the concrete loader
# overrides this method for other tests, so call the base implementation
# explicitly here).
# ---------------------------------------------------------------------------
class TestGetExperimentIdByNameBase:
    def test_base_impl_success(self, loader: ConcreteDatabaseLoader) -> None:
        result = MetaDatabaseLoader.get_experiment_id_by_name(loader, "exp1")
        assert result == 1

    def test_base_impl_empty_name_returns_none(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        assert MetaDatabaseLoader.get_experiment_id_by_name(loader, "") is None

    def test_base_impl_not_found_returns_none(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(loader, "query_database_directly", return_value=None):
            assert (
                MetaDatabaseLoader.get_experiment_id_by_name(loader, "missing") is None
            )

    def test_base_impl_raises_on_exception(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader, "query_database_directly", side_effect=RuntimeError("boom")
        ):
            with pytest.raises(RuntimeError, match="boom"):
                MetaDatabaseLoader.get_experiment_id_by_name(loader, "exp1")


# ---------------------------------------------------------------------------
# get_channel_db_id
# ---------------------------------------------------------------------------
class TestGetChannelDbId:
    def test_success(self, loader: ConcreteDatabaseLoader) -> None:
        mock_df = pd.DataFrame({"id": [42]})
        with patch.object(loader, "query_database_directly", return_value=mock_df):
            result = loader.get_channel_db_id("exp1", 0)
            assert result == 42

    def test_experiment_not_found(self, loader: ConcreteDatabaseLoader) -> None:
        with patch.object(loader, "get_experiment_id_by_name", return_value=None):
            assert loader.get_channel_db_id("nope", 0) is None

    def test_channel_query_returns_none(self, loader: ConcreteDatabaseLoader) -> None:
        with patch.object(loader, "query_database_directly", return_value=None):
            assert loader.get_channel_db_id("exp1", 0) is None

    def test_channel_query_returns_empty(self, loader: ConcreteDatabaseLoader) -> None:
        with patch.object(
            loader, "query_database_directly", return_value=pd.DataFrame()
        ):
            assert loader.get_channel_db_id("exp1", 0) is None

    def test_exception_is_caught(self, loader: ConcreteDatabaseLoader) -> None:
        with patch.object(
            loader, "get_experiment_id_by_name", side_effect=RuntimeError("boom")
        ):
            assert loader.get_channel_db_id("exp1", 0) is None


# ---------------------------------------------------------------------------
# export_subset_to_csv - error branches for each loaded table
# ---------------------------------------------------------------------------
class TestExportSubsetToCsvErrorBranches:
    def test_malformed_events_query_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (False, "bad") if "FROM events" in q else (True, ""),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed events query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_sublevels_load_returns_none_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        original_load_metadata = loader._load_metadata

        def fake_load_metadata(query):
            if "sublevels" in query.lower():
                return None
            return original_load_metadata(query)

        with patch.object(loader, "_load_metadata", side_effect=fake_load_metadata):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Failed to load sublevels"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_malformed_sublevels_query_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (
                (False, "bad") if "FROM sublevels" in q else (True, "")
            ),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed sublevels query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_experiments_table_load_fails(self, loader: ConcreteDatabaseLoader) -> None:
        original_query = loader.query_database_directly

        def fake_query(query):
            if "FROM experiments" in query:
                return None
            return original_query(query)

        with patch.object(loader, "query_database_directly", side_effect=fake_query):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Failed to load experiments"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_malformed_experiments_query_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (
                (False, "bad") if "FROM experiments" in q else (True, "")
            ),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed experiments query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_channels_table_load_fails(self, loader: ConcreteDatabaseLoader) -> None:
        original_query = loader.query_database_directly

        def fake_query(query):
            if "FROM channels" in query:
                return None
            return original_query(query)

        with patch.object(loader, "query_database_directly", side_effect=fake_query):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Failed to load channels"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_malformed_channels_query_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (
                (False, "bad") if "FROM channels" in q else (True, "")
            ),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed channels query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_columns_table_load_fails(self, loader: ConcreteDatabaseLoader) -> None:
        original_query = loader.query_database_directly

        def fake_query(query):
            if "FROM columns" in query:
                return None
            return original_query(query)

        with patch.object(loader, "query_database_directly", side_effect=fake_query):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Failed to load columns"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_malformed_columns_query_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (False, "bad") if "FROM columns" in q else (True, ""),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed columns query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_data_table_load_fails(self, loader: ConcreteDatabaseLoader) -> None:
        original_query = loader.query_database_directly

        def fake_query(query):
            if "FROM data" in query:
                return None
            return original_query(query)

        with patch.object(loader, "query_database_directly", side_effect=fake_query):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Failed to load data table"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_malformed_data_query_raises(self, loader: ConcreteDatabaseLoader) -> None:
        with patch.object(
            loader,
            "validate_filter_query",
            side_effect=lambda q: (False, "bad") if "FROM data" in q else (True, ""),
        ):
            with tempfile.TemporaryDirectory() as tmpdir:
                with pytest.raises(ValueError, match="Malformed data query"):
                    list(loader.export_subset_to_csv(tmpdir))

    def test_invalid_experiment_raises_keyerror(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(KeyError, match="Could not find experiment"):
                list(
                    loader.export_subset_to_csv(
                        tmpdir, experiments_and_channels={"nonexistent": [0]}
                    )
                )

    def test_with_experiments_and_channels_and_empty_channel_list(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # exercises the "no channel filter" branch -> "(experiment_id = X)"
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = loader.export_subset_to_csv(
                tmpdir, experiments_and_channels={"exp1": None}
            )
            progress = list(gen)
            assert progress[-1] == 1.0

    def test_with_experiments_and_channels_with_channels(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = loader.export_subset_to_csv(
                tmpdir, experiments_and_channels={"exp1": [0, 1]}
            )
            progress = list(gen)
            assert progress[-1] == 1.0


# ---------------------------------------------------------------------------
# construct_metadata_query - remaining branches
# ---------------------------------------------------------------------------
class TestConstructMetadataQueryBranches:
    def test_forced_join_sublevels_only_condition_on_events_column(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # sublevels columns selected, but the condition references an events
        # column -> forces the join via the "elif sublevels_columns and not
        # events_columns" branch, and the "else" (sublevels) arm inside the
        # forced-join builder.
        query, debug, table = loader.construct_metadata_query(
            ["sublevel_duration"], conditions="dwell_time > 5"
        )
        assert debug == ""
        assert query != ""
        assert "JOIN" in query
        assert table == "sublevels"

    def test_experiments_and_channels_with_empty_channel_list(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time"], experiments_and_channels={"exp1": None}
        )
        assert debug == ""
        assert "experiment_id = 1)" in query

    def test_sublevels_and_experiments_columns_only(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            ["sublevel_duration", "name"]
        )
        assert debug == ""
        assert query != ""
        assert "JOIN experiments" in query
        assert table == "sublevels"

    def test_events_sublevels_and_experiments_columns(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            ["dwell_time", "sublevel_duration", "name"]
        )
        assert debug == ""
        assert query != ""
        assert "JOIN sublevels" in query
        assert "JOIN experiments" in query
        assert table == "sublevels"

    def test_no_valid_table_columns_raises(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # Force get_table_by_column to report a table outside the
        # events/sublevels/experiments trio so none of the column buckets are
        # populated, triggering the final "else" branch.
        with patch.object(loader, "get_table_by_column", return_value="channels"):
            with pytest.raises(ValueError, match="No valid table columns specified"):
                loader.construct_metadata_query(["samplerate"])

    def test_final_query_validation_failure_returns_debug(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader, "validate_filter_query", return_value=(False, "bad query")
        ):
            query, debug, table = loader.construct_metadata_query(["dwell_time"])
            assert query == ""
            assert debug != ""
            assert table == "events"


# ---------------------------------------------------------------------------
# construct_event_data_query - remaining branches
# ---------------------------------------------------------------------------
class TestConstructEventDataQueryBranches:
    def test_empty_channel_list_branch(self, loader: ConcreteDatabaseLoader) -> None:
        query, debug = loader.construct_event_data_query(
            experiments_and_channels={"exp1": None}
        )
        assert debug == ""
        assert "(e.experiment_id = 1)" in query

    def test_tuple_builder_raises_on_all_none_channels(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with pytest.raises(ValueError, match="only None values"):
            loader.construct_event_data_query(experiments_and_channels={"exp1": [None]})

    def test_final_query_validation_failure_returns_debug(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader, "validate_filter_query", return_value=(False, "bad query")
        ):
            query, debug = loader.construct_event_data_query()
            assert query == ""
            assert debug != ""


# ---------------------------------------------------------------------------
# load_metadata_raw
# ---------------------------------------------------------------------------
class TestLoadMetadataRaw:
    def test_no_conditions_uses_default_query(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        df = loader.load_metadata_raw()
        assert df is not None
        assert isinstance(df, pd.DataFrame)

    def test_with_conditions_runs_raw_query(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        df = loader.load_metadata_raw("SELECT * FROM channels")
        assert df is not None
        assert isinstance(df, pd.DataFrame)


# ---------------------------------------------------------------------------
# load_event_data - malformed query branch
# ---------------------------------------------------------------------------
class TestLoadEventDataMalformed:
    def test_malformed_query_logs_warning_and_yields_nothing(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(
            loader, "validate_filter_query", return_value=(False, "bad query")
        ):
            events = list(loader.load_event_data())
            assert events == []


# ---------------------------------------------------------------------------
# query_database_directly_and_get_generator - generator-is-None branch
# ---------------------------------------------------------------------------
class TestQueryGeneratorNoneBranch:
    def test_none_generator_logs_warning_and_yields_nothing(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with patch.object(loader, "_load_metadata_generator", return_value=None):
            rows = list(
                loader.query_database_directly_and_get_generator("SELECT * FROM events")
            )
            assert rows == []


# ---------------------------------------------------------------------------
# get_empty_settings - base class default implementation (the concrete
# loader overrides this for other tests, so invoke the base version
# explicitly here).
# ---------------------------------------------------------------------------
class TestGetEmptySettingsBase:
    def test_base_impl_default(self, loader: ConcreteDatabaseLoader) -> None:
        settings = MetaDatabaseLoader.get_empty_settings(loader)
        assert settings == {"Input File": {"Type": str, "Options": ["All Files (*.*)"]}}


# ---------------------------------------------------------------------------
# tuple_builder "only None values" branches reachable via a channel list
# containing solely None entries (the channel list is truthy - i.e. non
# -empty - so the tuple_builder helper actually gets invoked, but every
# entry is filtered out as None).
# ---------------------------------------------------------------------------
class TestTupleBuilderOnlyNoneBranches:
    def test_export_subset_to_csv_channel_list_all_none(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="only None values"):
                list(
                    loader.export_subset_to_csv(
                        tmpdir, experiments_and_channels={"exp1": [None]}
                    )
                )

    def test_construct_metadata_query_channel_list_all_none(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        with pytest.raises(ValueError, match="only None values"):
            loader.construct_metadata_query(
                ["dwell_time"], experiments_and_channels={"exp1": [None]}
            )


# ---------------------------------------------------------------------------
# Condition qualification. The fixture registers dwell_time/amplitude/area to
# events, sublevel_duration/sublevel_amplitude to sublevels and name/date to
# experiments, mirroring how the real "columns" table maps a metric to the one
# table that owns it.
# ---------------------------------------------------------------------------
class TestConditionQualification:
    def test_literal_matching_a_column_name_is_not_rewritten(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # A quoted value is data, not a column reference. Rewriting it produced
        # valid SQL that quietly matched nothing.
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="name = 'sublevel_duration'"
        )
        assert debug == ""
        assert "'sublevel_duration'" in query
        assert "'s.sublevel_duration'" not in query

    def test_doubled_quote_escape_inside_a_literal_survives(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="name = 'it''s sublevel_duration'"
        )
        assert debug == ""
        assert "'it''s sublevel_duration'" in query

    def test_column_name_only_inside_a_literal_does_not_force_a_join(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # The join-detection scan reads the same way the qualifier does, so a
        # sublevels column that appears only as a value does not drag the
        # sublevels table into the query.
        query, debug, table = loader.construct_metadata_query(
            ["amplitude"], conditions="name = 'sublevel_duration'"
        )
        assert debug == ""
        assert "JOIN sublevels" not in query
        assert table == "events"

    def test_experiments_column_in_a_condition_forces_the_join(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            ["amplitude"], conditions="date > 50"
        )
        assert debug == ""
        assert "JOIN experiments exp" in query
        assert "exp.date > 50" in query
        assert table == "events"

    def test_experiments_column_condition_on_a_sublevels_plot_forces_the_join(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            ["sublevel_duration"], conditions="date > 50"
        )
        assert debug == ""
        assert "JOIN experiments exp" in query
        assert "ON exp.id = s.experiment_id" in query
        assert "exp.date > 50" in query
        assert table == "sublevels"

    def test_shared_identity_column_is_qualified_in_a_forced_join(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100 AND experiment_id = 2"
        )
        assert debug == ""
        assert "e.experiment_id = 2" in query

    def test_shared_identity_column_is_qualified_when_both_tables_are_selected(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # This shape used to pass the condition through unqualified into
        # "FROM events e JOIN sublevels s", where a bare experiment_id is
        # ambiguous to SQLite.
        query, debug, table = loader.construct_metadata_query(
            ["amplitude", "sublevel_duration"], conditions="experiment_id = 2"
        )
        assert debug == ""
        assert "e.experiment_id = 2" in query
        assert table == "sublevels"

    def test_events_condition_on_a_sublevels_and_experiments_plot_joins_events(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # Selecting sublevels+experiments columns and filtering on an events
        # column used to produce a query with no events table at all.
        query, debug, table = loader.construct_metadata_query(
            ["sublevel_duration", "date"], conditions="amplitude > 5"
        )
        assert debug == ""
        assert "JOIN events e" in query
        assert "e.amplitude > 5" in query
        assert table == "sublevels"

    def test_an_already_qualified_reference_is_left_alone(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="s.sublevel_duration < 100 AND e.amplitude > 5"
        )
        assert debug == ""
        assert "s.s.sublevel_duration" not in query
        assert "e.e.amplitude" not in query

    def test_single_table_query_leaves_identity_columns_bare(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # Nothing to disambiguate against, so no qualifier is added.
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="experiment_id = 2"
        )
        assert debug == ""
        assert "JOIN" not in query
        assert "WHERE experiment_id = 2" in query

    def test_event_data_query_qualifies_conditions(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # Its subquery always joins all three tables, so the same filter text has
        # to be qualified there too.
        query, debug = loader.construct_event_data_query(
            conditions="sublevel_duration < 100 AND experiment_id = 2"
        )
        assert debug == ""
        assert "s.sublevel_duration < 100" in query
        assert "e.experiment_id = 2" in query


# ---------------------------------------------------------------------------
# A bare "id" is the one reference the qualifier will not resolve: it is the
# events row id in one table and the sublevels row id in another, so guessing
# would silently filter against the wrong thing.
# ---------------------------------------------------------------------------
class TestAmbiguousIdRejection:
    def test_bare_id_in_a_joined_query_is_rejected_with_guidance(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100 AND id = 5"
        )
        assert query == ""
        assert '"e.id"' in debug
        assert '"s.id"' in debug

    def test_guidance_names_only_the_tables_that_query_joins(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        _, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100 AND id = 5"
        )
        assert '"exp.id"' not in debug

    def test_bare_id_is_allowed_when_only_one_table_is_queried(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="id = 5"
        )
        assert debug == ""
        assert "WHERE id = 5" in query

    def test_qualified_id_in_a_joined_query_is_accepted(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100 AND e.id = 5"
        )
        assert debug == ""
        assert "e.id = 5" in query

    def test_id_inside_a_string_literal_is_not_a_reference(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100 AND name = 'id'"
        )
        assert debug == ""
        assert "'id'" in query

    def test_bare_id_in_event_data_query_is_rejected_with_guidance(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        query, debug = loader.construct_event_data_query(conditions="id = 5")
        assert query == ""
        assert '"exp.id"' in debug


# ---------------------------------------------------------------------------
# Callers write derived columns back with UPDATE <table_name> ... WHERE id = ?
# (ClusteringView.commit_cluster_data), so the returned id column has to belong
# to the returned table name in every query shape.
# ---------------------------------------------------------------------------
class TestQueryShapeInvariants:
    @pytest.mark.parametrize(
        "columns, conditions, expected_table",
        [
            (["amplitude"], None, "events"),
            (["sublevel_duration"], None, "sublevels"),
            (["amplitude", "sublevel_duration"], None, "sublevels"),
            (["amplitude", "date"], None, "events"),
            (["sublevel_duration", "date"], None, "sublevels"),
            (["amplitude", "sublevel_duration", "date"], None, "sublevels"),
            (["date"], None, "events"),
            (["amplitude"], "sublevel_duration < 100", "events"),
            (["sublevel_duration"], "amplitude > 5", "sublevels"),
            (["amplitude"], "date > 50", "events"),
        ],
    )
    def test_returned_id_column_belongs_to_the_returned_table(
        self,
        loader: ConcreteDatabaseLoader,
        columns: List[str],
        conditions: Optional[str],
        expected_table: str,
    ) -> None:
        query, debug, table = loader.construct_metadata_query(
            columns, conditions=conditions
        )
        assert debug == ""
        assert table == expected_table
        alias = "e" if table == "events" else "s"
        assert query.split(",")[0].endswith(f"{alias}.id")

    def test_distinct_only_when_sublevels_is_joined_purely_to_filter(
        self, loader: ConcreteDatabaseLoader
    ) -> None:
        # An events plot filtered by a sublevels column repeats each event once
        # per sublevel and has to collapse them.
        filtered, _, _ = loader.construct_metadata_query(
            ["amplitude"], conditions="sublevel_duration < 100"
        )
        assert "SELECT DISTINCT" in filtered

        # Selecting a sublevels column means sublevel grain is what was asked
        # for, so the rows are not duplicates.
        plotted, _, _ = loader.construct_metadata_query(
            ["amplitude", "sublevel_duration"]
        )
        assert "SELECT DISTINCT" not in plotted


# ---------------------------------------------------------------------------
# The assertions above check the SQL that comes out. These check that it runs
# and selects the right rows, against a database carrying the schema
# SQLiteDBWriter actually creates. A shape assertion cannot catch a query that
# names a table the FROM clause never joined, which is what "exp.voltage"
# against "FROM events e JOIN sublevels s" used to be.
# ---------------------------------------------------------------------------
PRODUCTION_SCHEMA = """
CREATE TABLE experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    voltage REAL NOT NULL, thickness REAL NOT NULL, conductivity REAL NOT NULL);
CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL, samplerate REAL NOT NULL);
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
    channel_db_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL, start_time REAL NOT NULL,
    num_sublevels INTEGER NOT NULL, duration REAL, sequence TEXT);
CREATE TABLE sublevels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
    channel_db_id INTEGER NOT NULL, event_db_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL, event_id INTEGER NOT NULL,
    level_id INTEGER NOT NULL, levels_left INTEGER NOT NULL,
    sublevel_duration REAL);
CREATE TABLE data (
    id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id INTEGER NOT NULL,
    channel_db_id INTEGER NOT NULL, event_db_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL, event_id INTEGER NOT NULL,
    data_format TEXT NOT NULL, filtered_data BLOB NOT NULL,
    raw_data BLOB NOT NULL, fit_data BLOB NOT NULL);
CREATE TABLE columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
    table_name TEXT NOT NULL, units TEXT);

INSERT INTO columns (name, table_name, units) VALUES
    ('duration', 'events', 'us'),
    ('sequence', 'events', NULL),
    ('sublevel_duration', 'sublevels', 'us'),
    ('voltage', 'experiments', 'mV'),
    ('thickness', 'experiments', 'nm'),
    ('conductivity', 'experiments', 'S/m');

INSERT INTO experiments (name, voltage, thickness, conductivity)
    VALUES ('lo', 40, 10, 1.0), ('hi', 100, 10, 1.0);
INSERT INTO channels (experiment_id, channel_id, samplerate)
    VALUES (1, 0, 1e6), (2, 0, 1e6);

-- Experiment 1 is at 40 mV and holds a short event and a long one; experiment 2
-- is at 100 mV and holds a long one. Each event has a short leading sublevel and
-- a long trailing one, so events and sublevels select different row counts.
INSERT INTO events
    (experiment_id, channel_db_id, channel_id, event_id, start_time,
     num_sublevels, duration, sequence)
    VALUES (1, 1, 0, 0, 0.0, 2, 50.0, 'duration'),
           (1, 1, 0, 1, 1.0, 2, 500.0, 'ACGT'),
           (2, 2, 0, 0, 2.0, 2, 500.0, 'sublevel_duration');
INSERT INTO sublevels
    (experiment_id, channel_db_id, event_db_id, channel_id, event_id,
     level_id, levels_left, sublevel_duration)
    VALUES (1, 1, 1, 0, 0, 0, 1, 10.0), (1, 1, 1, 0, 0, 1, 0, 40.0),
           (1, 1, 2, 0, 1, 0, 1, 10.0), (1, 1, 2, 0, 1, 1, 0, 490.0),
           (2, 2, 3, 0, 0, 0, 1, 10.0), (2, 2, 3, 0, 0, 1, 0, 490.0);
"""


class ProductionSchemaLoader(ConcreteDatabaseLoader):
    """A loader whose column lookups come from a real database."""

    def __init__(self, connection: sqlite3.Connection):
        """
        Bind the loader to an open connection.

        :param connection: An open connection to a production-schema database.
        :type connection: sqlite3.Connection
        """
        self.connection = connection
        super().__init__(settings={"Input File": {"Type": str, "Value": ":memory:"}})

    def get_column_names_by_table(
        self, table: Optional[str] = None
    ) -> Optional[List[str]]:
        query = "SELECT name FROM columns"
        params: Tuple[str, ...] = ()
        if table is not None:
            query += " WHERE table_name = ?"
            params = (table,)
        return [row[0] for row in self.connection.execute(query, params)] or None

    def get_table_by_column(self, column: str) -> Optional[str]:
        row = self.connection.execute(
            "SELECT table_name FROM columns WHERE name = ?", (column,)
        ).fetchone()
        return row[0] if row else None

    def get_experiment_id_by_name(self, experiment_name: str) -> Optional[int]:
        row = self.connection.execute(
            "SELECT id FROM experiments WHERE name = ?", (experiment_name,)
        ).fetchone()
        return row[0] if row else None

    def validate_filter_query(self, query: str) -> Tuple[bool, str]:
        try:
            self.connection.execute("EXPLAIN " + query)
        except sqlite3.Error as exc:
            return False, f"{exc}\n{query}"
        return True, ""


@pytest.fixture
def real_db_loader() -> Generator[ProductionSchemaLoader, None, None]:
    """
    Build a loader over an in-memory database carrying the production schema.

    :return: A loader whose generated queries can actually be executed.
    :rtype: Generator[ProductionSchemaLoader, None, None]
    """
    connection = sqlite3.connect(":memory:")
    connection.executescript(PRODUCTION_SCHEMA)
    connection.commit()
    try:
        yield ProductionSchemaLoader(connection)
    finally:
        connection.close()


class TestGeneratedQueriesExecute:
    def test_filter_on_an_experiment_property_selects_matching_events(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        query, debug, table = real_db_loader.construct_metadata_query(
            ["duration"], conditions="voltage > 50"
        )
        assert debug == ""
        assert table == "events"
        rows = real_db_loader.connection.execute(query).fetchall()
        assert sorted(row[0] for row in rows) == [3]

    def test_filter_on_an_experiment_property_selects_matching_sublevels(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        query, debug, table = real_db_loader.construct_metadata_query(
            ["sublevel_duration"], conditions="voltage > 50"
        )
        assert debug == ""
        assert table == "sublevels"
        rows = real_db_loader.connection.execute(query).fetchall()
        assert sorted(row[0] for row in rows) == [5, 6]

    def test_experiment_and_sublevel_filters_combine(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        query, debug, _ = real_db_loader.construct_metadata_query(
            ["duration"], conditions="sublevel_duration > 400 AND voltage > 50"
        )
        assert debug == ""
        rows = real_db_loader.connection.execute(query).fetchall()
        assert sorted(row[0] for row in rows) == [3]

    def test_literal_matching_a_column_name_matches_by_value(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        # Event 3's sequence is the literal text "sublevel_duration". Rewriting
        # the value as a column reference used to return no rows at all.
        query, debug, _ = real_db_loader.construct_metadata_query(
            ["duration"], conditions="sequence = 'sublevel_duration'"
        )
        assert debug == ""
        rows = real_db_loader.connection.execute(query).fetchall()
        assert sorted(row[0] for row in rows) == [3]

    def test_shared_identity_filter_runs_when_both_tables_are_selected(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        query, debug, table = real_db_loader.construct_metadata_query(
            ["duration", "sublevel_duration"], conditions="experiment_id = 2"
        )
        assert debug == ""
        assert table == "sublevels"
        rows = real_db_loader.connection.execute(query).fetchall()
        assert sorted(row[0] for row in rows) == [5, 6]

    def test_event_data_query_runs_with_an_experiment_property_filter(
        self, real_db_loader: ProductionSchemaLoader
    ) -> None:
        query, debug = real_db_loader.construct_event_data_query(
            conditions="voltage > 50"
        )
        assert debug == ""
        # The data table is not populated here, so the point is that the query
        # is accepted by SQLite and its event subquery resolves.
        real_db_loader.connection.execute("EXPLAIN " + query)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
