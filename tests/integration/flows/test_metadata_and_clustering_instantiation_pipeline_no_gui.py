from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.mark.fast
@pytest.mark.integration
@pytest.mark.timeout(60)
def test_metadata_and_clustering_instantiation_pipeline_no_gui(sample_metadata_db: str):
    """
    Integration (no GUI): verify a prebuilt metadata DB loads via SQLiteDBLoader and is structurally sound.

    Steps
    -----
    1) Instantiate SQLiteDBLoader (standalone=True) and point to tests/integration/data/DB.db.
    2) Smoke-call a lightweight method on the loader.
    3) Run PRAGMA integrity checks and validate expected schema tables exist.
    4) Assert basic content exists (e.g., ≥1 channel row).
    """
    # Import the real loader class
    from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader

    db_path = Path(sample_metadata_db)
    assert db_path.exists(), f"Missing DB file at {db_path}"

    # 1) Instantiate + apply settings
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    assert (
        "Input File" in settings
    ), "SQLiteDBLoader should expose an 'Input File' setting"
    settings["Input File"]["Value"] = str(db_path)
    loader.apply_settings(settings)

    # 2) Simple smoke call (ensure no exception)
    _ = loader.report_channel_status(init=True)

    # Use MetaDatabaseLoader-style API: experiments -> channels per experiment
    experiments = loader.get_experiment_names()
    assert (
        isinstance(experiments, list) and len(experiments) >= 1
    ), "No experiments found via loader"

    first_exp = experiments[0]
    channels = loader.get_channels_by_experiment(first_exp)
    assert (
        isinstance(channels, list) and len(channels) >= 1
    ), f"No channels for experiment {first_exp}"

    # 3) Integrity + schema checks
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()

        # PRAGMA integrity check
        ok = cur.execute("PRAGMA integrity_check;").fetchone()
        assert ok and ok[0] == "ok", f"SQLite integrity_check failed: {ok}"

        # Gather tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        assert tables, "Metadata DB appears to contain no tables"

        # Expected minimum from SQLiteDBWriter schema
        expected_tables = {
            "experiments",
            "channels",
            "events",
            "sublevels",
            "data",
            "columns",
        }
        assert expected_tables.issubset(
            tables
        ), f"Missing tables: {expected_tables - tables}"

        # 4) Basic content checks
        n_channels = cur.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        assert n_channels >= 1, "No rows in channels table"

        n_columns = cur.execute("SELECT COUNT(*) FROM columns").fetchone()[0]
        assert n_columns >= 1, "No rows in columns table"

        # Soft check: experiments table has at least one experiment
        n_experiments = cur.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        assert n_experiments >= 1, "No experiments recorded"
