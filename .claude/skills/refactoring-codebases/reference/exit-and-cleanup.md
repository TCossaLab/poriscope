# Exit review and post-refactor cleanup

The question this phase answers: *is the plan's account of what happened true, and what did all the
moving leave behind?* Start once the last structural change has landed.

## Contents

- The exit review
- The post-refactor cleanup procedure (11 steps)
- Instruments for dead test code
- Release readiness and burn-in
- X3 A breaking-change inventory must be derived, and honest in both directions
- X4 Code outlives the plan, so it must not cite the plan
- X5 Deletion residue is found by diffing name sets, not by reading
- X6 Retire the tooling that guarded the refactor
- X7 Regroup the changelog last, and verify the mapping by script

The general finishing lessons - X1 (a review that only files findings has not finished), X2 (a
sweep is finished only where its instrument looked), X8 (a flake is fixed, not re-run) and X9
(suite time grows with coverage) - are in the general skill's [finishing.md](../../planning-and-executing-changes/reference/finishing.md).

## The exit review

1. **Plan against reality.** Walk every step, sub-step, decision and gate row against what landed.
   Split the plan across read-only reviewers by section; re-check every weighty finding by hand
   (reviewer reports are claims too). Anything outstanding is done, deleted, or moved to the queue
   as a forward-facing item. Verify every "done" by behaviour and by date (V12, general skill).
2. **Before and after on every baseline metric**, measured at both ends with the same committed
   instrument (`templates/exit-review.md`). Report: targets met, missed, or ruled the wrong
   instrument; starting figures that do not reproduce, with why; what was deferred and why.
3. **Amend the decisions** that did not land as written, with the date and who ruled.
4. **Manual pass over the whole application**, including every path CI cannot exercise.

## The post-refactor cleanup procedure

One branch per step, a full green suite before every commit, and nothing deleted on a hunch: every
removal comes from an instrument, and a finding the instrument cannot settle goes to the owner.

```
Cleanup progress:
- [ ] 1. Plan against reality (the exit review, part 1)
- [ ] 2. Code against docs
- [ ] 3. Dead production code
- [ ] 4. Dead test code
- [ ] 5. Orphaned assets
- [ ] 6. Plan citations out of prose
- [ ] 7. Retire refactor-only tooling
- [ ] 8. Suite-time check
- [ ] 9. Exit review, before and after
- [ ] 10. Changelog regroup (last; re-run after burn-in)
- [ ] 11. Record it
```

1. **Plan against reality.** Re-check every claim the plan makes about the current tree. Credit
   nothing from a docstring example or a signature that predates the refactor.
2. **Code against docs.** Audit the hand-written documentation (generated docs regenerate
   themselves) for mechanisms that moved, pages describing a replaced design, and dead
   cross-references. Rewrite a page for a removed mechanism to explain its replacement - naming the
   old mechanism so searches still land there - rather than deleting it.
3. **Dead production code.** Methods with no production caller, write-only attributes, unused
   imports. Check each for dynamic dispatch (`getattr`, string-named signals, registries,
   serialized action names) before deleting. A test that exists only to call a dead method goes with
   it; a test that is the only coverage of live behaviour is re-pointed at the live path.
4. **Dead test code.** Mocks accept any attribute, so deletions leave residue nothing flags. Use the
   instruments below, in order of yield. Leave scaffolding another developer added and never used; it
   is not refactor residue.
5. **Orphaned assets.** Check every file under the docs' static/asset directories by basename against
   the whole repository.
6. **Plan citations out of prose.** Grep code, tests, scripts *and* docs of every file type for step
   numbers, decision letters and method-rule numbers (`scripts/find_plan_citations.py`); rewrite each as
   the mechanism it stood for. Fan out across agents on disjoint file sets, then prove with an AST diff
   that only prose changed (the general skill's `scripts/structural_diff.py prose`). Keep a tool's own data keys if the tool
   is itself plan-bound and is being retired.
7. **Retire refactor-only tooling.** Sort every gate the refactor built into "guards the refactor"
   (delete it, its tests, its CI steps, and any CI cost it alone justified) and "guards the result"
   (keep, and strip its plan citations).
8. **Suite-time check.** Record per-test setup/call/teardown durations; compare against the
   pre-refactor commit in a worktree outside any synced folder; re-run outliers alone on both commits
   before calling anything a regression. Growth that is new coverage stays.
9. **Exit review.** Before/after with one committed instrument per metric.
10. **Changelog regroup, last.** Group the release section by theme with breaking changes first; map
    entries by script and verify every entry appears once and every breaking entry sits under Breaking.
    Re-run after burn-in adds entries, before the version bump.
11. **Record it.** Update the plan and its shared page with what each step found; keep the decision log,
    work queue, contributor docs and agent instructions in sync; delete the plan when the release ships
    (which is why nothing that ships may cite it).

## Instruments for dead test code

In order of yield on the source refactor:

1. **Names present in the pre-refactor source and absent now, still referenced in tests**
   (`scripts/find_stale_names.py --baseline <tag>`). ~60 hits.
2. **A full run recording every attribute a patch created** - e.g. wrap `mock.patch(create=True)` and
   `monkeypatch.setattr(raising=False)` to log when the target attribute did not previously exist. Zero
   hits there, which is itself worth knowing.
3. **String patch targets whose name the target module no longer uses.**
4. **Module-level test functions and fixtures referenced nowhere outside their own body** (AST scan).
5. **Comment banners with no code beneath them, and docstring rosters ("Covers: ...") naming methods that
   are gone.** 70 empty banners.
6. **Tests whose only assertion is "does not raise"** against code that no longer does anything - make
   them assert what the code now emits, or delete a duplicate.

Coverage and duplication instruments help and neither is sufficient: dead code can be covered by a dead test.

## Release readiness and burn-in

- **Make cutting the release a mechanical act, then do not cut it yet.** Let the result burn in with real
  users on the integration branch. Defects returning from burn-in are the purpose of the exercise.
- **Build and install the real release artefact in a clean environment** - a fresh virtualenv or
  container, installing the built wheel/sdist/binary rather than an editable checkout - and run the app
  and a smoke test from it. A restructure moves files, and packaging manifests, entry points, package data
  and import paths that work in a checkout can be missing from the artefact.
- **Build what depends on you.** Plugins, extensions, downstream packages and scripts that import the
  public API: build or import each against the release candidate. A breaking-change inventory is a claim;
  a downstream build is the measurement.
- **Keep externally observable names stable, or call them out as breaking**: logger names, metric and
  trace names, CLI flags, config keys, environment variables, event names, file formats. Moving a module
  renames its logger and anything keyed on `__name__`; dashboards and alerts break silently.
- **Remove temporary scaffolding** the refactor added to stay green mid-flight: re-export shims, feature
  flags, compatibility aliases, deprecated wrappers. Delete each or give it a dated removal target and a
  changelog line.
- **Add mechanical mass-change commits to `.git-blame-ignore-revs`** (formatting sweeps, mass renames,
  docstring rewrites), so `git blame` still points at the commit that made each line mean what it means.
- **Pin real user artefacts** from the previous version (a saved session, a config, a project file) with
  paths scrubbed, and assert that every class or key they name still exists - the actual compatibility
  question, which nothing else asks.
- **Add a version-consistency gate** comparing every file that states the version (package constant,
  citation metadata, tag, release dates) and reporting every disagreement at once. Downstream archives
  often build their record from a metadata file nothing validates.
- **Hand irreversible, interactive, once-per-release commands to a human** (a release-finish command that
  opens editors and merges to the main branch). Prepare everything up to it; let them run it and push.

## X3 · A breaking-change inventory must be derived, and honest in both directions

Parse every public base class at the previous release tag and at HEAD and compare method tables
(`scripts/api_surface_diff.py`). Then correct it both ways:

- **A new abstract method on a class that is itself new breaks nobody.** Listing it makes the release look
  more hostile than it is, and a list padded with non-events is skimmed instead of read.
- **Behavioural breaks are invisible to a signature diff** (a newly required settings key, a changed
  dispatch for `None`). Add them by hand from the decision log.
- **Every genuine break is called out as breaking**, including ones described accurately but filed as
  ordinary changes (a method moved down to a subclass base).

## X4 · Code outlives the plan, so it must not cite the plan

"Extracted in 5c.6" promises an explanation in a document that will be deleted. Write the mechanism and the
reason, which stay true; name the old mechanism where that helps findability; cite dates or permanent records
(decision log, changelog), never the plan. This accumulates invisibly - ~330 citations built up over one
refactor before a reader asked what "4a" meant - so write it right the first time.

## X5 · Deletion residue is found by diffing name sets, not by reading

Diff the set of names defined before the refactor against those defined now, and search the tests for the
difference. Reading 50 test files does not find what a set difference finds in seconds.

## X6 · Retire the tooling that guarded the refactor

A gate whose target list is the plan has nothing to guard once the plan is done, and its CI cost outlives
it. On the source refactor, retiring one coverage audit removed about 90 seconds from every CI run (its only
reason for collecting coverage).

## X7 · Regroup the changelog last, and verify the mapping by script

A flat list of ~200 entries in landing order is no help to someone asking whether anything they rely on
changed. Group by theme, breaking first and unmissable, one line per change. Do it last (burn-in will add
more), and check by script that every entry appears exactly once, every breaking entry sits under Breaking,
and older sections are byte-identical.

