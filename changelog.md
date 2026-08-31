## Poriscope 1.7: In Progress

* **Fixed: every dataset link in the documentation pointed at a retired FRDR record**
    * The tutorial dataset DOI in the docs, `10.20383/103.01599`, is Version 1. It was superseded on 2026-06-01 by `10.20383/103.01695` ("Adding a second dataset and README to extend the testing functionality of the dataset"). 11 occurrences across 6 files now point at the current DOI.
    * Added the DOI to the two pages where a new user first needs data and it was missing: `raw_data_tab.rst`, at the **Select Input File** step and naming `ChimeraReader20240501` for the deposit's `.log` files, and `tutorial.rst`, worded to keep the built-in Help -> Tutorial walkthrough distinct from the YouTube tutorial series that shares the dataset.

* **Breaking: `requires-python` raised to `>=3.12.10`, which is what everything else already assumed**
    * `pyproject.toml` declared `>=3.12`, so pip installed Poriscope happily onto Python 3.12.0. Every other statement of the requirement disagreed: `README.md` said 3.12.10 "to avoid dependencies compatibility issues", the three installation pages said `>=3.12.10`, and all five CI workflows pin exactly 3.12.10. The metadata was the only thing that could actually stop an install, and it was the one place that did not enforce the real floor - so a user on 3.12.3 got a clean install, no warning, and landed in exactly the territory the README warns about.
    * **This blocks installation for anyone on 3.12.0-3.12.9**, which is the intent, but it is a user-visible packaging change rather than a docs fix.
    * The docs are now consistent with it: `user_guide/getting_started.rst` said a bare **Python 3.12.10** / "Required version", which reads as *exactly* that release, and now says `>=3.12.10` / "Minimum required version"; `README.md` says "3.12.10 or newer".
    * Nothing else declares a Python floor - `mypy.ini` sets no `python_version`, and the `pyproject.toml` classifiers only say `Python :: 3`.

* **Pinned the Python level mypy checks against, and declared 3.12 to PyPI**
    * `mypy.ini` now sets `python_version = 3.12`. Nothing pinned the interpreter the pre-commit hook runs under - `mirrors-mypy` sets no `language_version` and `.pre-commit-config.yaml` has no `default_language_version` - so mypy fell back to whatever Python built the hook environment. A contributor on a newer interpreter could get a different verdict from CI on identical code, which is exactly the failure mode `CLAUDE.md` already warns about when it says to always measure with the hook. Hook verdict is unchanged by the pin (passed before, passes after).
    * Only `MAJOR.MINOR` is accepted - mypy rejects `3.12.10` outright ("expected format: 'x.y'"), because the setting selects the language and stdlib surface, which changes at minor versions and never at patch level. So this does **not** duplicate `requires-python`: the two state different kinds of fact and move independently, and a floor bump to 3.12.14 would not touch this.
    * Added the `Programming Language :: Python :: 3.12` classifier, which is what PyPI's version filter reads. Purely informational - `requires-python` is what enforces anything.
    * Left alone deliberately: the `Operating System :: Microsoft :: Windows` classifier is narrower than reality, since all five CI workflows run on Linux under Xvfb and `faq.rst` describes Linux as beta-tested with "functionality in place". Widening it advertises a support commitment, so it is a decision rather than a correction.

* **De-pinned the Python download link in the installation instructions**
    * Three pages linked `python.org/downloads/release/python-31210/`. That page resolves but states it has been superseded by 3.12.14 and was the last *full* maintenance release of the 3.12 line - everything after it is security-fixes only - and it dates from April 2025. Linking a specific patch release was never necessary and is the same failure mode as the retired dataset DOI above. All three now link `python.org/downloads/`, which cannot go stale.

* **View tests build mocked views instead of real Qt widgets**
    * `test_protein_view.py` and `test_event_analysis_view.py` built a full view per test - widget tree, Matplotlib canvases and controls panel - at roughly half a second each, which was fixture cost rather than test work: of protein_view's 123.8s, 103.8s was setup and 10.7s was the test bodies. Both now build the view with `__new__` and supply only what the code under test touches, following the pattern `test_metadata_view.py` and `test_raw_data_view.py` already used.
    * `test_protein_view.py` 123.8s to 26.1s (and that is with 36 more tests than before, mean per test 0.497s to 0.091s); `test_event_analysis_view.py` 32.3s to ~11s. Measured across the view tree, 364.9s to 249.1s.
    * Each file now has two fixtures: **`mock_view`** (378 tests between them) and **`real_view`** (44). A test needs `real_view` when it asserts construction actually produced something (an `is not None` check on a canvas passes vacuously against a mock), emits a real Qt signal to prove a connection exists, reads state back off an Axes or a populated combo box, or drives the real filter combobox. Everything else takes `mock_view`.
    * New `tests/unit/views/_qt_mocks.py` holds the shared pieces, following the existing `tests/e2e/_helpers.py` convention. Three of them exist because the obvious mock was wrong: **`FakeSignal`** keeps a real slot list so `connect()`-then-assert tests still receive their payload, while leaving `emit` a MagicMock so call assertions keep working; **`shadow_signals`** finds Qt signals by introspection rather than by name, because a `__new__` instance has no C++ QObject behind it and emitting a class-level `Signal` raises "Signal source has been deleted"; **`mock_figure`** really tracks the axes `add_subplot` creates and mirrors Matplotlib's link between `set_layout_engine("constrained")` and `get_constrained_layout()`, so tests asserting on either still mean something.
    * The view's `logger` is deliberately **not** mocked - it is a class attribute, so it resolves on its own, and replacing it silently blinds every `caplog` assertion in the module.
    * **Verified by mutation testing rather than by the suite going green.** Six deliberate defects - wrong double-Gaussian sum, `set_query` dropping its emit and dropping its state, `_factors` returning the widest pair, `validate_single_channel` no longer rejecting multi-channel, `_update_event_plot` skipping constrained layout - are all still caught. Two mutations that the mocked suite missed were checked against the original real-widget suite and missed there too, so they were a pre-existing gap rather than something mocking introduced; they are fixed below.

* **Fixed: nothing tested the Individual/Ensemble plot dispatch**
    * `fig_hist`, `ax_hist`, `canvas_hist` and their `_vm` counterparts are properties that read and write the `*_individual` or `*_ensemble` attribute depending on `_analysis_mode`. That dispatch is what makes switching analysis mode show that mode's own last-drawn plot rather than the other one's, and it was uncovered: a getter hard-wired to one side, or a setter that clobbers the other mode's figure, passed the entire suite.
    * 36 parametrized tests in `TestModeScopedProperties` now cover all six properties for getter dispatch in both modes, setter dispatch in both modes, that the two modes do not collapse onto the same object, and that writing one mode leaves the other untouched. All seven corresponding mutations are now caught, each failing only the tests that target it.

* **Fixed: a leaked `patch.object` in the event-analysis tests turned one failure into eighteen**
    * `TestShiftRangeAndUpdatePlot`, `TestHandlePlotEvents` and `TestHandlePlotEventsExtended` started a patcher inside a setup helper and stopped it from an explicit teardown call at the end of each test body. A test that failed before reaching that call left `_handle_plot_events` or `_update_event_plot` patched for the rest of the session, so one genuine failure surfaced as a cascade across unrelated classes.
    * All three are now autouse fixtures that patch around a `yield`, so the patch is undone whether the test passes or fails, and the 20 now-dead teardown calls are gone. Confirmed by injecting a failure: previously 18 failures, now 1.

* **Dropped the speed-based test markers now that durations are flat**
    * **Breaking for anyone with a local script using them:** `fast` and `slow` are gone from `pytest.ini`, along with the three `@pytest.mark.fast` decorators. `-m fast` and `-m slow` now select nothing.
    * The slow tail is now entirely e2e - every test above 2s, 14 of 14 - which is already a directory, and `fast`'s "<5s" definition matches 99.7% of the suite.
    * `e2e` and `integration` are now applied by path in `tests/conftest.py`, since they describe where a test lives rather than a per-test judgement; `-m e2e` selects 20 and `-m "not e2e"` deselects 20. The redundant hand-applied `@pytest.mark.integration` decorators are dropped. `compliance`, `smoke` and `e2e_ux` stay hand-applied - no directory implies them.
    * All four workflows (branches, fork PR, internal PR, release) now run plain `pytest`. The filters they previously carried referred to the unapplied markers, so `ci-branches.yml`'s `-m "not e2e and not slow"` selected everything and `ci-fork-pr.yml`'s `-m "fast"` selected three tests. At ~6 minutes there is no case for a subset, and the e2e tests are the highest-value coverage in the repo.
    * `--strict-markers` added to `addopts`, so a marker name that is not registered is a collection error rather than an expression matching nothing. Verified against a bogus marker.
    * New: **`pytest --marker-stats`** prints per-marker test counts and mean durations from the run's own timings, reading the marker list from `pytest.ini` so it stays correct as markers and tests are added. Current snapshot: `e2e` 20 tests/4.239s mean, `smoke` 4/0.537s, `compliance` 71/0.018s, `integration` 3/0.154s, all 2,616 tests at 0.130s mean.
    * `CLAUDE.md`, the Quality Control docs page and `future_fixes.md` updated to match; the `future_fixes.md` item is pruned as landed.

* **View-test teardown GC is now generation-limited, halving the view suite**
    * The `gc.collect()` in `tests/unit/views/conftest.py` was the single largest cost in the whole test suite: 193.0s across 1,494 tests, 129ms each, 95.9% of all teardown time and 55% of the view tree's wall clock. A full collect walks every generation including the long-lived one holding PySide6, numpy, pandas, sklearn and matplotlib, and that traversal is the entire cost - per-test Qt garbage is not in it.
    * **The sweep is not removed and its cadence is unchanged.** A collection still runs after every single test; only the full-generation sweep is now periodic (`gc.collect(1)` per test, full `gc.collect()` every 50). That call is load-bearing - it is what stopped the repeated Matplotlib/PySide segfaults in CI, which took three commits to settle (`06679373`, `cc2fd863`, `d829d688`) - so it was cost-reduced rather than dropped. Written up in `DECISIONS.md`.
    * Measured on the full view tree, all variants 1,494 passed: full collect per test 340.4s, **chosen option 168.5s**, full-every-50-only 176.9s, `gc.collect(1)` only 178.4s, `gc.collect(0)` 184.9s, no GC 163.7s. The chosen option reaches 97% of the no-GC floor without giving up the per-test cadence; "full every 50 only" is both slower and less safe. All measurements are Windows - CI on Linux/Xvfb is the real gate.

* **Dropped a redundant `show()` and `processEvents()` from two view-test fixtures**
    * `test_protein_view.py` and `test_event_analysis_view.py` built their view, then called `container.show()` and `qt_app.processEvents()` on every test. Neither file contains a single assertion on visibility, geometry, size, focus or window extent, so nothing depended on either call. Removing them cut those two files from 193.91s to 163.84s (-30.1s, -15.5%) with all 429 tests still passing.
    * Profiling first: of the 358ms the `ProteinView` fixture spent per build, `processEvents()` was 115.6ms and `show()` 17.8ms; the remaining ~72% is real widget construction (`_set_custom_display_area` 109.7ms, `ProteinView()` 95.5ms) and is untouched.
    * `test_metadata_view.py` mocks its Qt dependencies instead of building real widgets and costs 0.20s/test against protein_view's 0.66s, which is the template if these files are ever reworked further.

* **Fixed: the view test suite leaked every widget it created, making teardown the dominant cost**
    * `tests/unit/views/conftest.py`'s autouse `_close_leftover_widgets` fixture called `widget.close()` on every top-level widget after each test. `close()` only *hides* a widget - it stays alive and stays in `QApplication.topLevelWidgets()` for the life of the process. Every test therefore leaked its widgets, and since the fixture is autouse over the whole directory, each subsequent teardown walked a longer list and handed `gc.collect()` a larger heap.
    * The cost is positional, which is why it looked like specific files were slow: measured per-test averages rise monotonically with alphabetical collection order, from ~0.2s for `test_clustering_view.py` (first) to 7.5-9.8s for everything in `utils/` and `widgets/` (last). Those directories were carrying roughly 90% of the suite's wall-clock, spent almost entirely in teardown rather than in the tests themselves. The same files run fast in isolation, which is what made this look like slow widget construction - it is not: a bare `ClusteringSettingsDialog()` builds in ~8ms.
    * `deleteLater()` alone does not fix it. It posts a `DeferredDelete` event, and `QApplication.processEvents()` does not dispatch those, so the widgets stay scheduled for a deletion that never happens. Measured directly: 4 widgets leaked per iteration under both `close()` and `close() + deleteLater()`, 480 alive after 120 iterations. Adding `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` holds it at 0.
    * Result on the full `tests/unit/views` tree: **~3,540s to 465s, a 7.6x speedup**, with all 1,494 tests still passing and no segfaults. Teardown no longer appears anywhere in the fifteen slowest durations - the top entries are now actual test bodies (`call`), led by a 2.38s Gaussian-mixture clustering test. On `tests/unit/views/widgets` alone: 106.54s to 31.70s, slowest teardown 1.12s to 0.14s. Teardown cost is now flat across the session instead of climbing with position.
    * No test files were changed - every session-scoped fixture in this tree returns the `QApplication` itself rather than a widget, so nothing depended on a widget outliving its test.

* **Replaced the last `assert` in non-owner runtime code with an explicit check**
    * `ClassicBlockageFinder._filter_events` opened with `assert self.reader is not None`. The assert was doing real type-narrowing work for mypy, but asserts are stripped under `python -O`, which would have turned a missing reader into an opaque `AttributeError` on the following line. It now raises `RuntimeError`, matching how `MetaEventFinder` already guards that same `Optional` attribute (lines 143 and 203) and how the codebase reports missing prerequisites elsewhere. Nothing anywhere in `poriscope/` catches `AssertionError`, so changing the type breaks no handler.
    * The remaining seven `S101` sites are all in `NanoTrees.py`, which is owner-held and a deprecation candidate.

* **Cleared 17 unused loop-control variables (`B007`)**
    * Thirteen were `dict.items()` loops using only one half of the pair; they now iterate `.values()`, or the keys directly, which is exactly equivalent. One was a pointless `enumerate` in `EventAnalysisView._update_event_plot`.
    * Three sites zip two sequences and use only one: `MetaEventFinder`'s rejection tally, and `SingleBinaryDecoder._map_data`, which uses neither zipped value and only wants the index. These kept their `zip` with the unused names underscore-prefixed rather than being restructured, because dropping the pairing would change how many times the loop runs should the two sequences ever disagree in length - a behavioural difference that would be invisible at the call site.
    * Checked and cleared as a non-bug on the way past: `MetaEventFinder` discards the `bad_indices` half of `_filter_events`' return value in its tally loop, which looked like rejected events might never actually be excluded. They are - `bad_indices` is consumed separately at four sites below it via `if idx not in bad_indices`.
    * Three `B007` sites remain, all in `PeakFinder.py`.

* **Exception chaining restored across 23 `raise` sites**
    * Every `raise X(...)` inside an `except` block in non-owner code now carries `from e`, so the exception being replaced is preserved as `__cause__` rather than discarded. Exception type, message and control flow are all unchanged, so nothing that catches by type or matches on message text is affected.
    * **The 12 sites in the data readers were losing real diagnostic information, not merely a traceback.** All six readers share a copy-pasted `_map_data` whose handler raises `FileNotFoundError("File Not Found : At least one of the input raw data files is missing or renamed")`. That message says "at least one of" because at that point it does not know which - but the exception it was replacing names the exact file. A user with a multi-file dataset was told a file was missing and given no way to find out which one. The sibling `OSError` handler, for inaccessible remote or external-media paths, had the same problem.
    * The other 11: two `int()`/`float()` parse failures in `ClusteringView` (where the original names the field that failed to parse), three histogram bin-size calculations in `MetadataView`/`ProteinView` (which already interpolated `str(e)` into their message, so only the traceback was lost), three channel lookups in `MetaReader.load_data`, and one each in `SQLiteDBLoader.add_columns_to_table`, `MetaEventFitter.get_single_event_metadata` and `BaseLineEdit.__init__`.
    * Also fixed a typo in a user-visible message in `MetaReader.load_data`: "channel, start, and length must all a type that can be coerced to int" was missing a word.
    * `B904` is **not** being enabled as a gate. The single remaining site is in `PeakFinder.py`, which is owner-held, so enabling it would require a `per-file-ignores` entry - which hides a real check rather than satisfying it.

* **Silently swallowed exceptions outside the owner-held fitter files reduced to zero**
    * `BaseDataPlugin.unregister_dependent` and `unregister_parent` each wrapped a `set.remove()` in `try/except Exception: pass`. Both containers are sets, so `set.discard()` says "remove if present" - exactly what the docstrings already promised - with no exception handling at all.
    * **`BaseDataPlugin.apply_settings` narrowed its settings-value type test from `except Exception` to `except AttributeError`.** The `try` calls `.get_key()` on each settings value to work out whether it is a plugin instance rather than a plain number or string, and the `else` branch then registers the parent/dependent relationships that `DataPluginController` consults when it refuses to delete or rename a plugin that still has dependents. Catching every exception meant that any unexpected failure of `get_key()` on a genuine plugin silently skipped that registration, leaving the dependency graph incomplete and the plugin deletable out from under a live dependent. Only `AttributeError` actually signals "not a plugin"; everything else now surfaces.
    * Four cosmetic handlers keep their control flow but stop vanishing: three `tight_layout` calls in `ProteinView` and the stale-colorbar removal in `MetadataView` now log at debug level with `exc_info`. A failed layout should not stop a plot from rendering, but it should leave a trace when the plot looks wrong.
    * `S110`/`S112` in non-owner code is now **0**, down from 7. The remaining 14 are all in `PeakFinder.py` and have been written up separately for the developer who owns it.

* **Hardened three `zip` sites whose length invariant was implicit**
    * `SQLiteDBWriter` now transposes its sublevel metadata with `strict=True`. Every list in that dict is already the same length by the time the writer sees it, because `MetaEventFitter.fit_events` rejects any event whose metadata lists disagree with its sublevel count - but that guarantee lives three layers up and does not travel with the dict. `strict=True` asserts it at the point of use, so a hand-built dict from a test or a future fitter fails loudly rather than silently transposing into fewer rows than the event has. It cannot fire on the validated path.
    * **`ClusteringView._load_metadata_and_cluster` no longer mutates `columns`.** Appending `"id"` to it was what desynchronized it from the parallel `logs`/`norm`/`plot` flag lists and made the zips below truncate silently. The dataframe selection now uses a separate `frame_columns = columns + ["id"]`, which leaves `columns` index-aligned with its flag lists and in turn lets both zips assert that alignment with `strict=True`.
    * **`ClusteringView.update_plot` derives `plot_cols` from the filtered user-column list** rather than from `data.columns`, which carries trailing `"id"`, `"cluster_label"` and `"cluster_confidence"` entries. The previous form was correct only because the user-selected columns happened to come first; since `plot_cols` indexes the plot axes, any reordering would have silently rendered the wrong data against the wrong labels.

* **Fixed: `MetadataView` silently dropped plot features that had no label**
    * `_update_event_plot` zipped each per-subplot feature list against its label list (`zip(hlines, hlabels)` and the vertical and point equivalents). Both arrive from another plugin - `MetaDatabaseLoader.get_plot_features`, relayed over the signal bus - so their lengths are a cross-plugin contract rather than a local invariant, and `zip` stopping at the shorter of the two meant a short or absent label list silently removed lines and markers from the plot, with no error raised anywhere.
    * `EventAnalysisView._update_event_plot` already guarded exactly this case, standing in `[None] * len(...)` when the label list was absent. `MetadataView` never received that fix. It now has it, extended to also cover a label list that is present but *shorter* than its feature list rather than only one that is `None`.
    * The three label parameters are now `Sequence[Optional[Sequence[Optional[str]]]]`, matching `EventAnalysisView`. The previous `Sequence[Optional[List[str]]]` claimed the inner lists held `str`, while the loop body has always tested each individual label for `None`.
    * Found during a full audit of all 50 in-scope `B905` (`zip` without `strict=`) sites. `B905` is **not** being enabled as a gate: 43 of those zip sequences that are constructed together and need nothing, and three in `ClusteringView` depend on the truncation deliberately, so making them `strict=True` would raise on every clustering run. The `SQLiteDBWriter` sublevel transpose was verified safe - `MetaEventFitter.fit_events` rejects any event whose sublevel metadata lists disagree in length before the writer ever sees them.

* **Enabled the ruff `B006`/`B020` checks and cleared their three sites**
    * `pyproject.toml` now selects `B006` and `B020` alongside `I`, so both are enforced on every commit instead of sitting in a backlog. The rest of `flake8-bugbear` is still not adopted; its measured backlog stays in `future_fixes.md`. The contributor-facing gate description in `quality_control.rst` was updated to match.
    * `ClusteringView._normalize_column_data` and `DataPluginView.get_user_settings` each took a mutable `[]` as an argument default. Neither ever mutated it, so neither was an active bug, but both are now `Optional[List[str]] = None`. `get_user_settings` needed no body change at all - `DictDialog` already normalises `None` to `[]`, and was in fact already using the correct idiom itself.
    * `MetadataView._update_event_plot` unpacked a loop variable named `points` while zipping the parameter of the same name. Iteration was never affected, because `zip()` creates its iterators before the first loop assignment, but the shadowing was the reason the parameter had to be annotated `Any`. The loop variable is now `pts`, and the parameter is properly `Sequence[Optional[List[Tuple[float, float]]]]` - one fewer `Any` in the codebase.
    * **Fixed: `"id"` was never excluded from clustering normalization.** `_load_metadata_and_cluster` appends `"id"` to `columns` but not to the parallel `norm` list, so the `zip(columns, norm)` that builds the exclude list truncates before reaching it and can never place `"id"` there. Two lines that built an `exclude_cols` *including* `"id"` were dead: their result was discarded by a call that re-inlined the same comprehension without them, which is why no unused-variable check caught it (`.append()` counts as a use). Harmless in practice - `id` is always an integer serial number and `_normalize_column_data` only touches float columns - and evidently a leftover from the earlier fix that stopped `id` being fed to the Gaussian-mixture clustering. The dead lines are gone and `"id"` is now excluded explicitly rather than by dtype accident.

* **Integration: the PeakFinder classifier work merged against the docstring/type pass**
    * `feature_Peakfinder_classifier` (32 commits, ~2,840 new lines in `PeakFinder.py` plus changes to `SQLitePeakDBLoader`) was reconciled with the completed type-annotation pass on an integration branch rather than by merging each into `develop` in turn, so `develop` is never left in a gate-red state between the two merges. Both branches shared a merge base, and `develop` was merged in first and verified (1,575 passed, 2 skipped) before the classifier work was layered on.
    * Only one file conflicted: `PeakFinder.py`, in 11 hunks. Resolution rule was that **her logic wins unconditionally**, with the annotations and docstrings re-applied on top - the two import hunks were unioned, and three hunks that were annotation-style only (`Mapping` vs `Dict`, `list[dict]` vs `List[Dict[str, Any]]`) kept the typing-style spellings, which is required rather than preferred: `test_plugin_compliance.py` compares base and override annotations by equality, so `get_plot_features` and `_define_*_metadata_types` have to match `MetaEventFitter` verbatim.
    * The new classifier code was brought up to the current gates: nine functions annotated (including the three nested helpers `Gauss`, `Gauss_2` and `dgfit`), 46 pydoclint violations cleared, and her PEP 604 annotations aligned with the docstrings they contradicted. All four pre-commit gates pass.
    * **`filter_peaks` and `redefine_padding` had no docstring at all** - in `filter_peaks` the text existed but sat *below* four statements, making it a no-op string expression rather than a docstring. That was what `test_plugin_compliance.py` was reporting; both are fixed and compliance passes.

* **Fixed: three regressions in `SQLitePeakDBLoader.get_plot_features`**
    * The `except` handler around query construction had lost its `return`, so a failure there fell through to `validate_filter_query(query)` with `query` unbound - a `NameError` rather than the clean "no features to plot" result callers expect.
    * The `result is None` half of the empty-result guard had been dropped. `query_database_directly` returns `None` when a query yields nothing, and `len(None)` raises `TypeError`.
    * The `if unfolded is not None:` guard was removed while the line above still assigns `None` whenever the `unfolded_level` column is absent, so `baseline - sign * unfolded` raised `TypeError` in exactly that case.
    * Each fix carries a `NOTE (integration):` comment at the site explaining what changed and why.

* **Removed: `PeakFinder.fit_2_gauss`, which had never been able to run**
    * The method had no call sites anywhere in the codebase. It also could not have worked if called: its nested `Gauss` was defined with four parameters but invoked with five (repaired earlier in this branch), and separately it passed `np.linspace(min, max, 1000)` as `xdata` against the raw `(N, 1)` sample array as `ydata`, which `curve_fit` rejects unless an event happens to be exactly 1000 samples long - and which is not a distribution fit in any case, since both axes are current values rather than bin centres and counts.
    * Repairing it would have meant deciding what it should fit, which is the work already scoped for consolidating the three separate double-Gaussian implementations in this codebase (`bitthresh`'s `dgfit`, `ProteinView._fit_double_gaussian`, and this one) onto the sanity-checked ProteinView implementation. Deleting the dead one is the correct first step of that consolidation rather than a competing change. `bitthresh` and its `dgfit` are untouched and remain the live path.

* **Fixed: the `post-merge` git hook failed silently on Windows**
    * `scripts/setup_hooks.py` copied `scripts/hooks/post-merge.py` verbatim into `.git/hooks/post-merge`. Git runs hooks through its bundled POSIX shell on every platform and honours their shebang, and that file's `#!/usr/bin/env python3` does not resolve on Windows: `python3` there is the Microsoft Store stub, which is a real file on `PATH` (so a `command -v` check passes) but prints "Python was not found" and exits non-zero when run. Every merge on Windows therefore skipped the autodoc regeneration, the requirements refresh and the wavelet DLL build, printing one easily-missed line and continuing.
    * A POSIX-shell shim, `scripts/hooks/post-merge`, is now installed as the hook instead. It selects an interpreter by **executing** each candidate (`python3`, `python`, then `py -3`) rather than by looking it up on `PATH`, which is the only check that tells a working Python from the stub, and then launches `post-merge.py` with it. `post-merge.py` keeps all the logic and is unchanged.
    * If no interpreter is found the shim prints what it tried and what was skipped, and exits 0 - a post-merge hook cannot undo the merge, so failing loudly but harmlessly is the useful behaviour. Being quiet is what let the original breakage go unnoticed.
    * A `.gitattributes` was added at the same time pinning the shim (and any `*.sh`) to LF. Git for Windows defaults to `core.autocrlf=true`, which would have handed the next checkout a CRLF shim - and a shell script with CRLF endings fails to parse its own shebang, dying with `bad interpreter: /bin/sh^M`. Without this the fix would have broken again on a fresh clone, in the same silent way.

* **Fixed: event fitting progress never reached 100% when any event was rejected**
    * `MetaEventFitter.fit_events` yields `fitted / total_events` as its progress fraction, where `fitted` counts only events that complete. Every rejection path popped the event's metadata and `continue`d without adjusting the denominator, so a channel with any rejected event left the progress bar permanently short of complete. The `IndexError` path already decremented `total_events`; the remaining eight rejection paths now do the same, so the fraction closes on exactly 1.0 (with N events, R rejected and F fitted, the denominator ends at `N - R = F = fitted`).

* **Fixed: four e2e tests waited on file existence before asserting on file contents**
    * `tests/e2e/raw_data/test_events_flow_clicks.py::test_commit_events_writes_exact_schema` failed once in a full-suite run with `Missing expected tables: {'columns', 'channels', 'events'}` and an empty table set, while passing in isolation, in its own file, and across all of `tests/e2e`. The cause was the wait condition, not the writer: it waited on `out_db.exists()` and then asserted on the schema. **SQLite creates the database file the moment a connection opens, before any `CREATE TABLE` runs**, so the wait could be satisfied by a zero-table file; under a long run the gap widens and the assertion loses the race.
    * Three sibling sites had the same shape - waiting for a JSON file to appear and then `json.load`-ing it, where a partially written file raises `JSONDecodeError`: two in `test_metadata_events_nav_persistence.py` and one in `test_protein_events_nav_persistence.py`.
    * Added `sqlite_has_tables()` and `json_file_ready()` to `tests/e2e/_helpers.py`, both safe to use as `qtbot.waitUntil` predicates (they return `False` rather than raising while a file is absent, empty, locked or half-written), and pointed all four waits at the real postcondition. The helper module carries a comment explaining why waiting on `.exists()` before asserting on contents is always a race.

* **Fixed: seven latent defects in the PeakFinder classifier code**
    * **`fit_2_gauss` could never succeed.** Its nested `Gauss` declared four parameters but was called with five, so every call raised `TypeError` - swallowed by a bare `except Exception` around `curve_fit`, which then took the "fit failed" path unconditionally. The return statement unpacks `popt` in two groups of four, so four parameters per Gaussian is the intended shape; `Gauss` gained an `offset` term and `Gauss_2`'s parameters were renamed from `A/x/m/s` to `A/u/s/c`.
    * **Four `Optional` values were used in arithmetic without a guard**: `baseline_mean` in `find_mode_blockage_level`, `baseline_std` in `redefine_padding` and at seven threshold sites in `filter_peaks`, and the metadata-dict reads feeding `find_mode_blockage_level`. All now check and raise `RuntimeError` with a message naming what was missing, rather than surfacing a `TypeError` from inside numpy.
    * **A `None` test that could never fire.** `_save_classification_report` called `float(prominence_stats.get("threshold"))` and only then tested `threshold is not None`, so a missing key raised `TypeError` instead of skipping the line. The check now guards the conversion, and the `cast()` it existed to satisfy is gone.
    * **Two `float(bt.get("midpoint"))` calls** on an `Optional` lookup now raise explicitly.
    * `find_mode_blockage_level`'s `baseline_std` handling was a `float()` inside a bare `except Exception`, which made a legitimately-`None` value indistinguishable from a conversion failure; the `None` case now selects the `'auto'` binning path explicitly.
    * Every one of these carries a `NOTE (integration):` comment at the site, so the owning developer can see what changed and why when she re-branches.

* **Fixed: stale fixtures in `test_peak_finder.py`**
    * The event-metadata key `baseline_std` was renamed `baseline_stdev` and `longest_blockage_level` was replaced by `primary_level`, but the fixtures were never updated. Eight of the failures presented as `TypeError: object of type 'NoneType' has no len()` rather than a missing key, because `get_plot_features` catches the `KeyError` and converts it into an all-`None` return. Fixtures also gained the `sequence` and `translocation_direction` keys the method now reads, and the "Some" gauge-count expectation was corrected from 2 to 4.

* **New Dev Tooling: `pydoclint`**
    * Added as a blocking pre-commit/CI check that a docstring's documented parameters, return type, and raised exceptions match the real function signature/body. See `[tool.pydoclint]` in `pyproject.toml` for the config. This was originally adopted with `arg-type-hints-in-signature = false`; that setting has since been corrected to `true` (see "Corrected: pydoclint now treats signature type hints as the source of truth" below).
    * Run it yourself with `pydoclint --baseline=.pydoclint-baseline.txt poriscope` (pre-commit already runs it on staged files).
    * Pre-existing violations at adoption were grandfathered into `.pydoclint-baseline.txt` so existing code didn't need a mass cleanup up front; only *new* mismatches you introduce will fail the hook. If you fix a baselined violation, regenerate the baseline so it can't silently keep passing for a docstring that no longer matches: `pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope`.
    * A follow-up sweep cleared the great majority of the ~1,090-violation baseline this tool inherited across 58 files (down to ~430 lines, almost entirely `DOC108` plus `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py`, excluded per standing project policy), fixing real docstring bugs along the way: stale/copy-pasted parameters, wrong return types, and missing `Raises` sections, across nearly every plugin family in the codebase.
    * Along the way, adding the return-type annotations pydoclint asked for occasionally exposed pre-existing problems that had been invisible for lack of anything to check against: a few `Meta*` abstract methods' declared return types didn't actually match what their real subclasses return (caught by `test_plugin_compliance.py`'s covariance check once both sides had annotations to compare, fixed by correcting the abstract declaration), one genuine `mypy` false positive in `MetaReader.load_data` needing a `cast()` rather than a type change, and a few bare `except:` clauses narrowed to `except Exception:` so their `Raises` sections could be written down at all.
    * Documented the full set of automated QA checks (pydoclint, plugin interface compliance testing, and a step-by-step pre-PR checklist) in the Sphinx docs' Quality Control page, cross-linked from the plugin development manual so contributors know what to run before opening a PR.

* **New Dev Tooling: Type annotations for data plugins**
    * First installment of the full-codebase type-annotation pass tracked in `future_fixes.md`: added parameter/return type hints to every method across the `datareaders`, `eventfinders`, `filters`, `eventloaders`, `datawriters`, `db_loaders`, and `dbwriters` plugin families, plus the CUSUM-family fitters (`ClassicCUSUM`, `CUSUM`, `IntraCUSUM`, `NoFitter`), copied from each family's `Meta*` base contract. `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py` excluded per standing project policy. Docstring/signature only - no behavior changes.
    * Fixed a genuine pre-existing type-hint bug in `MetaReader.py` that this surfaced: `_get_configs`/`_map_data`/`_get_file_time_stamps`/`_get_file_channel_stamps` declared their file-list parameter `List[os.PathLike]`, but `_get_file_names` (the only producer of that list) has always returned `List[str]`, and every reader subclass's handling of it (regex matching, string `.replace()`) already assumed `str`. Narrowed to `List[str]` across the base class and all 7 reader subclasses to match actual behavior.
    * `.pydoclint-baseline.txt` regenerated to absorb the new (expected) `DOC108` entries these signature hints introduce under the then-current `arg-type-hints-in-signature = false` policy.
    * Follow-up fixes for the discrepancies this surfaced: `SQLiteEventWriter._write_data` now raises a clear `ValueError` if `start_sample`/`padding_before`/`padding_after` is ever `None`, instead of letting a bare `int(None)` crash; `SQLiteEventWriter._rescale_data_to_adc`'s `dtype` default changed from the string `"u2"` to `np.uint16` to actually match the base contract's declared `type` (still unused by this writer, per its own docstring); `CUSUM`/`NoFitter._populate_sublevel_metadata` now raise a clear `ValueError` if `baseline_std` is `None` (see the `CUSUM`/`IntraCUSUM`/`NoFitter` entry above); the `sublevel_starts`-typed-`List[int]`-but-actually-`ndarray` mismatch in the same two methods was resolved by wrapping the arithmetic in `np.asarray(...)` rather than widening `MetaEventFitter`'s declared type, which turns out to be intentionally generic (`_locate_sublevel_transitions`'s docstring explicitly allows non-int per-sublevel data).
    * Extended the pass to `poriscope/utils/MetaReader.py` and `poriscope/utils/MetaWriter.py`, exhaustively re-verifying every method (not just the subset touched incidentally by earlier mypy runs). Fixed two genuine pre-existing annotation bugs this surfaced: `MetaReader.get_raw_dtype` was declared `-> None` while actually returning `self.dtype` (now `-> np.dtype`, matching what every reader's `_set_raw_dtype` override actually produces); `MetaReader._get_file_names`'s `folder`/`pattern` params were unannotated (now `os.PathLike`/`str`, matching `SingleBinaryDecoder`'s already-typed override). Docstring/signature only - no behavior changes.
    * Completed exhaustive parameter/return type hints on `poriscope/utils/MetaEventFinder.py` and `poriscope/utils/MetaEventFitter.py` themselves (previously only partially annotated), deriving each signature from the already-typed `eventfinders`/CUSUM-family `eventfitters` subclasses per the same contract-matching rule. `tests/unit/plugins/test_plugin_compliance.py` (71 cases) and `pre-commit run mypy --files` both pass clean on these two files. One genuine pre-existing logic gap this surfaced was flagged rather than fixed: `MetaEventFitter.reset_channel`'s docstring promises resetting every channel when `channel=None`, but the implementation never branches on that case (unlike `MetaEventFinder.reset_channel`'s explicit loop) - narrow `# type: ignore[arg-type]`/`[index]` comments mark the resulting mypy findings without changing behavior.
    * Exhaustively re-verified `poriscope/utils/MetaDatabaseLoader.py` against its already-typed `SQLiteDBLoader`/`SQLitePeakDBLoader` subclasses: added the handful of hints those subclasses already had but the base was still missing - `__init__`/`_finalize_initialization`'s `-> None`, `get_empty_settings`'s `standalone: bool` param, and the three per-method-scoped `tuple_builder(id_list: List[int]) -> str` helpers in `export_subset_to_csv`/`construct_metadata_query`/`construct_event_data_query`. Docstring/signature only - no behavior changes.
    * Completed exhaustive parameter/return type hints on `poriscope/utils/MetaController.py` and `poriscope/utils/MetaView.py` (the shared GUI base classes inherited by every analysis-tab Controller/View pair). `tests/unit/plugins/test_plugin_compliance.py` (71 cases) and `pre-commit run mypy --files` both pass clean on these two files; no `analysistabs/` subclass signatures needed changes since their overrides of the handful of abstract methods checked by that test (`_init`/`_setup_connections`/`_set_control_area`/`_reset_actions`/`update_available_plugins`/`notify_plugin_state_changed`) are either already annotated compatibly or left unannotated (which always passes). A small, purely cosmetic local-variable rename in `MetaController.handle_kill_worker` (`channel_str` for the pre-split string, `channel` for the parsed `int`) resolved a type-narrowing artifact with no behavior change. Two genuine pre-existing gaps this surfaced were flagged rather than fixed, per narrow commented `# type: ignore` suppressions: `MetaView.update_actions_from_json` calls `getattr(self, function, None)` where `function` can be `None` if a stored action dict is missing its `"function"` key; `MetaView.handle_add_triggered` calls `self.available_subclasses.get(...)` where `available_subclasses` is `Optional` (via `set_available_subclasses`, which accepts `None`) but is used without a `None`-guard.
    * Completed the remaining `poriscope/utils/` files in this batch: `BaseDataPlugin.py` (the ultimate base for every data plugin - added the missing `__enter__`/`__exit__`/`update_raw_settings`/`_finalize_initialization` hints), `MetaDatabaseWriter.py`, `MetaFilter.py`, `MetaEventLoader.py`, `MetaModel.py` (its worker/generator/lock bookkeeping - `set_generator`/`run_generators`/`reset_lock`/`stop_workers` - annotated without touching any of that logic), and `LogDecorator.py` (formatting only). `tests/unit/plugins/test_plugin_compliance.py` (71 cases) and `pre-commit run mypy --all-files` both pass clean with all thirteen `poriscope/utils/` files from this batch applied together. Docstring/signature only - no behavior changes; `MetaModel.format_cache_data` gained an explicit `return None` on its no-op fallthrough path to match its new `Optional[pd.DataFrame]` return type, behaviorally identical to the implicit `None` it already returned.

* **New Dev Tooling: Type annotations for analysis-tab GUI plugins**
    * Continuation of the `future_fixes.md` type-annotation pass into `poriscope/plugins/analysistabs/`, done one tab family at a time. Shared infrastructure first (`utils/walkthrough.py`, `utils/walkthrough_mixin.py`, `utils/PluginManagerPopup.py`), then the Clustering triad and `utils/clusteringcontrols.py`. A new `WalkthroughStep` type alias in `walkthrough_mixin.py` pins down the `(title, description, view name, widget getter)` shape every tab's `get_walkthrough_steps` returns. Docstring/signature only - no behavior changes.
    * Fixed a genuine pre-existing annotation bug this surfaced: `ClusteringController.update_column_units` declared `column_units: Dict[str, str]`, but it is a `get_column_units` callback and actually receives the single unit string for one column (`Optional[str]`) followed by that column's name. Corrected the hints and documented the mismatch between the parameter names (`column_units`/`axis`) and what they really carry; renaming them is an API change left for review.
    * Two discrepancies were flagged rather than fixed, per narrow commented `# type: ignore` suppressions: `start_walkthrough` passes a possibly-`None` overlay into `StepDialog`, which declares it non-optional and relies on the resulting `AttributeError` being caught to produce its fallback dialog; and `ClusteringView.units` holds a `Dict[str, str]` when populated column-by-column but is overwritten with a positional sequence of unit strings by `update_plot`.
    * `.pydoclint-baseline.txt` regenerated to absorb the new (expected) `DOC108` entries these signature hints introduce under the then-current `arg-type-hints-in-signature = false` policy.
    * EventAnalysis triad and `utils/eventAnalysisControls.py` annotated next. Google-style `Args:`/`Returns:` docstrings in `EventAnalysisView` converted to the Sphinx style pydoclint checks against, so their parameter types are actually verified rather than silently baselined.
    * Fixed a genuine pre-existing annotation bug this surfaced: `EventAnalysisController.update_features` was annotated one nesting level too deep (`Optional[List[List[float]]]` etc.), but `MetaEventFitter.get_plot_features` returns one flat list of features per event, not one per subplot. Corrected the hints and the docstring wording that described the wrong level.
    * Corrected four `MetaView` range-helper signatures that were wrong against their only call sites: `_parse_event_indices` declared `allow_floats: Literal[True]` while both `EventAnalysisView` and `RawDataView` pass `False`, and `_shift_ranges`/`_merge_ranges`/`_format_ranges` were typed int-only while `RawDataView._shift_range_and_update_trace` feeds them floats. Also cleared seven stale `:type:` lines in the same file left over from the earlier `poriscope/utils/` installment.
    * One further discrepancy flagged rather than fixed: `EventAnalysisView._update_event_plot` zips each feature list against its label list while guarding only on the feature list being non-`None`, so a fitter returning features but no labels would raise `TypeError` (three sites, marked with commented `# type: ignore[arg-type]`).
    * RawData triad and `utils/rawdatacontrols.py` annotated next, with the same Google-to-Sphinx docstring conversion applied to `RawDataView`'s roughly twenty `Args:`/`Returns:` blocks. Two return/parameter types corrected to match reality: `_get_baseline_stats` was declared `tuple[float, float, float]` but returns the `np.array(...)` built from `_gaussian_fit`, and `_gaussian_fit`'s `histogram` parameter was documented `npt.NDArray[np.int64]` while its only caller passes `histogram1d` output (float).
    * One discrepancy flagged rather than fixed: `rawdatacontrols.on_button_clicked` (and the identical line in `eventAnalysisControls.on_button_clicked`) ends with `button_mapping.get(button_type, lambda: None).setChecked(False)`, so an unmapped `button_type` would raise `AttributeError` on the fallback lambda. Every current caller passes a mapped value.
    * Metadata triad and `utils/metadatacontrols.py` annotated next. Four more callback-shape annotations from the interrupted first attempt corrected in `MetadataController`: `relay_table_by_column` and `relay_units` were typed `dict` but are `get_table_by_column`/`get_column_units` callbacks receiving `Optional[str]`, `relay_column_type` was `str` against a `Optional[str]` source, and `update_features` had the same one-level-too-deep nesting as its EventAnalysis counterpart.
    * Two `MetadataView` attribute declarations corrected against what the code stores: `current_channel` was `Optional[int]` but holds the display string from the experiment/channel selection tree, and `hist_data` was `List[npt.NDArray[float]]` but is genuinely heterogeneous (1-D arrays from the histogram path, DataFrames from the density path, `(x, y)` tuples from the all-points path) - widened to `List[Any]` and flagged, since unifying it is a real refactor. `_handle_plot_events`'s six feature lists had the same shallow-nesting defect as EventAnalysis and were corrected the same way.
    * One discrepancy flagged rather than fixed: `MetadataView.on_raw_filter_validated` uses `_pending_filter_name`/`_pending_filter_text` as a dict key and value with no `None` guard, marked with a commented `# type: ignore`.
    * Worth knowing for the rest of this pass: pydoclint folds any prose that *follows* a sphinx field list into the last field's type, so a docstring written "params first, description last" reports a spurious `DOC105` on whichever parameter happens to be documented last. Seven `MetadataView` docstrings hit this and were reordered to put the description first.
    * Protein triad and `utils/proteincontrols.py` complete the family. Six `ProteinView` attributes first assigned `None` in `_init` (`fit_data`, `operation_success`, `plot_events_generator`, `allowed_bins`/`allowed_sizes`, and the four `ensemble_fit_*`) gained explicit `Optional[...]` declarations, without which mypy infers a `None`-only attribute and rejects every later assignment. `current_channel` had the same declared-`int`-but-holds-the-display-string mismatch as `MetadataView`.
    * A cross-tab inconsistency surfaced and left as-is for review: the channel slot of `plotted_datasets` is an `int` in `MetadataView`, which converts with `int(channel)`, but the raw selection-tree string in `ProteinView`, which does not. Each tab is internally consistent and is now annotated to match its own behaviour, but the same conceptual tuple meaning two different things across tabs looks unintended.
    * With this the whole `analysistabs/` family (22 files) is annotation-complete: no parameter or return left unannotated, and `pydoclint --arg-type-hints-in-signature=True` reports zero `DOC104`-`DOC107` anywhere under it. See `future_fixes.md` for the recurring defect classes this pass surfaced, the items flagged for follow-up, and the measured remaining scope (369 functions across 39 files, concentrated in `views/`).

* **Docstring correctness pass (`DOC105`) and the fixes it surfaced**
    * Cleared every in-scope `DOC105` in the codebase - 80 of them, across `poriscope/utils/`, all seven `datareaders`, the writers, loaders and CUSUM-family fitters. `.pydoclint-baseline.txt` went from 184 entries to 104. Docstring text only.
    * Half of those were not real disagreements. pydoclint folds any prose *following* a sphinx field list into the last `:type:` it saw, so a docstring written "params first, description last" reports a spurious `DOC105` against whichever parameter happens to be documented last. Twenty-four docstrings were rewritten description-first, with both parts preserved verbatim.
    * **Corrected units in `MetaReader.load_data` and `continuous_read`.** Both documented `start`/`length`/`total_length`/`chunk_length` as sample indices typed `int`, but every body multiplies them by `self.samplerate` and `continuous_read` calls `load_data` with `float(i / self.samplerate)` - they are times in **seconds**. The prose was as wrong as the type, and both were fixed.
    * **Those two methods no longer reassign their own parameters.** Each overwrote its seconds-valued parameters with sample counts (`start = int(start * self.samplerate)`), so the parameter's meaning changed silently mid-body - which is how the docstrings came to be wrong in the first place. The sample-domain values now have their own names (`start_sample`, `length_samples`, `total_length_samples`, `chunk_length_samples`). Behaviour is unchanged with one exception, which is a fix: `load_data`'s out-of-bounds `ValueError` formats its range as `"{0}s-{1}s ... with total duration {3}"` against a seconds-valued duration, but was being handed sample counts for the first two; it now reports genuine seconds.
    * `MetaReader._sort_objects_by_channel_and_time`'s `channel_numbers` narrowed from `List[Any]` to `List[int]`: its only caller passes `_get_file_channel_stamps(...)`, which is declared `-> List[int]` and whose own contract says the list "must be a list of integers".
    * Mechanical corrections elsewhere: `os.Pathlike` -> `os.PathLike`, `numpy.ndarray` -> the declared `npt.NDArray` forms, numpy-style `", optional"` suffixes replaced by `Optional[...]`, and `get_empty_settings`' `globally_available_plugins` realigned across ten files to the `Optional[Dict[str, List[str]]]` that `BaseDataPlugin` declares. `MetaReader._scale_data`'s docstring, indented sixteen spaces from its second line on and so rendering as a blockquote, was re-indented.
    * Three in-scope violations were deliberately left baselined, with the evidence in `DECISIONS.md`: both `_load_filter` `DOC501`/`DOC503` pairs document a `ValueError` that an `except Exception` in the same function catches, and `IntroDialog`'s `DOC605` cannot be resolved without keeping malformed reStructuredText - every well-formed alternative measured *worse*.

* **Type annotations and docstring compliance for the previously excluded fitters**
    * `PeakFinder.py` and `Basic_PeakFinder.py`, long held out of the type-annotation pass, are now fully annotated and report **zero** pydoclint violations, down from 35 and 36 respectively. Every parameter and return is typed; `.pydoclint-baseline.txt` drops from 104 entries to 33.
    * The ten `MetaEventFitter` overrides in each take the base class's contract verbatim rather than types inferred from their bodies. This is required, not just tidy: `test_plugin_compliance.py` compares generic annotations such as `Dict[str, npt.NDArray[Numeric]]` by *equality*, falling back to `issubclass` only for plain classes, so anything but an exact match fails it. All 71 compliance cases pass.
    * Docstring corrections that fell out: `Mapping[...]` return types realigned to the `Dict[...]` the base declares; `list[dict]`/`list[Optional[int]]` spelled as the `typing` forms used elsewhere in the family; `get_empty_settings`' bespoke nested return type replaced by `Dict[str, Dict[str, Any]]`; and both files' `get_empty_settings` docstrings reordered description-first, since their trailing prose was being folded into the return type.
    * Three `Raises` sections removed per file because those methods do not raise: `get_plot_features` logs and returns a tuple of `None`s when fitting is incomplete rather than raising `RuntimeError`, `_validate_settings` is a bare `pass`, and `_locate_sublevel_transitions` documents an `AttributeError` its body never raises. The base classes still document all three for implementations that do.
    * `Basic_PeakFinder.find_mode_blockage_level` documented an `is_carrier` parameter its three-argument signature has never had; PeakFinder's five-argument version is the one that takes it.
    * **`MetaEventFitter._populate_sublevel_metadata`'s `sublevel_starts` widened from `List[int]` to `List[Any]`**, along with the four subclasses that declare it (`CUSUM`, `NoFitter`, and both PeakFinders). The base was inconsistent with itself: `fit_events` feeds this parameter directly from `_locate_sublevel_transitions`, which is declared `Optional[List[Any]]` and whose docstring explicitly allows non-int per-sublevel data. Both PeakFinders genuinely pass a list of dicts. `List[Any]` is what the producer has always returned; the old `List[int]` accounted for 55 of the 130 mypy errors that annotating these bodies exposed.
    * Local dict accumulators in both files gained explicit annotations - `sublevel_metadata`, `event_metadata`, `metadata_types`, `metadata_units` - without which mypy infers their value type from whichever key happens to be assigned first and then rejects every later assignment of a different type.
    * Behaviour is untouched: signatures, hints and docstrings only. Four genuine defects surfaced while annotating and were marked with narrow `# type: ignore` comments and an explanatory note rather than fixed, since the logic in these plugins belongs to their owner - see `future_fixes.md`.
    * `NanoTrees.py` followed, completing the set: its 45 unannotated functions - two helper classes, seven module-level functions and the plugin's own seven-stage pass pipeline - are now fully typed, and it too reports zero pydoclint violations, down from 28. `settings` throughout the pass pipeline is the `dict` returned by `_set_automation_hyperparameters`, and the arrays threaded between passes are the `NDArray` produced by `_ml_automation`.
    * `NanoTrees.construct_fitted_event` had no return section in its docstring at all and documented a `RuntimeError` where the body raises `AttributeError`; both corrected against the wording `CUSUM` already uses for the same method. Its `_locate_sublevel_transitions` documented `ValueError` and `AttributeError` for a body containing no `raise` at all.
    * The seven reads of `HackyList`'s `.self` attribute in `NanoTrees._populate_sublevel_metadata` are marked `# type: ignore[attr-defined]` with a note: `_locate_sublevel_transitions` returns that list subclass specifically to smuggle the `Sublevels` object alongside the edges, and the base contract types the parameter as a plain list, so the attribute is invisible to a type checker by construction.
    * **With this, every function under `poriscope/` is annotated** - no exclusions left - and `.pydoclint-baseline.txt` is down to **5 entries**, all of them the deliberate ones recorded in `DECISIONS.md`.

* **The pydoclint baseline is now empty**
    * `.. pydoclint-baseline.txt` is a zero-byte file. The grandfathered backlog this tool was adopted with - roughly 1,090 violations across 58 files - is fully cleared, and every violation from here on is a real one that fails the hook.
    * **`_load_filter` no longer raises into its own `except` handler.** Both `MetadataView` and `ProteinView` wrapped the whole method in `try: ... except Exception` and used `raise ValueError(...)` inside it purely to reach that handler. The read and parse step now keeps a narrow `except (OSError, json.JSONDecodeError)`, the shape check is a plain log-and-return, and the forty lines of combo-box and signal work below are no longer wrapped - so a genuine Qt failure there surfaces instead of being silently swallowed and logged. The two `DOC501`/`DOC503` pairs went with the `raise`.
    * The same two methods disagreed on severity for the identical duplicate-name condition (`warning` in `MetadataView`, `error` in `ProteinView`); both are `warning` now. All three user-facing failure paths also emit to the message panel via `add_text_to_display`, since a user whose log level is above INFO previously got no indication that loading had done nothing.
    * **`IntroDialog`'s attribute directive was invalid reStructuredText** - `.. attribute :: start_walkthrough`, with a space before the `::`, which docutils reads as a comment, so Sphinx rendered nothing for it. Corrected to `.. attribute::`.
    * That change required disabling `check-class-attributes`, and the reason is an upstream bug worth recording: `docstring_parser_fork/rest_attr_parser.py` hardcodes the spaced literal, so pydoclint recognises **only** the form Sphinx ignores and ignores the form Sphinx renders. The correct directive and every canonical field form (`:ivar:`, `:cvar:`, `:var:`) all parse to an empty attribute list, meaning that under sphinx style the check could only ever fire against docstrings that were wrong. pydoclint's own documentation prescribes the invalid spelling, and both packages are already at their latest release. Rationale is recorded inline in `pyproject.toml` and in `DECISIONS.md`; the bug has since been filed upstream as https://github.com/jsh9/pydoclint/issues/304.
    * **`_rescale_data_to_adc`'s array and dtype hints made precise.** `data` moved from a bare `np.ndarray` - which is generic in numpy's stubs, so writing it bare leaves the element dtype implicitly `Any` - to `npt.NDArray[np.number]`, matching the declared return. This is the ADC-rescaling path, where dtype correctness decides whether written data is right, and it was the one place still using the form that checks nothing. `dtype` moved from `type` to `npt.DTypeLike`, which is what `astype` actually accepts and no longer rejects `np.dtype` instances or the `"u2"`-style strings this code originally used. Changed in `MetaWriter` and `SQLiteEventWriter` together, since the compliance test compares override annotations against the base by equality.
    * `SQLiteEventWriter._rescale_data_to_adc` also documented its `dtype` default as "16-bit signed int" while actually defaulting to the **unsigned** `np.uint16` (it inherits signed `adc_min`/`adc_max` bounds from `np.iinfo(np.int16)`). The wording now matches the default. The method is a passthrough stub that ignores `dtype` entirely, so this was latent rather than live.
    * `RawDataModel.integrate_noise` picked up the same treatment, leaving no bare `np.ndarray` hints in the codebase.

* **Cleanup: dead code, lying signatures and shared mutable defaults**
    * **All function-local imports removed.** `poriscope/` now has zero lazy imports: `HelpCentre` in `main_view`, two `import bisect` in `MetadataView`, and `import sys` in `settings_window` are hoisted to module level. Hoisting `HelpCentre` also removed the `TYPE_CHECKING` block that existed only to make its annotation resolve, and `main_controller`'s two `TYPE_CHECKING` imports became plain ones (verified by importing all three modules together - no cycle). The only `TYPE_CHECKING` blocks left are the two in the menu widgets, which are genuinely forced by a cycle and now carry a comment saying so.
    * **`addItem` no longer accepts a `userData` it throws away.** Both multi-select combo boxes took the parameter for `QComboBox` signature compatibility and never stored it, so a caller passing a payload lost it silently. The parameter is gone; such a call now raises `TypeError`. Worth recording: a test docstring asserted the filter widget "does store it" - it does not. It calls `item.setData(Qt.UserRole, name)`, storing the item's own name, not a caller-supplied value. Neither class ever stored `userData`.
    * **`MainView.show_walkthrough_intro` is substitutable again.** It overrode `WalkthroughMixin.show_walkthrough_intro(current_view: str)` with a no-argument version. It now accepts the argument with a default and derives the view itself when none is given, so existing zero-argument callers are unaffected and the `# type: ignore[override]` is gone.
    * **Two shared mutable defaults fixed.** `DictDialog(source_plugins=[])` now defaults to `None`. `MainModel.replace_class_names_with_classes`'s `class_dict` was a constant lookup table in all but name and is now the module-level `_JSON_CLASS_NAMES`.
    * **The worker-generator storage type is precise.** `MetaModel.generators` and both `set_generator` signatures moved from a bare `Generator` to `Generator[float, Optional[bool], None]` - possible only now that all five producers agree on the abort contract.
    * **Removed:** the unused `comma_delimited_float_range_edit.py` module in full (186 lines, no references anywhere), `FloatRangeLineEdit.get_values_with_type_info` (no callers), `createIconButton`'s unreachable tuple-path branch, and the unreachable `"menu"` entry in `IconTextMenuWidget.emitSignal` - which would have raised `TypeError` if reached, since `menuToggled` is `Signal()` there but the branch emits a `bool`.
    * **Renamed** `time_widget`'s `FloatRangeValidator` to `TimeRangeValidator`, so the name no longer collides with the unrelated validator of the same name in `float_range_line_edit.py`.
    * **Deleted** `ClusteringSettingsDialog.update_unit_label` and `reset_top_inputs`, leftovers from an earlier design with one set of top-level input widgets; that was replaced by per-row widget dicts, so the five attributes they read are never assigned and either call would raise `AttributeError`.
    * Two stray debug `print()` calls removed. The one in `DictDialog.init_ui` printed plugin settings to stdout immediately before raising on an unsupported type; that detail is now in the exception message instead.

* **Fixed: abort now works uniformly across worker generators, and two latent type traps closed**
    * **CSV export can be aborted.** `MetaDatabaseLoader.export_subset_to_csv` was the only worker generator that ignored the value sent into it, so an export ran to completion no matter what the user did with the stop control, while event finding, fitting and writing all stopped cleanly. It now reads the flag and stops between events, following the same `abort_opt = yield progress` shape the others use. Files already written are left in place, and the count reached is logged.
    * **`MetaWriter._commit_events` was mis-annotated.** It declared `Generator[float, None, None]` - "nothing can be sent to me" - while its body did `abort_opt = yield index / num_events` and honoured the result. Corrected to `Generator[float, Optional[bool], None]`; hint-only, the behaviour was already right. With this and the export change, all five worker-generator producers now share one contract.
    * **`QComboBox.lineEdit()` is bound once where its guarantee is made.** It returns `None` unless the combo is editable, and both multi-select widgets relied on a `setEditable(True)` call hundreds of lines away from the five uses that depended on it - correct, but silently breakable. Cached as `self._line_edit` immediately after `setEditable(True)`, with an explicit check there.
    * **`app_config` path values are normalised to `str` at the boundary.** The defaults were built with `pathlib.Path` and then usually overwritten by the JSON read-back, but two branches escaped that and left a `Path` in the dict for a whole session: a failed initial write, and - more likely - the upgrade path, where a config predating the `"User Plugin Folder"` key gets a `Path` assigned into an otherwise all-`str` dict and is written out but never re-read. That matters because `DataPluginController` pre-populates a new plugin's Folder setting from this value and `BaseDataPlugin._validate_param_types` rejects anything failing `isinstance(value, str)`. Coerced at both entry points, so `get_data_server_location`/`get_user_plugin_location` can now honestly declare `-> str` instead of `Any`.

* **Fixed: instance attributes no longer shadow inherited Qt methods**
    * Five widget classes stored state under a name their Qt base class already uses for a method, which replaced that method on the instance. The custom behaviour these classes provide was never affected - a custom validator is installed through `setValidator()`, and that is untouched - but the inherited *getter* was destroyed in each case, so idiomatic Qt code calling it would fail.
    * `NumericLineEdit.validator` -> `_validator` (`QLineEdit.validator()` restored). `DictDialog.result`, `DropdownDialog.result` and `TimeWidget.result` -> `_result` (`QDialog.result()` restored); every consumer of those three reads the outcome through `get_result()`, so nothing external changes.
    * `BaseSubsetFilterDialog.layout` was deleted rather than renamed: `QVBoxLayout(self)` installs itself on the widget, so the inherited `QWidget.layout()` already returned the same object and the attribute was pure redundancy. Replaced with a local.
    * These were latent rather than live - no current call site hit any of them - but the trap is real: `BaseLineEdit.isValid` does `validator = self.validator()`, the correct Qt idiom, which would have raised `TypeError` the day `NumericLineEdit` was reparented onto `BaseLineEdit`. The renames also cleared genuine mypy findings, including a `method-assign` error and six `"Callable[[], QLayout | None]" has no attribute "addWidget"` errors that the `self.layout` shadowing had produced.
    * Also removed `handleUser` and the `switchUser` signal from both menu widgets - leftovers from functionality deprecated long ago, with nothing connected to the signal.

* **Removed: the abandoned language and theme sidebar controls**
    * `setLanguageChecked`/`setThemeChecked` existed in both `icon_menu_widget.py` and `text_menu_widget.py` and set `language_*_button`/`theme_*_button`, buttons that are never constructed - either call would have raised `AttributeError`. `handleLanguage`/`handleTheme` logged a line and did nothing else. Nothing reached any of them: there is no language or theme control anywhere in the sidebar or the menu bar, and `MainView.sync_sidebar_highlight` only ever selects one of four other setters.
    * All six methods removed. The unused `language_text.png` and `theme_TEXT.png` icon assets are the only remaining trace of the feature and are left in place.

* **New Dev Tooling: Type annotations for `main_view.py`, completing step 3**
    * Ninth and final batch of step 3: `views/main_view.py` on its own, the largest single file in the pass. 65 functions. Docstring/signature only - no behavior changes. With this, **every function in `poriscope/` outside the three excluded plugins has a fully annotated signature**, verified by AST scan: 369 functions across 39 files at the start of step 3, zero remaining.
    * `self.help_window` is typed against `HelpCentre` through a `TYPE_CHECKING` import, because `HelpCentre` is imported lazily inside `on_help_button_click` and so is not a module-level name. Both that lazy import and the `TYPE_CHECKING` block it forced are removable - `views/help.py` imports nothing from `main_view` - and are flagged for the follow-up pass. The two `TYPE_CHECKING` imports in the menu widgets are *not* removable: `main_view` imports both widgets, so a runtime import back would cycle.
    * `MainView.show_walkthrough_intro()` overrides `WalkthroughMixin.show_walkthrough_intro(current_view: str)` with a no-argument version. Every `MainView` call site passes nothing, so this is latent rather than live, but any mixin-level caller would raise `TypeError` against a `MainView`. Marked and flagged rather than resolved, since either fix changes a signature.

* **New Dev Tooling: Type annotations for the app shell**
    * Eighth batch of step 3: `main_app.py`, `models/main_model.py` and `controllers/main_controller.py` - config loading, plugin discovery, session persistence and the signal relay every analysis tab depends on. 43 functions across 3 files. Docstring/signature only - no behavior changes.
    * `MainController.__init__`'s `main_model`/`main_view` are annotated through a `TYPE_CHECKING`-only import, since `main_app` is what wires the three together and a runtime import would be gratuitous.
    * Corrected an annotation that the call site disproved: `MainModel.load_plugin`'s `allowed_base_classes` reads like the `{name: class}` mapping `populate_available_plugins` builds, but the one caller passes `tuple(allowed_base_classes.values())` - which is what `issubclass` requires. Typed `Tuple[type, ...]`. Had it been annotated from the parameter name instead of the call site, the hint would have been wrong in a way nothing would ever have caught, since `load_plugin` swallows every exception into a log line.
    * `get_app_config` and the two path accessors built on it are typed `Any` rather than narrowed, because the config really is heterogeneous: `Parent Folder` and `User Plugin Folder` start life as `pathlib.Path` objects on a fresh install and come back as `str` after the config has round-tripped through JSON. That inconsistency is flagged for review rather than papered over with a narrower hint.
    * `MainModel.get_plugin` gained an explicit `return None` on its `KeyError` path to match its declared `Optional[type]`, behaviorally identical to the implicit `None` it already returned.

* **New Dev Tooling: Type annotations for data-plugin management**
    * Seventh batch of step 3: `controllers/DataPluginController.py` and `models/DataPluginModel.py`, the one shared controller/model pair through which every data plugin is instantiated, edited, renamed and deleted. 11 functions across 2 files. Docstring/signature only - no behavior changes.
    * `DataPluginController.set_settings` takes `Optional[Dict[str, Any]]`: `MainController` relays a possibly-absent history entry into it and also calls it with an explicit `None` to clear the cache, so the optionality is part of the contract rather than an oversight.
    * Corrected a test fixture this surfaced. `tests/unit/controllers/test_data_plugin_controller.py` seeded `available_plugin_classes` as `{"MetaReader": []}` in sixteen places, but that parameter is documented and used as metaclass -> {subclass name: class}. `DataPluginModel` is mocked throughout that file, so the wrong shape never had a runtime consequence and nothing caught it; now that the parameter carries a hint, it does. Changed to `{"MetaReader": {}}`.
    * Worth noting for step 6: that error only appeared because the pre-commit `mypy` hook passes test files as explicit paths, bypassing `mypy.ini`'s `exclude = ^tests/`. This is the first time that blind spot has produced a useful finding rather than noise.

* **New Dev Tooling: Type annotations for the settings and help windows**
    * Sixth batch of step 3: `views/settings_window.py` and `views/help.py`. 35 functions across 2 files, including the whole `create_*` widget-factory family that builds the settings tabs. Docstring/signature only - no behavior changes.
    * `_NoFocusRectDelegate.paint`'s `index` parameter is typed `Union[QModelIndex, QPersistentModelIndex]` to match what `QStyledItemDelegate` actually declares; the narrower `QModelIndex` alone is a Liskov violation that mypy reports against both `QStyledItemDelegate` and `QAbstractItemDelegate`.
    * `HelpWindow._load_icon` is `-> None`: despite three `return` statements it never returns a value - each is an early exit, and the pixmap it builds is handed to the label rather than returned.

* **New Dev Tooling: Type annotations for the remaining view widgets**
    * Fifth batch of step 3: `multiselect.py`, `multiselect_filter.py`, `time_widget.py` and `SelectionTree.py`. 42 functions across 4 files. Docstring/signature only - no behavior changes.
    * `handleItemChanged`'s parameter is `Optional[QListWidgetItem]` in both multi-select widgets, not `QListWidgetItem`: `addItems` calls it with an explicit `None` to force a display refresh after a bulk load, so the optionality is load-bearing rather than defensive.
    * `SelectionTree.__init__` was annotated `parent: QWidget = None`, which is a hint that contradicts its own default; corrected to `Optional[QWidget]`.
    * Both multi-select widgets accept a `userData` argument on `addItem` for `QComboBox` signature compatibility and then never store it, so a caller that passes one silently loses it. Annotated `Any` to match, and flagged.
    * This batch surfaced a consistent pattern rather than isolated bugs: Qt accessors that return `Optional` are used without a guard throughout these widgets - `self.lineEdit()` in both multi-select boxes, `item.child(i)`/`topLevelItem(i)` in `SelectionTree`, and `QApplication.instance()` in `multiselect.py` (matching the same call in `BaseLineEdit`). Each would raise `AttributeError` on `None`. Collected for review rather than guarded one by one.

* **New Dev Tooling: Type annotations for the widget dialogs**
    * Fourth batch of step 3: `clustering_settings_widget.py`, `dict_dialog_widget.py`, the three subset-filter dialogs (`base_widgets/base_subset_filter_dialog.py`, `add_subset_filter_dialog.py`, `edit_subset_filter_dialog.py`) and `walkthrough_steps.py`. 39 functions across 6 files. Docstring/signature only - no behavior changes.
    * `DictDialog.__init__` already carried a full sphinx docstring, so its new signature hints were copied verbatim from the `:type:` lines it already declared - which clears its `DOC107` and its `DOC105` together instead of trading one for the other.
    * `ClusteringSettingsDialog.column_units` is typed `Mapping[str, Optional[str]]`, not `Dict`: `ClusteringView.units` genuinely holds `Optional[str]` values (a column can have no unit), and `Dict` is invariant in its value type, so a `Dict` annotation would have rejected the widget's own `dict[str, str]` call site.
    * `BaseSubsetFilterDialog.name`/`filter_text` start as `None` and are filled by `try_accept`, so `Optional[str]` is their honest type - but `ProteinView` and `MetadataView` read them straight after `exec()` returns `Accepted`, which cannot happen unless `try_accept` ran. That guarantee travels through a Qt signal connection mypy cannot follow, so it is asserted once per block at the point the locals are bound, rather than guarded at each of the six downstream uses in each file.
    * A second instance of the dead-attribute defect found in the menu widgets: `ClusteringSettingsDialog.update_unit_label` and `reset_top_inputs` reference `unit_label`, `column_combo`, `log_cb`, `norm_cb` and `plot_cb`, none of which is ever assigned anywhere in the class, and neither method is called from anywhere in `poriscope/`. Flagged for review rather than removed.
    * `DictDialog.entrywidgets`/`unitwidgets` are typed `Dict[str, Any]` deliberately: they hold whichever widget class each parameter's declared `Type` calls for, and `on_ok` duck-types across them through chained `AttributeError` handling, so a concrete widget type would make correct code look wrong.

* **New Dev Tooling: Type annotations for the sidebar menu widgets**
    * Third batch of step 3: `views/widgets/icon_menu_widget.py`, `views/widgets/text_menu_widget.py` and `views/widgets/dropdown_selection_widget.py`. 53 functions across 3 files. Docstring/signature only - no behavior changes.
    * Both menu widgets take the `MainView` that owns them as their first constructor argument, and `main_view.py` imports both, so the back-reference is annotated through a `TYPE_CHECKING`-only import rather than a runtime one, which would cycle.
    * `IconMenuWidget.createIconButton`'s icon-path parameters are typed `str` to match what every call site passes, leaving its `isinstance(..., tuple)` branch as unreachable defensive code - the same call-site-driven narrowing applied to `MetaReader`'s file lists earlier in this release.
    * Checking these bodies for the first time confirmed a defect by machine that had been invisible: `setLanguageChecked` and `setThemeChecked` exist in *both* menu widgets and set `language_*_button`/`theme_*_button`, neither of which is ever created, so either would raise `AttributeError`. Nothing reaches them - `MainView.sync_sidebar_highlight` only ever picks one of four setters - and the matching `handleLanguage`/`handleTheme`/`handleUser` handlers are equally unwired. Flagged for review rather than removed, since deleting them is a behavior change.

* **New Dev Tooling: Type annotations for the line-edit / validator family**
    * Second batch of step 3: `utils/BaseLineEdit.py` and `utils/BaseValidator.py` (the abstract pair every range input inherits), the three range line edits (`float_range_line_edit`, `integer_range_line_edit`, `comma_delimited_float_range_edit`) and `views/widgets/validators/numeric_validation.py`. 44 functions across 6 files. Docstring/signature only - no behavior changes.
    * The whole family funnels through one shape, now written down once: every `common_validation`/`validate`/`_validate_intermediate`/`_validate_final` hook returns Qt's `Tuple[QValidator.State, str, int]` triple, and `has_forbidden_characters` returns the `Optional[re.Match]` its `re.search` produces rather than a `bool`. PySide6 declares `QValidator.validate` positional-only and returning `object`, so narrowing the return in a subclass is accepted.
    * `FloatRangeLineEdit.get_values` returns `List[float]` while `CommaFloatRangeLineEdit.get_values` returns `List[Tuple[Optional[float], Optional[float]]]` - the same method name means two different things in sibling classes. Each is internally consistent and is annotated to match its own behaviour; `CommaFloatRangeLineEdit` currently has no callers anywhere in `poriscope/`.
    * Annotating these methods made mypy check their bodies for the first time, which surfaced the expected crop of pre-existing PySide6 short-form enum accesses (`QValidator.Invalid`, `QEvent.Show`, and friends) that `DECISIONS.md` records as stub noise to be left alone. Three findings in that batch are genuine and were flagged rather than fixed: `NumericLineEdit.validator` shadows the inherited `QLineEdit.validator()` method, `BaseLineEdit.__init__` calls `QApplication.instance().installEventFilter(...)` with no `None` guard, and PySide6's stub types `QValidator.validate` as returning a bare `object` so every `state, _, _ = validator.validate(...)` unpack reads as an error despite working at runtime.

* **New Dev Tooling: Type annotations for app-shell leftovers**
    * Opens step 3 of the `future_fixes.md` type-annotation pass by closing the gaps steps 1 and 2 left behind in areas they reported complete: `QObjectABCMeta`/`QWidgetABCMeta`'s `__new__`/`__call__`, `QtHandler`, `EventWorker`'s `Worker`/`WorkerThread` pair, `DocstringDecorator`, `JsonDefaultSerializer`, `MetaDatabaseWriter.lookahead_generator`, `ABF2Header` in full, and a `get_empty_settings(standalone: bool)` / `_finalize_initialization -> None` pair repeated across `SQLiteEventWriter`, `SQLiteEventLoader`, `BesselFilter` and `WaveletFilter`. 37 functions across 12 files; every parameter and return now annotated, verified by AST scan rather than by eye. Docstring/signature only - no behavior changes.
    * Four attributes in `ABF2Header` and one in `SQLiteEventWriter` gained explicit element types (`scaleFactors`, `channel_names`, `channel_units`, `lADCChannelNameIndex`/`lADCUnitsIndex`, `channel_db_id`). These are the usual consequence of annotating a method: an empty-container attribute is invisible to mypy until its enclosing method is checked, at which point it needs a declared element type. Same for `Worker.process_generator`/`run`'s progress counter, which starts at the integer `0` and is then assigned the generator's float.
    * `Worker.__init__`'s generator parameter is annotated `Generator[Any, Any, Any]`, deliberately looser than the real runtime contract (it sends a `bool` and receives a normalized float). `MetaModel` stores these in a `Dict[str, Dict[int, Generator]]`, and a bare `Generator` reads as `Generator[Any, None, None]`, which is not assignable to the precise form. Tightening `MetaModel`'s declaration to the true contract is the correct fix but ripples out to every `set_generator` caller, so it is left for review rather than folded into this batch.
    * The pydoclint baseline dropped from 216 to 208 entries: batch 1 cleared the four `standalone`-parameter `DOC105`s and four `DOC107`s outright. The seven `DOC105`s remaining in `MetaDatabaseWriter`/`SQLiteEventWriter` are pre-existing docstring-text disagreements belonging to step 4 of the pass, not missing hints.

* **Corrected: pydoclint now treats signature type hints as the source of truth**
    * `arg-type-hints-in-signature` was set to `false` on the premise, recorded in `pyproject.toml`, that most plugin methods deliberately omit signature hints and document types only in the docstring. An AST scan of `poriscope/` disproved it: the large majority of functions already carry at least one signature hint. The setting was therefore not describing the codebase, it was fighting it - 663 of the baseline's 709 entries were `DOC108` ("you have type hints but the policy says you shouldn't"), which masked nothing, fixed nothing, and grew by a few lines every time the type-annotation pass added hints to another file.
    * Flipped to `true` and the baseline regenerated from scratch: **709 entries down to 216**, with `DOC108` gone entirely. What remains is real and actionable - 111 `DOC105` (a signature hint and a docstring `:type:` that disagree), 31 `DOC107` and 27 `DOC106` (missing or partial hints, exactly the work the type-annotation pass is doing), and the 46 pre-existing `DOC203`/`DOC5xx` entries that were already there under the old policy.
    * Practical effect for the ongoing annotation pass: each batch now *shrinks* the baseline instead of adding `DOC108` lines to it, so the file is a progress meter rather than accumulating noise to be deleted at the end.
    * This flip was not blocked by the pre-commit `mypy` hook's test-path scoping problem that still gates the `disallow_untyped_defs`/`check_untyped_defs` flip (see `future_fixes.md`): the pydoclint hook is already scoped `files: ^poriscope/`. The two were bundled into one step in the plan by mistake and have been split.

* **New Dev Tooling: `mypy` `strict_equality`**
    * Turned on in `mypy.ini`. It rejects equality comparisons between non-overlapping types - most usefully here, a display string compared against an `int` channel id, which always evaluates unequal and silently defeats cache-staleness checks.
    * Measured at **zero** new errors when enabled, because the channel-identifier fixes earlier in this release had already cleared every such site (five of them, in `MetadataView` and `ProteinView`). It is on so that bug class cannot quietly return; it is free at the point of adoption.

* **Fixed: abandoned walkthroughs no longer poll forever, and their retries no longer outlive the widget**
    * `WalkthroughMixin._run_next_walkthrough_step` waits for the user to be on the step's target view by rescheduling itself with `QTimer.singleShot(200, wait_for_view)`. That form is parented to nothing and had no cancellation of any kind, so a walkthrough that was launched and then abandoned - the user navigates away from the target view instead of following the step - kept polling at 5 Hz for the remaining life of the process, and each callback closed over a widget that might already be gone.
    * Both retry timers (the 200 ms view wait and the 500 ms auto-advance poll) now pass the widget as `QTimer.singleShot`'s `context` argument, so Qt drops the callback if the widget is destroyed first rather than calling into a deleted C++ object. Verified against the installed PySide6 6.9.0 that the overload is accepted, that a live context still fires exactly once, and that a destroyed context suppresses the callback entirely.
    * A generation token, bumped whenever a step starts and whenever the walkthrough ends, retires stale view-wait polls. It is deliberately a token rather than a `_walkthrough_active` check: `_handle_walkthrough_done` sets that flag `False` and *then* calls `_run_next_walkthrough_step()` for the pseudo-advance path, so guarding on the flag would return immediately on the next step's first call and silently break auto-advance-on-view-change. Starting a step issues a fresh token regardless of the flag, so the pseudo-advance path keeps working.
    * Note this is *not* the cause of the `tests/unit/views`-before-`tests/unit/plugins` segfault fixed above, despite being a plausible candidate for it - binding the timers to a context was tested against that crash first and did not fix it.

* **Fixed: the test suite no longer segfaults when `tests/unit/views` runs before `tests/unit/plugins`**
    * Running those two directories in that order killed the interpreter with an access violation inside `test_walkthrough_mixin.py::test_no_valid_widgets_logs_error`, in a `qtbot.wait(100)` that only spins the event loop - so that test was the victim, not the cause. CI never saw it because alphabetical collection runs `plugins` first, but a suite that dies on a legitimate partial selection is a real problem, and the crash was repeatedly mistaken for a regression in whatever had been committed last.
    * Bisected to `tests/unit/views/widgets/test_multiselect_filter.py`, then to `TestClearSelectionList`, then to the single call `listWidget.clear()`. The three widget test files tore their widgets down with `QWidget.destroy()`, which only releases the native window - the C++ object survives until Shiboken collects the Python wrapper at some arbitrary later point in the run. A widget disposed of that way can leave posted events behind that fault the interpreter the next time *any* test spins the event loop, hundreds of tests later. `test_multiselect_filter.py`, `test_multiselect.py` and `test_selection_tree.py` now dispose of widgets through a shared `dispose()` helper (`deleteLater()` plus a drained event loop), which deletes them while Qt can still clean up after them.
    * Several plausible causes were ruled out by experiment rather than by reading: the walkthrough `moveEvent` hook (recorded in `DECISIONS.md`), the widget's never-removed application-wide event filter, the unowned `QTimer.singleShot` retries in `walkthrough_mixin.py`, the parentless top-level `containerWidget` dialog, the module-level `get_icon` patch's shared `QIcon`, and `destroy()` followed by an explicit `gc.collect()` - none of which fixed it.

* **New Dev Tooling: tests can no longer reach the developer's real app-data directory**
    * Poriscope resolves its config, session and log directories through `platformdirs.user_data_dir()`, so anything that builds a real `MainModel` writes into the actual `%LOCALAPPDATA%/Poriscope` profile and can overwrite a real saved session and tab-action history. Every place that did so already redirected that call for itself - `tests/e2e/conftest.py`'s autouse `sandbox_appdata` and `tests/unit/models/conftest.py`'s `main_model` fixture - but that was a convention each area had to remember, not a property of the suite.
    * A new top-level `tests/conftest.py` makes the redirection an inherited default: an autouse fixture points `user_data_dir` at a per-test `tmp_path`, so a test added anywhere in the tree is sandboxed without doing anything. Both existing fixtures still run after it and deliberately override it with their own roots, since their assertions depend on the specific layout they build. `poriscope.main_app` is the other consumer and is only patched if something has already imported it, so the fixture cannot force a `QApplication` into every test. Full suite green (2,615 passed, 2 skipped).

* **Fixed: scoped channel identifier is now an int in the Metadata and Protein tabs**
    * The experiment/channel selection tree hands back display strings, but everything downstream treats the value as a channel id - it is interpolated unquoted into `channel_id = {channel}` SQL predicates, stored in `current_channel`, and put in the `plotted_datasets` tuple. `MetadataView` converted only at the `plotted_datasets` insertion, leaving `current_channel` holding a string; `ProteinView` never converted at all. Both views now convert once at the derivation site, so the stored value and the cache-staleness comparison are the same type and cannot silently disagree.
    * The `exp_and_ch`/`exp_and_ch_arg` dicts passed to loader plugins are deliberately unchanged: `MetaDatabaseLoader`'s `tuple_builder` stringifies list members unquoted, so string and int channels produce identical SQL, and converting them would touch the loader contract for no behavioural gain.

* **Fixed: raw-SQL subset filters are committed under the same guard as assisted filters**
    * Subset filters have two validation paths sharing one pending-state handoff (`_pending_filter_name`/`_pending_filter_text`/`_pending_old_filter_name`): assisted filters validate via `construct_metadata_query` and commit in `Metadata`/`ProteinController.relay_query`, raw SQL filters validate via `validate_filter_query` and commit in the view's `on_raw_filter_validated`. The controller half already checked `if name is not None:` and coerced the body with `filter_text or ""`; the view half did neither, so a callback with no pending state would have used `None` as a key and value in a `Dict[str, str]`. The view now applies the same guard and returns early with a warning. Not reachable today, since the pending fields are set immediately before the emit and `global_signal` dispatch is synchronous, but the two halves of the feature no longer disagree about the contract.

* **Fixed: `EventAnalysisView` crashed on fitted events whose features carry no labels**
    * `EventAnalysisController.update_features` explicitly accepts "a label (which can be explicitly None) for every feature, or no labels at all", and `MetaEventFitter.get_plot_features` declares each of its three label lists `Optional[...]`. But `_update_event_plot` guarded only on the feature list before zipping it against its label list, so a fitter returning vertical lines, horizontal lines, or points with the corresponding label list set to `None` raised `TypeError: zip argument #2 must support iteration`. All three sites now substitute a matching run of `None`s, which the existing `if label is None:` branch already renders as an unlabeled feature.
    * The label parameters were widened to `Sequence[Optional[Sequence[Optional[str]]]]` to describe what the loop bodies actually accept, and the inner loop variables renamed to `line_label`/`point_label` - they had been shadowing the outer per-subplot `label`, which is a plain `str`.

* **Fixed: `ClusteringView.units` was serving two incompatible roles**
    * `update_column_units` filled it as a column-name -> unit map, consumed by `ClusteringSettingsDialog`, while `update_plot` overwrote it with a positional list of units for the plotted columns, consumed by `_merge_clusters` when re-plotting. Whichever ran last won, so opening the cluster settings dialog after a plot passed a list to code that calls `.get()` on it. The positional list now lives in its own `self.plot_units`, alongside the `self.logs`/`self.normalized`/`self.plot` that `update_plot` already stored, and is initialised in `_init` so the attribute exists before the first plot (`_merge_clusters` reads it).

* **Updated: `start_walkthrough` falls back explicitly when the overlay cannot be created**
    * It previously passed a `None` overlay into `StepDialog`, whose constructor calls `update_step()` and therefore raised `AttributeError`, which the enclosing `try` turned into the fallback `QDialog`. Same outcome, but it now returns the fallback directly instead of constructing a dialog guaranteed to fail.

* **Fixed: the Metadata tab re-plotted datasets it had already drawn**
    * `_overlay_plot`'s "do not overlay the same thing twice" guard tested `plotted_datasets` membership with the raw `channel` - the display string handed back by the experiment/channel selection tree - while inserting the tuple with `int(channel)`. A string channel is never found in a set keyed on ints, so the guard only ever matched in the no-selection case, where both sides normalise to `None`. Every repeat of an identical selection therefore stacked another copy of the same curve. Both sides now use a single normalised `channel_id`, computed once per channel. The same normalisation was applied in `ProteinView`, which maintains `plotted_datasets` but never reads it, so that adding a guard there later cannot reintroduce the mismatch.

* **Fixed: a no-op plot click left an Undo step that restored an identical figure**
    * With the dedup guard working, clicking Update Plot again with an unchanged selection legitimately draws nothing - but `_overlay_plot` still returned `True`, so the action was recorded and Undo would spend a step re-rendering the same plot. It now reports whether anything actually reached the axes, and `handle_parameter_change`'s existing `if success is False` branch rolls the recorded action back. Note that rollback path replays the remaining history, so a no-op click re-renders before settling on the same figure; that is the pre-existing behaviour of every other `return False` path in this method and was left consistent.

* **Updated: `_set_control_area` takes a `QBoxLayout` rather than a `QLayout`**
    * `MetaView._setup_ui` only ever passes a `QVBoxLayout`, and all five tab implementations call `layout.addLayout(...)`, which exists on `QBoxLayout` but not on `QLayout`. The wider annotation claimed a `QGridLayout` was acceptable when every implementation would break on one. Narrowed on the abstract method and all five overrides, restoring the intent of the original "QVBoxLayout or QHBoxLayout" docstrings. The sibling layout hooks (`_set_display_area_base`, `_set_progress_area`, `_set_custom_display_area`) use `addWidget` only and correctly stay `QLayout`.

* **Fixed: an unmapped button type raised `AttributeError` instead of being ignored**
    * `on_button_clicked` in `rawdatacontrols`, `eventAnalysisControls` and `metadatacontrols` ended with `button_mapping.get(button_type, lambda: None).setChecked(False)`. The fallback is a plain function with no `setChecked`, so an unmapped `button_type` raised instead of doing nothing. `clusteringcontrols` and `proteincontrols` already guarded this correctly; the other three now match. Not reachable from the GUI - every `button_type` emitted by `connect_signals` is a key in `button_mapping` in all three files - but it is an easy trap when adding a button to only one of the two dicts.
    * The two existing tests that pinned the old behaviour with `pytest.raises(AttributeError)` now assert the no-op their own comments described as intended.
    * Worth recording for QA: this was invisible to the pre-commit `mypy` hook because that hook runs in an isolated virtualenv with no project dependencies and `--ignore-missing-imports`, so `QPushButton` is `Any` to it. The project venv's mypy flags it exactly. See `future_fixes.md` step 6 for the measured scope of that blind spot and why closing it is judged low value.

* **Updated: walkthrough dialog repositioning uses a hook instead of a monkey-patched Qt virtual**
    * `WalkthroughMixin` replaced the dialog's `moveEvent` on the instance (`self.walkthrough_dialog.moveEvent = self._reposition_dialog`). That does work - PySide6 honours an instance attribute for a virtual, confirmed by direct probe, so it was live code rather than the dead code it looks like - but it is invisible to static checking and it suppressed `QDialog`'s own `moveEvent` entirely. `StepDialog` now exposes an `on_move` callback and a real `moveEvent` override that chains to `super()` before invoking it, and the mixin assigns that instead.
    * Behaviour-neutral, verified rather than assumed: replaying the real install order (`start_walkthrough` shows the dialog, the mixin attaches the handler afterwards) gives the same handler call count for both forms, and `on_move` defaults to `None` so move events during construction and `show()` remain no-ops. This clears the last `# type: ignore` under `poriscope/plugins/analysistabs/`.

* **New Dev Tooling: the `@log` decorator no longer erases the signatures it wraps**
    * `LogDecorator.log` was declared `-> Callable`, i.e. `Callable[..., Any]`, so applying it replaced the decorated method's type with `Any` from every caller's point of view. It is applied to **935 methods across 71 files**, which means the type-annotation pass had made every *body* checkable while leaving essentially every *call site* into a plugin or controller method unchecked. `register_action` had the same defect. Both now take a `TypeVar` bound to `Callable` and hand back the type they were given.
    * Verified rather than assumed, before and after, with `reveal_type`: a decorated `(x: int) -> str` previously revealed as `Any` and accepted `p.decorated("not an int")` silently; it now reveals as `def (x: int) -> str` and rejects that call. Generator methods keep their `Generator[int, None, str]` through the `yield from` wrapper, and `functools.wraps`/`inspect.signature`/`isgeneratorfunction` behave exactly as before.
    * This is a type-level change only - the two `cast()` calls it adds are no-ops at runtime - but it is not cosmetic: turning it on surfaced **84 real call-site errors** under the pre-commit gate, which had been reporting clean. Roughly half were annotation defects and are fixed below; the rest are genuine logic defects, listed in `future_fixes.md` for review rather than fixed here.

* **New Dev Tooling: the pre-commit `mypy` hook no longer type-checks `tests/`**
    * `mypy.ini` sets `exclude = ^tests/`, but that governs directory *discovery* only - it does not apply to files listed explicitly on the command line, which is exactly how pre-commit invokes hooks. The hook was therefore checking all 73 test files as well as the 122 under `poriscope/`. Scoped it with `files: ^poriscope/`, matching how the `pydoclint` hook was already configured. The hook now reports "122 source files", the exact count under `poriscope/`.
    * This had to land before any tightening of the type-policy flags, since otherwise a change that looks clean under `mypy poriscope` would break every real commit.

* **BREAKING: `MetaReader.get_channel_length` takes a required channel and returns an `int`**
    * It was `get_channel_length(channel: Optional[int] = None) -> int | Dict[int, int]`, returning one channel's sample count when given a channel and a dict of every channel's when given nothing. **The no-argument form had no callers anywhere** - not in the app, not in the tests, and not in the `MetaReader` test double in `tests/unit/utils/test_meta_event_finder.py`, which has always declared `channel` as required. Internally the dict was reached directly through the `total_channel_samples` attribute rather than through this method. The union dated to the initial commit.
    * Because the declared return type is what callers see regardless of what they pass, that dead branch made the return unusable at all five real call sites: 15 of the 84 errors above were arithmetic on `int | dict[int, int]` in `MetaReader` and `MetaEventFinder`. Dropping the branch clears all of them with no casts and no `@overload`.
    * **This narrows a `Meta*` ABC, which is the plugin-facing contract.** Any third-party reader plugin calling `get_channel_length()` with no argument would break; a call with a channel is unaffected. There are no third-party plugins today, which is why this was taken rather than preserved.
    * `MainModel.get_available_plugins` had the identical shape - `Optional[str]` parameter, `List[str] | Dict[str, List[str]]` return - and the identical outcome: every caller in the app and in all fourteen e2e tests uses the no-argument form. The parameter is gone and it now returns `Dict[str, List[str]]`; the one unit-test assertion covering the dead branch was dropped with it.

* **Fixed: annotation defects the `@log` change exposed**
    * `DataPluginModel`'s plugin accessors were declared `-> object`, which is strictly *worse* than the `Any` they actually store - it made every real method call on a retrieved plugin an error. `get_plugin_instance`, `get_temp_instance`, `register_plugin` and the `plugins`/`available_plugins` containers now name `BaseDataPlugin`, and `get_plugin_instance` is honestly `Optional[...]` since it is a `dict.get`.
    * `MetaReader._sort_objects_by_channel_and_time` declared `Dict[int, List[Union[str, int, float, datetime, date, np.datetime64]]]` - the value type had been copied from its `timestamps` parameter. The function's last act is a comprehension whose comment reads "Extract only the objects, discarding the timestamps", so it returns the objects it was handed: `Dict[int, List[Any]]`. This is what made `configs` and `datamaps` unindexable throughout `load_data`.
    * `MetaReader._get_file_names` declared `folder: os.PathLike` but its only caller passes the `str` from `os.path.split`, and its body wraps it in `Path()` which accepts either. Widened to `Union[str, os.PathLike]` on the base and on `SingleBinaryDecoder`'s override, which has to copy the base verbatim to satisfy `test_plugin_compliance.py`.
    * `DataPluginView.get_user_settings` declared `-> tuple[dict, str]`, but it returns `DictDialog.get_result()`, which has **four** shapes: `(params, name)` on OK, `(None, None)` on Cancel, the sentinel string `"delete"`, and a bare `None` when the dialog is dismissed without either handler running. Corrected to match.
    * `MetaEventFinder.get_single_event_data`'s `rectify`/`raw_data` were `Optional[bool]` with no caller ever passing `None`, and `raw_data` is forwarded straight into `MetaReader.load_data`, which takes `bool`. `MainModel.populate_available_plugins` gained an explicit `plugin_class is not None` check that is redundant at runtime - the surrounding `metaclass` is only ever set on a branch that already tested it - but is what lets the checker see it.
    * Two findings in `PeakFinder`/`Basic_PeakFinder` are marked with narrow `# type: ignore[arg-type]` and an explanatory note rather than fixed, per the standing policy that logic in those two files belongs to their owner: the event metadata dict is declared `Union[int, float, str, bool]` by the base contract, so `baseline_current`/`baseline_stdev` read back wider than the `Optional[float]` that `find_mode_blockage_level` accepts.

* **BREAKING: `MainModel.get_plugin_classes` takes a required metaclass**
    * It was `get_plugin_classes(metaclass: Optional[str] = None) -> Union[Dict[str, type], Dict[str, Dict[str, type]]]`, returning one metaclass's subclass map when given a metaclass and the whole map when given nothing. Unlike `get_channel_length` and `get_available_plugins`, **both arms were genuinely live**: `main_controller.py:64` used the no-argument form to seed `DataPluginController`, and `:405` used `get_plugin_classes("MetaController")[subclass]`. Neither branch could simply be deleted.
    * Resolved by removing the `None` mode switch rather than the parameter: the metaclass is now required and the return is a single `Dict[str, type]`, and the one call site that wanted the full mapping builds it itself with a comprehension over `get_available_plugins()`, whose keys are the same metaclasses. Behaviour is unchanged - `available_plugin_classes` is populated exactly once in `MainModel.__init__` and never reassigned or mutated, so handing over a freshly built outer dict is equivalent to passing the live reference it used to pass.
    * **This narrows a public `MainModel` method.** A caller invoking `get_plugin_classes()` with no argument would now fail; a call with a metaclass is unaffected. The one unit-test assertion covering the dead form was dropped.

* **BREAKING: `DictDialog` reports deletion separately instead of through a sentinel return value**
    * `DictDialog.get_result()` had **four** return shapes - `(params, name)` on OK, `(None, None)` on Cancel, the string `"delete"` on Delete, and a bare `None` that was simply the never-reassigned initial value. The fourth was reachable: Cancel and Delete are plain `QPushButton`s, so dismissing the dialog with **Esc** or the **window close button** goes straight to `QDialog.reject()` without running either handler.
    * `get_result()` now always returns `Tuple[Optional[dict], Optional[str]]`, and deletion is reported by a separate `delete_requested()` accessor. Dismissal is now indistinguishable from Cancel, which is what every call site already assumed. `DataPluginView.get_user_settings` correspondingly returns `Tuple[Optional[dict], Optional[str], bool]` instead of the four-shape union.
    * This was the root cause of five type errors in `MetadataView` and two in `DataPluginController` that no amount of guarding could resolve without `isinstance` checks against the sentinel string. The `"delete"` branch in `MetadataView._export_csv_subset` was unreachable anyway - that dialog is constructed with `show_delete=False` - and is gone.
    * Test mocks for `get_user_settings` and `get_result` need the new shapes; the affected unit tests were updated.

* **Fixed: editing a plugin and dismissing the dialog crashed and left the dependency graph corrupted**
    * `DataPluginController.edit_plugin` tested `result == (None, None)` and `result == "delete"` but never the bare `None` that Esc or the window close button produces, so that case fell through to `settings, key = result` and raised `TypeError`. Worse than the crash: by that point the method had **already** run `unregister_dependent` on every parent, and every other abort path calls `_restore_parent_dependent_links` to undo that. The `TypeError` skipped restoration, leaving the edited plugin's parent links broken in the live model. Fixed by the `DictDialog` reshape above - dismissal now returns cleanly exactly as Cancel does.
    * `edit_plugin` also never `None`-guarded the instance it looks up. `get_plugin_instance` is a `dict.get`; the sole in-repo caller guards with `if plugin:` first, but `edit_plugin` is a public `@Slot`, so a direct invocation with an unknown key raised `AttributeError`. It now logs and returns.
    * The upfront unregister loop moved into a new `_unregister_parent_dependent_links`, the counterpart to the existing `_restore_parent_dependent_links`, and picked up the same `if pinstance:` guard that helper already had. A parent that has gone missing is now skipped rather than raising `AttributeError` out of `edit_plugin` uncaught.
    * A missing *dependent* instance in the rename loop now raises a `RuntimeError` naming the plugin. Control flow is unchanged - it lands in the same per-dependent handler that previously reported the resulting `AttributeError` - but the message now says what is actually wrong.

* **Updated: `DataPluginController.validate_and_instantiate_plugin` takes a required subclass**
    * `subclass` was `Optional[str] = None`, but all eight GUI emitters in `main_view.py` pass a real subclass string and the session-restore path passes `plugin["subclass"]`, a required key. Narrowed to `str`, which makes it positionally required; no caller passed fewer arguments.
    * `key` legitimately stays `Optional[str]` - `None` is the normal GUI path, reassigned from the settings dialog before use - but is now explicitly checked before `set_key`. The `ValueError` it raises is caught by the method's own handler, so an unreachable silent `set_key(None)` becomes a logged, reported no-op.

* **Fixed: `BaseDataPlugin.get_raw_settings` was declared `Optional[dict]` but can never return `None`**
    * It returns `self.raw_settings`, which is declared `dict[str, dict[str, Any]]`, initialised to `{}`, and only ever reassigned from a truthy dict inside `apply_settings`. There are no overrides. The false `Optional` was what made the settings dict unindexable throughout `edit_plugin`'s dependent-rename loop - six errors from one wrong return type. `DataPluginModel.get_plugin_settings` still returns `Optional[dict]`, correctly, because it returns `None` when there is no such plugin instance.

* **Fixed: `SQLiteDBWriter` could write sublevel and event-data rows keyed on a `None` event id**
    * `event_db_id = self.cursor.lastrowid` is `Optional[int]`, and was passed straight into `_insert_sublevels`/`_insert_event_data`. It now raises `RuntimeError` if the event insert reports success without producing a row id, matching the two existing `RuntimeError` guards in the same block, so the transaction rolls back instead of writing orphaned rows.

* **Fixed: assorted annotation defects the strictness flip surfaced**
    * `IntraCUSUM` accumulated `event_metadata["threshold_crossings"] += 1` directly into a dict slot the base contract declares `Union[int, float, str, bool]`. It now counts into a local `int` and assigns once after the loop; identical arithmetic.
    * `ProteinView._update_distribution_individual` read `parameters.get("sizes")` with no default, leaking `None` into a `bool` parameter. This is not the no-op it looks like - the use site tests `if sizes is False:`, an identity comparison, so `None` selects the bin-*width* branch where `False` selects bin-*count*. It now matches its sibling's `parameters.get("sizes", False)`; no live path changes, because `proteincontrols` always supplies a real bool.
    * `DataPluginController._restore_parent_dependent_links` declared its `parents` argument `List[Tuple[str, str]]` while its only caller passes the `Set[Tuple[str, str]]` from `get_parents()`; `DataPluginModel.get_instantiated_plugins_list` was declared `Mapping` while returning a dict comprehension. Both corrected. The delete branch's log line no longer rebinds `dependents` from a set of pairs to a list of keys.
    * `ProteinController` and `MetadataController` pass an `Optional[str]` `old_name` into `update_filter_name(old_name: str)`. The `None` is unreachable - `show_edit_filter_dialog` sets it from a `str` parameter before emitting the intent - but the guarantee travels through a signal connection the checker cannot follow, so each site carries a narrow `# type: ignore[arg-type]` and a note, matching the precedent already in `ProteinView`. Moving the call inside the existing `if old_name is not None:` guard was rejected: with `old_name=None` the body still adds and selects the renamed filter, so guarding it would silently drop the renamed filter from the combobox.

* **New Dev Tooling: `disallow_untyped_defs` and `check_untyped_defs` are on**
    * The final step of the type-annotation pass. `mypy.ini` had both at `False` since the pass began; with every function under `poriscope/` annotated and all 52 call-site errors resolved, both are now `True` and the pre-commit `mypy` hook passes clean across all 122 source files. New code is expected to be annotated - an unannotated `def` under `poriscope/` now fails the hook rather than being silently skipped.
    * Measured, not assumed: the flip produced zero new errors, because `disallow_untyped_defs` had nothing left to find and `check_untyped_defs` had no unchecked bodies left to check. That is only true because the 52 errors above were fixed first; the flip would have been meaningless on top of a decorator that erased 935 signatures.

* **New Data Plugin: `ThresholdBlockageFinder`**
    * Subclass of `ClassicBlockageFinder` that imposes much tighter bounds on the start and end times flagged in the output.

* **New: End-to-end (E2E) test suite**
    * Added comprehensive E2E/UX coverage for RawData, EventAnalysis, Metadata, Clustering , and Protein tabs
    * Added a shared `tests/synthetic_data` package for reproducible fixtures: synthetic Chimera recordings, synthetic events/metadata SQLite databases (with configurable event lengths and deliberately-rejected events for testing fitter rejection paths), removing reliance on checked-in binary test databases
    * Registered the `smoke` pytest marker in `pytest.ini`

* **Deprecated Data Plugin: `ABF2Reader`**
    * Renamed to `TCossaLabABFReader` to reduce ambiguity with file types.
    * Fixed `ABF2Header` never closing its file handle after parsing an ABF header, since the underlying file is only ever read during construction
    * Fixed `ABF2Header`'s per-channel scale-factor calculation checking `nTelegraphEnable[0]` for every channel instead of `nTelegraphEnable[i]`, silently corrupting current scaling on multi-channel files where telegraph-enable status differs between channels

* **Updated Data Plugin: `WaveletFilter`**
    * Fixed a ctypes ABI mismatch (`c_int` vs `int64_t`) on the signal-length argument that risked memory corruption on large arrays
    * Calls into the shared native library are now serialized with a lock, since filters are invoked directly by other plugins rather than through the channel-management system
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugin: `NoFitter`**
    * Fixed an unbounded backtrack loop that could silently corrupt sublevel edges via negative array indexing instead of cleanly rejecting the event
    * Added missing validation for `None` baseline/padding inputs
    * Fixed `_locate_sublevel_transitions`'s docstring being generic abstract-method boilerplate instead of describing what this class actually does (locate a single baseline crossing; no changepoint search)

* **Updated Data Plugin: `ClassicCUSUM`**
    * Removed an undocumented `/5` threshold divisor and a leftover debug `print()` that made this fitter far more sensitive than `CUSUM`/`IntraCUSUM`
    * Fixed `_locate_sublevel_transitions`'s docstring being generic abstract-method boilerplate that didn't mention this class's actual difference from `CUSUM`: Step Size is used directly in units of σ instead of being normalized against the local baseline standard deviation

* **Updated Data Plugins: `ClassicBlockageFinder`, `BoundedBlockageFinder`, `ThresholdBlockageFinder`**
    * Fixed a `ZeroDivisionError` on constant-signal chunks in baseline histogram calculation
    * Fixed dead code that silently skipped baseline-histogram window symmetrization
    * Fixed an ambiguous end-of-chunk check that could silently drop the remaining events in a chunk
    * Removed a dead `median_abs_deviation(data)` call (`ClassicBlockageFinder`/`BoundedBlockageFinder`) whose result was discarded, along with the now-unused import
    * Fixed `_filter_events`'s `channel` parameter docstring describing it as "Bool indicating whether this is the first chunk of data," despite being typed `int` and unused in the method body
    * Fixed `_get_baseline_stats`'s docstring (`ClassicBlockageFinder`/`BoundedBlockageFinder`) promising "the local amplitude, mean, and standard deviation," when the method only ever returns `(mean, std)`

* **Updated Data Plugins: `CUSUM`, `IntraCUSUM`, `NoFitter`**
    * Fixed an off-by-one indexing bug that shifted every reported extreme-sublevel duration by one level
    * Fixed `NoFitter._locate_sublevel_transitions` not validating `padding_after`/`baseline_std` for `None` despite the method's own docstring promising graceful handling for every argument but `data`; both now raise a clean `ValueError` instead of crashing later with a raw `TypeError`
    * Fixed `IntraCUSUM._populate_event_metadata` computing `np.sign(baseline_mean)` with no `None` guard despite `baseline_mean` being documented `Optional[float]`; `CUSUM`'s own base-class methods never use `baseline_mean`, so there was no upstream validation this could rely on. Now raises a clean `ValueError` instead of crashing
    * Fixed `CUSUM`/`NoFitter`'s `construct_fitted_event` docstrings claiming `:raises RuntimeError:` when fitting isn't complete; both actually return `None`
    * Removed a dead `get_samplerate(channel)` call in `CUSUM`/`NoFitter`'s `construct_fitted_event` whose result was discarded, and fixed a stale copy-pasted "CUSUM cannot operate..." error message inside `NoFitter`'s own error path
    * Fixed `CUSUM._locate_sublevel_transitions`'s docstring being generic abstract-method boilerplate instead of describing the adaptive-threshold CUSUM log-likelihood-ratio changepoint detection it actually runs
    * **Flagged for later:** `NoFitter`'s `rise_time` and `CUSUM`'s recovered `baseline_std` are each computed inside `_locate_sublevel_transitions` but needed again in `_populate_sublevel_metadata`, whose signature doesn't receive `padding_before`/`padding_after`; neither value can be safely recomputed independently there. `NoFitter` currently stashes `rise_time` on `self`, a call-ordering hazard, and `CUSUM`'s `baseline_std` recovery for a loader that omits it never propagates to `_populate_sublevel_metadata`. The base class's own docs point at the fix (encode the extra value into the returned `sublevel_starts`/`edges` structure instead of instance state), but that requires rewriting every `sublevel_starts[i]` reference in both classes' `_populate_sublevel_metadata` - deferred as a real refactor rather than a mechanical fix. **Partially addressed:** `_populate_sublevel_metadata` in both classes now raises a clean `ValueError` if `baseline_std` is `None` at that point, instead of the previous silent `TypeError`-driven rejection - the underlying propagation gap above is still open, this just gives it a clean failure mode

* **Updated Data Plugins: `Basic_PeakFinder`, `PeakFinder`**
    * Fixed an empty-slice bug that wrongly rejected legitimate events ending at the trace boundary

* **Updated Data Plugin: `BesselFilter`**
    * Fixed a boundary check that allowed `Poles = 0` despite requiring a positive integer
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugins: `ChimeraReader20240101`, `ChimeraReader20240501`, `ChimeraReaderVC100`, `TCossaLabABFReader`, `LegacyElementsReader`**
    * Fixed dead filename-pattern validation code that never actually rejected malformed filenames
    * Removed a dead `config["v_offset"]` lookup in `ChimeraReaderVC100._convert_data` whose result was discarded
    * Fixed `ChimeraReaderVC100`'s class docstring saying "VC1100" instead of "VC100"
    * Fixed `_convert_data`/`_get_configs` docstrings (`ChimeraReader20240101`, `ChimeraReader20240501`, `ChimeraReaderVC100`) claiming "data is already scaled"/"no config files needed" when each actually applies a gain/offset conversion and parses a header (embedded, companion `.json`, or companion `.mat`, respectively); also fixed the same stale `_convert_data` claim in `TCossaLabABFReader`, which applies a per-channel telegraph-derived scale from the ABF2 header

* **Updated Data Plugin: `SingleBinaryDecoder`**
    * Fixed exception handling wrapped around the wrong line, leaving real file-open errors unprotected
    * Fixed the class docstring being a leftover "Chimera VC1100" description; this reader is a generic, fully user-configured binary decoder

* **Updated Database Plugins: `SQLiteDBWriter`, `SQLiteEventWriter`, `SQLiteDBLoader`, `SQLitePeakDBLoader`, `SQLiteEventLoader`, `MetaDatabaseLoader`, `MetaDatabaseWriter`**
    * Fixed several `UnboundLocalError`-masking exception handlers that hid the real database error
    * Fixed a `finally`-block bug that silently swallowed real write errors and reported success instead
    * Unused `SAVEPOINT`s are now properly released/rolled back instead of being a no-op
    * Hardened interpolated experiment/channel/index values and escaped quotes in experiment names so legitimate names no longer break queries
    * Fixed a crash on an empty query result and on a missing unfolded-level value
    * Fixed stray logging arguments that would crash the moment the log line was actually emitted
    * Fixed an overly broad exception clause that made two more specific error handlers unreachable
    * Fixed `SQLiteDBLoader.get_experiment_names`/`_ensure_event_counts` never explicitly closing their `sqlite3` connections, unlike every other method in the file
    * Fixed `SQLiteDBLoader._ensure_event_counts` never explicitly closing its cursor
    * Fixed `SQLiteDBLoader.get_empty_settings` being decorated twice with `@log`, double-logging every call
    * Fixed a warning log in `SQLiteDBLoader._load_event_data` missing an `f` prefix, logging the literal `{event_id}`/`{channel_id}`/`{experiment_id}` placeholders instead of their values
    * Fixed `MetaDatabaseLoader.load_event_data`/`query_database_directly_and_get_generator` never explicitly closing the inner generator they wrap, relying on implicit garbage collection instead of the explicit cleanup used elsewhere in this codebase
    * Fixed `SQLiteDBWriter._write_event` swallowing genuine database errors (disk full, missing row, schema mismatch, etc.) and always reporting them to the user as the misleading, hardcoded "Cannot Overwrite Existing Event"; real errors now propagate with their actual message, while a legitimate duplicate-row rejection from `INSERT OR IGNORE` still returns `False` without raising
    * Fixed `MetaDatabaseWriter.write_events` breaking out of its loop on abort before ever calling `_write_event(..., abort=True)`, unlike the parallel `MetaWriter._commit_events`; subclasses like `SQLiteDBWriter` that rely on that documented final call to roll back and close their connection on abort were never getting it
    * Fixed `SQLiteDBWriter`/`SQLiteEventWriter`'s `reset_channel` opening a `SAVEPOINT reset_channel` that was never released or rolled back - a pure no-op - and corrected both methods' docstrings, which were copy-pasted from `close_resources` and described "gracefully closing resources" for a method that actually cascades a destructive `DELETE` of the channel's rows; also documented that `reset_channel(channel=None)` does not reset all channels, since SQL `channel_id = NULL` never matches
    * Fixed `SQLiteDBWriter.close_resources`'s docstring documenting per-channel behavior even though the method ignores its `channel` parameter entirely and always closes the single shared connection
    * Fixed `SQLiteDBWriter._insert_event_data`'s docstring documenting a nonexistent `:param channel:`; documented the real `channel_db_id`/`event_db_id` parameters instead
    * Fixed `SQLiteEventWriter._write_data`'s docstring documenting a nonexistent `batch_size` parameter, and removed a stale comment claiming `executemany` batching when the method has always inserted one row per call
    * Fixed `SQLiteEventLoader._finalize_initialization` stripping `sqlite_sequence` from the table list *after* `missing_tables`/`extra_tables` were already computed, making the removal dead code; a workaround special-case papered over the common case but still misreported `sqlite_sequence` alongside any other genuinely unexpected table. Moved the exclusion earlier and simplified the now-redundant special-case check
    * Fixed `SQLiteEventLoader.get_valid_indices`'s docstring claiming an "all channels" mode when `channel` is unspecified; `channel` is actually a required parameter with no default
    * Removed `SQLiteEventLoader.get_num_events`'s unreachable `if num_events_row is None: raise ValueError(...)` (`SELECT COUNT(*)` always returns exactly one row) and the resulting dead `except ValueError` clause alongside it

* **Updated Backend Infrastructure: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`, `MetaReader`, `MetaController`, `EventWorker`, `MetaModel`, `LogDecorator`, `BaseValidator`, `QtHandler`**
    * Fixed a bug where an unexpected exception during event processing left a channel permanently unable to run again
    * Fixed a falsy-zero bug that silently dropped a legitimate chunk-boundary event start
    * Fixed a `ZeroDivisionError` in fit-progress logging that could permanently wedge a channel
    * Removed a redundant global lock now that the channel dispatcher already serializes correctly
    * App shutdown now correctly waits for worker threads to finish instead of potentially destroying a still-running thread
    * Fixed the `@log` decorator silently breaking exception handling and result logging for every generator-based method in the app
    * `BaseValidator` now properly enforces its abstract validation methods
    * Added a reentrancy guard so concurrent error/warning logs no longer stack multiple modal dialogs
    * Fixed `MetaEventFinder.__init__` resetting `self.reader` after `apply_settings`, discarding an already-configured reader
    * Fixed `MetaEventFinder.find_events` not stopping promptly when aborted mid-run: it previously kept processing every remaining range before discarding all results, instead of stopping as soon as the abort was received
    * Fixed `MetaEventFitter.fit_events` crashing with a `KeyError` when a fitter subclass returned mismatched-length sublevel-metadata arrays; the event is now cleanly rejected instead of aborting the whole channel
    * Fixed `MetaWriter._rescale_data_to_adc`'s auto-scaling fallback computing its offset from `adc_max` instead of `data_max`, which silently corrupted ADC-encoded values (mapping them far outside the valid ADC range) whenever a writer relied on this fallback instead of an explicit gain setting
    * Fixed `MetaWriter._validate_param_types` never calling `super()`, unlike every sibling override, which would have silently skipped primitive-type validation for all `MetaWriter` subclasses now that the base check actually works
    * Fixed `MetaReader.report_channel_status` always formatting the samplerate with 2 decimal places regardless of whether it was a whole number, due to a dead ternary inside the f-string's format spec
    * Fixed `MetaEventFinder._find_events_single_range`'s "drop leading orphan event-end" check being permanently dead code (a `finally` block reset the flag it depended on before the check ever ran), which silently discarded every event found in a chunk whenever the requested range started mid-event
    * Fixed `MetaController._relay_global_signal`/`_relay_data_plugin_controller_signal` logging the literal string `"str(e)"` instead of the actual exception when relaying a global/data-plugin-controller signal failed, since neither `except Exception:` clause even bound the exception to a name
    * Fixed `MetaEventFinder.report_channel_status` skipping the "Accepted ...s of data" line whenever a channel had zero rejected data (the common, fully-successful case), since it was gated on `rejected_data` being truthy instead of always showing alongside a conditional "Rejected" line
    * Fixed `MetaEventFinder.find_events` silently swallowing a `RuntimeError` from `_find_events_single_range` and continuing to the next range as if nothing happened, even though that error is only raised after `_find_events_single_range` already reset all previously-accumulated events for the channel; the error now propagates, matching how `EventWorker`'s generator-driving loop already handles and reports it. Also removed a dead, unreachable `except StopIteration` alongside it
    * Fixed `MetaEventFinder.get_event_indices` comparing its per-channel dicts to an empty list literal (always `False`, so it never raised on a fresh instance despite documenting that it should) and dropped its unused `index` parameter; docstring/rtype now describe what the method actually returns
    * Fixed `MetaEventFinder.get_single_event_data`'s docstring documenting `:raises IndexError:`, even though the method already catches that internally and returns `None`
    * Fixed `MetaEventFitter.get_metadata_columns`/`get_sublevel_columns` hardcoding `[channel][0]` to sample an event's metadata keys; since `fit_events` pops any rejected event's entry out of that dict (a routine outcome for a noisy/malformed event) and marks fitting complete regardless, a rejected event 0 specifically crashed both methods with `KeyError: 0` even though other valid fitted events remained available. Both now sample from any available entry instead

* **Updated Plugin Management: `DataPluginController`, `DataPluginModel`, `BaseDataPlugin`**
    * Fixed `BaseDataPlugin._validate_param_types` never actually validating primitive setting types (a broken `isinstance` check made it dead code for every data plugin); `DataPluginController.validate_and_instantiate_plugin` now also resets a resolved plugin-dependency setting's `Type` to `None` (matching `edit_plugin`), so the fixed check correctly skips resolved plugin references instead of rejecting them
    * Fixed `BaseDataPlugin.apply_settings` registering plugin parent/dependent relationships under the wrong metaclass name for any plugin that subclasses another concrete plugin instead of its `Meta*` base directly (e.g. `BoundedBlockageFinder`/`ThresholdBlockageFinder` via `ClassicBlockageFinder`, `IntraCUSUM` via `CUSUM`): it used the plugin's immediate Python base class instead of its true metaclass, which could crash deletion of an unrelated plugin with a `KeyError` naming a class that was never even instantiated in the session
    * Fixed `DataPluginController.delete_plugin` never removing the deleted plugin's entry from `plugin_history.json`, unlike every other plugin-mutating operation, which left stale/deleted plugins persisted across app restarts
    * Fixed `DataPluginController.edit_plugin` unregistering a plugin as a dependent from all of its parents up front, before knowing whether the edit would succeed, and never restoring that link on any abort path (rename collision, a `set_key`/settings-resolution/`apply_settings` failure, or a delete blocked by dependents), even though the plugin instance and its actual parent usage were unchanged
    * Fixed `DataPluginController.edit_plugin`'s docstring documenting a nonexistent `subclass` parameter, leaving the real `key`/`settings` parameters undocumented, and claiming it raises on "unable to instantiate the plugin" - a description that doesn't match either its purpose (editing, not instantiating) or its actual design (failures are caught internally and reported via `add_text_to_display`/`logger`, not raised)
    * Fixed `DataPluginModel.update_plugin_key` silently overwriting (and orphaning) any plugin already registered under the destination key, with no existence check beforehand; it now refuses the rename and logs an error instead. Also corrected this method's and `register_plugin`'s/`get_temp_instance`'s docstrings, which variously claimed a `ValueError` or `NotImplementedError` that never happens, were stale copy-pastes of an unrelated method's params, or omitted the real `KeyError` these methods actually raise
    * Fixed `DataPluginController.set_settings`/`update_data_server_location` each having the other's docstring (a getter description on what are both actually setters)
    * Fixed `DataPluginModel`'s class docstring calling it a "controller"

* **Updated App Shell: `MainController`, `MainModel`, `MainView`**
    * Replaced a hardcoded institution-specific network path default with the user's home directory
    * A corrupted config file now regenerates defaults on startup instead of crashing the app
    * `JsonDefaultSerializer` now also handles `Enum`, `datetime`/`date`, and `set`/`frozenset` values instead of only `PurePath`
    * All config file writes in `App`/`MainModel` are now wrapped in error handling instead of letting a write failure crash the app
    * Fixed a missing comma in `MainController`'s `config_path` construction that silently concatenated `".."` and `"configs"` into a single path segment (currently harmless, since nothing reads `config_path`)
    * `MainController.previous_plugin_history` is now always initialized to a dict instead of only being set when a prior session exists, removing a fresh-install code path that relied on a caught `AttributeError` in `get_settings_from_history`
    * Fixed `MainController.handle_global_signal` silently swallowing, with zero logging, any exception raised by its `func(None)`/`return_function(None)` fallback calls (used when the primary call raises a `TypeError`), via a bare outer `except Exception: pass`; it now logs the real error
    * Fixed `MainController.send_curent_data_server`/`send_curent_user_plugin_location` being decorated `@Slot(str, str, object)` despite taking no parameters and being connected to parameterless `Signal()`s, a stale signature apparently copied from `get_plugin_instance`
    * Fixed `MainModel.populate_available_plugins`'s `try/except` around `os.walk(base_path)` being dead code (`os.walk` is a lazy generator that never raises, even for a missing directory), which meant an invalid plugin directory (e.g. a `User Plugin Folder` that hasn't been created on disk yet) silently contributed zero plugins with no diagnostic instead of logging the intended warning; replaced with an explicit directory-existence check. Also fixed `clear_cache`'s docstring documenting nonexistent `filepath`/`timeout` parameters and describing deletion/waiting behavior it doesn't have (it synchronously truncates the fixed `app.log` file)
    * Removed a dead `except ValueError` branch in `MainController.load_session` that special-cased a `"...already exists globally"` message `validate_and_instantiate_plugin` never actually raises (that method swallows all of its own failures internally and just logs/emits/returns); collapsed to a single `except Exception`, which already covers the same restore-and-continue behavior
    * Added class-level docstrings to `MainController`, `MainModel`, and `MainView`, and method docstrings to `MainController.handle_global_signal`/`handle_data_plugin_controller_signal`, none of which had any despite being the app's central signal-dispatch entry points

* **Updated Frontend Base Class: `MetaView`**
    * New `plugin_state_changed` signal and abstract `notify_plugin_state_changed` hook, allowing any tab to notify all other tabs when a plugin instance's state changes (e.g. new columns added to a database). Every `MetaView` subclass must now implement `notify_plugin_state_changed`, even if the correct implementation is to do nothing. Non-trivial implementations must determine whether the notification is relevant to that tab, and filter and react accordingly.
    * Removed a stray, uncallable leftover `add(a, b)` method

* **Updated Frontend Widgets: `IntegerRangeLineEdit`, `CommaFloatRangeLineEdit`, `FloatRangeLineEdit`, `FloatRangeValidator`, `DictDialog`, `MultiSelectComboBox` (`multiselect_filter.py`)**
    * Fixed `IntegerRangeLineEdit`/`CommaFloatRangeLineEdit` silently mis-parsing or truncating ranges containing an extra `-` (e.g. a leading minus sign or a stray third number); these fields only ever represent times or event indices, both non-negative, so a leading `-` is now rejected outright instead of ambiguously parsed
    * Fixed `FloatRangeLineEdit` crashing with an `AttributeError` on any invalid or empty input (e.g. the Raw Data tab's start-time field): unlike its sibling widgets, it never defined a `logger`, so every validation error path crashed instead of just logging
    * Fixed `DictDialog`'s hidden Input File/Output File/Folder "has a value" checkbox always starting unchecked regardless of whether the plugin being edited already had a valid path, permanently disabling OK on an already-configured plugin until the user re-ran the file picker just to change some unrelated field
    * Fixed `FloatRangeValidator` inflating a bare-integer end value (e.g. `"2"` → `"20"`) to guess whether more digits were coming, then using that inflated value for the start/end ordering check; an inverted integer range like `"10-2"` slipped past the check and was silently accepted and stored backwards, while the equivalent decimal range was correctly rejected
    * Fixed `MultiSelectComboBox.addItems` (filter variant) never refreshing the "Select All"/"Deselect All" button text or summary line-edit after repopulating, unlike the sibling `multiselect.py` widget
    * Fixed `MultiSelectComboBox`'s (filter variant) outside-click handler closing the popup but still falling through to `super().eventFilter(...)` instead of returning `True`, so the dismiss-click also reached whatever widget sat underneath it
    * Removed `_edit_button_clicked`/`_delete_button_clicked`, two dead methods (filter variant) superseded by the already-working `edit_filter`/`delete_filter` callback chain; `_edit_button_clicked` referenced a never-defined `self.on_edit_filter`, and `_delete_button_clicked` duplicated logic already correctly implemented in `MetadataView`/`ProteinView`

* **Updated Frontend Controls: `RawDataControls`, `EventAnalysisControls`, `ClusteringControls`, `MetadataControls`, `ProteinControls`**
    * Fixed `MetadataControls`/`ProteinControls` crashing when the bins field ended in a trailing comma
    * Removed the duplicated, uncallable `get_nested_value`/`get_plugin_data` helper methods (missing `self`, never called in production) from all five `*controls.py` files, along with their two dedicated unit test classes

* **Updated Frontend Infrastructure: Walkthrough**
    * Fixed the walkthrough's transparent "Analysis" menu highlight overlay leaking whenever a milestone dialog was dismissed manually (X/Done) instead of by navigating to the expected next view; cleanup now runs on both paths
    * Fixed the walkthrough's auto-advance polling loop continuing to reschedule itself after the walkthrough dialog was manually dismissed, risking a duplicate/late call into the completion handler if the tracked view was later revisited

* **Updated Frontend Plugins: `MetadataView` and `ProteinView`**
    * Replaced per-click DB queries with a cached event_id list and bisect-based navigation.
    * Previously, the forward/backward arrows shifted the "Event Index" field by a fixed step across the full database, with no awareness of any active filter. This made systematic inspection of filtered events tedious (there was no way to know how far to step to reach the next populated range, and the number of events plotted per step varied unpredictably depending on that range).
    * The old range field has been replaced with two new fields:
        * **Event ID** — snaps to the nearest filtered event at or after the requested ID
        * **# Events** — controls how many filtered events to display starting from that point
    * Forward/backward arrows now move through the filtered set directly, with wrap-around at both ends, so the subplot count is predictable and navigation stays filter-aware.
    * The display panel now shows the first and last event IDs in the filtered set, so users always know where they are.
    * Example: if only event_ids 2, 5, 8, 9, 12, 15 pass a filter (out of 15 total events), entering event_id=3 with # events=2 snaps to event_id 5, plots events 5 and 8, updates the Event ID field to 5, and displays "Filtered events: 6 total | first event_id: 2 | last event_id: 15". Clicking forward moves to event_id 9 and plots events 9 and 12 — always within the filtered set, never jumping over empty ranges.
    * Fetching and snapping is now O(1), a major speedup over the previous worst-case behavior.
    * Filter state (filter name and subset label) is now reflected directly in the display panel message.

* **Updated Frontend Plugin: `MetadataView`**
    * Fixed: some plot types (Categorical Histogram, Scatterplot, Raw/Filtered Event Overlay) failed to render after "Plot Events" + "Update Plot" due to a stale `self.axes` reference not caught by existing staleness check. Added `_axes_valid()` to detect and reset it properly.
    * Fixed: Silent crash in `_export_csv_subset` when the "Export Settings" dialog was canceled. Canceling the dialog now backs out cleanly.
    * Now refreshes its available column list automatically when another tab commits new columns to the currently selected database.
    * Fixed: `ZeroDivisionError` when constructing an event overlay from events that all have the same length
    * Fixed: crash when formatting an axis label for a column with no defined unit
    * Fixed: an unhandled plot type could leave plotting data unbound instead of raising a clear error
    * Fixed: a typo left stale event markers on the plot after a failed feature lookup
    * Removed a dead, exact-duplicate code block in all-points-histogram construction
    * Fixed `MetadataControls` DB Loader edit/delete buttons staying enabled when no database was loaded (placeholder text mismatch)
    * Fixed `MetadataControls` computing bins-field validity but never actually using it to enable/disable **Update Plot**
    * Fixed `MetadataControls.validate_inputs`'s bins-field validation always requiring whole numbers even when "Sizes" was checked (which expects decimal bin edges), disabling **Update Plot** for exactly the kind of value the field's own placeholder asked for

* **Updated Frontend Plugin: `ProteinView`**
    * Added a **RAW** checkbox to event plots, matching `MetadataView`: raw traces are shown before fitting, and included alongside fitted results once fitting is complete
    * Removed the Undo and Reset buttons from the Protein Tab
    * Fixed: `hist_min`/`hist_max` persisted across "Plot Histogram" calls and only ever expanded, so bin edges (and resulting histogram shape/fit) depended on plotting order and history instead of the event itself. Per-event histogram binning is now deterministic, and thus, so is plotting.
    * Fixed: Commit silently crashing every time due to a broken plugin-list refresh chain (the DB write itself still succeeded, so the crash went unnoticed). Replaced with a direct `update_available_columns(loader)` call. Removed dead code.
    * Committing now notifies other open tabs, so newly added columns appear immediately in any tab currently displaying that database.
    * Updated Walkthrough instructions. 
    * New **Report All** button in Ensemble mode: displays the double-Gaussian fit parameters (peak amplitude, mean, std) alongside the binning configuration that produced them, plus median ± std summaries of Prolate and Oblate V, a, b, and m from the Monte Carlo sample. Display-only, since Ensemble mode has no per-event id to write a database row against (replaced Commit All button).
    * New: Individual and Ensemble modes now use fully independent canvases for the histogram and V/M plots. Switching modes immediately shows that mode's last-drawn plot with no need to click Update Plot again, and no longer overwrites or erases the other mode's plot and data.
    * Updated: Reset previously cleared fit state for both Individual and Ensemble modes unconditionally, regardless of which mode was active. Reset is now scoped to the currently selected mode only, and the display panel confirms which mode's fit was cleared.
    * New: Running Update Plot in one mode could silently wipe out a valid fit stored in the other mode, causing "No ensemble fit available to report" even when a fit had been successfully computed earlier in the session.
    * Fixed: Clicking Commit Individual with no fit computed raised an unhandled `AttributeError` that was silently swallowed by the Qt event loop, giving no feedback in the UI. Now shows a clear message in the display panel.
    * Fixed: Some validation were passing an extra positional argument to `logger.warning`, crashing before the warning was ever shown.
    * Fixed: Leaving the **N** field blank in Ensemble mode raised a `ValueError` instead of falling back to a default, matching behavior already present in Individual mode.
    * Fixed: Default **N** value was set to 100 in the backend and 1000 in the frontend. Updated frontend to match the backend value.
    * Added Freedman-Diaconis auto-binning for per-event histograms
    * Fixed: zero-baseline divisions silently propagating NaN/Inf into histograms and fits
    * Added a hard cap to a previously-unbounded Monte Carlo sampling loop that could block the UI indefinitely
    * Fixed: plugin-list refresh crashing due to calling `.emit()` on a non-`Signal` method
    * Refactored `_update_distribution_ensemble`'s ~105-line double-Gaussian fit and Monte Carlo sampling block into its own method, `_fit_and_plot_ensemble_geometry`, called once after the loop finishes instead of relying on a comment plus careful indentation to stay safe if the surrounding experiment/channel/filter guards are ever relaxed
    * Fixed `ProteinControls.is_placeholder_item` checking for `"No Database"` instead of the actual `"No Event Database"` placeholder, which left the DB Loader edit/delete buttons wrongly enabled with no database selected
    * Fixed `_commit_fits` not aborting when the user clicked Cancel on the "Confirm Overwrite" dialog, falling through to commit the new fit columns anyway; also added the missing `ProteinController.check_column_exists`, without which the dialog could never appear in production at all (the return-callback name it relied on didn't match any real method, so the existing-column check silently never ran)
    * Fixed the `ProteinView` class docstring, still the literal unfilled placeholder `"Subclass of MetaView for TBD / Attributes: TBD"`
    * Fixed `ProteinModel`'s class docstring being a copy-paste of `MetadataModel`'s (described metadata processing, not protein volume/shape-factor fitting)

* **Updated Frontend Plugin: `ClusteringView`**
    * Fixed: Commit silently crashing every time due to a broken plugin-list refresh chain (the DB write itself still succeeded, so the crash went unnoticed). Replaced with a direct `update_available_columns(loader)` call. Removed dead code.
    * Committing now notifies other open tabs, so newly added columns appear immediately in any tab currently displaying that database.
    * Fixed: clicking Cancel on the cluster-overwrite confirmation dialog did not actually cancel the commit
    * Fixed: an unrecognized clustering method crashed with an unbound-variable error instead of a clear message
    * Fixed: `ZeroDivisionError` in baseline stats on a flat/constant data chunk
    * Fixed Gaussian Mixture clustering fitting on data that still included the `id` column, unlike HDBSCAN which already excluded it; `id`'s arbitrary, unnormalized magnitude could dominate the fit and produce meaningless clusters
    * Fixed `ClusteringSettingsDialog.remove_column_item` never refreshing the Apply-button/warning state after deleting a dynamic column row, unlike every other mutation path in the widget; deleting the row causing a validation warning left Apply stuck disabled until some unrelated widget happened to trigger a refresh
    * Added a missing docstring to `ClusteringController.display_write_status`

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed: `ZeroDivisionError` in baseline stats on a flat/constant data chunk; now logs a warning and skips just that channel's overlay instead of crashing the whole plot
    * Fixed: power spectral density calculation crashing or silently producing NaNs on very short channels
    * Fixed `RawDataModel.integrate_noise` crashing "Update PSD" with an uncaught `IndexError` when a short time window made `welch()` return a single-frequency-bin PSD
    * Fixed `RawDataModel`/`RawDataController`/`RawDataView` PSD calculation silently mislabeling a surviving channel's PSD under the wrong channel name whenever an earlier channel was skipped
    * Fixed a log message missing an `f` prefix (another instance of the same bug was fixed in `EventAnalysisView`), so the intended values were never actually interpolated
    * Fixed `_get_baseline_stats`'s docstring documenting a `tuple[float, float]` return, missing the local amplitude that's actually the first of three returned values
    * Fixed `RawDataController.update_channels` being decorated `@Slot(dict)` and documented as taking a `dict`, despite always being called with a `List[int]` of channel identifiers
    * Added missing docstrings to `RawDataController.update_available_plugins`/`update_plot_data`

* **Updated Frontend Plugin: `EventAnalysisView`**
    * Fixed: crash when zero channels were selected while shifting or plotting events
    * Fixed: a failed event load could silently reuse stale data from a previous event
    * Fixed: a typo left stale event markers on the plot after a failed feature lookup
    * Fixed `eventAnalysisControls.py` inserting `"No EventFitter"` into the fitter combo box while everything else checked for `"No Event Fitter"`, so the "no fitter selected" guard never fired and Fit Events could silently target a nonexistent plugin key; `validate_inputs` now also disables **Fit Events** when no real event fitter is selected, matching the loader/writer checks
    * Fixed `_start_eventfitter` re-raising a filter-loading failure instead of falling back gracefully like `_handle_plot_events` already does, so a broken/misconfigured filter crashed Fit Events instead of proceeding without one
    * Fixed `_start_eventfitter` returning out of its whole channel loop when the user clicked "No" on one channel's "already fitted" confirmation dialog during a multi-channel fit batch, silently cancelling fitting (and dropping any already-queued generators) for every remaining channel instead of just skipping that one
    * Fixed `_extract_plot_event_parameters`'s docstring documenting a 4-tuple return, omitting `loader` from the real 5-tuple
    * Fixed `EventAnalysisController.update_channels` being decorated `@Slot(dict)` and documented as taking a `dict`, despite always being called with a `List[int]` of channel identifiers
    * Added a missing docstring to `EventAnalysisController.update_available_plugins`
    * Fixed `_update_event_plot` accepting a `use_raw` parameter but never referencing it; the raw-trace overlay toggle worked only by accident, because the caller happened to already omit "Raw"-labeled entries from `event_data`/`labels` when raw wasn't requested. The method now explicitly skips any "Raw"-labeled entry when `use_raw` is False, matching how `MetadataView`'s equivalent method actually gates its raw-trace overlay

* **Updated Frontend Component: `MainView`**
    * Fixed: Sidebar highlighting (icon and text menus) did not update when an analysis tab was opened via the top menu bar (Analysis → New Analysis Tab) or via the "Add" dropdown menu — the previously active tab's button stayed highlighted instead of switching to the newly opened tab.
    * Fixed: Selecting Raw Data, Event Analysis, or Metadata from the "Add" dropdown did not highlight their dedicated sidebar button.
    * Fixed: The "Add" dropdown menu reopened immediately after selecting an item, due to a duplicate signal connection 
    * Fixed menu bar action icons silently failing to render due to an incorrect resource path (bug was invisible until now, since it failed silently)
    * Fixed the "All Analysis Tabs" dropdown menu always opening anchored at the main window's top-left corner instead of near the clicked button, since `populate_plugins_menu` read `self.sender()` after an async round-trip where it always resolved to `MainView` itself
    * Fixed `add_page` leaking an orphaned wrapper `QWidget` into the stacked widget every time a page name was reused (e.g. every time Settings was opened), instead of reusing/removing the previous wrapper
    * Removed `display_data`/`on_file_loaded`, two dead methods with zero callers anywhere in the app or tests; `display_data` referenced a `self.rawDataWidget` attribute that was never assigned, and its target (`RawDataView.display_data`) doesn't even exist under the current per-tab plugin architecture

* **Updated Frontend Component: `Settings`**
    * Settings window now follows OS light/dark mode automatically, and updates live if the OS theme changes while the app is open, no restart required
    * Fixed dropdown menus (combobox popups) rendering with a stray focus outline, a disappearing selection highlight on hover, and a double-border artifact
    * Application version in the About tab is now pulled from `poriscope.constants.__VERSION__` instead of a hardcoded string, so it can no longer drift out of sync
    * Fixed potential crash (`AttributeError`) if a folder-picker button was clicked before the data server / user plugin location had been set
    * Fixed the Logging Level combobox always opening at "None" regardless of the actually-configured level, since nothing ever pulled the real persisted value back into the widget (unlike Data Server/User Plugin Location's folder-picker seeding); added the same round-trip pattern (`MainModel.get_logging_level`, `MainController.send_curent_logging_level`, `MainView`/`SettingsWindow` relay plumbing) so opening Settings now shows the level that's actually active

* **Updated Utility: `get_icon` (`poriscope.configs.utils`)**
    * Icons now automatically recolor for light/dark mode instead of requiring separate hardcoded black/white icon files
    * New `get_themed_icon_path` helper for cases (like custom stylesheet arrows) that need a real file path rather than an icon object
    * Removed unused legacy icon assets and the broken/unused Qt `.qrc` resource system (`resources_rc.py`), which nothing in the app actually depended on
    * Standardized edit/add icons across control panels to use the same icon set consistently

### General Fixes and Improvements:
* Updated tests in `test_main_controller.py`, `test_classic_cusum.py`, `test_no_fitter.py`, and `test_meta_event_finder.py` to match already-landed fixes (RPC dispatcher log-and-return behavior, corrected `ClassicCUSUM` threshold sensitivity, corrected `NoFitter` duration/extreme-value index alignment, and a dead-code precondition fix in `get_event_data_generator`) that had left their expectations stale
* Fixed placeholder combobox text (`"No Reader"`, `"No Eventfinder"`, `"No Loader"`, `"No Event Database"`, etc.) routinely reaching `global_signal.emit(...)` as if it were a real plugin key, flooding startup/session-restore with failed lookups. Root causes: (1) several `update_X(items)` combobox-population helpers across the `*controls.py` files mutated the *caller's* list in place to insert the placeholder (`items.insert(0, "No X")`), which in `RawDataView.update_available_plugins` leaked the placeholder into a loop that treated it as a genuinely new plugin; (2) `RawDataView`/`EventAnalysisView._handle_other_actions` and `ClusteringView`/`MetadataView`/`ProteinView`'s `update_available_columns`/`request_experiment_structure` used truthy-only checks (`if reader:`) that don't filter out the non-empty placeholder string. Combobox helpers now build a local display list instead of mutating the parameter, and all affected call sites now guard against the specific placeholder value
* Replaced deprecated `set_constrained_layout(True)` calls with `set_layout_engine('constrained')` across `ClusteringView`, `EventAnalysisView`

## Poriscope 1.6.1: 2026-06-04

* **Bug hotfix
    * Fixed plotting bugs with `Peakfinder` plugin families

## Poriscope 1.6: 2026-06-04

### What's New since Poriscope 1.5:
    
* **PyPi integration**
    * Poriscope is now available on PyPi and can be installed with `pip install poriscope`
    
* **Updated Data Plugin Base Class: `MetaDatabaseLoader`**
    * Replaced N×M `COUNT(*)` query loop in `report_channel_status` with a `event_counts` summary table, making DB loading and experiment/channel count reporting ~10x faster.  
    * The `event_counts` summary table is maintained automatically via SQLite triggers in case of manual edits (event removal)
    * Backwards compatible — existing databases are upgraded automatically on first load
    * Added template for `get_plot_features()` function that can be implemented by subclasses that want to visualize data printed by specific `MetaEventFitter` subclasses
    
* **Updated Data Plugin Base Class: `CUSUM`**
    * Fixed numerical bug that was causing underestimates of sublevel transition probabilities
    * Fixed numerical bug that was causing shallow steps to be accepted when they should not have been
    * Reverted threshold loop to exact port of original C code implementation
    * Added new parameter Sensitivity to allow greater fine-tuning of step detection

* **Updated Data Plugin Base Class: `Peakfinder`**
    * Redefined sublevels by regions relative to peak flanks
    * Added new metadata to calculate peak mean blockage
    * Added settings for peak filtering fine-tuning
    * Fixed peak numbering relative to new sublevel definition
    * Fixed current direction dependance problem for peakfinding function
    
* **Updated Frontend Plugin: `MetadataView`**
    * Added **RAW** checkbox to the Plot Events section — raw data is always shown before fitting; once fitting is complete, checking RAW includes raw traces alongside the fitted results
    * Full SQL will always be printed after filter creation/editing, regardless of validity
    * Added the loader to both the legend label and the duplicate-check key so plots from different loaders are treated and displayed as separate datasets allowing for different loaders with the same experiment name to be overlayed.
    * Added **RAW** checkbox to the Plot Events section — when checked, raw data traces are included alongside filtered and fitted traces in event plots
    * New plot type: Categorical Histogram that plots bar charts of data counts for unique values of the specified database column
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    * Two event filter modes: **Assisted SQL** (WHERE clause only, Poriscope builds the query) and **Raw SQL** (complete SELECT statement, executed directly). Raw mode enables aggregations, computed columns, and subqueries not possible in assisted mode. See *Filtering and Querying* in the documentation. `ProteinView` brought to parity with MetadataView. 

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed bug causing float drift in trace navigation 

* **Updated Frontend Plugin: `ClusteringView`**
    * Increased size of color palette cycle when plotting large numbers of clusters
    * Increased markers size when plotting

* **Documentation**
    * Fixed missing method documentation in all `MetaView` subclasses caused by unresolved PySide6 imports at Sphinx build time
    
* **New Frontend Plugins: `ProteinView`/`ProteinController`/`ProteinModel`**	 
    * Allows fitting, visualization, and postprocessing of the Mayer model to protein volume and shape factors
    
* **New Data Plugin: `ClassicCUSUM`**	 
    * Reverts Step Size to being a multiple of the local baseline standard deviation instead of an absolute number
    * Ported bug fixes from base CUSUM class
    
* **New Data Plugin: `ClassicBlockageFinder`**	 
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    
* **New Data Plugin: `BoundedBlockageFinder`**	 
    * Fixed bug with baseline fitting that caused off centered fit when baseline drift was present
    
* **New Data plugin: `SQLitePeakDBLoader`**
    * Subclasses SQLiteDBLoader to add specific plotting features used by the `PeakFinder` plugin - only usable on databases created by `PeakFinder`
    
* **New Data Plugin: `Basic_Peakfinder`**	 
    * Stable release of basic and minimal peak finding features

### General Fixes and Improvements:
* Fixed bug with baseline calculation that was causing inaccurate baseline whenever drift was present
* Fixed crash when resetting or updating heatmaps in the Metadata tab
* Bin and size changes now trigger correct overlay replotting when clicking "Update Plot"
* Cross-table filtering is now supported for events plot filtered by sublevels column, and sublevels plot filtered by events column.
* Fixed float-to-index rounding drift in PeakFinder and NanoTrees 
* Added strict runtime length check in MetaEventFitter so any mismatch now fails immediately and loudly instead of silently propagating to plotting or downstream logic
* Fixed plugins' settings not being able to be edited 
* Single shared legend from all axes in the EventAnalysis Tab to prevent overlapping and sublplots shifting
* Fixed "Update Plot" not working after "Plot Events" due to stale figure state and tracking variables not being reset
* Select all items by default in MultiSelectComboBox
* Auto-select newly added filter to match reader's, loader's and writer's combobox population behavior

Disclaimer: As of version 1.6.0, Poriscope has experimental Linux support and is primarily tested through an Ubuntu virtual machine environment.

## Poriscope 1.5: 2025-12-08

### What's New since Poriscope 1.4:
* **linting and unit tests**
    * repository now runs sanity checks before allowing commits
    
* **workflow script**
    * Example script showing implementation of a "one-click" poriscope workflow added to the repository
    
* **pip integration**
    * Poriscope now includes setup.py and can be installed as a pip package
    
* **Tutorial Updates**
    * Tutorial now includes `ClusteringView`
    * Users can now add a walkthrough to their own plugin by inheriting from WalkthroughMixin.
        * For detailed instructions, see the documentation: User Manuals/Next Steps/Adding a Walkthrough.
        
* **Documentation Updates**
    * Data plugin creation tutorial and documentation added
    * scripting workflow example tutorial added
    * General improvements to cross-referencing within the documentation
    * **NOTE** to build and view docs, run `python scripts/hooks/post-merge-run_autodoc_pipeline.py` in  the top level repository folder

* **Updated Data Plugin Base Class: `MetaDatabaseWriter`**
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag

* **Updated Data Plugin Base Class: `MetaEventWriter`**
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **Updated Data Plugin Base Class: `MetaEventFinder`**
    * Now allows finding of events in a series of disconnected chunks with a single progressbar over all chunks
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **Updated Data Plugin Base Class: `MetaEventFitter`**
    * Enforce that sublevel_duration exist in the database and force crash during event fitting if it does not
    * All generators can now be aborted early to force axhaustion by sending in a boolean flag
    
* **DEPRECATED Data Plugin: `BinaryEventLoader`**
    * Per last release notes, `BinaryEventLoader` has been deprecated and is no longer available
    
* **Updated Data Plugin Base Class: `MetaDatabaseLoader`**
    * Updated load_event_data to also return padding before and padding after. 
    * Updated all metadata and data loading functions to take optional channel and experiment lists as arguments to unify SQL query construction logic
    * Columns in the experiments table are now included in the query builder
    * **DEPRECATED**: export sqlite subsets no longer works, in favor of persistent subset filters

* **Updated Frontend Plugins: `RawDataView`, `EventAnalysisView`,  `ClusteringView`, `MetadataView`**
    * Control panels now have a “delete” button next to the edit button in each view. This allows users to delete the currently selected plugina s long as it does not have dependent plugins
    * Change all long-running tasks that generate progress bars to allow cancellation regardless of serial or parallel status by moving abort functions to the data plugins
    * Plugin names can now be edited
    
* **Updated Frontend Plugin: `MetadataView`**
    * Complete overhaul of control panel
    * Subset and sql filters are now persistent objects that can be saved and reloaded
    * **DEPRECATED**: export sqlite subsets no longer works, in favor of persistent subset filters
    * Subsets can now be automatically segregated by experiment and channel id independent of other filters applied using the Scope button
    * Events can now be plotted directly in the view
    * You can now set bins either by size or counts
    * When plotting multiple overlaid histograms, bins will adjust to match across subsets
    * Enforces single exp/channel selection for event plots, which allows event_id to be used instead of global_id to identify events for plotting
    
* **Updated Frontend Plugin: `RawDataView`**
    * Added the option to calculate and plot the baseline stats on the raw data panel
    
* **Updated Frontend Plugin: `EventAnalysisView`**
    * Event plot line and  point elements now cycle through the matplotlib color cycle
    
* **Updated class structures**
    * Miscellaneous changes to data plugin base classes to explicitly include all required abstract methods in metaclasses for ease of subclass creation
    
* **Updated repository management**
    * Now includes pre-commit checks for code quality, linting, and proper type hinting
    * Post-merge pipeline updated to account for docs updates

### General Fixes and Improvements:
* **Click outside the pop-up or the x button in the selection menus (compatible with MacOs and Linux)**
* **Append SQL-like filters instead of overriding when loading a new .json file in the Metadata tab**

## Poriscope 1.4: 2025-06-09

### What's New since Poriscope 1.3:


* **Updated Data Plugins: `SQLiteEventLoader` and `SQLiteDBLoader`**
    * Now sanity checks database schema for expected tables and rejects initialization if it is non conformant
* **Updated Data Plugin: `IntraCUSUM`**
    * Now inherits from `CUSUM` instead of `MetaEventFitter` to allow common functionality to be preserved
* **Updated Data Plugin: `BoundedBlockageFinder`**
    * Now inherits from `ClassicBlockageFinder` instead of `MetaEventFinder` to allow common functionality to be preserved
* **Updated Data Plugins: `SQLiteEventWriter` and `SQLiteDBWriter`**
    * Implemented "close_resources".
* **Updated Base Classes: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`**
    * Allows base class settings key to have child plugin base class anywhere in the inheritance chain to allow for serial subclassing of data plugins
* **Updated Base Classes: `MetaEventFinder`**:
	* Allows for segments of the file to be analyzed as specified by comme-delimited list
* **Updated Base Class: `MetaDatabaseLoader`**
    * Metadata requests now return the id column to allow cross-referencing after querying
    * Now allows new columns to be written to existing database tables while preserving cross-table relationships
    * Now corrects for redundant column requests when attempting to plot event_id and will remove redundant columns from returned data
	 
* **Updated Frontend Plugins: `RawDataView` and `EventAnalysisView`**	 
    * Next and previous arrow buttons added to frontend to simplify flipping through data, events, and fits
* **Updated Frontend Plugin: `MetadataView`**	 
    * Now allows plotting of event_id and gracefully handles missing units in metadata databases
	* Now allows independent setting of x and y bin counts using a comma-delimited list. Extra entries beyond those needed are ignored. 
* **Updated Frontend Plugin: `EventAnalysisView`**	 
    * Now allows plotting of vertical and horizontal lines and points by coordinate on top of fitted events

* **Updated Frontend Base Classes: `MetaView`**	 
    * added a signal to cause plugin instantiation from analysis tabs
	 
* **New Frontend Plugins: `ClusteringView`/`ClusteringController`/`ClusteringModel`**	 
    * Allows HDBscan and Gaussian Mixtures clustering of arbitrary subsets of data, merging of clusters, and addition of cluster columns to sql databases of event metadata
	 
* **Logging Behavior Update**
    * logging at level "info" will now not print entry and exit points, only non-critical but potentially user-useful information to the console without blocking. Other logging level behaviors unchanged. 

* **New Feature: Sphinx Documentation**
    * Full plugin and base class documentation is now included using Sphinx.
    * Users can explore architecture, plugin structure, and extension workflows directly from the docs.
    * Plugin development guide 1.0 included. 

* **New Feature: Automation Scripts and Setup Hooks**
    * Scripts are now included to auto-generate Sphinx documentation.
    * Setup hooks allow backend commands to be automatically run during initial project configuration or environment setup.
 
* **Updated Frontend Plugins: `RawDataView`, `EventAnalysisView`,  `ClusteringView`, `MetadataView`**
    * Control panels now have a “+” button next to the edit button in each view. This allows users to instantiate the corresponding  metaclass plugin directly, without needing to access the top bar menu.
	* Frontend plugins now have tutorials that walk you through the use cases
	
* **Updated Frontend Plugin: `RawDataView`**
    * Control panel now has backward and forward arrows for "Plot Events".
    * Removed "Include" and "Exclude" events buttons from the control panel.

* **Updated Frontend Plugin: `MetadataView`**
    * Removed "New Axis" button.
    * Changed "Overlay" to "Update Plot".

* **Updated Event Finding Time Limits: `RawDataView`**
    * Takes comma delimited int/float ranges
    * Finds events for each of the ranges
    * Goes from any intermediate value to zero by doing: x-0

 **Tutorial: `MainView`,`RawDataView`, `EventAnalysisView`, `MetadataView`**
    * An interactive tutorial can be triggered from the Help menu (Help->Tutorial)
    * The tutorial walks you through all the components of the Tabs listed above
    * It can be triggered at any point or closed.

* **Main app updates**
	* App now defines a user plugin folder that will be searched for valid plugins at runtime and can be changed in settings
	* App will recognize imports relative to either the `app` folder, or the `[[user_plugin]]` folder, where `[[user_plugin]]` must be replaced with whatever the actual name of your user plugin folder is.

 **Tutorial: `ClusteringView`**
    * The tutorial has been extended to include ClusteringView.


## Poriscope 1.3: Released 2025-05-21

### What's New since Poriscope 1.2:

* **New Data Plugin: `MetaEventWriter` subclass `SQLEventWriter`**
    * Stores raw data in SQLite database format.
* **New Data Plugin: `MetaEventLoader` subclass `SQLEventLoader`**
    * Loads data from `SQLEventWriter` databases
* **New Data Plugin: `MetaEventFitter` subclass `PeakFinder`**
    * Allows extraction of peaks that do not reach steady states.
	* new function get_plot_features that allows x and y values to be highlighted as features of interest for plotting
* **New Data Plugin: `MetaEventFitter` subclass `IntraCUSUM`**
    * Allows for counting threshold crossings if necessary.
* **New Data Plugin: `MetaEventFinder` subclass `BoundedBlockageFinder`**
    * Allows users to specify valid baseline limits for event finding.
* **Updated Data Plugin: `MetaEventFitter` subclass `NanoTrees`**
    * Now is able to run safely in multiple threads

* **New Frontend Plugin: `Clustering` tab**
    * Has been added.
* **Updated Frontend Plugin: `MetadataView`**
    * Allows export of subsets into human-readable CSV format.
* **Updated Frontend Plugin: `RawDataView`**
    * Allows specification of time limits for event finding.
* **Updated Frontend Plugin: `EventAnalysisView`**
    * Now allows plotting of horizontal and vertical lines on plots to highlight features of interest

### Deprecated:

* `BinaryEventWriter` has been removed to enforce consistent file formats internally.

### Notice of Future Deprecation:

* `BinaryEventLoader` will be deprecated in a future release. Please convert any datasets written with BinaryEventWriter to the new SQLEventWriter before the next release. 

### Optimization:

* `SQLEventWriter` has been heavily optimized for speed.
* `SQLDBWriter` has been heavily optimized for speed.

### Metaclass Update:

* **`MetaEventLoader` and `MetaEventWriter`**
    * Have had updates to their interface to change the structure of databases.
* **`MetaDatabaseWriter`**
    * Now enforces inclusion of raw data, filtered data, and fitted data in the database.
    * Allows writing from plugins with different metadata to the same common database.
    * *Note: Missing values will be null.*
* **All Data Metaclasses**
    * Can now enforce serial channel operations through a flag if necessary.
    * Metaclasses that create generators that are operated on by the GUI (these being `MetaEventFinder`, `MetaEventFitter`, and `MetaEventWriter`) now allow internal early abort of the generator through provision of a flag to the generator.

* **All Frontend Metaclasses** 
    * Now set an abort Boolean and allow abort and cleanup to be handled internal to the plugin, which fixes a bug in which threads were not being properly canceled when serial operations were in force. 
    * Plugin editor no longer allows changing source plugins or names for the sake of internal state consistency

### General Fixes and Improvements:

* Plugin menu position adjusted for consistency.
* Bugs relating to canceling plugin initialization have been fixed.
* Plugins that use database connections have been updated to enforce transient database connections to avoid issues with open database handles between threads.
* Miscellaneous frontend cleanup.
* Updates to reports generated when plugins are loaded and/or complete their analysis.
