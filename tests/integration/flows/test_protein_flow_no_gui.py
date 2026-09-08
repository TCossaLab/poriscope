"""
Protein tab, end to end and headless: load, select, plot, export, check the CSV.

This one takes the plan's literal shape - load, filter, plot, export, assert on
exported CSV content - because the protein tab has a generic
``export_plot_data`` action that writes whatever is currently cached for the plot.
That makes it the cleanest available assertion on this tab: the numbers a user
would see on the axes, written to a file, rather than any widget state.

The route is entirely through ``handle_parameter_change`` action names, so nothing
here names an internal method and Steps 3-5 can move the computation to the Model
without touching it. The only bypass beyond the tab's creation and the plugin
settings dialog is ``get_save_filename``, the file picker, which is replaced with
a fixed path so the export either side of it is real.
"""

from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER_KEY = "loader"


@pytest.fixture
def protein_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A protein tab with a real loader over the synthetic metadata database.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("ProteinController", tmp_path)

    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER_KEY)

    triad.tab_view.handle_parameter_change(
        "proteincontrols", "loader_changed", ({"db_loader": LOADER_KEY},)
    )

    yield triad

    triad.close()


def plot_events(triad: Triad, selection: Dict[str, Any], event_index: str) -> None:
    """
    Select an experiment and channel, then plot the requested events.

    The selection is set directly rather than through the selection-tree dialog,
    which is the same bypass the metadata flow uses: it is UI, and the plotting
    behind it reads the selection from this attribute either way.

    :param triad: the tab under test
    :type triad: Triad
    :param selection: experiments mapped to the channels to plot
    :type selection: Dict[str, Any]
    :param event_index: the event index expression to plot
    :type event_index: str
    :return: None
    :rtype: None
    """
    triad.tab_view.selected_experiment_and_channels_by_loader[LOADER_KEY] = selection
    triad.tab_view.handle_parameter_change(
        "proteincontrols",
        "plot_events",
        ({"db_loader": LOADER_KEY, "subset": "All", "event_index": event_index},),
    )


def export(triad: Triad, mocker: Any, destination: Path) -> pd.DataFrame:
    """
    Drive the export action and read back what it wrote.

    :param triad: the tab under test
    :type triad: Triad
    :param mocker: pytest-mock's fixture, used to replace the file picker
    :type mocker: Any
    :param destination: where the export should write
    :type destination: Path
    :return: the exported rows
    :rtype: pd.DataFrame
    """
    mocker.patch.object(
        triad.tab_view, "get_save_filename", return_value=str(destination)
    )
    triad.tab_view.handle_parameter_change("proteincontrols", "export_plot_data", ({},))
    return pd.read_csv(destination)


@pytest.mark.timeout(120)
def test_the_tab_sees_the_registered_loader(protein_tab: Triad) -> None:
    """Registration reaches the tab, not just the plugin registry."""
    assert LOADER_KEY in protein_tab.available("MetaDatabaseLoader")


@pytest.mark.timeout(120)
def test_the_loader_structure_reaches_the_tab(protein_tab: Triad) -> None:
    """
    The experiment tree the selection dialog would show is populated for real.

    Note the channels arrive as strings: the domain model holds them as ints and
    the view layer stringifies them for display. Pinned because Step 4d moves this
    state to the Model, where the conversion has to survive.
    """
    structure = protein_tab.tab_view.available_experiment_and_channels_by_loader

    assert structure[LOADER_KEY] == {"exp_a": ["0", "1"]}


@pytest.mark.timeout(120)
def test_plotting_then_exporting_writes_the_plotted_numbers(
    protein_tab: Triad, mocker, tmp_path: Path
) -> None:
    """
    The end of the pipeline: what is on the axes, written to a file.

    Asserting on the CSV rather than on the axes is what makes this survive Steps
    3-5, since none of the methods that produced the numbers are named here.
    """
    plot_events(protein_tab, {"exp_a": ["0"]}, "1")

    frame = export(protein_tab, mocker, tmp_path / "plot.csv")

    assert not frame.empty
    assert len(frame.columns) >= 2


@pytest.mark.timeout(120)
def test_exporting_without_plotting_writes_nothing(
    protein_tab: Triad, mocker, tmp_path: Path
) -> None:
    """
    An export with an empty cache is a no-op, not a crash or an empty file.

    ``MetaController.export_plot_data`` returns early when the model has no cached
    data, so the file picker is never even reached - pinned because Step 4a moves
    that method's data access and an eager write would leave the user with a file
    full of nothing.
    """
    destination = tmp_path / "nothing.csv"
    mocker.patch.object(
        protein_tab.tab_view, "get_save_filename", return_value=str(destination)
    )

    protein_tab.tab_view.handle_parameter_change(
        "proteincontrols", "export_plot_data", ({},)
    )

    assert not destination.exists()
