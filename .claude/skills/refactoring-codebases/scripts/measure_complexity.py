#!/usr/bin/env python3
"""McCabe cyclomatic complexity per function, with an exact-match ratchet on offenders.

Counting rule (the definition is the number):

    complexity = 1
      + 1 per ``if`` / ``elif``            + 1 per conditional expression (``a if c else b``)
      + 1 per ``for`` / ``async for``      + 1 per ``while``
      + 1 per ``except`` clause            + 1 per ``case`` in a ``match`` (wildcard included)
      + 1 per comprehension ``for`` clause and per comprehension ``if`` clause
      + (operands - 1) per boolean operator chain (``a and b and c`` adds 2)

    NOT counted: ``with``, ``try`` itself, ``else``/``finally``, ``assert``, ``return``, ``break``.
    Nested functions, lambdas and classes are measured as their own functions and do not add to
    the enclosing function.

An ad-hoc script that scored ``with`` as a branch once hid a function sitting at exactly the
threshold; state the rule and keep the script committed.

Usage:
    python measure_complexity.py src/app/shell.py src/app/settings.py --threshold 10
    python measure_complexity.py FILES... --threshold 10 --baseline .complexity-baseline.json --check
    python measure_complexity.py FILES... --threshold 10 --baseline .complexity-baseline.json --update

The baseline records every function over the threshold with its score. ``--check`` fails when
the set or any score differs in either direction.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _score(func: ast.AST) -> int:
    score = 1
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        if isinstance(node, _SCOPES):
            continue  # measured separately
        if isinstance(
            node,
            (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler),
        ):
            score += 1
        elif isinstance(node, ast.BoolOp):
            score += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            score += 1 + len(node.ifs)
        elif hasattr(ast, "match_case") and isinstance(node, ast.match_case):
            score += 1
        stack.extend(ast.iter_child_nodes(node))
    return score


def measure_text(source: str, path: str) -> dict[str, int]:
    """Return {"path::Qual.name": complexity} for every function in ``source``."""
    out: dict[str, int] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = prefix + child.name
                key = f"{path}::{qual}"
                if key in out:
                    key = f"{key}@{child.lineno}"
                out[key] = _score(child)
                visit(child, qual + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(ast.parse(source), "")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="+")
    ap.add_argument(
        "--threshold", type=int, default=10, help="report functions strictly over this"
    )
    ap.add_argument("--baseline")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--update", action="store_true")
    ap.add_argument(
        "--all", action="store_true", help="print every function, not just offenders"
    )
    args = ap.parse_args(argv)

    scores: dict[str, int] = {}
    for f in args.files:
        scores.update(
            measure_text(Path(f).read_text(encoding="utf-8"), f.replace("\\", "/"))
        )
    over = {k: v for k, v in sorted(scores.items()) if v > args.threshold}
    shown = scores if args.all else over
    for k, v in sorted(shown.items(), key=lambda kv: -kv[1]):
        print(f"{v:4d}  {k}")
    print(
        f"functions={len(scores)} over_{args.threshold}={len(over)} total_over={sum(over.values())}"
    )

    if not args.baseline:
        return 0
    bpath = Path(args.baseline)
    payload = {"threshold": args.threshold, "over": over}
    if args.update:
        bpath.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Baseline written: {bpath}")
        return 0
    if args.check:
        if not bpath.exists():
            print(
                f"FAIL: baseline {bpath} is missing (is it ignored by version control?)"
            )
            return 1
        base = json.loads(bpath.read_text(encoding="utf-8"))
        if base.get("threshold") != args.threshold:
            print(
                f"FAIL: baseline threshold {base.get('threshold')} != {args.threshold}"
            )
            return 1
        b = base.get("over", {})
        ok = b == over
        for k in sorted(set(b) | set(over)):
            if b.get(k) != over.get(k):
                print(f"FAIL {k}: baseline {b.get(k)} -> current {over.get(k)}")
        if ok:
            print("Ratchet: exact match with baseline.")
            return 0
        print(
            "Ratchet mismatch: bank an improvement with --update in the same commit, and record why."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
