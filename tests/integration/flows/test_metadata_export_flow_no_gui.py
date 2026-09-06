"""
Metadata tab, end to end and headless: load, filter, export, check the CSV.

The plan's shape for these flows is load → filter → plot → export, **asserting on
exported CSV content rather than widget state**, so that the flow survives Steps
3-5 by construction: none of it names an internal method, so moving those methods
between View, Controller and Model cannot break it.

What is real here: the ``MainModel``/``MainView``/``MainController`` shell, the
``MetadataController``/``MetadataView`` triad created through the same call the
menu action reaches, a real ``SQLiteDBLoader`` over a real synthetic database, the
signal bus, and the export generator that writes the files.

What is not: the menu click that creates the tab, the settings dialog that would
configure the loader, and the folder-picker dialog on the export itself. All three
are UI, and each is skipped in a way that leaves the wiring behind it intact -
the tab still learns about the loader through the notification it normally learns
from, and the export still runs the same generator with the same arguments.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER_KEY = "loader"


class _StubDictDialog:
    """
    Stand-in for the export folder picker.

    Returns what the dialog would return once the user has filled it in, so the
    export path either side of it is the real one. Constructed with the same
    signature the View calls, and its ``exec`` does nothing rather than blocking.
    """

    folder: str = ""
    subset_name: str = "subset"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Accept whatever the View passes without inspecting it.

        :param args: positional arguments from the caller
        :type args: Any
        :param kwargs: keyword arguments from the caller
        :type kwargs: Any
        """

    def exec(self) -> None:
        """Do not block; a real dialog would wait for the user here."""

    def get_result(self) -> Tuple[Dict[str, Dict[str, str]], str]:
        """
        Report the folder and subset name the user would have chosen.

        :return: the settings dict and the subset name
        :rtype: Tuple[Dict[str, Dict[str, str]], str]
        """
        return ({"Folder": {"Value": type(self).folder}}, type(self).subset_name)


@pytest.fixture
def metadata_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader registered over the synthetic database.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("MetadataController", tmp_path)

    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER_KEY)

    yield triad

    triad.close()


def export(
    triad: Triad,
    qtbot: Any,
    folder: Path,
    name: str,
    selection: Dict[str, List[int]],
) -> List[Path]:
    """
    Drive the tab's export action and return the files it wrote.

    Goes through ``handle_parameter_change``, which is the entry point the controls
    widget uses, rather than calling the export method directly - so the dispatch
    is part of what is under test.

    :param triad: the tab under test
    :type triad: Triad
    :param qtbot: pytest-qt's fixture, used to wait for the worker to finish
    :type qtbot: Any
    :param folder: destination directory
    :type folder: Path
    :param name: subset name, which becomes part of the file names
    :type name: str
    :param selection: the experiments and channels to export
    :type selection: Dict[str, List[int]]
    :return: the CSV files written, sorted by name
    :rtype: List[Path]
    """
    _StubDictDialog.folder = str(folder)
    _StubDictDialog.subset_name = name
    triad.tab_view.selected_experiment_and_channels_by_loader[LOADER_KEY] = selection

    triad.tab_view.handle_parameter_change(
        "metadatacontrols", "export_csv_subset", ({"db_loader": LOADER_KEY},)
    )

    # The View emits run_generators itself and the export runs on a worker thread,
    # so the files appear some time after this call returns.
    #
    # The predicate is deliberately specific to *this* subset's tables, for the
    # reason DECISIONS.md 2026-09-03 records: a wait that is satisfied by a partial
    # signal reports done too early. A first attempt here waited for "any CSV with
    # rows in this folder", which a second export into the same folder satisfied
    # instantly from the first export's files - so it asserted against files the
    # run under test had not written. Waiting on the sublevels table specifically
    # also means waiting past the events table, which is written first.
    def subset_is_written() -> bool:
        """
        Report whether this subset's events and sublevels tables are readable.

        :return: True once both parse with rows in them
        :rtype: bool
        """
        for table in ("events", "sublevels"):
            path = folder / f"{name}_{table}.csv"
            if not path.exists():
                return False
            try:
                if len(pd.read_csv(path)) == 0:
                    return False
            except (pd.errors.EmptyDataError, OSError):
                return False
        return True

    qtbot.waitUntil(subset_is_written, timeout=60_000)

    return sorted(folder.glob(f"{name}_*.csv"))


@pytest.fixture(autouse=True)
def stub_the_folder_dialog(mocker) -> None:
    """
    Replace the export's folder picker for every test in this module.

    :param mocker: pytest-mock's fixture
    :type mocker: Any
    :return: None
    :rtype: None
    """
    mocker.patch(
        "poriscope.plugins.analysistabs.MetadataView.DictDialog", _StubDictDialog
    )


def row_counts(written: List[Path]) -> Dict[str, int]:
    """
    Map each exported table to its row count.

    The export writes one CSV per table, named ``<subset>_<table>.csv``, so the
    table name is the suffix after the subset name.

    :param written: the CSV files the export produced
    :type written: List[Path]
    :return: row count per table
    :rtype: Dict[str, int]
    """
    counts: Dict[str, int] = {}
    for path in written:
        table = path.stem.rsplit("_", 1)[-1]
        counts[table] = len(pd.read_csv(path))
    return counts


@pytest.mark.timeout(90)
def test_the_tab_sees_the_registered_loader(metadata_tab: Triad) -> None:
    """
    Registration reaches the tab, not just the plugin registry.

    If this fails, every assertion below would be exercising a tab that never
    learned the loader exists - which is the shape of a flow that passes while
    testing nothing.
    """
    assert LOADER_KEY in metadata_tab.available("MetaDatabaseLoader")


@pytest.mark.timeout(90)
def test_a_channel_exports_its_own_events_and_sublevels(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    The end of the pipeline: real rows, out of a real database, into real files.

    The synthetic database puts 25 events on channel 0, each fitted to three
    sublevels, and the export writes one CSV per table. Asserting on the files
    rather than on widget state is what makes this survive Steps 3-5.
    """
    out = tmp_path / "export_one"
    out.mkdir()

    rows = row_counts(export(metadata_tab, qtbot, out, "one_channel", {"exp_a": [0]}))

    assert rows["events"] == 25
    assert rows["sublevels"] == 75
    assert rows["data"] == 25


@pytest.mark.timeout(90)
def test_the_export_is_scoped_to_the_selected_channel(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    The selection is honoured, which is the whole point of exporting a subset.

    Channel 1 holds 15 events against channel 0's 25, so a selection that was
    silently ignored would give 40 here rather than 15.
    """
    out = tmp_path / "export_other"
    out.mkdir()

    rows = row_counts(export(metadata_tab, qtbot, out, "other_channel", {"exp_a": [1]}))

    assert rows["events"] == 15
    assert rows["sublevels"] == 45


@pytest.mark.timeout(90)
def test_selecting_both_channels_exports_both(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    The scoping is additive, and the channels table grows with it.

    One row per selected channel is what lets a reader of the export tell which
    channels it covers, so it is asserted alongside the event count.
    """
    out = tmp_path / "export_both"
    out.mkdir()

    rows = row_counts(
        export(metadata_tab, qtbot, out, "both_channels", {"exp_a": [0, 1]})
    )

    assert rows["events"] == 40
    assert rows["sublevels"] == 120
    assert rows["channels"] == 2


@pytest.mark.timeout(90)
def test_the_exported_events_carry_the_expected_columns(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    A reader of the CSV needs the identity columns to join the tables back up.

    Pinned because Step 4b moves the query that produces them, and a projection
    that lost one of these would still export a plausible-looking file.
    """
    out = tmp_path / "export_columns"
    out.mkdir()

    written = export(metadata_tab, qtbot, out, "columns", {"exp_a": [0]})
    events = pd.read_csv(next(p for p in written if p.name.endswith("_events.csv")))

    for column in ("id", "experiment_id", "channel_id"):
        assert column in events.columns


@pytest.mark.timeout(90)
def test_a_second_export_does_not_overwrite_the_first(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    Two subsets from one session land side by side, keyed by their names.

    Users export several subsets in a row; silently clobbering the previous one
    would lose work with no warning.
    """
    out = tmp_path / "export_twice"
    out.mkdir()

    export(metadata_tab, qtbot, out, "first", {"exp_a": [0]})
    export(metadata_tab, qtbot, out, "second", {"exp_a": [1]})

    # the folder, not either export's own file list, since each is scoped to its
    # own subset name
    names = {path.name for path in out.glob("*.csv")}
    assert "first_events.csv" in names
    assert "second_events.csv" in names
    assert len(pd.read_csv(out / "first_events.csv")) == 25
    assert len(pd.read_csv(out / "second_events.csv")) == 15
