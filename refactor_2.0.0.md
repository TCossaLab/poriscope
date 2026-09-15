## Where the gates stand - THE LIVE TABLE

**Every other gate table in this file is a dated snapshot and must not be edited.** This
one is the current state; update it as each branch lands. The distinction is not
decoration: the closeout's branch 3 began by editing the 2026-09-08 snapshot's audit row
as though it were live, because the live figures existed only in the artifact and a
snapshot was the nearest thing that looked like one.

| Gate | Refactor start | Now | Target |
| --- | --- | --- | --- |
| Boundary allowlist | 111 | **3** | 0 |
| - rule 1, View emits | 75 | **0** | 0 |
| - rule 2, View computation imports | 22 | **3** | 0 |
| - rules 3, 4 and 5 | 10 / 4 / - | **0 / 0 / 0** | 0 |
| Refactor-coverage audit | - | **85 of 85 pinned** | 100% |
| Duplication, removable - the original 6 families | 1,889 | **721** | - |
| - `*Model.py`, a 7th family added 2026-09-14 | not measured | **38** | 8 |
| - the 3 analysis-tab families of the original six | 1,199 | **31** | 31 (floor) |
| - the 3 Step-5 families, untouched by design | 690 | **690** | Step 5 |

**The duplication rows do not add up to one before/after pair, deliberately.** `*Model.py`
became a measured family part-way through, so 1,889 never included it and pairing 1,889
with a seven-family total would compare two different scopes - the mistake method rule 2
records this plan making four times. Its 38 is 30 removable lines from a byte-identical
`load_events_by_id` across `MetadataModel` and `ProteinModel`, plus an irreducible 8:
`MetaModel._init` is abstract, so all five subclasses implement it as `pass`. The
`*View.py` floor of 31 is `update_plot_features`, decided 2026-09-14.

## Step 4 closeout - the commit series, planned 2026-09-14 at `a1ef5906`

**What is left of Step 4**: 4c's remainder with 3d riding it, 4e, the event-plot promotion,
and the 4a exit-review item. Allowlist **8**, every entry rule 2. Duplication in the three
analysis-tab families **31**.

### The surface, re-measured - and smaller than the 4d handoff recorded

Counting only loads *outside* an annotation, which is what rule 2 now means:

| File | booked | methods | loads | the handoff said |
| --- | --- | --- | --- | --- |
| `MetaView.py` | numpy | 1 | 9 | 10 in 1 |
| `EventAnalysisView.py` | numpy | **1** | **1** | 5 in 2 |
| `ClusteringView.py` | pandas | **1** | **1** | 8 in 4 |
| `RawDataView.py` | numpy | **3** | **11** | 33 in 7 |
| `MetadataView.py` | numpy, pandas | **9 + 2** | **42 + 2** | 72 in 12, 16 in 7 |
| `ProteinView.py` | numpy, pandas | **8 + 4** | **76 + 7** | 100 in 9, 32 in 15 |

### Three kinds of numpy, and only two of them are Model code

This is what decides whether rule 2 can reach zero, so it is stated before the series
rather than discovered inside it.

1. **Computation** - histogram construction, the Monte Carlo geometry ensemble, theoretical
   blockages, the logscale filter. Moves to a Model. Most of the 8 points.
2. **A derived axis.** `time = np.arange(len(data)) / samplerate * 1e6` appears **five times
   across four Views** - `EventAnalysisView:536`, `RawDataView:204` (with `+ start`) and
   `:663`, `MetadataView:2426`, `ProteinView:1787`. The Model already owns the samples and
   the samplerate, so it hands the time base back with them. One decision, five sites.
3. **Artist parameters** - `extent=[np.min(x), np.max(x), ...]`, colorbar ticks via
   `np.linspace`, and the PSD axis limits `update_psd` derives with `np.searchsorted` and
   `ceil(log10(...))`. This is matplotlib configuration computed from data the Model already
   returned, and the plan's own line is that artist manipulation **stays in the View**.

**How the remaining sites are decided, settled 2026-09-14.** The rule is
*responsibility separation and maintainable code*, not import purity: does moving it to the
Model create complexity where none is needed, and does removing an import? Where the View is
the only consumer of a derived quantity, the Model supplies the **data** and the View does
the **visualisation calculation**. So branches 4 and 5 **move the computation and record the
view-side floor** rather than driving numpy to zero - `_construct_all_points_histogram` and
the Monte Carlo ensembles move, `set_heatmap`'s extent and colorbar ticks do not. Ambiguous
sites go to Kyle for a ruling rather than being guessed.

**Kind 3 gates exactly 2 of the 8 points** - `RawDataView`'s (`update_psd`) and
`MetadataView`'s numpy point (`set_heatmap`). **Decided 2026-09-14 and narrowed the same
day**, see `DECISIONS.md`: the test is **whether the value leaves the View**. A time base is
data - it is cached and exported to CSV - so the Model builds it. Axis limits never leave the
View, so they stay there and shed numpy by using `math` and `bisect` instead. Per-site
classification is the first task of each branch.

### The series

Order is forced in one place: **the logscale helper cannot move until all eight of its call
sites are converted**, and they sit in Clustering (1), Metadata (5) and Protein (2). So
`MetaView`'s point falls last, not first - the 4d handoff had it first.

0. **Close the nine `RUNS ONLY` targets - LANDED 2026-09-14.** The audit reads **78 of
   78 pinned** and exits 0; 33 tests, each class checked against four or five deliberate
   source mutations, all thirteen of which failed the class they were aimed at.
   `ci-branches.yml` now collects coverage and runs the audit. Two findings filed rather
   than bundled: the experiment/channel scope carries **three** annotations for one value,
   and `MetadataModel.py:296` uses the `scipy.stats.kde` namespace SciPy 2.0 removes.

   *The state that made it necessary, kept because it is the lesson:*
   Measured 2026-09-14 by running the suite under `--cov` and the audit against it:
   **69 of 78 pinned, 9 RUNS ONLY, 0 untested**, and the audit exits 1 on anything that is
   not `PINNED`. All nine are *destinations of moves this refactor already made*: five from
   4b (`resolve_event_ids` and `load_events_by_id` on both Models, `drop_fit_columns`),
   three from 4c Metadata (`kernel_densities`, `histogram_bin_edges`, `_log_exp_pdf`), and
   `ProteinView.set_distribution_fits`, which has **zero** test references anywhere. Their
   bodies run under the e2e and flow suites; nothing names them. **Method rule 52 for the
   third time** - a conversion owes tests to its destination - and pinning
   `set_distribution_fits` here is not wasted work, because rule 39 wants the pre-move
   golden to be the evidence branch 5's move changed nothing.

   **Why nobody saw it, which is the part worth keeping.** The audit needs coverage data, so
   it runs in exactly one place: `ci-internal-pr.yml`. Feature branches finish into
   `develop` through `git flow feature finish`, which merges locally and opens no PR - so
   every one of these landed without the gate ever running. Locally the two
   `test_refactor_coverage_gate.py` tests that would notice **skip** with "no coverage.json
   at the repository root", which reads as a configuration nit rather than as a disarmed
   net. Rule 41's shape exactly. Worth deciding separately whether the audit should also run
   on branch pushes, since that is where this work actually lands. **Decided 2026-09-14:
   it does.** `ci-branches.yml` gains the coverage flags and the audit step, which is what
   makes the gate see the path this work takes.

1. **EventAnalysis - LANDED 2026-09-14.** **Allowlist 8 -> 7**, `EventAnalysisView` off
   the list entirely. `EventAnalysisModel.event_time_bases` is that Model's first real
   method - it was the last `def _init: pass` Model in the repository. Two dead things
   came out with it, both called out as breaking: `EventAnalysisView.update_plot_samplerate`
   and `plot_samplerate`, write-only once the axis moved, and
   `MetaEventTabController.update_plot_samplerate`, a relay with **no production callers
   at all** - both event tabs call the View directly and always did, and only its two
   tests kept it looking alive (rule 65). 11 tests on the new method, mutation-checked.
   **Manual Windows pass run 2026-09-14 over the Event Analysis tab, all clear.**

   *The original framing, kept:* One point, one
   load, no logscale site. `EventAnalysisModel` is still `def _init: pass`, the last stub
   Model in the repo, so this gives it its first real method and fixes the shape kind 2 uses
   four more times. **Allowlist 8 -> 7.**
2. **Clustering - LANDED 2026-09-14.** **Allowlist 7 -> 6**, `ClusteringView` off the
   list. The restructure was cleaner than "move one line": `ClusteringController` was
   already loading `plot_data` and handing it *to* the View to filter, so the View now
   emits the unfiltered rows plus the spec and `ClusteringModel.build_clustering_frame`
   does the filtering, log-scaling and frame construction - taking the logscale call and
   the `pd.DataFrame` out together, so **1 of the 8 logscale callers is converted**.
   `MetaModel` gained the helper at the head of this branch per `DECISIONS.md`, with an
   equivalence test comparing the two copies as source so they cannot drift. The column
   guard moved to the Model, which turns a missing column from an unhandled raise into a
   status-panel message - safe because the Controller already wrapped both paths in the
   same handler. `ClusteringController.cluster` had **no test at all** (rule 52, third
   time) and now has six. 21 new tests.

   *The original framing:*
   `on_metadata_loaded` holds the logscale call at `:609` and the tab's only pandas use at
   `:613`, four lines apart: the Model logscales and returns the frame.
   **Allowlist 7 -> 6**, and 1 of 8 logscale sites.
3. **RawData - LANDED 2026-09-14.** **Allowlist 6 -> 5**, `RawDataView` off the list.
   The two time bases went to the Model and `event_time_bases` was promoted to
   `MetaModel.time_bases` with a scale and an offset, since RawData is the second caller
   and Metadata and Protein are the third and fourth. `update_psd`'s axis limits **stayed
   in the View** on Kyle's ruling and shed numpy by using `math` and `bisect` - proved
   equivalent over six hand-built cases and 2,000 randomised ones, zero mismatches.
   **Manual Windows pass run 2026-09-14 over the trace plot with and without the baseline
   band, a non-zero start time, the event plot and the PSD, all clear.**

   *The original framing:* `update_plot` and `_update_event_plot`
   take branch 1's shape. `update_psd` is kind 3 and **blocked on the open decision above**.
   **Allowlist 6 -> 5 only if the limits move.**
4. **Metadata - split into three, 2026-09-14, after reading what it actually touches.**
   The plan called this "move six methods"; both of the big ones consume
   `self.event_data_generator` from inside `_overlay_plot`, which measures **341 lines, 5
   loops, 29 ifs, 14 returns and 100 test references**, with 46 more on the generator
   attribute. That is a restructure of the densest method in the tab, and it is the reason
   3d had to ride 4c in the first place - so it gets its own branch rather than being a
   commit inside a larger one.

   **The split is two, not three - 4a dissolved on being worked, 2026-09-14.** It was to
   move the shared baseline-and-rectify (three copies in `MetadataView` at `:1755`, `:1805`
   and `:1871` - the padding in samples, the median of the pre-event baseline, then
   `sign(baseline) * trace - sign(baseline) * baseline`) to `MetadataModel`. **All three
   copies are inside View methods and no View can reach a Model**, so the move is not
   executable until the generator restructure below moves their callers. Extracting them to
   a single helper *is* executable and is worth doing - three copies of the measurement in
   one file, where the duplication ratchet cannot see them - but it moves no gate, and the
   helper is precisely what the generator branch then relocates. So it becomes that
   branch's first commit rather than a branch, and each call site is touched once. Rule 25:
   a recorded plan step is a claim like any other.

   **Split by method, not by kind of work** - `_plot_1d_histogram` is both a computation
   site and one of the five logscale callers, so splitting by kind would rewrite it twice
   (rule 60). Since branch 2 put `logscale_and_filter_columns` on `MetaModel`, each
   logscale caller now converts independently, which makes a per-method split possible:

   - **4b - four self-contained plot methods. LANDED 2026-09-14** at `d16a4172`, suite
     3,950 passed / 16 skipped, allowlist unchanged at 5 as predicted, audit 85 of 85.
     Manually passed on Windows the same day over all five plotting surfaces. `_plot_capture_rate`'s inter-event times,
     `_plot_categorical_histogram`'s counting (which takes one of the two pandas uses),
     `set_histogram_bins`' counts, and `_plot_1d_histogram`'s shared limits. Ordinary
     request/setter splits of the kind 4c Metadata already did four of. **Its logscale
     call moved to the next branch** - see `DECISIONS.md`: the Model can only filter if
     `hist_data` holds raw data, which is density's shape, and the two write the same
     shared limits. **Three defects surfaced while preparing this branch**, all
     pre-existing and all in code about to be moved: the plot-data export of a
     categorical histogram had never worked, the capture rate always reported one row
     dropped, and the density plot's limits were being read off the DataFrame - so a bin
     width there was accepted and silently ignored.
   - **4c - `_overlay_plot` and what it drives. LANDED 2026-09-14**, suite 3,987 passed
     / 16 skipped, **allowlist 5 -> 4** with pandas closed for `MetadataView` and numpy
     recorded as its floor, audit 85 of 85. Five commits: the baseline-rectify extracted
     to one body; both event-data reductions moved to `MetadataModel`, which is what took
     the pandas point; the categorical histogram ordered by count at a user's request; the
     heatmap and both scatterplots converted; and the 1-D pair last, together, for the
     reason method rule 72 records. **The generator no longer reaches the View at all** -
     `event_subset_requested` and `load_event_subset` went with it, and the query is set
     only once the reduction has succeeded too, so one guard refuses both failures.
     `hist_data` went from **four element types to two**. **Manual pass run the same day**: three reports, one a real pre-existing defect - an event overlay drew over whatever plot type preceded it, since that branch checked only that the axes were valid - and two that turned out to be a status-panel line scrolled past under the applied-query echo, settled by driving `handle_parameter_change` against a real app shell and reading the panel widget back. Two smaller behaviour changes
     fell out and are in `changelog.md`: a density plot on an empty subset no longer wipes
     the figure, and an unrecognised event plot type is refused rather than redrawing the
     previous event. **Five logscale callers, not four**, because 4b handed one back.

   **Neither branch closes a gate on its own**: the two pandas uses are one in each, so
   rule 2 for `MetadataView` moves only when 4c lands. Answered before starting, per rule
   38, so the branches stand on the layering. **Both held**: 4b left the allowlist at 5 and
   4c took it to 4.

   A manual pass follows each, on a tab whose last one returned four defects.

   Classified per site
   2026-09-14 under the governing test. **Moves to `MetadataModel`:**
   `_construct_all_points_histogram` (14 numpy + 1 pandas, returns a frame),
   `_construct_event_overlay`, `_plot_capture_rate`'s inter-event times (which feed the fit
   already on the Model), `_plot_1d_histogram`'s shared min/max, `set_histogram_bins`' bin
   counts, and `_plot_categorical_histogram`'s counting (which takes the second pandas
   use). **`_update_event_plot`'s time base stays here, unlike the other three tabs**: each
   event carries its own samplerate in its payload and the View materialises the event
   *generator* itself, so supplying the axis from the Model would mean the Controller
   consuming a stream the View is built to walk, or a round trip per event. Complexity
   where none is needed, and it costs no import because the heatmap ruling keeps numpy in
   this file anyway. `ProteinView` has the same shape and gets the same treatment. **Stays, as a recorded floor:** `set_heatmap`'s extent, colorbar ticks and
   export reshape - see `DECISIONS.md` for the ruling - and
   `_plot_all_points_histogram`'s display normalisation. **So pandas closes and numpy does
   not**: expect allowlist 5 -> 4 with `MetadataView` numpy recorded as floor. 11 methods, 2 points.
   **Confirmed on landing**, and the floor is what the boundary gate now records.
   `_plot_scatterplot` and `_plot_3d_scatterplot` were **deliberately excluded** from 4c
   Metadata because they freed no import - the logscale move puts them back in scope, which
   is method rule 60 arriving from the other direction. `set_heatmap` is the kind-3 case.
5. **Protein's 4c remainder, carrying two logscale sites.** The largest real computation
   left anywhere in the View layer. **Re-measured 2026-09-14 immediately before starting,
   and three of this entry's claims did not survive** - rule 1.

   - **Worth 1 point, not 2.** `ProteinView`'s computed pandas is 7 loads in 4 methods, all
     of them targets, so pandas closes. Its numpy is 60 loads in 8 methods, and **two of the
     eight are the recorded floors** - `_plot_all_points_histogram`'s display normalisation
     (`:822`) and `_update_event_plot`'s time base (`:1787`), the same two rulings Metadata
     records. So numpy is a floor here too: **expect allowlist 4 -> 3**. Rule 38, answered
     before starting.
   - **The pinning commit is already done.** `set_distribution_fits` had zero test
     references when this was written; closeout branch 0 closed it as one of the nine
     `RUNS ONLY` targets, and it now has 11 - every one behavioural, because
     `test_protein_view`'s `mock_view` is a real `ProteinView` with only its drawing
     surfaces mocked. Every other target counts the same way: no mocks. Rule 25 - a
     recorded blocker re-derived before being obeyed.
   - **16 targets, not 12**, taken from the audit's `MOVED` table rather than from this
     entry's prose (rule 16). 1,447 lines across them.

   The dependency graph sets the order: `_compute_theoretical_blockages` is
   `_generate_vm_ensemble`'s callee, and `_generate_vm_ensemble` and `_summarize_vm` are
   called from **both** distribution setters, so those five move as one commit - the one
   that takes the last pandas with it.

   **LANDED 2026-09-14**, suite 4,020 passed / 16 skipped, **allowlist 4 -> 3** with
   pandas closed for `ProteinView` and numpy recorded as its floor, audit 85 of 85.
   **Manual Windows pass the same day: all clear, no defects** - both distribution
   modes, the per-event grid, the Peak Scatterplot's error bars, Report All and the
   fit commit. The first pass of the closeout to return nothing, on the tab carrying
   the most moved computation.
   Five commits: the per-event binning, the ensemble average, the Monte Carlo, and the
   two logscale callers, on top of the re-measurement above. Three things worth
   carrying:

   - **`_summarize_vm` stays on the View**, decided 2026-09-14. It formats the display
     strings `_report_ensemble_fit` writes to the panel and nothing outside that method
     reads them; moving it would put `± nm³` in a Model. Recorded in the audit's table
     with the reason rather than dropped from it.
   - **The individual-distribution path binned each event over a running union** of the
     events before it, so the edges depended on arrival order. Both per-event paths use
     the same rule now, at Kyle's ruling.
   - **The plain scatterplot promoted to `MetaSubsetTabView` / `MetaSubsetTabController`**
     rather than being written twice: Protein's halves came out byte-identical to the
     ones Metadata gained in 4c, so a second copy would have raised the ratchet rather
     than lowered it. The promotion moves no number either way, because the bodies left
     the measured families rather than being deleted from them.
6. **3d closes. UNBLOCKED 2026-09-14** - branch 5 converted `ProteinView`'s two, and
   **no tab View calls `MetaView._logscale_and_filter_multiple_columns` any more**. The
   helper is deleted, the published plugin base sheds numpy, and that is **the last
   rule-2 point, or the floor**. The source-level equivalence test in
   `tests/unit/models/test_meta_model_logscale.py` raises by name when the `MetaView`
   copy goes, and is rewritten against the surviving one as part of this branch.
7. **4e - much smaller than recorded.** The View layer's only read/write sites are
   `MetaSubsetTabView._load_filter` (`:495-503`) and `_save_filter` (`:875-883`), both JSON
   round-trips; every other hit is `QFileDialog` path selection, which 4e keeps in the View
   by design. `MetadataView._export_csv_subset`, the audit's only 4e target, was already
   converted by 4a commit 5 and wants re-checking rather than moving. **Moves no gate** -
   say so before starting, method rule 38.
8. **The promotion review.** `load_event_plot_data` is **108 and 113 lines** now, down from
   122/129 before 4b moved the query construction out. Judge it now that 4b has landed;
   the two `resolve_event_ids` on the Models are the better merge candidate and want a
   `MetaSubsetTabModel` that does not exist.
9. **The 4a exit-review item.** The protein tab's unresolvable-experiment guard has still
   never run against a real database.

10. **Strip every refactor-plan reference out of the docstrings and the published
    docs** - added 2026-09-14 at Kyle's request, and it is a sweep rather than a
    judgement call. Docstrings across `poriscope/` cite "Step 4c", "Step 4's
    closeout", numbered method rules and "Decision B's command path"; the Sphinx
    pages are generated from them and inherit all of it. **None of it means anything
    to a later reader** - the plan is a temporary artefact, this file is deleted when
    2.0.0 ships, and a plugin author has no way to look any of it up. Rewrite each as
    the reason it is *today* - the invariant, what breaks if you change it - and leave
    the history here, in the artifact and in `DECISIONS.md`, which are written for
    that audience. Grep for `Step 4`, `Step 3`, `method rule`, `Decision [A-E]`,
    `rule \d`. **Nothing new is to be written this way from now on**, so the sweep
    only has to cover what is already there.

11. **A documentation pass over everything Step 4 changed** - added 2026-09-14 at Kyle's
    request, and it closes the series. Every doc touching behaviour Step 4 moved: the
    autogenerated plugin pages, the hand-written manuals under `docs/source/utils/`, and any
    prose describing where computation lives or how a tab talks to its Model. Correct what
    has gone stale rather than only regenerating - `sphinx-build -W` proves references
    resolve, not that sentences are still true.

**Two loose ends the audit carries.** Its `MOVED` table still lists the five
`MetaEventTabView` range helpers as 3d targets, and 3d no longer exists as a step - 3e moved
them down already. And the last 31 removable lines in `*View.py` are `update_plot_features`,
identical in `EventAnalysisView` and `MetadataView`, which sit in **different** base families
- so the only shared destination is `MetaView`, and the method writes six instance
attributes. Method rule 34 says that wants an intermediate and there is none. **Decided
2026-09-14: 31 is the floor**, recorded with its reason rather than widening the published
plugin API by six attributes to delete 31 lines. See `DECISIONS.md`.

**Each tab branch ends with a manual Windows pass over that tab's plotting surfaces**, dated
in the verification section, and the full suite green before every commit.

## Rule 2 relaxed, 2026-09-14 - the remainder re-priced

**Boundary rule 2 now counts computation, not annotations**, on Kyle's call: an import that
exists only to write a type is not the thing the rule is named for, and it is not worth
distorting a signature to shed one. `DECISIONS.md` carries the derivation. **Allowlist 14 ->
8**, and every remaining entry is a library actually being *used*.

| File | still booked | what it is |
| --- | --- | --- |
| `EventAnalysisView.py` | numpy | **one line**, `:536` - `np.arange` builds the time axis for `_plot_events` |
| `ClusteringView.py` | pandas | **one line**, `:613` - the frame rebuilt straight after the logscale call |
| `MetaView.py` | numpy | the logscale helper, i.e. 3d |
| `RawDataView.py` | numpy | 11 sites across 7 methods |
| `MetadataView.py` | numpy, pandas | numpy in 12 methods; pandas at `:846`, `:1812` |
| `ProteinView.py` | numpy, pandas | numpy in 9 methods; pandas at 7 sites |

**This re-orders the queue the 4d handoff proposed.** That handoff put `MetaView` first at
"the cheapest two points on the board"; under the corrected rule it is worth **one** point,
and it is still gated on all eight logscale callers moving, because 3d is folded into 4c.
`EventAnalysisView` and `ClusteringView` are now one point each and each is **a single
expression**, which makes them the cheapest work left by a wide margin.

**The annotation-only exemption also repays a debt.** `MetaSubsetTabView.event_id_rows` had
been typed `Optional[Any]` with a comment saying the gate was why, although it holds
`load_metadata`'s `Optional[pd.DataFrame]` and its only consumer uses `.empty`, `.columns`
and `["event_id"].tolist()`. It is annotated honestly again.

## Step 4d handoff, 2026-09-13 - COMPLETE

**Both halves of 4d are done and merged; `develop` is at `b1f9b911`.** Suite **3,795 passed
/ 16 skipped**, `pre-commit run --all-files` green, `sphinx-build -W` green. Two feature
branches: `step-4d-domain-state` (four commits) and `step-4d-subset-state` (four commits).

| Gate | Refactor start | Now | Target |
| --- | --- | --- | --- |
| Boundary allowlist | 111 | **14** | 0 |
| - rule 1, View emits | 75 | **0** | 0 |
| - rule 2, View computation imports | 22 | **14** | 0 |
| - rule 3, Controller reads a View private | 10 | **0** | 0 |
| - rules 4 and 5 | 4 / - | **0 / 0** | 0 |
| Duplication, removable - repo-wide, 6 families | 1,889 | **721** | - |
| - the 3 analysis-tab families | 1,199 | **31** | 0 |
| - the 3 Step-5 families, untouched by design | 690 | **690** | Step 5 |

**Rules 1, 3, 4 and 5 are all at zero. Every remaining allowlist entry is rule 2**, and the
composition has changed enough to be worth stating: `scipy`, `sklearn`, `hdbscan`,
`fast_histogram` and `sqlite3` are **gone from the View layer entirely**. What is left is
numpy (6 files), `numpy.typing` (5) and pandas (3).

### What landed

**The first half - threading the filter context.** The Views parked a filter's name, text
and the name it replaces on themselves while validation went out to the loader, and both
Controllers read those privates back. All of it now travels with the request. The three
`_pending_*` attributes, `clear_pending_filter_state` and a dead
`MetaSubsetTabController.on_raw_filter_validated` are gone. **Allowlist 19 -> 14, rule 3 to
zero** - the whole of 4d's gate value, from the half that deletes state rather than the half
that relocates it.

**The second half - and the plan's premise did not survive measurement.** `subset_filters`
does **not** move to the Model; see `DECISIONS.md` 2026-09-13. **No Model reads it** - Step
4b moved query construction down and it takes a single filter's *text* as an argument - so
the move would have installed a field nothing in the Model touches and turned **16
synchronous View reads** into round trips, for no gate movement and 165 test references.
What was actually wrong was narrower: the Controller mutating the View's dict at four sites.
`MetaSubsetTabView` gained `commit_filter` and `get_subset_filters`, and the Controller asks
rather than assigns. `restore_subset_filters` was promoted to the base on the way (20 of 21
lines identical, panel name the only difference).

**One user-visible defect, found while verifying and fixed in its own commit.** Restoring a
session dropped the subset filters of whichever tab was restored **last**, because
`instantiate_analysis_tab` snapshots `plugin_history` before `restore_session_state` fills
the tab in, and only the *next* tab's instantiation corrects it. Reported as "Metadata keeps
them, Protein does not"; the cause is order, not tab. Reproduced at `develop` first, so
pre-existing.

### Resume here

**Step 4's remainder is 3d plus 4c for the three tabs it never reached**, and the sizes are
very uneven. Measured 2026-09-13 at `b1f9b911`, as uses of `np.`/`npt.`/`pd.` and the number
of methods carrying them:

| File | numpy | numpy.typing | pandas | allowlist points |
| --- | --- | --- | --- | --- |
| `MetaView.py` | 10 in **1** method | 4 in 1 | - | 2 |
| `EventAnalysisView.py` | 5 in 2 | 4 in 2 | - | 2 |
| `ClusteringView.py` | 8 in 2 | - | 8 in 4 | 2 |
| `RawDataView.py` | 33 in 7 | 22 in 7 | - | 2 |
| `MetadataView.py` | 72 in 12 | 27 in 5 | 16 in 7 | 3 |
| `ProteinView.py` | 100 in 9 | 24 in 5 | 32 in 15 | 3 |

**Take `MetaView` first.** Its numpy use is confined to **one method** - the logscale helper,
which is 3d - and freeing it sheds numpy *and* `numpy.typing` from the published plugin base,
which is the best-placed 2 points on the board. The 2026-09-13 correction stands: the helper
is **not** a pure array transform, it emits `add_text_to_display` three times, so it goes to
`MetaModel` and its eight call sites each carry the logscale call across as part of their own
restructure. `EventAnalysisView` and `ClusteringView` are the next two cheapest at 2 methods
and 4 methods respectively.

**A trap specific to what is left.** Many `npt.` uses are *type annotations* on signatures,
not computation - they do not go away by moving a body, only by the method ceasing to take or
return an array. The related failure is already recorded: annotating a base member as
`Optional[pd.DataFrame]` put a pandas import in a View and the gate refused it;
`Optional[Any]` was the right trade for a member already scheduled for deletion. **Count how
many of a file's points are annotation-only before pricing it**, or a file will look like two
points of body-moving when one of them is a signature change.

**Then Step 5**, which is the 690 removable lines in the three untouched families and is
scoped in its own section below. Nothing in Step 5 is blocked by anything still open in
Step 4.

### Owed, carried forward

- **The 4a exit-review item is still open**: an unresolvable experiment on the protein tab
  cannot be provoked with the available data, so that hard stop has never run against a real
  database. Reverting the guard fails exactly one Controller test, so it is not unverified -
  but it is untried where it matters.
- **Making raw SQL subset filters work** is queued as a post-refactor feature,
  `future_refactors_and_features.md` Part 13, which also prices withdrawing them from the UI
  instead. Step 4a's breaking change stands until then.
- **Method rules 65-68** were added this session and the artifact is at **v45**.

## Step 4a handoff, 2026-09-12 - COMPLETE

**Step 4a is done, the manual pass is run, and CI is green on `7fbeca37`.** `global_signal.emit` has **no callers left
in the analysis tabs**: boundary rule 1 reads **0**, down from 75 at the start of the step
and 13 at the start of the final session. Allowlist total **25** - 20 forbidden View imports
(Step 4c) and 5 Controller reach-ins (4d). Suite **3,785 passed / 16 skipped**; all static
gates and `sphinx-build -W` green.

**One post-merge fix, worth knowing about before trusting a green local run.** CI aborted at
**exit 134** after the merge, in `sample_metadata_db` fixture setup. Cause: `Triad.close()`
closed the data plugins without killing the tab's workers first, which the app's own
shutdown does - so a flow test that started an export left a live `QThread` for Qt to
destroy. This was the "intermittent exit 127" that had been recorded as unexplained
flakiness and was in fact **three runs out of three** on one module, every test passing.
Fixed in `7e13af11`, pinned by two tests, and the `future_fixes.md` entry deleted.

Twelve commits, eleven on the branch plus the post-merge harness fix: merge-artifact doc fixes, the CSV export regression, the Raw Data range
trim, Protein's event-plot chain, `construct_event_data_query`'s tuple, Protein's
distribution subsets, `_commit_fits`, the base's last emit, the `call()` docs, and the
manual pass's own fixes.

**Six defects were found rather than converted**, every one invisible to the suite:

- `MetadataController.load_event_subset` bound `construct_event_data_query`'s declared
  `Tuple[str, str]` to one name, so a filter the database refused was neither reported nor
  able to stop the plot. **The Controller test pinned it**, because its stub answered with a
  bare string - rule 42's failure mode on the return value.
- The CSV subset export is a generator, so its own empty-subset check fired on the worker's
  first advance, after the export index had advanced. `changelog.md` had claimed this fixed
  for three days.
- `sphinx-build -W` is a gate in two workflows and had been failing since Step 3b, on a
  property the autodoc generator emitted as a method.
- **The protein tab's `_raw` filter branch had never worked**, on any version. It handed a
  complete `SELECT` where `load_event_data` expects a WHERE-clause body; measured, SQLite
  rejects it and the generator yields nothing, silently. Deleted, and raw filters are now
  refused at the plot entry points. This **voids the queued "share it with the metadata tab"
  item** - not a gap, a branch that does not work.
- A column that is NULL for every row *in the selected scope* comes back from pandas as an
  object array, and `np.isnan` cannot take it. Pre-existing in `MetaView`, whose 38 test
  references for that method are every one a `Mock`.
- Both protein distribution modes drew empty axes in silence for a subset holding no events.

**Manual pass, Windows, 2026-09-12.** Nine checks across the three tabs; eight passed or
were fixed and re-passed. One could not be run:

- **Open, for the exit review: an unresolvable experiment on the protein tab (#5).** The
  available data cannot provoke a failed experiment lookup, so the new hard stop has never
  run against a real database. Reverting the guard fails exactly one Controller test, so it
  is not unverified - but it is untried where it matters.

**Next, re-derived 2026-09-12 and decided.** Four plan claims moved; see
`DECISIONS.md` for the two calls taken.

| Claim as written | Verdict | Measured |
| --- | --- | --- |
| 3d moves **two** methods, **15** call sites | overstated 2x | **one** method, **8** call sites, one each in 8 methods. 3d-pre deleted the frame form; 3e moved the range helpers down |
| 3d blocked on a synchronous View-to-Model path | **still true** | `self.model` appears **0** times in all five Views and `MetaView`. 4a established the pattern, it did not give Views a Model |
| 3d's allowlist win | unrecorded | **2, and the best-placed two left** - the helper is the only user of `numpy` *and* `numpy.typing` in `MetaView`, so the published plugin base sheds numpy entirely |
| 3d's helper is a **pure array transform** | **wrong** (2026-09-13) | It emits `add_text_to_display` **three times** (`MetaView.py:702`, `:717`, `:752`) and reads `self.__class__.__name__`. Silencing them fails exactly 2 characterization tests |
| 3d's helper is **unpinned**, 38 refs all `Mock` | **stale** (2026-09-13) | `tests/unit/views/test_meta_view_characterization.py` covers it with **12 behavioural tests**. The 38 `Mock`s are `test_metadata_view.py` alone |
| 3d is a step of its own, run before 4c | **folded into 4c** (2026-09-13) | **7 of its 8 call sites are already 4c targets**. Doing 3d first restructures them twice |
| a round trip cannot resume a loop from a Qt callback | **overstated** (2026-09-13, same day) | Measured: a same-thread Qt signal is **synchronous**, the slot completing before `emit()` returns. What is unavailable is a *return value to the emitting line*. The 3d conclusion never depended on this |
| 4c's value per tab | uncounted | **Protein 3 for 2 methods** (`scipy.optimize` + `scipy.signal` both only in `_fit_double_gaussian`, `scipy.stats` only in `_fit_and_sanity_check_double_gaussian`); **Metadata 2** (`scipy`, `scipy.optimize`), its `scipy.stats` having 4 users |
| 4c Metadata is worth **2** | **understated** (2026-09-13) | Worth **3**. `scipy.stats`' four users are `_plot_1d_density`, `_plot_capture_rate`, `_plot_1d_histogram` and `_calculate_heatmap` - and **all four are already 4c targets**, so taking them together frees `scipy.stats` as well. Moving only the two the plan names leaves `iqr` behind in the other two and a later step has to re-open both |
| 4b moves SQL out of the widget: `_rebuild_event_id_cache`, `_resolve_event_db_ids`, `_fetch_event_data`, `_build_load_event_data_args`, the raw `SELECT` | **mostly done by 4a** (2026-09-13) | The View layer authors **3** SQL-bearing lines, all in `_reject_non_select_raw_filter`, and they *validate* a filter rather than build a query. `_resolve_event_db_ids` and `_build_load_event_data_args` no longer exist |
| 4b's raw-SQL surface is wider than recorded - 4 filter-dialog sites plus 2 commit methods | **now 5 arguments in 3 Controller methods** (2026-09-13) | `MetadataController.load_event_plot_data` (2), `ProteinController.load_event_plot_data` (2) and `ProteinController.commit_fits` (1). The filter-dialog sites are gone. **Counting rule, because the definition is the number:** an argument the analysis-tab layer *builds* and passes to a loader method that takes SQL - `query_database_directly`, `alter_database`, `load_event_data`, `construct_metadata_query`, `construct_event_data_query`, `validate_filter_query`, `export_subset_to_csv`. Passing a user's filter text or a column list through is marshalling, not authoring, and is not counted; by that rule 9 of the layer's 14 such calls are marshalling. A first attempt grepped for SQL keywords and gave 3, then a widened pattern gave 27 by matching the word "Select" in walkthrough prose |
| the correct destination shape | **already exists in-repo** (2026-09-13) | `ClusteringModel.drop_cluster_columns` builds its `ALTER`/`DELETE` and calls the loader itself, which 4c Clustering landed. It is the only SQL-authoring site in any Model, and the template the other three should match |
| **4b's value** | **zero on every gate** (2026-09-13) | No View or Controller imports `sqlite3`, so rule 2 cannot move; and the two promotion candidates are not byte-identical, so `*Controller.py` reads 0 identical / 0 removable and the ratchet cannot move either. The step is a layering fix, and has to be justified as one |
| 4d moves `subset_filters` **and** the three `_pending_*` to the Model | **two problems, not one** (2026-09-13) | `_pending_*` is per-request *context* parked on the widget and read back; the fix is to **thread it through the intent**, which deletes it, not to relocate it (rule 51's lesson applied to a request rather than an answer). `subset_filters` is real domain state and does belong on the Model. They have different fixes, different sizes and different value |
| 4d's rule-3 surface: **10** sites across two Controllers | **5, all on one base** (2026-09-13) | 3b promoted `relay_query` to `MetaSubsetTabController` and merged the two copies; the gate has read 5 since. All five are in that one method, reading `_pending_filter_name`, `_pending_filter_text` and `_pending_old_filter_name` |
| 4d's **12** public `subset_filters` reach-ins | **4** (2026-09-13) | Four direct dict touches in `MetaSubsetTabController` (`:569`, `:595`, `:596`, `:657`) plus one `restore_subset_filters` call. The 12 in `MetaSubsetTabView` are the View's own state, not reach-ins |
| 4d's value | **all 5 points, from the `_pending_*` half alone** (2026-09-13) | Threading the context removes every rule-3 violation: allowlist **19 -> 14** and rule 3 to **zero**. Moving `subset_filters` moves **no** gate - it is public, so rule 3 never saw it - and costs 157 test references across 82 test functions, 35 of them in e2e |
| bonus, unrecorded | **a promotion 3b missed** (2026-09-13) | `restore_subset_filters` is **21 of 22 lines identical** between the two tab Views, differing only in the controls-panel name - exactly what the `_subset_controls` accessor introduced in 3b exists to resolve (rule 44) |
| promotion: 65 identical lines of 73/78 | **re-measured** (2026-09-13) | They are Controller methods now at **122 and 129 lines, 94 identical**, ratio 0.749. Four real differences: an extra `action_label` parameter, an empty-`event_ids` guard Metadata lacks, `SELECT id` against `SELECT id, event_id`, and messages built from `action_label` |
| promotion: four surviving differences | **three, one inert** | 65 of 73/78 lines identical; Protein's empty-id guard cannot fire on the metadata side |

1. ~~**4c Protein first**, worth 3 allowlist points for two methods.~~ **LANDED
   2026-09-13** on `feature/step-4c-protein`, allowlist **25 -> 22**: `scipy.optimize`,
   `scipy.signal` and `scipy.stats` are gone from the View layer entirely and rule 2
   reads 17. The fit chain, `_double_gaussian` included, is on `ProteinModel`; its three
   callers go through `ProteinController`. **Manual Windows pass run 2026-09-13**, all
   three plotting surfaces working; one defect found that no gate could have - a
   distribution plot refused for too many channels reported only to the console, because
   `QtHandler` sits at `ERROR`. Its four existing tests assert on `caplog` and passed
   throughout. Fixed, with six tests that assert on the status panel instead.
2. ~~**Then 4c Metadata**~~ **LANDED 2026-09-13** on `feature/step-4c-metadata`,
   allowlist **22 -> 19** and rule 2 **17 -> 14**: `scipy`, `scipy.optimize` and
   `scipy.stats` are all out of the View layer and `MetadataView` is down from 6
   forbidden imports to 3. **Manual Windows pass run 2026-09-13** over the four plot
   types, which returned four defects and one non-defect. Three were **pre-existing**,
   established by reproducing them in a worktree at `develop` rather than by reading
   the diff: capture-rate bin widths accepted and ignored, a categorical histogram
   failing on NULLs, and an all-points histogram unpacking the previous plot type's
   data. The fourth was a scope silently widened back to every channel by any
   structure refresh, also pre-existing and on the shared subset base. The non-defect
   was a status message reported as never sent that had always been sent - the panel
   could not show that an identical line arrived twice, which is now fixed with a
   timestamp. All fixed on this branch; see method rule 64.
   Worth 3 rather than the 2 the plan recorded. Re-derived 2026-09-13 before starting. Scope is the **four**
   methods that use scipy, not the two the plan named: `_plot_1d_density` (frees `scipy`),
   `_plot_capture_rate` (frees `scipy.optimize`), `_plot_1d_histogram` and
   `_calculate_heatmap` - the last two matter because `iqr` lives in all four, so
   `scipy.stats` only leaves if all four do. Allowlist **22 -> 19**, rule 2 **17 -> 14**,
   `MetadataView` 6 forbidden imports -> 3. `numpy` (11 methods) and `pandas` (7) stay.

   Four structural facts, all measured rather than assumed: the three `_plot_*` returns
   are **ignored** by `update_plot`, so a request/setter split is transparent to it;
   `_calculate_heatmap` takes no `ax` and is the clean one, but its return *is* consumed,
   so its caller `_plot_heatmap` is what gets restructured; `update_plot`'s
   `try/except ValueError` around `_plot_capture_rate` keeps working, because both
   `raise` sites sit before the scipy work and stay in the request half; and
   `_plot_capture_rate` emits `add_text_to_display`, so the split has to place that
   deliberately. Coverage is 7-14 direct calls per method, so **no pinning commit**.

   **Advances 3d by zero, deliberately.** Three of the four contain a logscale call,
   but the helper emits to the status panel and lives on `MetaView`, so it moves only
   when all eight of its call sites can convert together. Each request half therefore
   calls it *before* emitting and hands the Model arrays that are already filtered.
   `MetaView` keeps `numpy`/`numpy.typing` until 3d proper. `_plot_scatterplot` and
   `_plot_3d_scatterplot` are deliberately **not** in scope: they free no import, so by
   method rule 38 they do not belong in a step aimed at the allowlist.
3. **3d is folded into 4c and is no longer a step.** The logscale helper goes to
   `MetaModel` as originally planned, but each caller carries its logscale call across as
   part of its own 4c restructure, so no caller is rewritten twice. The utils-module
   decision of 2026-09-12 is superseded: the helper is not a pure transform. `DECISIONS.md`
   carries both the correction and the caller arithmetic.
4. **Then 4b, which is much smaller than recorded** - re-derived 2026-09-13 on
   `feature/step-4b-sql`. Step 4a took most of it: the View layer authors **3**
   SQL-bearing lines and all three *validate* a raw filter rather than build a query.
   What is left is **3 query-builders sitting in Controllers**, which is a layer out:
   the Controller assembles the SQL and then uses `self.model.call(...)` as a conduit
   to the loader, where Decision A has the *Model* make the plugin call. So 4b is now
   "SQL out of the Controller", not "out of the widget".

   **It moves no gate, and that is stated rather than discovered.** Nothing imports
   `sqlite3`, so rule 2 cannot move; the two promotion candidates are not byte-identical,
   so `*Controller.py` reads 0 removable and the ratchet cannot move either. Method rule
   38 says to check that before starting - here the answer is zero, and the step has to
   stand on the layering alone.

   **LANDED 2026-09-13.** Layer counts by the recorded rule: **View 0, Controller 1,
   Model 6**. One View site the scan had missed turned up on the way - `MetaSubsetTabView`
   appended `" LIMIT 0"` to a raw filter before validation, which is a string
   concatenation rather than a loader-call argument and so matched nothing; it moved to
   `MetaSubsetTabController`. The single remaining Controller site is that clause, and it
   stops there deliberately: going further wants a Model shared by both subset tabs, and
   there is no `MetaSubsetTabModel`.

5. **The promotion, re-measured after 4b - the blocker has changed.** The two
   `load_event_plot_data` Controllers are now 110 and 115 lines with 83 identical
   (0.738, barely moved), but the query construction 4b pulled out landed as two
   `resolve_event_ids` Model methods that are **49 of 50/55 lines identical, ratio
   0.933** - they differ only in the projection. So the near-duplication is concentrated
   rather than removed, and it moved layer. **What now separates the two Controllers is
   `action_label`**: the Protein copy takes it, guards an empty `event_ids` with it, and
   builds three messages from it. That is a question about what the user is told, not
   about SQL, which is the form the promotion decision should be taken in. The two
   `resolve_event_ids` are the better merge candidate and want a shared subset-tab Model
   that does not exist yet.

   **Manual Windows pass run 2026-09-13, all clear**, over both tabs' event plotting, the
   fit overwrite, and raw-filter validation. One thing confirmed rather than found: raw
   SQL filters are still refused for plotting on every path, which is Step 4a's deliberate
   breaking change and not 4b's doing. **Making them work is queued as a feature for after
   the refactor** - `future_refactors_and_features.md` Part 13, which also prices the
   smaller alternative of withdrawing them from the UI. The two
   `load_event_plot_data` bodies are 122 and 129 lines with 94 identical. Three of their
   four differences are about the query and the messages, and moving the query to the
   Models takes the largest one out, so 4b should be done first and the promotion judged
   afterwards rather than planned now. Note both live in the five-file `*Controller.py`
   family while `MetaSubsetTabController` does not, so promoting them to the base drops
   them out of the measured set: `functions` falls, `removable` stays 0, and the win is
   real but invisible to the ratchet (rules 24 and 36).

6. **4d's first half - threading the filter context - LANDED 2026-09-13** on
   `feature/step-4d-domain-state`. **Allowlist 19 -> 14 and rule 3 to zero**, which is
   the whole of the step's gate value and came from the half that deletes state rather
   than the half that relocates it. `filter_validation_requested` and
   `raw_filter_validation_requested` now carry the filter's name and the name it
   replaces; `validate_filter`, `validate_raw_filter`, `relay_query` and
   `MetaSubsetTabView.on_raw_filter_validated` take them as arguments; and the three
   `_pending_*` attributes and `clear_pending_filter_state` are gone with nothing left
   to clear.

   **A dead Controller method fell out of it.**
   `MetaSubsetTabController.on_raw_filter_validated` was a two-argument passthrough left
   behind by Step 4a, which replaced the bus round-trip it served with the
   `raw_filter_validation_requested` intent. Nothing connected to it or called it
   afterwards, and only its three tests kept it alive - which is method rule 42's shape
   at one remove: tests that exercise a method no production caller reaches keep it
   looking live. Worth a check of the connection sites, not only the call sites, whenever
   a converted emit leaves a slot behind.

   **Test fallout was 73 failures, and the shape of it is the point.** Almost all of them
   set `_pending_*` on the widget and then asserted on what the Controller did with it -
   they pinned the mechanism, not the behaviour. Those were deleted rather than
   re-pointed; the ones that asserted on an outcome were re-pointed by passing the
   context as arguments.

   **Found while verifying, and fixed in its own commit: restoring a session dropped the
   last-restored tab's subset filters.** Kyle reported it as Metadata keeping its filters
   and Protein not, and the cause is order, not tab: restoring a tab is
   `instantiate_analysis_tab` then `restore_session_state`, and only the first refreshes
   `plugin_history` - via the `update_plugin_history` it ends on, which snapshots every
   open tab while the one being restored still has an empty filter list. Each tab was
   corrected only by the sync that the *next* tab's instantiation happened to trigger,
   so the last one was saved empty and lost its filters on the following restore.
   Protein was simply opened second. `load_session` now re-syncs and saves once the loop
   has finished. **Reproduced at `develop` in a worktree before being called a defect**,
   per method rule 64, and the on-disk session file was read directly rather than the
   in-memory state - the in-memory restore was correct on both tabs the whole time, which
   is why unit coverage of `restore_session_state` never saw it.

   **Manual Windows pass run 2026-09-13, all clear.** Ten checks over both tabs: adding,
   editing and renaming assisted and raw filters, an empty filter text, a filter naming a
   column that does not exist, save/load to file, and a session round trip restored
   **twice** - the second restore being where the defect above used to bite. No defects.
   One checklist item was itself wrong: it asked for two filters added back to back
   *without closing the dialog*, which the UI does not allow, since the dialog closes on
   OK. The thing it was trying to probe - that nothing is carried over from one request to
   the next - is covered by adding two filters in succession, which passed.

   **The promotion is taken: `restore_subset_filters` is on the base**, 20 of 21 lines
   identical with the panel name the only difference. Invisible to the ratchet, as rules
   24 and 36 predict - the copies were never byte-identical so `removable` was already 0,
   and the base sits outside the measured `*View.py` family, so only `functions` moves
   (199 -> 197).

   **`subset_filters` does not move to the Model - decided 2026-09-13, see
   `DECISIONS.md`.** The plan flagged this as "a design decision, not a move", and the
   measurement settles it: **no Model reads the dict**, because 4b's query construction
   takes the filter *text* as an argument, so the Model would gain a field nothing in it
   reads while all **16 synchronous View reads** (11 `get_selected_filters()` on the plot
   and export paths, plus both filter dialogs, `_load_filter` and `_save_filter`) became
   round trips. No gate moves either way - it is public, so rule 3 never counted it -
   against 165 test references over 72 test functions, 35 e2e. **Re-measured: the plan's
   157/82 were stale**, the 82 by 4d's own test deletions.

   What was actually wrong is narrower and is fixed instead: `MetaSubsetTabController`
   reaches into `self.view.subset_filters` at four sites, mutating the dict in
   `relay_query` and copying it in `get_session_state`. Those become two View methods, so
   the Controller asks rather than mutates.

**Read before writing code:** method rules **42, 45, 50, 51, 52** in the artifact
(<https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>), plus **53-57**
earned in the final session: a generator's guards run on whoever advances it; a stub answered
from the caller rather than the collaborator pins the bug; a derived gate reaching zero is
success; a nested function can hide a static check; and **check that a branch can do its job
before improving what it displays** - one commit here fixed the display of a code path that
had never been able to return a row.

# Poriscope 2.0.0 Refactor Plan

Approved 2026-09-03. **Step 0 and the whole of Step 1 (Tiers A, B2 and C) landed
2026-09-04** and are pushed; Step 2 onwards is open. 1.9.0 is ready and uncut.

**Every measurement below is re-baselined on `develop` at `062ef6f`, 2026-09-04.** Step 1
landed after the original `fc4fdf7` baseline (46 files, +416/-779 under `poriscope/`), so a
ratchet anchored there would credit Step 1's deletions to the refactor. Re-verifying this
document against `062ef6f` corrected nine of thirteen checkable Step 3a sub-claims, six Step 2
claims and the Decision E figure; the corrections are inline below.

**Step 2 was checked a fourth time at `c9fe294`, 2026-09-05, when it was planned in detail, and
three more claims moved** — the allowlist seed (106 → **107**), the duplication baseline (not
reproducible; no measurement tool exists), and the golden target list (most named methods are
already covered; a different set has zero coverage). Two of those three changed what the work
*is*, not just its numbers. See Step 2 below.

Full write-up: <https://claude.ai/code/artifact/304ba119-d177-4918-90af-471d6de6bb80>

Excluded throughout by standing policy: `PeakFinder.py`, `Basic_PeakFinder.py`, `NanoTrees.py`.

## Why

The analysis-tab layer never grew a real Model, so the Views absorbed everything.

| Layer | Lines | Methods | Note |
| --- | --- | --- | --- |
| 5 tab Views | 11,557 | 259 | `ProteinView` 4,043; `MetadataView` 3,651 |
| 5 Controls widgets | 4,381 | 145 | all inherit plain `QWidget`; no base class |
| 5 tab Controllers | 1,411 | 81 | 114 `self.view.*` against 8 `self.model.*` |
| 5 tab Models | 298 | 7 | 4 of 5 are `def _init(self): pass` |

75 of 77 `global_signal.emit` sites are in Views, 0 in Controllers. Views import `hdbscan`,
`GaussianMixture`, `curve_fit`, `find_peaks`, `fast_histogram`, and author raw SQL.
641 removable lines of byte-identical methods across the 5 Controls files, 444 of them
identical in all five; ~600 duplicated lines *each* between `MetadataView` and `ProteinView`;
17 of 23 Metadata/Protein Controller methods identical.

No characterization tests exist. Coverage runs (`pytest-cov` landed 2026-09-04) but nothing
fails on a drop.

## Decisions

Reasoning is in `DECISIONS.md` (2026-09-03, two entries).

- **A.** The return-value signal bus becomes `get_plugin`/`call` on `MetaController` and
  `MetaModel`, with instances **pushed** down the existing notification path.
  Fire-and-forget signals (`plugin_state_changed`, `add_text_to_display`,
  `update_progressbar`, `create_plugin`) are unchanged.
- **B.** Controller mediation is kept. Commands View→signal→Controller→call→Model; results
  Model→signal→View with the Controller connecting. `RawDataController.calculate_psd` is the
  template.
- **C.** 2.0.0 takes the queued ABC breaks: the `"Kind"` schema key, splitting
  `MetaReader.load_data`'s `raw_data` arm, `close_resources` channel dispatch,
  `_write_data`'s 13 parameters, `MetaEventFinder`'s undeclared `Threshold`.
- **D.** 1.9.0 ships Tier A + B2 + C only. Tier B ships inside 2.0.0.
- **E.** Moved tests are re-pointed, test owner reviews. **Needs her agreement before Step 2
  starts** - see "The ask to Carolina" below, which scopes it and corrects the earlier
  "1,085 view tests" figure to 324. Re-pointing is *mostly* mechanical, not entirely: 175 of
  the 324 are a receiver rename, but 75 encode a same-object stub seam and 46 more assert on a
  `global_signal.emit` that Step 4a deletes.

## Sequencing

Tab by tab. Clustering first (969 lines, self-contained, no bus calls in the hot path), then
RawData/EventAnalysis, then Metadata/Protein. Full suite green at every step; one feature
branch per piece, finished into `develop` before the next starts.

```
Step 0 (measurement) ──┐
                       ├──→ Step 2 (tests, GATE) ──┬──→ Step 3 ──→ Step 6 ──→ Step 7
Step 1 (1.9.0)      ───┘                           ├──→ Step 4
                                                   └──→ Step 5 (parallel)
Decision A ──→ Step 4a ──→ Protein threading fix, and Step 5b's relay extraction
Step 3a — independent of the test gate, but gated on directory ownership.
```

Hard blocks:

- Step 2 blocks Steps 3–5 absolutely.
- **Ownership, not just tests.** `.github/CODEOWNERS` assigns `tests/` and
  `poriscope/plugins/analysistabs/utils/` **solely** to @Carogg28, and `poriscope/views/` and
  `poriscope/plugins/analysistabs/` jointly. Step 3a rewrites all five `*controls.py` inside
  that solely-owned directory and lifts shared code out into Kyle-owned `poriscope/utils/`;
  Step 3f moves `walkthrough.py` and `walkthrough_mixin.py` out of it. So 3a is **not** the
  un-gated escape hatch an earlier handoff called it - it is independent of Step 2 and gated on
  the same person.
- Tier A had to land before goldens are generated, or goldens encode known bugs — done
  2026-09-04, so Step 2 is now unblocked on this axis.
- Decision E must be agreed before Step 2 starts.
- Protein threading fix is already recorded as blocked on the emit-then-read conversion.
- **The boundary gate must be widened before any Step 3 promotion moves an emit or a
  `self.view._private` read onto a base.** `check_mvc_boundary.py`'s rules 1-3 scan hardcoded
  filenames under `poriscope/plugins/analysistabs/`; a base in `poriscope/utils/` is invisible
  to them, so such a promotion drops the allowlist without fixing anything. This is the real
  block on 3b (see 3b below), and 3c, 3d and 3g have the same shape. 3a was unaffected because
  none of the twelve methods it promoted contained an emit, a forbidden import or a private
  read — verified by the allowlist holding at 111 across all four of its commits.
- `new_plugin.py`'s analysis-tab half is already deferred until this lands; it becomes Step 6.
- `@register_action` records `func.__name__` and `MetaView.update_actions_from_json` replays
  via `getattr(self, name)` **on the View**. **5** decorator sites over 4 distinct names
  (`ClusteringView.py:141`, `MetadataView.py:304`, `:1234`, `ProteinView.py:683`, `:2818`), not
  the 11 recorded earlier - six of those hits were docstring prose. None is on any move list,
  but decorated `_update_distribution_ensemble` is the twin of the moving
  `_update_distribution_individual`, so splitting the pair breaks the symmetry the tests are
  written against. Moving a decorated method breaks saved `.json` action files.
- Any `MetaEventFitter` signature change forces lockstep edits in the three owner-held
  fitters, because `test_plugin_compliance` compares annotations by equality. Check in first.

## The ask to Carolina — agreed 2026-09-04 (Step 2 unblocked)

**Status: put to her 2026-09-04 and answered affirmatively the same day — green light to
proceed with the plan.** Decision E is satisfied, so **Step 2 is no longer gated**, and neither
are Steps 3a and 3f. What was asked is recorded below, because the agreement is only as wide as
the ask it answered.

**Confirmed on the Step 2 split: there is no split.** Part 1 asked which half she wanted to
write; the answer is that **the whole plan is ours and she will not write any of it**. So all
five Step 2 deliverables are ours - the characterization goldens over View methods, the SQL
goldens, the `ast` boundary test, the duplication ratchet and the five no-GUI tab flows - as is
re-pointing her existing unit and e2e suites in Steps 3d and 4a-4e. Do not offer test work back
and do not treat a test-shaped deliverable as a reason to stop. This is a standing exception to
the "test-writing is hers" rule **for this plan only**; compliance-gate blocks 1 and 7 in
`future_fixes.md` remain hers.

Decision E had been recorded as a one-line ask about tests and stalled for a day because nobody
could state it precisely. It is one conversation with one person, in four parts, and three of
them are not about tests. Carolina González (@Carogg28) solely owns `tests/` and
`analysistabs/utils/`, co-owns `poriscope/views/` and `analysistabs/`, and authored 203 of the
~358 commits under `tests/` (59 against 22 in `tests/unit/views/`, 71 against 3 in
`tests/e2e/`).

1. **Who writes Step 2.** This is the gate, so it is the part that unblocks everything. Of the
   five deliverables, the `ast` boundary test, the duplication ratchet and the five no-GUI flows
   are new files overlapping no existing suite and fit the standing carve-out; the
   **characterization goldens over View methods overlap her view suites** and are hers to take
   or hand over.
2. **Re-pointing when a method changes receiver** - the original Decision E, scoped to Steps 3d
   and 4a-4e. **324 test functions** reference a moving name (11.7% of the suite's 2,781), of
   which **175 are a receiver rename**. Cheaper than it looks: each affected unit test takes one
   receiver fixture named once in its signature, there is one construction site per file, and
   `_qt_mocks.shadow_signals` finds signals by introspection so it covers a Model's signals with
   no edit at all.
3. **What is not mechanical, said up front.** 60 entries stub a moving method *as a collaborator
   on the receiver* and 15 assert on that stub - a same-object seam a View/Model split breaks,
   almost all in `test_metadata_view.py`. 46 more assert on a `global_signal.emit` that Step 4a
   deletes (`global_signal` appears in 142 test functions). Beyond that, 108 test names contain
   `view`, ~50 controller-test docstrings say "forward to the view", and Step 4d touches her
   **e2e** suites too, where `subset_filters` appears 14 times in a single test inside lambdas
   and f-strings.
4. **Structural rewrites inside her directories.** Step 3a across all five `*controls.py` (444
   removable lines, only 12 test functions touched) and Step 3f moving `walkthrough.py` /
   `walkthrough_mixin.py`. Neither is gated on Step 2.

**Offer 3a as the pilot**: it is the smallest, it re-points no test (pulling a method up to a
base preserves every `view.method(...)` call site), and it is the cheapest way to see what
"reviewed as a diff" means before agreeing to the rest.

**The escalation exit was never needed**, but it is worth keeping the principle: an ownership
block is asked first and gets a stated exit rather than an indefinite hold, because `CODEOWNERS`
is advisory by deliberate choice and Kyle has final say. Do **not** re-derive or re-send the ask:
it is above, with its measurements, and it has been answered.

## Step 0 — measurement baseline (landed 2026-09-04, re-baselined at `062ef6f`)

Re-measured on `develop` at `062ef6f`, full suite green (2,948 passed, 2 skipped). Re-run any
row with the command beside it; these are the numbers Steps 3-5 are judged against, and they
supersede the `fc4fdf7` figures.

**Coverage** — `pytest --cov=poriscope --cov-report=term-missing`. Repo total **83%**
(21,441 statements, 3,693 missed). Every percentage below is unchanged from `fc4fdf7`; only
statement counts moved, so Step 1 neither improved nor eroded coverage. Analysis-tab layer:

| Module | Stmts | Cover | | Module | Stmts | Cover |
| --- | --- | --- | --- | --- | --- | --- |
| `ClusteringView` | 359 | 89% | | `ClusteringController` | 55 | 100% |
| `EventAnalysisView` | 456 | 87% | | `EventAnalysisController` | 57 | 100% |
| `MetadataView` | 1,457 | 91% | | `MetadataController` | 136 | 96% |
| `ProteinView` | 1,587 | 90% | | `ProteinController` | 127 | 97% |
| `RawDataView` | 673 | 87% | | `RawDataController` | 56 | 100% |

The four empty Models are 12 statements each at 100%; `RawDataModel` is 40 at 88%. The
`Meta*` bases are the weak spot: `MetaWriter` 69%, `MetaReader` 71%, `MetaModel` 73%,
`MetaDatabaseWriter` 73%, `MetaEventFitter` 74%, `MetaEventLoader` 76%.

**LOC per layer** — `wc -l`. Views 11,557 (Protein 4,043, Metadata 3,651, RawData 1,722,
EventAnalysis 1,172, Clustering 969); Controls widgets 4,381; Controllers 1,411; Models 298.

**Byte-identical methods** — AST parse of each family, `ast.get_source_segment` per
function, dedented and stripped, counted where the identical text appears in more than one
file of the family. Removable lines = duplicate copies beyond the first.

| Family | Files | Methods | Identical bodies | Removable lines |
| --- | --- | --- | --- | --- |
| `*View.py` | 5 | 259 | 23 | 351 |
| `*Controller.py` | 5 | 81 | 20 | 207 |
| `*controls.py` | 5 | 145 | 25 | 641 |

Of the Controls family's 641, only **444 lines across 10 groups** are identical in all five
files and so belong to Step 3a. The rest is 152 in Metadata/Protein pairs (Step 3b), 39 in a
4-of-5 group (`createButton`) and 6 in a 3-of-5 group. The total is unchanged from `fc4fdf7`;
Step 1 removed no duplicate method.

**1,199 lines total, and now reproducible**: `python scripts/measure_duplication.py` re-derives
this table exactly, and `--check` holds it against `.duplication-baseline.json`. The original
figure was produced by a one-off unversioned script and could not be re-checked; the committed
instrument confirms it — 23/20/25 identical bodies and 351/207/641 removable lines — and also
confirms Step 3a's 444 lines across the ten groups identical in all five controls files.
The plan's ~1,900 and the >= 2,500 target both include
near-identical code this measure cannot see (`ClassicCUSUM`'s 195-line override differing in
2 lines, the Chimera readers differing in 23 of 390), so treat 1,199 as the *floor* the
ratchet starts from, not the whole prize. Largest single wins: `create_info_button` and
`create_delete_button` at 29 lines x 5 files each, `create_add_button` 17 x 5,
`update_channels` 52 x 2.

**Emit count** — `grep -rc "global_signal.emit" poriscope/`. **75** in Views
(Protein 21, Metadata 20, RawData 14, EventAnalysis 13, Clustering 7), 2 in
`MetaModel`/`MetaController`, 0 elsewhere. **77 total.** `062ef6f` removed the two
`query_database_directly` calls that `_build_where_clause`'s deletion collapsed.

`pytest-cov==7.1.0` is declared, the stray `poriscope/pytest.ini` is deleted, and
`typing_extensions` is gone from all 38 modules and from `new_plugin.py`'s generated
template in favour of the native `typing.override` — verified by importing all 124
`poriscope` modules with `typing_extensions` blocked at the meta-path.

## Step 1 — Poriscope 1.9.0 (landed 2026-09-04)

All three tiers are in. Tiers A and B2 were rewritten at `fc4fdf7` after the original lists
(drafted from the 2026-08-25 audit) named work `0abd08c`/`41adc07` had already done, and were
then **re-verified again at `c8dc953` immediately before implementation**, which corrected
five further claims — recorded inline below. The lesson stands for every remaining step:
**re-verify a tier immediately before working it.**

**Manually verified on Windows 2026-09-04 and all good**: the `3.0-` timer dialog, the
eventfinder channel list populating, and both export paths — a legitimately-empty sublevels
table writing an empty CSV, versus a filter matching no events reporting on the status panel
with no dialog. That was the last outstanding item on these tiers, so **nothing blocks cutting
1.9.0**. Note this is *not* the 2.0.0 manual pass in the Verification section below, which is a
wider sweep (all five tabs through the walkthrough plus the multiselect popup path) and is still
owed for the refactor itself.

### Tier A — before goldens are generated (landed)

What landed, and what the second verification pass changed:

- Seeding, `zip(strict=True)`, the `format_axis_label` alignment, `timer_channels` and the
  loader `None`-split all landed as described below.
- **Corrections found at `c8dc953`:** the `format_axis_label` drift is **latent, not live** —
  every unit reaching `ProteinView`'s copy is a hardcoded literal, and `proteincontrols` has
  no units label, so the single-space unit that produces `Label ( )` cannot arrive; the
  `zip` item's "size the grid from the materialised list" is redundant once `strict=True`
  raises, and was dropped; `RawDataView`'s line numbers were each off by one (registration
  `:375`, emit `:376`, read `:384`), and `timer_channels` is also never cleared between
  finders, so a failed dispatch seeded one finder with another's channels; the loaders live in
  `poriscope/plugins/db_loaders/`, not `plugins/dataplugins/databaseloaders/`;
  `_parse_ranges` splits on **every** hyphen, not the first, so a two-hyphen segment was
  dropped as well as an empty-end one.
- **`get_column_units` was not fixed** — its `""` conflation is inert, since every consumer
  erases the distinction. `DECISIONS.md` 2026-09-04.
- **`ClusteringView.axes` was not fixed.** Verified latent: both unguarded reads are
  immediately preceded by a `_reset_actions()` call, and `update_plot` carries no
  `@register_action`, so replay cannot reach it out of order. A real fix needs an
  `Optional[Axes]` declaration plus handling at both reads, which belongs with the
  canvas-lifecycle work in **Step 3**. Requeued in `future_fixes.md` with the corrected
  ~75/26 attribute counts.
- **Failure signalling:** the split is empty-frame-for-no-rows with `None` **kept** for
  failure, because `_dispatch_to` swallows exceptions and leaves the caller reading a stale
  attribute. `DECISIONS.md` 2026-09-04.

The verified detail, kept for reference:

- `ClusteringView.py:660` `GaussianMixture(n_init=100)` is unseeded; add `random_state`.
  `PeakFinder.py:5817`/`:5850` already pass `random_state=42`, so the convention exists.
  `ProteinView._generate_vm_ensemble:3268/3284/3300/3352` draws from the global NumPy RNG and
  needs the same treatment; HDBSCAN at `ClusteringView.py:912` is deterministic.
- `MetadataView.py:2576-2586` `zip()` without `strict=` over 7 fitter sequences while
  `num_events` sizes the grid. **Latent, not live** — the sole caller (`:2393-2400`) appends to
  all seven lists unconditionally per event, so lengths are structurally equal today. If they
  diverged, `labelnum` is computed from `num_events` rather than the trip count, so *no*
  subplot would get an x-axis label. Add `strict=True` and size the grid from the materialised
  list; do **not** add it to the three inner label zips at `:2619/2638/2656`, which are
  deliberately pre-padded with `None`.
- `None` means both "query failed" and "no rows" in `SQLiteDBLoader._load_metadata:823-852`
  (empty result and `sqlite3.Error` both return `None` at `:844`), and
  `MetaDatabaseLoader.load_metadata:1162` is declared `-> pd.DataFrame` while returning `None`
  at `:1189`/`:1194` — `load_metadata_raw:1145` has the same defect and
  `query_database_directly:1280` adds a third meaning, "failed validation".
  **`get_column_units` is not an instance of this**: `None` there means only "query failed";
  the conflation is `""`, which means both "units are NULL" and "no such column".
  **`get_experiment_id_by_name:400` silently depends on the current behaviour** — its
  `result.at[0, "id"]` would `KeyError` on an empty frame, so it must be fixed in the same
  commit. So must `export_subset_to_csv:522/566`, which reject a legitimately-empty
  `sublevels`/`data` table as "Failed to load".
- `RawDataView.timer_channels` used before assignment; papered over by the autouse fixture at
  `tests/e2e/conftest.py:67-86`, whose own docstring concedes the defect. One assignment
  (`:350`), one read (`:385`). The bus dispatch is `DirectConnection` so the happy path works;
  a failed dispatch raises `AttributeError`, swallowed at `:391` as "Updating ComboBoxes
  failed". **The damage is permanent**, because `:376` registers the finder key before the
  emit and the enclosing guard never retries. Add `self.timer_channels: Sequence[int] = []` to
  `_init`, move the `:376` registration after the loop, and delete the fixture.
- `format_axis_label` drifted between `ProteinView.py:4052` (module function) and
  `MetadataView.py:3626` (method). The difference is exactly ` and unit.strip()` and it is
  **behavioural, not cosmetic**: `metadatacontrols.update_column_units_label:879-889` coerces
  a missing unit to the single-space string `" "` for display and `collect_parameters:1014-1016`
  reads it straight back, so ProteinView renders `Label ( )`. A third divergent copy is inlined
  at `ClusteringView.py:733` using `unit != " "` instead of `.strip()`. 12 call sites in
  MetadataView, 8 in ProteinView, none cross-module.
- **~75 attributes assigned only outside `__init__`** across the five Views (not 28), with 26
  defensive guards (6 `hasattr`, 20 `getattr(self, ..., default)`), not 23.
  `ClusteringView.axes` is confirmed: assigned only in `_reset_actions:159/161`, read unguarded
  at `:740`/`:763`, while MetadataView guards its equivalent with `getattr`.
  **`ProteinView.ax_hist`/`ax_vm` are not an instance of this** — both are `@property` over
  axes built eagerly by `_set_custom_display_area`, which is on the construction path.

### Tier B2 — smaller than advertised (landed 2026-09-04)

Two of the six original items were already fixed by `0abd08c`/`41adc07` on 2026-08-24: the
four `AttributeError` methods (`update_unit_label`, `reset_top_inputs`, `setLanguageChecked`,
`setThemeChecked`) and `text_menu_widget`'s duplicated `QTimer.singleShot` plus stray
`print()`. What remains:

- **Landed 2026-09-04**: deleted `poriscope/views/widgets/walkthrough_steps.py`. Its duplicate
  tuple was real but had no user impact — `get_global_walkthrough_steps` had zero callers and
  all 394 lines were dead; each View carries its own live `get_walkthrough_steps`. Also
  deleted `FloatRangeLineEdit.get_values`/`used_floats`, uncalled and expanding `"3-5"` into 21
  values at 0.1 steps.
- `MainView.connect_signals:242-249`'s `isinstance(page, str)` branch is always dead — the list
  is a local literal three lines above the loop and all six values are bound methods. Delete
  the branch and correct `tests/unit/views/test_main_view.py:101-104`, whose docstring claims
  to cover it.
- **`TimeWidget` is a live user-facing bug, and not the one recorded.** The validator and
  `_parse_ranges` agree on a literal `end == 0.0`; they disagree on an *empty* end. `:69`
  substitutes `"0"` for an empty end string, so `"3.0-"` validates `Acceptable` and enables OK,
  while `_parse_ranges:188` has no such fallback, `float("")` raises, and the segment is
  dropped. `_on_ok` then stores `ranges = []` and `RawDataView.py:1118-1128` runs
  `find_events(channel, [], ...)` — event finding over no time at all, silently. Fix
  `_parse_ranges` (`split("-", 1)` plus empty-end to `0.0`), not the validator, which
  `tests/unit/views/widgets/test_time_widget.py:90-92` pins. **The `:78` unfiltered
  segment count was left alone**: `0-0` means the whole file and cannot legally be followed by
  anything, and `Invalid` on a `QValidator` refuses the keystroke outright, which is the right
  feedback. `DECISIONS.md` 2026-09-04.
- `IntegerRangeLineEdit` vs `FloatRangeLineEdit` leading-`-` handling is a **structural**
  difference only — no input produces different output, because the float version's every
  leading-`-` shape falls into its bare `except ValueError`. Nothing to rule on; Step 5d
  consolidates.

### Tier C — CI/tooling (landed 2026-09-04)

`requirements.txt` converted to UTF-8 (the Sphinx pins stay: `docs-check.yml` needs Sphinx and
the numeric stack from one file for autodoc); the mypy skew was three-way, not two (declared
1.9.0, hook v1.17.1, working venv 2.3.1) and the declared pin is now aligned to 1.17.1 with a
`DECISIONS.md` entry; `pytest.ini` gained `timeout = 300`; the dead `^tests/slow/` excludes and
the no-op `--exit-non-zero-on-fix` are gone from `.pre-commit-config.yaml`;
`tests/integration/data/` (455 KiB, referenced by nothing) is deleted.

### Deferred to 2.0.0 (Tier B)

Baseline-σ bias (+14.7%/+4.8%/+2.1% by chunk length, **two copies** — merge in 5a first);
`INSERT OR IGNORE` masking schema mismatch; `PRAGMA user_version` and the dead `extra_tables`
branch; session-restore type-name corruption; `Optional[int]` channel dispatch;
`test_plugin_compliance`'s import-order parametrization.

### Deferred into the refactor — do not fix twice

Duplication (~1,900 lines); `_setup_canvas`'s dead `num_channels`; `_factors` duplicated into
two subclasses that inherit it; `main_view.py:110-111`'s dead Figure; `hist_data`'s three
shapes; `MainView`'s navigation state as QLabel text; the five oversized `setupUi`; the
WARNING-level routine-state sweep.

## Step 2 — tests (GATE)

Re-verified at `062ef6f` (six claims moved, one bullet already done) and again at **`c9fe294`**
on 2026-09-05 when it was planned in detail — **three more moved, and two of them changed what
the work is**. Decision E is agreed and all five deliverables are ours.

### What the fourth pass changed

1. **Allowlist seed is 107, not 106.** 75 emits (21/20/14/13/7, confirmed) + **22** forbidden
   import statements over **13** distinct (View, module) pairs + 10 private-access sites. The
   bullet below instructs "add `fast_histogram`" and then quotes a total computed *before* that
   addition; `RawDataView.py:34` is the missing entry.
2. **The duplication baseline was not reproducible — now it is.** No measurement tool existed;
   Step 0's 1,199 / 68 came from a one-off unversioned script. `scripts/measure_duplication.py`
   now re-derives it and **confirms every figure exactly**, including Step 3a's 444 lines across
   ten all-five groups. So the number was right; it simply could not be checked, which is a
   different failure and a reminder that "unverifiable" is not the same as "wrong".
3. **The golden targets were wrong.** `_calculate_heatmap`, `_double_gaussian`,
   `_fit_double_gaussian`, `_compute_theoretical_blockages`, `_generate_vm_ensemble`,
   `_normalize_column_data` and both `_construct_all_points_histogram` copies **already have
   direct tests**. What has none: `RawDataView._gaussian_fit` (`:574` — its own source comment
   calls it "THE CRITICAL MATH FIX"), `RawDataView._get_baseline_stats` (`:467`, listed as
   covered in `test_raw_data_view.py:28`'s docstring with no such test),
   `MetaView._logscale_and_filter_dataframe` (`:789`), and `ProteinView._summarize_vm` (`:497`).
   Worst: **`MetaView._logscale_and_filter_multiple_columns` (`:696`) has 38 test references and
   every one is a `Mock`** — no behavioural coverage at all, on every 1-D and 2-D plot path.

### Execution — seven branches, in order

**Landed 2026-09-05: branches 1-4.** `develop` carries the harness, the duplication
ratchet, the MVC boundary allowlist and the characterization goldens. Suite at 3,136
passed / 2 skipped, up from 2,948 at the 1.9.0 baseline. Branch 5 is the coverage audit
added below; 6 and 7 are unchanged.

One branch per piece, finished into `develop` before the next starts. **Both gates are pytest
tests, not pre-commit hooks**, with measurement logic in `scripts/`: only a test is enforced by
all four CI workflows with no extra wiring and appears in `--marker-stats`, and the script keeps
"what do I have to fix" runnable on its own.

**1. `feature/step-2-test-harness`** — LANDED 2026-09-05. The shared prerequisite.
- `chore(test):` `pytest-regressions` pinned `==` in **both** `pyproject.toml [dev]` and
  `requirements-dev.txt` — `ci-branches.yml`/`ci-fork-pr.yml` install only from the latter and
  never read `pyproject.toml`; `release.yml` installs only the former. Register a
  `characterization` marker in `pytest.ini` (`--strict-markers` makes an unregistered marker a
  *collection error*). Add `pythonpath = .` — without it `tests.*` resolves only because
  `tests/e2e/conftest.py` is collected first, and `pytest tests/unit/views/test_event_analysis_view.py`
  alone fails with `ModuleNotFoundError: No module named 'tests'`.
- `docs:` `quality_control.rst` "Test Suite Configuration"; `changelog.md` under a new
  `## Poriscope 2.0.0: in progress`; `DECISIONS.md` on tests-not-hooks.

**2. `feature/step-2-duplication-ratchet`** — LANDED 2026-09-05. Second, not last: it makes Step 3a's "no copy was
lost" claim provable, and 3a precedes it.
- `chore(scripts):` `scripts/measure_duplication.py`, shaped like
  `scripts/check_plugin_module_level.py`. Algorithm per Step 0: AST-parse each file in a family,
  `ast.get_source_segment` per function, dedent + strip, group by identical text, removable lines
  = copies beyond the first. **Enumerate the five paths per family explicitly** — the fifth
  controls file is `eventAnalysisControls.py`, camelCase, and a `*controls.py` glob silently
  drops 742 lines (17% of the family).
- `test(scripts):` cover the instrument against small synthetic module texts, not the real tree,
  so the tests do not move when the refactor does.
- `test:` `.duplication-baseline.json` (precedent: `.pydoclint-baseline.txt`) plus the ratchet.
  **Exact match, not `<=`** — a commit that removes duplication lowers the baseline in the same
  commit, which is how the win gets recorded instead of accruing as slack. Correct Step 0's table
  to the re-derived numbers.

**3. `feature/step-2-mvc-boundary`** — LANDED 2026-09-05. The headline metric; this reaching 0 *is* Steps 3–5 finishing.
- `chore(scripts):` `scripts/check_mvc_boundary.py`. Three rules: no View contains
  `global_signal.emit`; no View imports numpy/scipy/sklearn/hdbscan/pandas/**`fast_histogram`**/sqlite3;
  no Controller reads a `view._private`. `sqlite3` contributes 0 today (Views build SQL as
  f-strings) and stays as a ratchet. **Pin the rule's exact definition in the module docstring —
  the definition *is* the number**: `numpy.typing` counts as `numpy` for the pair count but as its
  own `ast.Import` node, and that ambiguity is what produced the unreproducible 21/12.
- `test:` `.mvc-boundary-allowlist.json` seeded at **107**, keyed by file and symbol rather than
  line number so ordinary edits do not churn it, plus the exact-match gate.
- `docs:` `changelog.md` and a `DECISIONS.md` entry recording the rule definition. (The
  106 → 107 correction is already applied above and in the Verification table.)

**4. `feature/step-2-characterization-goldens`** — LANDED 2026-09-05. Pins the surface
nothing tested.
`pytest-regressions` where the output is an array or DataFrame; plain explicit assertions for
scalars, strings and short tuples. Keep samples small so every golden stays well under
`check-added-large-files --maxkb=123`.
- `test(views):` the two `_logscale_*` filters and the five range helpers, in `tests/unit/utils/`.
  Pin the divergence Step 3d proposes unifying: `~np.isnan` masking vs `df.dropna()` (which also
  drops nulls in columns nobody asked to log), `return ()` vs returning the *original object* on
  empty, and the `astype(np.float64)` the frame version forces. Replace `test_protein_view.py:1138`
  `TestRangeHelpers`' `or`-chained assertions — `_shift_ranges` **reflects** rather than translates
  a multi-element range, which is unpinned.
- `test(views):` `_gaussian_fit`, `_get_baseline_stats`, `_gaussian`; correct the stale coverage
  roster at `test_raw_data_view.py:28`.
- `test(views):` `_summarize_vm`, all three branches.
- `test(views):` equivalence tables — three `_factors` copies (`MetaView.py:139`,
  `RawDataView.py:109`, `EventAnalysisView.py:121`) and three `format_axis_label` copies
  (`ProteinView.py:4037` module function, `MetadataView.py:3645` method, and the **inlined,
  genuinely divergent** `ClusteringView.py:731-742`, which does not strip a trailing `(...)` and
  accepts `"  "` where the others reject it). Pin the divergence so Step 3's merge is a decision.

Reuse `_qt_mocks.shadow_signals` and the `__new__`-bypass fixture (`test_protein_view.py:108-161`);
`tests/unit/views/conftest.py` gives dialog patching and widget/GC teardown free. **Do not mock
the view's `logger`** — it blinds `caplog`.

**5. `feature/step-2-refactor-coverage-audit`** — **the criterion branches 1-4 were not built
to.** They pinned what had *zero* behavioural coverage plus equivalence for the copies Step 3
merges. The standing criterion is wider and better defined: **every method the refactor moves
or deduplicates must be covered**, derived from the refactor's own lists rather than from a
judgement about which methods look thin.
- `chore(scripts):` an audit that enumerates the affected set and reports what is unpinned.
  The **deduplicated** half is machine-derivable - `scripts/measure_duplication.py` already
  names every method in every duplicate group, **66 distinct methods**. The **moved** half is
  prose in Steps 3d and 4a-4e below and has to be written out explicitly before it can be
  checked; that list becomes part of the audit's input.
- **Counting call sites is not measuring coverage.** `_logscale_and_filter_multiple_columns`
  had 38 references and every one was a `Mock`, so it looked covered and was not. The audit
  must discriminate direct calls on a real instance from mock substitutions, and a naive
  reference count scored 64 of the 66 dedup methods "covered" on exactly that flawed basis.
- Known already from a first pass: **`_on_sizes_checkbox_toggled`** appears in
  `test_metadata_controls.py:108` *only as a comment*, and **`notify_plugin_state_changed`**
  appears in `tests/` only as stub definitions. Both are real zero-coverage cases.
- `test:` close the gaps the audit finds, then check the audit in so Steps 3-5 cannot move or
  merge a method that nothing pins.
- **Progress 2026-09-05.** `scripts/check_refactor_coverage.py` and its tests landed on the
  branch (`af14745`); suite 3,151 passed / 2 skipped. First run: **284 targets, 273 pinned,
  11 runs only, 0 untested.** The 11 are five `notify_plugin_state_changed` (now closed,
  23 tests), two `_on_sizes_checkbox_toggled`, `check_column_exists`/`set_column_exists`
  (Step 3e), and `ProteinView._resolve_event_db_ids` / `RawDataView._start_eventfinder`
  (Step 4a). **All 11 are now closed**, with 71 new tests across four files:
  `test_plugin_state_notifications.py` (23), `test_controls_bins_validator.py` (9),
  `test_column_exists_relay.py` (10), plus `_resolve_event_db_ids` added to
  `test_protein_view_characterization.py` and `_start_eventfinder` to
  `test_raw_data_view_characterization.py`. **Decided 2026-09-05:** the gate is *split*. Its structural half
  runs under plain `pytest` everywhere (`tests/unit/scripts/test_refactor_coverage_gate.py`);
  its execution half runs where coverage already exists — `ci-internal-pr.yml` now emits
  `--cov-report=json` and invokes the script. Exit is strict: anything not `PINNED` fails,
  `RUNS ONLY` included. Reasoning in `DECISIONS.md` 2026-09-05.
  **Audit now reports 284 targets, 284 pinned.**

**Note on line coverage.** It is the wrong instrument for this and should not be used as the
audit's measure. The five Views were at 87-91% *before* any characterization test existed, and
adding them moved the numbers by at most one point - those lines already executed under the e2e
suite, and nothing asserted the values. Post-branch-4: Metadata 91%, EventAnalysis 87%,
RawData 88%, Protein 90%, Clustering 89%, `MetaView` 92%.

**6. `feature/step-2-sql-goldens`** — LANDED 2026-09-05. Today **no test anywhere asserts on generated SQL text**;
all 110 tests in `test_meta_database_loader.py` use substring containment, so a refactor could
reorder joins, reassign aliases or change the projection and every one would still pass.
- `test(db):` exact-text goldens over `construct_metadata_query` (`:877`) across the shapes those
  classes already enumerate, pinning all three tuple elements.
- `test(db):` direct tests for `_split_on_opaque_spans` (`:712`), `_references_column` (`:763`),
  `_qualify_conditions` (`:785`), `_find_ambiguous_id` (`:835`) and `_end_of_subquery` (`~:695`) —
  **none has one**, and `_split_on_opaque_spans`' documented `"".join(result) == input` invariant
  is never asserted.
- `test(views):` the View-authored SQL, pinned *before* the refactor moves it into the loader.
  `ProteinView.py:1778` was already pinned in branch 5 via `_resolve_event_db_ids`;
  `ProteinView.py:1957-1967`'s `scoped_query` is pinned here including both mis-fires of its
  naive `"WHERE" in query.upper()` test. Metadata's twin **was** pinned only indirectly —
  inline, 120 lines into a 244-line orchestrator — until Step 4a moved that whole chain to
  `MetadataController.load_event_plot_data`, where `test_metadata_fetch_slots` drives it
  directly. The projection difference against its Protein twin (`id` vs `id, event_id`) is
  still asserted, because Step 4b has to reconcile them.
- **Two findings from verifying the goldens are actually sensitive.** The alias map at
  `MetaDatabaseLoader.py:1021-1029` feeds the projection and the WHERE qualification while the
  JOIN's `ON` clause hardcodes `s.`, so renaming an alias emits invalid SQL — latent today,
  live the moment Step 4b touches it. And a case named "duplicate columns are collapsed" was
  simply wrong: a repeated column is projected twice.

**7. `feature/step-2-tab-flows`** — LANDED 2026-09-06. Five flows, load → filter → plot → export, asserting on
exported CSV content rather than widget state.
- `test(integration):` `tests/integration/flows/_triad.py`. **This rung does not exist**: the three
  existing `*_no_gui.py` build no View or Controller, and there is no headless triad fixture
  between the mock-only unit controller tests and the click-driven e2e suites. Build it from the
  e2e construction at `tests/e2e/raw_data/test_trace_load_navigate_psd.py:102-120`, driving the
  controller API directly instead of the menubar. Reuse `tests/integration/conftest.py`'s
  `sample_*` fixtures and the four currently-unused `make_synthetic_*` factories, and the
  `Type = None` wiring idiom at `test_raw_data_instantiation_pipeline_no_gui.py:69-86`.
- `test(integration):` one tab first, to prove the harness. Where a flow waits on writer output,
  wait on committed **rows** via `sqlite_row_count` (`tests/e2e/_helpers.py:410`), never on table
  presence — `DECISIONS.md` 2026-09-03.
- `test(integration):` the remaining four. The `integration` marker is applied by path; do not
  hand-apply it.
- `docs:` close out Step 2 here, in `changelog.md`, `DECISIONS.md`, `future_fixes.md`, and the
  artifact.
- **What landed.** `tests/integration/flows/_triad.py` builds a real
  `MainModel`/`MainView`/`MainController` plus one tab in ~0.3 s each, with two bypasses only:
  the tab is created by calling `MainController.instantiate_analysis_tab`, which is what the
  menu action's signal reaches, and plugins are registered by handing a configured instance to
  `DataPluginController.model.register_plugin` and emitting the same `update_available_plugins`
  notification the real path emits. Then one flow per tab, 20 tests total: Metadata (CSV,
  six tables per subset), Clustering (database write, with every committed label compared back
  to the id it was computed for), RawData (committed event rows plus channel attribution),
  EventAnalysis (metadata rows plus the experiment row), Protein (plot then CSV export).
  Every flow is driven through `handle_parameter_change` action names, so **none of them names
  an internal method** and Steps 3-5 can move those methods freely.
- **Three waits were wrong, all caught rather than assumed.** `not model.workers` is true only
  before the first key appears, since `workers` is keyed metaclass then channel. A predicate of
  "any CSV with rows in this folder" was satisfied instantly by a *previous* export's files. And
  a commit wait on `row_count > 0` passed in isolation and failed the full suite at
  `assert 1 == 5`, because rows land incrementally on a worker thread — the same failure
  `DECISIONS.md` 2026-09-03 records, made again inside a file whose own docstring cites that
  decision.

### Step 2 exit review — DONE 2026-09-06. Five gaps found, all closed; Step 3 may start

Measured at `578b05e` on `develop`. Suite 3,300 passed / 4 skipped (2,948 at the 1.9.0
baseline). All three gates green. Repo coverage 83%, unchanged, with 3,593 missed statements
against Step 0's 3,693.

**Q1 — is everything that needs verifying testable?** Yes for Steps 3a-3g and 4a-4e, once the
audit's own list was corrected. **The audit was measuring an incomplete target set**: Step 4c
names `_construct_event_overlay`, `_plot_1d_density`, `_plot_capture_rate` and
`_update_distribution_individual` explicitly and none was a target, because the moved half of
the list had been hand-picked by how easily a method could be tested rather than by what the
step moves. Seventeen entries added (284 → 298); only two were unpinned and both are now
closed. **Audit: 298 of 298 pinned.**

**Correction, 2026-09-06: it is 308, and the invariant is the ratio, not the count.** The
target list is *derived*, not baselined — `check_refactor_coverage.deduplicated_targets()`
importlib-loads `measure_duplication.py` and calls `measure()` live. `8fe18359` added the
`eventfitters`, `datareaders` and `views/widgets` families to that instrument, which added
targets to this one, and nothing recorded it. **Record "100% pinned", never a fixed count**:
the number falls by design as each dedup step lands (Step 3a alone takes it to 248).

**Q2 — what checks are still missing?** Five, listed below with what each would cost.

**Q3 — have the gates' assumptions drifted?** Two figures in this document have:
- `self.view.subset_filters` reach-ins are **8**, not 12 — four each in `MetadataController`
  and `ProteinController`, and none anywhere else. Corrected in 4d below.
- The `@register_action` count **holds at 5**, verified by AST rather than grep; a naive grep
  gives 11 because six mentions are docstring prose, which is what produced the original
  wrong figure.
Everything else re-derives: `test_every_moved_target_exists` is green, and the emit-bearing
and SQL-authoring derivations still find what their steps describe.

**Q4 — is the manual Windows pass still the only cover for the platform-conditional paths?**
Yes, and it need not be. There are **10** platform-conditional sites, two of them in
`multiselect.py`. `test_multiselect.py` and `test_multiselect_filter.py` now exist but neither
patches `sys.platform`, so CI on Linux only ever builds the `QWidget` container and the
`QDialog` one that actually ships is never constructed. Parametrizing those two tests over the
platform is cheap and would convert the most fragile part of the manual pass into a real test.
**CLOSED** by `tests/unit/views/widgets/test_multiselect_platform_branch.py`, which builds both
containers on either host. The manual pass is still owed — only a human can see a popup fail to
dismiss or leave a ghost window — but a *structural* change to the Windows branch now fails in
CI. Note only `multiselect.py` has the branch; `multiselect_filter.py` uses `QDialog`
unconditionally, which is asserted so the asymmetry is not rediscovered.

#### The five missing checks — ALL CLOSED 2026-09-06

1. **The duplication ratchet covers only the three analysis-tab families.** Measured with the
   same instrument, the unratcheted families hold **772 removable lines** — `datareaders` 435,
   `eventfitters` 275, `views/widgets` 62 — against the 1,199 that are ratcheted. That is
   exactly the work Steps 5a and 5d do, with no instrument on it, and 772 is itself a floor
   since byte identity cannot see `ClassicCUSUM`'s 195-line override differing in two lines.
   **CLOSED.** `FAMILIES` now covers `eventfitters`, `datareaders` and `views/widgets`,
   taking the measured total from 1,199 to **1,889**. `PeakFinder.py`, `Basic_PeakFinder.py`
   and `NanoTrees.py` are excluded by name and asserted absent: their logic is another
   developer's, so ratcheting over them would fail on their owner's commits.
2. **Nothing pins `MetaView`'s abstract surface.** `test_plugin_compliance` *reads*
   `__abstractmethods__` to check subclasses implement it, but never asserts the set itself, so
   3a-bis making `_set_control_area` concrete would pass silently — and Decision C lists the ABC
   breaks 2.0.0 intends to take, which is only meaningful if an unlisted one fails.
   **CLOSED** by `tests/unit/plugins/test_mvc_base_contracts.py`, which pins all three MVC
   bases' abstract sets exactly.
3. **No layering rule.** Step 3f's whole point is that `views/main_view.py:53,58`,
   `views/widgets/add_subset_filter_dialog.py:30` and
   `views/widgets/clustering_settings_widget.py:52` import *up* from `plugins/analysistabs/`.
   Nothing asserts that, so 3f's completion is unobservable. **A fourth rule in
   `check_mvc_boundary.py` — no `poriscope/views/` module imports from `poriscope/plugins/` —
   costs a few lines and starts at an allowlist of 4.**
   **CLOSED.** Rule 4 added; allowlist 107 → **111**. Verified by adding an inversion to
   `main_controller.py` and watching the gate name it.
4. **Nothing replays a saved `.json` action file or session.** There is **no checked-in
   `.json` fixture anywhere in `tests/`**, and `update_actions_from_json` is asserted only on a
   *mock* view. Step 7 records that saved action files are user data and that moving a decorated
   method breaks replay; the same applies to `get_session_state`, which 4d changes.
   **CLOSED** by `tests/unit/views/test_saved_state_replay.py` against a checked-in fixture
   (which needed a `.gitignore` negation, since `*.json` is blanket-ignored). It pins the risk
   as current behaviour: **an action whose method has moved is silently skipped** — no error,
   no log line, a partial replay the user cannot detect.
5. **Autodoc output is unchecked.** Nothing in `tests/` mentions `automethod`. Step 3a would
   silently drop ~50 directives (the generators emit own methods only and skip classes with no
   docstring, which all five controls files lack), and 3f moves modules whose pages are keyed
   off the module path.
   **CLOSED, and measuring corrected this twice.** The five controls classes have no docstring
   and are documented anyway, carrying **143 `automethod` directives**; the generator writes a
   docstring only if present and documents the class regardless. And
   `metaclasses_generate_autodoc.py` scans `poriscope/utils/` as a *directory*, so a new
   `MetaControls.py` is picked up with no registration. **3a's autodoc risk is therefore small.**
   **3f's is real**: the generators scan only `poriscope/utils` and `poriscope/plugins`,
   `poriscope/views/` is covered by neither, and moving the walkthrough modules there would
   delete the four pages they own (`IntroDialog`, `Overlay`, `StepDialog`, `WalkthroughMixin`).
   Gated by `tests/unit/scripts/test_autodoc_coverage.py`.

#### A sixth gap, found 2026-09-08 — nothing asserted the golden net was armed

`pytest-regressions` is declared correctly in **both** dependency sources and was
nonetheless absent from one working environment. Every golden then errored at **setup**
with `fixture 'num_regression' not found` — four errors beside 3,400 passes, which reads
as an environment nit rather than as *the entire numeric golden net not running*. That net
is what licenses Step 4 to move computation at all, including `RawDataModel.gaussian_fit`,
whose own comment calls it "THE CRITICAL MATH FIX" and which the audit found had no
behavioural coverage.

None of the three gates can see it: the audit reads a coverage JSON, so an uncollected
test is indistinguishable from one that never existed. **CLOSED** by
`tests/test_safety_net_is_armed.py`, verified red-then-green — with `regressions`
deregistered both tests fail naming the cause and the install command. The plugin
registration name was measured, not guessed: it is **`regressions`**, and neither
`pytest_regressions` nor `pytest-regressions` resolves; `pytest-datadir` is asserted too,
since the goldens fail without it as well.

#### Two things the review confirmed rather than found

- **`createButton`'s divergence is real and unpinned.** `eventAnalysisControls.py` omits the
  `setStyleSheet("")` the other four have. Nothing asserts it, so promoting the majority version
  in 3a would change EventAnalysis's behaviour silently. **CLOSED** — pinned in
  `test_duplicated_helpers.py`, including that the four majority copies are byte-identical so
  "the majority version" is well defined, and that the stylesheet reset is the *only*
  difference.
- **The `Meta*` coverage worry was aimed at the wrong files.** 69-76% describes the *data-plugin*
  bases — `MetaWriter` 69.0%, `MetaReader` 70.5%, `MetaDatabaseWriter` 72.7%, `MetaEventFitter`
  73.8% — which Step 5b touches. Steps 3d and 4a-4e land in `MetaModel` (**77.9%**), `MetaView`
  (91.8%) and `MetaController` (97.1%). `MetaModel` is the weakest of the MVC triad bases and is
  the destination for the moves, so that is the number to watch, not the data-plugin ones.

### Original scope of the review, kept for reference

**Standing instruction, 2026-09-05: after branch 7 lands, re-assess the plan in light of
where the tests, pins and golden files actually ended up.** Step 2 was specified before any
of it existed, and four verification passes have already moved claims in Steps 3a, 3c, 3d and
4d. The review is not a formality; it is the last point at which a missing check is cheap.

What it has to answer:

1. **Is everything that needs verifying actually testable?** For each of Steps 3-5, name the
   observable that would fail if the step went wrong, and confirm something asserts it today.
   A step whose only evidence is "the suite is still green" is not covered - the suite was
   green before Step 2 started, with 11 refactor targets exercised only in passing.
2. **What checks are still missing?** Candidates already visible: nothing pins the
   `@register_action` replay path against a saved `.json` action file, which is user data;
   nothing pins `get_session_state` round-tripping a real 1.x session file, which Step 4d
   changes; and no gate holds the `Meta*` bases' coverage, which is where Steps 3d and 4a-4e
   land and which sits at 69-76%.
3. **Have the gates' own assumptions drifted?** Re-run all three, re-read the audit's
   hand-written `MOVED` list against the step descriptions, and confirm the emit-bearing and
   SQL-authoring derivations still find what the steps mean by them.
4. **Is the manual Windows pass still the only cover for the platform-conditional paths?**
   If so, schedule it against 3a rather than discovering it late.

Record the outcome here and in the artifact before starting Step 3.

### Already in place — do not rebuild

- **`test_plugin_compliance` already covers the triad** (all three bases, 15 of its 71 tests). The
  real gap is that `MetaModel` has exactly **one** abstract method, which 4 of 5 tab Models
  implement as `pass`, so `[MetaModel-*]` passes no matter what the refactor does to the Model
  layer. The same equality comparison that binds the owner-held fitters applies to `MetaView`'s
  five abstract methods once Step 3 promotes into the base.
- **`tests/e2e/` is already a characterization net** — 16 files, 5,469 lines, a full flow per tab
  driven through clicks, naming almost no internal method. The exception is exactly what Step 4d
  moves: `subset_filters` in 4 files, `view._analysis_mode`/`_display_mode` in 2 more.
- **Destination coverage stays absent, by design.** `tests/unit/models/` holds 3 files, only
  `test_protein_model.py` (64 lines, 8 tests) covers a tab Model, and `MetaModel` (363 lines, 12
  methods) has no test file. Step 2 does not close that; the goldens make the move observable and
  the destination's coverage comes with the move, in Steps 3d and 4a–4e.

### Deferred out of Step 2 — file, do not fix

The 13 dead `sys.path` shims in the e2e modules (placed *after* the import they exist to enable);
`test_raw_data_view.py` and `test_metadata_view.py` mocking the view's `logger` against
`_qt_mocks.py`'s explicit warning; `tests/conftest.py:8-15` referencing a conftest deleted in
`c99249ea`; `ProteinView`'s naive `WHERE` substring test; and `ClusteringView`'s GMM branch
(`:660-670`), which has no extracted method to pin and gets one in Step 4c.

## Next up — state as of 2026-09-08

**Steps 0–3 complete.** Step 4 in progress on `feature/step-4a-plugin-call`, **17 commits,
not yet merged to `develop`**. Every row below re-measured 2026-09-08 on the
working tree; suite **3,573 passed / 4 skipped**. Re-measured 2026-09-09 after Metadata's
last six emits; the artifact's table carries the same numbers and the reasoning behind the
rows that moved.

| Gate | Start of refactor | Now | Target |
| --- | --- | --- | --- |
| Duplication, removable — repo-wide, 6 families | 1,889 | **721** | — |
| — the 3 analysis-tab families | 1,199 | **31** | 0 |
| — the 3 Step-5 families, untouched by design | 690 | **690** | Step 5 |
| Boundary allowlist | 111 | **38** | 0 |
| — rule 1, View emits | 75 | **13** | 0 |
| — rule 2, View computation imports | 22 | **20** | 0 |
| — rule 3, Controller reads a View private | 10 | **5** | 0 (4d) |
| — rule 4, layering | 4 | **0** | 0 |
| — rule 5, tab reaches a plugin | 0 | **0** | 0 (added at zero) |
| Refactor-coverage audit | — | **100% pinned** | 100% |

**Rule 3 halved without anything being fixed.** Promoting `relay_query` to
`MetaSubsetTabController` merged two copies of the same five reach-ins into one, so the count
went 10 → 5 while the violations are unchanged in kind and still wait on 4d moving the
pending-filter state to the Model. Recorded because a ratchet that falls without a fix is the
reading error method rule 21 warns about. **Rule 2 is unmoved and one attempt would have made
it worse**: annotating the base's `relayed_query_result` as `Optional[pd.DataFrame]` put a
pandas import in a View and the gate refused it; `Optional[Any]` was the right trade for a
member already scheduled for deletion.

**Corrected 2026-09-08: the duplication row was comparing two scopes.** It read
`1,889 → 31`. **1,889 is the six-family repo-wide total** — the ratchet was widened in
the Step 2 exit review — while **31 is the three analysis-tab families alone**. Read
against 31 the refactor looks finished when Step 5 has not begun, and the ≥ 2,500
target in the Verification table is a repo-wide number. Method rule 2's fourth firing,
and the first one that arose *after* the rule was written: **when a gate's scope is
widened, every recorded before/after pair using the old scope becomes wrong in the same
commit.**

### Resume here

**Finish 4a, tab by tab.** The conversion pattern is established and proven four times:
the View emits a **typed intent**, the Controller's slot calls the plugin through
`self.model.call(...)`, and the result goes back through a setter on the View. Remaining:

- **RawData is done — the second View in the repo at zero emits**, after Clustering. Six
  commits, 2026-09-08, taking it 14 → 0. The conversions in order:
  `update_available_plugins`, the trace and PSD loading, the event plots,
  `_handle_commit_events`, and `_start_eventfinder`.

  **Nine unguarded stale reads were closed along the way**, all of the same shape: an
  answer parked on a View attribute written only on success and never cleared before the
  emit, with `_dispatch_to` swallowing the failure. The plan had described this whole
  surface in one line as "all emit-then-read on `self.plot_data`". Two of the nine
  decided *what the user saw*: the event count bounded which event indices were in range,
  and the finder's status decided whether the "already completed, start over?" prompt was
  shown — both for the previous channel rather than this one. Two emits genuinely had no
  stale read (`commit_events` and `find_events` both hand back a generator as an argument
  to `set_generator`), which is recorded so the absence does not read as an oversight.

  **`_start_eventfinder` was the awkward one**, and it is a two-phase launch now: it
  interleaved a plugin call with a question for the user, so the Controller resolves the
  statuses, the View prompts about already-finished channels, and the approved channels
  come forward again. The filter key travels through both halves rather than being held
  on the View between them.

- **EventAnalysis is done — the third View at zero emits**, after Clustering and
  RawData. Four commits, 2026-09-08, taking it 13 → 0. `_handle_plot_events` was the
  largest single conversion in 4a at 243 lines and all eight of its remaining emits, and
  it was **pinned as its own commit first** (24 tests) precisely because RawData's
  equivalent had shown what a one-line plan description can hide.

  **The pinning pass is what made the conversion correct**, and three of its five
  findings would otherwise have shipped silently:
  - **The bus applies three unpacking rules in that one method**, chosen from each
    callee's declared return type by `MainController._unpack_result`: `load_event`
    returns a dict whose `data` key is the samples, `get_fitted_event` returns a bare
    array that must *not* be unwrapped, and `get_plot_features` returns a six-tuple that
    is **splatted** across `update_features`' six parameters. None of it is visible at a
    call site.
  - **Two return-function names differ from their View methods** — `set_event_filter` →
    `set_data_filter_function`, `update_features` → `update_plot_features` — because the
    bus resolves them on the Controller.
  - **The per-event feature alignment.** `event_data` and `labels` take one to three
    entries per event; the six feature lists take exactly one placeholder each. Breaking
    it attaches a fit's features to another event's subplot, which no gate would notice.
    Perturbation confirmed three tests catch it.

  Only two of the eight emits were stale reads, not the four-plus RawData had — this
  method cleared most of its parked answers, which is worth having measured rather than
  assumed.

- **`MetaSubsetTabView` is at zero emits**, landed 2026-09-08. Its two genuinely shared
  lookups — `get_column_names_by_table` and `get_experiments_and_channels` — became
  intents wired by a shared `_setup_connections` on `MetaSubsetTabController`, so the
  pair is connected once rather than in each tab. Both threaded a `ret_args` the
  conversion had to carry: the loader key, so the experiment structure can be filed
  under it.

  **The third emit was not a base concern at all.** `update_units` moved *down* to
  `MetadataView`, its only caller, which is 3e's category rather than 4a's. That also
  retired the base's now-dead `update_column_units` relay and settled the
  `future_fixes.md` entry that had been misdiagnosed since 2026-09-04 — `ProteinView`'s
  missing `update_column_units` was **unreachable**, not swallowed, because the protein
  tab has no units label, no units cache, and hardcoded axis-label units.
- **Metadata is done — the fourth View at zero emits**, 2026-09-09, taking it 17 → 0 over
  nine commits shared with the base and the protein tab. The last six: the categorical
  guard's `get_column_type`, the CSV subset export, and `_handle_plot_events`' four -
  three of which were **one chain** (resolve the experiment, resolve the event ids within
  scope, load those rows) and became a single intent answered by
  `MetadataController.load_event_plot_data`, rather than three intents keeping three
  answer-slot attributes on the View.

  **One more unscoped-query fault**, of the same class as commit 4's three stale reads: a
  failed experiment lookup left the id `None` and the id query ran with no scope, so an
  `event_id` that exists in two channels could return the wrong channel's events. It stops
  the plot now. Reasoning in `DECISIONS.md`.

  **Two dead guards went with the emits.** The View's `try/except` around the per-event
  feature lookup and around the export could never fire - the bus swallowed plugin
  exceptions before they reached it, and a Qt slot's exception does not propagate back to
  the emitter either. Measured on PySide6 6.9.0: `emit()` returns normally, the traceback
  goes to `sys.excepthook`, and the remaining slots still run.

  **The commit-4 methods had no Controller-side test.** `load_metadata_subset` and
  `load_event_subset` shipped covered only by View tests that stub the answer, so a wrong
  call signature or a swallowed failure would have satisfied the whole suite.
  `tests/unit/controllers/test_metadata_fetch_slots.py` covers them alongside this commit's
  four, 24 tests, and two mutations - dropping the scope guard, and handing the query over
  before the rows load - each fail exactly one of them.
- **Protein is done — the fifth and last View at zero emits**, 2026-09-12, taking it
  12 → 0 over three commits. The event-plot chain (`_resolve_event_db_ids` +
  `_fetch_event_data`) went as one intent, as Metadata's had; the two distribution twins
  and `_build_load_event_data_args` went as one more, because all three ran the same
  four-emit chain; and `_commit_fits` went two-phase, because it interleaves a plugin call
  with a modal question.

  **Three unscoped-query faults of the same family closed with them**, each one the bus
  swallowing a lookup and the View then dropping the scope rather than stopping: the
  experiment on the event-id query, and the experiment *and* channel on a `_raw` filter's
  scope clause. A raw filter meant for one channel read the whole database.

  **And the tab showed one query while running another.** For a `_raw` subset it displayed
  what `construct_event_data_query` built - which does not refuse a complete SELECT, it
  splices it in after `WHERE` - and then loaded through a separately scoped raw query.

- **`MetaSubsetTabView` is at zero for the second time**, 2026-09-12. Its last emit was
  `_rebuild_event_id_cache`'s `load_metadata`, and the recorded claim that its callers
  needed restructuring first was false: re-derived, **all five** call sites (not the two the
  plan named - the method lives on the base, so ProteinView has three) consume only the
  `bool` return and read `filtered_event_ids` a statement later. `relayed_query_result` and
  its three relay methods went with it.

**Then 3d**, which 4a's commit 1 unblocked, and **4c Protein and Metadata**, which are much
cheaper after 4a for the reason recorded under 4c below.

### Standing rules added this session

- **New runtime mechanisms are written test-first, verified red-then-green.** Not for
  moves — the ratchets cover those — but for anything with wiring that did not exist
  before. This session's only escaped regression was the refactor's first new mechanism.
- **A regression the suite missed gets a test once positively diagnosed**, written against
  the *invariant* rather than the symptom, and seen red before it is trusted.
- **New tests are owned by whoever adds the mechanism**, not the usual test owner.
- **When a gate's scope is widened, restate every recorded before/after pair for it in the
  same commit** — otherwise the old-scope figures survive as a self-contradiction, which is
  how `1,889 → 31` happened.
- **A safety net's absence has no signature, so assert the net is armed.** A missing test
  dependency errors at setup rather than failing, which reads as a pass.
- **A converted slot needs its own test, not just its caller's.** The View tests stub the
  Controller's answer, so they cannot see a wrong call signature or a swallowed failure, and
  no gate covers a method that did not exist before the commit. Rule 52.
- **Delete a guard the conversion makes unreachable, once you have measured that it is.** A
  Qt slot's exception does not reach the emitter, so a `try/except` around an emit is dead
  code that reads as error handling. Rule 50.
- Method notes are at **52 rules** in the artifact, grouped by refactor phase; the
  artifact is the source material for an end-to-end refactor skill, not only a metrics one.

### Owed

- **Metadata's last six emits are unchecked on Windows** — the event-plot chain, the CSV
  export and the categorical-histogram guard. Everything earlier is cleared, the five paused
  subset-tab commits on 2026-09-09.
- **`WalkthroughStep` as a frozen dataclass** — 90 tuple literals across 7 files, moves no
  gate. Still open from 3f.

#### 4c Clustering pilot — LANDED 2026-09-07

**Boundary allowlist 106 → 103, and rule 2 falls for the first time in the refactor.**
`hdbscan`, `pandas.api.types` and `sklearn.mixture` were each used by exactly one moving
method, so all three imports left `ClusteringView`, which drops from 5 forbidden imports to
2. `numpy` and `pandas` stay — `update_plot` uses both, which is correctly View code.
Duplication unmoved (single copies). Suite 3,346 passed / 4 skipped.

`ClusteringModel` went from `def _init: pass` to owning `normalize_column_data`,
`cluster_hdbscan`, `cluster_gaussian_mixture` and `cluster()`.

**The caller restructure was the work, exactly as the fifth pass predicted.**
`_load_metadata_and_cluster` → `_load_metadata_and_request_clustering`: it no longer returns
a 7-tuple, it emits `cluster_requested`. `ClusteringController.cluster` calls the Model and
hands the answer to `ClusteringView.set_clustering_result`, which does the display message,
the axes reset and the plot that used to follow the call inline.

Kept in the View deliberately: the two `global_signal` emits (**4a**), the logscale call
(**3d**, blocked on 4a), and parsing the settings dialog's parameter strings — so a malformed
parameter is reported against the form it came from, and the Model takes typed values it
cannot fault. The per-column display flags are held on the View between the emit and the
answer rather than round-tripped through a Controller with no use for them, and
`set_clustering_result` refuses a result with no request outstanding rather than plotting
against another run's flags.

**Two things worth carrying to the other 4c tabs.** First, the win to aim at is *which
import leaves*: check that each forbidden import is used by exactly one moving method before
starting, because that is what makes the allowlist fall. Second, extracting an inline branch
finds coverage that never existed — the Gaussian-mixture branch was fifteen lines inside a
136-line View method reachable only by constructing the widget and answering two bus emits,
and it now has four direct tests including one pinning that 1.9.0's seeding survived the
move.

#### 4a — CONVERSIONS DONE 2026-09-12. Mechanism + Clustering landed 2026-09-07

**Allowlist 102 → 95.** `ClusteringView` is the **first View in the repo at zero emits**;
the View-layer total is 72 → 65.

| Commit | What | Allowlist |
| --- | --- | --- |
| 1 | `call()` on `MetaController`/`MetaModel`, instances pushed | 102 (unchanged, by design) |
| 2 | Clustering's column lookups | 100 |
| 3 | The cluster commit path, and its SQL (4b for that path) | 97 |
| 4 | Clustering's metadata load | 95 |
| 5-6 | The regression below | 95 |

**Design decisions taken in commit 1**, all measured free before being taken: `call()`
refuses a `_`-prefixed method name (all 75 bus calls targeted public methods, so nothing
broke); `get_plugin` is **private**, so `call()` is the only public door; and
`check_mvc_boundary` gained **rule 5**, counting the ways around it, reading **zero**
across 32 tab-layer modules. `call()` also takes `**kwargs`, which the bus could not — 48
methods on the data-plugin bases have default parameters, several last in the signature.
Deliberately **no call-stack inspection**: it would cost real time on a path that runs per
chunk and per event, reject the worker-thread path whose stack starts at Qt's thread entry,
and fail on a user's machine rather than on the developer's commit. `DECISIONS.md` carries
the reasoning.

##### The first escaped regression of the refactor, and why it escaped

Reported from a real run: restoring a session with one clustering tab and one loader gave
`KeyError("No MetaDatabaseLoader plugin registered under 'SQLiteDBLoader_0'")` for a key
listed one widget away. **Two faults**, and it took two attempts:

1. `instantiate_analysis_tab` pushed plugin *names* to a new tab but not the instances.
2. **The ordering.** Fixing (1) was not enough. Handing a tab the names populates its
   comboboxes, and populating a combobox fires a selection change **synchronously** —
   which is when the tab asks the selected loader for its columns. Names were pushed
   first, so that call ran against an empty map. Instances now go first at both sites, and
   the instances come from `DataPluginModel.get_plugin_instances()` — the same dict the
   *names* are read from — rather than being rebuilt key by key inside `MainController`.
   Every create/delete/rename route already emitted, so the creation path was never the
   problem: the payload and the order were.

It also unmasked a latent fault: `ClusteringView.columns` was created only by the
`update_column_names` callback and never initialised, so **any** failed column fetch left
the settings dialog raising `AttributeError` instead of opening empty.

**Why no gate caught it.** Steps 0–3 were all *moves*, and the three gates are built for
moves: the ratchet checks that copies vanished, the allowlist that nothing crossed a layer,
the audit that everything moved stays pinned. This was the refactor's first new **runtime
mechanism**, and a missing call at one of two sites is not duplication, not a boundary
crossing and not an uncovered target — **absence has no signature**. It also only bit under
session restore, the one ordering nothing exercises: the e2e suite builds a tab and *then*
creates plugins, which is the order that works.

Two standing rules came out of it: **new runtime mechanisms are written test-first,
verified red-then-green**, and **any regression the suite missed gets a test once
positively diagnosed**. The first regression test written here was itself too weak — it
asserted both pushes happen, which the broken code satisfied, because the counts were right
and only the order was wrong. Stating the invariant as *"a tab can call what it is being
told about, at the moment it is told"* has the ordering in it; asserting that two calls
happened does not. Verified on Windows against a live session and a restored one,
2026-09-07.

### Fifth verification pass — Step 4 re-checked after Step 3, 2026-09-06

Step 3 moved a great deal of what Step 4 names, so every checkable claim below was
re-measured at `5c4ea613`. **All named targets survive** — nothing has been deleted out from
under the step — but ten claims moved, and two change what the work *is*.

| Claim as written | Verdict | What is actually true |
| --- | --- | --- |
| 4a · **75** emits | **72**, and one is on a base | 3b collapsed 3+3 duplicated emits to 3 on `MetaSubsetTabView`. Views: Clustering 7, EventAnalysis 13, Metadata 17, Protein 18, RawData 14, `MetaSubsetTabView` 3. The repo total is 74; the other two are in `MetaController` and `MetaModel`, where an emit is legitimate and **not 4a's business**. So 4a now touches a shared base as well as five tabs |
| 4a · `global_signal` in **142** test functions, **46** assert on the emit | **156** and **37** | Counting rule, stated so it can be re-derived: a test function counts if `global_signal` appears anywhere in its source segment; it counts as *asserting* if that segment matches `assert.*global_signal` or `global_signal.*assert_` on one line. Step 2 added references, hence 142 → 156; the assertion figure is lower than 46 under this definition and 46 was never written down precisely enough to reproduce |
| 4a · the stale-read guard is at `MetadataView.py:2334-2336` | **8 sites, two files** | `MetadataView.py:1369, 1982, 2238, 2257` and `ProteinView.py:1499, 1678, 1694, 1852`. All eight are clear-before-emit guards and all eight are code this step deletes |
| 4d · **eight** further `self.view.subset_filters` reach-ins, **two** `restore_subset_filters` calls | **six**, and **zero** | 3 per Controller, not 4, and `restore_subset_filters` is no longer called from either Controller at all — 3b promoted `get_session_state`/`restore_session_state` to `MetaSubsetTabController` and took those reach-ins with them. **4d's Controller-side surface shrank from 10 to 6, and part of it is now on a base.** The 10 `self.view._pending` private reads are unchanged, 5 per Controller |
| 4d · 15 of 16 `subset_filters` reads are synchronous | **shape changed** | The reads now span three files: 13 mentions in `MetadataView`, 14 in `ProteinView` and 6 in `MetaSubsetTabView` (`_save_filter` and, since Step 4a promoted it, `get_selected_filters`). The synchronous-access problem is unchanged in kind, but the fix now lands once on the base for `_save_filter`, `show_edit_filter_dialog`, `_delete_filter` and `get_selected_filters` |
| 4d · `hist_data` · 21 tests | **confirmed exactly** | 21 test functions, 13 mentions in `MetadataView` and 4 in `ProteinView` |
| 4c · Clustering pilot has **6** existing tests | **understated** | 5 for `_update_clusters_hdbscan`, 8 for `_load_metadata_and_cluster`, 6 for `_normalize_column_data`. The "6" matches one method, not the trio |
| 4e · `_save_filter`/`_load_filter` | **half shared now** | `_save_filter` moved to `MetaSubsetTabView` in 3b (one copy); `_load_filter` is still per-tab (two copies). `_export_csv_subset` exists only in `MetadataView` |
| 4b · `MetadataView.py:2351`'s raw `SELECT` | moved, and **the surface is wider than recorded** | That site is now `_handle_plot_events:2253`. The full raw-SQL surface in the View layer: `_rebuild_event_id_cache` (Metadata `:1957`, Protein `:1476`), `_resolve_event_db_ids` (`:1693`), `_handle_plot_events` (`:2253`), **plus `_show_add_filter_dialog` and `show_edit_filter_dialog` in both subset tabs — four sites the plan does not mention at all** — and the two commit methods `ClusteringView._commit_clusters` and `ProteinView._commit_fits`, which are 4e's |
| 4b · `_build_where_clause` is gone | **still true** | Confirmed absent from `poriscope/` and `tests/` |

**The one thing that makes Step 4 possible at all, verified rather than assumed.**
Decision B's template is real and works: `RawDataView` declares `calculate_psd = Signal(list, float)`
and emits it; `RawDataController.calculate_psd` (`:62`) calls `self.model.calculate_psd(...)`
**synchronously inside its own slot** and hands the result to `self.view.set_psd(...)`. So a
View→Model round trip exists today; what it does not offer is a *return value to the emitting
line*. That is why 3d is blocked and why every 4b/4c move is a restructure of its caller —
everything after the computation has to move into the `set_*` handler — rather than a
relocation. **Budget for the caller rewrite, not the method move.**


- **4a** The **75** emits become `self.call(...)` in the Model. Highest value in the refactor.
  Note the cost on the test side: `global_signal` appears in 142 test functions and **46 assert
  on the emit**, so those assertions are rewritten rather than re-pointed. The stale-read guard
  `062ef6f` left at `MetadataView.py:2334-2336` (clear the attribute immediately before the
  emit) is code this step deletes.
- **4b** SQL out of the widget: `_rebuild_event_id_cache` (`MetadataView.py:2039`,
  `ProteinView.py:1538` — 4 parameters now, not 5), `_resolve_event_db_ids`
  (`ProteinView.py:1731`), `_fetch_event_data` (`:1794`), `_build_load_event_data_args`
  (`:1908`), and `MetadataView.py:2351`'s raw `SELECT`. **`_build_where_clause` is gone** —
  `062ef6f` deleted it from both Views and routed both caches through
  `construct_metadata_query`, which is a large part of 4b already landed. (`DECISIONS.md`
  2026-08-25 accepts the f-string interpolation itself — this is about *where* the SQL lives.)
- **4c** Computation. Clustering is the pilot (`_update_clusters_hdbscan`,
  `_load_metadata_and_cluster`'s GMM, `_normalize_column_data` — 6 existing tests, no bus
  calls). Then Protein (`_double_gaussian`, `_fit_double_gaussian`,
  `_fit_and_sanity_check_double_gaussian`, `_compute_theoretical_blockages`,
  `_generate_vm_ensemble`, `_update_distribution_individual`, `_summarize_vm`), Metadata
  (`_calculate_heatmap`, `_construct_all_points_histogram`, `_construct_event_overlay`,
  `_plot_1d_density`, `_plot_capture_rate`, `is_categorical_type`), RawData
  (`_get_baseline_stats`, `_gaussian`, `_gaussian_fit`, the `histogram1d` binning).
  Does **not** reopen the 2026-08-25 double-Gaussian decision; `PeakFinder`'s copy is untouched.
- **4d** Domain state off the View: `subset_filters` (declared `MetadataView.py:152`,
  `ProteinView.py:232`), `_pending_filter_name`, `_pending_filter_text`,
  `_pending_old_filter_name` → Model. Removes the Controller-reaches-into-View-privates
  violation, which is **10 sites across two files**, not the one recorded:
  `MetadataController.py:199-200` and `:221-223`, **and `ProteinController.py:153-154` and
  `:175-177`**. **Eight** further `self.view.subset_filters` reach-ins plus **two**
  `restore_subset_filters` calls across the same two Controllers move with them, and the
  `_private` rule will not flag those. (This applies the Q3 correction above, which said "8, not
  12, corrected in 4d below" and then was never applied here — the figure had read "Twelve"
  since. Verified 2026-09-06: four bare `subset_filters` and one `restore_subset_filters` in
  each Controller, none anywhere else in `poriscope/`.)
  This is the step that reaches her **e2e** suites. Resolve `hist_data`'s three shapes here
  (21 tests reference it, so those assertions change by design).
  - **4d is harder than 3b, which is why the ordering below inverts.** **No View anywhere
    references `self.model`** — verified 2026-09-06, zero occurrences across all five `*View.py`
    and `MetaView.py`. Views reach the Model only asynchronously, through `global_signal` via
    the Controller. But **15 of the 16 `subset_filters` reads are synchronous**: dialog
    construction at `MetadataView.py:3108` and `:3195`, and `get_selected_filters` - now one
    copy on `MetaSubsetTabView` - on every plot. Moving the dict to the Model therefore needs either a synchronous View→Model accessor
    that Decision B currently forbids, or a View-side cache. That is a design decision, not a
    move, and doing it before 3b means taking it twice — once per tab — instead of once on the
    base.
- **4e** File I/O: `_export_csv_subset`, `_save_filter`/`_load_filter`, `_commit_fits`,
  `_commit_clusters`, `_merge_clusters`. Keep `QFileDialog` path selection in the View.
  `MetaController.export_plot_data` is the precedent.

Stays in the View: matplotlib artists, axes/canvas lifecycle, widget state, file dialogs,
walkthrough step lists.

## Step 5 — outside the analysis tabs

Absorbs `future_refactors_and_features.md` Parts 5–12. Order: zero-risk deletions and
correctness issues, then mechanical extractions, then god-methods (coverage first).

- **5a data plugins (~1,000 lines).** `CUSUM`/`NoFitter` share 411 identical lines;
  `ClassicCUSUM` is a 195-line override differing in 2 → `CUSUM` + `_normalize_step_size()`;
  the two Chimera readers differ in 23 of 390; `_get_baseline_stats`/`_find_events_in_chunk`
  duplicated across two finders — **merge first, then fix the baseline-σ bug once**;
  `QObjectABCMeta`/`QWidgetABCMeta` 49 lines differing in 2 with dead `__new__` overrides;
  four `Meta*` bases carry a byte-identical 3,584-char `get_empty_settings` docstring.
- **5b `Meta*` internals.** Correctness first: `BaseDataPlugin.apply_settings` decides "is
  this a plugin instance" via `.get_key()` in a bare `except Exception`. Then
  `fit_events`' nine repeated reject blocks (`_reject_event` helper, ~35-40 lines);
  `find_events` reimplementing `reset_channel` inline (three copies of 10 lines — recorded as
  the safest finding in the part); `export_subset_to_csv`'s 4-step pattern ×5 (~65→~15 lines);
  `tuple_builder` defined three times. `MetaController`'s two ~60-line relay methods are
  **blocked on 4a** — most of that code is deleted rather than extracted.
- **5c app shell.** `DataPluginController.edit_plugin` (+ `_resolve_plugin_references` and
  `_check_key_available` extractions that shrink it); `MainView`'s 9 menu blocks + 8 handlers
  → table + `functools.partial` (~90→~25 lines); `switch_to_page` duplicating
  `clear_milestone_dialog`; `SettingsWindow`'s ~8 repeated row blocks and two mirror-image
  log-level dicts.
- **5d shared widgets.** `multiselect.py`/`multiselect_filter.py` ~90% duplicate — 8 methods
  copy-pasted, and demonstrably diverged (the redundant nested `if` and the false 3-way
  "select all" branch exist in both). **`DECISIONS.md` 2026-09-01 requires the event filter to
  stay on the application and records the load-bearing path as unexercisable on Linux CI —
  manual Windows check required.** Range parsing → `poriscope/utils/range_parsing.py` using the
  Tier B2 rulings. `dict_dialog_widget.on_ok`'s try/except type dispatch — but note
  `DECISIONS.md` 2026-09-01: that file has **no unit tests** and writing them is a prerequisite,
  not part of it. `clustering_settings_widget`'s three ~50-line row builders.

Constraints: `MetaEventFitter` changes force owner-held edits (check in first); the
`close_resources()` timeout was **built and reverted once** for a documented reason — the recipe
is in `future_refactors_and_features.md`, do not re-derive it; `BaseLineEdit` is re-exported
from `exposed.py` so changing it is breaking.

## Step 6 — scaffold and docs

- `scripts/new_plugin.py`'s analysis-tab half. **Generating a working ~100-line triad against
  the new structure is the acceptance test.** Re-run the four stub-body probes rather than
  reasoning about them (`pass` under a non-`None` return is mypy `empty-body`; a copied
  `:raises X:` above `pass` is DOC502; the same above `raise NotImplementedError` is DOC503;
  raising with no field is DOC501).
- Replace the stale `HelloWorld` example (4 of `MetaView`'s 5 abstract methods; imports
  `from utils.MetaView import MetaView`).
- Autodoc publishes 478 private methods across 1,119 `automethod` directives — omit privates.
- Update `quality_control.rst`; regenerate autodoc.

## Step 7 — release mechanics

- Breaking-change inventory in `changelog.md`, each called out explicitly, including every
  Decision C contract change.
- **Action history**: **5** `@register_action` sites over 4 names, replayed by name off the View. Keep them
  as thin View façades, or ship a name-migration map. Saved `.json` files are user data.
- **Session state**: `get_session_state` serializes `self.view.subset_filters`; verify against
  a real 1.x session file after 4d.
- `CITATION.cff`'s version is a hand-maintained copy of `constants.py`; `release.yml` never
  checks it against the tag.

## Verification

| Metric | Baseline | Target | Instrument |
| --- | --- | --- | --- |
| MVC boundary allowlist | **107** (75 emits, 22 imports, 10 privates) | 0 | `ast` test (Step 2 branch 3) |
| Duplicated lines removed | 0 of **1,889** repo-wide, 6 families (re-derived, baselined) | ≥ 2,500 | `scripts/measure_duplication.py` + ratchet |
| Golden net armed | unasserted | asserted | `tests/test_safety_net_is_armed.py` |
| Analysis-tab coverage | unmeasured | ratchet up | `pytest-cov` (Step 0) |
| Numerical output | unpinned | unchanged | golden files (2A) |
| Minimal runnable triad | n/a | ~100 lines | `new_plugin.py` (Step 6) |

Full `pytest` green before every commit, no path arguments and no marker filter.
`pre-commit run --all-files` is the mypy gate. **Manual Windows pass** driving all five tabs
through the walkthrough plus the multiselect popup path — CI is Linux under Xvfb and
`DECISIONS.md` records that path as structurally unexercisable there.

**Baseline manual pass: run 2026-09-04, all clear.** All five tabs through the walkthrough; the
column and filter multiselect popups on both Metadata and Protein (open, select, deselect,
select-all, dismiss on an outside click, reopen with the selection intact); and no widget
outliving the app on close. That is the pre-refactor baseline, so a later failure is
attributable. **Re-run it after each structural step** — certainly after 3a, which rewrites all
five controls widgets, and after 3f, which moves the walkthrough modules.

**Subset-base manual pass: run 2026-09-08, all clear.** The first of the five
checkpoints scheduled for the subset tabs. Covers the column and experiment pickers on
both Metadata and Protein — which now go through the two shared base slots — and
Metadata's axis unit labels, which go through its own slot after `update_units` moved
down. The next is owed after the filter dialogs are converted.

**Step 4a EventAnalysis manual pass: run 2026-09-08, all clear.** Covers the four
conversions that took the tab 13 emits to 0 — the loader channel lookup, the event write,
the two-phase fitting launch, and the 243-line event-plot path. **Clustering, RawData and
EventAnalysis are all at zero emits and every path they have converted has been seen
working on Windows.** The next pass is owed after the subset tabs.

**Third Step 4a RawData manual pass: run 2026-09-08, all clear.** Covers the event
finding and commit paths rewritten by `ac26f71c` and `67f335b1` — including the two-phase
launch, where the "already completed, start over?" prompt now follows a Controller-side
status call rather than a bus emit. **RawData is at zero emits and every path it has
converted has been seen working on Windows.** The next pass is owed after EventAnalysis.

**Second Step 4a RawData manual pass: run 2026-09-08, all clear.** Covers the three plots
rewritten after the first pass — the trace and noise spectrum (`a572644`) and the event
plots (`8446eb4`) — so every path 4a has converted has now been seen working on Windows.
This pass also surfaced three clarity defects rather than correctness ones, all fixed in
`2ad8ba0`: an out-of-range event index reported "No data available for plotting" instead
of naming the bound, stepping the index below 0 was declined silently, and finding or
fitting events with no filter selected could register almost every sample as an event with
no warning. The last of those was reported as a hang and correctly diagnosed as user
error; it is guarded by a confirmation now.

**Step 4a RawData manual pass: run 2026-09-08, all clear.** The two paths that had no
cover, verified as separate checks because they exercise different widgets and would fail
in different places. **The channel multiselect** (`f1fd81c`): a reader's channels populate
`channel_comboBox`, which `DECISIONS.md` 2026-09-01 records as structurally unexercisable
on Linux CI. **The event-finding time limits** (`1ff9e92`): a new event finder's Timer
dialog opens with one row per channel, ranges set there survive a later plugin
add/delete, and `find_events` runs over them — `analysis_time_limits` is reached only
through `_handle_timer` and `_start_eventfinder`, so no combobox is involved. Together
with the Clustering tab and session restore verified 2026-09-07, **every path Step 4a has
converted so far has now been seen working on Windows.** The next one is owed after the
remaining RawData conversions.

**Post-3a manual pass: run 2026-09-06, all clear.** Same scope as the baseline, against a
branch that had rewritten all five controls widgets — so the promoted widget factories, the
`create_info_button`/`create_add_button`/`create_delete_button` wiring and the placeholder
guard were all exercised through the real UI. Nothing regressed. The next one is owed after
3f.
