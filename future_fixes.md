# Future Fix: Full Codebase Type-Annotation Pass

Context block for a dedicated future session. Paste/point Claude Code at this file to
resume this work; it is written to be self-contained.

## Goal

Add type hints to every parameter (and return type) of every function/method across
`poriscope/` so the codebase can adopt a strict, signature-based typing policy end to
end, instead of the current partial/legacy state.

## Why this matters (background)

Two config knobs currently tolerate untyped code, and they interact:

- `mypy.ini`: `disallow_untyped_defs = False`, `check_untyped_defs = False` — mypy
  does not require annotations on plugin methods, and (more importantly) does not even
  type-check the *body* of a function that has zero annotations.
- `pyproject.toml` `[tool.pydoclint]`: `arg-type-hints-in-signature = false` — pydoclint
  expects type info to live in the docstring, not the signature, and its `DOC108`
  check exists specifically to flag functions that *do* have signature type hints
  under this policy (see `pydoclint/utils/violation.py` and `visitor.py:608-622` in the
  installed package for the exact trigger condition).

As of the `feature/loadbearing_docstrings` branch's pydoclint baseline cleanup
(`.pydoclint-baseline.txt`, ~430 remaining lines), the residual backlog is almost
entirely `DOC108` — i.e. functions that already happen to carry signature type hints,
which is a "policy nag," not a real defect. There is no way to clear these for real
(short of stripping existing hints back out, which would be regressive) other than
flipping `arg-type-hints-in-signature` to `true`. That flip is the actual goal of this
future pass; this file exists because flipping it is not a small edit — see Scope below.

## What flipping the policy actually requires

`pydoclint/visitor.py` only checks a function at all if it has a non-empty docstring
(functions with zero docstring are skipped entirely — "we don't check functions
without docstrings"). But for every function that *does* have a docstring, once
`arg-type-hints-in-signature = true`:

- `DOC106` fires if a documented, parameterized function has **no** signature type
  hints at all.
- `DOC107` fires if it has **some but not all** parameters hinted.

So in practice this pass means adding type hints to essentially every parameter of
every documented function in `poriscope/` (not just the ~430 currently-flagged spots).
Once that's done, `mypy.ini`'s `check_untyped_defs = False` / `disallow_untyped_defs =
False` leniency has nothing left to exempt and becomes a no-op — it can be safely
flipped to `True` (or removed) at that point, verified by the fact that the test suite
and `pre-commit run --all-files` still pass identically before and after the flip.

## Scope / sequencing

1. Add type hints file-by-file (or in small independent batches via subagents — see
   Method below) across all of `poriscope/`, including `Meta*` ABCs in
   `poriscope/utils/`, all plugin families, controllers/models/views, and app-shell
   code.
2. Once annotation coverage is effectively complete, flip
   `[tool.pydoclint] arg-type-hints-in-signature = true` in `pyproject.toml`, run
   `pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope`
   fresh from a clean tree, and confirm the new baseline is empty or near-empty (a
   near-empty remainder here would represent a real gap to close, not something to
   wave through).
3. Flip `mypy.ini`'s `disallow_untyped_defs`/`check_untyped_defs` to `True` and confirm
   `mypy poriscope` is still clean (or fix what it now surfaces — see Known gotchas).
4. Update `CLAUDE.md`'s description of the pydoclint/mypy config to reflect the new,
   stricter policy (it currently documents the old permissive one).

## Method (lessons carried over from the pydoclint baseline cleanup)

This mirrors the process that worked well for the docstring/baseline cleanup on
`feature/loadbearing_docstrings`:

- Pure type-hint additions (no behavior change) can proceed automatically; anything
  that looks like it would change runtime behavior should pause for a check-in.
- Work file-by-file, or hand independent file groups to parallel subagents
  (`Agent` tool, `general-purpose` type, one self-contained prompt per group) — this
  scaled well last time across ~60 files.
- Commit in small batches (e.g. every 5 files) so a rollback is cheap if a batch turns
  out to have a subtle issue.
- Update `changelog.md` as you go, but keep entries terse — a "New Dev Tooling"-style
  consolidated summary at the end is more useful to other developers than a per-file
  violation list (see the `## Poriscope 1.7` section for the pattern used last time).

## Known gotchas to expect (all hit during the pydoclint pass; will likely recur)

- **mypy "annotation-unchecked" cascade**: a function with zero annotations is
  currently invisible to mypy's body-checking (`check_untyped_defs = False`). Adding
  *any* annotation to it (even just a return type) flips it to "checked," which can
  surface pre-existing, previously-invisible type errors unrelated to the annotation
  you just added. Fix patterns established last time:
  - If the error is `self.attr = None` being inferred as a `None`-only type, add a
    proper `Optional[X]` annotation at that attribute's first assignment — this is a
    pure type-hint fix, safe to apply on sight.
  - If it's a genuine logic-shaped mismatch, flag it for human review rather than
    fixing blindly — unless it's provably behavior-neutral (e.g. a `cast()` where the
    real runtime type is already guaranteed by surrounding code, as was needed once in
    `MetaReader.load_data`).
- **`test_plugin_compliance.py` exact-equality trap**: its `_return_type_compatible` /
  `_param_type_compatible` checks do not understand real generic covariance — for
  non-"classlike" (generic alias) annotations it falls back to exact equality between
  a `Meta*` base method's annotation and every subclass override's annotation. Widening
  or correcting an abstract method's annotation to satisfy mypy will break this test
  for every subclass whose override doesn't match exactly, and all of them need to be
  updated to match. Run
  `pytest tests/unit/plugins/test_plugin_compliance.py` after touching any `Meta*`
  base signature.
- **Baseline file race condition**: if multiple concurrent agents/processes run
  `pydoclint --baseline=.pydoclint-baseline.txt` with auto-regeneration on narrow file
  subsets, they can corrupt or prune unrelated entries from the shared baseline. Use
  `--auto-regenerate-baseline=False` for read-only checks during the pass, and only do
  one authoritative full-tree `--generate-baseline=True` regeneration once all edits
  for a batch are complete.

## Exclusions (standing project policy — do not spend effort here)

- `NanoTrees.py` — likely to be deprecated soon.
- `Basic_PeakFinder.py` / `PeakFinder.py` — owned by another developer.

## Verification checklist before considering this pass done

- `pre-commit run --all-files` clean (ruff + mypy + pydoclint).
- `pytest -m "not e2e and not slow"` clean (matches CI).
- `pytest tests/unit/plugins/test_plugin_compliance.py` clean.
- `pydoclint --baseline=.pydoclint-baseline.txt poriscope` clean with
  `arg-type-hints-in-signature = true`, baseline regenerated fresh from a clean tree.
- `mypy poriscope` clean with `disallow_untyped_defs = True` /
  `check_untyped_defs = True` (or documented exceptions added deliberately, not by
  default).
- `changelog.md` updated with a concise summary, not an exhaustive per-file list.
