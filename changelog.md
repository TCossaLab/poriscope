## Poriscope 1.7: In Progress

* **New Dev Tooling: `pydoclint`**
    * Added as a blocking pre-commit/CI check that a docstring's documented parameters, return type, and raised exceptions actually match the real function signature/body. Configured with `arg-type-hints-in-signature = false` (see `[tool.pydoclint]` in `pyproject.toml`) so it doesn't require every plugin method to carry type hints, matching `mypy.ini`'s existing tolerance for unannotated plugin code.
    * Pre-existing violations (1,090 across 58 files, mostly return-type/raises-section/parameter-name mismatches accumulated before this was introduced) are grandfathered into `.pydoclint-baseline.txt`; only new mismatches introduced from here on fail the hook.
    * Fixed one real violation it surfaced immediately: `MetadataView._plot_heatmap`'s docstring documented a `norm` parameter that doesn't exist in the signature and was never implemented anywhere in the method.
    * Cleared the baseline for `SQLiteEventWriter`, `SQLiteDBLoader`, `SQLitePeakDBLoader`, `SQLiteDBWriter`, and `SQLiteEventLoader`: filled in missing `Raises`/return-type annotations, and fixed `SQLiteDBLoader._load_event_data`'s docstring, which claimed to yield a `Dict` when it actually yields a `Tuple`, and `add_columns_to_table`'s `Raises` section, which promised a never-raised `IOError` while omitting the `sqlite3.Error`/`Exception` paths it actually takes. Also fixed `_validate_settings` docstrings in `SQLiteEventWriter`/`SQLiteEventLoader` claiming `ValueError` when the code actually raises `KeyError`.
    * As per-plugin return-type annotations were filled in across the codebase, `tests/unit/plugins/test_plugin_compliance.py`'s base/subclass annotation-covariance check surfaced several places where an abstract `Meta*` method's own return annotation didn't match what every one of its concrete overrides actually returns (previously invisible, since neither side had annotations to compare). Fixed by correcting the abstract method's annotation (and docstring) to match reality, not by touching the (already-correct) concrete overrides:
        * `MetaReader._convert_data` was annotated `-> npt.NDArray[np.float64]`, contradicting its own docstring and every reader subclass, which can also return `Tuple[np.ndarray, float, float]` when `raw_data=True`. Also reordered its docstring so the `:param:`/`:return:` field list comes after the prose instead of being interrupted by it, which was causing `pydoclint` to swallow the trailing prose into the `:rtype:` field.
        * `MetaReader._map_data` was annotated `-> List[npt.NDArray[Any]]`; narrowed to `-> List[np.ndarray]` to match every reader subclass.
        * `MetaReader._get_file_time_stamps` was annotated with a specific `Union` of timestamp types, but concrete readers legitimately return different narrower element types (`List[int]`, `List[datetime]`, `List[Any]`); widened to `-> Any` since the abstract interface can't honestly commit to one shape.
        * `MetaDatabaseLoader._load_event_data` was annotated `-> Generator[Dict[str, Any], bool, None]`, but `SQLiteDBLoader`/`SQLitePeakDBLoader` (the only two loader implementations) yield tuples, not dicts; widened to `-> Any` and clarified the docstring to say the concrete payload shape is subclass-defined.
        * `MetaDatabaseLoader.get_llm_prompt`/`get_event_counts_by_experiment_and_channel` were annotated `-> str`/`-> int`, but `SQLiteDBLoader`'s implementations genuinely return `None` on failure (consistent with most of this class's other `Optional[...]`-returning methods); widened to `Optional[str]`/`Optional[int]`.
        * `MetaEventFitter._populate_event_metadata` was annotated `-> Dict[str, Numeric]` (`Numeric = Union[int, float, np.number]`), but every fitter that implements it (`CUSUM`, `IntraCUSUM`, `ClassicCUSUM`, `NoFitter`) declares `-> Dict[str, float]`; narrowed to match.
    * Fixed `tests/unit/views/test_metadata_view.py::test_clear_figure_state_sets_constrained_layout`, which asserted the now-superseded `figure.set_constrained_layout(True)` call; `MetadataView._clear_figure_state` actually calls the modern `figure.set_layout_engine("constrained")`.
    * **Flagged, not fixed:** widening `MetaReader._convert_data`'s return annotation to the correct `Union[Tuple[np.ndarray, float, float], np.ndarray]` surfaced a pre-existing mypy error in `MetaReader.load_data` (`poriscope/utils/MetaReader.py:239`, `Item "tuple[...]" of "tuple[...] | Any" has no attribute "astype"`): the loop reassigns the same `data` variable across both the tuple and array branches, which mypy can't narrow across the `raw_data` conditional. The code is correct at runtime (every branch that produces a tuple immediately unpacks it), but resolving this cleanly needs an actual refactor (e.g. distinct variable names or an explicit `cast`), not a type-hint-only change.
    * Cleared the baseline for `BoundedBlockageFinder`, `ClassicBlockageFinder`, `ThresholdBlockageFinder`, `CUSUM`, `ClassicCUSUM`, `IntraCUSUM`, and `NoFitter`: added missing `get_empty_settings`/`_locate_sublevel_transitions`/`_populate_*_metadata`/`_define_*_metadata_*` return-type annotations, fixed `ClassicBlockageFinder._validate_settings`'s `Raises` section claiming `ValueError` when the code actually raises `KeyError`, removed a `:raises AttributeError:` line from `CUSUM`/`ClassicCUSUM`/`NoFitter`'s `_locate_sublevel_transitions` docstrings that doesn't match any exception actually raised in those bodies, and fixed `CUSUM`/`NoFitter`'s `_define_event_metadata_units` docstrings (and `IntraCUSUM`'s override), which claimed the same `Union[int, float, str, bool]` return type as the sibling `_define_*_types` methods despite only ever returning unit strings or `None`.

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
    * **Flagged for later:** `NoFitter`'s `rise_time` and `CUSUM`'s recovered `baseline_std` are each computed inside `_locate_sublevel_transitions` but needed again in `_populate_sublevel_metadata`, whose signature doesn't receive `padding_before`/`padding_after`; neither value can be safely recomputed independently there. `NoFitter` currently stashes `rise_time` on `self`, a call-ordering hazard, and `CUSUM`'s `baseline_std` recovery for a loader that omits it never propagates to `_populate_sublevel_metadata`, causing a silent `TypeError`-driven rejection instead of a clean one. The base class's own docs point at the fix (encode the extra value into the returned `sublevel_starts`/`edges` structure instead of instance state), but that requires rewriting every `sublevel_starts[i]` reference in both classes' `_populate_sublevel_metadata` - deferred as a real refactor rather than a mechanical fix

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
    * Fixed pydoclint baseline violations in `MetaDatabaseLoader`/`MetaDatabaseWriter`: fixed a typo (`expeirments_and_channels`) repeated across half a dozen `experiments_and_channels` parameter docs; fixed `MetaDatabaseLoader.export_subset_to_csv`'s docstring, which documented a duplicated/misnamed `conditions` param instead of the real `subset_name`, used a malformed `:raises:` format that pydoclint couldn't parse, and described a `:return:` where the method actually `yield`s progress; corrected `get_table_by_column`'s `rtype` (`List[str]` when it actually returns `Optional[str]`); added missing `Raises` sections to `get_experiment_id_by_name`/`construct_metadata_query`; removed inaccurate `Raises` sections from `get_plot_features`/`report_channel_status`, which don't actually raise; fixed `MetaDatabaseWriter._write_event`'s docstring documenting a stale `data` parameter while leaving the real `sublevel_metadata` parameter undocumented; fixed `MetaDatabaseWriter.write_events`'s docstring describing a `:return:` where the method actually `yield`s progress, and added its missing `Raises` section; and fixed a missing leading colon on a `:param settings:` field in both files' `_validate_param_types` that left the parameter entirely undocumented

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
    * Fixed pydoclint baseline violations in `LogDecorator`/`MetaController`/`MetaModel`/`MetaReader`/`MetaWriter`: corrected `MetaController._relay_global_signal`/`_relay_data_plugin_controller_signal`'s docstrings, which documented `return_function` instead of the real `return_function_name` and listed it out of order relative to `call_args`; fixed `MetaController.__init__`/`MetaModel.__init__`'s docstrings misnaming their `**kwargs` parameter; added missing `-> None` return annotations to `MetaController.load_actions_from_json`/`update_tab_actions`; added a missing `logger` class attribute entry to `MetaReader`'s class docstring, and reworded its opening sentence, which started with a bare `:ref:` role that silently broke the docstring parser for the entire class docstring; fixed `MetaReader.load_data`'s `Raises` section omitting the `IndexError` paths it actually takes; corrected `MetaReader.get_raw_dtype`'s docstring documenting a stale `configs` parameter that method doesn't take; fixed `MetaReader._sort_objects_by_channel_and_time`'s `rtype` missing a closing bracket; corrected `MetaReader.continuous_read`'s return annotation, which claimed a plain array despite being a generator, to `Generator[...]`; added missing `Raises` sections to `MetaReader._set_sample_rate`/`_scale_data`; fixed `MetaWriter._write_data`'s docstring documenting a stale `batch_size` parameter while leaving the real `abort` parameter undocumented; fixed `MetaWriter.commit_events`/`_commit_events`'s docstrings documenting a `:return:`/`float` instead of the `:yield:` these generators actually produce, and added `_commit_events`'s missing `Raises` section; and added several missing `-> None`/`-> bool` return annotations across all five files where none existed

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
    * Fixed pydoclint baseline violations: `handle_edit_triggered`/`handle_delete_triggered`'s docstrings documented their `metaclass`/`key` parameters in the opposite order from the real signature; `_update_cache`/`_logscale_and_filter_multiple_columns`'s docstrings misnamed their `*args`-style parameters and were missing `Raises` sections for the `ValueError`s they actually raise; `handle_add_triggered` was missing a return annotation and a `:type:` for its documented parameter; and `_factors`/`_logscale_and_filter_multiple_columns` were missing return-type annotations entirely

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
    * Fixed pydoclint baseline violations in `ProteinController`/`ProteinView`: corrected `relay_query`'s docstring to name its `*args` parameter correctly; added missing `:param:`/`:type:` entries for `_plot_all_points_histogram`'s `norm`, `_construct_all_points_histogram`'s `sizes`, `_show_filter_info_dialog`'s `parameters`, and the untyped-in-docstring params of `_build_where_clause`/`_rebuild_event_id_cache`/`_shift_range_and_update_plot`; removed a stale copy-pasted `args`/`kwargs` param doc from `_init`; added missing `:raises:` sections to `_commit_fits`, `_plot_xyerr_scatterplot`, `_construct_all_points_histogram`/`_construct_single_event_histogram`, `_update_event_histogram`, `_fit_double_gaussian`, `_compute_theoretical_blockages`, and `_handle_other_actions`; and added return-type annotations (and, where needed, a matching `list[float]` variable annotation for `_generate_vm_ensemble`'s Monte Carlo accumulators) to over a dozen methods that previously had none

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
    * Fixed pydoclint baseline violations in `RawDataModel`/`RawDataView`: added missing `:param:`/`:type:` entries for `update_plot`'s `start`/`baseline` args and `update_psd`'s misnamed/undocumented `psd_data`/`rms_data`/`frequency` args; fixed `_gaussian`'s docstring documenting its `mean` parameter under the wrong name (`A` instead of `m`) and missing a return section; added missing `:raises:` sections to `_get_baseline_stats`, `_handle_plot_events`, and `_start_eventfinder`; added `-> None` return annotations to several handler methods that never return a value; and added return-type annotations to `RawDataModel.integrate_noise`/`calculate_psd`

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
