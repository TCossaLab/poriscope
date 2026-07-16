from typing import Sequence

from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


def _normalize_label(text: str) -> str:
    """Remove accelerator ampersands and trim whitespace."""
    return (text or "").replace("&", "").strip()


def open_menu_hybrid(
    main_view: QtWidgets.QMainWindow,
    menu_path_labels: Sequence[str],
    qtbot,
    timeout_ms: int = 10_000,
) -> QtGui.QAction:
    """
    Click top-level menu; traverse persistent submenus; trigger final action.
    """
    assert menu_path_labels, "menu path is empty"

    # --- Click top-level menu on the menubar
    menu_bar = main_view.menuBar()
    top_level_label = menu_path_labels[0]
    top_level_action = next(
        action
        for action in menu_bar.actions()
        if _normalize_label(action.text()) == _normalize_label(top_level_label)
    )
    action_rect = menu_bar.actionGeometry(top_level_action)
    QTest.mouseClick(menu_bar, Qt.LeftButton, Qt.NoModifier, action_rect.center())
    qtbot.wait(10)

    # --- Traverse the logical menu tree (no popup geometry)
    current_menu = top_level_action.menu()
    qtbot.waitUntil(lambda: current_menu is not None, timeout=timeout_ms)

    # Walk intermediate labels and descend through submenus
    for intermediate_label in menu_path_labels[1:-1]:
        intermediate_action = next(
            action
            for action in current_menu.actions()
            if _normalize_label(action.text()) == _normalize_label(intermediate_label)
        )
        next_menu = intermediate_action.menu()
        if next_menu is None:
            # Some apps build submenus lazily; trigger to force creation
            intermediate_action.trigger()
            next_menu = intermediate_action.menu()
        current_menu = next_menu
        qtbot.wait(10)

    # Trigger the final action
    final_label = menu_path_labels[-1]
    final_action = next(
        action
        for action in current_menu.actions()
        if _normalize_label(action.text()) == _normalize_label(final_label)
    )
    final_action.trigger()
    qtbot.wait(20)

    return final_action


# ---------------------------------------------------------------------------
# Shared dialog/widget-finding utilities.
# ---------------------------------------------------------------------------

def _first_modal_dialog():
    """Find the currently active modal dialog, with a fallback for
    Qt.Popup-flagged dialogs (e.g. SelectionTree.show_dialog()) which don't
    reliably register via activeModalWidget()/activePopupWidget() under
    the offscreen platform plugin used in headless test runs."""
    w = QtWidgets.QApplication.activeModalWidget()
    if isinstance(w, QtWidgets.QDialog):
        return w
    w = QtWidgets.QApplication.activePopupWidget()
    if isinstance(w, QtWidgets.QDialog):
        return w
    for tw in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(tw, QtWidgets.QDialog) and tw.isVisible():
            return tw
    return None


def _find_button(dlg, label_lower: str):
    """Find a QPushButton in dlg whose text matches label_lower exactly
    (case-insensitive)."""
    for b in dlg.findChildren(QtWidgets.QPushButton):
        if (b.text() or "").lower() == (label_lower or "").lower():
            return b
    return None


def _find_button_contains(dlg, snippet: str):
    """Find a QPushButton in dlg whose text contains snippet
    (case-insensitive substring match)."""
    needle = (snippet or "").lower()
    for b in (dlg.findChildren(QtWidgets.QPushButton) if dlg else []):
        if needle in (b.text() or "").lower():
            return b
    return None


def _fake_get_item_exact_then_substring(*wants):
    """Build a QInputDialog.getItem replacement that tries an exact match
    against each of `wants` first, then falls back to a substring match -
    avoids issues like "CUSUM" matching "ClassicCUSUM" first because it's
    alphabetically earlier when only substring matching is used."""

    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for want in wants:
            if not want:
                continue
            for it in items:
                if it == want:
                    return it, True
        for want in wants:
            if want and any(want in it for it in items):
                for it in items:
                    if want in it:
                        return it, True
        return (items[0] if items else "No Selection"), True

    return fake_get_item