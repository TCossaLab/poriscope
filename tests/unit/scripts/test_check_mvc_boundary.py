"""
Tests for ``scripts/check_mvc_boundary.py``, the analysis-tab MVC boundary measure.

These drive the three rules against small synthetic module texts rather than the
real Views and Controllers, so they pin the *definition* of each rule and do not
move every time the refactor removes a violation. That matters more here than
usual: an earlier count of "21 import statements over 12 View x module pairs"
could not be reproduced because the rule was never written down precisely enough
to re-derive, and the real figures are 22 and 13.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import ast
import importlib.util
import textwrap
import types
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "check_mvc_boundary.py")


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    Import ``scripts/check_mvc_boundary.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("check_mvc_boundary", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse(source: str) -> ast.Module:
    """
    Parse a dedented synthetic module.

    :param source: the module text, indented for readability in the test
    :type source: str
    :return: the parsed module
    :rtype: ast.Module
    """
    return ast.parse(textwrap.dedent(source))


# ===========================================================================
# Rule 1 - global_signal.emit in a View
# ===========================================================================


class TestEmitDetection:
    """The rule is about the plugin bus, not about Qt signals in general."""

    def _count(self, mod: types.ModuleType, source: str) -> int:
        """
        Count global_signal emits in a synthetic module.

        :param mod: the module under test
        :type mod: types.ModuleType
        :param source: the module text
        :type source: str
        :return: the number of matching call sites
        :rtype: int
        """
        tree = parse(source)
        return sum(1 for n in ast.walk(tree) if mod.is_global_signal_emit(n))

    def test_counts_a_global_signal_emit(self, mod: types.ModuleType) -> None:
        """The canonical form counts."""
        assert self._count(mod, "self.global_signal.emit('a', 'b')") == 1

    def test_counts_each_site_separately(self, mod: types.ModuleType) -> None:
        """Two calls are two entries, not one."""
        source = """
            self.global_signal.emit('a')
            self.global_signal.emit('b')
            """
        assert self._count(mod, source) == 2

    def test_ignores_a_different_signal(self, mod: types.ModuleType) -> None:
        """A View emitting its own signal is fine; only the bus is the violation."""
        assert self._count(mod, "self.plot_requested.emit(data)") == 0

    def test_ignores_a_non_emit_call_on_the_bus(self, mod: types.ModuleType) -> None:
        """Connecting to the bus is not emitting on it."""
        assert self._count(mod, "self.global_signal.connect(handler)") == 0

    def test_counts_regardless_of_receiver(self, mod: types.ModuleType) -> None:
        """The receiver need not be ``self`` - what matters is the signal's name."""
        assert self._count(mod, "widget.global_signal.emit('a')") == 1


# ===========================================================================
# Rule 2 - forbidden imports in a View
# ===========================================================================


class TestForbiddenImports:
    """One entry per import statement, keyed by the dotted path as written."""

    def test_plain_and_submodule_imports_are_two_entries(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``numpy`` and ``numpy.typing`` are two statements, not one module.

        This is precisely the ambiguity that made the earlier count of 21
        unreproducible: it is 22 statements over 13 distinct pairs.
        """
        source = """
            import numpy as np
            import numpy.typing as npt
            """
        assert mod.forbidden_imports(parse(source)) == ["numpy", "numpy.typing"]

    def test_from_import_records_the_module_not_the_names(
        self, mod: types.ModuleType
    ) -> None:
        """``from scipy.stats import iqr, t`` is one entry, however many names it binds."""
        source = "from scipy.stats import iqr, t"
        assert mod.forbidden_imports(parse(source)) == ["scipy.stats"]

    def test_a_submodule_of_a_forbidden_package_is_forbidden(
        self, mod: types.ModuleType
    ) -> None:
        """The top-level package decides, so a deep submodule still counts."""
        source = "from pandas.api.types import is_float_dtype"
        assert mod.forbidden_imports(parse(source)) == ["pandas.api.types"]

    def test_allowed_imports_are_ignored(self, mod: types.ModuleType) -> None:
        """Qt, matplotlib and the standard library are not the rule's business."""
        source = """
            import logging
            from PySide6.QtWidgets import QWidget
            import matplotlib.pyplot as plt
            """
        assert mod.forbidden_imports(parse(source)) == []

    def test_relative_imports_are_skipped(self, mod: types.ModuleType) -> None:
        """A relative import is in-package and cannot reach a third-party library."""
        source = "from . import numpy"
        assert mod.forbidden_imports(parse(source)) == []

    def test_sqlite3_is_in_the_rule_although_it_is_zero_today(
        self, mod: types.ModuleType
    ) -> None:
        """
        Kept as a ratchet.

        No View imports the driver - they build SQL as f-strings and hand it to the
        loader - so this contributes nothing today and would catch it changing.
        """
        assert "sqlite3" in mod.FORBIDDEN_IMPORTS
        assert mod.forbidden_imports(parse("import sqlite3")) == ["sqlite3"]

    def test_fast_histogram_is_in_the_rule(self, mod: types.ModuleType) -> None:
        """
        Without it, Step 4c could finish with the rule still reporting success.

        ``RawDataView`` imports ``fast_histogram`` and Step 4c moves it, so leaving
        it out would let that completion go unregistered.
        """
        assert "fast_histogram" in mod.FORBIDDEN_IMPORTS


# ===========================================================================
# Rule 3 - a Controller reading a View private
# ===========================================================================


class TestViewPrivateReads:
    """``self.view._x`` is the Controller reaching past the View's interface."""

    def test_counts_each_access_site(self, mod: types.ModuleType) -> None:
        """Two reads of the same attribute are two sites."""
        source = """
            a = self.view._pending_filter_name
            b = self.view._pending_filter_name
            """
        assert mod.view_private_reads(parse(source)) == [
            "_pending_filter_name",
            "_pending_filter_name",
        ]

    def test_ignores_public_attributes(self, mod: types.ModuleType) -> None:
        """The rule is about privates; a public reach-in is a separate concern."""
        assert mod.view_private_reads(parse("a = self.view.subset_filters")) == []

    def test_ignores_dunders(self, mod: types.ModuleType) -> None:
        """Dunders are Python protocol, not View internals."""
        assert mod.view_private_reads(parse("a = self.view.__class__")) == []

    def test_ignores_privates_on_anything_but_the_view(
        self, mod: types.ModuleType
    ) -> None:
        """A Controller's own privates, and the Model's, are not this rule."""
        source = """
            a = self._cache
            b = self.model._rows
            """
        assert mod.view_private_reads(parse(source)) == []


# ===========================================================================
# Totals and comparison
# ===========================================================================


class TestTotals:
    """The allowlist total, and the smaller pair count reported beside it."""

    def _allowlist(self, mod: types.ModuleType) -> Dict[str, Dict[str, object]]:
        """
        Build a small allowlist-shaped mapping.

        :param mod: the module under test
        :type mod: types.ModuleType
        :return: an allowlist-shaped mapping
        :rtype: Dict[str, Dict[str, object]]
        """
        return {
            "emits": {"AView.py": 3},
            "imports": {"AView.py": ["numpy", "numpy.typing", "pandas"]},
            "private_access": {"AController.py": 2},
        }

    def test_total_sums_all_three_rules(self, mod: types.ModuleType) -> None:
        """Emits plus import statements plus private sites."""
        assert mod.total(self._allowlist(mod)) == 3 + 3 + 2

    def test_distinct_pairs_collapses_submodules(self, mod: types.ModuleType) -> None:
        """
        ``numpy`` and ``numpy.typing`` are one pair but two statements.

        The pair count is reported for context and is deliberately *not* what the
        allowlist totals.
        """
        assert mod.distinct_pairs(self._allowlist(mod)) == 2


class TestComparison:
    """Both directions of disagreement are reported, with different guidance."""

    def _allowlist(self) -> Dict[str, Dict[str, object]]:
        """
        Build a minimal allowlist-shaped mapping.

        :return: an allowlist-shaped mapping
        :rtype: Dict[str, Dict[str, object]]
        """
        return {"emits": {"AView.py": 3}, "imports": {}, "private_access": {}}

    def test_a_match_is_silent(self, mod: types.ModuleType) -> None:
        """No disagreement means no message."""
        assert mod.compare(self._allowlist(), self._allowlist()) == []

    def test_a_new_file_is_a_new_violation(self, mod: types.ModuleType) -> None:
        """A violation appearing where the allowlist has none fails loudly."""
        current = {
            "emits": {"AView.py": 3, "BView.py": 1},
            "imports": {},
            "private_access": {},
        }
        problems: List[str] = mod.compare(current, self._allowlist())
        assert any("new violation was introduced" in p for p in problems)

    def test_a_cleaned_file_asks_for_the_win_to_be_recorded(
        self, mod: types.ModuleType
    ) -> None:
        """
        Progress fails too, so the allowlist stays a truthful progress metric.

        Under a "no worse than" rule the allowlist would overstate the violations
        remaining, which is the one thing it exists to report.
        """
        current: Dict[str, Dict[str, object]] = {
            "emits": {},
            "imports": {},
            "private_access": {},
        }
        problems = mod.compare(current, self._allowlist())
        assert any("record the win with --update" in p for p in problems)

    def test_a_changed_count_is_reported_with_both_numbers(
        self, mod: types.ModuleType
    ) -> None:
        """A partial change names what it was and what it is."""
        current = {"emits": {"AView.py": 2}, "imports": {}, "private_access": {}}
        problems = mod.compare(current, self._allowlist())
        assert any("was 3, is now 2" in p for p in problems)


class TestFileLists:
    """Guards on the explicit file lists."""

    def test_every_named_file_exists(self, mod: types.ModuleType) -> None:
        """A renamed file must fail loudly rather than shrink the measurement."""
        for name in mod.VIEWS + mod.CONTROLLERS:
            assert (mod.TABS / name).is_file(), f"{name} is missing"

    def test_all_five_tabs_are_covered_on_both_sides(
        self, mod: types.ModuleType
    ) -> None:
        """Five Views and five Controllers, or the metric is measuring a subset."""
        assert len(mod.VIEWS) == 5
        assert len(mod.CONTROLLERS) == 5
