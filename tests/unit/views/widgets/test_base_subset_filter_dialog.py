"""
The subset filter dialog shows an example in the empty filter box and, in Raw SQL mode, an info
mark that says how to follow the Scope selection.

The example follows the mode: a condition for Assisted, a complete scoped query for Raw. The
info mark is only for Raw, where the user has to write the scope and the ``event_id``
themselves. Runs headlessly.
"""

import pytest
from PySide6.QtGui import QColor
from pytestqt.qtbot import QtBot

from poriscope.configs import utils as icon_utils
from poriscope.configs.utils import get_icon
from poriscope.views.widgets.base_widgets.base_subset_filter_dialog import (
    ASSISTED_INFO,
    ASSISTED_PLACEHOLDER,
    INFO_ICON,
    INFO_ICON_RENDER_SIZE,
    INFO_ICON_SIZE,
    RAW_INFO,
    RAW_PLACEHOLDER,
    BaseSubsetFilterDialog,
)


def make_dialog(
    qtbot: QtBot, default_name: str = "", default_filter: str = ""
) -> BaseSubsetFilterDialog:
    """
    Build the dialog without a parent.

    :param qtbot: pytest-qt fixture that owns the widget
    :type qtbot: QtBot
    :param default_name: the subset name the dialog opens with
    :type default_name: str
    :param default_filter: the filter text the dialog opens with
    :type default_filter: str
    :return: the dialog
    :rtype: BaseSubsetFilterDialog
    """
    dialog = BaseSubsetFilterDialog(
        None, "Filter", [], default_name=default_name, default_filter=default_filter
    )
    qtbot.addWidget(dialog)
    return dialog


@pytest.mark.timeout(60)
def test_assisted_mode_has_a_condition_as_its_example_and_its_icon_beside_its_button(
    qtbot: QtBot,
) -> None:
    """
    Assisted is the default mode: the example is a condition, and the info icon beside the
    Assisted button points to the Assisted page of the guide. The Raw icon is hidden.
    """
    dialog = make_dialog(qtbot)

    assert dialog.filter_input.placeholderText() == ASSISTED_PLACEHOLDER
    assert not dialog.assisted_info.isHidden()
    assert dialog.raw_info.isHidden()
    assert dialog.assisted_info.toolTip() == ASSISTED_INFO
    assert "Assisted SQL filters" in dialog.assisted_info.toolTip()
    assert "<b>Help</b> → <b>Help</b> → <b>Documentation</b>" in (
        dialog.assisted_info.toolTip()
    )


@pytest.mark.timeout(60)
def test_each_mode_has_its_icon_beside_its_own_radio_button(qtbot: QtBot) -> None:
    """
    The Assisted icon follows the Assisted button and the Raw icon follows the Raw button,
    so each sits beside the mode it explains.
    """
    dialog = make_dialog(qtbot)
    layout = dialog.layout().itemAt(2).layout()

    order = [layout.itemAt(i).widget() for i in range(4)]

    assert order == [
        dialog.assisted_radio,
        dialog.assisted_info,
        dialog.raw_radio,
        dialog.raw_info,
    ]


@pytest.mark.timeout(60)
def test_the_info_icon_is_the_icon_file_and_it_exists(qtbot: QtBot) -> None:
    """
    The icon is drawn from the app's own file, not a text character, so a font without that
    character cannot leave it blank.
    """
    dialog = make_dialog(qtbot)

    assert not get_icon(INFO_ICON).isNull()
    assert not dialog.assisted_info.pixmap().isNull()
    assert not dialog.raw_info.pixmap().isNull()


@pytest.mark.timeout(60)
def test_the_info_icon_is_rendered_large_enough_to_stay_sharp(qtbot: QtBot) -> None:
    """
    The icon is rasterised well above the size it is shown at, so a high-resolution screen
    scales it down instead of stretching a tiny bitmap.
    """
    dialog = make_dialog(qtbot)

    source = get_icon(INFO_ICON, size=INFO_ICON_RENDER_SIZE)
    sizes = [size.width() for size in source.availableSizes()]

    assert max(sizes) == INFO_ICON_RENDER_SIZE
    assert INFO_ICON_RENDER_SIZE >= 4 * INFO_ICON_SIZE
    assert (
        dialog.assisted_info.pixmap().deviceIndependentSize().width() == INFO_ICON_SIZE
    )


def ink(dialog: BaseSubsetFilterDialog) -> QColor:
    """
    Read the colour the info icon is drawn in.

    :param dialog: the dialog under test
    :type dialog: BaseSubsetFilterDialog
    :return: the colour of the first visible pixel of the Assisted icon
    :rtype: QColor
    """
    image = dialog.assisted_info.pixmap().toImage()
    for y in range(image.height()):
        for x in range(image.width()):
            colour = image.pixelColor(x, y)
            if colour.alpha() > 200:
                return QColor(colour.red(), colour.green(), colour.blue())
    raise AssertionError("the icon has no visible pixel")


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    ("dark", "expected"),
    [
        (False, icon_utils.LIGHT_MODE_ICON_COLOR),
        (True, icon_utils.DARK_MODE_ICON_COLOR),
    ],
)
def test_the_info_icon_follows_the_theme_like_the_other_buttons(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, dark: bool, expected: str
) -> None:
    """
    Dark ink on a light theme and light ink on a dark one, as the add, edit and delete icons.
    """
    monkeypatch.setattr(icon_utils, "is_dark_mode", lambda: dark)

    dialog = make_dialog(qtbot)

    assert ink(dialog).name() == QColor(expected).name()


@pytest.mark.timeout(60)
def test_choosing_raw_sql_moves_the_icon_and_switches_the_example(
    qtbot: QtBot,
) -> None:
    """
    The icon and the example follow the mode radio button, both ways.
    """
    dialog = make_dialog(qtbot)

    dialog.raw_radio.setChecked(True)
    assert dialog.filter_input.placeholderText() == RAW_PLACEHOLDER
    assert not dialog.raw_info.isHidden()
    assert dialog.assisted_info.isHidden()
    assert dialog.raw_info.toolTip() == RAW_INFO

    dialog.assisted_radio.setChecked(True)
    assert dialog.filter_input.placeholderText() == ASSISTED_PLACEHOLDER
    assert not dialog.assisted_info.isHidden()
    assert dialog.raw_info.isHidden()


@pytest.mark.timeout(60)
def test_a_hidden_icon_keeps_its_space_so_the_buttons_do_not_move(
    qtbot: QtBot,
) -> None:
    """
    Hiding an icon must not shift the radio buttons beside it.
    """
    dialog = make_dialog(qtbot)

    assert dialog.assisted_info.sizePolicy().retainSizeWhenHidden()
    assert dialog.raw_info.sizePolicy().retainSizeWhenHidden()


@pytest.mark.timeout(60)
def test_the_raw_tooltip_says_how_to_follow_the_scope_and_where_to_read_more(
    qtbot: QtBot,
) -> None:
    """
    It names both placeholders, the ``WHERE`` to add, ``event_id`` and the Raw page.
    """
    dialog = make_dialog(qtbot)

    tip = dialog.raw_info.toolTip()

    assert ":experiment_id" in tip
    assert ":channel_id" in tip
    assert "Scope selection" in tip
    assert "SELECT event_id" in tip
    assert "add <b>WHERE" in tip
    assert "<b>Help</b> → <b>Help</b> → <b>Documentation</b>" in tip
    assert (
        "<b>User Guide</b> → <b>Filtering and Querying</b> → <b>Raw SQL filters</b>"
        in tip
    )


@pytest.mark.timeout(60)
def test_the_raw_example_is_a_complete_scoped_query_starting_with_event_id() -> None:
    """
    What the empty Raw box shows is itself a good filter.
    """
    example = RAW_PLACEHOLDER.removeprefix("e.g. ")

    assert example.startswith("SELECT event_id,")
    assert "experiment_id = :experiment_id" in example
    assert "channel_id = :channel_id" in example


@pytest.mark.timeout(60)
def test_editing_a_raw_filter_opens_with_the_raw_icon(qtbot: QtBot) -> None:
    """
    The mode is pre-selected from the name's suffix, so the Raw icon must be the shown one.
    """
    dialog = make_dialog(qtbot, default_name="mine_raw", default_filter="SELECT 1")

    assert not dialog.raw_info.isHidden()
    assert dialog.assisted_info.isHidden()
    assert dialog.filter_input.placeholderText() == RAW_PLACEHOLDER
