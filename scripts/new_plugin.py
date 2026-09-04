# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs

"""
Generate a compliant starting point for a new Poriscope plugin.

    python scripts/new_plugin.py                            # ask what to build
    python scripts/new_plugin.py --list                     # show both menus
    python scripts/new_plugin.py MetaEventFinder MyFinder   # new plugin from a base class
    python scripts/new_plugin.py ClassicBlockageFinder MyVariant --override _filter_events

BASE is either one of the eight ``Meta*`` data plugin base classes, in which case every
abstract method it declares is stubbed out, or the name of a plugin that already ships,
in which case the new plugin inherits everything and stubs out only what ``--override``
names.

Method signatures and docstrings are copied verbatim out of the base class, because
``tests/unit/plugins/test_plugin_compliance.py`` compares signatures for exact equality
and annotations by equality for anything generic. The generated file passes ruff, mypy,
pydoclint and the plugin compliance suite before a line of it is filled in.
"""

import argparse
import ast
import importlib
import inspect
import json
import keyword
import logging
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import (
    Any,
    Dict,
    FrozenSet,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
)

from platformdirs import user_data_dir

from poriscope.utils.BaseDataPlugin import BaseDataPlugin
from poriscope.utils.plugin_schemas import discover_plugin_classes

REPO_ROOT = Path(__file__).resolve().parent.parent

LICENSE_HEADER = """# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
"""


class Family(NamedTuple):
    """
    One data plugin family: its base class, where its plugins live, and what it does.

    :param module: the module the base class is defined in
    :type module: str
    :param folder: the folder under ``poriscope/plugins/`` its subclasses live in
    :type folder: str
    :param summary: one line describing what a plugin in this family is responsible for
    :type summary: str
    """

    module: str
    folder: str
    summary: str


# The eight data plugin families. The folder column is the reason this table exists at
# all: nothing else in the repository maps a base class to its plugin folder, and the
# names are not guessable from the base class ("datawriters" for MetaWriter but
# "dbwriters" for MetaDatabaseWriter, and "db_loaders" with an underscore).
#
# The analysis tab families (MetaController/MetaModel/MetaView) are deliberately absent:
# they are a three-file triad rather than a single file, and are queued separately in
# future_fixes.md. A test asserts these keys are a subset of the canonical base class
# list in MainModel.populate_available_plugins, so the two cannot drift apart silently.
FAMILIES: Dict[str, Family] = {
    "MetaReader": Family(
        "poriscope.utils.MetaReader",
        "datareaders",
        "read raw timeseries out of a file format",
    ),
    "MetaFilter": Family(
        "poriscope.utils.MetaFilter",
        "filters",
        "transform a chunk of timeseries data",
    ),
    "MetaEventFinder": Family(
        "poriscope.utils.MetaEventFinder",
        "eventfinders",
        "flag event start and end times in a chunk",
    ),
    "MetaWriter": Family(
        "poriscope.utils.MetaWriter",
        "datawriters",
        "write extracted event traces out to a file",
    ),
    "MetaEventLoader": Family(
        "poriscope.utils.MetaEventLoader",
        "eventloaders",
        "read extracted events back out of a file",
    ),
    "MetaEventFitter": Family(
        "poriscope.utils.MetaEventFitter",
        "eventfitters",
        "fit sublevels and extract event metadata",
    ),
    "MetaDatabaseWriter": Family(
        "poriscope.utils.MetaDatabaseWriter",
        "dbwriters",
        "write fitted event metadata to a database",
    ),
    "MetaDatabaseLoader": Family(
        "poriscope.utils.MetaDatabaseLoader",
        "db_loaders",
        "query event metadata back out of a database",
    ),
}

# Methods a plugin may usefully override that are abstract in no family. The first three
# have concrete implementations on BaseDataPlugin or the family base; get_plot_features
# exists only on MetaEventFitter. Every override in the six plugins that ship today as
# variants of another plugin falls inside this set plus the family's own abstract
# methods, which is where the set comes from.
OPTIONAL_HOOKS: Tuple[str, ...] = (
    "report_channel_status",
    "force_serial_channel_operations",
    "get_plot_features",
)

# Reaching a prompt with nothing to read means the tool was run without arguments from
# somewhere that cannot answer - a CI step, or a pipe. Say so rather than hanging or
# reporting an empty answer as if the user had given one.
NOT_INTERACTIVE = (
    "BASE and NAME are required when this is not run interactively.\n"
    "Run 'python scripts/new_plugin.py --list' to see what you can subclass."
)

SETTINGS = "get_empty_settings"
STUB_RAISE = "NotImplementedError"

_RAISES = re.compile(r"^\s*:raises\s+([A-Za-z_][A-Za-z0-9_.]*)\s*:\s*(.*)$")
_FIELD = re.compile(r"^\s*:([a-zA-Z]+)")


class GenerationError(Exception):
    """Raised when the requested plugin cannot be generated."""


class ImportSpec(NamedTuple):
    """
    One importable name, recorded so it can be re-emitted in the generated file.

    :param module: the module the name comes from
    :type module: str
    :param name: the name imported from that module, or None for a plain ``import``
    :type name: Optional[str]
    :param asname: the alias the name is bound to, if any
    :type asname: Optional[str]
    """

    module: str
    name: Optional[str]
    asname: Optional[str]


class Stub(NamedTuple):
    """
    One rendered method stub, plus what its imports have to be resolved against.

    :param text: the full method text, indented ready to drop into a class body
    :type text: str
    :param names: every name the signature's annotations and defaults reference
    :type names: FrozenSet[str]
    :param defining_module: the module the signature was copied out of
    :type defining_module: str
    """

    text: str
    names: FrozenSet[str]
    defining_module: str


def annotation_names(node: ast.FunctionDef) -> FrozenSet[str]:
    """
    Collect every name a signature's annotations and default values reference.

    Reading these off the AST rather than scanning the signature text is what keeps
    parameter names out of the set. A parameter called ``data`` must not cause a
    module-level ``data`` in the base's module to be imported into the generated file.

    :param node: the parsed function node
    :type node: ast.FunctionDef
    :return: the referenced names
    :rtype: FrozenSet[str]
    """
    args = node.args
    expressions: List[ast.expr] = [a.annotation for a in args.args if a.annotation]
    expressions += [a.annotation for a in args.kwonlyargs if a.annotation]
    expressions += [a for a in args.defaults if a is not None]
    expressions += [a for a in args.kw_defaults if a is not None]
    if node.returns is not None:
        expressions.append(node.returns)
    found: Set[str] = set()
    for expression in expressions:
        found |= {n.id for n in ast.walk(expression) if isinstance(n, ast.Name)}
    return frozenset(found)


def family_base(family: str) -> type:
    """
    Get a family's base class, importing its module if that has not happened yet.

    :param family: one of the eight family names
    :type family: str
    :return: the base class
    :rtype: type
    """
    module = importlib.import_module(FAMILIES[family].module)
    return getattr(module, family)


def family_of(plugin_cls: type) -> str:
    """
    Report which of the eight families a plugin class belongs to.

    :param plugin_cls: the plugin class to classify
    :type plugin_cls: type
    :raises GenerationError: if the class belongs to no known family
    :return: the family's base class name
    :rtype: str
    """
    for family in FAMILIES:
        if issubclass(plugin_cls, family_base(family)):
            return family
    raise GenerationError(f"{plugin_cls.__name__} belongs to no known plugin family")


def resolve_definition(cls: type, name: str) -> Tuple[type, Any]:
    """
    Find the closest class in the MRO that actually defines a method.

    :param cls: the class whose MRO should be searched
    :type cls: type
    :param name: the method name to look for
    :type name: str
    :raises GenerationError: if no class in the MRO defines the method
    :return: the defining class and the function object it holds
    :rtype: Tuple[type, Any]
    """
    for klass in cls.__mro__:
        if name in klass.__dict__:
            return klass, klass.__dict__[name]
    raise GenerationError(f"{cls.__name__} has no method named {name}")


def parse_method(cls: type, name: str) -> Tuple[type, List[str], ast.FunctionDef]:
    """
    Get a method's dedented source lines and its parsed AST node.

    :param cls: the class whose MRO should be searched for the method
    :type cls: type
    :param name: the method name
    :type name: str
    :raises GenerationError: if the source cannot be read or is not a function
    :return: the defining class, its dedented source lines, and the function node
    :rtype: Tuple[type, List[str], ast.FunctionDef]
    """
    defining_cls, func = resolve_definition(cls, name)
    try:
        source = textwrap.dedent(inspect.getsource(func))
    except (OSError, TypeError) as exc:
        raise GenerationError(f"cannot read the source of {name}: {exc}") from exc
    node = ast.parse(source).body[0]
    if not isinstance(node, ast.FunctionDef):
        raise GenerationError(f"{name} is not a plain function definition")
    return defining_cls, source.splitlines(), node


def split_signature_and_docstring(
    lines: List[str], node: ast.FunctionDef
) -> Tuple[List[str], List[str]]:
    """
    Slice a method's source into its signature lines and its docstring lines.

    Slicing the original text rather than rebuilding it from the AST is deliberate: it
    preserves black's formatting of multi-line signatures exactly, and it is what makes
    the copied annotations compare equal to the base class's under the compliance
    suite's equality check.

    :param lines: the method's dedented source lines
    :type lines: List[str]
    :param node: the parsed function node
    :type node: ast.FunctionDef
    :return: the signature lines, and the docstring lines or empty if there is none
    :rtype: Tuple[List[str], List[str]]
    """
    first = node.body[0]
    has_docstring = (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )
    if not has_docstring:
        return lines[node.lineno - 1 : first.lineno - 1], []
    start = first.lineno - 1
    end = first.end_lineno or first.lineno
    return lines[node.lineno - 1 : start], lines[start:end]


def returns_none(node: ast.FunctionDef) -> bool:
    """
    Report whether a method is annotated as returning None.

    This decides the stub's body. mypy's ``empty-body`` check rejects a ``pass`` body
    under any other return annotation, so these are the only methods that can be stubbed
    as no-ops - which is also the set for which a no-op is a legitimate implementation.

    :param node: the parsed function node
    :type node: ast.FunctionDef
    :return: True if the method returns None
    :rtype: bool
    """
    if node.returns is None:
        return True
    return isinstance(node.returns, ast.Constant) and node.returns.value is None


def normalise_docstring(doc_lines: List[str], indent: str) -> List[str]:
    """
    Expand a one-line docstring onto three lines so fields can be inserted into it.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :param indent: the leading whitespace the docstring is written at
    :type indent: str
    :return: the docstring lines, guaranteed to end on a line holding only the quotes
    :rtype: List[str]
    """
    if len(doc_lines) == 1:
        inner = doc_lines[0].strip().strip('"').strip()
        return [f'{indent}"""', f"{indent}{inner}", f'{indent}"""']
    return doc_lines


def docstring_indent(doc_lines: List[str], default: str = "    ") -> str:
    """
    Get the indentation a docstring's body is written at.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :param default: what to fall back on when the docstring has no body lines
    :type default: str
    :return: the leading whitespace to use for inserted lines
    :rtype: str
    """
    for line in doc_lines[1:]:
        if line.strip():
            return line[: len(line) - len(line.lstrip())]
    return default


def strip_raises_fields(doc_lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Pull every ``:raises:`` field out of a docstring, restating each as a prose line.

    Measured against the pydoclint this repository pins, every naive combination fails:
    a copied ``:raises ValueError:`` above a ``pass`` body is DOC502, the same field
    above a ``raise NotImplementedError`` body is DOC503, and raising with no field at
    all is DOC501. The contract therefore cannot stay in a field - but it is worth
    keeping, so it moves into the prose block where the contributor still reads it.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :return: the docstring without its raises fields, and the prose replacing them
    :rtype: Tuple[List[str], List[str]]
    """
    kept: List[str] = []
    prose: List[str] = []
    in_raises = False
    for line in doc_lines:
        match = _RAISES.match(line)
        if match:
            in_raises = True
            exception, description = match.groups()
            prose.append(
                f"Your implementation must raise ``{exception}``: {description}".rstrip()
            )
            continue
        continuation = (
            in_raises
            and line.strip()
            and '"""' not in line
            and _FIELD.match(line) is None
        )
        if continuation:
            prose[-1] = f"{prose[-1]} {line.strip()}"
            continue
        in_raises = False
        kept.append(line)
    return kept, prose


def hoist_trailing_prose(doc_lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Move any prose written after a docstring's field block up out of it.

    A handful of the base classes end a docstring with prose rather than with its last
    field - ``MetaDatabaseLoader.add_columns_to_table`` puts its ``**Purpose:**`` block
    after ``:rtype:``. Sphinx field parsers attach that prose to whichever field precedes
    it, which is harmless while a ``:raises:`` field sits in between and becomes DOC203
    the moment this scaffold strips those fields out. Hoisting the prose to where it
    belongs fixes the cause rather than the symptom.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :return: the docstring without its trailing prose, and that prose unindented
    :rtype: Tuple[List[str], List[str]]
    """
    last_field = max(
        (i for i, line in enumerate(doc_lines) if _FIELD.match(line)), default=-1
    )
    if last_field < 0:
        return doc_lines, []
    closing = len(doc_lines) - 1 if doc_lines[-1].strip() == '"""' else len(doc_lines)
    # A line directly under the last field continues it; prose starts after a blank.
    start = next(
        (i for i in range(last_field + 1, closing) if not doc_lines[i].strip()), closing
    )
    prose = [line.strip() for line in doc_lines[start:closing]]
    while prose and not prose[0]:
        prose.pop(0)
    while prose and not prose[-1]:
        prose.pop()
    return doc_lines[:start] + doc_lines[closing:], prose


def insert_prose(doc_lines: List[str], prose: List[str], indent: str) -> List[str]:
    """
    Put prose lines at the end of a docstring's prose block, before its first field.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :param prose: the prose lines to insert, without indentation
    :type prose: List[str]
    :param indent: the leading whitespace to write them at
    :type indent: str
    :return: the docstring lines with the prose inserted
    :rtype: List[str]
    """
    if not prose:
        return doc_lines
    block = [f"{indent}{line}" if line else "" for line in prose]
    for index, line in enumerate(doc_lines):
        if _FIELD.match(line):
            return splice_lines(
                doc_lines[:index], block, doc_lines[index:], blank_after=True
            )
    return splice_lines(doc_lines[:-1], block, doc_lines[-1:], blank_after=False)


def splice_lines(
    before: List[str], block: List[str], after: List[str], blank_after: bool
) -> List[str]:
    """
    Insert a block of lines between two halves without ever doubling a blank line.

    :param before: the lines the block goes after
    :type before: List[str]
    :param block: the lines to insert
    :type block: List[str]
    :param after: the lines the block goes before
    :type after: List[str]
    :param blank_after: whether the block should be followed by a blank line
    :type blank_after: bool
    :return: the joined lines
    :rtype: List[str]
    """
    lead = [] if before and not before[-1].strip() else [""]
    trail = [""] if blank_after and after and after[0].strip() else []
    return before + lead + block + trail + after


def insert_raises_field(doc_lines: List[str], indent: str) -> List[str]:
    """
    Add the ``:raises NotImplementedError:`` field a raising stub body needs.

    :param doc_lines: the docstring's source lines
    :type doc_lines: List[str]
    :param indent: the leading whitespace to write the field at
    :type indent: str
    :return: the docstring lines with the field inserted
    :rtype: List[str]
    """
    field = f"{indent}:raises {STUB_RAISE}: this stub has not been written yet"
    for index, line in enumerate(doc_lines):
        match = _FIELD.match(line)
        if match and match.group(1) in ("return", "rtype"):
            return doc_lines[:index] + [field] + doc_lines[index:]
    return doc_lines[:-1] + [field] + doc_lines[-1:]


def placeholder_docstring(name: str, indent: str) -> List[str]:
    """
    Build a docstring for a base method that has none of its own.

    The compliance suite requires every method in a plugin's class body to carry a
    non-empty docstring, so a stub cannot simply inherit the gap.

    :param name: the method name
    :type name: str
    :param indent: the leading whitespace to write the docstring at
    :type indent: str
    :return: the docstring lines
    :rtype: List[str]
    """
    return [
        f'{indent}"""',
        f"{indent}TODO: describe what {name} does in your plugin.",
        f'{indent}"""',
    ]


def build_docstring(
    doc_lines: List[str], name: str, stub_raises: bool, indent: str
) -> List[str]:
    """
    Turn a base method's docstring into one a stub can carry past every gate.

    :param doc_lines: the base's docstring source lines, empty if it has none
    :type doc_lines: List[str]
    :param name: the method name, used if a placeholder has to be invented
    :type name: str
    :param stub_raises: whether the stub body raises NotImplementedError
    :type stub_raises: bool
    :param indent: the leading whitespace the docstring will be written at
    :type indent: str
    :return: the docstring lines
    :rtype: List[str]
    """
    if not doc_lines:
        built = placeholder_docstring(name, indent)
    else:
        normalised = normalise_docstring(doc_lines, indent)
        kept, prose = strip_raises_fields(normalised)
        kept, trailing = hoist_trailing_prose(kept)
        built = insert_prose(kept, trailing + prose, docstring_indent(kept, indent))
    if stub_raises:
        built = insert_raises_field(built, docstring_indent(built, indent))
    return built


def super_call(node: ast.FunctionDef) -> str:
    """
    Build a ``super()`` delegation passing every parameter straight through.

    :param node: the parsed function node
    :type node: ast.FunctionDef
    :return: the call expression, without a ``return`` keyword
    :rtype: str
    """
    args = [arg.arg for arg in node.args.args if arg.arg != "self"]
    args += [f"{arg.arg}={arg.arg}" for arg in node.args.kwonlyargs]
    return f"super().{node.name}({', '.join(args)})"


def render_stub(cls: type, name: str, delegate: bool) -> Stub:
    """
    Render one method stub, copying its signature and docstring out of the base class.

    :param cls: the class the new plugin will inherit from
    :type cls: type
    :param name: the method to stub
    :type name: str
    :param delegate: if True the body calls ``super()`` rather than standing unwritten
    :type delegate: bool
    :return: the rendered stub
    :rtype: Stub
    """
    defining_cls, lines, node = parse_method(cls, name)
    sig_lines, doc_lines = split_signature_and_docstring(lines, node)
    is_none = returns_none(node)

    todo = f"    # TODO: {'narrow' if delegate else 'implement'} {name}"
    if delegate:
        call = super_call(node)
        body = [todo, f"    {call}" if is_none else f"    return {call}"]
        stub_raises = False
    elif is_none:
        body = [todo, "    pass"]
        stub_raises = False
    else:
        body = [todo, f'    raise {STUB_RAISE}("{name} is not implemented")']
        stub_raises = True

    doc = build_docstring(doc_lines, name, stub_raises, "    ")
    parts = ["@log(logger=logger)", "@override", *sig_lines, *doc, *body]
    return Stub(
        textwrap.indent("\n".join(parts), "    "),
        annotation_names(node),
        defining_cls.__module__,
    )


def render_settings_stub(cls: type) -> Stub:
    """
    Render a ``get_empty_settings`` override, calling ``super()`` wherever that is real.

    Seven of the eight families implement this concretely and seed mandatory keys in it -
    the reader an event finder depends on, the output file a writer needs - so an
    override that forgets the ``super()`` call silently loses the plugin's dependency
    wiring, and nothing checks for that. It is written out rather than described. On
    MetaFilter, where the method is genuinely abstract, there is nothing to call and the
    whole dict is authored instead.

    :param cls: the class the new plugin will inherit from
    :type cls: type
    :return: the rendered stub
    :rtype: Stub
    """
    defining_cls, lines, node = parse_method(cls, SETTINGS)
    sig_lines, doc_lines = split_signature_and_docstring(lines, node)
    example = [
        '        "Type": float,',
        '        "Value": None,',
        '        "Min": 0.0,',
        '        "Units": "pA",',
    ]
    if SETTINGS in getattr(cls, "__abstractmethods__", frozenset()):
        body = [
            "    # TODO: replace this example with the parameters your plugin needs",
            "    settings: Dict[str, Dict[str, Any]] = {",
            '        "My Parameter": {',
            *[f"    {line}" for line in example],
            "        },",
            "    }",
            "    return settings",
        ]
    else:
        body = [
            "    settings = super().get_empty_settings("
            "globally_available_plugins, standalone)",
            "    # TODO: replace this example with the parameters your plugin needs",
            '    settings["My Parameter"] = {',
            *example,
            "    }",
            "    return settings",
        ]
    doc = build_docstring(doc_lines, SETTINGS, False, "    ")
    parts = ["@log(logger=logger)", "@override", *sig_lines, *doc, *body]
    return Stub(
        textwrap.indent("\n".join(parts), "    "),
        annotation_names(node),
        defining_cls.__module__,
    )


def collect_module_imports(module_name: str) -> Dict[str, ImportSpec]:
    """
    Map every name a module imports to the import statement that binds it.

    :param module_name: the dotted module name to read
    :type module_name: str
    :return: import specs keyed by the name they bind
    :rtype: Dict[str, ImportSpec]
    """
    module = sys.modules.get(module_name)
    bindings: Dict[str, ImportSpec] = {}
    try:
        source = inspect.getsource(module) if module else ""
    except (OSError, TypeError):
        return bindings
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                bindings[bound] = ImportSpec(alias.name, None, alias.asname)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                bindings[alias.asname or alias.name] = ImportSpec(
                    node.module, alias.name, alias.asname
                )
    for name in module_level_names(source):
        bindings.setdefault(name, ImportSpec(module_name, name, None))
    return bindings


def module_level_names(source: str) -> List[str]:
    """
    List the names a module binds at module level by plain assignment.

    Type aliases live here and nowhere else: ``MetaEventFitter`` annotates several of its
    abstract methods with ``Numeric``, which it defines as
    ``Numeric = Union[int, float, np.number]`` rather than importing. A stub copying such
    a signature has to import the alias from the module that declares it, or ruff's
    ``F821`` fails the generated file on an undefined name.

    :param source: the module's source text
    :type source: str
    :return: the names bound at module level
    :rtype: List[str]
    """
    names: List[str] = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def render_imports(specs: Sequence[ImportSpec]) -> str:
    """
    Render an import block ordered the way ruff's isort rule expects it.

    Ruff's default ``F401`` fails an unused import, so the caller passes only what the
    generated file actually references. Ordering is stdlib, third party, then first
    party, with plain ``import x`` lines ahead of ``from x import y`` lines within each
    group - the order ``pyproject.toml``'s isort configuration produces.

    :param specs: the imports to render, in any order
    :type specs: Sequence[ImportSpec]
    :return: the rendered import block
    :rtype: str
    """
    buckets: Dict[int, List[ImportSpec]] = {0: [], 1: [], 2: []}
    for spec in set(specs):
        root = spec.module.split(".")[0]
        if root in sys.stdlib_module_names:
            buckets[0].append(spec)
        elif root in ("poriscope", "tests"):
            buckets[2].append(spec)
        else:
            buckets[1].append(spec)

    blocks: List[str] = []
    for index in (0, 1, 2):
        plain = sorted(s for s in buckets[index] if s.name is None)
        grouped: Dict[str, Set[str]] = {}
        for spec in buckets[index]:
            if spec.name is not None:
                bound = f"{spec.name} as {spec.asname}" if spec.asname else spec.name
                grouped.setdefault(spec.module, set()).add(bound)
        lines = [
            f"import {s.module} as {s.asname}" if s.asname else f"import {s.module}"
            for s in plain
        ]
        lines += [
            f"from {module} import {', '.join(sorted(names))}"
            for module, names in sorted(grouped.items())
        ]
        if lines:
            blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def required_imports(base_cls: type, stubs: Sequence[Stub]) -> List[ImportSpec]:
    """
    Work out exactly which imports the generated file needs and no more.

    :param base_cls: the class the new plugin inherits from
    :type base_cls: type
    :param stubs: the rendered method stubs
    :type stubs: Sequence[Stub]
    :return: the imports to emit
    :rtype: List[ImportSpec]
    """
    specs = [
        ImportSpec("logging", None, None),
        ImportSpec("typing", "override", None),
        ImportSpec("poriscope.utils.DocstringDecorator", "inherit_docstrings", None),
        ImportSpec("poriscope.utils.LogDecorator", "log", None),
        ImportSpec(base_cls.__module__, base_cls.__name__, None),
    ]
    for stub in stubs:
        available = collect_module_imports(stub.defining_module)
        specs += [available[n] for n in sorted(stub.names & set(available))]
    return specs


def render_plugin(
    base_cls: type, name: str, methods: Sequence[str], delegate: bool, author: str
) -> str:
    """
    Render a complete plugin file.

    :param base_cls: the class the new plugin inherits from
    :type base_cls: type
    :param name: the new plugin's class name, which is also its filename stem
    :type name: str
    :param methods: the methods to stub out, not including get_empty_settings
    :type methods: Sequence[str]
    :param delegate: if True stub bodies call ``super()`` rather than standing unwritten
    :type delegate: bool
    :param author: the name to record on the Contributors line
    :type author: str
    :return: the complete file text
    :rtype: str
    """
    settings_stub = render_settings_stub(base_cls)
    stubs = [render_stub(base_cls, method, delegate) for method in methods]
    imports = render_imports(required_imports(base_cls, [settings_stub] + stubs))

    public = [s for s, m in zip(stubs, methods) if not m.startswith("_")]
    private = [s for s, m in zip(stubs, methods) if m.startswith("_")]

    verb = "may be overridden by" if delegate else "must be implemented by"
    sections = [f"    # public API, {verb} subclasses\n{settings_stub.text}"]
    sections += [s.text for s in public]
    if private:
        head, *rest = [s.text for s in private]
        sections.append(f"    # private API, {verb} subclasses\n{head}")
        sections += rest

    return "\n".join(
        [
            LICENSE_HEADER + f"# {author}",
            "",
            imports,
            "",
            "",
            "@inherit_docstrings",
            f"class {name}({base_cls.__name__}):",
            '    """',
            f"    TODO: describe what {name} does, and how it differs from",
            f"    {base_cls.__name__}.",
            '    """',
            "",
            "    logger = logging.getLogger(__name__)",
            "",
            "\n\n".join(sections),
            "",
        ]
    )


def overridable_methods(plugin_cls: type) -> List[str]:
    """
    List the methods a variant of an existing plugin can usefully override.

    :param plugin_cls: the shipped plugin class being extended
    :type plugin_cls: type
    :return: the method names, sorted, excluding get_empty_settings
    :rtype: List[str]
    """
    abstract = set(family_base(family_of(plugin_cls)).__abstractmethods__)
    hooks = {hook for hook in OPTIONAL_HOOKS if hasattr(plugin_cls, hook)}
    return sorted((abstract | hooks) - {SETTINGS})


def git_author() -> str:
    """
    Get the committer name git is configured with, for the Contributors line.

    :return: the configured name, or a placeholder if git has none
    :rtype: str
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
        )
    except OSError:
        return "Your Name"
    return result.stdout.strip() or "Your Name"


def user_plugin_folder() -> Path:
    """
    Get the folder Poriscope scans for user plugins, resolved as the app resolves it.

    :return: the configured user plugin folder
    :rtype: Path
    """
    appdata = Path(user_data_dir(), "Poriscope")
    config_file = Path(appdata, "config", "config.json")
    try:
        stored = json.loads(config_file.read_text(encoding="utf-8"))
        return Path(stored["User Plugin Folder"])
    except (OSError, ValueError, KeyError):
        return Path(appdata, "user_plugins")


def print_menus(plugins: Dict[str, Type[BaseDataPlugin]]) -> None:
    """
    Print both menus: the families to subclass, and the plugins available to extend.

    :param plugins: the plugins that already ship, keyed by class name
    :type plugins: Dict[str, Type[BaseDataPlugin]]
    :return: None
    :rtype: None
    """
    print("New plugin - subclass a Poriscope base class.")
    print("Folders below are under poriscope/plugins/.\n")
    families = sorted(FAMILIES, key=lambda f: len(family_base(f).__abstractmethods__))
    for family in families:
        count = len(family_base(family).__abstractmethods__)
        folder = f"{FAMILIES[family].folder}/"
        print(f"  {family:<19}{count:>3}  {folder:<16}{FAMILIES[family].summary}")

    print("\nVariant - subclass a plugin that already ships, and change part of it.\n")
    for name in sorted(plugins):
        count = len(overridable_methods(plugins[name]))
        print(f"  {name:<25}{family_of(plugins[name]):<20}{count:>3} overridable")

    print("\nRun --list with one of these names to see the methods involved.")


def print_detail(base: str, plugins: Dict[str, Type[BaseDataPlugin]]) -> None:
    """
    Print what subclassing one particular base or shipped plugin would give you.

    :param base: a family base class name, or the name of a plugin that already ships
    :type base: str
    :param plugins: the plugins that already ship, keyed by class name
    :type plugins: Dict[str, Type[BaseDataPlugin]]
    :return: None
    :rtype: None
    """
    base_cls, is_variant = resolve_base(base, plugins)
    if is_variant:
        methods = overridable_methods(base_cls)
        family = family_of(base_cls)
        print(f"{base} is a {family} living in {Path(inspect.getfile(base_cls)).name}.")
        print("Subclassing it inherits a working plugin. You may override:\n")
    else:
        methods = sorted(m for m in base_cls.__abstractmethods__ if m != SETTINGS)
        print(f"{base}: {FAMILIES[base].summary}.")
        print(f"Plugins live in poriscope/plugins/{FAMILIES[base].folder}/.")
        print("Subclassing it requires you to implement:\n")
    for method in methods:
        print(f"  {method}")
    print(f"\n  {SETTINGS}  (always stubbed for you)")


def ask(prompt: str, choices: Sequence[str]) -> str:
    """
    Ask the user to pick from a numbered list.

    :param prompt: the question to print above the list
    :type prompt: str
    :param choices: the options to offer
    :type choices: Sequence[str]
    :raises GenerationError: if the input stream closes before a choice is made
    :return: the chosen option
    :rtype: str
    """
    print(f"\n{prompt}")
    for index, choice in enumerate(choices, start=1):
        print(f"  {index}. {choice}")
    while True:
        try:
            answer = input("> ").strip()
        except EOFError as exc:
            raise GenerationError(NOT_INTERACTIVE) from exc
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        if answer in choices:
            return answer
        print(f"Enter a number from 1 to {len(choices)}.")


def ask_text(prompt: str) -> str:
    """
    Ask the user for a line of free text.

    :param prompt: the question to print
    :type prompt: str
    :raises GenerationError: if the input stream closes before an answer is given
    :return: what the user typed, stripped
    :rtype: str
    """
    try:
        return input(f"{prompt} ").strip()
    except EOFError as exc:
        raise GenerationError(NOT_INTERACTIVE) from exc


def resolve_base(
    base: str, plugins: Dict[str, Type[BaseDataPlugin]]
) -> Tuple[type, bool]:
    """
    Turn the BASE argument into a class, and say which of the two modes it selects.

    :param base: a family base class name, or the name of a plugin that already ships
    :type base: str
    :param plugins: the plugins that already ship, keyed by class name
    :type plugins: Dict[str, Type[BaseDataPlugin]]
    :raises GenerationError: if the name matches neither a family nor a shipped plugin
    :return: the base class, and True if this is a variant of an existing plugin
    :rtype: Tuple[type, bool]
    """
    if base in FAMILIES:
        return family_base(base), False
    if base in plugins:
        return plugins[base], True
    raise GenerationError(
        f"{base!r} is neither a base class nor a plugin that ships today.\n"
        f"Run 'python scripts/new_plugin.py --list' to see both menus."
    )


def target_folder(base_cls: type, is_variant: bool, args: argparse.Namespace) -> Path:
    """
    Work out where the generated file should be written.

    :param base_cls: the class the new plugin inherits from
    :type base_cls: type
    :param is_variant: whether this is a variant of an existing plugin
    :type is_variant: bool
    :param args: the parsed command line
    :type args: argparse.Namespace
    :return: the folder to write into
    :rtype: Path
    """
    if args.output_dir:
        return Path(args.output_dir)
    if args.user:
        return user_plugin_folder()
    family = family_of(base_cls) if is_variant else base_cls.__name__
    return Path(REPO_ROOT, "poriscope", "plugins", FAMILIES[family].folder)


def build(args: argparse.Namespace, plugins: Dict[str, Type[BaseDataPlugin]]) -> Path:
    """
    Validate the request, render the plugin, and write it to disk.

    :param args: the parsed command line
    :type args: argparse.Namespace
    :param plugins: the plugins that already ship, keyed by class name
    :type plugins: Dict[str, Type[BaseDataPlugin]]
    :raises GenerationError: if the name is unusable, already taken, or already a file
    :return: the path that was written
    :rtype: Path
    """
    base_cls, is_variant = resolve_base(args.base, plugins)

    if not args.name.isidentifier() or keyword.iskeyword(args.name):
        raise GenerationError(f"{args.name!r} is not a usable Python class name")
    if args.name in plugins:
        raise GenerationError(
            f"a plugin named {args.name} already exists, at "
            f"{inspect.getfile(plugins[args.name])}.\nPlugin names have to be unique "
            f"across every family, so pick another."
        )

    if is_variant:
        available = overridable_methods(base_cls)
        unknown = sorted(set(args.override) - set(available))
        if unknown:
            raise GenerationError(
                f"{base_cls.__name__} has no overridable method(s) "
                f"{', '.join(unknown)}.\nAvailable: {', '.join(available)}"
            )
        methods = sorted(args.override)
    else:
        methods = sorted(m for m in base_cls.__abstractmethods__ if m != SETTINGS)

    path = Path(target_folder(base_cls, is_variant, args), f"{args.name}.py")
    if path.exists():
        raise GenerationError(f"{path} already exists; delete it or pick another name")
    path.parent.mkdir(parents=True, exist_ok=True)

    text = render_plugin(base_cls, args.name, methods, is_variant, args.author)
    path.write_text(text, encoding="utf-8")

    count = len(methods) + 1
    print(f"\nCreated {path}  ({count} methods, {len(text.splitlines())} lines)")
    print("\nNext:")
    print(f"  1. Fill in the {count} methods marked TODO. Each carries its contract.")
    print(f"  2. python scripts/check_plugin_schemas.py {args.name}")
    print("  3. pytest tests/unit/plugins/test_plugin_compliance.py")
    return path


def interactive(
    args: argparse.Namespace, plugins: Dict[str, Type[BaseDataPlugin]]
) -> None:
    """
    Fill in the missing arguments by asking, when the tool is run without them.

    :param args: the parsed command line, modified in place
    :type args: argparse.Namespace
    :param plugins: the plugins that already ship, keyed by class name
    :type plugins: Dict[str, Type[BaseDataPlugin]]
    :raises GenerationError: if no name is given
    :return: None
    :rtype: None
    """
    fresh = "Write a new plugin from scratch (subclass a Poriscope base class)"
    variant = "Vary a plugin that already ships (subclass it and change part of it)"
    if ask("What are you building?", [fresh, variant]) == fresh:
        args.base = ask("Which family?", sorted(FAMILIES))
    else:
        args.base = ask("Which plugin do you want to vary?", sorted(plugins))
        print("\nWhich methods do you want to override? Blank overrides none.")
        for method in overridable_methods(plugins[args.base]):
            print(f"  {method}")
        args.override = ask_text("Names, space separated:").split()

    args.name = ask_text("\nName for your plugin (also its filename):")
    if not args.name:
        raise GenerationError("a name is required")

    if args.output_dir:
        return
    here = "this repository, ready to contribute"
    private = "your user plugin folder, private to you"
    if ask("Where should it go?", [here, private]) == private:
        args.user = True


def main(argv: List[str]) -> int:
    """
    Parse the command line and generate the requested plugin.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 on success, 1 on any refusal
    :rtype: int
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "base", nargs="?", help="a Meta* base class or a shipped plugin"
    )
    parser.add_argument("name", nargs="?", help="the new plugin's class name")
    parser.add_argument(
        "--list", action="store_true", help="show the families and the shipped plugins"
    )
    parser.add_argument(
        "--override",
        nargs="+",
        default=[],
        metavar="METHOD",
        help="when varying a shipped plugin, which of its methods to override",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help="write into your user plugin folder instead of this repository",
    )
    parser.add_argument(
        "--output-dir", metavar="DIR", help="write into this folder instead"
    )
    parser.add_argument(
        "--author", default=None, help="name for the Contributors line in the header"
    )
    args = parser.parse_args(argv)

    # Discovery imports every plugin file and several log at import time; that output is
    # noise here, the same way it is in check_plugin_schemas.py.
    logging.disable(logging.WARNING)
    plugins = discover_plugin_classes()
    if args.author is None:
        args.author = git_author()

    try:
        if args.list:
            if args.base:
                print_detail(args.base, plugins)
            else:
                print_menus(plugins)
            return 0
        if not args.base or not args.name:
            interactive(args, plugins)
        build(args, plugins)
    except GenerationError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
