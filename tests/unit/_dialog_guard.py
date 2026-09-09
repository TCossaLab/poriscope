"""
The modal-dialog guard, shared by the view and controller unit tests.

A blocking dialog in a unit test does not fail it - it *stalls* it. ``exec()``
starts its own nested event loop and waits for a click that will never come, and
the static helpers (``QMessageBox.question`` and friends) open their own loop
without going through ``exec()`` at all, so patching only ``exec`` leaves a gap.

This lived in ``tests/unit/views/conftest.py`` until Step 4a promoted
``on_raw_filter_validated`` to ``MetaSubsetTabView`` with Metadata's modal in it.
``tests/unit/controllers/test_protein_controller.py`` drives that method through
the Controller's forwarder against a real View, and immediately hung - the
controller directory had no guard of its own. Rather than duplicate the patches,
both directories now install this.

It is deliberately **not** applied at ``tests/conftest.py`` level. The e2e suite
opts into dismissing message boxes explicitly, via its own
``auto_dismiss_message_boxes`` fixture, and a blanket autouse patch would
pre-empt that and quietly make those assertions vacuous.
"""

from PySide6.QtWidgets import QDialog, QMessageBox


def prevent_blocking_dialogs(monkeypatch) -> None:
    """
    Make every modal dialog return immediately instead of opening a real loop.

    ``question`` answers Yes, so a confirmation reads as "the user agreed"; a
    test that wants the No branch patches it itself. A test that wants to assert
    dialog *content* should patch the specific call it cares about rather than
    rely on this default.

    :param monkeypatch: the calling fixture's monkeypatch, so the patches are
        undone at that fixture's teardown
    :type monkeypatch: pytest.MonkeyPatch
    :return: None
    :rtype: None
    """
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QDialog, "exec_", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(
        QMessageBox, "exec_", lambda self: QMessageBox.StandardButton.Ok
    )
    # The *static* helpers block too, and patching only exec/exec_ did not cover
    # them: QMessageBox.question() opens its own event loop without going through
    # either. The gap was invisible until a confirmation was added on a path these
    # tests drive, and the symptom is a hung test rather than a failing one.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    for _static in ("warning", "information", "critical"):
        monkeypatch.setattr(
            QMessageBox,
            _static,
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
        )
