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


def test_the_recorded_reset_names_the_mode_of_the_plot_it_starts(
    protein_tab: Triad,
) -> None:
    update_plot(protein_tab, "ensemble")

    reset = next(iter(protein_tab.tab_controller.tab_action_history.values()))
    assert reset["kwargs"]["mode"] == "ensemble"


def test_an_ensemble_plot_replayed_in_individual_mode_draws_on_the_ensemble_figures(
    protein_tab: Triad,
) -> None:
    """The figures a recorded plot draws on follow its mode, not the page showing."""
    update_plot(protein_tab, "ensemble")
    history = list(protein_tab.tab_controller.tab_action_history.values())
    view = protein_tab.tab_view
    drawn = [line.get_label() for line in view.ax_hist_ensemble.lines]
    press(protein_tab, "set_mode_individual", {})
    protein_tab.tab_controller.tab_action_history.clear()

    protein_tab.tab_controller.replay(history)

    assert [line.get_label() for line in view.ax_hist_ensemble.lines] == drawn
    assert len(view.ax_hist_individual.lines) == 0


def history(triad: Triad) -> List[Dict[str, Any]]:
    """
    The tab's recorded history, oldest first.

    :param triad: the tab under test
    :type triad: Triad
    :return: the recorded entries
    :rtype: List[Dict[str, Any]]
    """
    return list(triad.tab_controller.tab_action_history.values())


def said(triad: Triad) -> List[str]:
    """
    Collect what the tab's View and Controller put on the status panel from now on.

    :param triad: the tab under test
    :type triad: Triad
    :return: the list the messages are appended to
    :rtype: List[str]
    """
    messages: List[str] = []
    triad.tab_view.add_text_to_display.connect(lambda text, _: messages.append(text))
    triad.tab_controller.add_text_to_display.connect(
        lambda text, _: messages.append(text)
    )
    return messages


def test_an_individual_plot_is_recorded_with_its_intent(protein_tab: Triad) -> None:
    update_plot(protein_tab, "individual")

    assert actions(protein_tab) == ["reset", "update_individual_distribution"]
    kwargs = history(protein_tab)[-1]["kwargs"]
    assert kwargs == {
        "loader": LOADER,
        "filters": {},
        "scope": {"exp_a": ["0"]},
        "bins": [20],
        "sizes": False,
        "pore_diameter": 10.0,
        "pore_length": 10.0,
        "n_values": 20,
    }


def test_the_individual_fit_is_kept_by_the_model(protein_tab: Triad) -> None:
    update_plot(protein_tab, "individual")

    fit = protein_tab.tab_controller.model.individual_fit
    assert fit is not None and len(fit) > 0
    assert not hasattr(protein_tab.tab_view, "fit_data")


def test_an_ensemble_plot_leaves_the_individual_fit(protein_tab: Triad) -> None:
    update_plot(protein_tab, "individual")
    fit = protein_tab.tab_controller.model.individual_fit

    update_plot(protein_tab, "ensemble")

    assert protein_tab.tab_controller.model.individual_fit is fit


def test_a_refused_individual_plot_records_nothing_and_leaves_the_figure(
    protein_tab: Triad,
) -> None:
    update_plot(protein_tab, "individual")
    before = history(protein_tab)
    drawn = len(protein_tab.tab_view.ax_vm_individual.collections)
    messages = said(protein_tab)
    protein_tab.tab_view.selected_experiment_and_channels_by_loader[LOADER] = {
        "exp_a": ["0", "1"]
    }

    update_plot(protein_tab, "individual")

    assert history(protein_tab) == before
    assert len(protein_tab.tab_view.ax_vm_individual.collections) == drawn
    assert (
        "Only a single channel at a time can be used for protein analysis" in messages
    )


def test_commit_individual_writes_the_model_s_fit(protein_tab: Triad) -> None:
    update_plot(protein_tab, "individual")

    press(protein_tab, "commit_individual", {"db_loader": LOADER})

    table = protein_tab.tab_controller.model.call(
        "MetaDatabaseLoader", LOADER, "get_table_by_column", "prolate_volume"
    )
    assert table == "events"


def test_commit_individual_with_no_fit_says_so(protein_tab: Triad) -> None:
    messages = said(protein_tab)

    press(protein_tab, "commit_individual", {"db_loader": LOADER})

    assert (
        "No individual fit available to commit. Run Update Plot in Individual mode first."
        in messages
    )
