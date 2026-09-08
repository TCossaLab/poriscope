"""
Tests for ``scripts/measure_duplication.py``, the byte-identical-method measure.

These drive the measure against small synthetic module texts rather than the real
analysis-tab files, so they pin the counting *rule* and do not move every time the
refactor deletes a duplicate. The one exception is
``test_every_family_file_exists``, which is a guard: the family lists are
deliberately explicit, so a renamed file must fail loudly rather than silently
shrink the measurement.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import importlib.util
import textwrap
import types
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "measure_duplication.py")


def load_script() -> types.ModuleType:
    """
    Import ``scripts/measure_duplication.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("measure_duplication", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Load the measurement module once for the whole file.

    :return: the imported module
    :rtype: types.ModuleType
    """
    return load_script()


def write(tmp_path: Path, name: str, body: str) -> Path:
    """
    Write a dedented synthetic module and return its path.

    :param tmp_path: pytest's per-test temporary directory
    :type tmp_path: Path
    :param name: the file name to write
    :type name: str
    :param body: the module text, indented for readability in the test
    :type body: str
    :return: the path written
    :rtype: Path
    """
    path = tmp_path / name
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


# ===========================================================================
# collect_functions - which functions are considered, and as what text
# ===========================================================================


class TestCollectFunctions:
    """What the measure treats as a function, and what text it compares."""

    def test_finds_module_level_functions_and_methods(
        self, mod: types.ModuleType
    ) -> None:
        """Both a bare function and a method of a module-level class are collected."""
        source = textwrap.dedent(
            """
            def loose():
                return 1

            class Thing:
                def method(self):
                    return 2
            """
        )
        names = [name for name, _ in mod.collect_functions(source, "x.py")]
        assert names == ["loose", "Thing.method"]

    def test_skips_functions_nested_in_a_function(self, mod: types.ModuleType) -> None:
        """A closure is not collected: its text is already inside its parent's."""
        source = textwrap.dedent(
            """
            def outer():
                def inner():
                    return 1
                return inner
            """
        )
        names = [name for name, _ in mod.collect_functions(source, "x.py")]
        assert names == ["outer"]

    def test_dedents_so_a_method_matches_a_bare_function(
        self, mod: types.ModuleType
    ) -> None:
        """Indentation is normalised, so nesting depth does not affect equality."""
        loose = mod.collect_functions("def f(self):\n    return 1\n", "a.py")[0][1]
        method = mod.collect_functions(
            "class C:\n    def f(self):\n        return 1\n", "b.py"
        )[0][1]
        assert loose == method

    def test_decorators_are_not_part_of_the_compared_text(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``get_source_segment`` starts at the ``def`` line, so decorators are excluded.

        Documented behaviour, pinned here because it is surprising: the body is
        what a promotion to a base class deletes.
        """
        plain = mod.collect_functions("def f(self):\n    return 1\n", "a.py")[0][1]
        decorated = mod.collect_functions(
            "@log(logger=logger)\ndef f(self):\n    return 1\n", "b.py"
        )[0][1]
        assert plain == decorated

    def test_a_syntax_error_propagates(self, mod: types.ModuleType) -> None:
        """A file that cannot be parsed is a failure, not a silent zero."""
        with pytest.raises(SyntaxError):
            mod.collect_functions("def (:\n", "broken.py")


# ===========================================================================
# measure_family - what counts as duplication, and how much it is worth
# ===========================================================================


class TestMeasureFamily:
    """The grouping rule and the removable-line arithmetic."""

    def test_identical_body_across_two_files_is_one_group(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """Three lines shared by two files is one group worth three removable lines."""
        body = """
            class C:
                def shared(self):
                    a = 1
                    return a
            """
        files = [write(tmp_path, "a.py", body), write(tmp_path, "b.py", body)]
        result = mod.measure_family(files)

        assert result["identical_bodies"] == 1
        assert result["removable_lines"] == 3
        assert result["functions"] == 2

    def test_removable_scales_with_the_number_of_files(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """Five copies of a three-line body leave four removable copies, not five."""
        body = """
            class C:
                def shared(self):
                    a = 1
                    return a
            """
        files = [write(tmp_path, f"f{i}.py", body) for i in range(5)]
        result = mod.measure_family(files)

        assert result["identical_bodies"] == 1
        assert result["removable_lines"] == 12

    def test_a_body_repeated_inside_one_file_is_not_duplication(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """The family measure is about copies *across* files; one file is not a group."""
        body = """
            class C:
                def one(self):
                    return 1

                def two(self):
                    return 1
            """
        files = [write(tmp_path, "a.py", body), write(tmp_path, "b.py", "x = 1\n")]
        result = mod.measure_family(files)

        assert result["identical_bodies"] == 0
        assert result["removable_lines"] == 0

    def test_bodies_that_differ_by_one_token_are_not_a_group(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """Byte identity is the rule, so near-misses are invisible - stated in the docstring."""
        files = [
            write(tmp_path, "a.py", "class C:\n    def f(self):\n        return 1\n"),
            write(tmp_path, "b.py", "class C:\n    def f(self):\n        return 2\n"),
        ]
        assert mod.measure_family(files)["identical_bodies"] == 0

    def test_groups_are_reported_largest_first(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """The report leads with the biggest win."""
        body = """
            class C:
                def small(self):
                    return 1

                def big(self):
                    a = 1
                    b = 2
                    c = 3
                    return a + b + c
            """
        files = [write(tmp_path, "a.py", body), write(tmp_path, "b.py", body)]
        groups = mod.measure_family(files)["groups"]

        assert [g["names"][0].split(".")[-1] for g in groups] == ["big", "small"]


# ===========================================================================
# Baseline handling
# ===========================================================================


class TestBaselineComparison:
    """Both directions of disagreement are reported, with different guidance."""

    def _counts(self, removable: int, functions: int = 10) -> Dict[str, Dict[str, int]]:
        """
        Build a one-family baseline mapping with the given counts.

        :param removable: the removable-line count to record
        :type removable: int
        :param functions: the function count to record
        :type functions: int
        :return: a baseline-shaped mapping
        :rtype: Dict[str, Dict[str, int]]
        """
        return {
            "*View.py": {
                "files": 5,
                "functions": functions,
                "identical_bodies": 1,
                "removable_lines": removable,
            }
        }

    def test_identical_measurements_agree(self, mod: types.ModuleType) -> None:
        """No disagreement means no message."""
        assert mod.compare(self._counts(10), self._counts(10)) == []

    def test_a_rise_is_reported_as_added_duplication(
        self, mod: types.ModuleType
    ) -> None:
        """Going up is a regression and says so."""
        problems: List[str] = mod.compare(self._counts(12), self._counts(10))
        assert len(problems) == 1
        assert "rose from 10 to 12" in problems[0]
        assert "duplication was added" in problems[0]

    def test_a_fall_asks_for_the_baseline_to_be_updated(
        self, mod: types.ModuleType
    ) -> None:
        """
        Going down fails too, so the win is recorded in the commit that earned it.

        Without this the baseline overstates the duplication left and the slack
        accrues silently, which is why the check is exact rather than ``<=``.
        """
        problems: List[str] = mod.compare(
            self._counts(8, functions=6), self._counts(10, functions=10)
        )
        assert any("fell from 10 to 8" in p and "--update" in p for p in problems)

    def test_a_real_promotion_is_not_flagged_as_divergence(
        self, mod: types.ModuleType
    ) -> None:
        """Promoting to a base deletes the copies, so the function count falls too."""
        problems: List[str] = mod.compare(
            self._counts(8, functions=6), self._counts(10, functions=10)
        )
        assert not any("edited into divergence" in p for p in problems)

    def test_a_copy_edited_into_divergence_is_called_out(
        self, mod: types.ModuleType
    ) -> None:
        """
        Removable lines falling with no function deleted is the brittle case.

        Changing a few characters in one copy of a five-way duplicate drops that
        copy out of its group, so this measure reads a whole copy's worth of
        progress while nothing was deduplicated and the duplication is in fact
        worse. The function count is what tells the two apart.
        """
        problems: List[str] = mod.compare(
            self._counts(8, functions=10), self._counts(10, functions=10)
        )
        assert any("edited into divergence" in p for p in problems)
        assert any("no function was deleted" in p for p in problems)

    def test_a_new_family_is_reported(self, mod: types.ModuleType) -> None:
        """Measuring a family the baseline does not know about is a disagreement."""
        problems = mod.compare(self._counts(10) | {"*New.py": {}}, self._counts(10))
        assert any("absent from the baseline" in p for p in problems)

    def test_a_dropped_family_is_reported(self, mod: types.ModuleType) -> None:
        """A family in the baseline that is no longer measured is a disagreement."""
        problems = mod.compare({}, self._counts(10))
        assert any("no longer measured" in p for p in problems)

    def test_to_baseline_drops_the_group_detail(
        self, mod: types.ModuleType, tmp_path: Path
    ) -> None:
        """
        Only the counts are recorded.

        The per-group names are useful to read and useless to diff; recording them
        would churn the baseline on every rename.
        """
        body = "class C:\n    def f(self):\n        return 1\n"
        files = [write(tmp_path, "a.py", body), write(tmp_path, "b.py", body)]
        reduced = mod.to_baseline({"fam": mod.measure_family(files)})

        assert set(reduced["fam"]) == {
            "files",
            "functions",
            "identical_bodies",
            "removable_lines",
        }


# ===========================================================================
# The family lists themselves
# ===========================================================================


class TestFamilyLists:
    """Guards on the explicit file lists, which a glob would get wrong."""

    def test_every_family_file_exists(self, mod: types.ModuleType) -> None:
        """
        A renamed or moved file must fail loudly rather than shrink the measurement.

        ``measure()`` raises rather than skipping, which is the whole reason the
        lists are enumerated instead of globbed.
        """
        for family, names in mod.FAMILIES.items():
            for name in names:
                path = mod.REPO_ROOT / name
                assert path.is_file(), f"{family}: {name} is missing"

    def test_the_owner_held_fitters_are_not_ratcheted(
        self, mod: types.ModuleType
    ) -> None:
        """
        PeakFinder, Basic_PeakFinder and NanoTrees are deliberately absent.

        Their logic is another developer's under standing policy, so ratcheting
        over them would fail on their owner's commits and block work that is not
        ours to gate. Absent by design, not by oversight - asserted so a later
        "completeness" tidy-up cannot quietly add them.
        """
        listed = {name for names in mod.FAMILIES.values() for name in names}
        for excluded in ("PeakFinder.py", "Basic_PeakFinder.py", "NanoTrees.py"):
            assert not any(name.endswith(excluded) for name in listed), excluded

    def test_the_controls_family_includes_the_camelcase_file(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``eventAnalysisControls.py`` does not match a case-sensitive ``*controls.py``.

        Globbing that pattern finds four files and silently drops 742 lines, 17% of
        the family, so this is pinned rather than left to a comment.
        """
        controls = mod.FAMILIES["*controls.py"]
        assert any(name.endswith("eventAnalysisControls.py") for name in controls)
        assert len(controls) == 5
