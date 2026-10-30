"""
Protein write-back: a recorded entry's values are shown in a fresh tab.

``write_back`` writes what an entry used, so a restored tab shows what produced its result:
for an Individual or Ensemble plot, its mode, loader, filters, scope, bins and Sizes, pore and
N; for Plot Events and Plot Histogram, the loader, the filter, the scope, the Event ID, the
event count, and Raw or the bins and Sizes. It never reads a widget (it runs while a replay is
under the tripwire), and it never emits an action: a handler reacting to a value that was just
written would undo it. These tests build a real tab with a loader registered over the
synthetic database.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from poriscope.utils.ReplayGuard import replaying
from tests.integration.flows._triad import Triad, build_triad, named

LOADER = "loader"
FILTERS = {"F0": "duration >= 0", "F1": "duration >= 1"}


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """A Protein tab with a real loader and two named filters, nothing selected or plotted."""
    triad = build_triad("ProteinController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    view = triad.tab_view
    for name, text in FILTERS.items():
        view.subset_filters[name] = text
        view.proteincontrols.filter_comboBox.addItem(name)
    # Another option is selected, the way a second loader would be, so writing the
    # recorded one back is seen to change the panel.
    view.proteincontrols.db_loader_comboBox.addItem("another database")
    view.proteincontrols.set_loader("another database")
    yield triad
    triad.close()


@pytest.fixture
def emitted(tab: Triad) -> List[str]:
    """Every action the panel emits from now on: a write-back must emit none."""
    actions: List[str] = []
    tab.tab_view.proteincontrols.actionTriggered.connect(
        lambda _view, action, _params: actions.append(action)
    )
    return actions


def said(tab: Triad, mocker: Any) -> Any:
    """Spy on the status panel."""
    return mocker.patch.object(tab.tab_view, "add_text_to_display")


def distribution_entry(tab: Triad, action: str, **changes: Any) -> Dict[str, Any]:
    """A recorded distribution plot of F1 in channel 1, its values named as the decorator saves them."""
    values: Dict[str, Any] = {
        "loader": LOADER,
        "filters": {"F1": FILTERS["F1"]},
        "scope": {"exp_a": ["1"]},
        "bins": [0.5],
        "sizes": True,
        "pore_diameter": 12.5,
        "pore_length": 30.0,
        "n_values": 250,
    }
    values.update(changes)
    return named(tab, action, *values.values())


def events_entry(
    tab: Triad, action: str = "plot_events", **changes: Any
) -> Dict[str, Any]:
    """A recorded Plot Events (with Raw) or Plot Histogram (with bins) of three events of F0 in channel 0."""
    values: Dict[str, Any] = {
        "loader": LOADER,
        "event_ids": [4, 5, 7],
        "experiment": "exp_a",
        "channel": "0",
        "subset_name": "F0",
        "sql_filter": FILTERS["F0"],
    }
    if action == "plot_events":
        values["raw"] = True
    else:
        values.update({"bins": [40], "sizes": False})
    values.update(changes)
    return named(tab, action, *values.values())


@pytest.mark.parametrize(
    ("action", "mode", "other"),
    [
        ("update_ensemble_distribution", "ensemble", "individual"),
        ("update_individual_distribution", "individual", "ensemble"),
    ],
)
def test_a_distribution_entry_shows_everything_the_plot_used_and_its_mode(
    tab: Triad, emitted: List[str], action: str, mode: str, other: str
) -> None:
    view = tab.tab_view
    controls = view.proteincontrols
    controls.set_mode(other)
    view._analysis_mode = other
    view._set_display_mode("event")

    view.write_back(action, (), distribution_entry(tab, action))

    assert controls.db_loader_comboBox.currentText() == LOADER
    assert controls.filter_comboBox.getSelectedItems() == ["F1"]
    assert view.selected_experiment_and_channels_by_loader[LOADER] == {"exp_a": ["1"]}
    assert controls.sizes_checkbox.isChecked()
    assert controls.bins_lineEdit.text() == "0.5"
    assert controls.pore_diameter_lineEdit.text() == "12.5"
    assert controls.pore_length_lineEdit.text() == "30.0"
    assert controls.n_values_lineEdit.text() == "250"
    assert getattr(controls, f"{mode}_button").isChecked()
    assert view._analysis_mode == mode
    assert view.mode_stack.currentWidget() is getattr(view, f"{mode}_dist_page")
    assert view._display_mode == "distribution"
    assert emitted == []


def test_a_plot_events_entry_shows_everything_the_plot_used(
    tab: Triad, emitted: List[str]
) -> None:
    view = tab.tab_view
    controls = view.proteincontrols
    view._last_event_action = "plot_histogram"

    view.write_back("plot_events", (), events_entry(tab))

    assert controls.db_loader_comboBox.currentText() == LOADER
    assert controls.filter_comboBox.getSelectedItems() == ["F0"]
    assert view.selected_experiment_and_channels_by_loader[LOADER] == {"exp_a": ["0"]}
    assert controls.event_id_lineEdit.text() == "4"
    assert controls.n_events_lineEdit.text() == "3"
    assert controls.raw_checkbox.isChecked()
    assert view._last_event_action == "plot_events"
    assert emitted == []


def test_a_plot_histogram_entry_shows_its_bins_and_sets_the_arrows_to_histograms(
    tab: Triad, emitted: List[str]
) -> None:
    view = tab.tab_view
    controls = view.proteincontrols
    controls.set_raw(True)

    view.write_back(
        "plot_event_histograms", (), events_entry(tab, "plot_event_histograms")
    )

    assert controls.filter_comboBox.getSelectedItems() == ["F0"]
    assert controls.event_id_lineEdit.text() == "4"
    assert controls.n_events_lineEdit.text() == "3"
    assert controls.bins_lineEdit.text() == "40"
    assert not controls.sizes_checkbox.isChecked()
    assert controls.raw_checkbox.isChecked()  # not part of a histogram: left as it was
    assert view._last_event_action == "plot_histogram"
    assert emitted == []


def test_the_full_dataset_clears_the_filter_selection(
    tab: Triad, emitted: List[str]
) -> None:
    """A distribution plot of no filter records none; an event plot records the full dataset by name."""
    controls = tab.tab_view.proteincontrols
    controls.set_filters(["F0", "F1"])
    tab.tab_view.write_back(
        "update_ensemble_distribution",
        (),
        distribution_entry(tab, "update_ensemble_distribution", filters={}),
    )
    assert controls.filter_comboBox.getSelectedItems() == []

    controls.set_filters(["F0"])
    tab.tab_view.write_back(
        "plot_events", (), events_entry(tab, subset_name="Full Dataset", sql_filter="")
    )
    assert controls.filter_comboBox.getSelectedItems() == []


def test_a_filter_whose_sql_changed_since_is_not_selected_and_said(
    tab: Triad, emitted: List[str], mocker: Any
) -> None:
    spy = said(tab, mocker)
    tab.tab_view.subset_filters["F1"] = "duration >= 99"

    tab.tab_view.write_back(
        "update_individual_distribution",
        (),
        distribution_entry(tab, "update_individual_distribution"),
    )

    assert tab.tab_view.proteincontrols.filter_comboBox.getSelectedItems() == []
    messages = [call.args[0] for call in spy.emit.call_args_list]
    assert any("F1" in message for message in messages)


def test_a_loader_that_is_not_an_option_is_skipped_and_said(
    tab: Triad, emitted: List[str], mocker: Any
) -> None:
    spy = said(tab, mocker)
    controls = tab.tab_view.proteincontrols

    tab.tab_view.write_back(
        "plot_events", (), events_entry(tab, loader="a loader that is gone")
    )
    tab.tab_view.write_back(
        "update_ensemble_distribution",
        (),
        distribution_entry(tab, "update_ensemble_distribution", loader="also gone"),
    )

    messages = " ".join(call.args[0] for call in spy.emit.call_args_list)
    assert "a loader that is gone" in messages and "also gone" in messages
    assert controls.db_loader_comboBox.currentText() == "another database"
    assert emitted == []


def test_the_scope_is_a_copy_of_the_entry_s(tab: Triad, emitted: List[str]) -> None:
    entry = distribution_entry(tab, "update_ensemble_distribution")

    tab.tab_view.write_back("update_ensemble_distribution", (), entry)
    entry["scope"]["exp_a"].append("0")

    assert tab.tab_view.selected_experiment_and_channels_by_loader[LOADER] == {
        "exp_a": ["1"]
    }


def test_write_back_reads_no_widget(tab: Triad, emitted: List[str]) -> None:
    """It runs under the replay tripwire: a read of a controls helper would raise."""
    view = tab.tab_view
    with replaying():
        for action in (
            "update_individual_distribution",
            "update_ensemble_distribution",
        ):
            view.write_back(action, (), distribution_entry(tab, action))
        view.write_back("plot_events", (), events_entry(tab))
        view.write_back(
            "plot_event_histograms", (), events_entry(tab, "plot_event_histograms")
        )

    assert emitted == []


def test_an_action_with_nothing_to_show_is_ignored(
    tab: Triad, emitted: List[str]
) -> None:
    view = tab.tab_view
    controls = view.proteincontrols

    view.write_back("reset", (), named(tab, "reset", "2d", "ensemble"))
    view.write_back("an_action_from_another_tab", ("x",), {})

    assert controls.db_loader_comboBox.currentText() == "another database"
    assert view._analysis_mode == "individual"
    assert emitted == []
