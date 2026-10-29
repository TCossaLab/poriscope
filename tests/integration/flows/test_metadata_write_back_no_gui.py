"""
Metadata write-back: a recorded entry's values are shown in a fresh tab.

``write_back`` writes what an entry used, so a restored tab shows what produced its result: for an
overlay, the loader, its columns, the plot type, the log flags, the bins and Sizes, the filters and the
scope; for Plot Events, the loader, the filter, the scope, the Event ID, the event count and Raw. It
never reads a widget (it runs while a replay is under the tripwire), and it never emits an action: a
handler reacting to a value that was just written would undo it. These tests build a real tab with a
loader registered over the synthetic database.
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
    """A Metadata tab with a real loader and two named filters, nothing selected or plotted."""
    triad = build_triad("MetadataController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    view = triad.tab_view
    for name, text in FILTERS.items():
        view.subset_filters[name] = text
        view.metadatacontrols.filter_comboBox.addItem(name)
    # Another option is selected, the way a second loader would be, so writing the
    # recorded one back is seen to change the panel.
    view.metadatacontrols.db_loader_comboBox.addItem("another database")
    view.metadatacontrols.set_loader("another database")
    yield triad
    triad.close()


@pytest.fixture
def emitted(tab: Triad) -> List[str]:
    """Every action the panel emits from now on: a write-back must emit none."""
    actions: List[str] = []
    tab.tab_view.metadatacontrols.actionTriggered.connect(
        lambda _view, action, _params: actions.append(action)
    )
    return actions


def said(tab: Triad, mocker: Any) -> Any:
    """Spy on the status panel."""
    return mocker.patch.object(tab.tab_view, "add_text_to_display")


def overlay_entry(tab: Triad, **changes: Any) -> Dict[str, Any]:
    """A recorded scatterplot of F1 in channel 1, its values named as the decorator saves them."""
    values: Dict[str, Any] = {
        "loader": LOADER,
        "plot_type": "Scatterplot",
        "axes": ["start_time", "max_blockage", "duration"],
        "logs": [True, False, False],
        "bins": [7],
        "sizes": False,
        "filters": {"F1": FILTERS["F1"]},
        "scope": {"exp_a": ["1"]},
    }
    values.update(changes)
    return named(tab, "overlay_plot", *values.values())


def events_entry(tab: Triad, **changes: Any) -> Dict[str, Any]:
    """A recorded Plot Events of three events of F0 in channel 0, with Raw."""
    values: Dict[str, Any] = {
        "loader": LOADER,
        "event_ids": [4, 5, 7],
        "experiment": "exp_a",
        "channel": "0",
        "subset_name": "F0",
        "sql_filter": FILTERS["F0"],
        "raw": True,
    }
    values.update(changes)
    return named(tab, "plot_events", *values.values())


def test_an_overlay_entry_shows_everything_the_plot_used(
    tab: Triad, emitted: List[str]
) -> None:
    view = tab.tab_view
    controls = view.metadatacontrols

    view.write_back("overlay_plot", (), overlay_entry(tab))

    assert controls.db_loader_comboBox.currentText() == LOADER
    assert controls.plot_type_comboBox.currentText() == "Scatterplot"
    assert controls.x_axis_comboBox.currentText() == "start_time"
    assert controls.y_axis_comboBox.currentText() == "max_blockage"
    assert controls.z_axis_comboBox.currentText() == "duration"
    assert controls.y_axis_comboBox.isEnabled()
    assert not controls.z_axis_comboBox.isEnabled()
    assert controls.x_axis_logscale_checkbox.isChecked()
    assert not controls.y_axis_logscale_checkbox.isChecked()
    assert controls.bins_lineEdit.text() == "7"
    assert not controls.sizes_checkbox.isChecked()
    assert controls.filter_comboBox.getSelectedItems() == ["F1"]
    assert view.selected_experiment_and_channels_by_loader[LOADER] == {"exp_a": ["1"]}
    assert emitted == []


def test_an_overlay_entry_shows_bin_widths_with_sizes(
    tab: Triad, emitted: List[str]
) -> None:
    controls = tab.tab_view.metadatacontrols

    tab.tab_view.write_back(
        "overlay_plot", (), overlay_entry(tab, bins=[0.5, 2.0], sizes=True)
    )

    assert controls.sizes_checkbox.isChecked()
    assert controls.bins_lineEdit.text() == "0.5, 2.0"


def test_a_plot_events_entry_shows_everything_the_plot_used(
    tab: Triad, emitted: List[str]
) -> None:
    view = tab.tab_view
    controls = view.metadatacontrols

    view.write_back("plot_events", (), events_entry(tab))

    assert controls.db_loader_comboBox.currentText() == LOADER
    assert controls.filter_comboBox.getSelectedItems() == ["F0"]
    assert view.selected_experiment_and_channels_by_loader[LOADER] == {"exp_a": ["0"]}
    assert controls.event_id_lineEdit.text() == "4"
    assert controls.n_events_lineEdit.text() == "3"
    assert controls.raw_checkbox.isChecked()
    assert emitted == []


def test_the_full_dataset_clears_the_filter_selection(
    tab: Triad, emitted: List[str]
) -> None:
    """An overlay of no filter records none; Plot Events records the full dataset by name."""
    controls = tab.tab_view.metadatacontrols
    controls.set_filters(["F0", "F1"])
    tab.tab_view.write_back("overlay_plot", (), overlay_entry(tab, filters={}))
    assert controls.filter_comboBox.getSelectedItems() == []

    controls.set_filters(["F0"])
    tab.tab_view.write_back(
        "plot_events", (), events_entry(tab, subset_name="Full Dataset", sql_filter="")
    )
    assert controls.filter_comboBox.getSelectedItems() == []


def test_writing_back_a_loader_asks_for_its_columns_and_each_axis_its_units(
    tab: Triad, emitted: List[str]
) -> None:
    """The held-off dropdown signals would have asked; write-back asks once per axis instead."""
    view = tab.tab_view
    columns: List[str] = []
    units: List[Any] = []
    view.column_names_requested.connect(columns.append)
    view.column_units_requested.connect(lambda *args: units.append(args))

    view.write_back("overlay_plot", (), overlay_entry(tab))

    assert columns == [LOADER]
    assert units == [
        (LOADER, "start_time", "x_axis"),
        (LOADER, "max_blockage", "y_axis"),
        (LOADER, "duration", "z_axis"),
    ]


def test_a_filter_whose_sql_changed_since_is_not_selected_and_said(
    tab: Triad, emitted: List[str], mocker: Any
) -> None:
    spy = said(tab, mocker)
    tab.tab_view.subset_filters["F1"] = "duration >= 99"

    tab.tab_view.write_back("overlay_plot", (), overlay_entry(tab))

    assert tab.tab_view.metadatacontrols.filter_comboBox.getSelectedItems() == []
    messages = [call.args[0] for call in spy.emit.call_args_list]
    assert any("F1" in message for message in messages)


def test_values_that_are_not_options_are_skipped_and_said(
    tab: Triad, emitted: List[str], mocker: Any
) -> None:
    spy = said(tab, mocker)
    controls = tab.tab_view.metadatacontrols

    tab.tab_view.write_back(
        "overlay_plot",
        (),
        overlay_entry(
            tab,
            plot_type="Pie Chart",
            axes=["a column that is gone", "max_blockage", "duration"],
            filters={"a filter that is gone": "x > 1"},
        ),
    )
    tab.tab_view.write_back(
        "plot_events", (), events_entry(tab, loader="a loader that is gone")
    )

    messages = " ".join(call.args[0] for call in spy.emit.call_args_list)
    for gone in (
        "Pie Chart",
        "a column that is gone",
        "a filter that is gone",
        "a loader that is gone",
    ):
        assert gone in messages
    assert controls.y_axis_comboBox.currentText() == "max_blockage"
    assert emitted == []


def test_the_scope_is_a_copy_of_the_entry_s(tab: Triad, emitted: List[str]) -> None:
    entry = overlay_entry(tab)

    tab.tab_view.write_back("overlay_plot", (), entry)
    entry["scope"]["exp_a"].append("0")

    assert tab.tab_view.selected_experiment_and_channels_by_loader[LOADER] == {
        "exp_a": ["1"]
    }


def test_write_back_reads_no_widget(tab: Triad, emitted: List[str]) -> None:
    """It runs under the replay tripwire: a read of a controls helper would raise."""
    with replaying():
        tab.tab_view.write_back("overlay_plot", (), overlay_entry(tab))
        tab.tab_view.write_back("plot_events", (), events_entry(tab))

    assert emitted == []


def test_an_action_with_nothing_to_show_is_ignored(
    tab: Triad, emitted: List[str]
) -> None:
    controls = tab.tab_view.metadatacontrols

    tab.tab_view.write_back("reset", (), named(tab, "reset", "3d"))
    tab.tab_view.write_back("an_action_from_another_tab", ("x",), {})

    assert controls.db_loader_comboBox.currentText() == "another database"
    assert emitted == []
