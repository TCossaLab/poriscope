"""
Tests for the two sidebar menus, ``IconMenuWidget`` and ``IconTextMenuWidget``.

Both are built against a stand-in main view that carries the one signal they
connect to, so no ``MainView`` has to be constructed.
"""

import os
from typing import List

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from poriscope.views.widgets import icon_menu_widget, text_menu_widget
from poriscope.views.widgets.icon_menu_widget import IconMenuWidget
from poriscope.views.widgets.text_menu_widget import IconTextMenuWidget


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _MainViewStandIn(QObject):
    """The part of ``MainView`` the menus touch: the signal they connect to."""

    help_window_closed = Signal()


@pytest.fixture
def main_view():
    return _MainViewStandIn()


@pytest.fixture
def loaded_icons(monkeypatch) -> List[str]:
    """
    Record every icon file either menu loads.

    Swaps the modules' ``QIcon`` for a subclass that notes the path given to its
    constructor or to ``addFile``, and otherwise behaves as ``QIcon``.
    """
    paths: List[str] = []

    class RecordingIcon(QIcon):
        def __init__(self, *args):
            if args and isinstance(args[0], str):
                paths.append(args[0])
            super().__init__(*args)

        def addFile(self, path, *args):
            paths.append(path)
            super().addFile(path, *args)

    monkeypatch.setattr(icon_menu_widget, "QIcon", RecordingIcon)
    monkeypatch.setattr(text_menu_widget, "QIcon", RecordingIcon)
    return paths


def _icon_files(widget) -> List[str]:
    return os.listdir(widget.icon_path)


# ---------------------------------------------------------------------------
# each click switches once
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "button, signal",
    [
        ("help_icon_button", "switchToHelp"),
        ("settings_icon_button", "switchToSettings"),
        ("raw_data_icon_button", "switchToRawData"),
    ],
)
def test_a_click_emits_its_switch_signal_once(main_view, button, signal):
    """
    Clicking a sidebar icon emits its switch signal exactly once.

    Help and Settings used to emit twice, from ``connectSignals`` and again from
    their click handlers, so the Settings page was built twice per click.
    """
    menu = IconMenuWidget(main_view)
    emitted = []
    getattr(menu, signal).connect(lambda: emitted.append(signal))

    getattr(menu, button).click()

    assert emitted == [signal]


# ---------------------------------------------------------------------------
# icon files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("menu_class", [IconMenuWidget, IconTextMenuWidget])
def test_every_icon_the_menu_loads_exists_with_that_exact_case(
    main_view, loaded_icons, menu_class
):
    """
    Every icon path a menu loads names a file that exists, spelled with its case.

    Compared against a directory listing rather than ``os.path.exists``, so a
    wrongly cased name fails on Windows too, not only on case-sensitive Linux.
    """
    menu = menu_class(main_view)
    on_disk = set(_icon_files(menu))

    missing = sorted(
        {os.path.basename(p) for p in loaded_icons} - on_disk,
    )

    assert loaded_icons, "the recording stand-in saw no icons"
    assert missing == []


def test_the_text_menus_raw_data_entry_uses_the_raw_data_icon(main_view, mocker):
    """The text menu's Raw Data entry shows the pie icon, not Event Analysis's."""
    spy = mocker.spy(IconTextMenuWidget, "createTextButton")

    IconTextMenuWidget(main_view)

    icon_for = {c.args[2]: os.path.basename(c.args[4]) for c in spy.call_args_list}
    assert icon_for["data"] == "datapie-black.svg"
