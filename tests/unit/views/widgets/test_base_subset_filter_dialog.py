"""
The subset filter dialog tells a raw SQL author how to follow the Scope selection.

The hint names the placeholders a raw filter scopes itself with, so it is shown in Raw SQL
mode and hidden in Assisted mode, where the builder adds the scope itself. Runs headlessly.
"""

import pytest
from pytestqt.qtbot import QtBot

from poriscope.views.widgets.base_widgets.base_subset_filter_dialog import (
    BaseSubsetFilterDialog,
)


def make_dialog(qtbot: QtBot, default_name: str = "") -> BaseSubsetFilterDialog:
    """
    Build the dialog without a parent.

    :param qtbot: pytest-qt fixture that owns the widget
    :type qtbot: QtBot
    :param default_name: the subset name the dialog opens with
    :type default_name: str
    :return: the dialog
    :rtype: BaseSubsetFilterDialog
    """
    dialog = BaseSubsetFilterDialog(None, "Filter", [], default_name=default_name)
    qtbot.addWidget(dialog)
    return dialog


@pytest.mark.timeout(60)
def test_the_hint_is_hidden_in_assisted_mode(qtbot: QtBot) -> None:
    """
    Assisted is the default mode, and it needs no placeholders.
    """
    dialog = make_dialog(qtbot)

    assert dialog.raw_hint.isHidden()


@pytest.mark.timeout(60)
def test_choosing_raw_sql_shows_the_hint_and_going_back_hides_it(qtbot: QtBot) -> None:
    """
    The hint follows the mode radio button, and names both placeholders.
    """
    dialog = make_dialog(qtbot)

    dialog.raw_radio.setChecked(True)
    assert not dialog.raw_hint.isHidden()
    assert ":experiment_id" in dialog.raw_hint.text()
    assert ":channel_id" in dialog.raw_hint.text()

    dialog.assisted_radio.setChecked(True)
    assert dialog.raw_hint.isHidden()


@pytest.mark.timeout(60)
def test_editing_a_raw_filter_opens_with_the_hint_shown(qtbot: QtBot) -> None:
    """
    The mode is pre-selected from the name's suffix, so the hint must start visible.
    """
    dialog = make_dialog(qtbot, default_name="mine_raw")

    assert not dialog.raw_hint.isHidden()
