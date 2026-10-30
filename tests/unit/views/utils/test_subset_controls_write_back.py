"""
The write-back setters both subset-tab panels share, on each panel.

Each writes one field without emitting an action, and says whether a value was an
option, so a recorded value can be shown in either tab's panel.
"""

from typing import Any, List

import pytest
from PySide6.QtWidgets import QApplication

from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls


@pytest.fixture(params=[MetadataControls, ProteinControls], ids=["metadata", "protein"])
def panel(request: Any, qapp: QApplication) -> MetaSubsetTabControls:
    """
    A fresh panel of each subset tab.

    :param request: pytest's request, carrying the panel class
    :type request: Any
    :param qapp: pytest-qt's application fixture
    :type qapp: QApplication
    :return: the panel
    :rtype: MetaSubsetTabControls
    """
    widget = request.param()
    qapp.processEvents()
    return widget


@pytest.fixture
def emitted(panel: MetaSubsetTabControls) -> List[str]:
    """
    Every action the panel emits from now on.

    :param panel: the panel under test
    :type panel: MetaSubsetTabControls
    :return: the emitted action names, in order
    :rtype: List[str]
    """
    actions: List[str] = []
    panel.actionTriggered.connect(
        lambda _view, action, _params: actions.append(action)
    )
    return actions


def test_set_loader_shows_an_option(panel, emitted) -> None:
    panel.db_loader_comboBox.addItem("first")
    panel.db_loader_comboBox.addItem("second")
    emitted.clear()  # the first loader added is selected, which emits

    assert panel.set_loader("second") is True

    assert panel.db_loader_comboBox.currentText() == "second"
    assert emitted == []


def test_set_loader_refuses_a_loader_not_on_offer(panel, emitted) -> None:
    panel.db_loader_comboBox.addItem("first")

    assert panel.set_loader("gone") is False

    assert panel.db_loader_comboBox.currentText() == "first"


def test_set_bins_writes_widths_with_sizes_and_its_validator(panel, emitted) -> None:
    panel.set_bins([0.5, 1.5], True)

    assert panel.sizes_checkbox.isChecked()
    assert panel.bins_lineEdit.text() == "0.5, 1.5"
    assert panel.bins_lineEdit.validator() is panel.float_validator
    assert emitted == []


def test_set_bins_writes_counts_without_sizes(panel, emitted) -> None:
    panel.set_bins([0.5], True)

    panel.set_bins([20], False)

    assert not panel.sizes_checkbox.isChecked()
    assert panel.bins_lineEdit.text() == "20"
    assert panel.bins_lineEdit.validator() is panel.int_validator


def test_set_bins_clears_the_entry_for_estimated_bins(panel, emitted) -> None:
    panel.bins_lineEdit.setText("7")

    panel.set_bins(None, False)

    assert panel.bins_lineEdit.text() == ""


def test_set_event_count_writes_the_count(panel, emitted) -> None:
    panel.set_event_count(4)

    assert panel.n_events_lineEdit.text() == "4"
    assert emitted == []


def test_set_raw_ticks_the_box(panel, emitted) -> None:
    panel.set_raw(True)

    assert panel.raw_checkbox.isChecked()
    assert emitted == []


def test_set_filters_selects_exactly_those(panel, emitted) -> None:
    for name in ("F0", "F1", "F2"):
        panel.filter_comboBox.addItem(name)
    panel.filter_comboBox.selectItem("F2")

    assert panel.set_filters(["F0", "F1"]) is True

    assert panel.filter_comboBox.getSelectedItems() == ["F0", "F1"]
    assert emitted == []


def test_set_filters_selects_those_on_offer_and_says_one_was_not(panel, emitted) -> None:
    panel.filter_comboBox.addItem("F0")

    assert panel.set_filters(["F0", "gone"]) is False

    assert panel.filter_comboBox.getSelectedItems() == ["F0"]


def test_set_filters_with_none_clears_the_selection(panel, emitted) -> None:
    panel.filter_comboBox.addItem("F0")
    panel.filter_comboBox.selectItem("F0")

    assert panel.set_filters([]) is True

    assert panel.filter_comboBox.getSelectedItems() == []
