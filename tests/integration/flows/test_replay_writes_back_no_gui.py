"""
A replayed action's recorded values are shown in its tab's panel.

Every replay - the restore dialog's, Replay Actions, Load Plot Configuration, Go back - runs
through the tab's ``ReplaySequence``, which writes each entry's values back into the panel
(``MetaView.write_back``) before it calls the action. So a restored tab shows the channel,
plugins and values that produced what it draws, and the next manual click starts from them.
These tests build real tabs and replay recorded entries through ``start_replay``.
"""

from pathlib import Path
from typing import Any, Dict, Iterator

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import (
    Triad,
    build_rawdata_tab,
    build_triad,
    named,
)

READER = "reader"
FINDER = "finder"
LOADER = "loader"


def _entry(triad: Triad, action: str, *values: Any) -> Dict[str, Any]:
    return {"action": action, "args": [], "kwargs": named(triad, action, *values)}


def _replay(triad: Triad, qtbot: Any, mocker: Any, *entries: Dict[str, Any]) -> None:
    """Replay the entries through the tab's sequence, keeping whatever a failed step drew."""
    mocker.patch.object(triad.tab_view, "ask_after_replay_failure", return_value="keep")
    controller = triad.tab_controller
    assert controller.start_replay(list(entries))
    qtbot.waitUntil(lambda: not controller.is_replaying(), timeout=30000)


@pytest.fixture
def rawdata(
    qapp: Any, tmp_path: Path, sample_chimera: Dict[str, str]
) -> Iterator[Triad]:
    triad = build_rawdata_tab(tmp_path, sample_chimera, READER, FINDER)
    yield triad
    triad.close()


@pytest.fixture
def protein(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Iterator[Triad]:
    triad = build_triad("ProteinController", tmp_path)
    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    yield triad
    triad.close()


@pytest.mark.timeout(120)
def test_a_replayed_trace_shows_its_reader_channel_and_range(
    rawdata: Triad, qtbot: Any, mocker: Any
) -> None:
    channel = rawdata.channel  # type: ignore[attr-defined]
    controls = rawdata.tab_view.rawdatacontrols
    controls.start_time_lineEdit.set_range(0.0, 0.1)

    _replay(
        rawdata,
        qtbot,
        mocker,
        _entry(rawdata, "update_trace", READER, [channel], 0.2, 0.05, "", False),
    )

    assert controls.readers_comboBox.currentText() == READER
    assert controls.channel_comboBox.getSelectedItems() == [str(channel)]
    assert controls.start_time_lineEdit.get_start() == 0.2
    assert controls.start_time_lineEdit.get_duration() == pytest.approx(0.05)


@pytest.mark.timeout(120)
def test_a_replayed_protein_plot_shows_its_values(
    protein: Triad, qtbot: Any, mocker: Any
) -> None:
    view = protein.tab_view
    controls = view.proteincontrols
    action = "update_individual_distribution"

    _replay(
        protein,
        qtbot,
        mocker,
        _entry(
            protein,
            action,
            LOADER,
            {"Full Dataset": ""},
            {"exp_a": ["1"]},
            [0.5],
            True,
            12.5,
            30.0,
            250,
        ),
    )

    assert controls.db_loader_comboBox.currentText() == LOADER
    assert controls.pore_diameter_lineEdit.text() == "12.5"
    assert controls.pore_length_lineEdit.text() == "30.0"
    assert controls.n_values_lineEdit.text() == "250"
    assert controls.bins_lineEdit.text() == "0.5"
    assert controls.individual_button.isChecked()
