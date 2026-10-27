#!/usr/bin/env python3
"""Measure byte-identical function duplication per family of Python files, and ratchet it.

Counting rule (the definition is the number - change it only with a re-baseline):

* A *family* is an explicit list of files (sibling modules expected to share code). Globs are
  expanded case-sensitively by the OS; list files explicitly when names mix case.
* Every ``def`` / ``async def`` at any depth is a *function*, keyed ``path::Qual.name``.
* A function's *text* is its source from the ``def`` keyword to its last line (decorators
  excluded), dedented. With ``--ignore-docstrings`` the leading docstring is removed first,
  so two bodies that differ only in prose count as identical and two that match only in prose
  do not. With ``--ignore-names`` the function name is blanked, so identically-bodied
  functions with different names are grouped too.
* An *identical group* is two or more functions in the family with the same text (any files,
  including the same file). ``removable_lines`` = sum over groups of (copies - 1) x lines.
* ``functions`` = number of functions in the family. It is the second number that tells a real
  promotion (functions fall) from a copy edited into divergence (removable falls, functions do not).

Blind spots: near-copies differing by one character; copies split across different names
(unless ``--ignore-names``); logic duplicated at statement level inside different functions.

Usage:
    python measure_duplication.py --family views=src/app/a_view.py,src/app/b_view.py
    python measure_duplication.py --config dup_families.json --baseline .dup-baseline.json --check
    python measure_duplication.py --config dup_families.json --baseline .dup-baseline.json --update
    python measure_duplication.py --config f.json --simulate src/app/a_view.py=/tmp/a_view_modified.py

Config JSON: {"families": {"views": ["src/a.py", "src/b.py"]}, "ignore_docstrings": false,
              "ignore_names": false}

``--check`` fails (exit 1) when any family's figures differ from the baseline in EITHER
direction: an improvement must be banked by updating the baseline in the commit that earned it.
"""
from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import json
import sys
import textwrap
from pathlib import Path


def _strip_docstring(node: ast.AST, text: str) -> str:
    body = getattr(node, "body", [])
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        doc = body[0]
        lines = text.splitlines(keepends=True)
        # Positions are relative to the function's own first line.
        start = doc.lineno - node.lineno
        end = doc.end_lineno - node.lineno
        del lines[start:end + 1]
        return "".join(lines)
    return text


def function_texts(source: str, path: str, ignore_docstrings: bool = False,
                   ignore_names: bool = False) -> dict[str, tuple[str, int]]:
    """Return {"path::Qual.name": (normalised text, line count)} for every def in ``source``."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    out: dict[str, tuple[str, int]] = {}

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                seg = "".join(lines[child.lineno - 1:child.end_lineno])
                seg = textwrap.dedent(seg)
                if ignore_docstrings:
                    seg = _strip_docstring(child, seg)
                if ignore_names:
                    seg = seg.replace(f"def {child.name}(", "def _(", 1)
                key = f"{path}::{qual}"
                if key in out:  # redefinition in the same scope: keep both, disambiguate
                    key = f"{key}@{child.lineno}"
                out[key] = (seg, len(seg.splitlines()))
                visit(child, qual + ".")
            elif isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            else:
                visit(child, prefix)

    visit(tree, "")
    return out


def measure_texts(files: dict[str, str], ignore_docstrings: bool = False,
                  ignore_names: bool = False) -> dict:
    """Measure one family given {path: source text}. Takes text so changes can be simulated."""
    functions: dict[str, tuple[str, int]] = {}
    for path, text in files.items():
        functions.update(function_texts(text, path, ignore_docstrings, ignore_names))
    by_hash: dict[str, list[str]] = {}
    for key, (text, _n) in functions.items():
        by_hash.setdefault(hashlib.sha1(text.encode()).hexdigest(), []).append(key)
    groups = []
    removable = 0
    for members in by_hash.values():
        if len(members) > 1:
            n = functions[members[0]][1]
            removable += (len(members) - 1) * n
            groups.append({"lines": n, "copies": len(members), "members": sorted(members)})
    groups.sort(key=lambda g: (-(g["copies"] - 1) * g["lines"], g["members"]))
    return {"files": len(files), "functions": len(functions), "identical_groups": len(groups),
            "removable_lines": removable, "groups": groups}


def _expand(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True)) if any(c in pat for c in "*?[") else [pat]
        if not hits:
            print(f"WARNING: pattern matched nothing: {pat}", file=sys.stderr)
        paths.extend(h.replace("\\", "/") for h in hits)
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON config with families")
    ap.add_argument("--family", action="append", default=[], help="NAME=path[,path...] (globs allowed)")
    ap.add_argument("--ignore-docstrings", action="store_true")
    ap.add_argument("--ignore-names", action="store_true")
    ap.add_argument("--simulate", action="append", default=[],
                    help="REAL_PATH=MODIFIED_PATH: measure MODIFIED_PATH's text in place of REAL_PATH")
    ap.add_argument("--baseline", help="baseline JSON path")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exact-match check against the baseline")
    mode.add_argument("--update", action="store_true", help="write current figures to the baseline")
    ap.add_argument("--groups", action="store_true", help="print every identical group")
    args = ap.parse_args(argv)

    families: dict[str, list[str]] = {}
    ignore_doc, ignore_names = args.ignore_docstrings, args.ignore_names
    if args.config:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
        families.update(cfg.get("families", {}))
        ignore_doc = ignore_doc or cfg.get("ignore_docstrings", False)
        ignore_names = ignore_names or cfg.get("ignore_names", False)
    for spec in args.family:
        name, _, paths = spec.partition("=")
        families[name] = paths.split(",")
    if not families:
        ap.error("no families given (--config or --family)")

    sims = {}
    for spec in args.simulate:
        real, _, mod = spec.partition("=")
        sims[real.replace("\\", "/")] = Path(mod).read_text(encoding="utf-8")

    results = {}
    for name, patterns in families.items():
        paths = _expand(patterns)
        texts = {p: sims.get(p) if p in sims else Path(p).read_text(encoding="utf-8") for p in paths}
        results[name] = measure_texts(texts, ignore_doc, ignore_names)

    for name, r in results.items():
        print(f"{name:24s} files={r['files']:3d} functions={r['functions']:5d} "
              f"identical_groups={r['identical_groups']:4d} removable_lines={r['removable_lines']:6d}")
        if args.groups:
            for g in r["groups"]:
                print(f"    {g['copies']}x{g['lines']:>4d} lines: " + ", ".join(g["members"]))
    total = sum(r["removable_lines"] for r in results.values())
    print(f"{'TOTAL':24s} removable_lines={total}")
    if sims:
        print("(simulated: " + ", ".join(sims) + ")")

    if not args.baseline:
        return 0
    summary = {n: {k: r[k] for k in ("files", "functions", "identical_groups", "removable_lines")}
               for n, r in results.items()}
    bpath = Path(args.baseline)
    if args.update:
        if sims:
            print("Refusing to write a baseline from simulated text.", file=sys.stderr)
            return 2
        bpath.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Baseline written: {bpath}")
        return 0
    if args.check:
        if not bpath.exists():
            print(f"FAIL: baseline {bpath} is missing (is it ignored by version control?)")
            return 1
        base = json.loads(bpath.read_text(encoding="utf-8"))
        ok = True
        for n in sorted(set(base) | set(summary)):
            b, c = base.get(n), summary.get(n)
            if b != c:
                ok = False
                print(f"FAIL {n}: baseline {b} != current {c}")
                if b and c and c["removable_lines"] < b["removable_lines"] and c["functions"] >= b["functions"]:
                    print(f"  NOTE {n}: removable fell while functions did not - a real deletion offset by "
                          "additions, a copy edited into divergence, or prose-only change. Prove it before banking.")
        if ok:
            print("Ratchet: exact match with baseline.")
            return 0
        print("Ratchet mismatch. If the change is an earned improvement (or an accepted, recorded loss), "
              "re-run with --update in the same commit and say why in the commit message.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
