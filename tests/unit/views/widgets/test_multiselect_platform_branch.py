"""
Both platform branches of ``MultiSelectComboBox``'s popup container.

CI runs on Linux under Xvfb, so it only ever builds the ``QWidget`` container.
The ``QDialog`` one is what actually ships to users, and ``DECISIONS.md``
2026-09-01 records this path as structurally unexercisable on Linux - which is why
the 2.0.0 plan schedules a manual Windows pass after every structural step.

It does not have to be unexercisable. The branch reads ``sys.platform`` at
construction time, so patching it builds either container on either host. That does
not replace the manual pass - only a human can see whether a popup dismisses
properly or leaves a ghost window behind - but it does mean a *structural* change to
the Windows branch fails in CI rather than waiting for someone to run the app.

Added by the Step 2 exit review, which found that ``test_multiselect.py`` and
``test_multiselect_filter.py`` exist but neither patches the platform.

**Only this widget has the branch.** ``multiselect_filter.py`` builds a ``QDialog``
unconditionally, so there is nothing to parametrize there - asserted below so the
asymmetry is recorded rather than rediscovered.
"""

import sys

import pytest
from PySide6.QtWidgets import QDialog, QWidget

from poriscope.views.widgets import multiselect, multiselect_filter
from poriscope.views.widgets.multiselect import MultiSelectComboBox

pytestmark = pytest.mark.characterization


@pytest.fixture
def as_platform(qapp, monkeypatch, request):
    """
    Build the widget as if running on the requested platform.

    ``qapp`` is requested explicitly: these construct real widgets, and without a
    QApplication the interpreter segfaults rather than failing a test.

    :param qapp: pytest-qt's application fixture
    :type qapp: Any
    :param monkeypatch: pytest's fixture
    :type monkeypatch: Any
    :param request: the parametrized platform name
    :type request: Any
    :return: a freshly built combo box
    :rtype: MultiSelectComboBox
    """
    monkeypatch.setattr(multiselect.sys, "platform", request.param)
    widget = MultiSelectComboBox()
    yield widget
    widget.containerWidget.close()
    widget.deleteLater()


@pytest.mark.parametrize("as_platform", ["linux"], indirect=True)
def test_linux_uses_a_frameless_popup_widget(as_platform) -> None:
    """
    The branch CI has always taken.

    A plain ``QWidget`` with popup flags, because a ``QDialog`` popup misbehaves
    under some Linux window managers.
    """
    assert isinstance(as_platform.containerWidget, QWidget)
    assert not isinstance(as_platform.containerWidget, QDialog)


@pytest.mark.parametrize("as_platform", ["win32", "darwin"], indirect=True)
def test_every_other_platform_uses_a_dialog(as_platform) -> None:
    """
    The branch that actually ships, and that CI has never built until now.

    Both non-Linux values are covered because the condition is written as
    ``== "linux"`` rather than as an explicit Windows check, so macOS takes the
    same path Windows does.
    """
    assert isinstance(as_platform.containerWidget, QDialog)


@pytest.mark.parametrize("as_platform", ["win32"], indirect=True)
def test_the_dialog_branch_gets_a_title_and_a_stylesheet(as_platform) -> None:
    """
    Two things only the shipped branch does, neither of which CI has ever run.

    The window title is what a user sees on the popup, and the stylesheet is what
    stops it inheriting the parent's styling - both were previously covered only by
    somebody launching the app on Windows.
    """
    assert as_platform.containerWidget.windowTitle() == "Select Channel"
    assert as_platform.containerWidget.styleSheet() != ""


@pytest.mark.parametrize("as_platform", ["linux"], indirect=True)
def test_the_linux_branch_gets_no_stylesheet(as_platform) -> None:
    """The other side of the same condition, so the asymmetry is deliberate."""
    assert as_platform.containerWidget.styleSheet() == ""


@pytest.mark.parametrize("as_platform", ["linux", "win32"], indirect=True)
def test_the_container_is_parentless_on_both_platforms(as_platform) -> None:
    """
    Owned by nobody either way, which is why the manual pass checks for ghosts.

    Recorded here rather than fixed: a parentless top-level widget outliving the
    app is exactly what was once observed, and changing the ownership is a
    behaviour change that belongs in Step 5d, not in a test.
    """
    assert as_platform.containerWidget.parent() is None


def test_the_filter_widget_has_no_platform_branch() -> None:
    """
    ``multiselect_filter.py`` builds a ``QDialog`` unconditionally.

    The two widgets are ~90% duplicates and are usually described together, so the
    asymmetry is asserted rather than assumed - Step 5d merges them, and a merge
    that gave the filter widget a platform branch it never had would change
    behaviour on Linux.
    """
    source = multiselect_filter.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()

    assert "sys.platform" not in text


def test_the_real_platform_is_restored_afterwards() -> None:
    """The monkeypatching above must not leak into the rest of the session."""
    assert multiselect.sys.platform == sys.platform
