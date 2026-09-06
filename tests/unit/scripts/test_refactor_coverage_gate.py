"""
The refactor-coverage gate: every method the refactor touches must be pinned.

This holds the standing criterion for the 2.0.0 safety net - **every method the
refactor moves or deduplicates must be covered** - against
``scripts/check_refactor_coverage.py``'s derived target list.

**Why this gate is shaped differently from the other two.** The duplication ratchet
and the MVC boundary check are pure AST measurements, so they run under a plain
``pytest`` like any other test. This one needs to know whether each method's body
actually *executed*, which only ``coverage.py`` can say, and a plain run carries no
coverage data. Rather than make the whole gate conditional, it is split:

- The **structural half always runs**. Every target must resolve to a real file that
  really defines it, and every deduplicated method must be named by at least one
  test. That catches the two failures a rename causes - a target silently dropping
  off the list, and a method losing its only direct test - with no coverage needed.
- The **execution half runs when coverage data is present** and is skipped with a
  reason otherwise. Generate it with::

      pytest --cov=poriscope --cov-report=json:coverage.json

  ``ci-internal-pr.yml`` already runs the coverage variant, so wiring the report
  there costs nothing and makes this half enforced on every internal pull request.

``scripts/`` is not a package, so the module is loaded by file path.
"""

import importlib.util
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "check_refactor_coverage.py")
COVERAGE = REPO_ROOT / "coverage.json"


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


needs_coverage = pytest.mark.skipif(
    not COVERAGE.is_file(),
    reason=(
        "no coverage.json at the repository root; generate it with "
        "`pytest --cov=poriscope --cov-report=json:coverage.json`"
    ),
)


# ===========================================================================
# Always runs - no coverage data required
# ===========================================================================


def test_every_target_resolves_to_a_file_that_defines_it(
    mod: types.ModuleType,
) -> None:
    """
    A target the audit cannot locate is a hole in the safety net, not a pass.

    Renaming a method without updating the audit would otherwise quietly shrink
    the covered set, which is exactly the failure this whole branch exists to
    prevent.
    """
    missing = []
    for file, method, step in mod.collect_targets():
        path = REPO_ROOT / file
        if not path.is_file() or method not in mod.method_line_ranges(path):
            missing.append(f"{step}: {file}::{method}")

    assert not missing, "Audit targets that no longer exist:\n" + "\n".join(missing)


def test_every_deduplicated_method_is_named_by_some_test(
    mod: types.ModuleType,
) -> None:
    """
    Step 3 merges these copies, so each needs a test that names it before the
    merge - a method exercised only in passing cannot show that the merge
    preserved its behaviour.

    Structural, so it holds without a coverage run.
    """
    direct, _ = mod.count_test_calls()
    unnamed = sorted(
        {
            method
            for _, method, step in mod.collect_targets()
            if step == "3-dedup" and direct.get(method, 0) == 0
        }
    )

    assert (
        not unnamed
    ), "Deduplicated methods with no test naming them:\n  " + "\n  ".join(unnamed)


# ===========================================================================
# Runs when coverage data is available
# ===========================================================================


@needs_coverage
def test_no_target_is_untested(mod: types.ModuleType) -> None:
    """
    The definitive failure: the body never ran, so nothing can be asserting it.

    This is what catches a method that every test replaces with a ``Mock``.
    """
    records = mod.audit(COVERAGE)
    bad = [
        r for r in records if r["verdict"] in {"UNTESTED", "NOT FOUND", "MISSING FILE"}
    ]

    assert not bad, "Refactor targets with no executed coverage:\n" + "\n".join(
        f"  {r['verdict']}  {r['step']}  {Path(str(r['file'])).name}::{r['method']}"
        for r in bad
    )


@needs_coverage
def test_no_target_is_merely_run_in_passing(mod: types.ModuleType) -> None:
    """
    The standing criterion, in full.

    ``RUNS ONLY`` means the body executed - almost always under a click-driven e2e
    flow - but no test named it, so nothing checked what it produced. That is not
    coverage for a method about to be moved. All eleven such cases were closed on
    this branch; this keeps them closed.
    """
    records = mod.audit(COVERAGE)
    bad = [r for r in records if r["verdict"] == "RUNS ONLY"]

    assert not bad, (
        "Refactor targets exercised only in passing, with no test naming them:\n"
        + "\n".join(
            f"  {r['step']}  {Path(str(r['file'])).name}::{r['method']}" for r in bad
        )
        + "\n\nAdd a test that calls each directly, or, if an end-to-end flow is "
        "genuinely the only sensible exercise, record why in DECISIONS.md and "
        "exclude it explicitly rather than loosening this gate."
    )
