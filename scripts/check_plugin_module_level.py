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
Check that no data plugin runs code at import time.

    python scripts/check_plugin_module_level.py [--quiet] [PATH ...]

Plugin discovery executes every file it walks: ``MainModel.load_plugin`` calls
``spec.loader.exec_module``, and Python runs module-level code unconditionally,
before any compliance check gets to reflect on the class. A plugin therefore has
no business doing anything at module level beyond declaring imports, constants,
classes and functions.

The rule is that module-level *assignment* is fine but module-level *invocation*
is not, so a type alias such as ``Numeric = Union[int, float, np.number]`` passes
while ``logger = logging.getLogger(__name__)`` does not.

With no PATH arguments it checks the eight data-plugin families - what an outside
contribution actually adds. Exits 1 if any file reports a problem, so it is usable
as a gate.
"""

import argparse
import ast
import sys
from pathlib import Path
from typing import List, Tuple

#: The plugin families an outside contribution realistically adds. ``analysistabs``
#: is deliberately absent: its module-level statements are benign (warnings filters,
#: an ``os.environ`` guard, ``__main__`` demo blocks), and admitting them would mean
#: a rule with carve-outs rather than a rule with none. Those files are still covered
#: by the ``ruff-plugin-security`` hook, which needs no exceptions anywhere.
PLUGIN_FAMILIES = (
    "datareaders",
    "datawriters",
    "db_loaders",
    "dbwriters",
    "eventfinders",
    "eventfitters",
    "eventloaders",
    "filters",
)

#: Statement types a plugin may use at module level. Note that decorators on a
#: permitted class or function are *not* examined, even though they are calls
#: evaluated at import time: ``@log`` from ``poriscope/utils/LogDecorator.py`` is
#: integral to the plugin pattern, so flagging it would be noise, not a finding.
ALLOWED_STATEMENTS = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "poriscope" / "plugins"


def display(path: Path) -> str:
    """
    Render a path for the report, relative to the repository root where possible.

    :param path: the path to render
    :type path: Path
    :return: a repository-relative path, or the path unchanged if it lies outside
    :rtype: str
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def contains_call(node: ast.AST) -> bool:
    """
    Report whether an expression subtree invokes anything.

    :param node: the expression to inspect
    :type node: ast.AST
    :return: True if any node in the subtree is a call
    :rtype: bool
    """
    return any(isinstance(child, ast.Call) for child in ast.walk(node))


def check_source(source: str, filename: str) -> List[str]:
    """
    Report every module-level statement in one file that runs code at import time.

    :param source: the file's text
    :type source: str
    :param filename: the name to attribute syntax errors to
    :type filename: str
    :return: one human-readable message per problem, empty if the file is clean
    :rtype: List[str]
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [f"line {exc.lineno}: file could not be parsed: {exc.msg}"]

    problems = []
    for node in tree.body:
        if isinstance(node, ALLOWED_STATEMENTS):
            continue

        # A bare string is the module docstring, which evaluates to nothing.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is None or not contains_call(node.value):
                continue
            problems.append(
                f"line {node.lineno}: module-level assignment calls something, so it "
                f"runs when the plugin is discovered; move it into a method"
            )
            continue

        problems.append(
            f"line {node.lineno}: module-level {type(node).__name__} runs when the "
            f"plugin is discovered; only imports, constants, classes and functions "
            f"belong at module level"
        )

    return problems


def default_paths() -> List[Path]:
    """
    Collect every Python file in the eight data-plugin families.

    :return: the files to check when none were named on the command line
    :rtype: List[Path]
    """
    paths: List[Path] = []
    for family in PLUGIN_FAMILIES:
        paths.extend(sorted((PLUGIN_ROOT / family).rglob("*.py")))
    return paths


def resolve_paths(named: List[str]) -> Tuple[List[Path], List[str]]:
    """
    Turn the command line's path arguments into files to check.

    :param named: paths as given on the command line, possibly empty
    :type named: List[str]
    :return: the files to check, and any named path that does not exist
    :rtype: Tuple[List[Path], List[str]]
    """
    if not named:
        return default_paths(), []

    paths: List[Path] = []
    missing: List[str] = []
    for name in named:
        path = Path(name)
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.py")))
        elif path.is_file():
            paths.append(path)
        else:
            missing.append(name)
    return paths, missing


def main(argv: List[str]) -> int:
    """
    Check every requested plugin file for module-level code and report the results.

    :param argv: command-line arguments, excluding the program name
    :type argv: List[str]
    :return: 0 if every checked file is clean, 1 otherwise
    :rtype: int
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        metavar="PATH",
        help="files or directories to check; defaults to the data-plugin families",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="report only the files that have problems",
    )
    args = parser.parse_args(argv)

    paths, missing = resolve_paths(args.paths)
    if missing:
        print(f"No such file or directory: {', '.join(missing)}", file=sys.stderr)
        return 1
    if not paths:
        print("No plugin files were found to check.", file=sys.stderr)
        return 1

    failed = 0
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            failed += 1
            print(f"FAIL {display(path)}: could not be read: {exc!r}")
            continue

        problems = check_source(source, display(path))
        if problems:
            failed += 1
            print(f"FAIL {display(path)}: {len(problems)} problem(s)")
            for problem in problems:
                print(f"       {problem}")
        elif not args.quiet:
            print(f"ok   {display(path)}")

    print(f"\n{len(paths) - failed}/{len(paths)} files clean.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
