# Future Fixes

Queued work and standing policy for the Poriscope codebase. Keep this terse: prune
items as they land rather than leaving completed-work narrative behind. Reasoning about
things deliberately *not* done lives in `DECISIONS.md`; what changed lives in
`changelog.md`.

**The full-codebase type-annotation pass is complete (2026-08-26).** Every function
under `poriscope/` is annotated with no exclusions, `.pydoclint-baseline.txt` is a
zero-byte file, and `mypy.ini` enforces `disallow_untyped_defs`, `check_untyped_defs`
and `strict_equality`. All four pre-commit gates are green. The step-by-step plan, the
batch tables and the retrospective that used to fill this file have been removed now
that they describe finished work; the narrative is in `changelog.md` and the standing
rules that came out of it are in `CLAUDE.md` and `DECISIONS.md`. What remains below is
only what is still open.

## Still queued

- **Aborting any operation produces no message in the panel.** `MetaController`'s
  `handle_kill_worker`/`handle_kill_all_workers` only call `self.logger`, so a user whose
  log level is above INFO gets no confirmation that a stop took effect - for every
  operation, not just CSV export. Note a data plugin **cannot** emit to the panel: it is a
  plain `ABC` with no signals, and the established route is returning a string from
  `report_channel_status()`, which `MetaModel.generate_report` relays. `add_text_to_display`
  exists only on `MetaController`/`MetaModel`/`MetaView`, so that is where any fix belongs.
- **A duplicated call** in `IconTextMenuWidget.menu_button_clicked`: it schedules
  `QTimer.singleShot(100, self.uncheckMenuButton)` twice in a row. Idempotent, so
  harmless, but plainly a copy-paste artifact.

## Exclusions (standing project policy)

Revised 2026-08-25. These three files are no longer excluded wholesale; the exclusion
now splits by *kind of change*.

- `NanoTrees.py` — likely to be deprecated soon.
- `Basic_PeakFinder.py` / `PeakFinder.py` — owned by another developer.

**Docstring, signature and type-hint changes: in scope.** All three are now fully
annotated and report zero pydoclint violations.

**Logic changes: out of scope, unconditionally.** This holds even when annotating
surfaces a real bug, and several did. Write the honest annotation describing what the
code does today, mark the defect with a narrow `# type: ignore` and a `NOTE:` at the
site, record it under "Defects in the formerly excluded fitter plugins" below, and leave
the fix to the owning developer.

## Defects in the formerly excluded fitter plugins - flagged, never to be fixed here

Policy as of 2026-08-25: `NanoTrees.py`, `PeakFinder.py` and `Basic_PeakFinder.py` are
**in scope for docstring, signature and type-hint work but never for logic changes**,
even when annotating surfaces a real bug. The logic in these files belongs to another
developer. Everything below was found while annotating and left in place, marked with a
narrow `# type: ignore` and a `NOTE:` comment at the site.

- **`find_mode_blockage_level` guards two of its three Optional parameters.** In both
  `PeakFinder.py` and `Basic_PeakFinder.py` the body explicitly handles `data is None`
  and `baseline_std is None`, then computes `abs(data_min - baseline_mean)` with no
  guard at all on `baseline_mean`, which is equally `Optional[float]` under the
  `MetaEventFitter` contract. A caller with no baseline estimate gets a `TypeError`.
  The asymmetry looks like a simple oversight rather than a decision.
- **`PeakFinder.filter_peaks` multiplies by a possibly-`None` `baseline_std`** at three
  adjacent lines (`type0_thresh`/`type1_thresh`/`type2_thresh`). Same root cause.
- **`Basic_PeakFinder._populate_event_metadata` can put `None` into event metadata.**
  It assigns `baseline_mean` and `baseline_std` straight into `event_metadata`, whose
  declared value type is `Union[int, float, str, bool]`. A `None` reaching the database
  writer downstream is not something that contract allows for.
- **`PeakFinder.filter_peaks` treats a sample count as microseconds.** Its only caller
  passes `len(data[padding_before:-padding_after])` as `event_length`, and the body then
  computes `event_length * samplerate * 1e-6` and logs it as
  `f"event_length={event_length:.1f} us"`. Either the argument or the label is wrong.
- **`NanoTrees._DNA` slices with two unguarded `Optional[int]` paddings.**
  `data[:padding_before]` and `data[-padding_after:]` are computed with no `None`
  check, so the negation raises `TypeError` for any event loader that supplies
  neither. The method has no live caller today - the only call site is commented out
  inside `_locate_sublevel_transitions` - which is presumably why it has gone unnoticed.
- **`NanoTrees._locate_sublevel_transitions` overwrites both baseline arguments.**
  Its first two statements recompute `baseline_std` and `baseline_mean` from
  `data[:padding_before]`, discarding whatever the event loader passed in. That may
  well be deliberate, but it means the two parameters are inert and the docstring's
  promise to "handle gracefully the case where any of the arguments except data are
  None" is met by accident rather than by design.
- **Both PeakFinders' `sublevel_starts` really holds dicts, not indices.** Their
  `_locate_sublevel_transitions` returns a list of dicts keyed `"type"` and friends. This
  is now consistent rather than broken - the `MetaEventFitter` contract was widened to
  `List[Any]` to match what it has always actually produced - but it is worth knowing
  that the parameter name still says "starts" while the payload is per-sublevel records.

## Open against the PeakFinder integration (2026-08-26)

Found while merging `feature_Peakfinder_classifier` into the docstring/type work. The
defects below were **authorised for repair** and have been fixed - each carries a
`NOTE (integration):` comment at the site explaining what changed and why, so the owning
developer can see it when she re-branches. What remains open is listed under "Still open"
at the end of this section.

### Fixed during the integration

- **`fit_2_gauss` could never succeed.** Its nested `Gauss` declared four parameters
  (`x, Amplitude, mean, stdev`) but was called with five in both places inside `Gauss_2`,
  so every call raised `TypeError`; the `curve_fit` call is wrapped in a bare
  `except Exception`, which swallowed it and took the `popt is None` path forever. Since
  the return statement unpacks `popt` in two groups of four, four parameters per Gaussian
  is the intended shape, so `Gauss` gained an `offset` term and `Gauss_2`'s parameters
  were renamed from `A/x/m/s` to `A/u/s/c` to say which is which.
- **`find_mode_blockage_level` used `baseline_mean` unguarded.** Now raises `RuntimeError`
  up front. Its `baseline_std` handling was also a `float()` inside a bare
  `except Exception`, which made a legitimately-`None` value indistinguishable from a
  conversion failure; the `None` case now selects the `'auto'` binning path explicitly.
- **`redefine_padding` divided by `2 * baseline_std` with no `None` check.** Now raises.
- **`filter_peaks` scaled every threshold by a possibly-`None` `baseline_std`** at seven
  sites. Guarded once at function entry with a raise.
- **`_populate_event_metadata` passed metadata-dict values straight into
  `find_mode_blockage_level`**, where the base contract's
  `Union[int, float, str, bool]` is wider than the `Optional[float]` accepted. Now
  narrowed with explicit `isinstance` checks that raise on a non-numeric value, and the
  returned primary level is checked for `None` before being stored.
- **A dead `None` test in `_save_classification_report`.** It called
  `float(prominence_stats.get("threshold"))` and only *then* tested
  `threshold is not None` - a test that can never fire, since `float()` either returns a
  float or raises. A missing key therefore raised `TypeError` instead of skipping the
  line. The check now guards the conversion, and the `cast()` it needed is gone.
- **Two `float(bt.get("midpoint"))` calls** on an `Optional` lookup, in
  `_classify_peak_prominences` and `_classify_translocation_direction`. Both now raise.
- **`test_cluster_of_type1_labeled_type3` deleted** as out of date, on instruction: it
  asserted that two nearby type-2 peaks both become type 3, which the current clustering
  logic does not do.

### Closed by decision, not by code

Both settled 2026-08-25; the reasoning is in `DECISIONS.md`. Recorded here only so they
are not re-raised as open work.

- The four `# type: ignore[assignment]` on the deliberate `None` placeholder writes in
  `_populate_event_metadata` **stay**. They are safe and correct; clearing them would mean
  widening a `Meta*` ABC across six fitter plugins.
- The **double-Gaussian consolidation is not being pursued here.** The owning developer is
  rewriting that fitting code from scratch, which supersedes it. `fit_2_gauss`, the dead
  third implementation, has already been deleted.

### Still open

- **`SQLitePeakDBLoader` no longer casts its interpolated SQL values to `int`.** Reviewed
  and **deliberately accepted**: the database is a local file owned by the user running
  the app, so there is no privilege boundary for an injection to cross. Recorded here
  only so the same finding is not re-raised. This also downgrades the `S608` item in the
  bandit proposal below, which described these sites as "worth real scrutiny".
- **Three nested function definitions** remain: `dgfit` inside `bitthresh`, and formerly
  `Gauss`/`Gauss_2` inside the now-deleted `fit_2_gauss`. `CLAUDE.md` forbids nested
  functions but nothing enforces it (that is block 8 below). Annotated in place and left
  nested, on instruction.
- **The histogram low-end cut-off in the classifier plots.** Diagnosed but not fixed, and
  parked pending the double-Gaussian rewrite: the "All Events (incl. outliers)" bar chart
  is binned against edges `bitthresh` computed from a *filtered subset*, and
  `np.histogram` silently discards values outside the given bin range. Which subset wins
  is decided by discrete ratio tests, so the plot's left edge jumps to the 25th percentile
  when the blockage-filter re-run branch fires - which is why the cut-off appears at
  certain threshold settings and not others. Three call sites share the pattern
  (`_classify_folded_unfolded`, `_classify_peak_prominences`,
  `_classify_translocation_direction`). The fix is to build the histogram once from the
  full data and pass it into the fit, rather than letting the fit dictate the plot's bins.

## Also queued - found during the type-annotation pass, not part of it

- **`pydoclint` class-attribute bug - filed upstream, now awaiting a fix.** Reported to
  the maintainer as https://github.com/jsh9/pydoclint/issues/304; jsh9 maintains both
  `pydoclint` and `docstring_parser_fork`. Nothing to do here until a release lands -
  `check-class-attributes` stays `false` in `pyproject.toml` in the meantime. Kept in
  case the report needs restating: the one-line fix is to replace the two hardcoded
  `".. attribute ::"` literals in `rest_attr_parser.py` with
  `re.compile(r"^\.\.\s+attribute\s*::\s*(?P<name>.+)$")`, which accepts both spellings
  so no existing docstring breaks. Reproduction: a class documented with the *correct*
  `.. attribute::` directive plus any `:param:` block reports `DOC601` + `DOC603`;
  adding a space before the `::` makes it pass. Full diagnosis in `DECISIONS.md` under
  the `IntroDialog` entry.

- **Adopt the rest of ruff `bugbear` (B) and `bandit` (S).** Proposed in review on the
  grounds that both run against real code logic and so complement pydoclint's
  docstring/signature checking for catching silent bugs. `B006` and `B020` are **done**
  and are now enforced through `extend-select` in `pyproject.toml`; everything below is
  what is left. Re-measured on `poriscope/` (2026-08-25): **B = 104, S = 54**. `tests/`
  adds 10 more B hits, one of which is a `B023` closure-over-a-loop-variable - a real
  bug class, but test code belongs to another developer.

  | Rule | Hits | Character |
  | --- | --- | --- |
  | `B905` zip-without-explicit-strict | 54 | **Audited and closed 2026-08-25; deliberately not enabled as a gate.** 50 sites were in scope (the other 7 are in owner-held fitter files); 43 zipped sequences that are built together and need nothing. The 4 that mattered are fixed: 3 in `MetadataView` were silently dropping plot features that had no label, and `ClusteringView` no longer mutates `columns`, so its two zips now assert their alignment with `strict=True` rather than depending on truncation to hide the appended `"id"`. `SQLiteDBWriter`'s sublevel transpose was verified equal-length upstream and now says so with `strict=True`. Not enabled because the 54 remaining sites would each need their own `strict=` decision, and at least one - the list-against-generator zip in `MetaDatabaseLoader` CSV export - cannot be proven equal-length in advance. The rule earned its keep as a one-time audit. |
  | `B904` raise-without-from-inside-except | 24 | loses the exception chain; mechanical but touches `raise` statements |
  | `B007` unused-loop-control-variable | 20 | mostly cosmetic |
  | `B010` set-attr-with-constant | 2 | both in `LogDecorator.py`; cosmetic |
  | `B028` no-explicit-stacklevel | 1 | one `warnings.warn` in `MetaWriter.py`; cosmetic |
  | `S608` hardcoded-sql-expression | 25 | **downgraded.** The database is a local file owned by the user running the app, so there is no privilege boundary for an injection to cross. Settled - see the `SQLitePeakDBLoader` note above. |
  | `S110` try-except-pass | 13 | **Triaged 2026-08-25; all 13 remaining are in `PeakFinder.py`.** The 6 that were in our own code are fixed: two `set.remove()` handlers became `set.discard()`, one settings-value type test narrowed to `except AttributeError`, and three cosmetic `tight_layout` handlers now log at debug. Enabling the rule would need either the owner to fix hers or a `per-file-ignores` entry for `PeakFinder.py` - the latter hides a real check rather than satisfying it, so it is not proposed. |
  | `S101` assert | 8 | asserts in non-test code |
  | `S112` try-except-continue | 1 | the single site is in `PeakFinder.py` (`_classify_folded_unfolded`, a bare `continue` on an array index); see the `S110` row. |

  Almost every remaining fix is a logic change, so this is unclaimed rather than
  blocked. `B905`, `S110` and `S112` are all now audited and closed as non-gates (see
  their rows above); what they surfaced in our own code is fixed, and what remains sits
  in owner-held files. Next up is `B904`, then `S101`. Re-measure before starting, and
  enable each rule only once its own backlog is zero, the way `B006`/`B020` were.

  Note this overlaps, but is not the same as, the bandit proposal in the
  community-plugin block below: that one is scoped to `poriscope/plugins/` as a trust
  boundary for unvetted contributions, this one is codebase-wide as a bug-catcher.

- **`hist_data` holds three shapes.** In both `MetadataView` and `ProteinView` it
  receives 1-D arrays from the histogram path, whole DataFrames from the density path,
  and `(x, y)` tuples from the all-points path. Widened to `List[Any]` with a comment;
  unifying it is a real refactor.

---

# Future Fix: Community-Contributed-Plugin Compliance Gate

The context blocks below were designed together, as a set: the goal is a pipeline that
lets a community-contributed data plugin (or, occasionally, a frontend analysis-tab
plugin family) be verified as safe and correct to merge with a bounded amount of human
review, instead of relying entirely on a reviewer reading the diff. Each block below is
independently actionable and can be picked up in its own future session; the suggested
order is 1 → 2 (cheap, static, highest signal) → 3 (makes 1/2 easy to satisfy from the
start) → 4/5 (merge-gating infrastructure) → 6/7/8 (rounding out coverage).

## 1. Behavioral conformance suite (not just signature compliance)

**Goal.** A test suite that instantiates every discovered plugin and actually runs its
core method(s) against small synthetic data, asserting it behaves like a well-formed
member of its `Meta*` family — not just that it has the right method names.

**Why.** `tests/unit/plugins/test_plugin_compliance.py` already does the hard part of
discovery: it walks `poriscope.plugins` with `pkgutil.walk_packages`, imports every
module, and (via `BASE_CLASS_DATA`) knows which concrete classes implement which
`Meta*` base. But it only checks `__abstractmethods__`/type-hint compliance — it never
calls the plugin. A community-contributed plugin can satisfy every signature check and
still crash immediately on real data, leak resources, or silently produce garbage.

**Implementation plan.**
1. Add `tests/unit/plugins/test_plugin_conformance.py`, structured like
   `test_plugin_compliance.py` (reuse its discovery loop and `META_CLASSES` set) but
   parametrized over *concrete* plugin classes rather than base classes.
2. For each `Meta*` family, define one canonical synthetic fixture already present
   under `tests/synthetic_data/` (`synthetic_chimera.py`/`multichannel_chimera.py` for
   readers, `synthetic_events_db.py` for db loaders/writers, `synthetic_metadata_db.py`
   for metadata-consuming plugins) and a minimal valid `settings` dict built from each
   plugin's own `get_empty_settings()` (fill required `Value`s with the midpoint of
   `Min`/`Max` or the first `Options` entry — this doubles as a smoke test that
   `get_empty_settings()` itself returns a self-consistent schema, see block 2 below).
3. Write one generic conformance check per `Meta*` family (not per plugin) that:
   - instantiates the plugin with the synthetic settings dict,
   - drives it through its family's real lifecycle (e.g. for `MetaEventFinder`: find
     events on a synthetic trace and assert the returned event boundaries are
     monotonic, in-bounds, and non-overlapping; for `MetaReader`: `load_data` on a
     synthetic channel and assert dtype/shape match `get_raw_dtype()`/declared
     channel count; for `MetaEventFitter`: fit a synthetic event and assert
     `_populate_event_metadata`'s return dict has the keys the base class documents),
   - calls `close_resources()` afterward and asserts no exception and no dangling
     open file handles/db connections (e.g. via `psutil.Process().open_files()` diffed
     before/after, if `psutil` is already a dependency, otherwise skip this specific
     assertion rather than adding a new dependency just for it).
4. Register this as its own pytest marker (e.g. `conformance`) so it can be run
   standalone in CI for exactly the plugin file(s) that changed in a PR (see block 5).

**Gotchas.** This will only be as strong as the synthetic fixtures are representative —
keep the fixtures' parameters (trace length, noise level, event count) realistic enough
that a finder/fitter can't trivially pass by doing nothing. Don't try to make one
mega-fixture cover every family; a small dedicated fixture per family, reused across
all plugins in that family, is easier to reason about and keeps failures attributable
to the plugin under test rather than the fixture.

**Verification.** Run against every *existing* in-repo plugin first (they should all
pass, since they're already trusted) before treating a conformance failure on a new
contribution as meaningful signal.

## 2. Settings-schema linter for `get_empty_settings()`

**Goal.** A static (no I/O, no instantiation-with-real-data-required) check that a
plugin's declared settings schema is internally self-consistent.

**Why.** `BaseDataPlugin.get_empty_settings()` (see `poriscope/utils/BaseDataPlugin.py`)
returns `Dict[str, Dict[str, Any]]` entries shaped `{"Type", "Value", "Options", "Min",
"Max"}`, and `_validate_param_types`/`_validate_param_ranges` check a *supplied*
settings dict against this schema at runtime, per-instantiation. Nothing currently
checks the schema itself for self-consistency independent of any particular value
supplied — e.g. `Min > Max`, a `Value`/`Options` list mixing incompatible `Type`s, or a
`Type` that doesn't match the Python type of `Value`. These are exactly the kind of
copy-paste mistake a first-time contributor adapting an existing plugin would make.

**Implementation plan.**
1. Add a small pure-Python validator, e.g.
   `poriscope/utils/settings_schema.py::validate_settings_schema(schema: dict) -> list[str]`
   returning a list of human-readable problems (empty list = clean), checking per
   parameter entry: `Type` and `Value` keys are present; if `Value is not None`,
   `isinstance(Value, Type)`; if both `Min` and `Max` are set, `Min <= Max`; if
   `Options` is set, every option's type matches `Type` and (if `Value is not None`)
   `Value in Options`.
2. Add a fast, no-fixture-needed pytest test (can live in `test_plugin_compliance.py`
   itself, right next to the existing structural checks, or as a new
   `test_settings_schema.py`) that calls `plugin_cls().get_empty_settings()` for every
   discovered concrete plugin class and runs it through `validate_settings_schema`,
   asserting an empty problem list. (Most plugins' `get_empty_settings()` should be
   callable without a fully-populated `settings` dict — confirm this holds for all
   existing plugins first; a few may need `standalone=True` passed.)
3. This is cheap enough to run as a blocking pre-commit/CI check on every PR touching
   `poriscope/plugins/**`, well before the more expensive conformance suite in block 1.

**Gotchas.** `Options`/`Min`/`Max` are explicitly optional (can be `None`) per the
existing docstring — don't require them, only check consistency *when present*.

## 3. Contribution scaffold / template generator

**Goal.** Shift compliance left: a new plugin should start out already satisfying
pydoclint, mypy, `test_plugin_compliance.py`, and (once built) blocks 1 and 2 above,
rather than a contributor discovering violations only after opening a PR.

**Why.** Every plugin family's abstract method list, docstring style (sphinx-style,
per `[tool.pydoclint] style = "sphinx"`), and settings-schema shape is already fully
determined by its `Meta*` base — there's no reason a contributor should hand-write
this from a blank file when it can be generated correctly the first time.

**Implementation plan.**
1. Add `scripts/new_plugin.py`, invoked like
   `python scripts/new_plugin.py --family MetaEventFinder --name MyEventFinder`.
2. For the given `--family`, use `inspect` on the corresponding `Meta*` class (same
   introspection `test_plugin_compliance.py` already does via
   `get_required_methods`/`__abstractmethods__`) to generate a stub subclass in the
   right `poriscope/plugins/<category>/` folder, with:
   - one method stub per abstract method, each with a sphinx-style docstring skeleton
     whose `:param:`/`:return:`/`:rtype:` entries are pre-filled from the base method's
     own signature and docstring (so pydoclint passes on the stub immediately),
   - a `get_empty_settings()` stub returning one example parameter entry with a comment
     showing the full `{"Type", "Value", "Options", "Min", "Max"}` shape,
   - a matching `tests/unit/plugins/<category>/test_my_event_finder.py` stub that
     imports the new class (so `test_plugin_compliance.py`'s discovery picks it up
     immediately) and includes a placeholder for the block-1 conformance test.
3. Document the script in `CLAUDE.md` under "Where to add a new plugin" as the
   recommended starting point (the existing prose there, pointing at "an existing tab
   (e.g. `Protein*`) as a template," is a weaker substitute for a scaffold that's
   guaranteed to already pass every check).

**Gotchas.** Keep the generated stub minimal (raise `NotImplementedError` in method
bodies) — the goal is a compliant skeleton, not a working plugin; don't try to
generate real algorithmic logic.

## 4. Static security review for module-level plugin code

**Goal.** Reduce the trust risk inherent in blindly executing arbitrary community-
submitted `.py` files inside a desktop app running with the user's full privileges.

**Why.** Per `MainModel.populate_available_plugins()`'s documented behavior, plugin
discovery imports *every* `.py` file found under `poriscope/plugins/` (and the user
plugin folder) — and Python import always executes module-level code unconditionally,
before any of `test_plugin_compliance.py`'s reflection even runs. For in-house
contributors this is an accepted, low-risk convenience; for unvetted community
submissions landing in the same discovery path, it's a real code-execution trust
boundary that none of the current tooling (ruff/mypy/pydoclint) is designed to police.

**Implementation plan.**
1. Add `bandit` to `requirements-dev.txt` and run it as a `pre-commit` `repo: local`
   hook scoped to `files: ^poriscope/plugins/` (mirroring how the pydoclint hook is
   already scoped), using a conservative rule subset first (e.g. flag
   `subprocess`/`eval`/`exec`/`pickle.load`/dynamic `importlib` calls, network access,
   and filesystem writes outside of an expected data directory) to avoid a noisy
   first run.
2. Additionally add a narrow, purpose-built AST check (simpler and more targeted than
   general-purpose `bandit` rules) that flags any *module-level* statement in a plugin
   file other than imports, constants, and class/function definitions — since a
   compliant plugin should never need top-level side effects, and "module-level code
   that does something when merely imported" is the single highest-risk pattern for
   this specific discovery mechanism.
3. Triage findings as blocking (network/subprocess/eval/exec) vs. advisory (everything
   else) — don't try to make `bandit`'s full default rule set blocking on day one, or
   it will generate enough noise to undermine trust in the check.

**Gotchas.** This is a deliberately narrow first pass, not a sandbox — it raises the
bar for a careless or lazy submission but is not a defense against a determined
adversary (a plugin can still do plenty of damage inside a legitimate-looking method
body that only runs once instantiated). True sandboxing (subprocess isolation,
restricted execution) is a much larger architectural change and is explicitly out of
scope here; if that level of isolation is ever wanted, treat it as a separate,
much larger design discussion, not an incremental addition to this one.

## 5. Required, scoped CI gate + CODEOWNERS for `poriscope/plugins/**`

**Goal.** No plugin file merges without both automated checks (scoped to just the
changed plugin) and a human sign-off — formalizing, for everyone, the informal
per-plugin "ownership" that already exists for a few plugins today.

**Why.** `.github/workflows/ci-fork-pr.yml` already exists specifically for
fork-originated PRs (the realistic path for a community contribution) and already runs
strict `pre-commit run --all-files` plus `pytest -m fast` with `contents: read`
fork-safe permissions — this is the right place to add plugin-specific gating rather
than inventing a parallel workflow. There is currently no `CODEOWNERS` file in the
repo, so plugin review isn't enforced by GitHub at all today.

**Implementation plan.**
1. Add a `CODEOWNERS` file at the repo root mapping each
   `poriscope/plugins/<category>/` folder (and, once it exists, `poriscope/utils/Meta*`)
   to the relevant maintainer(s)/owner(s) — this only takes effect as a *required*
   review gate once "Require review from Code Owners" is turned on for the target
   branch's protection rule in repo Settings (an out-of-repo, admin-only config step;
   note it explicitly here so it isn't forgotten as "already handled" just because the
   file exists).
2. In `ci-fork-pr.yml`, add a step after checkout that computes the changed files
   (`git diff --name-only origin/${{ github.base_ref }}...HEAD`) and, if any match
   `poriscope/plugins/**`, runs the block-2 settings-schema check and block-1
   conformance suite scoped to just those files (e.g.
   `pytest -m conformance -k <derived from changed filenames>`), in addition to the
   existing `pytest -m fast` step — so a plugin-touching PR gets strictly more
   scrutiny than a non-plugin PR, without slowing down every PR with the full
   conformance suite.
3. Mark this new step (and the existing strict `pre-commit` step) as required status
   checks in branch protection for `main`/`develop`.

**Gotchas.** `ci-fork-pr.yml`'s permissions are deliberately `contents: read` for fork
safety — don't add anything to this workflow that needs write access (e.g. auto-fix
commits); that's what `ci-internal-pr.yml` is for, and it isn't fork-safe.

## 6. Docs-render check in CI (Sphinx warnings-as-errors)

**Goal.** Catch a plugin whose docstrings are pydoclint-compliant but still break
Sphinx rendering, before merge rather than after.

**Why.** `.github/workflows/build_and_deploy_docs.yml` only runs
`scripts/generate_all_autodoc_rst.py` + `sphinx-build -b html docs/source docs/build`
on push to `main` (or manual dispatch) — never on a PR, and without `-W`
(warnings-as-errors), so a bad cross-reference or malformed directive in a new
plugin's docstring currently surfaces, if at all, only after it's already merged and
deployed.

**Implementation plan.**
1. Add a `docs-check` job to `ci-fork-pr.yml`/`ci-internal-pr.yml` (or a new dedicated
   PR-triggered workflow) that runs the same two commands
   (`python scripts/generate_all_autodoc_rst.py` then
   `sphinx-build -b html docs/source docs/build`) but with `-W --keep-going` so
   warnings fail the build and all of them are reported in one pass rather than
   stopping at the first.
2. This job doesn't need the full Qt/Xvfb system dependency set that the test jobs
   need (autodoc generation and Sphinx build don't launch the app) — keep it as a
   lighter, faster job so it doesn't slow down the PR feedback loop.
3. No need to deploy anything from this job — it's a build-only check; reuse
   `actions/upload-artifact` only if reviewers want a preview of the rendered docs.

**Gotchas.** Turning on `-W` will likely surface pre-existing warnings from plugins
already in the repo, not just future ones — expect an initial cleanup pass (grandfather
via a suppression list keyed by warning text, mirroring the `.pydoclint-baseline.txt`
pattern, if the initial warning count is large) before this can be made blocking.

## 7. Fuzz / malformed-input testing for data readers

**Goal.** Catch unhandled crashes in community-contributed parsers on truncated,
corrupted, or otherwise malformed binary input — the single most likely crash surface
for a new `MetaReader` subclass, since readers parse arbitrary externally-produced
files by nature.

**Why.** None of the current checks (compliance, conformance from block 1, pydoclint,
mypy) exercise a reader against anything but a well-formed synthetic file. A community-
contributed reader for a new hardware/file format is exactly the plugin family most
likely to choke on a real-world file that's merely slightly off-spec (truncated
mid-record, wrong header magic, unexpected byte order) — the app should degrade
gracefully (raise a clear, caught exception) rather than crash or hang.

**Implementation plan.**
1. Add `tests/unit/plugins/datareaders/test_reader_fuzz.py`, parametrized over every
   concrete `MetaReader` subclass discovered the same way `test_plugin_compliance.py`
   does.
2. For each reader, take its family's existing valid synthetic fixture (e.g.
   `synthetic_chimera.py`'s output for `ChimeraReader*`) and generate a small, fixed
   set of deterministic mutations rather than open-ended random fuzzing (truncate to
   several byte offsets, flip the header's magic bytes, zero out a middle section) —
   deterministic mutations keep the test reproducible and avoid flaky CI, which
   open-ended `hypothesis`-style fuzzing would risk here.
3. Assert only that each mutation results in either a clean successful read (if the
   mutation happened to still be valid) or a caught, well-typed exception — never an
   unhandled crash, hang, or silent data corruption (e.g. returning a truncated array
   without signaling the truncation).
4. This test is necessarily reader-format-specific for the mutation *generation* step
   (each format's header/magic bytes differ), but the assertion logic and discovery
   loop should be shared/generic — write one small per-format "corrupt this fixture"
   helper per reader family, not per individual reader.

**Gotchas.** This only meaningfully applies to `MetaReader`; don't try to generalize it
to every plugin family — event finders/fitters/filters operate on already-validated
in-memory arrays, not raw external files, so this specific risk doesn't apply to them.

## 8. Custom lint rules encoding existing tribal knowledge

**Goal.** Make the project's already-established-but-only-documented-in-CLAUDE.md/
memory conventions mechanically enforced, so they don't depend on a human reviewer
remembering to check for them on every plugin PR.

**Why.** Several patterns are currently enforced only by convention and review
attentiveness: no nested function definitions, no bare `except:` (narrow to
`except Exception:` at minimum so a `Raises` docstring section is even possible), and
explicit `finally`-block cleanup of sqlite3 cursors/connections. These are exactly the
kind of thing a first-time community contributor won't know to do unless a machine
tells them.

**Implementation plan.**
1. No nested functions: a straightforward `ast`-based check (walk each `FunctionDef`
   node's body for a nested `FunctionDef`/`AsyncFunctionDef`) — add as a `ruff`
   custom rule if ruff's plugin API supports it cleanly for this project's ruff
   version, otherwise a small standalone script run as a `pre-commit` `repo: local`
   hook (same pattern as the pydoclint hook), scoped to `files: ^poriscope/`.
2. Bare `except:`: `ruff` already has a built-in rule for this
   (`E722`/`BLE001`-family, depending on ruleset naming in the installed ruff
   version) — check whether it's already enabled in this project's `pyproject.toml`
   ruff config before writing a custom check; if not, this is a one-line config
   addition, not new code.
3. Explicit sqlite3 resource cleanup in a `finally` block: harder to express as a
   generic AST rule (requires tracking whether a `sqlite3.connect`/`.cursor()` call's
   result is closed on every exit path) — likely not worth a fully general static
   checker; instead, cover this via the block-1 conformance suite's open-file-handle
   check for `MetaDatabaseLoader`/`MetaDatabaseWriter`/`MetaWriter` plugins
   specifically, which catches the same defect empirically rather than syntactically.
4. Document whichever of these become real automated checks in `CLAUDE.md`'s
   "General Instructions" section, replacing the current prose-only statement of the
   rule with a note that it's now enforced by `<tool>`.

**Gotchas.** Don't over-invest in generalized static analysis for the sqlite3-cleanup
rule specifically — it's a narrow, semantic (not syntactic) pattern where a runtime
conformance check is a better cost/benefit trade than a bespoke AST checker.
