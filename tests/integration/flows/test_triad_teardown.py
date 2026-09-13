"""
The flow harness tears a tab down the way closing the app does.

**Why this exists.** ``Triad.close()`` closed the data plugins but left the tab's own
worker threads running, so Qt destroyed a live ``QThread`` when the triad went out of
scope. That aborts the interpreter rather than failing a test - **exit 134 on Linux,
127 on Windows** - with every test reported as passed and no traceback naming the
cause, which is why it read as flakiness for days and was recorded in
``future_fixes.md`` as unexplained.

It is a race, so it bit only when a worker outlived its test: the export, event-fitting
and event-finding flows are the three that start one. Before the fix,
``test_metadata_export_flow_no_gui.py`` exited 127 on **three runs out of three** while
reporting ``8 passed``; after it, zero out of four, and CI went from aborting at exit
134 to green.

So the assertion here is not about worker threads for their own sake. It is that **the
harness's teardown matches the application's**, which is the property that makes every
flow test in this directory safe to run beside its neighbours.
"""

from pathlib import Path

import pytest

from poriscope.plugins.db_loaders.SQLiteDBLoader import SQLiteDBLoader
from tests.integration.flows._triad import Triad, build_triad

LOADER_KEY = "loader"


@pytest.fixture
def metadata_tab(qapp, tmp_path: Path, sample_metadata_db: str) -> Triad:
    """
    A metadata tab with a real loader, the same shape the export flow builds.

    :param qapp: pytest-qt's application fixture; MainView is a real widget
    :type qapp: Any
    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :param sample_metadata_db: path to a generated metadata database
    :type sample_metadata_db: str
    :return: the assembled triad
    :rtype: Triad
    """
    triad = build_triad("MetadataController", tmp_path)

    loader = SQLiteDBLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = sample_metadata_db
    loader.apply_settings(settings)
    triad.register(loader, "MetaDatabaseLoader", LOADER_KEY)

    return triad


@pytest.mark.timeout(90)
def test_closing_the_triad_leaves_no_worker_thread_running(
    metadata_tab: Triad, tmp_path: Path
) -> None:
    """
    The invariant, stated against the completed state rather than against a count.

    A worker is started and then the triad is closed *without waiting for it*, which
    is the ordering that used to abort. ``exiting=True`` is what makes the shutdown
    block until each thread has actually finished, so afterwards every thread this
    tab owns must report itself stopped.
    """
    out = tmp_path / "export"
    out.mkdir()

    metadata_tab.tab_controller.export_csv_subset(
        LOADER_KEY, str(out), "Subset_0", None, {"exp_a": [0]}, 0
    )

    model = metadata_tab.tab_controller.model
    started = [
        thread for threads in model.threads.values() for thread in threads.values()
    ]
    assert started, (
        "the export staged no worker, so this test is not exercising the teardown "
        "it exists for"
    )

    metadata_tab.close()

    still_running = [thread for thread in started if thread.isRunning()]
    assert not still_running, (
        f"{len(still_running)} worker thread(s) outlived Triad.close(); Qt aborts the "
        "interpreter when it destroys a running QThread, which reports as a crash "
        "rather than as a failure here"
    )


@pytest.mark.timeout(90)
def test_the_harness_kills_workers_the_way_the_app_does() -> None:
    """
    The teardown is only trustworthy while it mirrors the real shutdown handler.

    ``MainController.handle_about_to_quit`` kills each tab's workers *before* closing
    the data plugins, because a worker still running against a loader whose
    connections have been closed is the other half of the same fault. Asserting the
    order here is cheaper than rediscovering it from a core dump.

    :return: None
    :rtype: None
    """
    import inspect

    from poriscope.controllers.main_controller import MainController

    app_shutdown = inspect.getsource(MainController.handle_about_to_quit)
    harness = inspect.getsource(Triad.close)

    for source, label in ((app_shutdown, "the app"), (harness, "Triad.close")):
        kill = source.index("handle_kill_all_workers")
        exit_plugins = source.index("handle_exit")
        assert kill < exit_plugins, (
            f"{label} closes the data plugins before killing the workers that run "
            "against them"
        )
        assert (
            "exiting=True" in source
        ), f"{label} asks the workers to stop without waiting for them to finish"
