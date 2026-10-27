#!/usr/bin/env python3
"""Breaking-change inventory: compare the class/method surface of Python files at two git refs.

For every class in the selected files at OLD and NEW, compares method tables: removed methods,
added abstract methods, signature changes, and abstractness changes. Each finding is marked
with whether it can actually break a downstream subclass or caller:

* an abstract method added to a class that did not exist at OLD breaks nobody (nobody could
  have subclassed it) - listed separately so the inventory is not padded with non-events;
* removals and signature changes on classes that existed at OLD are potential breaks.

Blind spot, stated because it is the one that matters: behavioural contract changes that leave
signatures alone (a newly required settings key, a new meaning for ``None``) are invisible here.
Add those by hand from the decision log.

By default only public methods and abstract methods are compared (a leading underscore can mark
a subclass author's obligation, so abstract privates are always included). ``--all`` compares
every method.

Usage:
    python api_surface_diff.py --old v1.9.0 --new HEAD --glob "src/pkg/base/*.py"
    python api_surface_diff.py --old v1.9.0 --new HEAD src/pkg/meta_reader.py src/pkg/meta_writer.py
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def files_at(ref: str, globs: list[str], paths: list[str]) -> list[str]:
    tracked = git("ls-tree", "-r", "--name-only", ref).split("\n")
    wanted = [p for p in tracked if p.endswith(".py") and (p in paths or any(fnmatch.fnmatch(p, g) for g in globs))]
    return sorted(set(wanted))


def _is_abstract(fn: ast.AST) -> bool:
    for d in getattr(fn, "decorator_list", []):
        name = d.attr if isinstance(d, ast.Attribute) else getattr(d, "id", "")
        if name in ("abstractmethod", "abstractproperty"):
            return True
    return False


def _in_scope(name: str, abstract_somewhere: bool, include_all: bool) -> bool:
    public = not name.startswith("_") or (name.startswith("__") and name.endswith("__"))
    return include_all or public or abstract_somewhere


def surface(source: str, include_all: bool) -> dict[str, dict[str, tuple[str, bool]]]:
    """Return {ClassName: {method: (signature, is_abstract)}} for top-level classes (all methods)."""
    out: dict[str, dict[str, tuple[str, bool]]] = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods = {}
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ret = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                methods[item.name] = (f"({ast.unparse(item.args)}){ret}", _is_abstract(item))
        out[node.name] = methods
    return out


def collect(ref: str, files: list[str], include_all: bool) -> dict[str, dict]:
    classes: dict[str, dict] = {}
    for f in files:
        try:
            src = git("show", f"{ref}:{f}")
        except subprocess.CalledProcessError:
            continue
        for cls, methods in surface(src, include_all).items():
            classes[f"{f}::{cls}"] = methods
    return classes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--glob", action="append", default=[], help="fnmatch pattern over repo paths")
    ap.add_argument("--all", action="store_true", help="include non-abstract private methods")
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args(argv)
    if not args.glob and not args.paths:
        ap.error("give --glob patterns or paths")

    files = sorted(set(files_at(args.old, args.glob, args.paths)) | set(files_at(args.new, args.glob, args.paths)))
    old, new = collect(args.old, files, args.all), collect(args.new, files, args.all)
    # Match classes by name, so a class moved between files is compared, not reported as removed+added.
    old_by = {k.split("::")[1]: (k, v) for k, v in old.items()}
    new_by = {k.split("::")[1]: (k, v) for k, v in new.items()}

    breaks, nonevents, notes = [], [], []
    for name in sorted(set(old_by) - set(new_by)):
        breaks.append(f"class removed: {old_by[name][0]}")
    for name in sorted(set(new_by) - set(old_by)):
        abstract = [m for m, (_s, a) in new_by[name][1].items() if a]
        nonevents.append(f"class new: {new_by[name][0]}" + (f" (abstract: {', '.join(abstract)} - breaks nobody)" if abstract else ""))
    for name in sorted(set(old_by) & set(new_by)):
        (ko, mo), (kn, mn) = old_by[name], new_by[name]
        # A method is in scope if it is public, or abstract at EITHER ref - so a private abstract
        # hook that became concrete is reported as an abstractness change, not as a removal.
        scope = {m for m in set(mo) | set(mn)
                 if _in_scope(m, mo.get(m, ("", False))[1] or mn.get(m, ("", False))[1], args.all)}
        mo = {m: v for m, v in mo.items() if m in scope}
        mn = {m: v for m, v in mn.items() if m in scope}
        if ko != kn:
            notes.append(f"class moved: {ko} -> {kn} (import path changed - a break for importers)")
            breaks.append(f"import path changed: {name}")
        for m in sorted(set(mo) - set(mn)):
            breaks.append(f"{name}.{m} removed (was {mo[m][0]})")
        for m in sorted(set(mn) - set(mo)):
            if mn[m][1]:
                breaks.append(f"{name}.{m} added as ABSTRACT - every existing subclass must implement it")
            else:
                notes.append(f"{name}.{m} added")
        for m in sorted(set(mo) & set(mn)):
            (so, ao), (sn, an) = mo[m], mn[m]
            if so != sn:
                breaks.append(f"{name}.{m} signature {so} -> {sn}")
            if ao != an:
                (breaks if an else notes).append(f"{name}.{m} abstract {ao} -> {an}")

    print(f"Compared {len(files)} file(s), {len(old_by)} class(es) at {args.old}, {len(new_by)} at {args.new}.\n")
    print(f"Potential breaks ({len(breaks)}):")
    for b in breaks:
        print(f"  - {b}")
    print(f"\nNew surface that breaks nobody ({len(nonevents)}):")
    for n in nonevents:
        print(f"  - {n}")
    print(f"\nOther changes ({len(notes)}):")
    for n in notes:
        print(f"  - {n}")
    print("\nNot visible here: behavioural contract changes with unchanged signatures. Add them by hand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
