from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


@pytest.mark.fast
@pytest.mark.integration
@pytest.mark.timeout(90)
def test_raw_data_pipeline_instantiation_no_gui(sample_chimera, tmp_path):
    """
    Integration test (no GUI) for the *raw data* instantiation pipeline:
    (Specifically for 2kbp_n200mV_HS3_20240604_122657.log in tests/integration/data/)

      ChimeraReader20240501  ->  BesselFilter  ->  ClassicBlockageFinder  ->  SQLiteEventWriter

    Pass criteria:
      - All plugins instantiate and apply settings without error,
      - Filter settings are applied as configured,
      - Event finding completes (generators consumed) *without* applying the filter,
      - Finder status reports the expected event counts / rejections,
      - Writer status reports the expected write counts,
      - Output SQLite DB passes integrity and has expected tables/rows.
    """
    # Real plugins
    from poriscope.plugins.datareaders.ChimeraReader20240501 import (
        ChimeraReader20240501,
    )
    from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
    from poriscope.plugins.eventfinders.ClassicBlockageFinder import (
        ClassicBlockageFinder,
    )
    from poriscope.plugins.filters.BesselFilter import BesselFilter

    # ----- 1) Reader: point only to the .log (Chimera reader will discover its .json)
    reader = ChimeraReader20240501()
    reader_settings = reader.get_empty_settings(standalone=True)
    reader_settings["Input File"]["Value"] = sample_chimera["log"]
    reader.apply_settings(reader_settings)

    _ = reader.report_channel_status(init=True)

    # Sample rate (used only to configure the filter's settings)
    try:
        fs = float(reader.get_samplerate())
    except Exception:
        fs = 5_000_000.0  # fallback if needed

    # ----- 2) Bessel filter with safe parameters (apply + verify settings)
    bfilter = BesselFilter()
    fset = bfilter.get_empty_settings()
    fset["Poles"]["Value"] = 2
    fset["Cutoff"]["Value"] = 200_000.0  # stable cutoff (example safe value)
    if "Samplerate" in fset:
        fset["Samplerate"]["Value"] = fs
    bfilter.apply_settings(fset)

    # Verify filter settings stuck
    assert bfilter.settings["Poles"]["Value"] == 2
    assert float(bfilter.settings["Cutoff"]["Value"]) == pytest.approx(
        200_000.0, rel=0, abs=1e-6
    )
    if "Samplerate" in bfilter.settings:
        assert float(bfilter.settings["Samplerate"]["Value"]) == pytest.approx(
            fs, rel=0, abs=1e-6
        )

    # ----- 3) Event finder (point directly to the reader instance)
    finder = ClassicBlockageFinder()
    finderset = finder.get_empty_settings(standalone=True)
    if "MetaReader" in finderset:
        finderset["MetaReader"]["Value"] = reader
    # Dataset-tuned values you mentioned
    if "Threshold" in finderset:
        finderset["Threshold"]["Value"] = 2000.0  # pA
    if "Min Duration" in finderset:
        finderset["Min Duration"]["Value"] = 1.0  # µs
    if "Max Duration" in finderset:
        finderset["Max Duration"]["Value"] = 1_000_000.0  # µs
    if "Min Separation" in finderset:
        finderset["Min Separation"]["Value"] = 1.0  # µs
    finder.apply_settings(finderset)

    # Channels discovered by the finder
    channels = finder.get_channels()
    assert isinstance(channels, (list, tuple)) and len(channels) >= 1
    # Your dataset is expected to use channel 3 (HS3 → ch 3)
    assert 3 in channels, f"Expected channel 3 in dataset; got {channels}"

    # ----- 4) Run event finding WITHOUT applying the Bessel filter (identity function)
    # Use a no-op "filter" so the event finder runs on unfiltered data.
    # This helps verify the pipeline wiring independently of the Bessel filter.
    def identity(x):
        return x

    # Process the raw data in ~3-second chunks. The finder will load data in
    # these increments per channel and yield progress until it finishes.
    chunk_len_sec = 3.0

    for ch in channels:
        # Ask the finder to scan the *entire* channel: [(0.0, 0.0)] means
        # "from start to end". We pass the identity function so no filtering
        # is applied to the data before detection.
        gen = finder.find_events(ch, [(0.0, 0.0)], chunk_len_sec, identity)

        # Drive the generator to completion (consume all yielded progress values).
        # We don't assert on the number of events here—datasets can legitimately
        # have zero events—this just ensures the detection loop runs without error.
        for _ in gen:
            pass

    # Assert expected finder status details for Ch3
    fstatus = finder.report_channel_status()
    # Look for the specific lines you asked about
    assert (
        "Ch3: Found 9 events" in fstatus
    ), f"Finder status didn't match expectation:\n{fstatus}"
    assert (
        "Rejected Events:" in fstatus
    ), f"Finder status missing rejection header:\n{fstatus}"
    assert (
        "Too Short: 8" in fstatus
    ), f"Finder status missing 'Too Short: 8':\n{fstatus}"

    # ----- 5) Write events to SQLite
    out_db: Path = tmp_path / "events.sqlite"
    writer = SQLiteEventWriter()
    writer_settings = writer.get_empty_settings(standalone=True)
    writer_settings["MetaEventFinder"]["Value"] = finder
    writer_settings["Experiment Name"]["Value"] = "chimera_integration_test"
    writer_settings["Voltage"]["Value"] = 200.0
    writer_settings["Membrane Thickness"]["Value"] = 10.0
    writer_settings["Conductivity"]["Value"] = 1.0
    writer_settings["Output File"]["Value"] = str(out_db)
    writer.apply_settings(writer_settings)

    # Commit per channel (consume generators)
    for ch in channels:
        genw = writer.commit_events(ch)
        for _ in genw:
            pass

    # Check writer status for Ch3 write counts
    wstatus = writer.report_channel_status()
    assert (
        "Ch3: Wrote 9/9 events" in wstatus
    ), f"Writer status didn't match expectation:\n{wstatus}"
    # It's fine if no explicit rejection counts follow; we just ensure the header exists
    assert (
        "Rejected Events" in wstatus
    ), f"Writer status missing 'Rejected Events' header:\n{wstatus}"

    # ----- 6) Sanity-check the output DB
    assert out_db.exists() and out_db.stat().st_size > 0

    with sqlite3.connect(str(out_db)) as conn:
        cur = conn.cursor()

        # Integrity check
        (ok_msg,) = cur.execute("PRAGMA integrity_check;").fetchone()
        assert ok_msg == "ok", f"SQLite integrity_check failed: {ok_msg}"

        # Tables present (SQLiteEventWriter schema minimum)
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        assert {"channels", "events", "columns"}.issubset(
            tables
        ), f"Unexpected tables: {tables}"

        # At least one channel row should exist
        (n_channels,) = cur.execute("SELECT COUNT(*) FROM channels").fetchone()
        assert n_channels >= 1, "No rows in channels table"

        # Columns table should have entries (writer seeds units/columns)
        (n_columns_rows,) = cur.execute("SELECT COUNT(*) FROM columns").fetchone()
        assert n_columns_rows >= 1, "No rows in columns table"
