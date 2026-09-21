"""
Tests for ``scripts/measure_shell_complexity.py``, the app-shell complexity measure.

These drive the measure against small synthetic module texts rather than the real
shell files, so they pin the counting *rule* and do not move every time Step 5c
splits a method. The exceptions are the guards at the end: the file list is
deliberately explicit, so a renamed or newly added module must fail loudly rather
than silently shrink the measurement.

The rule is the number, so every construct that scores and every construct that
deliberately does not gets its own test. ``with`` is the one worth naming here: an
earlier ad-hoc measurement counted it as a branch, which scored a function worse
for using a context manager and hid ``remove_pages_except`` at exactly the
threshold. See the module docstring of the script under test.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import importlib.util
import textwrap
import types
from pathlib import Path
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "measure_shell_complexity.py")


def load_script() -> types.ModuleType:
    """
    Import ``scripts/measure_shell_complexity.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("measure_shell_complexity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> types.ModuleType:
    """
    The imported script, shared across the module's tests.

    :return: the imported module
    :rtype: types.ModuleType
    """
    return load_script()


def cx_of(mod: types.ModuleType, body: str) -> int:
    """
    Measure the complexity of a single synthetic function named ``f``.

    :param mod: the imported script
    :type mod: types.ModuleType
    :param body: the function's source, dedented by this helper
    :type body: str
    :return: the function's cyclomatic complexity
    :rtype: int
    """
    source = textwrap.dedent(body)
    collected = mod.collect_functions(source, "synthetic.py")
    assert len(collected) == 1, f"expected exactly one function, got {collected}"
    return int(collected[0][1])


class TestTheBaseCase:
    """A function with no decision points scores one."""

    def test_a_straight_line_function_is_one(self, mod: types.ModuleType) -> None:
        """Complexity counts paths, and straight-line code has exactly one."""
        assert (
            cx_of(
                mod,
                """
                def f():
                    a = 1
                    b = 2
                    return a + b
                """,
            )
            == 1
        )

    def test_an_empty_function_is_one(self, mod: types.ModuleType) -> None:
        """The abstract-hook ``pass`` bodies all over the plugin tree score one."""
        assert cx_of(mod, "\ndef f():\n    pass\n") == 1


class TestBranchesThatCount:
    """Every construct that adds a decision point."""

    def test_an_if_adds_one(self, mod: types.ModuleType) -> None:
        """One binary decision, two paths."""
        assert (
            cx_of(mod, "\ndef f(x):\n    if x:\n        return 1\n    return 0\n") == 2
        )

    def test_an_else_adds_nothing(self, mod: types.ModuleType) -> None:
        """``else`` is the other side of a decision already counted, not a new one."""
        assert (
            cx_of(
                mod,
                """
                def f(x):
                    if x:
                        return 1
                    else:
                        return 0
                """,
            )
            == 2
        )

    def test_each_elif_adds_one(self, mod: types.ModuleType) -> None:
        """``elif`` parses as a nested ``If``, so the walk picks it up on its own."""
        assert (
            cx_of(
                mod,
                """
                def f(x):
                    if x == 1:
                        return 1
                    elif x == 2:
                        return 2
                    elif x == 3:
                        return 3
                    return 0
                """,
            )
            == 4
        )

    def test_a_for_adds_one(self, mod: types.ModuleType) -> None:
        """A loop is a decision taken once per iteration plus once to leave."""
        assert cx_of(mod, "\ndef f(xs):\n    for x in xs:\n        print(x)\n") == 2

    def test_a_while_adds_one(self, mod: types.ModuleType) -> None:
        """Same as ``for``."""
        assert cx_of(mod, "\ndef f(n):\n    while n:\n        n -= 1\n") == 2

    def test_each_except_handler_adds_one(self, mod: types.ModuleType) -> None:
        """
        Each handler is a path out of the ``try``; the ``try`` itself is not one.

        The shell's report-then-return blocks are built out of these, so the count
        has to track handlers rather than ``try`` statements.
        """
        assert (
            cx_of(
                mod,
                """
                def f():
                    try:
                        go()
                    except ValueError:
                        pass
                    except KeyError:
                        pass
                """,
            )
            == 3
        )

    def test_a_ternary_adds_one(self, mod: types.ModuleType) -> None:
        """An inline conditional branches exactly as a statement ``if`` does."""
        assert cx_of(mod, "\ndef f(x):\n    return 1 if x else 0\n") == 2

    def test_a_boolop_counts_each_short_circuit(self, mod: types.ModuleType) -> None:
        """
        ``a and b and c`` has two points at which it can stop early, so it adds two.

        Counting the ``BoolOp`` node once instead would score ``a and b and c`` the
        same as ``a and b``, which is what the earlier ad-hoc measurement did.
        """
        assert cx_of(mod, "\ndef f(a, b, c):\n    return a and b and c\n") == 3
        assert cx_of(mod, "\ndef f(a, b):\n    return a or b\n") == 2

    def test_a_comprehension_counts_per_generator(self, mod: types.ModuleType) -> None:
        """A comprehension carries its loop with it, and a nested one carries two."""
        assert cx_of(mod, "\ndef f(xs):\n    return [x for x in xs]\n") == 2
        assert (
            cx_of(mod, "\ndef f(xs, ys):\n    return [x for x in xs for y in ys]\n")
            == 3
        )

    def test_a_comprehension_filter_adds_one(self, mod: types.ModuleType) -> None:
        """The ``if`` in a comprehension is a decision like any other."""
        assert cx_of(mod, "\ndef f(xs):\n    return [x for x in xs if x]\n") == 3

    def test_every_comprehension_form_counts(self, mod: types.ModuleType) -> None:
        """Set, dict and generator comprehensions score as the list form does."""
        assert cx_of(mod, "\ndef f(xs):\n    return {x for x in xs}\n") == 2
        assert cx_of(mod, "\ndef f(xs):\n    return {x: x for x in xs}\n") == 2
        assert cx_of(mod, "\ndef f(xs):\n    return sum(x for x in xs)\n") == 2

    def test_each_match_case_adds_one(self, mod: types.ModuleType) -> None:
        """``match`` is an n-way branch, so each case is a path."""
        assert (
            cx_of(
                mod,
                """
                def f(x):
                    match x:
                        case 1:
                            return "a"
                        case 2:
                            return "b"
                """,
            )
            == 3
        )


class TestConstructsThatDeliberatelyDoNotCount:
    """
    The rule's deviations from "anything that looks like control flow".

    Each of these is a deliberate exclusion, and each is load-bearing for the
    recorded baseline, so each is pinned rather than left to inference.
    """

    def test_a_with_block_is_not_a_branch(self, mod: types.ModuleType) -> None:
        """
        ``with`` is straight-line code and must not be scored as a decision.

        This is the deviation that matters most. The project requires explicit
        resource cleanup, so counting ``with`` would score correct code worse: it
        inflated ``create_appdata_folders`` from 17 to 20 on its four ``with``
        blocks alone, purely for opening its files properly.
        """
        assert (
            cx_of(
                mod,
                """
                def f(path):
                    with open(path) as handle:
                        return handle.read()
                """,
            )
            == 1
        )

    def test_a_try_without_handlers_is_not_a_branch(
        self, mod: types.ModuleType
    ) -> None:
        """``try``/``finally`` with no handler adds no path through the function."""
        assert (
            cx_of(
                mod,
                """
                def f():
                    try:
                        go()
                    finally:
                        clean()
                """,
            )
            == 1
        )

    def test_an_assert_is_not_a_branch(self, mod: types.ModuleType) -> None:
        """
        ``assert`` is excluded, so a debug check cannot push a function over the gate.

        It changes nothing in the shell today - no scoped function has one - so it
        is excluded as the simpler rule rather than on evidence.
        """
        assert cx_of(mod, "\ndef f(x):\n    assert x\n    return x\n") == 1

    def test_an_early_return_is_not_a_branch(self, mod: types.ModuleType) -> None:
        """
        A ``return`` is a path already counted by whatever decided to reach it.

        Counting returns as well would double-count every guard clause, which is
        exactly the shape 5c.2 is about to extract.
        """
        assert (
            cx_of(
                mod,
                """
                def f(x):
                    if x:
                        return 1
                    return 0
                """,
            )
            == 2
        )


class TestCollection:
    """Which functions are measured, and under what name."""

    def test_finds_module_level_functions_and_methods(
        self, mod: types.ModuleType
    ) -> None:
        """The scope is module-level functions plus methods of module-level classes."""
        source = textwrap.dedent(
            """
            def loose():
                pass

            class Thing:
                def method(self):
                    pass
            """
        )
        names = [name for name, _ in mod.collect_functions(source, "synthetic.py")]
        assert names == ["loose", "Thing.method"]

    def test_a_nested_function_is_not_reported_separately(
        self, mod: types.ModuleType
    ) -> None:
        """
        A closure is scored inside its parent, not alongside it.

        Reporting both would count the closure's branches twice in the totals. This
        matches ``measure_duplication.py``, which skips nested functions for the
        same reason, so the two instruments agree on what a function is.
        """
        source = textwrap.dedent(
            """
            def outer(xs):
                def inner(x):
                    if x:
                        return 1
                    return 0
                return [inner(x) for x in xs]
            """
        )
        collected = mod.collect_functions(source, "synthetic.py")
        assert [name for name, _ in collected] == ["outer"]

    def test_a_nested_function_contributes_to_its_parent(
        self, mod: types.ModuleType
    ) -> None:
        """The closure's own branch still counts, because reading the parent means reading it."""
        source = textwrap.dedent(
            """
            def outer(xs):
                def inner(x):
                    if x:
                        return 1
                    return 0
                return [inner(x) for x in xs]
            """
        )
        # 1 base + 1 for inner's ``if`` + 1 for the comprehension's generator.
        assert dict(mod.collect_functions(source, "synthetic.py"))["outer"] == 3

    def test_an_async_function_is_measured(self, mod: types.ModuleType) -> None:
        """``async def`` is a function like any other."""
        source = "\nasync def f(x):\n    if x:\n        return 1\n    return 0\n"
        assert dict(mod.collect_functions(source, "synthetic.py"))["f"] == 2

    def test_a_syntax_error_propagates(self, mod: types.ModuleType) -> None:
        """An unparseable file is a failure to report, never a file measured as zero."""
        with pytest.raises(SyntaxError):
            mod.collect_functions("def f(:\n    pass\n", "synthetic.py")


class TestTheThreshold:
    """Only functions above the threshold are recorded, and the totals follow them."""

    def test_the_threshold_is_ten(self, mod: types.ModuleType) -> None:
        """Pinned so a change to it is a deliberate edit with a baseline update."""
        assert mod.THRESHOLD == 10

    def test_a_function_at_the_threshold_is_not_recorded(
        self, mod: types.ModuleType
    ) -> None:
        """The gate is strictly above, so exactly ten is under it."""
        source = "\ndef f(x):\n" + "".join(
            f"    if x == {i}:\n        return {i}\n" for i in range(9)
        )
        assert dict(mod.collect_functions(source, "synthetic.py"))["f"] == 10
        assert mod.measure_source(source, "synthetic.py")["over_threshold"] == 0

    def test_a_function_above_the_threshold_is_recorded(
        self, mod: types.ModuleType
    ) -> None:
        """One more branch takes the same function over."""
        source = "\ndef f(x):\n" + "".join(
            f"    if x == {i}:\n        return {i}\n" for i in range(10)
        )
        measured = mod.measure_source(source, "synthetic.py")
        assert measured["over_threshold"] == 1
        assert measured["total_complexity"] == 11

    def test_total_complexity_sums_only_the_functions_over_the_threshold(
        self, mod: types.ModuleType
    ) -> None:
        """
        The total is the weight of the problem, not the weight of the file.

        Summing every function would move on any edit anywhere in the file and
        would make the gate unreadable as a measure of how much is left to do.
        """
        over = "\ndef big(x):\n" + "".join(
            f"    if x == {i}:\n        return {i}\n" for i in range(10)
        )
        under = "\ndef small(x):\n    if x:\n        return 1\n    return 0\n"
        measured = mod.measure_source(over + under, "synthetic.py")
        assert measured["functions"] == 2
        assert measured["over_threshold"] == 1
        assert measured["total_complexity"] == 11

    def test_functions_counts_everything_scanned(self, mod: types.ModuleType) -> None:
        """``functions`` is the whole file, which is what makes an escape visible."""
        source = "\ndef a():\n    pass\n\ndef b():\n    pass\n"
        assert mod.measure_source(source, "synthetic.py")["functions"] == 2


class TestComparison:
    """The ratchet's verdicts, which are exact in both directions."""

    @staticmethod
    def entry(functions: int = 10, over: int = 1, total: int = 20) -> Dict[str, int]:
        """
        Build one file's baseline entry.

        :param functions: the number of functions scanned in the file
        :type functions: int
        :param over: the number of functions above the threshold
        :type over: int
        :param total: the summed complexity of those functions
        :type total: int
        :return: a baseline entry
        :rtype: Dict[str, int]
        """
        return {
            "functions": functions,
            "over_threshold": over,
            "total_complexity": total,
        }

    def test_identical_measurements_agree(self, mod: types.ModuleType) -> None:
        """The quiet case: nothing to say."""
        current = {"a.py": self.entry()}
        assert mod.compare(current, {"a.py": self.entry()}) == []

    def test_a_rise_is_reported_as_added_complexity(
        self, mod: types.ModuleType
    ) -> None:
        """Going up is a regression and must fail."""
        problems = mod.compare(
            {"a.py": self.entry(total=25)}, {"a.py": self.entry(total=20)}
        )
        assert len(problems) == 1
        assert "rose from 20 to 25" in problems[0]

    def test_a_fall_asks_for_the_baseline_to_be_updated(
        self, mod: types.ModuleType
    ) -> None:
        """
        Going down fails too, so the win is banked in the commit that earned it.

        Under ``<=`` the baseline would drift above reality and the slack would
        accrue unnoticed, which is the whole reason the duplication ratchet is
        exact as well.
        """
        problems = mod.compare(
            {"a.py": self.entry(total=15)}, {"a.py": self.entry(total=20)}
        )
        assert len(problems) == 1
        assert "--update" in problems[0]

    def test_a_new_file_is_reported(self, mod: types.ModuleType) -> None:
        """A measured file absent from the baseline means the baseline is stale."""
        problems = mod.compare({"a.py": self.entry()}, {})
        assert problems and "absent from the baseline" in problems[0]

    def test_a_dropped_file_is_reported(self, mod: types.ModuleType) -> None:
        """A baselined file no longer measured means the scope shrank silently."""
        problems = mod.compare({}, {"a.py": self.entry()})
        assert problems and "no longer measured" in problems[0]

    def test_a_split_into_helpers_is_not_flagged_as_an_escape(
        self, mod: types.ModuleType
    ) -> None:
        """
        The intended shape: complexity falls while the function count rises.

        Splitting ``edit_plugin`` into named helpers on the same class leaves every
        piece in scope, so this is a real win and must not carry a warning.
        """
        problems = mod.compare(
            {"a.py": self.entry(functions=15, over=0, total=0)},
            {"a.py": self.entry(functions=10, over=1, total=20)},
        )
        assert all("left the measured scope" not in p for p in problems)

    def test_complexity_moved_out_of_scope_is_called_out(
        self, mod: types.ModuleType
    ) -> None:
        """
        Complexity falling *with* the function count is an escape, not a win.

        Moving a complex method into a module the file list does not name reads as
        progress here while the code is untouched. The two cases are distinguishable
        without any extra measurement, because a genuine split leaves the pieces in
        the file and raises ``functions``.
        """
        problems = mod.compare(
            {"a.py": self.entry(functions=9, over=0, total=0)},
            {"a.py": self.entry(functions=10, over=1, total=20)},
        )
        assert any("left the measured scope" in p for p in problems)

    def test_to_baseline_drops_the_per_function_detail(
        self, mod: types.ModuleType
    ) -> None:
        """
        The baseline records counts only.

        The per-function list is useful to read and useless to diff: it would churn
        the baseline on every rename and bury the number the ratchet is about.
        """
        results = mod.measure()
        reduced = mod.to_baseline(results)
        for entry in reduced.values():
            assert set(entry) == {"functions", "over_threshold", "total_complexity"}


class TestTheScopeGuards:
    """
    The file list is explicit, so it has to be kept honest by a test.

    ``measure_duplication.py`` learned this the hard way: a case-sensitive glob
    silently dropped 742 lines from a family. Here the risk is the mirror image -
    a helper module added beside the ones listed, carrying complexity the gate
    never sees.
    """

    def test_every_shell_file_exists(self, mod: types.ModuleType) -> None:
        """A renamed file must fail loudly rather than shrink the measurement."""
        missing = [name for name in mod.SHELL_FILES if not (REPO_ROOT / name).is_file()]
        assert not missing, (
            f"named in SHELL_FILES but absent from the repository: {missing}. "
            f"The list is deliberately explicit, so update it."
        )

    def test_the_scoped_packages_are_fully_enumerated(
        self, mod: types.ModuleType
    ) -> None:
        """
        Nothing may sit in ``controllers/`` or ``models/`` without being measured.

        This is the escape hatch that matters for Step 5c: splitting a god-method
        into a new module in the same package would otherwise take its complexity
        out of the gate's sight and read as a win.
        """
        listed = set(mod.SHELL_FILES)
        for package in mod.SCOPED_PACKAGES:
            for path in sorted((REPO_ROOT / package).glob("*.py")):
                rel = path.relative_to(REPO_ROOT).as_posix()
                assert rel in listed, (
                    f"{rel} is in the scoped package {package} but is not in "
                    f"SHELL_FILES, so its complexity is unmeasured. Add it and "
                    f"rerun `python scripts/measure_shell_complexity.py --update`."
                )

    def test_the_file_list_matches_the_recorded_scope(
        self, mod: types.ModuleType
    ) -> None:
        """
        Nine files, as ``DECISIONS.md`` records for the 2026-09-20 scoping decision.

        Pinned because the figure is quoted in the decision, the plan and the QA
        page; a change to the scope has to be a deliberate edit that updates them.
        """
        assert len(mod.SHELL_FILES) == 9
        assert len(set(mod.SHELL_FILES)) == 9

    def test_the_owner_held_and_flat_qt_code_is_out_of_scope(
        self, mod: types.ModuleType
    ) -> None:
        """
        The gate is the shell, not the repository.

        Repo-wide there are 124 functions over 80 lines, most in owner-held fitters
        and in the ``setupUi`` methods the plan keeps per-tab, so a repo-wide gate
        would fail on commits that are not ours to gate.
        """
        for name in mod.SHELL_FILES:
            assert not name.startswith("poriscope/plugins/"), (
                f"{name} is a plugin file; the shell gate must not reach into the "
                f"plugin tree, which is measured by the duplication ratchet instead."
            )
