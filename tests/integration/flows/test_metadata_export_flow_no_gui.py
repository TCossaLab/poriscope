"""
Metadata tab, end to end and headless: load, filter, export, check the CSV.

The shape of these flows is load → filter → plot → export, **asserting on
exported CSV content rather than widget state**, so that the flow survives
refactoring by construction: none of it names an internal method, so moving those
methods between View, Controller and Model cannot break it.

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

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad
from tests.synthetic_data.synthetic_metadata_db import generate_metadata_database

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


def open_loader(db_path: str) -> SQLiteDBLoader:
    """
    A real loader over a database file, configured as the settings dialog would.

    :param db_path: the metadata database to read
    :type db_path: str
    :return: the configured loader
    :rtype: SQLiteDBLoader
    """
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = db_path
    loader.apply_settings(settings)
    return loader


def build_metadata_tab(tmp_path: Path, db_path: str) -> Triad:
    """
    A metadata tab with a real loader registered over a database file.

    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param db_path: the metadata database the loader reads
    :type db_path: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("MetadataController", tmp_path)
    triad.register(open_loader(db_path), "MetaDatabaseLoader", LOADER_KEY)
    return triad


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
    triad = build_metadata_tab(tmp_path, sample_metadata_db)

    yield triad

    triad.close()


@pytest.fixture
def channels_written_out_of_order(tmp_path: Path) -> str:
    """
    A database whose channel 1 was written before its channel 0.

    The events query of a scoped export walks the ``(experiment_id, channel_id,
    event_id)`` index, so it returns channel 0's events first, while the ``data``
    table holds channel 1's rows first. The default synthetic database writes its
    channels in id order, where the two orders agree and a positional pairing of
    them goes unnoticed. The channels get different seeds because the generator's
    default seed would give channel 1's event *k* exactly channel 0's event *k*
    samples, and a trace swapped between those two would look right.

    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: path to the written database
    :rtype: str
    """
    database = generate_metadata_database(
        tmp_path / "out_of_order.sqlite3",
        experiments=[
            {
                "name": "exp_a",
                "channels": [
                    {"channel_id": 1, "num_events": 6, "seed": 1},
                    {"channel_id": 0, "num_events": 6, "seed": 2},
                ],
            }
        ],
    )
    return str(database.db_path)


@pytest.fixture
def out_of_order_tab(qapp, tmp_path: Path, channels_written_out_of_order: str) -> Triad:
    """
    A metadata tab over the database whose channels were written out of order.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param channels_written_out_of_order: path to that database
    :type channels_written_out_of_order: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_metadata_tab(tmp_path, channels_written_out_of_order)

    yield triad

    triad.close()


def stored_raw_data(db_path: str, event_db_id: int) -> np.ndarray:
    """
    Read one event's raw trace straight out of the database file.

    :param db_path: the metadata database
    :type db_path: str
    :param event_db_id: the event's ``events.id``
    :type event_db_id: int
    :return: the stored raw trace
    :rtype: np.ndarray
    """
    with sqlite3.connect(db_path) as conn:
        data_format, blob = conn.execute(
            "SELECT data_format, raw_data FROM data WHERE event_db_id = ?",
            (event_db_id,),
        ).fetchone()
    return np.frombuffer(blob, dtype=data_format)


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

    # The export runs on a worker thread, so the files appear some time after this
    # call returns. Only the worker finishing says they are all there: the export
    # writes its tables and then one trace file per event, so a wait on any of the
    # files - even all six tables - is satisfied while trace files are still being
    # written, and a test that then reads them fails with EmptyDataError.
    #
    # The Controller stages the worker under the loader's key synchronously, inside
    # the call above, and it is popped by a queued signal once the generator is
    # exhausted - so the entry existing now and emptying later is this run's
    # completion, not a previous export's. Asserting it exists first is what stops a
    # refused export from satisfying the wait instantly.
    workers = triad.tab_controller.model.workers
    assert workers.get(LOADER_KEY), "the export never started a worker"
    qtbot.waitUntil(lambda: not workers.get(LOADER_KEY), timeout=60_000)

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
    rather than on widget state is what makes this survive refactoring.
    """
    out = tmp_path / "export_one"
    out.mkdir()

    rows = row_counts(export(metadata_tab, qtbot, out, "one_channel", {"exp_a": [0]}))

    assert rows["events"] == 25
    assert rows["sublevels"] == 75
    assert rows["data"] == 25


@pytest.mark.timeout(90)
def test_every_event_gets_its_own_trace_file(
    metadata_tab: Triad, qtbot, tmp_path: Path, monkeypatch
) -> None:
    """
    The per-event trace files are part of the export, and all of them are finished.

    The export writes its six tables first and one ``<subset>_event_<id>.csv`` per
    event after them, yielding between events. Each per-event write is slowed here so
    that a wait satisfied by the tables alone - before the worker is done - returns
    while trace files are still missing or empty, which is how this flow once read a
    half-written file and failed with ``EmptyDataError``.
    """
    original_to_csv = pd.DataFrame.to_csv

    def slow_event_writes(self: pd.DataFrame, path: Any, *args: Any, **kwargs: Any):
        """
        Delay each per-event write, then write it as the real method does.

        :param self: the frame being written
        :type self: pd.DataFrame
        :param path: the destination
        :type path: Any
        :param args: positional arguments for ``to_csv``
        :type args: Any
        :param kwargs: keyword arguments for ``to_csv``
        :type kwargs: Any
        :return: whatever ``to_csv`` returns
        :rtype: Any
        """
        if "_event_" in Path(str(path)).name:
            time.sleep(0.05)
        return original_to_csv(self, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_csv", slow_event_writes)
    out = tmp_path / "export_traces"
    out.mkdir()

    export(metadata_tab, qtbot, out, "traces", {"exp_a": [0]})

    traces = sorted(out.glob("traces_event_*.csv"))
    assert len(traces) == 25
    assert all(len(pd.read_csv(path)) > 0 for path in traces)


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
def test_every_exported_trace_belongs_to_the_event_it_is_named_for(
    out_of_order_tab: Triad,
    qtbot,
    tmp_path: Path,
    channels_written_out_of_order: str,
) -> None:
    """
    Each trace file holds its own event's samples, and ``data.csv`` names it.

    The export used to name its trace files in the events query's order and fill
    them in the event-data query's order, and to label the ``data`` rows the same
    way, pairing all three by position. Neither query is ordered, and on a database
    written channel 1 first they disagree, so every file went to another event.
    The first assertion is the guard that this database really reorders them.
    """
    out = tmp_path / "export_out_of_order"
    out.mkdir()

    export(out_of_order_tab, qtbot, out, "pairs", {"exp_a": [0, 1]})

    event_ids = pd.read_csv(out / "pairs_events.csv")["id"].tolist()
    assert event_ids != sorted(event_ids), "the events query came back in id order"

    data = pd.read_csv(out / "pairs_data.csv")
    assert len(data) == 12
    for _, row in data.iterrows():
        assert row["filename"] == f"pairs_event_{row['event_db_id']}.csv"

    traces = sorted(out.glob("pairs_event_*.csv"))
    assert len(traces) == 12
    for path in traces:
        event_db_id = int(path.stem.rsplit("_", 1)[-1])
        exported = pd.read_csv(path)["raw_data"].to_numpy()
        stored = stored_raw_data(channels_written_out_of_order, event_db_id)
        # CSV text keeps about 15 significant figures, not every bit; two events
        # differ by picoamps of noise, far outside this tolerance.
        assert len(exported) == len(stored), f"{path.name} holds another event"
        assert np.allclose(
            exported, stored, rtol=1e-9, atol=0
        ), f"{path.name} holds another event"


@pytest.mark.timeout(90)
def test_event_data_carries_the_events_table_id(
    qapp, tmp_path: Path, sample_metadata_db: str
) -> None:
    """
    ``load_event_data`` reports each event by its ``events.id``.

    The export names trace files by that id and the Protein tab writes its fits
    back to ``events`` by it. The ``data`` table numbers its rows separately, and
    the two sequences agree only while every event was written whole - a writer
    before 1.8.0 could commit an event without its data row, after which they
    differ for the rest of the file. Shifting the ``data`` ids here is that file.
    """
    with sqlite3.connect(sample_metadata_db) as conn:
        conn.execute("UPDATE data SET id = id + 1000")
        expected = {
            (channel_id, event_id): db_id
            for db_id, channel_id, event_id in conn.execute(
                "SELECT id, channel_id, event_id FROM events"
            )
        }

    loader = open_loader(sample_metadata_db)
    try:
        events = list(loader.load_event_data(None, {"exp_a": None}))
    finally:
        loader.close_resources()

    assert len(events) == len(expected) == 40
    for event in events:
        assert event["id"] == expected[(event["channel_id"], event["event_id"])]


@pytest.mark.timeout(90)
def test_the_exported_events_carry_the_expected_columns(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    A reader of the CSV needs the identity columns to join the tables back up.

    Pinned because the query that produces them moved off the View, and a projection
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


@pytest.mark.timeout(90)
def test_an_empty_subset_is_refused_and_keeps_its_name(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    The layer that can see this: a real loader, so a real generator.

    ``export_subset_to_csv`` is a generator function, so every guard in its body -
    including its own "No events found matching subset criteria" - runs on the
    worker's first advance, long after the Controller's ``try/except`` has passed
    and the View has advanced the export index. A Controller unit test cannot see
    that at all, because its model's ``call`` is free to raise synchronously, which
    the real plugin can never do. Hence a flow test, driving the real thing.

    Channel 7 does not exist in the synthetic database, so the subset is empty
    while the experiment name still resolves - an empty result, not a lookup
    failure.
    """
    out = tmp_path / "export_empty"
    out.mkdir()

    messages: List[str] = []
    metadata_tab.tab_controller.add_text_to_display.connect(
        lambda text, source: messages.append(text)
    )
    before = metadata_tab.tab_view.subset_export_count

    _StubDictDialog.folder = str(out)
    _StubDictDialog.subset_name = "empty_subset"
    metadata_tab.tab_view.selected_experiment_and_channels_by_loader[LOADER_KEY] = {
        "exp_a": [7]
    }
    metadata_tab.tab_view.handle_parameter_change(
        "metadatacontrols", "export_csv_subset", ({"db_loader": LOADER_KEY},)
    )

    # Nothing was staged, so there is no worker to wait on and no progress bar to
    # run to the end; the refusal is complete by the time the call returns.
    assert list(out.glob("*.csv")) == []
    assert metadata_tab.tab_view.subset_export_count == before
    assert any("No events match empty_subset" in text for text in messages)
    assert any("still available" in text for text in messages)


@pytest.mark.timeout(90)
def test_the_name_a_refused_export_kept_is_reused_by_the_next_one(
    metadata_tab: Triad, qtbot, tmp_path: Path
) -> None:
    """
    The user-visible half of the same guard.

    The export index names the file *and* keys the worker, so a refusal that
    advanced it would leave a gap in the user's numbering for an export that never
    produced a file. Asserting the index is unchanged proves the counter; this
    proves what the counter is for.
    """
    out = tmp_path / "export_reuse"
    out.mkdir()

    offered: List[str] = []
    original_init = _StubDictDialog.__init__

    def record_name(self: Any, *args: Any, **kwargs: Any) -> None:
        """
        Record the name the dialog was offered before standing in for it.

        :param args: positional arguments from the caller
        :type args: Any
        :param kwargs: keyword arguments from the caller
        :type kwargs: Any
        :return: None
        :rtype: None
        """
        offered.append(str(kwargs.get("name")))
        original_init(self, *args, **kwargs)

    _StubDictDialog.__init__ = record_name  # type: ignore[method-assign]
    try:
        _StubDictDialog.folder = str(out)
        _StubDictDialog.subset_name = "refused"
        metadata_tab.tab_view.selected_experiment_and_channels_by_loader[LOADER_KEY] = {
            "exp_a": [7]
        }
        metadata_tab.tab_view.handle_parameter_change(
            "metadatacontrols", "export_csv_subset", ({"db_loader": LOADER_KEY},)
        )

        export(metadata_tab, qtbot, out, "accepted", {"exp_a": [0]})
    finally:
        _StubDictDialog.__init__ = original_init  # type: ignore[method-assign]

    assert offered == ["Subset_0", "Subset_0"]
