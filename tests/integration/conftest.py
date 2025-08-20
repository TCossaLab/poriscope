from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

import pytest

# Headless Qt for anything that might import Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Keep test logs quieter by default; change to INFO for debugging
logging.basicConfig(level=logging.WARNING)

tmp_path = Path(__file__).parent / "tmp"


@pytest.fixture
def sample_chimera(tmp_path):
    """
    Locate a small Chimera .log + matching .json pair under tests/integration/data/,
    copy them into the test's tmp_path, and return their locations.

    """
    data_dir = Path(__file__).parent / "data"  # -> tests/integration/data

    if not data_dir.exists():
        pytest.skip("Missing folder: tests/integration/data/")

    # Find a .log that has a same-stem .json alongside it
    src_log = src_json = None
    for log in sorted(data_dir.glob("*.log")):
        jsn = data_dir / f"{log.stem}.json"
        if jsn.exists():
            src_log, src_json = log, jsn
            break

    if not (src_log and src_json):
        pytest.skip(
            "No matching Chimera pair found in tests/integration/data/ "
            "(need <name>.log and <name>.json with the same stem)"
        )

    # Copy into per-test temp dir
    dst_log = tmp_path / src_log.name
    dst_json = tmp_path / src_json.name
    shutil.copyfile(src_log, dst_log)
    shutil.copyfile(src_json, dst_json)

    return {
        "log": str(dst_log),
        "json": str(dst_json),
        "folder": str(tmp_path),
        "source_dir": str(data_dir),
    }


@pytest.fixture
def sample_events_db(tmp_path) -> str:
    """
    Use a prebuilt events SQLite DB for analysis-only tests.

    Expects a single file at:
      tests/integration/data/events.sqlite

    The file is copied into a temporary directory and that path is returned.
    """
    src = Path("tests/integration/data/events.sqlite3")
    if not src.exists() or not src.is_file():
        pytest.skip("Missing tests/integration/data/events.sqlite3")

    dst = tmp_path / src.name
    shutil.copy2(src, dst)
    return str(dst)


@pytest.fixture
def sample_metadata_db() -> str:
    """
    Return the path to a prebuilt metadata DB used for the analysis phase.
    Expects the file to exist at tests/integration/data/DB.db.
    """
    p = Path("tests/integration/data/DB.db")
    if not p.exists() or not p.is_file():
        pytest.skip("Missing tests/integration/data/DB.db")
    return str(p)
