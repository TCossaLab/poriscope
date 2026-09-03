# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Poriscope is a PySide6 (Qt) desktop application for selecting and analyzing nanopore
timeseries data (event detection, fitting, clustering, protein analysis, etc.). Python
>= 3.12, Windows-focused but CI runs on Linux under Xvfb.

## Setup

```
pip install -e ".[dev]"
python scripts/setup_hooks.py   # git hooks (pre-commit, post-merge) + git flow tag prefix
```

Run the app with the `poriscope` console-script entry point (`poriscope.main_app:main`).

## Common commands

```
pytest                                        # full suite - also what CI runs, everywhere
pytest tests/unit/plugins/test_plugin_compliance.py   # plugin interface compliance
pytest path/to/test_file.py::test_name        # single test
pytest --marker-stats                         # per-marker test counts and mean durations
pytest -m "not e2e"                           # skip the e2e tests

pre-commit run --all-files --hook-stage manual   # auto-fix: black, ruff --fix
pre-commit run --all-files                       # strict check: ruff + mypy + pydoclint (what pre-commit/CI enforce on real commits)
mypy poriscope                                    # NOT the gate - see the warning below
pydoclint --baseline=.pydoclint-baseline.txt poriscope   # docstring/signature consistency check directly
```

Note: `black` and the ruff auto-fix hook only run at `stages: [manual]` — they do not
run automatically on `git commit`. Run `pre-commit run --all-files --hook-stage manual`
yourself before committing if you want formatting applied; the pre-commit hook itself
runs ruff (strict, no fix), mypy, and pydoclint.

**`pre-commit run mypy --all-files` is the mypy gate; `mypy poriscope` is not.** The two
disagree wildly and are blind in opposite directions. The hook runs in an isolated
virtualenv with no project dependencies, so PySide6/numpy/pandas types are all `Any` to
it; the project venv's `mypy poriscope` sees real types but is a different version and
reports several hundred errors that are overwhelmingly known noise (191 PySide6
short-form enum accesses alone - see `DECISIONS.md`). **Always measure with the hook.**
The hook is scoped `files: ^poriscope/` because `mypy.ini`'s `exclude = ^tests/` governs
directory discovery only and does not apply to explicitly listed paths.

Every function you add under `poriscope/` needs type hints, and `mypy.ini` enforces that
(read its own comments for which settings and why). Do not relax any of them to get a
commit through.

`pydoclint` checks a docstring's documented parameters, return type and raised exceptions
against the real signature and body — see `[tool.pydoclint]` in `pyproject.toml` for the
settings and the reasoning behind each. A function with no docstring is skipped entirely;
a documented one must carry type hints that agree with its `:type:`/`:rtype:`. **Every
function under `poriscope/` is annotated, with no exclusions.**

Keep `.pydoclint-baseline.txt` empty: prefer fixing the violation, and do not let the file
grow back silently. `check-class-attributes` stays `false` until upstream fixes it — do
not flip it back on (`pyproject.toml` and `DECISIONS.md` carry the evidence).

The pytest markers are listed in `pytest.ini`. `e2e` and `integration` are applied
**automatically by path** in `tests/conftest.py` - do not hand-apply them.

## Architecture

Two layers using the same MVC pattern recursively: an app-shell triad (`MainModel` /
`MainView` / `MainController`) and a plugin system for everything else — analysis tabs and
data plugins. **Load the `plugin-architecture` skill** before adding, moving or
restructuring a plugin, a `Meta*` base or an analysis tab; it carries the two plugin
families, the signal-relay bus, discovery, and the `BaseDataPlugin` settings lifecycle.
Three rules apply regardless:

- Cross-tab behavior goes through the `MetaController` signal relay, never a direct import
  of another tab's controller.
- New data plugin: **generate it, don't hand-write it** —
  `python scripts/new_plugin.py MetaEventFinder MyFinder` (`--list` shows the eight
  families and every shipped plugin). Signatures and docstrings are copied from the base
  verbatim, which is what the compliance test's exact-equality comparison requires.
- New analysis tab: a Controller/Model/View triad under
  `poriscope/plugins/analysistabs/`, subclassing `MetaController`/`MetaModel`/`MetaView`
  and following an existing tab as a template.

## Testing conventions

- **Run the whole suite before every commit: plain `pytest`, no path arguments and no
  marker filter.** A full run is ~2.5 minutes, so there is no reason to select a subset,
  and choosing one is itself the error-prone step — a scoped run that skipped
  `tests/unit/controllers/` once let a broken commit reach CI. Iterating on a single
  failing test while debugging is fine; the gate is a full green run immediately before
  the commit. Documentation-only changes (docstrings, comments, markdown) need no run.
- `tests/unit/` mirrors `poriscope/{controllers,models,views,plugins,utils}`, with one
  exception: the analysis-tab triads under `poriscope/plugins/analysistabs/` are tested in
  `tests/unit/views/` and `tests/unit/controllers/`, while `tests/unit/plugins/analysistabs/`
  covers only the `utils/` helpers.
- `tests/unit/plugins/test_plugin_compliance.py` recursively imports every module
  under `poriscope.plugins` and asserts each plugin subclass implements all abstract
  methods of its `Meta*`/`BaseDataPlugin` base — this is the guardrail that keeps the
  plugin contract intact; run it after touching any `Meta*` base or plugin signature.
  Note it compares generic annotations (`List[str]` and friends) by **equality**, using
  `issubclass()` only when both sides are plain classes — so widening or correcting a
  base method's annotation breaks every subclass whose override does not match it
  exactly. Annotate a plugin method by copying the base signature verbatim rather than
  inferring it from the body.
- **Never pass test paths in a hand-picked order** on the rare occasion you pass any.
  Pytest runs explicitly listed paths in the order given, and inverting natural collection
  order (e.g. `pytest tests/unit/views tests/unit/plugins`) has reliably segfaulted the
  interpreter from leaked Qt state, and makes `test_plugin_compliance` audit test doubles
  that natural order never exposes it to. Relatedly, never pipe a test run through
  `tail`/`grep` as its only record — a faulthandler dump names the crashing test at the
  *top* of its output, which is exactly what a tail discards — and never call a run green
  from a progress line; read the real summary line.
- `tests/integration/flows/` instantiate real controller/model/view stacks
  "no_gui" (headless) for cross-plugin flows; `tests/e2e/` drive actual Qt widgets
  (`e2e_ux` marker) end-to-end. **CI runs the entire suite on every branch push,
  fork PR, internal PR and release** - there is no subset and no marker filter.

## Docs

Sphinx docs live in `docs/` and are largely autogenerated from plugin docstrings via
`scripts/autodoc/*.py` / `scripts/generate_all_autodoc_rst.py`, run automatically by
the `post-merge` git hook. Published at https://tcossalab.github.io/poriscope/.

## Changelog

Any time you make changes to the code, update `changelog.md` under the appropriate
header/subheader, respecting the formatting conventions already present in that file.

**One line per change, and no more.** `changelog.md` is written for *users*: it carries the
essential user-facing information and nothing else. No sub-bullets, no evidence, no
measurements, no explanation of why the change was made or what was rejected on the way
there. Breaking changes are still called out explicitly as breaking, because that is
user-facing.

Everything you would otherwise have put in those sub-bullets goes in `DECISIONS.md`, which
is written for devs and for Claude: the reasoning behind a choice, the alternatives scoped
and rejected, the measurements that settled a question, and what would make it worth
revisiting.

## Where things are written down

- `changelog.md` — what changed, user-facing. Update it for any code change.
- `future_fixes.md` — what is still queued. Keep it terse; prune items as they land
  rather than leaving completed-work narrative behind. Delete a landed entry outright —
  do not mark it `**Fixed**`, strike it through with `~~`, or retitle its section
  `DONE`/`CLOSED`; the history already lives in `changelog.md`. When only part of an
  item lands, delete it and rewrite what remains as a forward-facing item.
- `DECISIONS.md` — why we chose *not* to do something, with the evidence and what
  would make it worth revisiting. Check here before re-litigating a settled question.
- `future_refactors_and_features.md` — larger speculative work.
- `fit_fallbacks.md` — every fallback path in `PeakFinder`'s shared double-Gaussian fit
  chain (`fit_threshold` and its callees) and how each classifier responds to a degraded
  fit. **Update it whenever a fallback is added, removed, or changes what it degrades to**,
  when a classifier changes how it responds, or when one of the fit constants changes.
- `docs/source/utils/user_manuals/plugins_manual/development_workflow/quality_control.rst`
  — the contributor-facing description of the QA gates. Hand-written, not autogenerated.
  **Update it whenever the tooling or its configuration changes** (`mypy.ini`,
  `.pre-commit-config.yaml`, `[tool.pydoclint]`, the baseline policy), or it will go on
  telling contributors a policy that no longer holds.

**All three of `changelog.md`, `DECISIONS.md` and `future_fixes.md` should be as terse as
possible.** Two of them are written for Claude, so every needless sentence is context spent
on a future read. Cut the prose, keep the facts: a `future_fixes.md` entry is one to three
lines carrying the `file:line` and the measured number, and a `DECISIONS.md` entry keeps its
context/decision/evidence/revisit shape in as few sentences as the reasoning survives in.
Never drop the measurement itself — a queued finding without its number has to be
re-measured before it can be worked.

Depth belongs in those files, not in this one: this file is loaded in full at the start
of every session, so it should stay a short list of standing rules.

## General Instructions

- Prefer module- or class-level functions over nesting one function inside another, but
  **a nested function is fine where it is genuinely the simpler option and the nested
  function is short and simple** - typically a small closure that captures a local so it
  can be handed to a callback, a timer or a signal. Reach for a hoisted method plus
  `functools.partial` when the closure grows, is reused, or needs testing on its own; do
  not hoist a three-line callback just to avoid nesting, and do not "flatten" an existing
  one that reads well. Decorators always nest, because they require a closure -
  `utils/LogDecorator.py` and `utils/SerializeDecorator.py` are the two modules that exist
  today; if you add another, say in a comment that this is why it nests.
- **Never add `@overload` or `cast()` to work around an over-broad return union.** Verify
  every incoming call and delete the dead branch instead. If both arms are genuinely live,
  flag it for review rather than overloading - the fix is usually to change the callers.
  See `DECISIONS.md`.
- **Call out breaking changes explicitly in `changelog.md`**, rather than describing them
  as ordinary fixes. Narrowing or removing anything on a `Meta*` ABC counts.
- Imports go at module level. Do not add function-local ("lazy") imports, and hoist
  any you come across. The only exception is a real circular import, which goes in an
  `if TYPE_CHECKING:` block with a comment explaining the cycle (see
  `views/widgets/icon_menu_widget.py` for the pattern).
- When the user reports a bug to you and asks you to fix it, double check the assumptions 
  before implementing the fix. Do not blindly accept the assertions of the user as to the
  cause of potential issues. Be thorough in your analysis, ensuring that you fully trace 
  related logic paths to ensure that nothing breaks downstream as the result of an applied
  fix, and explain any issues surfaced to the user and request input before proceeding if
  you find that a user-based assumption or instruction would cause problems.
- We are not in a rush, and the poriscope codebase is complex. Take the time and spend the 
  tokens you need to get it right.
- Before finishing any tasks, verify that the docs (both auto generated and hand-written) 
  accurately reflect the changes, and mmake any necessary updates to the docs to keep them
  in sync with the codebase.

## Version Controller

- Poriscope uses git flow worksflows. feature branches are branched off `develop`, not `main`,
  keep that in mind when doing code review on feature branches or merging anything.
- Release tags carry a `v` prefix (`v1.7.0`), because `.github/workflows/release.yml`
  triggers on `tags: ['v*']`. `scripts/setup_hooks.py` sets `gitflow.prefix.versiontag`
  to `v` so plain `git flow release finish <version>` does this; git config is per-clone,
  so a fresh checkout needs that script run before cutting a release.
