#!/usr/bin/env python3
"""Structural checks between two versions of Python source.

Text edits over structured code fail silently: a splice between two ``def`` anchors deletes
whatever sat between them; a line-matched deletion re-parents the next statement; an
"only docstrings changed" sweep across 50 files may have touched code. These checks are
structural, so they catch what a diff read by eye misses.

Sources are given as a file path, or ``REV:path`` to read a file from git (``git show``).

Modes:

  methods OLD NEW [--expect-removed A.b,C.d] [--expect-added X.y]
      List functions/methods lost and gained (qualified names). With --expect-*, exit 1 unless
      the sets match exactly - run it after every scripted splice.

  prose OLD NEW
      Exit 0 only if the two versions have identical ASTs once every docstring is removed
      (comments never reach the AST). Proves an edit changed prose only.

  prose --git REV_A REV_B [PATHSPEC...]
      Same check for every .py file changed between two git revisions.

Examples:
    python structural_diff.py methods HEAD:src/app/view.py src/app/view.py --expect-removed View._old
    python structural_diff.py prose --git main HEAD -- tests/
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path


def read_source(spec: str) -> str:
    """Read ``path`` or ``REV:path`` (git). A Windows drive letter is not a revision."""
    if ":" in spec and not (len(spec) > 1 and spec[1] == ":" and spec[0].isalpha()):
        return subprocess.run(
            ["git", "show", spec],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    return Path(spec).read_text(encoding="utf-8")


def qualified_defs(source: str) -> set[str]:
    names: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(prefix + child.name)
                visit(child, prefix + child.name + ".")
            elif isinstance(child, ast.ClassDef):
                names.add(prefix + child.name + " (class)")
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return names


class _StripDocstrings(ast.NodeTransformer):
    def _strip(self, node):
        self.generic_visit(node)
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
        return node

    visit_Module = visit_ClassDef = visit_FunctionDef = visit_AsyncFunctionDef = _strip


def code_dump(source: str) -> str:
    return ast.dump(
        _StripDocstrings().visit(ast.parse(source)), include_attributes=False
    )


def cmd_methods(args) -> int:
    old, new = qualified_defs(read_source(args.old)), qualified_defs(
        read_source(args.new)
    )
    lost, gained = sorted(old - new), sorted(new - old)
    print("Lost:   " + (", ".join(lost) or "(none)"))
    print("Gained: " + (", ".join(gained) or "(none)"))
    ok = True
    if args.expect_removed is not None:
        want = set(filter(None, args.expect_removed.split(",")))
        if want != set(lost):
            ok = False
            print(f"FAIL: expected removed {sorted(want)}, got {lost}")
    if args.expect_added is not None:
        want = set(filter(None, args.expect_added.split(",")))
        if want != set(gained):
            ok = False
            print(f"FAIL: expected added {sorted(want)}, got {gained}")
    if ok and (args.expect_removed is not None or args.expect_added is not None):
        print("OK: structural change is exactly the intended one.")
    return 0 if ok else 1


def cmd_prose(args) -> int:
    pairs: list[tuple[str, str, str]] = []
    if args.git:
        rev_a, rev_b = args.git
        names = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                "--diff-filter=M",
                rev_a,
                rev_b,
                "--",
                *args.paths,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        pairs = [
            (n, f"{rev_a}:{n}", f"{rev_b}:{n}") for n in names if n.endswith(".py")
        ]
    else:
        if len(args.paths) != 2:
            print("prose needs OLD NEW, or --git REV_A REV_B [pathspec]")
            return 2
        pairs = [(args.paths[1], args.paths[0], args.paths[1])]
    bad = []
    for label, a, b in pairs:
        if code_dump(read_source(a)) != code_dump(read_source(b)):
            bad.append(label)
    print(f"Checked {len(pairs)} file(s).")
    for b in bad:
        print(f"CODE CHANGED: {b}")
    if bad:
        return 1
    print("OK: only docstrings/comments changed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="mode", required=True)
    m = sub.add_parser("methods")
    m.add_argument("old")
    m.add_argument("new")
    m.add_argument("--expect-removed")
    m.add_argument("--expect-added")
    p = sub.add_parser("prose")
    p.add_argument("--git", nargs=2, metavar=("REV_A", "REV_B"))
    p.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    if args.mode == "prose" and args.paths[:1] == ["--"]:
        args.paths = args.paths[1:]
    return cmd_methods(args) if args.mode == "methods" else cmd_prose(args)


if __name__ == "__main__":
    sys.exit(main())
