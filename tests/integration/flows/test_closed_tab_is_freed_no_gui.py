"""
A tab the app shell has let go of is freed.

``MainController`` connects each tab's signals to its own methods. A connection is held on
the Qt side, out of sight of Python's garbage collector, so a connected callable that holds
the shell or the tab strongly keeps both alive for as long as the tab's signal exists - for
good. Every ``MainModel`` imports the plugin modules afresh, so each kept tab also keeps its
plugin classes registered as subclasses of the ``Meta*`` bases, and every later
``issubclass`` against those bases slows down, until a long test run times out.
Real shell and tab, built and closed the way every flow in this directory does it.
"""

import gc
import weakref
from pathlib import Path
from typing import Any

from tests.integration.flows._triad import build_triad


def test_a_closed_tab_is_freed_with_its_shell(qapp: Any, tmp_path: Path) -> None:
    """
    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :param tmp_path: per-test scratch directory
    """
    triad = build_triad("MetadataController", tmp_path)
    tab = weakref.ref(triad.tab_controller)
    triad.close()
    triad.view.close()
    triad.view.deleteLater()
    del triad
    qapp.processEvents()

    gc.collect()

    assert tab() is None
