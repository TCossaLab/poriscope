"""
Protein tab, headless: what Update Plot records and draws in each analysis mode.

Each plot starts a new figure with one recorded reset and draws one subset, so a saved
history replays onto cleared figures. The route is ``handle_parameter_change``, as the
controls panel sends it, over a real ``SQLiteDBLoader`` and the synthetic metadata database.
"""

from pathlib import Path
from typing import Any, Dict, List

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER = "loader"


@pytest.fixture
def protein_tab(qapp: Any, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A Protein tab with a real loader, one experiment and channel in scope, no filter.

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
    triad.register(loader, "MetaDatabaseLoader", LOADER)
    view = triad.tab_view
    view.handle_parameter_change(
        "proteincontrols", "loader_changed", ({"db_loader": LOADER},)
    )
    view.selected_experiment_and_channels_by_loader[LOADER] = {"exp_a": ["0"]}
    yield triad
    triad.close()


def press(triad: Triad, action: str, parameters: Dict[str, Any]) -> None:
    """
    Press a control on the Protein panel, with the parameters it sends.

    :param triad: the tab under test
    :type triad: Triad
    :param action: the action the control sends
    :type action: str
    :param parameters: what the panel sends with it
    :type parameters: Dict[str, Any]
    """
    triad.tab_view.handle_parameter_change(
        "proteincontrols", action, (dict(parameters),)
    )


def update_plot(triad: Triad, mode: str, bins: int = 20) -> None:
    """
    Choose a mode and press Update Plot, as the panel does.

    :param triad: the tab under test
    :type triad: Triad
    :param mode: "individual" or "ensemble"
    :type mode: str
    :param bins: the bin count entered
    :type bins: int
    """
    press(triad, f"set_mode_{mode}", {})
    press(
        triad,
        "update_plot",
        {
            "db_loader": LOADER,
            "pore_diameter": "10",
            "pore_length": "10",
            "n_values": "20",
            "bins": [bins],
            "sizes": False,
        },
    )


def actions(triad: Triad) -> List[str]:
    """
    The names of the tab's recorded actions, oldest first.

    :param triad: the tab under test
    :type triad: Triad
    :return: the action names
    :rtype: List[str]
    """
    return [
        entry["action"] for entry in triad.tab_controller.tab_action_history.values()
    ]


def test_an_ensemble_plot_records_one_reset_before_it(protein_tab: Triad) -> None:
    update_plot(protein_tab, "ensemble")

    assert actions(protein_tab) == ["reset", "update_ensemble_distribution"]


def test_a_second_ensemble_plot_records_one_reset_too(protein_tab: Triad) -> None:
    update_plot(protein_tab, "ensemble")
    update_plot(protein_tab, "ensemble", bins=30)

    assert actions(protein_tab)[2:] == ["reset", "update_ensemble_distribution"]
