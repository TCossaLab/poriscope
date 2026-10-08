"""
The scripting guide's own code, run end to end as a script.

``docs/source/utils/user_manuals/user_guide/scripting.rst`` walks through every data
plugin family without the GUI: read, filter, find, write events, load them, fit, write
metadata, load metadata. This takes every ``.. code:: python`` block from the guide, in
order, fills in the paths the guide leaves for the reader, and runs the result in a
fresh interpreter on a synthetic ABF recording - so the guide's text, values included,
is what is tested, and an edit that breaks it breaks this. The blocks under "Debug
logging, one plugin at a time" are left out: they only show how to raise log levels,
and would turn on DEBUG output for the whole run.

The run happens in a subprocess because the guide configures the root logger, which
would otherwise leak into every test after this one.

It also checks what only a script exercises: plugins made without the GUI have keys, and
the metadata database's provenance names them, so the chain from metadata writer to
fitter to event loader can be followed.
"""

import json
import re
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import List

from tests.synthetic_data.synthetic_abf2 import (
    Abf2RecordingConfig,
    generate_abf2_modern_dataset,
)

GUIDE = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "source"
    / "utils"
    / "user_manuals"
    / "user_guide"
    / "scripting.rst"
)
NUM_EVENTS = 5


def guide_blocks() -> List[str]:
    """
    The guide's Python code blocks, in order, without the debug-logging examples.

    :return: each block's code, dedented
    :rtype: List[str]
    """
    text = GUIDE.read_text(encoding="utf-8")
    start = text.index("Debug logging, one plugin at a time")
    end = text.index("Loading raw data")
    text = text[:start] + text[end:]
    blocks = re.findall(r"^\.\. code:: python\n\n((?:(?: {4}.*)?\n)+)", text, re.M)
    return [textwrap.dedent(block) for block in blocks]


def metadata_rows(path: Path, query: str) -> List[tuple]:
    """
    :param path: the metadata database
    :type path: Path
    :param query: the query to run
    :type query: str
    :return: its rows
    :rtype: List[tuple]
    """
    connection = sqlite3.connect(str(path))
    try:
        return connection.execute(query).fetchall()
    finally:
        connection.close()


def test_the_scripting_guide_runs_from_raw_data_to_loaded_metadata(
    tmp_path: Path,
) -> None:
    recording = generate_abf2_modern_dataset(
        tmp_path / "raw",
        Abf2RecordingConfig(
            samplerate=1_000_000.0,
            duration_s=0.5,
            baseline=2000.0,
            noise_std=15.0,
            event_amplitude=-1500.0,
            event_duration_s=0.0005,
        ),
        num_events=NUM_EVENTS,
    )
    events_db = (tmp_path / "events.sqlite3").as_posix()
    metadata_db = tmp_path / "metadata.sqlite3"
    script = "\n".join(guide_blocks())
    for placeholder, path in {
        "<<Path to your ABF input file>>": Path(recording.data_path).as_posix(),
        "<<Your output file path>>/<<your database name>>.sqlite3": events_db,
        "<<your output path>>/<<your database name>>.sqlite3": metadata_db.as_posix(),
    }.items():
        assert placeholder in script, f"the guide no longer has {placeholder}"
        script = script.replace(placeholder, path)
    script_path = tmp_path / "guide.py"
    script_path.write_text(script, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Found {NUM_EVENTS} events" in result.stdout
    assert metadata_rows(metadata_db, "SELECT name FROM experiments") == [
        ("script_demo",)
    ]
    assert metadata_rows(metadata_db, "SELECT COUNT(*) FROM events") == [(NUM_EVENTS,)]
    ((stored,),) = metadata_rows(metadata_db, "SELECT provenance FROM channels")
    provenance = json.loads(stored)
    keys = [provenance[role]["key"] for role in ("writer", "fitter", "event_loader")]
    assert all(keys) and len(set(keys)) == 3
    assert provenance["writer"]["settings"]["MetaEventFitter"] == keys[1]
    assert provenance["fitter"]["settings"]["MetaEventLoader"] == keys[2]
