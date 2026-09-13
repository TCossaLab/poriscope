"""
conftest.py for tests/unit/controllers

These tests drive real Controller/View pairs, so a View method that opens a modal
stalls the test rather than failing it. That went from theoretical to actual when
Step 4a promoted ``on_raw_filter_validated`` to ``MetaSubsetTabView`` carrying
Metadata's ``QMessageBox.warning``: ``test_protein_controller``'s
``test_invalid_forwards_to_view`` drives it through the Controller's forwarder and
hung on the real dialog, because this directory had no guard while
``tests/unit/views`` did.

Only the dialog patches are installed here. Unlike ``tests/unit/views``, this
directory sets no offscreen Qt platform and no Agg backend, and this fixture
deliberately does not start doing so - that would change how every test in here
constructs its widgets, which is well beyond keeping a modal from stalling one.
"""

import pytest

from tests.unit._dialog_guard import prevent_blocking_dialogs


@pytest.fixture(autouse=True)
def _prevent_blocking_dialogs(monkeypatch):
    """
    Auto-applied to every test in this directory: makes any modal dialog return
    immediately instead of opening a real blocking event loop.

    A test that wants to assert what a dialog said should patch the specific call
    it cares about, as ``test_protein_controller`` does for the raw-filter modal.
    """
    prevent_blocking_dialogs(monkeypatch)
