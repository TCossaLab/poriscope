"""
Tests for ``scripts/check_refactor_coverage.py``, the refactor-coverage audit.

The audit's job is to answer one question: is every method the 2.0.0 refactor moves
or deduplicates pinned by a test? Its value depends entirely on the target list being
complete, so the tests here fall into two groups - the AST helpers, driven against
synthetic input so they pin the rule rather than today's tree, and guards on the
hand-written half of the target list, which a rename would otherwise silently shrink.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import importlib.util
import json
import textwrap
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "check_refactor_coverage.py")


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Import ``scripts/check_refactor_coverage.py`` by path.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("check_refactor_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(tmp_path: Path, name: str, body: str) -> Path:
    """
    Write a dedented synthetic module.

    :param tmp_path: pytest's per-test temporary directory
    :type tmp_path: Path
    :param name: the file name
    :type name: str
    :param body: the module text, indented for readability
    :type body: str
    :return: the path written
    :rtype: Path
    """
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


class TestMethodLineRanges:
    """Locating each method so its lines can be checked against coverage."""

    def test_it_finds_module_functions_and_methods(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """Both shapes are targets, so both must be locatable."""
        path = write(
            tmp_path,
            "m.py",
            """
            def loose():
                return 1

            class Thing:
                def method(self):
                    return 2
            """,
        )
        ranges = mod.method_line_ranges(path)

        assert set(ranges) == {"loose", "method"}

    def test_a_name_defined_twice_records_both_spans(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """
        An override and its base can share a module, and a duplicate name is the
        normal case for the families this audits. Executing either counts.
        """
        path = write(
            tmp_path,
            "m.py",
            """
            class A:
                def shared(self):
                    return 1

            class B:
                def shared(self):
                    return 2
            """,
        )
        assert len(mod.method_line_ranges(path)["shared"]) == 2

    def test_the_span_covers_the_whole_body(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """A method counts as executed if any of its lines ran, so the span matters."""
        path = write(
            tmp_path,
            "m.py",
            """
            def f():
                a = 1
                b = 2
                return a + b
            """,
        )
        ((start, end),) = mod.method_line_ranges(path)["f"]
        assert end - start == 3


class TestCountTestCalls:
    """Separating a call on a method from a substitution of it."""

    def test_a_direct_call_is_counted(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """The plain case."""
        write(tmp_path, "test_x.py", "def test_a():\n    view.compute(1)\n")
        direct, _ = mod.count_test_calls(tmp_path)

        assert direct["compute"] == 1

    def test_mock_assertion_helpers_are_not_counted_as_calls(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """
        ``mock.assert_called_once_with(...)`` is a call, but not a call to the
        method under audit, and counting it would make any mocked method look
        exercised.
        """
        write(
            tmp_path,
            "test_x.py",
            """
            def test_a():
                view.compute.assert_called_once_with(1)
            """,
        )
        direct, _ = mod.count_test_calls(tmp_path)

        assert direct.get("assert_called_once_with", 0) == 0

    def test_a_patch_target_is_counted_as_a_substitution(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """
        ``mocker.patch.object(view, "compute")`` replaces the method rather than
        running it. This is the signal that exposed
        ``_logscale_and_filter_multiple_columns``.
        """
        write(
            tmp_path,
            "test_x.py",
            """
            def test_a(mocker):
                mocker.patch.object(view, "compute")
            """,
        )
        _, patched = mod.count_test_calls(tmp_path)

        assert patched["compute"] == 1

    def test_a_substitution_is_not_also_a_direct_call(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """Patching names the method as a string, never as a call."""
        write(
            tmp_path,
            "test_x.py",
            'def test_a(mocker):\n    mocker.patch.object(view, "compute")\n',
        )
        direct, _ = mod.count_test_calls(tmp_path)

        assert direct.get("compute", 0) == 0

    def test_an_unparseable_file_is_skipped_rather_than_fatal(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """One broken file must not take the whole audit down."""
        write(tmp_path, "test_broken.py", "def (:\n")
        write(tmp_path, "test_ok.py", "def test_a():\n    view.compute(1)\n")

        direct, _ = mod.count_test_calls(tmp_path)

        assert direct["compute"] == 1


class TestExecutedLines:
    """Reading coverage.py's JSON report."""

    def test_backslash_paths_are_normalised(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """
        coverage.py writes native separators, and the audit keys on posix paths.

        On Windows this is the difference between finding every file and finding
        none of them.
        """
        report = tmp_path / "coverage.json"
        report.write_text(
            json.dumps(
                {"files": {"poriscope\\utils\\MetaView.py": {"executed_lines": [1, 2]}}}
            ),
            encoding="utf-8",
        )

        lines = mod.executed_lines(report)

        assert lines["poriscope/utils/MetaView.py"] == {1, 2}

    def test_a_missing_report_explains_how_to_make_one(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """The audit needs a coverage run first, and says so."""
        with pytest.raises(FileNotFoundError, match="--cov-report=json"):
            mod.executed_lines(tmp_path / "nope.json")


class TestTargetList:
    """Guards on the half of the target list that is written by hand."""

    def test_every_moved_target_exists(self, mod: types.ModuleType) -> None:
        """
        A renamed or moved method must fail loudly rather than drop off the audit.

        This is the failure mode the audit exists to prevent, so it must not be
        possible for the audit itself to suffer it silently.
        """
        for file, method, step in mod.MOVED:
            path = REPO_ROOT / file
            assert path.is_file(), f"{step}: {file} is missing"
            assert method in mod.method_line_ranges(
                path
            ), f"{step}: {file} no longer defines {method}"

    def test_emit_bearing_methods_are_found(self, mod: types.ModuleType) -> None:
        """
        Step 4a's targets are derived, not listed, so the derivation must work.

        There are 75 emit sites across the five Views, so the method count is
        non-zero and smaller than that.
        """
        found = mod.emit_bearing_methods()

        assert found
        assert all(step == "4a" for _, _, step in found)
        assert len({m for _, m, _ in found}) <= 75

    def test_sql_authoring_methods_are_found(self, mod: types.ModuleType) -> None:
        """Step 4b's targets are derived too, and the Views really do author SQL."""
        found = mod.sql_authoring_methods()

        assert found
        assert all(step == "4b" for _, _, step in found)

    def test_the_deduplicated_half_comes_from_the_duplication_measure(
        self, mod: types.ModuleType
    ) -> None:
        """
        Derived from ``measure_duplication.py`` so the two instruments agree.

        If the ratchet says a method is duplicated, the audit must require it to be
        pinned before Step 3 merges the copies.
        """
        found = mod.deduplicated_targets()

        assert found
        assert all(step == "3-dedup" for _, _, step in found)

    def test_collect_targets_resolves_every_target_to_a_real_file(
        self, mod: types.ModuleType
    ) -> None:
        """A target the audit cannot locate would be reported as a failure forever."""
        for file, method, step in mod.collect_targets():
            assert (REPO_ROOT / file).is_file(), f"{step}: {file}"
