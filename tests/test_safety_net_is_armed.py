"""
That the characterization golden net is actually running, not merely present.

Step 2 pinned the numeric surface Step 4 moves - ``RawDataModel.gaussian_fit`` and
``get_baseline_stats``, whose own source comment calls the first "THE CRITICAL MATH
FIX" and which the Step 2 coverage audit found had *no* behavioural coverage, plus
the exact-text SQL goldens. All of it runs through ``pytest-regressions``.

**The gap this closes, found 2026-09-08.** ``pytest-regressions`` is declared
correctly in *both* dependency sources - ``pyproject.toml [dev]`` and
``requirements-dev.txt``, both required because ``ci-branches.yml`` and
``ci-fork-pr.yml`` install only from the latter while ``release.yml`` installs only
the former. It was nonetheless absent from one working environment, and the failure
mode is the problem: every golden errored at **setup** with ``fixture
'num_regression' not found``, which renders as four errors beside 3,400 passes. That
reads as an environment nit rather than as *the entire numeric golden net not
running*, and a scoped or filtered run would not have shown it at all.

The three structural gates cannot see this. The duplication ratchet checks that
copies vanished, the boundary allowlist that nothing crossed a layer, and the
refactor-coverage audit that every moved method is named by a test *and* executed -
but the audit reads a coverage JSON, so an uncollected test is indistinguishable from
one that never existed. A net's **absence has no signature**, which is the same shape
as the refactor's first escaped regression one level up. Hence a test whose failure
names the cause outright.

**The registration name was measured, not guessed, and guessing would have been wrong
twice.** ``pytest-regressions`` registers with the plugin manager as ``regressions``;
neither ``pytest_regressions`` nor ``pytest-regressions`` resolves. Its
``original_datadir``/``datadir`` dependency registers under its own distribution name,
``pytest-datadir``, and the goldens fail without it too, so both are asserted.
"""

import pytest

# The names the plugin manager knows these by, which are not the distribution names
# in requirements-dev.txt. Measured against pytest 8.4.1 / pytest-regressions 2.11.0.
REQUIRED_PLUGINS = ("regressions", "pytest-datadir")

# Every fixture the checked-in goldens are written against. ``num_regression`` and
# ``data_regression`` are the two in use today; the other two are asserted so that a
# release renaming any of them fails here rather than inside whichever test adopts it.
GOLDEN_FIXTURES = (
    "num_regression",
    "data_regression",
    "dataframe_regression",
    "file_regression",
)

INSTALL_HINT = (
    "The characterization golden net is NOT running. Install the dev extras with "
    '`pip install -e ".[dev]"` (or `pip install pytest-regressions==2.11.0`). '
    'Until then every golden errors at setup with "fixture not found" rather than '
    "failing, so the numeric and SQL surface Step 4 moves is unpinned while the "
    "suite still reports a pass."
)


def test_the_golden_plugins_are_registered(pytestconfig: pytest.Config) -> None:
    """
    The load-bearing check: without these the goldens do not run at all.

    Asserted through ``hasplugin`` rather than by importing, because registration
    with *this* pytest session is the property that matters - an importable
    distribution that failed to load as a plugin would leave the fixtures missing
    just the same.
    """
    missing = [
        name
        for name in REQUIRED_PLUGINS
        if not pytestconfig.pluginmanager.hasplugin(name)
    ]
    assert not missing, f"pytest plugins not registered: {missing}. {INSTALL_HINT}"


def test_every_golden_fixture_resolves(request: pytest.FixtureRequest) -> None:
    """
    Each fixture the goldens name is reachable, so a rename cannot pass silently.

    ``getfixturevalue`` builds the comparer object only; nothing is compared and no
    golden file is read or written, so this stays inert.
    """
    unresolved = []
    for name in GOLDEN_FIXTURES:
        try:
            request.getfixturevalue(name)
        except pytest.FixtureLookupError:
            unresolved.append(name)
    assert not unresolved, f"golden fixtures unavailable: {unresolved}. {INSTALL_HINT}"
