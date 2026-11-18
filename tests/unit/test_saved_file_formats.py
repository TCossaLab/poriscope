"""
The format numbers of the files Poriscope saves change only with the major version.

A saved file follows the release's version discipline (``DECISIONS.md``, 2026-11-18):
only a major release may stop reading a file, or write one an earlier release of the
same major cannot read. So a format number is fixed for the life of a major, a change
to a saved file within a major is additive, and every reader of that major ignores what
it does not know.

This file is the gate on the first half. ``FORMAT_NUMBERS_BY_MAJOR`` records the numbers
each major writes; the release being prepared is read from the changelog's first header,
which names it while it is in progress, before ``poriscope/constants.py`` is bumped.

**If this fails because you changed a format number:** the change is breaking, so the
release you are preparing must be a major one. Do not edit the row of a major that has
shipped. Add a row for the new major, say so under Breaking Changes, "Saved files", and
decide what the new reader does with a file in the older format.
"""

import re
from pathlib import Path
from typing import Dict

import pytest

from poriscope.models.main_model import SESSION_FORMAT_VERSION
from poriscope.plugins.datawriters.SQLiteEventWriter import SQLiteEventWriter
from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.plugins.dbwriters.SQLiteDBWriter import SQLiteDBWriter
from poriscope.plugins.eventloaders.SQLiteEventLoader import SQLiteEventLoader
from poriscope.utils.MetaModel import PLOT_CONFIGURATION_FORMAT_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.characterization

#: What each major version writes. A row is added when a major is prepared and is never
#: edited once that major has shipped.
FORMAT_NUMBERS_BY_MAJOR: Dict[int, Dict[str, int]] = {
    3: {
        "session": 2,
        "plot configuration": 1,
        "metadata database": 1,
        "events database": 1,
    },
}


def release_major() -> int:
    """
    The major version of the release this tree belongs to, from the changelog.

    :raises AssertionError: if the changelog does not open with a release header
    :return: the major version number
    :rtype: int
    """
    changelog = Path(REPO_ROOT, "changelog.md").read_text(encoding="utf-8")
    header = re.search(r"^## Poriscope (\d+)\.\d+", changelog, flags=re.MULTILINE)
    assert header is not None, "changelog.md does not open with '## Poriscope X.Y'"
    return int(header.group(1))


def test_a_format_number_changes_only_with_the_major_version() -> None:
    """The numbers this tree writes are the ones recorded for its major."""
    major = release_major()
    assert major in FORMAT_NUMBERS_BY_MAJOR, (
        f"Poriscope {major} has no row in FORMAT_NUMBERS_BY_MAJOR: add one when "
        "preparing a major release, with the format numbers it writes"
    )

    assert {
        "session": SESSION_FORMAT_VERSION,
        "plot configuration": PLOT_CONFIGURATION_FORMAT_VERSION,
        "metadata database": SQLiteDBWriter.SCHEMA_VERSION,
        "events database": SQLiteEventWriter.SCHEMA_VERSION,
    } == FORMAT_NUMBERS_BY_MAJOR[major]


def test_each_database_loader_reads_up_to_the_version_its_writer_stamps() -> None:
    """A writer and its loader move together, or a file this version writes is refused."""
    assert SQLiteDBLoader.SCHEMA_VERSION == SQLiteDBWriter.SCHEMA_VERSION
    assert SQLiteEventLoader.SCHEMA_VERSION == SQLiteEventWriter.SCHEMA_VERSION
