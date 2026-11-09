"""
What each tab clears when the user goes back to before a replay that failed.

The tab is cleared, then its history from before the replay is replayed onto it. So the
clear leaves no figure and no result a later action could draw from, and records nothing:
the history is put back afterwards. Controllers built without Qt, with their View and Model
mocked, so only the calls each one makes are observed.
"""

from collections import OrderedDict
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ClusteringController import ClusteringController
from poriscope.plugins.analysistabs.EventAnalysisController import (
    EventAnalysisController,
)
from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.RawDataController import RawDataController
from poriscope.utils.MetaView import MetaView


def _make(cls: type, mocker: MockerFixture) -> Any:
    controller = cls.__new__(cls)
    controller.view = mocker.Mock()
    controller.model = mocker.Mock()
    controller.logger = mocker.Mock()
    controller.tab_action_history = OrderedDict()
    for signal in ("add_text_to_display", "update_tab_action_history"):
        setattr(controller, signal, mocker.Mock())
    return controller


@pytest.mark.parametrize("cls", [RawDataController, EventAnalysisController])
def test_an_event_tab_clears_its_figure(cls: type, mocker: MockerFixture) -> None:
    controller = _make(cls, mocker)

    controller.clear_for_replay()

    controller.view.clear_figure.assert_called_once_with()
    assert controller.tab_action_history == OrderedDict()


def test_metadata_clears_its_figure_and_what_the_figure_held(
    mocker: MockerFixture,
) -> None:
    controller = _make(MetadataController, mocker)

    controller.clear_for_replay()

    controller.model.clear_overlay.assert_called_once_with("2d")
    controller.view.clear_plot.assert_called_once_with("2d")
    assert controller.tab_action_history == OrderedDict()


def test_clustering_clears_its_figure_and_its_result(mocker: MockerFixture) -> None:
    controller = _make(ClusteringController, mocker)
    controller.model.result = ("frame", "labels", "confidence")

    controller.clear_for_replay()

    controller.view.clear_plot.assert_called_once_with()
    assert controller.model.result is None
    assert controller.tab_action_history == OrderedDict()


def test_protein_clears_both_modes_figures_and_both_fits(
    mocker: MockerFixture,
) -> None:
    controller = _make(ProteinController, mocker)
    controller.model.individual_fit = "individual fit"
    controller.model.ensemble_fit = "ensemble fit"

    controller.clear_for_replay()

    assert controller.view.clear_plot.call_args_list == [
        mocker.call("2d", "individual"),
        mocker.call("2d", "ensemble"),
    ]
    assert controller.model.individual_fit is None
    assert controller.model.ensemble_fit is None
    assert controller.tab_action_history == OrderedDict()


def test_the_views_clear_empties_the_figure_and_redraws_it() -> None:
    view = MagicMock()

    MetaView.clear_figure(view)

    view.figure.clear.assert_called_once_with()
    view.canvas.draw.assert_called_once_with()
