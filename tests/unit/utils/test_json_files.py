"""
``write_json_atomically``: a failed write leaves the file that was there, and nothing beside it.
"""

import json
import os
from pathlib import Path
from typing import Any, List

import pytest
from pytest_mock import MockerFixture

from poriscope.utils.json_files import REPLACE_ATTEMPTS, write_json_atomically


def test_the_file_reads_back_as_written(tmp_path: Path) -> None:
    path = tmp_path / "saved.json"

    write_json_atomically({"a": [1, 2], "b": "x"}, path)

    assert json.loads(path.read_text()) == {"a": [1, 2], "b": "x"}
    assert not list(tmp_path.glob("*.tmp"))


def test_a_value_that_cannot_be_written_leaves_the_earlier_file(tmp_path: Path) -> None:
    path = tmp_path / "saved.json"
    write_json_atomically({"kept": True}, path)
    before = path.read_text()

    with pytest.raises(TypeError):
        write_json_atomically({"bad": object()}, path)

    assert path.read_text() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_a_rename_refused_briefly_is_retried(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    path = tmp_path / "saved.json"
    real_replace = os.replace
    tries: List[Any] = []

    def refused_twice(src: Any, dst: Any) -> None:
        tries.append(src)
        if len(tries) <= 2:
            raise PermissionError(13, "Access is denied")
        real_replace(src, dst)

    mocker.patch("poriscope.utils.json_files.os.replace", side_effect=refused_twice)
    mocker.patch("poriscope.utils.json_files.time.sleep")

    write_json_atomically({"a": 1}, path)

    assert json.loads(path.read_text()) == {"a": 1}
    assert len(tries) == 3


def test_a_rename_refused_every_time_raises_after_every_attempt(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    path = tmp_path / "saved.json"
    write_json_atomically({"kept": True}, path)
    before = path.read_text()
    replace = mocker.patch(
        "poriscope.utils.json_files.os.replace",
        side_effect=PermissionError(13, "Access is denied"),
    )
    mocker.patch("poriscope.utils.json_files.time.sleep")

    with pytest.raises(PermissionError):
        write_json_atomically({"other": 1}, path)

    assert replace.call_count == REPLACE_ATTEMPTS
    assert path.read_text() == before
    assert not list(tmp_path.glob("*.tmp"))
