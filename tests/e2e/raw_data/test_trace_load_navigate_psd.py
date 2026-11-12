"""
End-to-end tests for loading and viewing a raw trace in the Raw Data tab.

Covers the browsing half of the tab, upstream of any event detection:
adding a reader, plotting a window of the recording, stepping that window
forward and back, and requesting baseline statistics and a power spectral
density plot.

add reader → select channel → plot 0–0.5 s → step right (expect 0.5–1 s) → step left (back to 0–0.5 s) → baseline + PSD buttons.
Asserts exact sample count against WINDOW_S × ds.samplerate. The window is a
quarter of the two-second recording, so a step right still lands inside it.

Test data comes from the ``synthetic_chimera_dataset`` fixture, so the
recording's sample rate and duration are known and can be asserted against
exactly.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from poriscope.controllers.main_controller import MainController
from poriscope.models.main_model import MainModel
from poriscope.views.main_view import MainView
from tests.e2e._helpers import (
    QT_SHORT_PAUSE_MS,
    QT_WAIT_TIMEOUT_MS,
    READER_NAME,
    channels_have_loaded,
    ensure_name_filled,
    find_button,
    find_channel_combo,
    open_menu_hybrid,
    schedule_dialog_autofill,
    select_any_channel,
)

# A step right must stay inside the two-second recording, or there is nothing to redraw.
WINDOW_S = 0.5


def _round(val: float, ndigits=6) -> float:
    """Round for comparison, absorbing floating-point representation noise."""
    return round(float(val), ndigits)


def _trace_lines(raw_view) -> list:
    """Every line on the trace figure; the trace itself is drawn first."""
    return [ln for ax in raw_view.figure.axes for ln in ax.lines]


def _plotted_start(raw_view) -> float:
    """
    The time of the first plotted sample, or NaN while nothing is plotted.

    The trace's time axis is seconds from the start of the recording, so this is
    the window's start as drawn - it moves only when the figure is redrawn.
    """
    lines = _trace_lines(raw_view)
    return float(lines[0].get_xdata()[0]) if lines else float("nan")


@pytest.mark.e2e_ux
@pytest.mark.timeout(120)
def test_trace_load_navigate_psd(
    qtbot, tmp_path, monkeypatch, synthetic_chimera_dataset
):
    """
    Load a trace, step the view window, and request baseline and PSD plots.

    Walks the tab's viewing controls end to end:

    1. Add a reader for the synthetic recording and select a channel.
    2. Plot the window from 0-0.5 s and check the sample count is right.
    3. Step right, expecting the window to advance to 0.5-1 s, then left,
       expecting it back at 0-0.5 s.
    4. Click the baseline-statistics and PSD buttons, confirming each emits
       its corresponding action.

    Each arrow must be enabled once a trace is plotted, and each step waits
    for the figure to be redrawn at the new window, not only for the range
    fields to change.
    """
    ds = synthetic_chimera_dataset

    # Replace the reader-subclass picker and the file browser with automatic
    # responses. Each is patched both at its source module and at the module
    # that imported the name directly, since the latter holds its own
    # reference that a source-only patch would not reach.
    def fake_get_item(parent, title, label, items, current=0, editable=False):
        for text in items:
            if READER_NAME in text:
                return text, True
        return (items[0] if items else READER_NAME), True

    monkeypatch.setattr(
        "PySide6.QtWidgets.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=False,
    )
    monkeypatch.setattr(
        "poriscope.utils.MetaView.QInputDialog.getItem",
        staticmethod(fake_get_item),
        raising=True,
    )
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(ds.data_path), "All Files (*)")),
        raising=False,
    )
    monkeypatch.setattr(
        "poriscope.views.widgets.dict_dialog_widget.QFileDialog.getOpenFileName",
        staticmethod(lambda *_a, **_k: (str(ds.data_path), "All Files (*)")),
        raising=True,
    )

    # Launch the application against a throwaway config in tmp_path.
    model = MainModel(
        {
            "Parent Folder": str(tmp_path),
            "User Plugin Folder": str(tmp_path),
            "Log Level": 20,
        }
    )
    view = MainView(model.get_available_plugins())
    _controller = MainController(model, view)  # kept alive for the test's duration
    qtbot.addWidget(view)
    view.show()

    open_menu_hybrid(view, ["Analysis", "New Analysis Tab", "RawDataController"], qtbot)
    qtbot.waitUntil(lambda: "RawDataView" in view.pages, timeout=QT_WAIT_TIMEOUT_MS)
    view.switch_to_page("RawDataView")
    raw_view = view.pages["RawDataView"]["widget"]
    controls = raw_view.rawdatacontrols

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

    qtbot.waitUntil(
        lambda: controls.readers_comboBox.count() > 0, timeout=QT_WAIT_TIMEOUT_MS
    )
    idx = controls.readers_comboBox.findText(READER_NAME)
    controls.readers_comboBox.setCurrentIndex(idx if idx >= 0 else 0)

    # Selecting a reader kicks off an asynchronous fetch of its channels.
    qtbot.waitUntil(lambda: channels_have_loaded(controls), timeout=QT_WAIT_TIMEOUT_MS)
    chan_cb = find_channel_combo(controls)
    assert select_any_channel(
        chan_cb, prefer=str(ds.channel)
    ), "No channel options available"

    # Plot the first window.
    controls.set_range_inputs(0, WINDOW_S)
    qtbot.waitUntil(
        lambda: controls.update_trace_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    # Nothing is plotted on a new tab, so any line is this click's trace.
    assert not _trace_lines(raw_view), "the figure held lines before 'Update Trace'"
    QTest.mouseClick(controls.update_trace_pushButton, Qt.LeftButton)
    qtbot.waitUntil(lambda: bool(_trace_lines(raw_view)), timeout=QT_WAIT_TIMEOUT_MS)

    # The plotted point count should match the window at the recording's
    # sample rate, confirming the reader decoded the file rather than just
    # drawing something.
    x_data, _ = _trace_lines(raw_view)[0].get_data()
    expected_samples = int(WINDOW_S * ds.samplerate)
    assert len(x_data) == pytest.approx(expected_samples, rel=0.01), (
        f"Plotted trace has {len(x_data)} samples, expected ~{expected_samples} "
        f"for a {WINDOW_S}s window at {ds.samplerate}Hz"
    )

    # Record which actions the controls emit, so the baseline and PSD
    # buttons can be checked by the request they raise rather than by
    # inspecting their eventual output.
    emitted_actions: list[str] = []
    controls.actionTriggered.connect(
        lambda sub, action, args: emitted_actions.append(action)
    )

    assert _round(controls.start_time_lineEdit.get_start()) == 0.0
    assert _round(controls.start_time_lineEdit.get_duration()) == WINDOW_S

    # Step the window forward one full width, then back again. The range fields
    # change before the redraw, so each step also waits for the trace itself to
    # start at the new window.
    one_sample = 1.0 / ds.samplerate
    assert controls.right_trace_arrow_button.isEnabled(), "right arrow disabled"
    QTest.mouseClick(controls.right_trace_arrow_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _round(controls.start_time_lineEdit.get_start()) == WINDOW_S
        and _round(controls.start_time_lineEdit.get_duration()) == WINDOW_S
        and abs(_plotted_start(raw_view) - WINDOW_S) < one_sample,
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    assert controls.left_trace_arrow_button.isEnabled(), "left arrow disabled"
    QTest.mouseClick(controls.left_trace_arrow_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: _round(controls.start_time_lineEdit.get_start()) == 0.0
        and _round(controls.start_time_lineEdit.get_duration()) == WINDOW_S
        and abs(_plotted_start(raw_view)) < one_sample,
        timeout=QT_WAIT_TIMEOUT_MS,
    )

    QTest.mouseClick(controls.calculate_baseline_button, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: "get_baseline_stats" in emitted_actions, timeout=QT_WAIT_TIMEOUT_MS
    )

    QTest.mouseClick(controls.update_psd_pushButton, Qt.LeftButton)
    qtbot.waitUntil(
        lambda: "load_data_and_update_psd" in emitted_actions,
        timeout=QT_WAIT_TIMEOUT_MS,
    )
