"""
``scripts/check_text_encoding.py`` - requirements files are UTF-8 with no BOM.

The gate exists because ``requirements.txt`` was committed as UTF-16LE with a BOM
and stayed that way for over a year: PowerShell's ``>`` redirection and ``Out-File``
default to that encoding, so ``pip freeze > requirements.txt`` reproduces it, and git
treats every revision of such a file as a binary blob.

The case that matters most is the one the stock hook misses. ``pre-commit-hooks``'
``fix-byte-order-marker`` matches the *UTF-8* BOM only, so a UTF-16LE file passes it
untouched; the first two tests below are what would fail if this check were ever
replaced by that hook.

Measured by mutation: cutting the BOM table down to the UTF-8 entry alone - which is
exactly the stock hook's behaviour - fails those two and nothing else. The UTF-16 files
are still *refused*, because ``b"\\xff\\xfe"`` is not valid UTF-8 either, so the two
halves of the check cover that case independently and only the message changes. That
is worth knowing before anyone trims either half.
"""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.characterization

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "check_text_encoding.py"


def run(*paths: Path) -> subprocess.CompletedProcess:
    """
    Run the check over the given files.

    :param paths: the files to check
    :type paths: Path
    :return: the completed process, with stderr captured
    :rtype: subprocess.CompletedProcess
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(p) for p in paths)],
        capture_output=True,
        text=True,
    )


class TestWhatItRefuses:
    """Every encoding a Windows shell produces by accident."""

    def test_utf_16_le_is_refused(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"\xff\xfenumpy\x00")

        result = run(path)

        assert result.returncode == 1
        assert "UTF-16LE byte-order mark" in result.stderr

    def test_utf_16_be_is_refused(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"\xfe\xff\x00n")

        result = run(path)

        assert result.returncode == 1
        assert "UTF-16BE byte-order mark" in result.stderr

    def test_a_utf_8_bom_is_refused(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes("﻿numpy==2.0\n".encode("utf-8"))

        result = run(path)

        assert result.returncode == 1
        assert "UTF-8 byte-order mark" in result.stderr

    def test_bytes_that_are_not_utf_8_are_refused(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"numpy \xe9\n")

        result = run(path)

        assert result.returncode == 1
        assert "not valid UTF-8" in result.stderr

    def test_the_failure_names_the_fix(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"\xff\xfenumpy\x00")

        result = run(path)

        assert "-Encoding utf8" in result.stderr

    def test_one_bad_file_fails_a_whole_run(self, tmp_path):
        good = tmp_path / "requirements-dev.txt"
        good.write_bytes(b"black\n")
        bad = tmp_path / "requirements.txt"
        bad.write_bytes(b"\xff\xfenumpy\x00")

        result = run(good, bad)

        assert result.returncode == 1
        assert "requirements-dev.txt" not in result.stderr


class TestWhatItAccepts:
    """Plain UTF-8, including the non-ASCII a contributor's name can carry."""

    def test_plain_ascii_passes(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"numpy==2.0\npyside6\n")

        assert run(path).returncode == 0

    def test_utf_8_without_a_bom_passes(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes("# Alejandra González\nnumpy\n".encode("utf-8"))

        assert run(path).returncode == 0

    def test_an_empty_file_passes(self, tmp_path):
        path = tmp_path / "requirements.txt"
        path.write_bytes(b"")

        assert run(path).returncode == 0


class TestTheRepositoryItself:
    """The files the hook is scoped to, checked as they stand."""

    def test_the_shipped_requirements_files_are_clean(self):
        root = Path(__file__).resolve().parents[3]
        shipped = sorted(root.glob("requirements*.txt"))

        assert shipped, "no requirements files found to check"
        assert run(*shipped).returncode == 0
