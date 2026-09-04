## Poriscope 1.9.0: in progress

* **Corrected what filter types 4 and 5 are documented to mean; no behaviour change**
    * The codes name **which arm of the construct the star is bound to** - 5 the long (higher-ECD) arm, 4 the short one - and carry no information about where the star sits in the trace. The code was already right; three places said otherwise.
    * `_classify_bound_star`'s `star_went_first` is renamed `star_on_long_arm`, because it never meant temporal order: `star_is_before == (direction == "forward")` reduces to "the star is on the higher-ECD arm" in both branches, since `forward` is by construction the population where the pre-barcode arm carries the larger ECD. On a backward event the flag is True precisely when the star is temporally **last**.
    * The report line `Long end (star translocates first)` / `Short end (star translocates last)` now reads `(star on the higher-ECD arm)` / `(star on the lower-ECD arm)`. The old text asserted the temporal reading, which is false for backward events - there the long arm threads last, so a type-5 star went through the pore last.
    * `_classify_bound_star`'s docstring claimed `"long end"` "always means the star end entered the pore first however that event happened to thread". That is the opposite of what the direction flip does: the flip exists to *remove* the threading order and leave a statement about the arm. Rewritten, with the four-case table spelled out and the false reading called out explicitly.
    * `_classify_translocation_direction`'s summary said it decides "which end of the construct entered the pore first". It now says it decides which way round the construct threaded, and adds that `"forward"` is a *name* for the higher-`log10(pre / post)` population rather than an independently established threading order - and that being a fitted split, it is not a per-event `pre > post` test, so an event whose own ratio is below one can still land in the `"forward"` population.
    * One new test, `test_the_code_is_the_arm_and_not_the_position_in_the_trace`, pins the invariant from both sides: each trace position yields both codes depending on direction, and each code is reachable from both trace positions, so neither can be read off the other. 194 tests passing.

* **Tightened the normalized peak prominence report's unit lines**
    * The three units on each line are chained with `~` rather than `=`, since they are the same quantity in different units and the rounding means they are not literally equal, and the bare ratio has dropped its `unfolded levels` suffix - the line reads `Threshold: log10 +0.464 ~ 2.91 ~ 2007.2 pA`.
    * **The standard deviations now report a single pA figure instead of a multiplicative factor and a range.** A log-space width is a multiplicative spread - +/-1 sigma runs from `centre/factor` to `centre*factor`, which is not symmetric about the centre and so has no single "+/- x pA" - but it does have a total width, and that is what is reported: `centre * (factor - 1/factor)` against the run's unfolded level, which is exactly the span the old `x/1.12 to x1.12, 1248.0 to 1557.8 pA` described. So `Std (lower): log10 0.048 ~ 309.8 pA`. It is the one-number answer to "how wide is this population in pA", and unlike the factor it is in the same units as the centres above it, so the two can be read against each other.
    * Available to consumers as a new `std_currents` entry on `_peak_prominence_classification_results` (empty when the run has no unfolded level to scale against). `std_factors` is retained - the conversion is derived from it - and on a linear fit the width is already a ratio and is only scaled by the reference.
    * Dropped the trailing `pA figures use an unfolded level of ... (fitted unfolded centre)` line. The reference and its provenance are still carried on the results dict as `unfolded_reference` and `unfolded_reference_source` for anything that needs them.
    * Three new tests pin the pA span against both its closed form and the two independently computed ends of the span, the empty result without a reference level, and the linear path.

* **A bound-star candidate that is the widest peak in its own event can no longer be promoted to type 4 or 5**
    * `_classify_bound_star`'s depth floor tests only how *deep* a candidate goes - its modal blockage against twice the event's unfolded level - and never how long it lasts, so a carrier body, a long fold, or a stretch the peak finder resolved as one broad peak clears it while being the wrong shape for a star, which is a sharp spike. A candidate whose `peak_width` (measured at half height) equals the maximum over every peak in the event is now excluded.
    * **The maximum includes the candidate itself and every other peak in the event**, whatever its type - including peaks inside the barcode that were never candidates - so `>=` against the maximum is exact and needs no tolerance, and peaks *tied* at the maximum are all excluded rather than none of them being "the widest".
    * **It filters the candidate pool rather than vetoing the winner.** Where a wide candidate and a narrow one both clear position and depth, dropping the wide one hands the star to the narrow one instead of the event losing its star altogether - even when the wide one was the more prominent and would have won on prominence alone.
    * Events where the rule empties the pool are counted under a new `widest_peak` result, overall and per sequence, and surfaced in the report (a summary line and an extra breakdown column, both shown only when the count is non-zero, matching how `no_height_reference` is already handled). They are deliberately **not** folded in with the genuinely starless events: such an event did have a deep enough peak in the right place, and a run where this fires often is one where the depth floor is admitting broad features - which is worth seeing rather than hiding.
    * Ordering is unchanged ahead of it: the rule runs after the depth floor, so an event with no `unfolded_level` still reports as `no_height_reference`. That signal fires for a whole run at once when folding classification declines and must not be masked.
    * **Backward compatible with databases written before `peak_width` existed**: absent or all-NaN widths skip the rule rather than blocking every star, and a candidate whose own width is NaN cannot be shown to be the widest and is left alone.
    * 10 new tests in `TestBoundStarWidestPeakRule` cover the rejection and the kept -1, the separate counter, the narrower-candidate control, pool-filtering over winner-vetoing, ties at the maximum, a NaN-width candidate, absent and all-NaN widths, the depth floor still reporting first, and an interior peak counting toward the maximum. Five of the ten fail against the previous behaviour. `_star_event` gained an optional `peak_width`, defaulted to *omitted* so the existing position/prominence/depth tests are not silently exercising this rule too.

* **The double-Gaussian fit now fits a flat constant as a seventh free parameter**
    * `_double_gaussian` gained an `offset` term, and it is a genuine parameter of the same `curve_fit` call (and of the constrained SLSQP refit), not a value computed beforehand and subtracted off. It models a uniform background - counts spread across the whole histogram belonging to neither population - which the two Gaussians otherwise have to absorb by widening. Gated by the new `FIT_CONSTANT_OFFSET` class constant, on by default.
    * **Measured**: two symmetric populations of true sigma 300 sitting on a flat background of 2500 events came back with widths 335 and 338 without the constant and 305 and 301 with it, the constant landing on 79.6 counts against a true 78.1, and the residual sum of squares falling from 52632 to 6880 - better than sevenfold. On data with **no** background it is inert: the constant settles at 1-8 counts and moves no fitted mean by more than 0.1%, across clean bimodal, skewed bimodal, single-population, minimum-bin-count and 60-point histograms.
    * **Bounded to `[0, max(counts)]`**, the same ceiling the amplitudes already get, and deliberately no tighter. Counting data cannot go negative and a pedestal above the tallest bin would put the model over the data everywhere, but a *fractional* ceiling proved actively harmful rather than safer: capping at 2% and 5% of the tallest bin clipped the real 78-count pedestal to 21.9 and 54.7 and left the fit worse than the unclipped one, and nothing below 10% recovered it. No new tuning constant was needed, because least squares has no incentive to raise a pedestal that is not in the data.
    * **Both the seven- and the six-parameter fit are run per initial guess, and the constant is dropped if it made the residual meaningfully worse.** The constant only adds a degree of freedom, so at a true optimum the larger model can never score worse - if it does, the extra dimension moved the optimizer somewhere worse. That is reachable: seeded from the histogram-split guess alone, on two populations whose higher one held 5% of the events, the free constant found a local minimum scoring 6426 against the six-parameter fit's 4900, collapsed the minority component onto the majority one (mean 2384 against a true 3500) and flipped `n_components` from 2 to 1 - a population lost to a fit that was worse on its own objective. Against the two-stage seeding actually in use it did not recur over 112 fits spanning minority fractions from 1% to 45% and four skew levels, but the comparison stays as the net that makes this a strict improvement rather than a trade. Near-ties go to the seven-parameter fit, so float noise on background-free data cannot flip the length of `params` between runs on equivalent data.
    * **The constant goes last in `params`, and defaults to zero.** Positions 0-5 keep exactly the meanings every existing consumer assumes, so six-element unpacks and index reads like `params[2]`/`params[5]` for the two widths stay correct; `fit_threshold` also exposes it under its own `"offset"` key, always present and 0.0 where none was fitted. `_gaussian_intersection`, `_classification_confidence` and `_warn_if_fitted_means_are_off_their_peaks` read the components positionally and ignore a trailing constant.
    * **It moves no class boundary.** Being common to both components the constant cancels out of the crossing `_gaussian_intersection` solves for and out of both of the constrained refit's constraints, and it is deliberately excluded from `_classification_confidence`'s posterior: including it as a third uniform class would put the score at the crossing at `g/(2g+offset)`, strictly below 0.5, breaking the documented property that a `"constrained"` threshold is exactly where the confidence reads 0.5. What that costs is only that a point sitting on pure background is still scored on which population it is *nearer* rather than on whether it belongs to either; `"offset"` is there to say how much background was found.
    * The `n_components` diagnostics are unchanged, except that the constant is exempt from the unconstrained-parameter warning - it is the one parameter whose correct value is routinely zero, and a relative-error test can never be passed by a parameter that is legitimately near zero, so including it would have fired that warning on almost every clean fit. Its fitted value is logged at DEBUG either way. Plots draw both components sitting on the fitted background plus a dotted line at the pedestal itself, so it reads as a fitted quantity rather than an unexplained gap between the curves and the bars; with no background the plot is what it was before.
    * **One behaviour change on the constrained-refit path, and an improvement.** Where the threshold search puts its valley out in a sparse tail, the six-parameter refit used to "succeed" by parking a broad, near-flat higher component past the end of the data to cover it (measured on one dataset: mean 8324 with std 3883 for a valley at 6383). With a pedestal available that flat contribution goes to the constant instead, the higher component collapses below the bin width, and the existing collapse guard declines the refit and keeps the joint fit - rather than reporting a component 5000 pA past any data. Two `TestValleySeparationConstraint` tests used the one seed of eight that produces such a tail valley; they now use a representative seed, so they exercise the separation constraint they were written for, and the tail corner has a test of its own.
    * 25 new tests in `TestFitConstantOffset` cover the model term and its zero default, the recovered background and the widths that stop absorbing it, inertness without a background, the residual guard in both directions plus its one-fit-raised and both-fits-raised paths, near-ties keeping seven parameters, the `"offset"` key and the unmoved width indices, the constant not moving the crossing or the confidence, the still-exact 0.5 at the crossing, the exemption from the unconstrained warning, the refit keeping it free, the tail-valley decline, and the three plot paths. `MIN_FIT_BINS`' 30-bin floor is unchanged and its rationale is restated for seven parameters.

* **Normalized peak classification is fitted on a base-10 log scale, and is back to reading types 1, 2 and 3**
    * **Reverted** the type-3-only selection from the entry below: `_classify_peak_prominences` reads every type 1, 2 and 3 peak again, and types 1 and 2 carry a class and a confidence as they did before. The docstrings, the warning text and `fit_fallbacks.md` are back to describing that, and the three tests that pinned the narrower selection are retargeted.
    * **The fit is now taken on `log10(normalized_prominence)`**, gated by the new `PROMINENCE_FIT_LOG_SCALE` class constant. A double Gaussian on log values is a double log-normal on the measured ones, which is the shape the upper population has - `future_fixes.md` records it as right-skewed with a log-normal beating a Gaussian by 24% RMS. Transforming the input gets that **without touching the six-element `params` contract** shared by the plotting code and all three classifiers, which is what deferred the change when it was posed as fitting a log-normal component directly. That item can now be closed on the prominence classifier's behalf. The base is presentational only - the histogram, the fit and the split are equivariant under it, so the classes come out identical for any base - and base 10 was picked over natural log because a reader can convert a decade in their head.
    * Everything the fit produces stays in log units - the split, the per-peak confidences, and the plot, whose x axis is relabelled `log10(Normalized Peak Prominence)` and whose threshold line is annotated with both the fitted value and the ratio it corresponds to (`10**threshold`). The run's report (`_peak_prominence_classification_results`, and the text block `report_channel_status` builds from it) now carries the threshold, both centres and both standard deviations in **three unit systems** at once: the raw fitted decade (`threshold_fitted`/`centers_fitted`/`stds_fitted`), the ratio to the event's unfolded level (`threshold`/`centers`, via `10**value`, plus `std_factors` - the multiplicative spread `10**std` each standard deviation corresponds to, since a log-space width is a *factor* once exponentiated, not a linear one), and, when a representative unfolded level is available, the equivalent current in pA. That level comes from the new `_run_unfolded_level` helper, which prefers the folding fit's own lower centre (`_classification_results["lower_center"]`) and falls back to the median of the run's per-event `unfolded_level` values, reporting which source it used (`unfolded_reference`/`unfolded_reference_source`) so a reader knows what a pA figure was computed against; with neither available the pA column is simply omitted rather than invented. A peak whose normalized prominence is not strictly positive has no logarithm and is dropped from the fit with a warning rather than becoming a `-inf` that would take the histogram's range with it.
    * **Measured on synthetic double-log-normal data** (600 peaks per trial, medians 0.2 and 0.6, sigma_log 0.45, 12 trials): the linear fit returned `n_components = 1` in **10 of 12** trials - declining the bimodality and falling to the above-floor threshold rung - and recovered the true classes **61%** of the time. On the log scale that is **1 of 12** and **85%**; this comparison is unaffected by the log base, since the fit's success or failure only depends on linearizing the log-normal shape, not on which base does it. The tradeoff is a new failure mode: the log fit raised `could not fit a double Gaussian` outright in **2 of 12**, where the linear fit never did, and that exception classifies nothing at all rather than degrading. Worth watching on the first real dataset moved onto this scale; `PROMINENCE_FIT_LOG_SCALE = False` restores the linear fit for a side-by-side.
    * `TestClassifyPeakProminences` now has twelve tests: the original coverage of the eligible types, that `fit_threshold` receives `log10` values, that the split happens in log space, that the report converts back with `10**value` rather than log units, that non-positive ratios are dropped and left unclassified, the no-eligible-peak decline, and the linear path with the constant switched off, plus five new tests for `_run_unfolded_level`'s two sources and its `None` fallback, the fitted/ratio/std-factor fields the report now carries, and the empty `std_factors` when the log scale is off.

* **Superseded, kept for the record: normalized peak classification briefly fitted and labelled type 3 peaks only**
    * `_classify_peak_prominences` selected every type 1, 2 and 3 peak. The classes it writes exist to spell out each event's `sequence`, which `_post_process_events` builds from type-3 peaks alone, so a carrier or folded-carrier peak that never joined a barcode was never going to appear in a sequence and yet was helping decide where the class boundary fell. It now reads type 3 and nothing else.
    * **Two things change in the output.** Type 1 and 2 peaks keep `classified = nan` and `classification_confidence = nan` where they previously carried values, so the in-app plot labels them `Filter: 1.0` with no `Class:`/`Confidence:` - the same shape the bound star already had. And the fit sample is now at most `Number of peaks` per event rather than every typed peak in it, so the double-Gaussian has less to work on; sequences themselves are unaffected in *shape*, but the threshold that produces them is estimated from a smaller, cleaner sample.
    * **A barcode decline is now also a prominence decline**, which was not true before: an event with no barcode contributes nothing, and a run with no barcode anywhere declines at the "no usable input" rung instead of falling back on the carrier peaks. `fit_fallbacks.md` is updated for both the new input set and this knock-on.
    * Three new tests in `TestClassifyPeakProminences` - the first tests this method has had - pin that only type-3 values reach `fit_threshold`, that only type-3 peaks come back with a class, and that a run with no barcode declines without calling the fit. All three fail against the previous selection.

* **Breaking: `PeakFinder`'s shipped defaults are now a working barcode configuration**
    * `Event Type` `Unspecified` -> **`Barcode`**, `Number of peaks` 1 -> **4**, `Lower Filter Threshold` -4 -> **-5**, `Higher Filter Threshold` 2 -> **5**, `Peak to Peak Distance Ratio` 5% -> **30%**. `Window Length Percentage` (10%) and `Min Carrier Blockage` (300 pA) already matched and are unchanged. The plugin exists to read barcodes, so it should be usable without retuning every field first; the defaults are pinned by a test.
    * **This changes results for anyone who accepted the old defaults**, in two ways worth separating. `Event Type` now types peaks at all where it previously did nothing, and the two filter thresholds widen the carrier bands from -4/+2 sigma to -5/+5. Nothing needs rescaling by hand - these are the values the settings dialog is used with in practice - but a saved configuration keeps whatever it stored, so only new plugin instances see them.
    * **`Peak to Peak Distance Ratio` at 30% lands in a costlier regime than 5% did**, because it is what decides how many candidates fall inside one window and the barcode search is exponential in that. Measured end-to-end over `filter_peaks`: a clean 4-peak barcode stays around 70 us/event, but a 16-candidate event at `Number of peaks` 6 runs ~500 us and a 40-candidate event with the window opened wide reaches ~8.5 ms - 85 s per 10k events. `BARCODE_SEARCH_NODE_CAP` bounds the worst case and logs when it fires.

* **Five metadata fields are no longer persisted, without changing what PeakFinder computes**
    * Dropped from the database: `unfolded_level`, `folded_level`, `bound_star` and `translocation_confidence` from the events table, and `base_at_edge` from the sublevels table. These are working values rather than results - the carrier levels every later stage measures against, the star's end now that the peak itself carries it as filter type 4 or 5, and the flag recording which bases the trim invented.
    * **They are still computed and still written onto `event_metadata` / `sublevel_metadata`, and every internal reader is untouched** - `get_plot_features` still draws the unfolded level and its two sigma bands, `filter_peaks` still reads `base_at_edge`, `_classify_bound_star` still sizes its height floor off `unfolded_level`. What changed is that `get_single_event_metadata` now returns shallow copies with the private keys stripped, and the fields are absent from the declared types and units. That accessor is reached only through `get_event_metadata_generator`, which `MetaDatabaseWriter` iterates when writing - so it is the one seam where "what PeakFinder computes" and "what gets persisted" part company.
    * **Both halves of that are required and have to agree.** `SQLiteDBWriter` builds its `INSERT` from the keys of the dict it is handed, not from the declared types, so a key with no column fails the write outright with "no such column", while a declared column that is never supplied is merely NULL. The two new tuples `PRIVATE_EVENT_METADATA` and `PRIVATE_SUBLEVEL_METADATA` name the fields once and drive the accessor; three new tests assert that they are absent from the declared types and units, that types and units agree key-for-key, and that the accessor strips them while leaving the internal dicts intact.
    * **What this costs on the reading side.** `SQLitePeakDBLoader` already treats all four event fields as `OPTIONAL_EVENT_COLUMNS` and omits them from its label when a database does not carry them, so nothing breaks - but a database written from now on will replay without the unfolded-level reference line and its sigma bands, without the "Bound star: …" annotation, and without the translocation confidence. The in-memory plot during fitting is unaffected, since it reads the internal metadata. The star's end is recoverable from the sublevel `filtered` values (4 = short end, 5 = long end) if that loader is later taught to read it; the carrier level is not recoverable from what remains, because the `normalized_*` columns are ratios rather than levels.
    * **`num_sublevels` could not be removed and is left in place.** It is not the plugin's to drop: `MetaEventFitter._define_metadata_types` injects it after the plugin's dict is built, and it is a hard-coded `NOT NULL` column in `SQLiteDBWriter`'s `CREATE TABLE events` alongside `start_time` and `event_id`. Suppressing it in the plugin would leave the writer inserting no value into a `NOT NULL` column; removing it properly means changing both the ABC and the writer's fixed schema, which is a wider breaking change than this one and would want its own decision.

* **Barcode selection now scores peak *width* too, and no longer prefers on ECD by default**
    * Diagnosed on Exp 1 / Ch 2 / Event 35304: a regular four-peak train at ~105 us spacing (p2, p3, p4, p6) with a low noise peak (p5) 60 us after p4. The selection took `p3+p4+p5+p6`, whose spacings are 105/60/50, over the train, whose recomputed spacings are 105/105/110. Spacing alone prefers the train by a factor of ten; what outvoted it was the ECD term, because the train's labels differ in depth by nearly a factor of two while p5's ECD sat comfortably among the trailing peaks'.
    * **`peak_width` is now a third similarity term**, plumbed into the `properties` dict alongside `sublevel_raw_ecd` - again an existing per-sublevel column that simply was not reaching `filter_peaks`, so no schema change. Spacing and width are both *time* quantities set by how fast the construct threaded, so a barcode's labels stay alike in both even when they thread at different depths; ECD is depth-weighted and does not.
    * **`BARCODE_ECD_WEIGHT` now defaults to 0**, with `BARCODE_WIDTH_WEIGHT` at 1 beside `BARCODE_SPACING_WEIGHT`. The ECD term is kept, not deleted: it is still what breaks a tie between equally well-matched sets, so zeroing the weight silences it as a *preference* while leaving the tie-break intact, and one constant restores it for a construct whose labels really are alike in charge. On the Event 35304 geometry, spacing+width picks the train in every width scenario tested (p5 narrower, equal, or wider), where spacing+ECD alone picked `p3+p4+p5+p6` whenever p5 was the wider peak, and then only by 3%.
    * A term whose values are not all finite is dropped wholesale rather than per peak, as before - so a database predating either column scores on what it has, and dropping ECD drops the tie-break with it, leaving ties to the earliest set.
    * **A skip needs headroom in `Peak to Peak Distance Ratio`**, which is the standing tension between allowing non-consecutive sets and treating `max_distance` as a hard constraint. Skipping p5 makes p4 -> p6 a single 110 us gap against a ~105 us train spacing, so on this ~1100 us event the intended set is only *legal* at a ratio of 10% or more; at 9.5% no four-peak set exists at all. Both cases are pinned by tests, the second deliberately asserting the train is *not* recovered.
    * Tests: the two ECD-preference tests are retargeted to width, a new one raises `BARCODE_ECD_WEIGHT` to confirm the ECD term still works when asked for, the tie-break test now uses uniform widths so ECD is what breaks the tie, and two new tests cover the Event 35304 geometry and its distance-limit headroom.

* **Breaking: the barcode is now the best-*matched* set of type-1 peaks, not the most prominent consecutive run**
    * The old step 2 slid a window of `num_peaks` time-consecutive type-1 peaks and kept the one with the highest summed raw prominence. Nothing in it looked at whether the peaks were evenly spaced or alike in size - a barcode's two defining properties - and because runs had to be consecutive, one off-pattern peak inside a real train either joined it or truncated it.
    * **The new rule.** Candidates are the type-1 peaks with another type-1 peak within `max_distance`. `_select_barcode_peaks` then scores every legal set of exactly `num_peaks` of them on how alike its *consecutive* peak-to-peak spacings are and how alike its peaks' `sublevel_raw_ecd` values are, each term divided by a per-event median so both are dimensionless, weighted by the new `BARCODE_SPACING_WEIGHT` / `BARCODE_ECD_WEIGHT` constants. Lowest total wins; ties go to the largest total ECD, then to the earliest set. Scoring consecutive differences rather than spread about a mean is deliberate: a barcode whose spacing or depth drifts as the translocation slows is still one barcode.
    * **Sets need not be consecutive.** An off-pattern peak in the middle of a train is now skipped, and **keeps its type 1** rather than being rejected - so it does not appear in the event's `sequence`, which is therefore shorter than the count of type-1 peaks spanned by the barcode.
    * **`max_distance` is a constraint on the selected set**, checked on the spacings recomputed *after* peaks are skipped, so a skip that would put two type-3 peaks more than `max_distance` apart is illegal however well it scores. Adjacent pairs, not all pairs - the total span of a barcode is still unbounded.
    * **Prominence no longer takes any part in the selection.** It still drives the class 0/1 call in `_classify_peak_prominences`. `test_most_prominent_cluster_is_chosen_over_an_earlier_one` is repurposed as `test_a_later_cluster_can_win_on_score`: the geometry that guarded "consider every candidate set, not just the first" is kept, driven by ECD instead, and arranged so the *later* cluster has to win against the tie-break.
    * `sublevel_raw_ecd` is plumbed into the `properties` dict `update_event_metadata_post_processing` rebuilds. No new column and no schema change - the field has always been per-sublevel metadata; it simply was not reaching `filter_peaks`. A database written before it was plumbed supplies NaN, which drops the ECD term and scores on spacing alone rather than poisoning the comparison.
    * **Runtime.** The search is exponential in `num_peaks` and, more sharply, in how many candidates fall inside one `max_distance` window, so `Peak to Peak Distance Ratio` now has a cost as well as an effect. Measured end-to-end over `filter_peaks`: 17 -> 68 us/event on a clean 4-peak barcode, 51 -> 497 us at 16 candidates with `num_peaks` 6, and 149 us -> 8.5 ms on a 40-candidate event with the window opened to half the event - about 0.7 s, 5 s and 85 s respectively per 10k events. Two exact prunes keep the normal case cheap (a partial set already costing more than the best complete one is abandoned, as is one with too few candidates left to finish), and `BARCODE_SEARCH_NODE_CAP` bounds the pathological case at 100k partial sets, logging the event's candidate count and keeping the best complete set found so far. An exact O(N*d^2*k) DP over `(prev, last, count)` was built and discarded: it agreed with the search on 400 random events but ran 2-12x slower at every size measured, because the cost prune fires almost immediately on a near-ideal barcode while the DP always pays its full state space.
    * **What it does and does not discriminate, measured.** The search is exact - verified against brute-force enumeration of every subset. Whether the *objective* prefers the true barcode is a separate question, and depends on how regular the real train is against how many stray type-1 peaks compete with it: recovery of a planted 4-peak barcode across 60 random events per cell runs at 100% with no strays at any jitter, 95% with 2-4 strays, 85-90% with 8, and falls to 43% with 16 strays at +/-3 us jitter on a 45 us period (3% at +/-12 us). Strays there carry ECDs uniform over 0.3-6.0 against a label ECD of 2.0, so a few sit essentially on the label value; real folds and blips are likely easier to separate, and the weights are exposed as constants for exactly this reason.
    * Nine new tests cover the ideal train, the mid-train skip, ECD choosing between two equally regular trains, the recomputed-gap constraint refusing a skip, the ECD tie-break, exactly-`num_peaks`, the no-ECD fallback, too-few candidates, and isolated peaks never reaching the search.

* **The bound-star peak now carries its end in its own `filtered` label: 5 for the long end, 4 for the short**
    * `_classify_bound_star` previously recorded its finding only on the event, as `bound_star`, leaving the peak itself labelled -1 like any unclassified blip - so nothing downstream of the metadata could point at *which* peak the star was. The winning candidate's `filtered` entry is now rewritten to 5 or 4, matching the `"long end"` / `"short end"` the event records, and both codes are written here and nowhere else.
    * **Only the winner, and only when its end is known.** Losing candidates on a multi-candidate event keep their -1, and a star on an event with no `translocation_direction` keeps -1 as well, since the label *is* the end and there is no end to name. The pass runs last of the four, after prominence classification (which selects on types 1, 2 and 3) and after the sequence builder (type 3), so no earlier stage can see the new codes; the `filter_peaks` re-run that would otherwise overwrite them happens earlier still, inside `_classify_folded_unfolded`.
    * **The pass is no longer idempotent**: a second run would not find the starred peak in the -1 pool it draws candidates from. `_post_process_events` already prevents re-running it, via `_global_postprocessing_done`, and this is now stated in the docstring rather than left implicit.
    * The report's peak-filtering breakdown gained `Type 4 (Bound Star - Short End)` and `Type 5 (Bound Star - Long End)`. **Expect the Type -1 count to fall by exactly one peak per starred event**, which is the only statistic that moves: the "Filtered/Unfiltered peaks" totals are derived from `classified`, not `filtered`, and are unaffected.
    * `test_losing_candidates_keep_their_labels` asserted the whole `filtered` array came back untouched and is updated to the narrower contract it was really guarding - losers unchanged, winner relabelled. Two new tests cover the mapping across all four combinations of trace position and translocation direction, and the no-direction case; all fail against the prior behaviour.

* **Breaking: `filter_peaks` typed carrier-seated peaks as baseline peaks in the barcode branch**
    * Type 0's band was `t2*s` wide, sized from `Higher Filter Threshold` - the tolerance meant for the *carrier* levels - while type 1's band opens at `U + t1*s`. The two overlap whenever `U <= (t2 - t1)*s`, and since type 0 was tested first it claimed the overlap: a peak sitting on the unfolded carrier came out type 0. Measured on an event with `t1/t2 = -5/+5`, `s = 0.088 nA` and `U = 0.77 nA`, the type-0 ceiling sat at 0.44 against a type-1 floor of 0.33, so any peak whose bases landed in `[0.33, 0.44]` was mistyped - and being lost from the type-1 pool it could also drop a barcode run below `Number of peaks`, removing the event's sequence entirely.
    * **Two independent changes, either of which fixes the observed event.** The baseline band is now a fixed `BASELINE_BAND_SIGMA = 3.0` class constant rather than `t2`, because the two size different things; and type 1 is tested ahead of type 0, so an overlap can no longer mistype a carrier peak whatever the settings and however noisy the baseline. Type 0 stays reachable for genuinely baseline-seated peaks, which is why the band was fixed rather than intersected with the carrier band. Type 2 is still tested before type 1, so that relationship is unchanged.
    * **This changes which peaks are typed 0, 1 and -1 on any dataset whose `Higher Filter Threshold` is not 3**, and therefore which events get a sequence. Nothing needs rescaling by hand: `Higher Filter Threshold` keeps its meaning around the carrier levels, and the baseline band is no longer user-tunable at all.
    * Both bands, and both bases, are blockage depths measured from the baseline, so the typing does not depend on the sign of the current; this was already true and is now stated in the docstring and asserted for both polarities.
    * Two new regression tests cover the overlap (a base inside both bands must be type 1) and the decoupling (raising `t2` to 5 must not widen the baseline band); both fail against the prior logic in the expected direction, returning type 0.

* **A type-1 peak whose base was pinned to an end of the trimmed event is now rejected to -1**
    * `find_peaks` walks outward from each peak to find its bases and stops at the array edge. For a peak near either end of the trimmed event that stop is the trim, not a minimum in the trace: the base holds whatever the event happened to be doing at its own edge - a carrier level, usually - so it reads as a valid type-1 base while neither it nor the prominence measured from it describes the peak.
    * A new per-peak `base_at_edge` flag is recorded in `_locate_sublevel_transitions`, where the base indices still exist - they are overwritten with currents immediately afterwards - persisted as a `base_at_edge` sublevel column, and read back by `filter_peaks` through the properties dict `update_event_metadata_post_processing` rebuilds. Recording it at detection time rather than reconstructing base positions later keeps the test exact (`index == 0` or `index == len - 1`) and needs no tolerance. Bases stopped early by `wlen` are not edge cases and are not flagged.
    * **Both ends are treated alike**, because `_classify_translocation_direction` may reverse a sequence: a rule that rejected only the leading edge would take opposite ends off a forward and a backward copy of the same molecule.
    * **Two consequences worth watching.** These peaks join the type -1 pool `_classify_bound_star` draws its candidates from, and they sit outside the type-3 span by construction, so a demoted peak whose blockage clears `2U + t2*s` can be crowned the event's bound star - star counts may rise. And because `Number of peaks` is both the minimum run length and the cap, demoting one member can drop a run below the minimum and leave the event with no sequence at all.
    * Databases written before the column existed read NaN, which types exactly as it used to; a peak record built without the key defaults the same way `max_blockage` already did. Four new tests cover rejection at each end, both ends at once, the flag being ignored on a non-type-1 peak, and the absent/NaN cases.

* **Peak prominence classification now splits on `normalized_prominence` rather than raw `prominence`**
    * `_classify_peak_prominences` fitted prominences in pA, which are not comparable across events whose unfolded level differs. It now fits each peak's prominence divided by its own event's unfolded level - the `normalized_prominence` column `update_event_metadata_post_processing` already filled in - so the split is comparable across events whose carrier drifts through a run. The threshold, centres and per-peak confidences are correspondingly dimensionless, and the `pA` suffixes on them in the report, the plot axis and the threshold annotation are gone.
    * `normalized_prominence` is only populated for an event with a positive `unfolded_level`, which `_classify_folded_unfolded` establishes before this classifier runs, so a peak whose event never got one is now skipped rather than classified on raw prominence. The "no peaks available" warning says so.
    * The fit itself is unaffected by the change of units: `_histogram_for_fit` bins by Freedman-Diaconis with a `MIN_FIT_BINS` floor, and the double-Gaussian fit and confidence derivation are scale-equivariant, so what changes the classes is the per-event denominator, not the rescaling.

* **Integration: `feature/peakfinders` merged against 1.8.0's develop**
    * `feature/peakfinders` (8 commits by Nada Kerrouri) was reconciled with `develop` on an integration branch rather than merged directly, the same way `feature_Peakfinder_classifier` was earlier in this release. The branch was 107 commits behind, and `develop` had since taken two breaking changes; neither touches anything the branch uses, so nothing on her side needed adapting.
    * **Four files conflicted, but only one of any size.** `PeakFinder.py` reported 70 hunks and ~2,800 conflicted lines - and **1,156 of develop's ~1,200 changed lines in that file came from a single `style: auto-fix via pre-commit hooks` commit**, so almost the entire conflict was black re-wrapping rather than disagreement. Measured before resolving, by re-reading develop's four commits against that file: everything else was 45 lines of docstrings, a 2-line docutils indent fix and a one-sentence docstring correction.
    * **Resolution rule, unchanged from the earlier integration: her logic wins unconditionally**, with docstrings re-applied on top. `PeakFinder.py` and `SQLitePeakDBLoader.py` were both taken wholesale from her branch and verified byte-identical to it before anything was layered back on.
    * **Three of develop's four docstring commits turned out to be superseded by her own docstring pass, and were deliberately not re-applied.** The sentence one of them edited in `get_empty_settings` no longer exists - she replaced that docstring's inherited boilerplate with a per-setting description of what this plugin actually declares - and the "Implementation notes" block another fixed the indentation of has been deleted outright. The two `NOTE:` comments the third dropped, she had already dropped.
    * **What was re-applied is the four `:param:`/`:raises:` blocks**, on `close_resources`, `_classify_folded_unfolded`, `_classify_peak_prominences` and `_classify_translocation_direction`. These are not cosmetic: `skip-checking-short-docstrings` defaults to true, so a docstring carrying no field section is skipped by `pydoclint` entirely - which is why her file passed the gate without them, and why re-adding them is a real addition rather than a formality. Each was checked against her code rather than pasted: the documented `RuntimeError` and `ValueError` are both genuinely raised in every method they are claimed for, the `ValueError` really is caught by the method's own plotting guard and does not escape, and **develop's `:param all_raw_ecds_array:` was dropped because her signature no longer has that parameter** - pasting develop's block verbatim would have introduced a pydoclint violation rather than fixing one.
    * **Her changelog entries were auto-merged into the wrong release and had to be moved.** Her branch predates both 1.7.1 and 1.8.0, so 1.7.0 was the newest header it carried and git anchored all 238 of her lines *inside that already-released section*. They now sit at the top of 1.8.0. Worth knowing for the next stale branch: git reported this as a clean merge, and nothing but reading it would have caught it.
    * **`future_fixes.md` kept develop's pruned form, plus one item of hers.** Three of the four items her side carried are stale - the abort-with-no-panel-message and the duplicated `QTimer.singleShot` are both fixed on develop (the code the latter describes no longer exists at all), and the `S608` interpolated-SQL reasoning has since moved to `DECISIONS.md`. Her log-normal `fit_threshold` item is genuinely open and is carried over next to the histogram cut-off. The rest of her side was the previous integration's completed-work narrative, which that file's own policy says belongs in the changelog and which develop had already pruned.
* **Fixed a time range with no end silently finding no events**: a range like `3.0-` was accepted by the Time Range dialog but then discarded, so event finding ran over no time at all; it now means "from 3 seconds to the end of the signal", as an end of `0` always has

* **Fixed the event finder channel list failing permanently** if it could not be read the first time, which then made Find Events fail for every channel of that plugin

* Gaussian Mixtures clustering and the protein tab's shape ensemble are now seeded, so re-running either on the same data gives the same answer instead of a slightly different one each time

* **An analysis run that stops early now says why on the status panel instead of interrupting with an error dialog and a traceback** — exporting a subset that matches no events was the common way to hit it

* A failed database query or an inconsistent database still raises an error dialog during subset export, so a real problem is not mistaken for an empty result

* **Fixed subset export failing on a subset with no fitted sublevels**, which was reported as "Failed to load sublevels data" rather than exporting an empty sublevels table

* **Fixed a metadata plot or clustering run silently reusing the previous subset's rows** when the database call behind it failed, instead of reporting that the subset returned nothing

* A metadata query that matches no rows is now reported as an empty result rather than as a failed query

* **Fixed a subset filter on a sublevel column finding no events when plotting events**: filters like `filtered = 5` were applied to the events table alone, so every one of them failed as an unknown column and was reported as an empty subset — event plotting, its navigation arrows and the protein tab's plots now apply a filter through the same table joins as the metadata plots

* **Assisted filters may now contain a subquery**, which is passed through exactly as typed instead of being rewritten against the outer query's tables; this also makes `GROUP BY`/`HAVING` inside a subquery work in assisted mode

* A filter naming a column that cannot be resolved now raises an error dialog when plotting events, instead of quietly reporting that no events matched

* **Fixed a clean `pip install poriscope` failing on import**: `typing_extensions` was imported by 38 modules but declared as a dependency nowhere; the native `typing.override` replaces it everywhere, including in newly generated plugins

* Test coverage is measured again: `pytest-cov` was declared in no dependency source, so the pull-request workflow's test step failed outright instead of running

* Tests now time out after 300 seconds by default rather than hanging until the CI job's own six-hour limit

* Removed a stray `poriscope/pytest.ini` that enabled coverage against the wrong root whenever pytest was run from inside the package

* `requirements.txt` is now UTF-8 instead of UTF-16, so it reads correctly in diffs and in any tool that assumes UTF-8

* The declared `mypy` version now matches the version the pre-commit hook actually runs

* Removed two dead `pre-commit` settings: an exclude naming a directory that does not exist, and `--exit-non-zero-on-fix` on a hook that applies no fixes

* Removed 455 KB of checked-in test data that no test referenced

* Removed an unused 394-line copy of the guided-walkthrough step list; it was a stale fork of the per-tab lists the app actually shows, and nothing loaded it

* Removed `FloatRangeLineEdit.get_values` and `used_floats`, which nothing called

## Poriscope 1.8.0: 2026-09-03

* **Fixed assisted metadata filters silently returning the wrong rows**, and they now work on experiment voltage, thickness and conductivity and on `experiment_id`/`channel_id`/`event_id` in every plot and when loading event data
    * A quoted value matching a column name was rewritten as a column reference; a filter on an experiment column emitted a table the query did not join
    * A bare `id` is still rejected, since it means a different row in each table, but now with instructions naming the qualifier to use

* Removed `WaveletFilter`'s internal lock; wavelet filtering now runs in parallel across channels and instances instead of one at a time

* **Fixed three ways event writing could lose data silently**
    * Resetting one channel could delete unrelated experiments; databases written by earlier versions are repaired on the next write
    * One failed event discarded every event already written in the same run
    * A write that could not open its output file, failed to commit, or failed to reset a channel reported success anyway

* **Fixed a CUSUM fitting bug that under-detected shallow sublevels** (`CUSUM`, `ClassicCUSUM`, `IntraCUSUM`)
    * Near-threshold transitions at a 3σ step are now found roughly 9 percentage points more often; well-separated transitions are unaffected
    * **Fitting results change** — re-fitting existing data may yield more sublevels than before
    * `PeakFinder` is unchanged and still carries the defect

* **Updated Data Plugin: `PeakFinder`**
    * **BREAKING**: `Peak to Peak Distance Ratio` compared a sample count against microseconds, so it only matched its declared percentage at 1 MHz — multiply an existing value by the sample rate in MHz to keep current clustering
    * **Fitting results change**: `bitthresh` is deleted, all three classifiers now use a double-Gaussian fit, and the threshold is the analytic crossing of the two fitted components rather than the midpoint of their means
    * Both components are re-fit with each mean constrained to its own side of the histogram valley, so the higher one no longer covers the lower population's shoulder
    * A single-population dataset is now recognised as such and split above the fitted population, instead of being force-fit as two
    * The second component no longer collapses to zero width on a sharp mode with a decaying shoulder, and the fit is no longer distorted by a heavy sparse tail
    * Translocation direction is estimated from the 5th–95th percentile of the log-ECD ratio but applied to every event, so no event goes unclassified for being an outlier
    * New `bound_star` event metadata column recording which end of the construct carried the bound star through the pore, as `long end` or `short end`
    * A bound-star candidate must now be deeper than a fold, so a leading fold is no longer labelled as the star
    * New **Bound Star Classification** report section: sequence-bearing events, the starred/unstarred split, and a per-sequence breakdown
    * `filter_peaks` now picks the most prominent barcode candidate rather than the first one it finds
    * Warnings raised during classification are saved into the report instead of only being logged
    * A fitted mean that is not centred on the histogram peak it describes is now logged
    * Fixed the saved classification report being duplicated once per channel
    * Removed the unused **Visualize Classification** setting and its dead `Classify Levels` gate
    * Removed the "Outliers excluded from fit" lines, the "ECD-filtered outliers" report line and the smoothing-spline overlay from the three classification plots
    * Fields absent from an event's metadata are omitted from plot legends rather than printed as `nan`
    * Fixed an event fitted with classification disabled losing its whole figure to a `KeyError`
    * Fixed 14 silently-swallowed exceptions in the three classifiers, one of which dropped events from the folded/unfolded tally with no log line

* **Updated Data Plugin: `SQLitePeakDBLoader`**
    * `get_plot_features` now produces the same labels as `PeakFinder`, including `bound_star` and both confidence values
    * Databases written before those columns existed still plot, degrading to the fields they hold

* **New: `fit_fallbacks.md`**, documenting every fallback in `PeakFinder`'s double-Gaussian fit chain and how each classifier responds to a degraded fit

* **BREAKING: `@log`'s `debug_only` parameter is removed.** It was never read; passing it now raises `TypeError`

* **BREAKING: `DataPluginModel.get_plugin_details` is removed.** Resolve the plugin and call `get_raw_settings()` on it instead

* **BREAKING: nine dead signals are removed and the sidebar Exit button is gone.** `MetaView.save_requested` is the one a plugin author could have referred to; the window close button already ran a more complete shutdown than Exit did

* Fixed `@log`'s debug gate testing the root logger's exact level, so raising one plugin module to DEBUG produced nothing and a root level below DEBUG logged less than DEBUG did

* Fixed a `config.json` missing any key but the most recently added one killing the app before logging existed; every missing key is now restored and named in a warning

* Fixed a failed session save taking the app down, and a failed Save Session saying nothing: an autosave failure now reports on the status panel, a save to a chosen path reports as an error

* Fixed `get_raw_settings()` handing out a live reference to a plugin's internal settings, so renaming a plugin retroactively changed what session history had recorded

* Fixed three defects in plugin settings validation: a missing `Value` raised `KeyError`, a `None` value beside a `Min` raised `TypeError` instead of reporting a missing value, and a `Folder` parameter with file filters was rejected

* Fixed 11 plugin settings defaults declaring `Type: float` but giving an int (`CUSUM`, `ClassicCUSUM`, `IntraCUSUM`, `Basic_PeakFinder`), which rejected the schema on any path handing it back unchanged

* Fixed the `post-merge` hook picking whichever Python started first, which under Git Bash on Windows was the MSYS2 interpreter, so every merge silently skipped the docs, requirements and wavelet-library steps

* Fixed `pytest tests/unit` erroring intermittently with "Internal C++ object already deleted", from multi-select combo box event filters installed on the application and never removed

* Fixed CI: a third-party apt repository the project never uses could fail every workflow; all eight `apt-get update` sites now drop those sources first

* **New Dev Tooling: `scripts/new_plugin.py` generates a compliant data plugin to start from** — `python scripts/new_plugin.py MetaEventFinder MyFinder`; `--list` shows the eight families and every shipped plugin

* **New Dev Tooling: plugin settings schemas are checked for self-consistency**, by `python scripts/check_plugin_schemas.py` and on every branch push

* **New Dev Tooling: two pre-commit gates for plugin code**, since plugin discovery executes every file it finds — a `ruff` security selection over `poriscope/plugins/`, and a check that the eight data-plugin families run nothing at module level

* **New Dev Tooling: `.github/CODEOWNERS`**, so a pull request automatically requests the maintainer of the code it touches. Advisory only — it never blocks a merge

* **New Dev Tooling: the autodoc generators now delete pages for modules that no longer exist**

* Changed: the no-nested-functions convention is relaxed — a short, simple closure handed to a callback, timer or signal is now permitted

* **Docs**
    * The Scripting guide explains how to raise the log level for one plugin at a time; the Settings window keeps one application-wide level
    * `PeakFinder.py` gained a full comment and docstring pass, including where every method is called from
    * The docs render is fixed for classes whose name begins with an underscore, and for a docstring type ending in an underscore
    * The reasons for the six declined lint rules are recorded per rule rather than as one claim that only held for two of them

## Poriscope 1.7.1: 2026-08-31

* Fixed the documentation build failing on CI with several hundred `wrapper loop when unwrapping PySide6.QtGui` errors: `conf.py`'s PySide6 mock is removed, and both docs workflows now install the Qt native libraries the build needs
* Fixed a broken image on the Menus and Sessions page, from a filename case mismatch only Linux resolves strictly
* Fixed hotfix branches running no CI at all; `hotfix/*` is now in the trigger list for the branch tests and the docs render check
* Changed: `poriscope/__init__.py` logs a warning when `exposed` imports only partly, instead of passing silently

## Poriscope 1.7.0: 2026-08-31

### What's New since Poriscope 1.6:

* **New: Reset Session**, under File
    * Returns the app to a freshly-launched state without quitting: every data plugin deleted, every analysis tab closed, both histories cleared, landing page restored
    * Running workers are stopped first, an active walkthrough is cancelled, and the sidebar highlight, status panel, sidebar layout and Help window are all reset
    * The saved session files are left on disk, so Restore Session still works afterwards
    * The plugin menus are re-scanned, so a plugin added mid-session appears as it would after a relaunch

* **New: Save Session captures each tab's live subset filters, and Load Session restores them**
    * `MetadataView`/`ProteinView` filters previously vanished when a session was closed and reopened
    * New `MetaController.get_session_state()`/`restore_session_state()` hook, so any tab can persist its own state
    * Session state is now flushed on a normal app close, not only when a plugin or tab changes

* **New: the Settings window's Reset button is hooked**
    * Restores the data server location, user plugin folder and logging level to their defaults, routed so they take effect immediately
    * Touches only `config.json` — saved sessions, configured plugins and log files are left alone
    * The Settings rows now describe what each action does and what it leaves alone; "Clear Cache" empties the application log file

* **New: changing the user plugin folder takes effect immediately**, so plugins in the new folder appear in the menus without a restart

* **New Data Plugin: `ThresholdBlockageFinder`**
    * Subclass of `ClassicBlockageFinder` that imposes much tighter bounds on the start and end times flagged in the output

* **Deprecated Data Plugin: `ABF2Reader`**
    * Renamed to `TCossaLabABFReader` to reduce ambiguity with file types
    * Fixed `ABF2Header` never closing its file handle after parsing an ABF header
    * Fixed `ABF2Header`'s per-channel scale factor reading `nTelegraphEnable[0]` for every channel, corrupting current scaling on multi-channel files

* **Updated Data Plugin: `WaveletFilter`**
    * Fixed a ctypes ABI mismatch (`c_int` vs `int64_t`) on the signal-length argument that risked memory corruption on large arrays
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugin: `NoFitter`**
    * Fixed an unbounded backtrack loop that could corrupt sublevel edges via negative indexing instead of rejecting the event
    * Added missing validation for `None` baseline and padding inputs
    * Fixed `_locate_sublevel_transitions`'s docstring being abstract-method boilerplate rather than describing the single baseline crossing it locates

* **Updated Data Plugin: `ClassicCUSUM`**
    * Removed an undocumented `/5` threshold divisor and a leftover debug `print()` that made this fitter far more sensitive than `CUSUM`/`IntraCUSUM`
    * Fixed `_locate_sublevel_transitions`'s docstring not mentioning this class's actual difference from `CUSUM`: Step Size is used directly in units of σ

* **Updated Data Plugins: `ClassicBlockageFinder`, `BoundedBlockageFinder`, `ThresholdBlockageFinder`**
    * Fixed a `ZeroDivisionError` on constant-signal chunks in baseline histogram calculation
    * Fixed dead code that silently skipped baseline-histogram window symmetrization
    * Fixed an ambiguous end-of-chunk check that could silently drop the remaining events in a chunk
    * Removed a dead `median_abs_deviation(data)` call whose result was discarded (`ClassicBlockageFinder`/`BoundedBlockageFinder`)
    * Replaced `_filter_events`' opening `assert` with an explicit `RuntimeError`, so a missing reader is still reported under `python -O`
    * Fixed `_filter_events`'s `channel` docstring describing it as a bool, and `_get_baseline_stats`'s promising three return values where it returns two

* **Updated Data Plugins: `CUSUM`, `IntraCUSUM`, `NoFitter`**
    * Fixed an off-by-one indexing bug that shifted every reported extreme-sublevel duration by one level
    * `NoFitter._locate_sublevel_transitions` now validates `padding_after`/`baseline_std` for `None`, as its own docstring promised
    * `IntraCUSUM._populate_event_metadata` now raises rather than computing `np.sign(baseline_mean)` with no `None` guard
    * `_populate_sublevel_metadata` now raises a clean `ValueError` when `baseline_std` is `None`, instead of failing silently later
    * Removed a dead `get_samplerate(channel)` call in `construct_fitted_event`, and fixed a stale copy-pasted "CUSUM cannot operate..." message in `NoFitter`'s error path
    * Fixed `construct_fitted_event`'s docstrings claiming `:raises RuntimeError:` when both actually return `None`
    * Fixed `CUSUM._locate_sublevel_transitions`'s docstring being abstract-method boilerplate rather than describing its log-likelihood-ratio changepoint detection

* **Updated Data Plugins: `Basic_PeakFinder`, `PeakFinder`**
    * Fixed an empty-slice bug that wrongly rejected legitimate events ending at the trace boundary
    * Fixed seven latent defects in the classifier: unguarded `Optional` values used in arithmetic, a `None` test that could never fire, and a `baseline_std` conversion that hid a legitimate `None`
    * Removed `PeakFinder.fit_2_gauss`, which had no callers and could never have run

* **Updated Data Plugin: `BesselFilter`**
    * Fixed a boundary check that allowed `Poles = 0` despite requiring a positive integer
    * Fixed `reset_channel`'s docstring being a copy-paste of `close_resources`'s

* **Updated Data Plugins: `ChimeraReader20240101`, `ChimeraReader20240501`, `ChimeraReaderVC100`, `TCossaLabABFReader`, `LegacyElementsReader`**
    * Fixed dead filename-pattern validation that never actually rejected malformed filenames
    * File-not-found and permission errors now name the file that is missing or inaccessible, instead of "at least one of the input raw data files"
    * Removed a dead `config["v_offset"]` lookup in `ChimeraReaderVC100._convert_data`, and fixed its class docstring saying "VC1100"
    * Fixed `_convert_data`/`_get_configs` docstrings claiming "data is already scaled"/"no config files needed" when each applies a conversion and parses a header

* **Updated Data Plugin: `SingleBinaryDecoder`**
    * Fixed exception handling wrapped around the wrong line, leaving real file-open errors unprotected
    * Fixed the class docstring being a leftover "Chimera VC1100" description; this reader is a generic, fully user-configured binary decoder

* **Updated Database Plugins: `SQLiteDBWriter`, `SQLiteEventWriter`, `SQLiteDBLoader`, `SQLitePeakDBLoader`, `SQLiteEventLoader`, `MetaDatabaseLoader`, `MetaDatabaseWriter`**
    * Fixed several `UnboundLocalError`-masking exception handlers that hid the real database error
    * Fixed a `finally`-block bug that swallowed real write errors and reported success instead
    * Unused `SAVEPOINT`s are now released or rolled back instead of being a no-op
    * Hardened interpolated experiment/channel/index values and escaped quotes in experiment names, so legitimate names no longer break queries
    * Fixed a crash on an empty query result and on a missing unfolded-level value
    * Fixed `SQLiteDBWriter` writing sublevel and event-data rows keyed on a `None` event id instead of rolling back
    * Fixed three regressions in `SQLitePeakDBLoader.get_plot_features`: a lost `return`, a dropped `None`-result guard and a dropped unfolded-level guard
    * CSV export can now be aborted, like every other long-running operation
    * Fixed stray logging arguments that would crash the moment the log line was emitted
    * Fixed an overly broad exception clause that made two more specific handlers unreachable
    * Fixed `SQLiteDBLoader.get_experiment_names`/`_ensure_event_counts` never closing their connections, and `_ensure_event_counts` never closing its cursor
    * Fixed `SQLiteDBLoader.get_empty_settings` being decorated twice with `@log`, double-logging every call
    * Fixed a warning log in `SQLiteDBLoader._load_event_data` missing an `f` prefix, so it logged the placeholders instead of the values
    * Fixed `MetaDatabaseLoader.load_event_data`/`query_database_directly_and_get_generator` never closing the inner generator they wrap
    * Fixed `SQLiteDBWriter._write_event` reporting every database error as "Cannot Overwrite Existing Event"; real errors now propagate with their own message
    * Fixed `MetaDatabaseWriter.write_events` never calling `_write_event(..., abort=True)` on abort, so subclasses never got the rollback and close they rely on
    * Fixed `reset_channel` opening a savepoint that was never released, and corrected both docstrings, which described closing resources for a method that deletes the channel's rows
    * Documented that `reset_channel(channel=None)` does not reset all channels, since SQL `channel_id = NULL` never matches
    * Fixed `SQLiteDBWriter.close_resources`'s docstring documenting per-channel behaviour for a method that ignores its `channel` argument
    * Fixed `SQLiteDBWriter._insert_event_data`'s docstring documenting a nonexistent `channel` parameter
    * Fixed `SQLiteEventWriter._write_data`'s docstring documenting a nonexistent `batch_size` parameter, and a stale comment claiming `executemany` batching
    * Fixed `SQLiteEventLoader._finalize_initialization` stripping `sqlite_sequence` after the table comparison had already run, so it was misreported alongside genuinely unexpected tables
    * Fixed `SQLiteEventLoader.get_valid_indices`'s docstring claiming an "all channels" mode it does not have
    * Removed `SQLiteEventLoader.get_num_events`'s unreachable `None`-row check and the dead `except ValueError` beside it

* **Updated Backend Infrastructure: `MetaEventFinder`, `MetaEventFitter`, `MetaWriter`, `MetaReader`, `MetaController`, `EventWorker`, `MetaModel`, `LogDecorator`, `BaseValidator`, `QtHandler`**
    * Fixed an unexpected exception during event processing leaving a channel permanently unable to run again
    * Fixed a falsy-zero bug that silently dropped a legitimate chunk-boundary event start
    * Fixed a `ZeroDivisionError` in fit-progress logging that could permanently wedge a channel
    * Fixed a `TypeError` raised inside any plugin generator being reported as a successful run that found nothing
    * Fixed event fitting progress never reaching 100% whenever any event was rejected
    * `force_serial_channel_operations()` is now enforced per plugin instance rather than per analysis-tab model, so one writer can no longer run two channels at once while unrelated plugins serialize for nothing
    * All five worker-driven generators share one abort contract, and an aborted generator is closed explicitly rather than left to garbage collection (`MetaModel.reset_lock` is renamed `discard_generator`)
    * Fixed finished `Worker`/`WorkerThread` objects, and everything their generator closure captured, being retained for the whole app session
    * App shutdown now waits for worker threads to finish instead of potentially destroying a still-running thread
    * Fixed the `@log` decorator silently breaking exception handling and result logging for every generator-based method in the app
    * `BaseValidator` now properly enforces its abstract validation methods
    * Added a reentrancy guard so concurrent error/warning logs no longer stack multiple modal dialogs
    * Corrected `MetaReader.load_data`/`continuous_read` documenting `start`/`length`/`total_length`/`chunk_length` as sample indices when they are times in seconds; the out-of-bounds error now reports genuine seconds
    * Fixed `MetaEventFinder.__init__` resetting `self.reader` after `apply_settings`, discarding an already-configured reader
    * Fixed `MetaEventFinder.find_events` processing every remaining range before discarding the results when aborted mid-run, instead of stopping when the abort arrived
    * Fixed `MetaEventFitter.fit_events` crashing with a `KeyError` on mismatched-length sublevel metadata; the event is now cleanly rejected instead of aborting the channel
    * Fixed `MetaWriter._rescale_data_to_adc`'s auto-scaling fallback taking its offset from `adc_max` instead of `data_max`, silently corrupting ADC-encoded values
    * Fixed `MetaWriter._validate_param_types` never calling `super()`, which skipped primitive-type validation for every `MetaWriter` subclass
    * Fixed `MetaReader.report_channel_status` always formatting the samplerate to 2 decimal places, from a dead ternary inside the f-string's format spec
    * Fixed `MetaEventFinder._find_events_single_range`'s orphan-event-end check being dead code, which discarded every event in a chunk whenever the range started mid-event
    * Fixed `MetaController`'s two relays logging the literal `"str(e)"` instead of the exception, and reporting a relay failure as "not a callable attribute" for a callback that had already resolved
    * Fixed `MetaEventFinder.report_channel_status` skipping the "Accepted ...s of data" line whenever a channel had zero rejected data
    * Fixed `MetaEventFinder.find_events` swallowing a `RuntimeError` that is only raised after the channel's accumulated events have been reset; it now propagates. Removed an unreachable `except StopIteration` beside it
    * Fixed `MetaEventFinder.get_event_indices` comparing its per-channel dicts against an empty list, so it never raised on a fresh instance; dropped its unused `index` parameter
    * Fixed `MetaEventFinder.get_single_event_data`'s docstring documenting an `IndexError` it catches internally
    * Fixed `MetaEventFitter.get_metadata_columns`/`get_sublevel_columns` sampling event 0's metadata, which crashed with `KeyError: 0` whenever event 0 was rejected; both now sample any available entry

* **Updated Plugin Management: `DataPluginController`, `DataPluginModel`, `BaseDataPlugin`**
    * Fixed `_validate_param_types` never actually validating primitive setting types, and made the fixed check skip resolved plugin references rather than reject them
    * Fixed `apply_settings` registering parent/dependent relationships under the wrong metaclass for any plugin subclassing another concrete plugin, which could crash deletion of an unrelated plugin
    * Fixed `apply_settings` catching every exception while deciding whether a settings value is a plugin, so an unexpected failure left a plugin deletable out from under a live dependent
    * Fixed a user plugin silently replacing a built-in of the same filename; the first file found now wins and the collision is reported
    * Fixed editing a plugin and dismissing the dialog with Esc or the close button crashing and leaving the plugin's parent links broken in the live model
    * Fixed `delete_plugin` never removing the deleted plugin from `plugin_history.json`, leaving deleted plugins persisted across restarts
    * Fixed `edit_plugin` unregistering a plugin from all of its parents up front and never restoring those links on any abort path
    * Fixed `update_plugin_key` silently overwriting and orphaning any plugin already registered under the destination key; it now refuses the rename
    * Fixed `edit_plugin`'s docstring documenting a nonexistent `subclass` parameter and a raise it never performs, and `update_plugin_key`/`register_plugin`/`get_temp_instance`'s docstrings naming exceptions that never happen
    * Fixed `set_settings`/`update_data_server_location` each carrying the other's docstring, and `DataPluginModel`'s class docstring calling it a "controller"

* **Updated App Shell: `MainController`, `MainModel`, `MainView`**
    * Fixed Load Session / Restore Session failing with an "already exists" error when the workspace already held state; a load now resets the session first, syncs the sidebar highlight, and names what it loaded on the status panel
    * The signal-bus dispatcher no longer retries a failed call with `func(None)`: arity is checked by reflection first, so a target runs at most once and a `TypeError` from its body is reported with a traceback
    * The dispatcher unpacks a return value from the callee's declared return type rather than by trial, which also fixes a `None` result never reaching a callback that takes trailing arguments
    * Both signal-bus handlers now share one dispatch body, so an unregistered metaclass no longer crashes out of a Qt slot and the two cannot diverge in what they log
    * Fixed seven emit sites passing a bare value where the signal declares a tuple, and made the six global-signal connections explicitly `DirectConnection`
    * Fixed the main menu's **Abort Analysis** item doing nothing whatsoever
    * Replaced a hardcoded institution-specific network path default with the user's home directory
    * A corrupted config file now regenerates defaults on startup instead of crashing the app
    * `JsonDefaultSerializer` now also handles `Enum`, `datetime`/`date` and `set`/`frozenset` values instead of only `PurePath`
    * All config file writes are wrapped in error handling instead of letting a write failure crash the app
    * `app_config` path values are normalised to `str`, so a `Path` can no longer reach a plugin's `Folder` setting and be rejected
    * Fixed a missing comma in `config_path` construction that concatenated `".."` and `"configs"` into one path segment
    * `MainController.previous_plugin_history` is always initialized to a dict, removing a fresh-install path that relied on a caught `AttributeError`
    * Fixed `send_curent_data_server`/`send_curent_user_plugin_location` being decorated `@Slot(str, str, object)` despite taking no parameters
    * Fixed `populate_available_plugins`'s `try/except` around `os.walk` being dead code, so a plugin directory that does not exist contributed zero plugins with no diagnostic
    * Fixed `clear_cache`'s docstring documenting nonexistent parameters and deletion behaviour it does not have; it truncates `app.log`
    * Removed a dead `except ValueError` in `load_session` special-casing a message that is never raised
    * Added class docstrings to `MainController`, `MainModel` and `MainView`, and method docstrings to both signal-dispatch entry points

* **Updated Frontend Base Class: `MetaView`**
    * New `plugin_state_changed` signal and abstract `notify_plugin_state_changed` hook, so any tab can notify all others when a plugin's state changes (e.g. new columns added to a database). Every subclass must now implement it, even as a no-op
    * `_set_control_area` takes a `QBoxLayout` rather than a `QLayout`, restoring the intent of its original docstring
    * Removed a stray, uncallable leftover `add(a, b)` method

* **Updated Frontend Widgets: `IntegerRangeLineEdit`, `CommaFloatRangeLineEdit`, `FloatRangeLineEdit`, `FloatRangeValidator`, `DictDialog`, `MultiSelectComboBox` (`multiselect_filter.py`)**
    * Fixed `IntegerRangeLineEdit`/`CommaFloatRangeLineEdit` mis-parsing ranges containing an extra `-`; these fields only ever hold times or event indices, so a leading `-` is now rejected outright
    * Fixed `FloatRangeLineEdit` crashing with an `AttributeError` on any invalid or empty input, because it never defined a `logger`
    * Fixed `DictDialog`'s hidden Input File/Output File/Folder "has a value" checkbox always starting unchecked, which disabled OK on an already-configured plugin until the file picker was re-run
    * Fixed `FloatRangeValidator` inflating a bare-integer end value (`"2"` → `"20"`) before the ordering check, so an inverted integer range like `"10-2"` was accepted and stored backwards
    * Fixed `MultiSelectComboBox.addItems` (filter variant) never refreshing the Select All button text or summary line-edit after repopulating
    * Fixed the filter variant's outside-click handler falling through to `super().eventFilter(...)`, so the dismiss-click also reached the widget underneath
    * Both multi-select combo boxes no longer accept an `addItem` `userData` argument they silently threw away
    * Five widget classes no longer store state under a name that shadows an inherited Qt method (`NumericLineEdit.validator`, `DictDialog`/`DropdownDialog`/`TimeWidget.result`, `BaseSubsetFilterDialog.layout`)
    * Removed `_edit_button_clicked`/`_delete_button_clicked`, two dead methods superseded by the `edit_filter`/`delete_filter` callback chain
    * Removed the unused `comma_delimited_float_range_edit.py` module, `FloatRangeLineEdit.get_values_with_type_info`, `ClusteringSettingsDialog.update_unit_label`/`reset_top_inputs`, and two stray debug `print()` calls

* **Updated Frontend Controls: `RawDataControls`, `EventAnalysisControls`, `ClusteringControls`, `MetadataControls`, `ProteinControls`**
    * Fixed `MetadataControls`/`ProteinControls` crashing when the bins field ended in a trailing comma
    * Fixed an unmapped `button_type` raising `AttributeError` in three of the five files instead of being ignored, as it already was in the other two
    * Removed the duplicated, uncallable `get_nested_value`/`get_plugin_data` helpers from all five files, along with their two dedicated test classes

* **Updated Frontend Infrastructure: Walkthrough**
    * Fixed the transparent "Analysis" menu highlight overlay leaking whenever a milestone dialog was dismissed manually instead of by navigating on
    * Fixed the auto-advance polling loop rescheduling itself after the dialog was manually dismissed, risking a late call into the completion handler
    * Fixed an abandoned walkthrough polling at 5 Hz for the rest of the process's life, each callback closing over a widget that might already be gone
    * Dialog repositioning uses a real `on_move` hook on `StepDialog` instead of monkey-patching `moveEvent`, which had suppressed `QDialog`'s own handler
    * `start_walkthrough` returns its fallback dialog directly instead of constructing one guaranteed to raise

* **Updated Frontend Plugins: `MetadataView` and `ProteinView`**
    * Event navigation is now filter-aware, driven by a cached event_id list and bisect search instead of a DB query per click
    * The old range field is replaced by **Event ID** (snaps to the nearest filtered event at or after the requested id) and **# Events** (how many filtered events to show from there)
    * Forward/backward arrows step through the filtered set with wrap-around, so the subplot count is predictable and no step lands on an empty range
    * The display panel shows the filtered total, the first and last event ids, and the active filter name and subset label
    * Fixed the scoped channel identifier being the selection tree's display string rather than an `int`, so cache-staleness comparisons silently never matched
    * Selecting no database loader no longer logs an error and raises a dialog
    * `_load_filter` no longer raises into its own `except` handler, so a genuine Qt failure below the parse step surfaces; both views now report a duplicate filter name identically and on the message panel

* **Updated Frontend Plugin: `MetadataView`**
    * Fixed Categorical Histogram, Scatterplot and Raw/Filtered Event Overlay failing to render after "Plot Events" + "Update Plot", from a stale `self.axes` reference the staleness check missed
    * Fixed a silent crash in `_export_csv_subset` when the Export Settings dialog was cancelled
    * Now refreshes its available column list when another tab commits new columns to the selected database
    * Fixed the tab re-plotting datasets it had already drawn, because the overlay guard compared a display string against an `int` channel id
    * Fixed a no-op Update Plot click still recording an Undo step that re-rendered an identical figure
    * Fixed plot features arriving with a short or absent label list silently dropping lines and markers from the plot
    * Fixed a `ZeroDivisionError` when building an event overlay from events that all have the same length
    * Fixed a crash formatting an axis label for a column with no defined unit
    * Fixed an unhandled plot type leaving plotting data unbound instead of raising a clear error
    * Fixed a typo that left stale event markers on the plot after a failed feature lookup
    * Removed a dead, exact-duplicate code block in all-points-histogram construction
    * Fixed the DB Loader edit/delete buttons staying enabled with no database loaded, from a placeholder text mismatch
    * Fixed `MetadataControls` computing bins-field validity but never using it to enable **Update Plot**, and requiring whole numbers even when "Sizes" was checked

* **Updated Frontend Plugin: `ProteinView`**
    * Added a **RAW** checkbox to event plots, matching `MetadataView`: raw traces before fitting, and alongside fitted results once fitting is complete
    * New **Report All** button in Ensemble mode, showing the double-Gaussian fit parameters and binning configuration plus median ± std summaries of Prolate and Oblate V, a, b and m (replaces Commit All; display-only, since Ensemble mode has no per-event id)
    * Individual and Ensemble modes now use fully independent canvases, so switching modes shows that mode's last plot and neither overwrites the other
    * Reset is now scoped to the currently selected mode, and the display panel confirms which mode's fit was cleared
    * Fixed Update Plot in one mode wiping out a valid fit stored in the other, which produced "No ensemble fit available to report" after a successful fit
    * Removed the Undo and Reset buttons from the Protein Tab, and updated the walkthrough instructions
    * Added Freedman-Diaconis auto-binning for per-event histograms
    * Fixed `hist_min`/`hist_max` persisting across "Plot Histogram" calls and only ever expanding, so bin edges depended on plotting order rather than the event
    * Fixed Commit silently crashing every time from a broken plugin-list refresh chain (the write itself succeeded, so it went unnoticed)
    * Committing now notifies other open tabs, so new columns appear immediately in any tab displaying that database
    * Fixed Commit Individual with no fit computed raising an `AttributeError` swallowed by the Qt event loop; it now reports on the display panel
    * Fixed `_commit_fits` not aborting on Cancel in the Confirm Overwrite dialog, and added the missing `ProteinController.check_column_exists` without which that dialog could never appear
    * Fixed some validation passing an extra positional argument to `logger.warning`, crashing before the warning was shown
    * Fixed a blank **N** field in Ensemble mode raising `ValueError` instead of falling back to a default, and the frontend default of 1000 disagreeing with the backend's 100
    * Fixed zero-baseline divisions propagating NaN/Inf into histograms and fits
    * Added a hard cap to a previously unbounded Monte Carlo sampling loop that could block the UI indefinitely
    * Fixed a plugin-list refresh crashing on `.emit()` against a non-`Signal` method
    * Extracted `_update_distribution_ensemble`'s ~105-line fit and sampling block into `_fit_and_plot_ensemble_geometry`, called once after the loop rather than relying on careful indentation
    * Fixed `is_placeholder_item` checking for `"No Database"` instead of `"No Event Database"`, leaving the DB Loader buttons enabled with nothing selected
    * Fixed the `ProteinView` class docstring still being the unfilled `"Subclass of MetaView for TBD"` placeholder, and `ProteinModel`'s being a copy of `MetadataModel`'s

* **Updated Frontend Plugin: `ClusteringView`**
    * Fixed Commit silently crashing every time from a broken plugin-list refresh chain (the write itself succeeded, so it went unnoticed)
    * Committing now notifies other open tabs, so new columns appear immediately in any tab displaying that database
    * Fixed Cancel on the cluster-overwrite confirmation dialog not actually cancelling the commit
    * Fixed an unrecognized clustering method crashing with an unbound-variable error instead of a clear message
    * Fixed a `ZeroDivisionError` in baseline stats on a flat or constant data chunk
    * Fixed Gaussian Mixture clustering fitting on data that still included the `id` column, whose unnormalized magnitude could dominate the fit
    * Fixed `self.units` serving as both a column-to-unit map and a positional list, so opening the settings dialog after a plot passed a list to code expecting a dict
    * Fixed the plotted-column list being derived from the dataframe's own columns, which carry trailing `id`/`cluster_label`/`cluster_confidence` entries
    * Fixed `ClusteringSettingsDialog.remove_column_item` never refreshing the Apply-button state, leaving Apply stuck disabled after deleting the offending row
    * Added a missing docstring to `ClusteringController.display_write_status`

* **Updated Frontend Plugin: `RawDataView`**
    * Fixed a `ZeroDivisionError` in baseline stats on a flat or constant chunk; it now warns and skips that channel's overlay instead of crashing the plot
    * Fixed power spectral density calculation crashing or producing NaNs on very short channels
    * Fixed committing events doing nothing at all when the channel argument was a single value rather than a list
    * Fixed `RawDataModel.integrate_noise` crashing "Update PSD" with an `IndexError` when a short window made `welch()` return a single frequency bin
    * Fixed PSD calculation labelling a surviving channel's PSD under the wrong channel name whenever an earlier channel was skipped
    * Fixed a log message missing an `f` prefix, so the intended values were never interpolated (same bug also fixed in `EventAnalysisView`)
    * Fixed `_get_baseline_stats`'s docstring documenting a two-value return, missing the local amplitude that is the first of three
    * Fixed `RawDataController.update_channels` being decorated `@Slot(dict)` despite always receiving a `List[int]`
    * Added missing docstrings to `RawDataController.update_available_plugins`/`update_plot_data`

* **Updated Frontend Plugin: `EventAnalysisView`**
    * Fixed a crash when zero channels were selected while shifting or plotting events
    * Fixed a failed event load silently reusing stale data from a previous event
    * Fixed a typo that left stale event markers on the plot after a failed feature lookup
    * Fixed a crash on a fitted event whose features carry no labels
    * Fixed the fitter combo box inserting `"No EventFitter"` while everything else checked for `"No Event Fitter"`, so Fit Events could silently target a nonexistent plugin key
    * Fixed `_start_eventfitter` re-raising a filter-loading failure instead of proceeding without one, as `_handle_plot_events` already did
    * Fixed answering "No" to one channel's "already fitted" prompt cancelling fitting for every remaining channel in the batch
    * Fixed `_update_event_plot` never referencing its `use_raw` parameter, so the raw-trace toggle worked only by accident
    * Fixed `_extract_plot_event_parameters`'s docstring documenting a 4-tuple return, omitting `loader` from the real 5-tuple
    * Fixed `EventAnalysisController.update_channels` being decorated `@Slot(dict)` despite always receiving a `List[int]`, and added a missing docstring to `update_available_plugins`

* **Updated Frontend Component: `MainView`**
    * Fixed sidebar highlighting not updating when a tab was opened from the menu bar or the "Add" dropdown, and not highlighting the dedicated Raw Data / Event Analysis / Metadata buttons
    * Fixed the "Add" dropdown reopening immediately after selecting an item, from a duplicate signal connection
    * Fixed the "All Analysis Tabs" dropdown always opening at the window's top-left corner instead of near the clicked button
    * Fixed menu bar action icons silently failing to render from an incorrect resource path
    * Fixed `add_page` leaking an orphaned wrapper `QWidget` every time a page name was reused, e.g. every time Settings was opened
    * Menu actions are now parented to the menu that shows them, so a rebuild destroys them instead of leaving a full menu bar's worth alive on the window
    * Removed `display_data`/`on_file_loaded`, two dead methods with no callers whose target no longer exists
    * Removed the abandoned language and theme sidebar controls — six methods setting buttons that are never constructed — along with `handleUser`/`switchUser`
    * Fixed `IconTextMenuWidget.menu_button_clicked` scheduling the same `QTimer.singleShot` twice

* **Updated Frontend Component: `Settings`**
    * The Settings window follows OS light/dark mode automatically and updates live if the OS theme changes, with no restart
    * Fixed combobox popups rendering with a stray focus outline, a disappearing hover highlight and a double-border artifact
    * The About tab's version is pulled from `poriscope.constants.__VERSION__` rather than a hardcoded string
    * Fixed a potential `AttributeError` if a folder-picker button was clicked before the data server or user plugin location had been set
    * Fixed the Logging Level combobox always opening at "None" regardless of the configured level, since nothing pulled the persisted value back into the widget

* **Updated Utility: `get_icon` (`poriscope.configs.utils`)**
    * Icons now recolor automatically for light/dark mode instead of requiring separate black and white files
    * New `get_themed_icon_path` helper for cases (like custom stylesheet arrows) that need a real file path
    * Removed unused legacy icon assets and the broken, unused Qt `.qrc` resource system (`resources_rc.py`)
    * Standardized edit/add icons across control panels

### Breaking Changes:

* `QtHandler` no longer raises a dialog for every `WARNING` and no longer inherits the root logger's level; its constructor takes a `level`, defaulting to `ERROR`. A burst of errors is queued and shown in turn rather than losing all but the first, and the dialog carries the bare message instead of a formatted log line
* `BaseDataPlugin.lock` is a per-instance `RLock`, not one class attribute shared by every data plugin in the process. Class-level access breaks; `self.lock` now means "my lock"
* `MetaReader.get_channel_length` takes a required channel and returns an `int`; the no-argument whole-dict form is gone
* `MainModel.get_plugin_classes` takes a required metaclass; `MainModel.get_available_plugins` takes no argument and always returns the full mapping
* `DictDialog.get_result()` always returns `(settings, name)`, with deletion reported by a new `delete_requested()` instead of a `"delete"` sentinel; `DataPluginView.get_user_settings` returns `(settings, name, delete_requested)`
* `DataPluginController.__init__` takes a required `history_lookup` callable; its `get_settings_from_history` signal and `set_settings` are removed, and `MainController.get_settings_from_history` is now `_lookup_historical_settings` and returns a value
* `MainView.kill_all_workers` is replaced by `abort_all_analysis`, handled for every open tab rather than hard-coded to one
* `MetaView` gains an abstract `notify_plugin_state_changed`, which every subclass must implement
* `requires-python` is raised to `>=3.12.10`, blocking installation on 3.12.0–3.12.9
* The `fast` and `slow` pytest markers are removed; `-m fast` and `-m slow` now select nothing

### New Dev Tooling:

* **`pydoclint`**, a blocking pre-commit/CI check that a docstring's documented parameters, return type and raised exceptions match the real function. Run it with `pydoclint --baseline=.pydoclint-baseline.txt poriscope`; see `[tool.pydoclint]` in `pyproject.toml`. The ~1,090-violation backlog it was adopted with is fully cleared and the baseline file is now empty
* **Every function under `poriscope/` is annotated**, with no exclusions, and `mypy`'s `disallow_untyped_defs`, `check_untyped_defs` and `strict_equality` are on, so a new unannotated `def` fails the hook. `mypy.ini` pins `python_version = 3.12`, and the hook is scoped to `poriscope/` so it no longer checks `tests/`
* **The `@log` decorator no longer erases the signatures it wraps** (935 methods across 71 files), so call sites into plugin and controller methods are type-checked for the first time; turning it on surfaced 84 real call-site errors
* **The Sphinx documentation render is a CI gate.** New `docs-check.yml` regenerates the autodoc `.rst` files and runs `sphinx-build -W --keep-going` on every pull request targeting `main`, `develop` or `release/*`; the deploy workflow and the local `post-merge` hook use the same flags. The 18 pre-existing warnings that blocked it are fixed
* **New end-to-end test suite** covering the RawData, EventAnalysis, Metadata, Clustering and Protein tabs, plus a shared `tests/synthetic_data` package, so no test depends on a checked-in recording or database. `tests/data/` is removed
* **`setup_hooks.py` sets `gitflow.prefix.versiontag` to `v`**, so plain `git flow release finish <version>` creates the `v<version>` tag `release.yml` triggers on. Git config is per-clone, so a fresh checkout must run the script before cutting a release
* **`pytest --marker-stats`** prints per-marker test counts and mean durations. `e2e` and `integration` are applied by path, `--strict-markers` is on, and all four workflows run plain `pytest` with no marker filter
* The view test suite is roughly 7.6x faster: widgets are actually deleted at teardown rather than only hidden, the GC sweep is generation-limited, and the protein and event-analysis tests build mocked views instead of real Qt widgets
* Tests can no longer reach the developer's real app-data directory, via an autouse fixture in a new top-level `tests/conftest.py`
* Fixed the test suite segfaulting when `tests/unit/views` ran before `tests/unit/plugins`, from widgets torn down with `QWidget.destroy()` leaving posted events behind
* Fixed four e2e tests waiting on a file existing before asserting on its contents, and a leaked `patch.object` that turned one failure into eighteen
* Fixed the `post-merge` git hook failing silently on Windows: a POSIX-shell shim now selects a working interpreter by executing each candidate, and `.gitattributes` pins it to LF
* `ruff`'s `B006` and `B020` checks are enabled, and the `Programming Language :: Python :: 3.12` classifier is declared to PyPI

### General Fixes and Improvements:

* Fixed 19 routine states being logged at ERROR, and so raising a modal dialog each — including one per keystroke in a range box and one per channel with no data. Empty-state guards now report on the message panel
* Fixed aborting an operation giving no feedback while failing to abort raised a dialog containing a repr of the whole worker dictionary; every branch now reports on the message panel
* Fixed placeholder combobox text (`"No Reader"`, `"No Eventfinder"`, `"No Event Database"`, etc.) reaching `global_signal.emit(...)` as a real plugin key, flooding startup and session-restore with failed lookups
* Exception chaining restored across 23 `raise` sites, so the original error is preserved rather than discarded
* Silently swallowed exceptions outside the owner-held fitter plugins reduced to zero; four remaining cosmetic handlers now log at debug with a traceback
* Cleared 17 unused loop-control variables, and hardened three `zip` sites whose length invariant was implicit
* Fixed `"id"` never actually being excluded from clustering normalization, from two dead lines whose result was discarded
* Replaced deprecated `set_constrained_layout(True)` with `set_layout_engine('constrained')` in `ClusteringView` and `EventAnalysisView`
* All function-local ("lazy") imports removed; the only `TYPE_CHECKING` blocks left are the two forced by a real import cycle
* Two shared mutable argument defaults fixed, and `time_widget`'s `FloatRangeValidator` renamed `TimeRangeValidator` so it no longer collides with the unrelated validator of the same name
* Every dataset link in the documentation now points at the current FRDR record, the Python download link is no longer pinned to a superseded patch release, and the installation pages state `>=3.12.10` consistently
* New contributor documentation: a Quality Control page describing every automated gate with a pre-PR checklist, and a `serial_channel_operations` page covering what `force_serial_channel_operations()` promises and who applies the decorator
* Fixed `MetaReader.load_data`/`continuous_read` reassigning their own seconds-valued parameters to sample counts mid-body, which is how their docstrings came to be wrong
* Corrected 80 docstrings whose documented parameter types disagreed with the signature, and the docs workflow's own comments, which claimed it published from `develop` while triggering on `main`
* Updated tests whose expectations had gone stale against already-landed fixes (`test_main_controller.py`, `test_classic_cusum.py`, `test_no_fitter.py`, `test_meta_event_finder.py`, `test_peak_finder.py`), and removed a dead, shadowed `main_model` fixture

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
