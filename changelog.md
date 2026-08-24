## Poriscope 1.7: In Progress

* **New Dev Tooling: `pydoclint`**
    * Added as a blocking pre-commit/CI check that a docstring's documented parameters, return type, and raised exceptions match the real function signature/body. See `[tool.pydoclint]` in `pyproject.toml` for the config; notably `arg-type-hints-in-signature = false`, so it does **not** require every plugin method to carry type hints, matching `mypy.ini`'s existing tolerance for unannotated plugin code - only docstrings themselves are held accountable.
    * Run it yourself with `pydoclint --baseline=.pydoclint-baseline.txt poriscope` (pre-commit already runs it on staged files). `DOC108` results are a harmless policy nag (signature already has type hints despite the policy above) - safe to ignore.
    * Pre-existing violations at adoption were grandfathered into `.pydoclint-baseline.txt` so existing code didn't need a mass cleanup up front; only *new* mismatches you introduce will fail the hook. If you fix a baselined violation, regenerate the baseline so it can't silently keep passing for a docstring that no longer matches: `pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope`.
    * A follow-up sweep cleared the great majority of the ~1,090-violation baseline this tool inherited across 58 files (down to ~430 lines, almost entirely `DOC108` plus `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py`, excluded per standing project policy), fixing real docstring bugs along the way: stale/copy-pasted parameters, wrong return types, and missing `Raises` sections, across nearly every plugin family in the codebase.
    * Along the way, adding the return-type annotations pydoclint asked for occasionally exposed pre-existing problems that had been invisible for lack of anything to check against: a few `Meta*` abstract methods' declared return types didn't actually match what their real subclasses return (caught by `test_plugin_compliance.py`'s covariance check once both sides had annotations to compare, fixed by correcting the abstract declaration), one genuine `mypy` false positive in `MetaReader.load_data` needing a `cast()` rather than a type change, and a few bare `except:` clauses narrowed to `except Exception:` so their `Raises` sections could be written down at all.
    * Documented the full set of automated QA checks (pydoclint, plugin interface compliance testing, and a step-by-step pre-PR checklist) in the Sphinx docs' Quality Control page, cross-linked from the plugin development manual so contributors know what to run before opening a PR.

* **New Dev Tooling: Type annotations for data plugins**
    * First installment of the full-codebase type-annotation pass tracked in `future_fixes.md`: added parameter/return type hints to every method across the `datareaders`, `eventfinders`, `filters`, `eventloaders`, `datawriters`, `db_loaders`, and `dbwriters` plugin families, plus the CUSUM-family fitters (`ClassicCUSUM`, `CUSUM`, `IntraCUSUM`, `NoFitter`), copied from each family's `Meta*` base contract. `NanoTrees.py`/`Basic_PeakFinder.py`/`PeakFinder.py` excluded per standing project policy. Docstring/signature only - no behavior changes.
    * Fixed a genuine pre-existing type-hint bug in `MetaReader.py` that this surfaced: `_get_configs`/`_map_data`/`_get_file_time_stamps`/`_get_file_channel_stamps` declared their file-list parameter `List[os.PathLike]`, but `_get_file_names` (the only producer of that list) has always returned `List[str]`, and every reader subclass's handling of it (regex matching, string `.replace()`) already assumed `str`. Narrowed to `List[str]` across the base class and all 7 reader subclasses to match actual behavior.
    * `.pydoclint-baseline.txt` regenerated to absorb the new (expected) `DOC108` entries these signature hints introduce under the current `arg-type-hints-in-signature = false` policy.
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
    * `.pydoclint-baseline.txt` regenerated to absorb the new (expected) `DOC108` entries these signature hints introduce under the current `arg-type-hints-in-signature = false` policy.
    * EventAnalysis triad and `utils/eventAnalysisControls.py` annotated next. Google-style `Args:`/`Returns:` docstrings in `EventAnalysisView` converted to the Sphinx style pydoclint checks against, so their parameter types are actually verified rather than silently baselined.
    * Fixed a genuine pre-existing annotation bug this surfaced: `EventAnalysisController.update_features` was annotated one nesting level too deep (`Optional[List[List[float]]]` etc.), but `MetaEventFitter.get_plot_features` returns one flat list of features per event, not one per subplot. Corrected the hints and the docstring wording that described the wrong level.
    * Corrected four `MetaView` range-helper signatures that were wrong against their only call sites: `_parse_event_indices` declared `allow_floats: Literal[True]` while both `EventAnalysisView` and `RawDataView` pass `False`, and `_shift_ranges`/`_merge_ranges`/`_format_ranges` were typed int-only while `RawDataView._shift_range_and_update_trace` feeds them floats. Also cleared seven stale `:type:` lines in the same file left over from the earlier `poriscope/utils/` installment.
    * One further discrepancy flagged rather than fixed: `EventAnalysisView._update_event_plot` zips each feature list against its label list while guarding only on the feature list being non-`None`, so a fitter returning features but no labels would raise `TypeError` (three sites, marked with commented `# type: ignore[arg-type]`).

* **New Data Plugin: `ThresholdBlockageFinder`**
    * Subclass of `ClassicBlockageFinder` that imposes much tighter bounds on the start and end times flagged in the output.

* **New: End-to-end (E2E) test suite**
    * Added comprehensive E2E/UX coverage for RawData, EventAnalysis, Metadata, Clustering , and Protein tabs
    * Added a shared `tests/synthetic_data` package for reproducible fixtures: synthetic Chimera recordings, synthetic events/metadata SQLite databases (with configurable event lengths and deliberately-rejected events for testing fitter rejection paths), removing reliance on checked-in binary test databases

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
