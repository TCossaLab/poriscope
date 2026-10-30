"""
The Protein panel's own write-back setters: the pore, N and the analysis mode.

Each writes without emitting an action, so a recorded value can be shown without
asking for anything.
"""

from typing import Any, List

import pytest
from PySide6.QtWidgets import QApplication

from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls


@pytest.fixture
def panel(qapp: QApplication) -> ProteinControls:
    """
    A fresh Protein panel.

    :param qapp: pytest-qt's application fixture
    :type qapp: QApplication
    :return: the panel
    :rtype: ProteinControls
    """
    widget = ProteinControls()
    qapp.processEvents()
    return widget


@pytest.fixture
def emitted(panel: ProteinControls) -> List[str]:
    """
    Every action the panel emits from now on.

    :param panel: the panel under test
    :type panel: ProteinControls
    :return: the emitted action names, in order
    :rtype: List[str]
    """
    actions: List[str] = []
    panel.actionTriggered.connect(
        lambda _view, action, _params: actions.append(action)
    )
    return actions


def test_set_pore_writes_the_diameter_and_length(panel: Any, emitted: Any) -> None:
    panel.set_pore(12.5, 30.0)

    assert panel.pore_diameter_lineEdit.text() == "12.5"
    assert panel.pore_length_lineEdit.text() == "30.0"
    assert emitted == []


def test_set_n_values_writes_n(panel: Any, emitted: Any) -> None:
    panel.set_n_values(250)

    assert panel.n_values_lineEdit.text() == "250"
    assert emitted == []


@pytest.mark.parametrize("mode", ["ensemble", "individual"])
def test_set_mode_checks_its_button_and_not_the_other(
    panel: Any, emitted: Any, mode: str
) -> None:
    other = "individual" if mode == "ensemble" else "ensemble"
    getattr(panel, f"{other}_button").setChecked(True)

    assert panel.set_mode(mode) is True

    assert getattr(panel, f"{mode}_button").isChecked()
    assert not getattr(panel, f"{other}_button").isChecked()
    assert getattr(panel, f"{mode}_button").font().bold()
    assert emitted == []


def test_set_mode_refuses_a_mode_it_does_not_have(panel: Any, emitted: Any) -> None:
    assert panel.set_mode("sideways") is False

    assert panel.individual_button.isChecked()
