"""
The shared metadata database fixture: built once for the run, copied for each test.

A test that writes to its database (a clustering commit adds columns) must not change
what the next test is handed, so each test's copy has to be its own file, holding the
same database as the one built for the run.
"""

import sqlite3
from pathlib import Path

import pytest


def _tables(path: str) -> list:
    connection = sqlite3.connect(path)
    try:
        return sorted(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        )
    finally:
        connection.close()


@pytest.mark.timeout(60)
def test_a_test_gets_its_own_copy_of_the_database(
    tmp_path: Path, sample_metadata_db: str, _metadata_db_template: Path
) -> None:
    assert Path(sample_metadata_db).parent == tmp_path
    assert Path(sample_metadata_db) != _metadata_db_template
    assert Path(sample_metadata_db).read_bytes() == _metadata_db_template.read_bytes()


@pytest.mark.timeout(60)
def test_writing_to_a_copy_leaves_the_runs_database_as_it_was(
    sample_metadata_db: str, _metadata_db_template: Path
) -> None:
    before = _metadata_db_template.read_bytes()
    connection = sqlite3.connect(sample_metadata_db)
    try:
        connection.execute("CREATE TABLE written_by_a_test (x)")
        connection.commit()
    finally:
        connection.close()

    assert "written_by_a_test" in _tables(sample_metadata_db)
    assert "written_by_a_test" not in _tables(str(_metadata_db_template))
    assert _metadata_db_template.read_bytes() == before
