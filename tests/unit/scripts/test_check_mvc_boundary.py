"""
Tests for ``scripts/check_mvc_boundary.py``, the analysis-tab MVC boundary measure.

These drive the five rules against small synthetic module texts rather than the
real Views and Controllers, so they pin the *definition* of each rule and do not
move every time the refactor removes a violation. That matters more here than
usual: an earlier count of "21 import statements over 12 View x module pairs"
could not be reproduced because the rule was never written down precisely enough
to re-derive, and the real figures are 24 and 14.

``TestLayerMembership`` is the exception, and reads the real tree on purpose. Which
files a rule covers is not a definition that can be checked against synthetic text,
and it was the gate's blind spot: rules 1-3 scanned ten hardcoded filenames under
``poriscope/plugins/analysistabs/``, so promoting a method to a base in
``poriscope/utils/`` removed it from the measurement without fixing it.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import ast
import importlib.util
import textwrap
import types
from pathlib import Path
from typing import Dict, List, Set

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
            "emits": {"poriscope/a/AView.py": 3},
            "imports": {"poriscope/a/AView.py": ["numpy", "numpy.typing", "pandas"]},
            "private_access": {"poriscope/a/AController.py": 2},
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
        return {
            "emits": {"poriscope/a/AView.py": 3},
            "imports": {},
            "private_access": {},
        }

    def test_a_match_is_silent(self, mod: types.ModuleType) -> None:
        """No disagreement means no message."""
        assert mod.compare(self._allowlist(), self._allowlist()) == []

    def test_a_new_file_is_a_new_violation(self, mod: types.ModuleType) -> None:
        """A violation appearing where the allowlist has none fails loudly."""
        current = {
            "emits": {"poriscope/a/AView.py": 3, "poriscope/a/BView.py": 1},
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
        current = {
            "emits": {"poriscope/a/AView.py": 2},
            "imports": {},
            "private_access": {},
        }
        problems = mod.compare(current, self._allowlist())
        assert any("was 3, is now 2" in p for p in problems)


class TestLayerMembership:
    """
    Which files rules 1-3 read, now that the layer is derived rather than listed.

    The original ten hardcoded filenames made the gate blind to its own refactor: a
    method promoted to a base in ``poriscope/utils/`` left the measurement without
    being fixed. These pin the two tests that replaced them - a whole-directory
    membership and a filename suffix - and, more importantly, pin the *destinations*,
    since those are what the list could not see.
    """

    def _names(self, paths: List[Path]) -> Set[str]:
        """
        Reduce a layer scan to repository-relative paths.

        :param paths: the files a layer scan returned
        :type paths: List[Path]
        :return: their repository-relative paths
        :rtype: Set[str]
        """
        return {p.resolve().relative_to(REPO_ROOT).as_posix() for p in paths}

    def test_the_five_tab_views_and_controllers_are_all_classified(
        self, mod: types.ModuleType
    ) -> None:
        """The original ten, which the hardcoded lists covered and must still cover."""
        views = self._names(mod.view_modules())
        controllers = self._names(mod.controller_modules())
        tabs = "poriscope/plugins/analysistabs"

        for tab in ("Clustering", "EventAnalysis", "Metadata", "Protein", "RawData"):
            assert f"{tabs}/{tab}View.py" in views
            assert f"{tabs}/{tab}Controller.py" in controllers

    def test_the_promotion_destinations_are_classified(
        self, mod: types.ModuleType
    ) -> None:
        """
        The whole point of widening the scan.

        ``MetaController`` is where Step 3b would promote ``relay_query``, which holds
        **all ten** of rule 3's violations; ``MetaView`` and ``MetaControls`` are
        Step 3's View-side destinations. Under the hardcoded lists a promotion to any
        of them zeroed the rule without fixing anything.
        """
        assert "poriscope/utils/MetaView.py" in self._names(mod.view_modules())
        assert "poriscope/utils/MetaControls.py" in self._names(mod.view_modules())
        assert "poriscope/utils/MetaController.py" in self._names(
            mod.controller_modules()
        )

    def test_a_data_plugin_base_is_in_neither_layer(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``poriscope/utils/`` is flat and holds bases for every layer.

        This is why role is read off the filename there rather than taking the
        directory wholesale: ``MetaReader`` and its seven siblings import numpy by
        design, and classifying them as Views would book eight violations the refactor
        will never remove.
        """
        both = self._names(mod.view_modules()) | self._names(mod.controller_modules())

        assert "poriscope/utils/MetaReader.py" not in both
        assert "poriscope/utils/MetaEventFitter.py" not in both

    def test_the_two_layers_do_not_overlap(self, mod: types.ModuleType) -> None:
        """A module in both layers would be counted under rules it does not own."""
        overlap = self._names(mod.view_modules()) & self._names(
            mod.controller_modules()
        )

        assert overlap == set()

    def test_no_dunder_init_is_scanned(self, mod: types.ModuleType) -> None:
        """Re-exports are noise, and are excluded on both sides as in rule 4."""
        scanned = mod.view_modules() + mod.controller_modules()

        assert not any(p.name == "__init__.py" for p in scanned)

    def test_an_empty_layer_raises_rather_than_reading_as_clean(
        self, mod: types.ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The one failure mode a derived scan has that a list does not.

        A list goes stale loudly - the file it names is missing. A derived scan goes
        stale *silently*: rename a directory and it matches nothing, which measures as
        a clean layer rather than as a broken gate.
        """
        monkeypatch.setattr(mod, "VIEW_DIRS", ())
        monkeypatch.setattr(mod, "VIEW_SUFFIXES", ("NoSuchSuffix.py",))

        with pytest.raises(FileNotFoundError, match="View layer"):
            mod.measure()


# ===========================================================================
# Rule 4 - an app-shell module importing from a plugin package
# ===========================================================================


class TestPluginImports:
    """
    The layering rule, added by the Step 2 exit review.

    Step 3f's whole point was that the app shell imported *up* from
    ``plugins/analysistabs/utils/walkthrough*``. Without this rule nothing observed
    that inversion, so 3f could have been done, half-done or undone with every gate
    green. 3f landed 2026-09-06 and the rule now reads zero; these use a module that
    still exists, since the walkthrough modules have moved into the shell.
    """

    def test_a_plugin_import_is_recorded(self, mod: types.ModuleType) -> None:
        """The canonical form: the shell reaching into a plugin package."""
        source = "from poriscope.plugins.analysistabs.MetadataView import MetadataView"

        assert mod.plugin_imports(parse(source)) == [
            "poriscope.plugins.analysistabs.MetadataView"
        ]

    def test_a_plain_import_is_recorded_too(self, mod: types.ModuleType) -> None:
        """Both import forms reach the same package."""
        source = "import poriscope.plugins.analysistabs.MetadataView"

        assert mod.plugin_imports(parse(source)) == [
            "poriscope.plugins.analysistabs.MetadataView"
        ]

    def test_imports_within_the_shell_are_ignored(self, mod: types.ModuleType) -> None:
        """
        The rule is about the direction of the dependency, not about imports.

        The shell importing from itself, or from ``poriscope.utils``, is exactly
        how it is supposed to be built.
        """
        source = """
            from poriscope.utils.MetaView import MetaView
            from poriscope.views.widgets.time_widget import TimeWidget
            from PySide6.QtWidgets import QWidget
            """
        assert mod.plugin_imports(parse(source)) == []

    def test_relative_imports_are_skipped(self, mod: types.ModuleType) -> None:
        """A relative import cannot cross packages, so it cannot invert layering."""
        assert mod.plugin_imports(parse("from . import walkthrough")) == []

    def test_the_shell_scan_covers_views_controllers_and_models(
        self, mod: types.ModuleType
    ) -> None:
        """
        All three shell packages, not just views.

        Views are where the inversion lives today; controllers and models are
        included so a new one cannot appear somewhere unwatched.
        """
        scanned = {p.as_posix() for p in mod.shell_modules()}

        assert any("/views/" in p for p in scanned)
        assert any("/controllers/" in p for p in scanned)
        assert any("/models/" in p for p in scanned)

    def test_no_dunder_init_is_scanned(self, mod: types.ModuleType) -> None:
        """
        Package ``__init__`` files re-export by design and would be noise.

        Excluded deliberately, so a later reader does not mistake their absence for
        an oversight.
        """
        assert not any(p.name == "__init__.py" for p in mod.shell_modules())


# ===========================================================================
# Rule 5 - an analysis-tab module reaching a plugin outside call()
# ===========================================================================


class TestPluginReach:
    """
    ``call()`` is the whole plugin-facing API a tab gets, and this counts the ways
    around it.

    Added by Step 4a, reading **zero** from the start - so unlike rules 1 to 3 it is a
    ratchet rather than a backlog. Python cannot enforce this at runtime without
    inspecting the call stack on every plugin call, which would cost more than it is
    worth and would reject the worker-thread path; failing on the commit is earlier and
    cheaper.
    """

    def test_resolving_an_instance_directly_counts(self, mod: types.ModuleType) -> None:
        """The most direct way around ``call()``."""
        source = "x = self.controller.get_plugin_instance('MetaReader', 'r0')"

        assert mod.plugin_reaches(parse(source)) == ["get_plugin_instance"]

    def test_touching_the_data_plugin_controller_counts(
        self, mod: types.ModuleType
    ) -> None:
        """Holding the registry is holding every plugin in it."""
        source = "x = self.data_plugin_controller"

        assert mod.plugin_reaches(parse(source)) == ["data_plugin_controller"]

    def test_the_signal_of_a_similar_name_does_not_count(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``data_plugin_controller_signal`` is a different identifier.

        Tabs emit it legitimately, so matching it would make the rule unusable - and a
        substring check would have done exactly that.
        """
        source = "self.data_plugin_controller_signal.emit('a', 'b', 'c', (), 'd', ())"

        assert mod.plugin_reaches(parse(source)) == []

    def test_importing_a_concrete_plugin_counts(self, mod: types.ModuleType) -> None:
        """A tab names plugins by key, never by class."""
        source = (
            "from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader"
        )

        assert mod.plugin_reaches(parse(source)) == [
            "poriscope.plugins.db_loaders.SQLiteDBLoader"
        ]

    def test_importing_another_analysis_tab_does_not_count_here(
        self, mod: types.ModuleType
    ) -> None:
        """
        Rule 5 is about *data* plugins.

        A tab importing its own sibling module is ordinary; the cross-tab rule is the
        signal-relay convention in CLAUDE.md, not this.
        """
        source = (
            "from poriscope.plugins.analysistabs.MetadataModel import MetadataModel"
        )

        assert mod.plugin_reaches(parse(source)) == []

    def test_all_eight_families_are_covered(self, mod: types.ModuleType) -> None:
        """
        Missing one would leave a hole exactly where a plugin lives.

        Named as a set so that adding a ninth family fails here rather than silently
        going unwatched.
        """
        assert mod.PLUGIN_FAMILIES == {
            "datareaders",
            "datawriters",
            "db_loaders",
            "db_writers",
            "eventfinders",
            "eventfitters",
            "eventloaders",
            "filters",
        }

    def test_the_data_plugin_bases_are_not_tab_modules(
        self, mod: types.ModuleType
    ) -> None:
        """
        ``MetaReader`` and its siblings legitimately hold one another.

        ``MetaEventFinder`` holds a ``MetaReader`` and ``MetaDatabaseWriter`` holds a
        ``MetaEventFitter``, so rule 5 must not apply to them - which is why the
        tab-layer suffixes are narrower than the View and Controller layers above.
        """
        scanned = {p.name for p in mod.tab_layer_modules()}

        assert "MetaReader.py" not in scanned
        assert "MetaEventFinder.py" not in scanned
        assert "MetaView.py" in scanned
        assert "MetaModel.py" in scanned

    def test_the_tab_layer_includes_every_analysis_tab_module(
        self, mod: types.ModuleType
    ) -> None:
        """Everything under analysistabs/, plus the bases those tabs inherit."""
        scanned = {
            p.resolve().relative_to(REPO_ROOT).as_posix()
            for p in mod.tab_layer_modules()
        }

        assert "poriscope/plugins/analysistabs/MetadataView.py" in scanned
        assert "poriscope/plugins/analysistabs/utils/metadatacontrols.py" in scanned
        assert "poriscope/utils/MetaSubsetTabController.py" in scanned
