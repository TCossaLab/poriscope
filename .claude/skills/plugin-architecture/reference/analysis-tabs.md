# Building an analysis tab

What a new analysis tab needs beyond what `scripts/new_plugin.py AnalysisTab <Name>` writes and the
frontend guide says. The guide is authoritative and comes first:
`docs/source/utils/user_manuals/plugins_manual/plugin_development/frontend_plugin/ready_to_build/`
(`index.rst` for the generator, `metacontroller_base.rst` for recording and replay, `metamodel_base.rst`,
`metaview_base.rst`, `choosing_a_base.rst`). This file holds only what those pages do not, each point with
the case that taught it - most from building the Conditioning tab (2026-11-11). Answer each from the code
before relying on it.

## Contents

- Shape and lifetime
- Where the data comes from
- Views
- Recording and replay
- Background work
- Controls panels
- Docstrings

## Shape and lifetime

- **Generate it.** In this repository the generator writes the triad to `poriscope/plugins/analysistabs/`
  and the controls panel to `analysistabs/utils/<name>controls.py`, where every shipped tab keeps its own;
  `--user` / `--output-dir` keep the panel beside the triad. *Case:* until 2026-11-11 it wrote
  `<Name>Controls.py` beside the triad, which `test_new_plugin`'s suffix test rejects; the Conditioning
  panel was moved by hand before the generator was fixed.
- **One instance per tab type** - `MainController.analysis_tabs` is keyed by the Controller class. A tab
  without a sidebar button opens from **Analysis -> New Analysis Tab -> `<Name>Controller`**.

## Where the data comes from

- **A tab never reads input files.** Everything arrives from a data plugin through `MetaModel.call`. If no
  family can supply the input, which family to add is a ruling, not a detail of the tab. *Case:* the
  Conditioning tab's experiment folder became a new family, `MetaConditioningLoader` (see "Adding a
  data-plugin family" in `SKILL.md`), rather than a folder picker in the tab.
- **A View needs a request/answer pair for a plugin's channels**: the View emits a request carrying the
  plugin key, the Controller asks the Model and calls the View's setter. *Case:* `ConditioningView`'s
  `channels_requested` -> Controller -> `set_channels`; the same request is re-sent from `write_back`.

## Views

- **No computation library at runtime** - `check_mvc_boundary` rule 2 counts any import of numpy, scipy,
  pandas and friends that is used to compute. An import used only in annotations is allowed; for a little
  arithmetic use `math`. Computation goes in the Model.
- **Option sets fit `DictDialog`**, the same widget the plugin settings use. *Case:* Raw Data's PSD
  Options (segment length, overlap, fit range, noise thresholds) is a `DictDialog` behind one button.
- **A drawing helper two tabs need goes on `MetaView`**, or the duplication ratchet rises. *Case:*
  `MetaView.noise_shade`, shared by Raw Data's PSD and the Conditioning plot.

## Recording and replay

The rules are in `metacontroller_base.rst` (record Controller methods only, declare `kind` and `figure`,
list `plugin_args`, keep arguments small). What bit in practice:

- **Every value is saved under its parameter name, defaults included.** A new keyword parameter with a
  default keeps old saved entries replayable, but changes what new entries hold, so tests that pin an
  entry's contents change with it. *Case:* adding the PSD options to Raw Data's `load_psd_data` with
  defaults equal to the old behaviour kept old sessions replaying; five tests that pinned entries were
  updated.
- **A background computation that is not one plugin on one channel has no replay kind of its own.**
  *Case:* the Conditioning plot computes many channels on workers; it is recorded as a `view` action that
  starts the workers, recorded at the start, and replay starts it and moves on (ruling R5 of that port).
- **Every recorded action needs a `write_back`** that shows the recorded values in the panel, without
  emitting.

## Background work

- **Workers are keyed by (plugin key, channel)** through `MetaModel.set_generator` /
  `run_generators`, and `generate_report` calls the plugin's `report_status(channel)` after each worker
  ends - so the plugin's per-channel status line is what the user reads at the end of every run; make it
  say something.
- **Honour plugins that cannot run channels concurrently**:
  `with self.call(family, key, "serialize_channel_operations"):` around the per-channel work.
- **Time the work before designing it.** Seconds per plot on real data means workers with progress, and
  keeping results so a replot is instant.

## Controls panels

- **A combobox refilled with its signals blocked leaves its edit and delete buttons stale.** The buttons
  from `create_info_button` / `create_delete_button` re-check only on `currentIndexChanged`; a refill
  that blocks signals (to avoid emitting twice) must call `toggle_info_button` for each itself. *Case:*
  2026-11-11, the Conditioning tab's experiment pencil and trash stayed grey after the first experiment
  was added, and would have stayed live on "No Experiment" after the last was deleted; found in the
  manual pass, pinned by `test_the_edit_and_delete_buttons_follow_the_experiment_list`.
- **A panel's placeholder text** ("No Experiment") must be in its own `placeholder_texts`, or the guard
  above treats it as a real plugin.

## Docstrings

- **pydoclint does not see `x = yield ...` as a yield.** Document such a generator with `:return:` and
  `:rtype: Generator[...]`. *Case:* `ConditioningModel.one_hz_run`, which receives a stop flag through
  `send`.
