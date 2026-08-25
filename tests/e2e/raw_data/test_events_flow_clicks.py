"""
End-to-end tests for the Raw Data tab's event detection and export workflow.

Exercises the full chain a user follows to get from a raw recording to a
database of detected events, driving the real application through synthetic
mouse clicks:

    add reader -> select channel -> draw trace -> add event finder
    -> find events -> plot events -> add writer -> commit to database

The workflow is expressed as a chain of fixtures, each building on the last
(``app_with_rawdata_tab`` -> ``reader_added`` -> ``trace_drawn`` ->
``eventfinder_added`` -> ``events_found``). Tests then attach at whichever
stage they care about. This keeps each test's failure attributable to a
specific stage rather than to one long undifferentiated script, and lets
several tests share the expensive setup work.

Test data comes from the ``synthetic_chimera_dataset`` fixture (see
``_synthetic.py``), which generates a Chimera-format recording with a known
number of events at known positions. Because the ground truth is known,
assertions here check exact values -- the precise event count, the precise
number of database rows -- rather than merely that something happened.
"""

import sqlite3
import sys
from pathlib import Path

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import (
    FINDER_NAME,
    QT_SHORT_PAUSE_MS,
    QT_WAIT_TIMEOUT_MS,
    READER_NAME,
    channels_have_loaded,
    count_plot_lines,
    ensure_name_filled,
    find_button,
    find_channel_combo,
    open_menu_hybrid,
    schedule_dialog_autofill,
    select_any_channel,
    sqlite_has_tables,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ==========================================================================
# Workflow stages
# ==========================================================================


@pytest.fixture
def app_with_rawdata_tab(qtbot, tmp_path):
    """
    Launch the application and open a Raw Data tab.

    Builds the MVC trio against a throwaway config rooted in ``tmp_path`` so
    the test never touches real user data or plugin directories, shows the
    main window, and navigates the menus to create a Raw Data tab.

    The model, view and controller are attached to the returned view as
    ``_test_keepalive``. They must stay referenced for the lifetime of the
    tab: they are ``QObject``s with no C++ parent, so their Qt-side
    existence follows their Python references. If they were left as locals
    they would be collected when this fixture returns, tearing down the
    signal connections that make the UI respond to clicks -- silently, with
    no error, leaving a window that simply ignores input.

    :return: ``(raw_view, controls)`` -- the tab widget and its
        ``RawDataControls`` panel.
    """
    model = MainModel(
        {
            "Parent Folder": str(tmp_path),
            "User Plugin Folder": str(tmp_path),
            "Log Level": 20,
        }
    )
    view = MainView(model.get_available_plugins())
    controller = MainController(model, view)
    qtbot.addWidget(view)
    view.show()

    open_menu_hybrid(view, ["Analysis", "New Analysis Tab", "RawDataController"], qtbot)
    qtbot.waitUntil(lambda: "RawDataView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("RawDataView")
    raw_view = view.pages["RawDataView"]["widget"]
    controls = raw_view.rawdatacontrols

    raw_view._test_keepalive = (model, view, controller)

    # Let the newly shown page complete its layout pass. Synthetic clicks
    # are delivered to widget coordinates, which aren't meaningful until the
    # widget has been laid out.
    qtbot.wait(100)
    assert controls.readers_add_button.isVisible(), (
        "readers_add_button not visible after switching to RawDataView -- "
        "page may not be fully shown/laid out yet"
    )
    assert (
        controls.readers_add_button.isEnabled()
    ), "readers_add_button unexpectedly disabled"

    return raw_view, controls


@pytest.fixture
def reader_added(qtbot, monkeypatch, app_with_rawdata_tab, synthetic_chimera_dataset):
    """
    Add a reader for the synthetic dataset and select one of its channels.

    Adding a reader through the UI opens two dialogs in sequence: a picker
    for which reader subclass to instantiate, and a settings dialog for that
    instance (which itself opens a file browser). All three are replaced
    with automatic responses so the flow runs unattended:

    * ``QInputDialog.getItem`` -- returns the configured reader class.
      Patched both at its source module and at ``MetaView``, which imported
      the name directly and so holds its own reference to the original.
    * ``QFileDialog.getOpenFileName`` -- returns the synthetic log file.
      Patched at its source and in ``dict_dialog_widget`` for the same reason.
    * The settings dialog itself -- filled and accepted by
      ``fill_reader_dialog`` below.

    Once the reader exists, selecting it in the combo box triggers an
    asynchronous fetch of its channel list, which must complete before a
    channel can be ticked.

    :return: ``(raw_view, controls, dataset, reader_key)`` where
        ``reader_key`` is the instance name the application assigned.
    """
    raw_view, controls = app_with_rawdata_tab
    ds = synthetic_chimera_dataset

    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for it in items:
            if READER_NAME in it:
                return it, True
        return (items[0] if items else "No Selection"), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )
    monkeypatch.setattr(
        "poriscope.utils.MetaView.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(ds.data_path), "All Files (*)")),
        raising=False,
    )
    monkeypatch.setattr(
        "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(ds.data_path), "All Files (*)")),
        raising=False,
    )

    def fill_reader_dialog(dlg) -> bool:
        """Choose the input file, name the instance, and accept the dialog."""
        pick = find_button(dlg, "select input file")
        if pick:
            QTest.mouseClick(pick, Qt.LeftButton)
            qtbot.wait(QT_SHORT_PAUSE_MS)
        ensure_name_filled(dlg, "reader_e2e")
        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_reader_dialog)
    QTest.mouseClick(controls.readers_add_button, Qt.LeftButton)

    # The application names instances by appending a counter to the class
    # name ("ChimeraReader20240501_0"), so match on prefix. Note the combo
    # box is never empty -- it shows a "No Reader" placeholder when no
    # reader exists -- so its item count says nothing about whether the add
    # succeeded.
    def real_reader_present() -> bool:
        return any(
            controls.readers_comboBox.itemText(i).startswith(READER_NAME)
            for i in range(controls.readers_comboBox.count())
        )

    qtbot.waitUntil(real_reader_present, timeout=QT_WAIT_TIMEOUT_MS)

    reader_index = next(
        i
        for i in range(controls.readers_comboBox.count())
        if controls.readers_comboBox.itemText(i).startswith(READER_NAME)
    )
    controls.readers_comboBox.setCurrentIndex(reader_index)
    reader_key = controls.readers_comboBox.currentText()

    qtbot.waitUntil(lambda: channels_have_loaded(controls), timeout=QT_WAIT_TIMEOUT_MS)
    assert select_any_channel(find_channel_combo(controls), prefer=str(ds.channel))

    return raw_view, controls, ds, reader_key


@pytest.fixture
def trace_drawn(qtbot, reader_added):
    """
    Plot the first two seconds of the selected channel.

    Waits for the new lines to appear on the figure rather than for a fixed
    delay, since reading and rendering the trace happens asynchronously.
    """
    raw_view, controls, ds, reader_key = reader_added
    controls.set_range_inputs(0, 2.0)
    qtbot.waitUntil(
        lambda: controls.update_trace_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    before = count_plot_lines(raw_view.figure)
    QTest.mouseClick(controls.update_trace_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: count_plot_lines(raw_view.figure) > before, timeout=QT_WAIT_TIMEOUT_MS
    )
    return raw_view, controls, ds, reader_key


@pytest.fixture
def eventfinder_added(qtbot, monkeypatch, trace_drawn):
    """
    Add an event finder configured to detect the dataset's planted events.

    Two things are stubbed out:

    * ``TimeWidget`` -- the dialog that asks which time ranges to analyse.
      Replaced with a stand-in that returns the dataset's full duration
      without showing anything, so the "restrict time range" button can be
      clicked without blocking.
    * ``QInputDialog.getItem`` -- returns the configured event finder class,
      patched in both locations for the reasons given in ``reader_added``.

    Detection thresholds are chosen against the dataset's known event
    amplitude: the trigger threshold sits well below the planted blockage
    depth, and the duration bounds comfortably bracket the planted event
    length, so every planted event should be found and none rejected.

    :return: ``(raw_view, controls, dataset, reader_key, finder_key)``.
    """
    raw_view, controls, ds, reader_key = trace_drawn

    import poriscope.plugins.analysistabs.RawDataView as rawdataview_mod
    import poriscope.views.widgets.time_widget as time_widget_mod

    class _FakeTimeWidget:
        """Stand-in for the time-range dialog that accepts the full recording."""

        def __init__(self, *a, **k):
            self._res = {ds.channel: {"ranges": [(0.0, ds.duration_s)]}}

        def exec(self):
            return 1

        def get_result(self):
            return self._res

    monkeypatch.setattr(time_widget_mod, "TimeWidget", _FakeTimeWidget)
    monkeypatch.setattr(rawdataview_mod, "TimeWidget", _FakeTimeWidget)

    def fake_get_item(_parent, _title, _label, items, *_a, **_k):
        for it in items:
            if FINDER_NAME in it:
                return it, True
        return (items[0] if items else "No Selection"), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )
    monkeypatch.setattr(
        "poriscope.utils.MetaView.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )

    def fill_finder_dialog(dlg) -> bool:
        """Point the finder at our reader, set detection limits, and accept."""
        ensure_name_filled(dlg, f"{FINDER_NAME}_e2e")
        widgets = getattr(dlg, "entrywidgets", {})

        for key, cb in widgets.items():
            if key.lower().replace(" ", "") in {"metareader", "reader"} and isinstance(
                cb, QtWidgets.QComboBox
            ):
                idx = cb.findText(reader_key)
                cb.setCurrentIndex(idx if idx >= 0 else 0)

        field_values = {
            "Threshold": "200.0",  # pA; planted events are 400 pA deep
            "Min Duration": "100.0",  # us; planted events are 500 us long
            "Max Duration": "1000000.0",
            "Min Separation": "10.0",
        }
        for field, value in field_values.items():
            if field in widgets and hasattr(widgets[field], "setText"):
                widgets[field].setText(value)

        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_finder_dialog)
    QTest.mouseClick(controls.eventfinders_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.eventfinders_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    finder_key = controls.eventfinders_comboBox.currentText()

    return raw_view, controls, ds, reader_key, finder_key


@pytest.fixture
def events_found(qtbot, eventfinder_added):
    """
    Run event detection over the recording and wait for it to yield results.

    Progress is observed by asking the finder plugin how many events it has
    found. The view has no direct handle on the plugin, so the question goes
    out over the application's global signal bus, which routes it to the
    plugin and writes the answer back onto the view.

    :return: ``(raw_view, controls, dataset, reader_key, finder_key)``.
    """
    raw_view, controls, ds, reader_key, finder_key = eventfinder_added

    def num_events_found() -> int:
        raw_view.global_signal.emit(
            "MetaEventFinder",
            finder_key,
            "get_num_events_found",
            (ds.channel,),
            "set_num_events_allowed",
            (),
        )
        return getattr(raw_view, "num_events_allowed", 0)

    QTest.mouseClick(controls.timer_pushButton, Qt.LeftButton)
    QTest.mouseClick(controls.find_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(lambda: num_events_found() > 0, timeout=QT_WAIT_TIMEOUT_MS)

    return raw_view, controls, ds, reader_key, finder_key


# ==========================================================================
# Tests
# ==========================================================================


@pytest.mark.e2e_ux
@pytest.mark.timeout(60)
def test_reader_and_trace(trace_drawn):
    """
    The reader loads the recording and plots the requested time window.

    Checks the plotted sample count matches what two seconds at the
    dataset's sample rate should produce, confirming the reader decoded the
    file correctly rather than merely drawing something.
    """
    raw_view, controls, ds, reader_key = trace_drawn
    lines = [ln for ax in raw_view.figure.axes for ln in ax.lines]
    assert len(lines) >= 1
    x_data, _ = lines[0].get_data()
    expected_samples = int(2.0 * ds.samplerate)
    assert len(x_data) == pytest.approx(expected_samples, rel=0.01)


@pytest.mark.e2e_ux
@pytest.mark.timeout(90)
def test_eventfinder_finds_exact_planted_count(qtbot, events_found):
    """
    Event detection finds every planted event, and no spurious extras.

    The dataset contains a known number of events, so this checks for that
    exact count -- catching both missed detections and false positives,
    which a "found at least one" check would let through.
    """
    raw_view, controls, ds, reader_key, finder_key = events_found

    def num_events_found() -> int:
        raw_view.global_signal.emit(
            "MetaEventFinder",
            finder_key,
            "get_num_events_found",
            (ds.channel,),
            "set_num_events_allowed",
            (),
        )
        return raw_view.num_events_allowed

    qtbot.waitUntil(
        lambda: num_events_found() == ds.num_events, timeout=QT_WAIT_TIMEOUT_MS
    )
    assert (
        num_events_found() == ds.num_events
    ), f"Expected exactly {ds.num_events} planted events, found {num_events_found()}"


@pytest.mark.e2e_ux
@pytest.mark.timeout(120)
def test_plot_and_navigate_events(qtbot, events_found):
    """
    Detected events can be plotted, and the navigation arrows work.

    Requests every event by index, waits for the figure to gain lines, then
    steps forward and back through the event list to confirm the arrow
    controls don't error.
    """
    raw_view, controls, ds, reader_key, finder_key = events_found

    controls.event_index_lineEdit.setText(f"0-{ds.num_events - 1}")
    before = count_plot_lines(raw_view.figure)
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: count_plot_lines(raw_view.figure) > before, timeout=QT_WAIT_TIMEOUT_MS
    )

    if hasattr(controls, "right_plot_arrow_button"):
        QTest.mouseClick(controls.right_plot_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_SHORT_PAUSE_MS)
        QTest.mouseClick(controls.left_plot_arrow_button, Qt.LeftButton)
        qtbot.wait(QT_SHORT_PAUSE_MS)


@pytest.mark.e2e_ux
@pytest.mark.timeout(150)
def test_commit_events_writes_exact_schema(qtbot, monkeypatch, tmp_path, events_found):
    """
    Committing events writes a database with the expected structure and contents.

    Adds an SQLite writer, commits the detected events, then inspects the
    resulting file directly: the three tables the writer defines are
    present, the event count matches the number planted in the dataset, and
    the channel metadata row carries the values entered in the dialog.
    """
    raw_view, controls, ds, reader_key, finder_key = events_found

    controls.event_index_lineEdit.setText(f"0-{ds.num_events - 1}")
    QTest.mouseClick(controls.plot_events_pushButton, Qt.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)

    out_db = tmp_path / "events_out.sqlite3"

    def fill_writer_dialog(dlg) -> bool:
        """
        Populate the writer settings and accept the dialog.

        The output path is set directly on the dialog's parameter dictionary
        rather than by clicking its "Select Output File" button, which would
        open a native save dialog. That button's handler normally also marks
        the path as chosen and re-runs the dialog's validation, so both are
        done here explicitly -- without the validation call the OK button
        stays disabled and the dialog can never be accepted.
        """
        widgets = getattr(dlg, "entrywidgets", {})

        if "MetaEventFinder" in widgets and isinstance(
            widgets["MetaEventFinder"], QtWidgets.QComboBox
        ):
            idx = widgets["MetaEventFinder"].findText(finder_key)
            widgets["MetaEventFinder"].setCurrentIndex(idx if idx >= 0 else 0)

        text_fields = {
            "Experiment Name": "e2e_events_test",
            "Voltage": "200.0",
            "Membrane Thickness": "10.0",
            "Conductivity": "1.0",
            "Output File": str(out_db),
        }
        for field, value in text_fields.items():
            if field in widgets and isinstance(widgets[field], QtWidgets.QLineEdit):
                widgets[field].setText(value)

        if hasattr(dlg, "params") and "Output File" in dlg.params:
            dlg.params["Output File"]["Value"] = str(out_db)
        if "Output File" in getattr(dlg, "unitwidgets", {}):
            dlg.unitwidgets["Output File"].setChecked(True)
        if hasattr(dlg, "check_validity"):
            dlg.check_validity()

        ok = find_button(dlg, "ok", exact=True)
        if ok and ok.isEnabled():
            QTest.mouseClick(ok, Qt.LeftButton)
            return True
        return False

    schedule_dialog_autofill(fill_writer_dialog)
    QTest.mouseClick(controls.writers_add_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: controls.writers_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )

    QTest.mouseClick(controls.commit_btn, Qt.LeftButton)
    # NOTE: wait for the tables, not for the file. sqlite3 creates the database
    # file the instant the writer opens it, so waiting on out_db.exists() can
    # return while the file still has zero tables - which made the assertion
    # below fail intermittently in full-suite runs and pass in isolation.
    qtbot.waitUntil(
        lambda: sqlite_has_tables(out_db, {"channels", "events", "columns"}),
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    with sqlite3.connect(out_db) as conn:
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = sorted(r[0] for r in cur.fetchall())
        expected_tables = {"channels", "events", "columns"}
        assert expected_tables.issubset(
            set(tables)
        ), f"Missing expected tables: {expected_tables - set(tables)}"

        cur.execute("SELECT COUNT(*) FROM events")
        n_rows = cur.fetchone()[0]
        assert (
            n_rows == ds.num_events
        ), f"Expected {ds.num_events} event rows, got {n_rows}"

        cur.execute("SELECT name, channel_id, voltage FROM channels")
        channel_row = cur.fetchone()
        assert channel_row == (
            "e2e_events_test",
            ds.channel,
            200.0,
        ), f"Unexpected channel metadata row: {channel_row}"
