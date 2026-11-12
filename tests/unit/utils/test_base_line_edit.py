"""
``BaseLineEdit`` suspends its validation while a message box is up, and stops at quit.

A message box takes the focus, and a line edit holding invalid text would otherwise
refuse to give it up and validate against the box. One application-wide guard watches
for message boxes and sets ``BaseLineEdit``'s two class flags. Every line edit used to
install its own copy of that filter on the application, so each Qt event passed through
one Python call per live line edit - in November 2026 the test suite's leaked line edits
made building one controller take 11.6 s instead of 52 ms.
"""

from typing import Any, Iterator

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox

from poriscope.utils.BaseLineEdit import BaseLineEdit
from poriscope.utils.MessageBoxValidationGuard import MessageBoxValidationGuard


@pytest.fixture
def flags() -> Iterator[None]:
    """Restore the class flags the tests change, so no other test sees them set."""
    suspended, closing = BaseLineEdit.suspend_validation, BaseLineEdit.app_closing
    yield
    BaseLineEdit.suspend_validation, BaseLineEdit.app_closing = suspended, closing


def test_a_shown_message_box_suspends_validation_until_it_hides(
    qapp: Any, flags: None
) -> None:
    edit = BaseLineEdit()
    box = QMessageBox()
    box.show()
    assert BaseLineEdit.suspend_validation is True
    assert edit.isValid() is True
    box.hide()
    assert BaseLineEdit.suspend_validation is False


def test_the_application_quitting_marks_it_closing(qapp: Any, flags: None) -> None:
    edit = BaseLineEdit()
    QApplication.instance().aboutToQuit.emit()
    assert BaseLineEdit.app_closing is True
    assert edit.isValid() is True


def test_one_guard_serves_every_line_edit(qapp: Any) -> None:
    edits = [BaseLineEdit() for _ in range(20)]
    guards = QApplication.instance().findChildren(MessageBoxValidationGuard)
    assert len(guards) == 1, f"{len(guards)} guards for {len(edits)} line edits"


def test_the_guard_outlives_the_line_edits(qapp: Any, flags: None) -> None:
    edit = BaseLineEdit()
    edit.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    box = QMessageBox()
    box.show()
    assert BaseLineEdit.suspend_validation is True
    box.hide()


def test_a_line_edit_is_no_longer_an_application_event_filter(qapp: Any) -> None:
    calls = []

    class Counting(BaseLineEdit):
        def eventFilter(self, obj: Any, event: Any) -> bool:
            calls.append(event.type())
            return False

    _edit = Counting()  # held, so it is alive when the box shows
    box = QMessageBox()
    box.show()
    box.hide()
    assert calls == []
