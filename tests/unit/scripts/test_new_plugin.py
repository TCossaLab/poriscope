"""
Tests for ``scripts/new_plugin.py``, the plugin scaffold generator.

The promise the generator makes is that its output is green against every gate before a
line of it is filled in, so these tests generate a stub for each of the eight data plugin
families plus two variants of shipped plugins and assert exactly that.

Four of the assertions stand in for a gate that cannot be shelled out to here. ``ruff``,
``mypy`` and ``black`` live in pre-commit's own virtualenvs and are on no PATH the test
suite can rely on, so instead of skipping the checks they are re-expressed directly:
resolving every annotation catches the same thing ruff's ``F821`` does (and caught a real
one - ``MetaEventFitter`` annotates methods with a module-level ``Numeric`` alias it does
not import), comparing imported names against used names catches ``F401``, asserting the
class is concrete catches a missed abstract method, and mypy's ``empty-body`` rule is what
the ``pass``-versus-``raise`` split in the generator exists to satisfy. ``pydoclint`` is a
real console script and is run for real when it is installed.

``scripts/`` is not a package, so the module under test is loaded by file path.
"""

import ast
import importlib.util
import inspect
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Set, get_type_hints

import pytest

from poriscope.utils.plugin_schemas import discover_plugin_classes, get_declared_schema
from poriscope.utils.settings_schema import validate_settings_schema

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(REPO_ROOT, "scripts", "new_plugin.py")

# One variant per shape that exists today: a second-level subclass overriding an abstract
# method of its family plus a non-abstract hook, and one overriding only a hook.
VARIANTS = [
    ("ClassicBlockageFinder", ["_find_events_in_chunk", "report_channel_status"]),
    ("SQLiteDBLoader", ["get_plot_features"]),
]


def load_script() -> types.ModuleType:
    """
    Import ``scripts/new_plugin.py`` by path, since ``scripts/`` is not a package.

    :return: the imported module
    :rtype: types.ModuleType
    """
    spec = importlib.util.spec_from_file_location("new_plugin", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> types.ModuleType:
    """
    Provide the generator module.

    :return: the imported module
    :rtype: types.ModuleType
    """
    return load_script()


@pytest.fixture(scope="module")
def shipped() -> Dict[str, Any]:
    """
    Provide every plugin that ships today, keyed by class name.

    :return: the discovered plugin classes
    :rtype: Dict[str, Any]
    """
    return discover_plugin_classes()


def generate(
    script: types.ModuleType, base: str, name: str, out: Path, overrides: List[str]
) -> Path:
    """
    Run the generator and return the file it wrote.

    :param script: the generator module
    :type script: types.ModuleType
    :param base: the family or shipped plugin to subclass
    :type base: str
    :param name: the new plugin's class name
    :type name: str
    :param out: the folder to generate into
    :type out: Path
    :param overrides: methods to override, for a variant of a shipped plugin
    :type overrides: List[str]
    :return: the path that was written
    :rtype: Path
    """
    argv = [base, name, "--output-dir", str(out), "--author", "Test Author"]
    if overrides:
        argv += ["--override", *overrides]
    assert script.main(argv) == 0
    path = Path(out, f"{name}.py")
    assert path.is_file()
    return path


def load_generated(path: Path, name: str) -> type:
    """
    Import a generated plugin file and return the class it defines.

    :param path: the generated file
    :type path: Path
    :param name: the class name, which is also the filename stem
    :type name: str
    :return: the generated class
    :rtype: type
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return getattr(module, name)


def own_methods(cls: type) -> Dict[str, Any]:
    """
    Get the functions a class defines in its own body.

    :param cls: the class to inspect
    :type cls: type
    :return: the functions, keyed by name
    :rtype: Dict[str, Any]
    """
    return {k: v for k, v in vars(cls).items() if callable(v)}


def stripped_signature(func: Any) -> inspect.Signature:
    """
    Get a signature with annotations removed, the way the compliance suite compares them.

    :param func: the function to inspect
    :type func: Any
    :return: the signature, with every annotation replaced by the empty marker
    :rtype: inspect.Signature
    """
    signature = inspect.signature(func)
    parameters = [
        p.replace(annotation=inspect.Parameter.empty)
        for p in signature.parameters.values()
    ]
    return signature.replace(
        parameters=parameters, return_annotation=inspect.Signature.empty
    )


def imported_names(tree: ast.Module) -> Set[str]:
    """
    Collect every name a module's import block binds.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: the bound names
    :rtype: Set[str]
    """
    bound: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bound |= {a.asname or a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            bound |= {a.asname or a.name for a in node.names}
    return bound


def referenced_names(tree: ast.Module) -> Set[str]:
    """
    Collect every bare name a module references anywhere outside its import block.

    :param tree: the parsed module
    :type tree: ast.Module
    :return: the referenced names
    :rtype: Set[str]
    """
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


@pytest.fixture(scope="module")
def families(script: types.ModuleType) -> List[str]:
    """
    Provide the eight family names the generator knows about.

    :param script: the generator module
    :type script: types.ModuleType
    :return: the family names
    :rtype: List[str]
    """
    return sorted(script.FAMILIES)


class TestGeneratedPluginsAreCompliant:
    """Every family and variant must produce a plugin that clears all four gates."""

    def _cases(self, script: types.ModuleType) -> List[tuple]:
        """
        Build the (base, name, overrides) tuples covering all ten cases.

        :param script: the generator module
        :type script: types.ModuleType
        :return: the cases
        :rtype: List[tuple]
        """
        cases = [(f, f"Generated{f}", []) for f in sorted(script.FAMILIES)]
        cases += [(b, f"Generated{b}Variant", o) for b, o in VARIANTS]
        return cases

    def test_every_case_produces_a_concrete_class(self, script, tmp_path):
        """A leftover abstract method is the one failure the whole tool exists to prevent."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            cls = load_generated(path, name)
            assert not inspect.isabstract(cls), f"{name} is still abstract"
            assert cls.__abstractmethods__ == frozenset(), name

    def test_every_annotation_resolves(self, script, tmp_path):
        """Stands in for ruff F821; this is what caught the unimported ``Numeric`` alias."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            cls = load_generated(path, name)
            module = sys.modules.get(cls.__module__)
            for method_name, func in own_methods(cls).items():
                get_type_hints(func, vars(module) if module else None)

    def test_no_pass_body_sits_under_a_non_none_return(self, script, tmp_path):
        """Stands in for mypy's empty-body rule, which the pass/raise split satisfies."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            klass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
            for node in klass.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                body = [
                    s
                    for s in node.body
                    if not (
                        isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                    )
                ]
                pass_only = len(body) == 1 and isinstance(body[0], ast.Pass)
                none_return = node.returns is None or (
                    isinstance(node.returns, ast.Constant)
                    and node.returns.value is None
                )
                assert not (pass_only and not none_return), f"{name}.{node.name}"

    def test_no_import_is_unused(self, script, tmp_path):
        """Stands in for ruff F401, which fails an import the generated file never uses."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            unused = imported_names(tree) - referenced_names(tree)
            assert not unused, f"{name} imports but never uses {sorted(unused)}"

    def test_signatures_match_the_base_exactly(self, script, tmp_path, shipped):
        """The compliance suite compares parameter names, order, kind and defaults."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            cls = load_generated(path, name)
            base_cls = cls.__mro__[1]
            for method_name, func in own_methods(cls).items():
                _, original = script.resolve_definition(base_cls, method_name)
                assert stripped_signature(func) == stripped_signature(
                    original
                ), f"{name}.{method_name} does not match {base_cls.__name__}"

    def test_every_method_has_a_docstring(self, script, tmp_path):
        """The compliance suite requires one on the class and on every method in it."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            cls = load_generated(path, name)
            assert cls.__doc__ and cls.__doc__.strip(), name
            for method_name, func in own_methods(cls).items():
                doc = inspect.getdoc(func)
                assert doc and doc.strip(), f"{name}.{method_name} has no docstring"

    def test_declared_schema_is_self_consistent(self, script, tmp_path):
        """The generated get_empty_settings example must pass the schema checker."""
        for base, name, overrides in self._cases(script):
            path = generate(script, base, name, tmp_path, overrides)
            cls = load_generated(path, name)
            assert validate_settings_schema(get_declared_schema(cls)) == []

    @pytest.mark.skipif(
        shutil.which("pydoclint") is None, reason="pydoclint is not on PATH"
    )
    def test_pydoclint_is_clean(self, script, tmp_path):
        """Run the real docstring/signature gate over every generated file."""
        for base, name, overrides in self._cases(script):
            generate(script, base, name, tmp_path, overrides)
        result = subprocess.run(
            ["pydoclint", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestGetEmptySettings:
    """The seven families with a concrete implementation must have super() called."""

    def test_super_is_called_where_the_base_implements_it(self, script, tmp_path):
        for family in sorted(script.FAMILIES):
            if family == "MetaFilter":
                continue
            path = generate(script, family, f"Super{family}", tmp_path, [])
            text = path.read_text(encoding="utf-8")
            assert "super().get_empty_settings(" in text, family

    def test_metafilter_authors_the_dict_instead(self, script, tmp_path):
        """MetaFilter declares it abstract, so there is nothing to delegate to."""
        path = generate(script, "MetaFilter", "AuthoredFilter", tmp_path, [])
        text = path.read_text(encoding="utf-8")
        assert "super().get_empty_settings(" not in text
        assert "settings: Dict[str, Dict[str, Any]] = {" in text

    def test_the_seeded_dependency_key_survives(self, script, tmp_path):
        """An event finder that loses the MetaReader key is silently unwired."""
        path = generate(script, "MetaEventFinder", "SeededFinder", tmp_path, [])
        cls = load_generated(path, "SeededFinder")
        assert "MetaReader" in get_declared_schema(cls)


class TestVariants:
    """A variant inherits a working plugin, so its overrides delegate rather than raise."""

    def test_overrides_delegate_to_super(self, script, tmp_path):
        path = generate(
            script, "ClassicBlockageFinder", "Delegating", tmp_path, ["_filter_events"]
        )
        text = path.read_text(encoding="utf-8")
        assert "return super()._filter_events(" in text
        assert "NotImplementedError" not in text

    def test_only_the_named_methods_are_stubbed(self, script, tmp_path):
        path = generate(
            script, "ClassicBlockageFinder", "Narrow", tmp_path, ["_filter_events"]
        )
        cls = load_generated(path, "Narrow")
        assert set(own_methods(cls)) == {"_filter_events", "get_empty_settings"}

    def test_an_unknown_override_is_refused(self, script, tmp_path, capsys):
        argv = [
            "ClassicBlockageFinder",
            "Bad",
            "--output-dir",
            str(tmp_path),
            "--override",
            "no_such_method",
        ]
        assert script.main(argv) == 1
        assert not Path(tmp_path, "Bad.py").exists()


class TestRefusals:
    """Every refusal happens before anything is written."""

    def test_an_unknown_base_is_refused(self, script, tmp_path):
        assert script.main(["NotABase", "Thing", "--output-dir", str(tmp_path)]) == 1
        assert list(tmp_path.glob("*.py")) == []

    def test_an_invalid_class_name_is_refused(self, script, tmp_path):
        assert (
            script.main(["MetaFilter", "not a name", "--output-dir", str(tmp_path)])
            == 1
        )
        assert list(tmp_path.glob("*.py")) == []

    def test_a_python_keyword_is_refused(self, script, tmp_path):
        assert script.main(["MetaFilter", "class", "--output-dir", str(tmp_path)]) == 1
        assert list(tmp_path.glob("*.py")) == []

    def test_a_name_a_shipped_plugin_already_has_is_refused(self, script, tmp_path):
        """Plugin names are unique across every family; the app only says so at startup."""
        assert (
            script.main(["MetaFilter", "BesselFilter", "--output-dir", str(tmp_path)])
            == 1
        )
        assert list(tmp_path.glob("*.py")) == []

    def test_an_existing_file_is_never_overwritten(self, script, tmp_path):
        generate(script, "MetaFilter", "Twice", tmp_path, [])
        before = Path(tmp_path, "Twice.py").read_text(encoding="utf-8")
        assert script.main(["MetaFilter", "Twice", "--output-dir", str(tmp_path)]) == 1
        assert Path(tmp_path, "Twice.py").read_text(encoding="utf-8") == before


class TestInteractive:
    """Run with no BASE or NAME, the tool asks rather than printing usage and quitting."""

    def _answers(self, monkeypatch, replies: List[str]) -> None:
        """
        Feed a scripted sequence of answers to the prompts.

        :param monkeypatch: pytest's monkeypatch fixture
        :type monkeypatch: Any
        :param replies: the answers to give, in order
        :type replies: List[str]
        :return: None
        :rtype: None
        """
        queue = list(replies)
        monkeypatch.setattr("builtins.input", lambda *a: queue.pop(0))

    def test_it_asks_its_way_to_a_new_plugin(self, script, tmp_path, monkeypatch):
        families = sorted(script.FAMILIES)
        self._answers(
            monkeypatch, ["1", str(families.index("MetaFilter") + 1), "Asked"]
        )
        assert script.main(["--output-dir", str(tmp_path)]) == 0
        cls = load_generated(Path(tmp_path, "Asked.py"), "Asked")
        assert cls.__mro__[1] is script.family_base("MetaFilter")

    def test_it_asks_its_way_to_a_variant(self, script, tmp_path, monkeypatch, shipped):
        names = sorted(shipped)
        self._answers(
            monkeypatch,
            [
                "2",
                str(names.index("BesselFilter") + 1),
                "_apply_filter",
                "AskedVariant",
            ],
        )
        assert script.main(["--output-dir", str(tmp_path)]) == 0
        cls = load_generated(Path(tmp_path, "AskedVariant.py"), "AskedVariant")
        assert cls.__mro__[1] is shipped["BesselFilter"]
        assert set(own_methods(cls)) == {"_apply_filter", "get_empty_settings"}

    def test_nothing_to_read_is_reported_rather_than_hung(
        self, script, tmp_path, monkeypatch, capsys
    ):
        """A CI step or a pipe reaches a prompt with no answer; it must exit, not wait."""

        def eof(*args: Any) -> str:
            raise EOFError

        monkeypatch.setattr("builtins.input", eof)
        assert script.main(["--output-dir", str(tmp_path)]) == 1
        assert "not run interactively" in capsys.readouterr().err
        assert list(tmp_path.glob("*.py")) == []


class TestFamilyTable:
    """The family table duplicates part of the app's own list; it must not drift."""

    def test_every_family_is_in_the_apps_allowed_base_classes(self, script):
        source = Path(REPO_ROOT, "poriscope", "models", "main_model.py").read_text(
            encoding="utf-8"
        )
        for family in script.FAMILIES:
            assert re.search(rf'"{family}":\s*{family},', source), family

    def test_every_family_folder_exists(self, script):
        for family, meta in script.FAMILIES.items():
            folder = Path(REPO_ROOT, "poriscope", "plugins", meta.folder)
            assert folder.is_dir(), f"{family} points at a missing folder {meta.folder}"

    def test_every_family_base_is_abstract(self, script):
        for family in script.FAMILIES:
            assert inspect.isabstract(script.family_base(family)), family

    def test_shipped_plugins_land_in_their_familys_folder(self, script, shipped):
        """The folder column is only useful if it matches where plugins actually are."""
        for name, cls in shipped.items():
            expected = script.FAMILIES[script.family_of(cls)].folder
            assert Path(inspect.getfile(cls)).parent.name == expected, name
