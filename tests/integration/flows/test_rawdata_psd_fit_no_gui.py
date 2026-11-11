"""
Raw Data's Update PSD with a segment length, an overlap and a 1/f fit.

The fit and its 1 Hz value are the conditioning app's single-file PSD view, ported: a straight
line through log PSD against log frequency over the fit range, read off at 1 Hz, drawn over the
PSD with the panel shaded green, orange or red by that value. Every new value of the recorded
``update_psd`` has a default that reproduces the PSD Raw Data always drew, so an entry saved
before they existed replays unchanged.

The recording is an NI binary file read with NIBinaryReader, the reader the port added for it.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest
from scipy.signal import welch

from poriscope.plugins.datareaders.NIBinaryReader import NIBinaryReader
from tests.integration.flows._triad import Triad, build_triad, named
from tests.synthetic_data.synthetic_ni import (
    NI_CHANNELS,
    ni_file_name,
    noise_mv,
    write_ni_binary,
)

READER = "ni"
SAMPLERATE = 1_000
POINTS = 2_000
DURATION = POINTS / SAMPLERATE


@pytest.fixture
def recording(tmp_path: Path) -> Dict[str, Any]:
    data = noise_mv(POINTS, SAMPLERATE, np.random.default_rng(5), NI_CHANNELS)
    path = tmp_path / ni_file_name(
        "TS1", POINTS, 1, SAMPLERATE, datetime(2026, 11, 10, 15, 40)
    )
    write_ni_binary(path, data)
    return {"path": path, "data": data}


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, recording: Dict[str, Any]) -> Triad:
    triad = build_triad("RawDataController", tmp_path)
    reader = NIBinaryReader()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(recording["path"])
    reader.apply_settings(settings)
    triad.register(reader, "MetaReader", READER)
    yield triad
    triad.close()


@pytest.fixture
def panel(tab: Triad) -> List[str]:
    messages: List[str] = []
    tab.tab_controller.add_text_to_display.connect(
        lambda text, _source: messages.append(text)
    )
    return messages


def _fit_lines(tab: Triad) -> List[Any]:
    return [
        line
        for ax in tab.tab_view.figure.axes
        for line in ax.get_lines()
        if "1 Hz" in str(line.get_label())
    ]


def test_the_fit_is_drawn_with_its_1hz_value_and_shading(
    tab: Triad, recording: Dict[str, Any], panel: List[str]
) -> None:
    drawn = tab.tab_controller.load_psd_data(
        READER,
        [3, 12],
        0.0,
        DURATION,
        "",
        segment_length=POINTS,
        overlap=0.0,
        fit=True,
        fit_start=1.0,
        fit_end=30.0,
        good_noise=1e-3,
        decent_noise=1e9,
    )
    assert drawn is True
    lines = _fit_lines(tab)
    assert len(lines) == 2
    for channel, line in zip([3, 12], lines):
        frequency, psd = welch(
            recording["data"][:, channel],
            fs=SAMPLERATE,
            window="hann",
            nperseg=POINTS,
            noverlap=0,
        )
        mask = (frequency >= 1.0) & (frequency <= 30.0)
        _, intercept = np.polyfit(
            np.log10(frequency[mask]), np.log10(psd[mask] + 1e-60), 1
        )
        assert f"{10**intercept:.4g}" in line.get_label()
        assert any(f"Channel {channel}" in text and "1 Hz" in text for text in panel)
    # Between Good and Decent, so every panel is shaded orange.
    for line in lines:
        assert line.axes.get_facecolor() == pytest.approx((1.0, 0.6, 0.0, 0.15))


def test_without_the_fit_the_psd_is_what_raw_data_always_drew(
    tab: Triad, recording: Dict[str, Any]
) -> None:
    assert tab.tab_controller.load_psd_data(READER, [5], 0.0, DURATION, "") is True
    assert _fit_lines(tab) == []
    _, expected = welch(recording["data"][:, 5], SAMPLERATE, nperseg=POINTS // 10)
    np.testing.assert_array_equal(tab.tab_view.Pxx_list[0], expected)


def test_a_segment_length_and_overlap_set_the_welch_segments(
    tab: Triad, recording: Dict[str, Any]
) -> None:
    tab.tab_controller.load_psd_data(
        READER, [5], 0.0, DURATION, "", segment_length=500, overlap=25.0
    )
    _, expected = welch(
        recording["data"][:, 5], fs=SAMPLERATE, nperseg=500, noverlap=125
    )
    np.testing.assert_array_equal(tab.tab_view.Pxx_list[0], expected)


def test_a_fit_range_out_of_order_is_refused_and_not_recorded(
    tab: Triad, panel: List[str]
) -> None:
    before = dict(tab.tab_controller.tab_action_history)
    drawn = tab.tab_controller.load_psd_data(
        READER, [5], 0.0, DURATION, "", fit=True, fit_start=30.0, fit_end=1.0
    )
    assert drawn is False
    assert tab.tab_controller.tab_action_history == before
    assert any("fit range" in text for text in panel)


def test_an_entry_saved_before_the_new_values_still_replays(tab: Triad) -> None:
    old = {
        "action": "update_psd",
        "args": [],
        "kwargs": {
            "reader": READER,
            "channels": [2],
            "start": 0.0,
            "length": DURATION,
            "data_filter": "",
        },
    }
    resolved = tab.tab_controller.resolve_replayed_entry(old)
    assert resolved is not None
    method, args, kwargs = resolved
    assert method(*args, **kwargs) is True
    assert _fit_lines(tab) == []


def test_the_new_values_are_written_back_to_the_panel(tab: Triad) -> None:
    values = named(
        tab, "update_psd", READER, [2], 0.0, DURATION, "", 500, 10.0, True, 2.0, 20.0
    )
    tab.tab_view.write_back("update_psd", (), values)
    options = tab.tab_view.rawdatacontrols.psd_options
    assert options == {
        "segment_length": 500,
        "overlap": 10.0,
        "fit": True,
        "fit_start": 2.0,
        "fit_end": 20.0,
        "good_noise": 10.0,
        "decent_noise": 100.0,
    }


def test_the_panels_defaults_are_the_recorded_methods_defaults(tab: Triad) -> None:
    defaults = named(tab, "update_psd", READER, [2], 0.0, DURATION, "")
    panel = tab.tab_view.rawdatacontrols.PSD_OPTION_DEFAULTS
    assert {name: defaults[name] for name in panel} == panel
