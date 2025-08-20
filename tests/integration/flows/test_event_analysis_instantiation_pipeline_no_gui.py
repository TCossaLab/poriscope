from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import pytest


def _get_settings(obj):
    """Call get_empty_settings with or without standalone=True depending on plugin signature."""
    try:
        return obj.get_empty_settings(standalone=True)
    except TypeError:
        return obj.get_empty_settings()


def _sqlite_tables(path: Path) -> set[str]:
    with sqlite3.connect(str(path)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r[0] for r in cur.fetchall()}


def _assert_db_schema_sqlite_dbwriter(
    db_path: Path,
    expected_channels: Optional[Iterable[int]] = None,
) -> None:
    """Assert the metadata DB produced by SQLiteDBWriter has expected schema/content."""
    assert db_path.exists() and db_path.stat().st_size > 0

    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()

        # integrity check
        ok = cur.execute("PRAGMA integrity_check;").fetchone()
        assert ok and ok[0] == "ok", f"SQLite integrity_check failed: {ok}"

        # schema
        tables = _sqlite_tables(db_path)
        expected = {"experiments", "channels", "events", "sublevels", "data", "columns"}
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

        # content
        (n_channels,) = cur.execute("SELECT COUNT(*) FROM channels").fetchone()
        assert n_channels >= 1, "No rows in channels table"

        (n_cols,) = cur.execute("SELECT COUNT(*) FROM columns").fetchone()
        assert n_cols >= 1, "No rows in columns table"

        # channel id presence matches/contains what we processed
        if expected_channels is not None:
            db_chs = {
                r[0]
                for r in cur.execute(
                    "SELECT DISTINCT channel_id FROM channels"
                ).fetchall()
            }
            missing = set(expected_channels) - db_chs
            assert not missing, f"Expected channel IDs not present in DB: {missing}"


@pytest.mark.fast
@pytest.mark.integration
@pytest.mark.timeout(90)
def test_event_analysis_instantiation_pipeline_no_gui(sample_events_db, tmp_path):
    """
    Integration (no GUI):
    (Specifically for events.sqlite3 in tests/integration/data/)

      SQLiteEventLoader -> CUSUM -> SQLiteDBWriter

    Pass if:
      - Plugins apply settings without error,
      - Fitting generators run to completion for all channels,
      - Output DB exists, passes integrity check, has required schema,
      - DB contains at least one channel row, and includes the processed channel IDs,
      - Text reports contain the exact expected counts.
    """
    from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
    from poriscope.plugins.eventfitters.CUSUM import CUSUM
    from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader

    # ---- Loader
    events_loader = SQLiteEventLoader()
    loader_settings = _get_settings(events_loader)
    key = (
        "Input File"
        if "Input File" in loader_settings
        else next((k for k in loader_settings if "file" in k.lower()), None)
    )
    assert (
        key
    ), f"SQLiteEventLoader settings missing an input file key: {list(loader_settings.keys())}"
    loader_settings[key]["Value"] = sample_events_db
    events_loader.apply_settings(loader_settings)

    _ = events_loader.report_channel_status(init=True)

    # ---- Fitter
    fitter = CUSUM()
    fitter_settings = _get_settings(fitter)
    if "MetaEventLoader" in fitter_settings:
        fitter_settings["MetaEventLoader"]["Value"] = events_loader
    if "Max Sublevels" in fitter_settings:
        fitter_settings["Max Sublevels"]["Value"] = 10
    if "Rise Time" in fitter_settings:
        fitter_settings["Rise Time"]["Value"] = 10.0
    if "Step Size" in fitter_settings:
        fitter_settings["Step Size"]["Value"] = 1000.0
    fitter.apply_settings(fitter_settings)

    # test fitting for multiple channels ? (Current demo only has one channel)
    channels = fitter.get_channels()
    assert isinstance(channels, (list, tuple)) and len(channels) >= 1
    ch0 = min(channels)  # use the first/lowest channel id in the dataset

    # Fit all events on every channel, ignoring intermediate outputs.
    # If anything raises, the test will fail.

    # A no-op filter: returns input unchanged; passed to the fitter as the data_filter.
    def identity(x):
        return x

    # Iterate over each channel returned by the pipeline (e.g., from the loader/fitter).
    for ch in channels:
        # fit_events(...) returns a generator that yields progress or per-event updates.
        # Consuming the generator is what actually runs the fitting.
        for _ in fitter.fit_events(ch, data_filter=identity):
            # We don't use the yielded values here—just drive the generator to completion.
            # Exceptions during fitting will bubble up and fail the test.
            pass

    # exact-number assertions for the fitter report
    fit_report = fitter.report_channel_status()
    assert re.search(
        rf"Ch{ch0}:\s*24/25\s+good fits", fit_report
    ), f"Unexpected CUSUM report:\n{fit_report}"
    assert re.search(
        r"Rejected Events:\s*(?:\n|\r\n)?\s*Too Few Levels:\s*1", fit_report
    ), f"Unexpected CUSUM rejections:\n{fit_report}"

    # ---- Writer
    out_db = tmp_path / "event_metadata.sqlite"
    writer = SQLiteDBWriter()
    writer_settings = _get_settings(writer)
    if "MetaEventFitter" in writer_settings:
        writer_settings["MetaEventFitter"]["Value"] = fitter
    if "Experiment Name" in writer_settings:
        writer_settings["Experiment Name"]["Value"] = "cusum_integration_test"
    for k, v in (
        ("Voltage", 200.0),
        ("Membrane Thickness", 10.0),
        ("Conductivity", 1.0),
    ):
        if k in writer_settings:
            writer_settings[k]["Value"] = float(v)
    if "Output File" in writer_settings:
        writer_settings["Output File"]["Value"] = str(out_db)
    writer.apply_settings(writer_settings)

    for ch in channels:
        for _ in writer.write_events(ch):
            pass

    # schema/content checks
    _assert_db_schema_sqlite_dbwriter(out_db, expected_channels=channels)

    # exact-number assertions for the writer report
    write_report = writer.report_channel_status()
    assert re.search(
        rf"Ch{ch0}:\s*Wrote\s*24/24\s+events", write_report
    ), f"Unexpected writer report:\n{write_report}"
    assert (
        "Rejected Events:" in write_report
    ), f"Missing 'Rejected Events' section:\n{write_report}"
