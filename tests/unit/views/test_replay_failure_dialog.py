"""
The question a tab asks when a replayed entry fails: go back to before the replay, or keep.

The real ``QMessageBox`` is built; ``exec`` is replaced by a click on the named button, or by
nothing for a dialog that is closed, so no event loop is entered.
"""

from typing import Any, List, Optional

import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from poriscope.utils.MetaView import MetaView


def _ask(
    monkeypatch: Any, click: Optional[str], seen: List[str], details: str = ""
) -> str:
    def exec_(box: QMessageBox) -> int:
        seen.extend([box.text(), box.defaultButton().text()])
        if details:
            seen.append(box.informativeText())
        if click is not None:
            next(b for b in box.buttons() if b.text() == click).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_)
    parent = QWidget()
    return MetaView.ask_after_replay_failure(
        parent,  # type: ignore[arg-type]
        "MetadataController",
        2,
        3,
        "overlay_plot",
        "overlay_plot raised KeyError: 'width'",
        details,
    )


@pytest.mark.parametrize("click, answer", [("Go back", "back"), ("Keep", "keep")])
def test_the_clicked_button_is_the_answer(
    qtbot: Any, monkeypatch: Any, click: str, answer: str
) -> None:
    assert _ask(monkeypatch, click, []) == answer


def test_closing_the_dialog_keeps(qtbot: Any, monkeypatch: Any) -> None:
    assert _ask(monkeypatch, None, []) == "keep"


def test_it_names_the_tab_the_step_the_action_and_the_reason(
    qtbot: Any, monkeypatch: Any
) -> None:
    seen: List[str] = []

    _ask(monkeypatch, "Keep", seen)

    assert seen == [
        "MetadataController could not replay step 2 of 3, overlay_plot: overlay_plot "
        "raised KeyError: 'width'.",
        "Keep",
    ]


def test_what_the_step_reported_is_in_the_question(
    qtbot: Any, monkeypatch: Any
) -> None:
    """The one dialog a failed replay shows carries the errors its step logged."""
    seen: List[str] = []

    _ask(monkeypatch, "Keep", seen, details="Requested channel=5 is invalid")

    assert seen[2].startswith(
        "What the step reported:\nRequested channel=5 is invalid\n\n"
    )
