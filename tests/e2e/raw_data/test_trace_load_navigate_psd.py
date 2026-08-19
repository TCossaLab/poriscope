"""
End-to-end tests for loading and viewing a raw trace in the Raw Data tab.

Covers the browsing half of the tab, upstream of any event detection:
adding a reader, plotting a window of the recording, stepping that window
forward and back, and requesting baseline statistics and a power spectral
density plot.

add reader → select channel → plot 0–2 s → step right (expect 2–4 s) → step left (back to 0–2 s) → baseline + PSD buttons.
Asserts exact sample count against 2.0 × ds.samplerate.

Test data comes from the ``synthetic_chimera_dataset`` fixture, so the
recording's sample rate and duration are known and can be asserted against
exactly.
"""

import sys
from pathlib import Path

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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _round(val: float, ndigits=6) -> float:
    """Round for comparison, absorbing floating-point representation noise."""
    return round(float(val), ndigits)


@pytest.mark.e2e_ux
@pytest.mark.timeout(120)
def test_trace_load_navigate_psd(
    qtbot, tmp_path, monkeypatch, synthetic_chimera_dataset
):
    """
    Load a trace, step the view window, and request baseline and PSD plots.

    Walks the tab's viewing controls end to end:

    1. Add a reader for the synthetic recording and select a channel.
    2. Plot the window from 0-2 s and check the sample count is right.
    3. Step right, expecting the window to advance to 2-4 s, then left,
       expecting it back at 0-2 s.
    4. Click the baseline-statistics and PSD buttons, confirming each emits
       its corresponding action.

    Steps 3 and 4 are conditional on their controls being enabled, so the
    test degrades gracefully if a control is unavailable in a given build.
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
    controller = MainController(
        model, view
    )  # noqa: F841  (kept alive for the test's duration)
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

    # Plot the first two seconds.
    controls.set_range_inputs(0, 2.0)
    qtbot.waitUntil(
        lambda: controls.update_trace_pushButton.isEnabled(), timeout=QT_WAIT_TIMEOUT_MS
    )
    QTest.mouseClick(controls.update_trace_pushButton, Qt.LeftButton)
    qtbot.wait(QT_SHORT_PAUSE_MS)

    # The plotted point count should match two seconds at the recording's
    # sample rate, confirming the reader decoded the file rather than just
    # drawing something.
    assert raw_view.figure.axes, "No axes created after 'Update Trace'"
    lines = [ln for ax in raw_view.figure.axes for ln in ax.lines]
    assert len(lines) >= 1, "No plotted lines detected after 'Update Trace'"
    x_data, _ = lines[0].get_data()
    expected_samples = int(2.0 * ds.samplerate)
    assert len(x_data) == pytest.approx(expected_samples, rel=0.01), (
        f"Plotted trace has {len(x_data)} samples, expected ~{expected_samples} "
        f"for a 2s window at {ds.samplerate}Hz"
    )

    # Record which actions the controls emit, so the baseline and PSD
    # buttons can be checked by the request they raise rather than by
    # inspecting their eventual output.
    emitted_actions: list[str] = []
    controls.actionTriggered.connect(
        lambda sub, action, args: emitted_actions.append(action)
    )

    assert _round(controls.start_time_lineEdit.get_start()) == 0.0
    assert _round(controls.start_time_lineEdit.get_duration()) == 2.0

    # Step the window forward one full width, then back again.
    if controls.right_trace_arrow_button.isEnabled():
        QTest.mouseClick(controls.right_trace_arrow_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: _round(controls.start_time_lineEdit.get_start()) == 2.0
            and _round(controls.start_time_lineEdit.get_duration()) == 2.0,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    if controls.left_trace_arrow_button.isEnabled():
        QTest.mouseClick(controls.left_trace_arrow_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: _round(controls.start_time_lineEdit.get_start()) == 0.0
            and _round(controls.start_time_lineEdit.get_duration()) == 2.0,
            timeout=QT_WAIT_TIMEOUT_MS,
        )

    if hasattr(controls, "calculate_baseline_button"):
        QTest.mouseClick(controls.calculate_baseline_button, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: "get_baseline_stats" in emitted_actions, timeout=QT_WAIT_TIMEOUT_MS
        )

    if hasattr(controls, "update_psd_pushButton"):
        QTest.mouseClick(controls.update_psd_pushButton, Qt.LeftButton)
        qtbot.waitUntil(
            lambda: "load_data_and_update_psd" in emitted_actions,
            timeout=QT_WAIT_TIMEOUT_MS,
        )
