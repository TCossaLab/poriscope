"""
The Conditioning tab end to end: an experiment registered, a plot computed on worker threads,
drawn, recorded, redrawn from what was kept, and written back.

The tab is the conditioning app's main view, ported. A plot computes each channel's 1 Hz
noise at every PSD recording in the background - the slow part - and draws when the last
worker ends; a second plot of the same experiment and fit range draws at once. Two of the
app's defects are pinned here the other way round: its noise bands were placed by cycle index,
so with a PSD every second cycle they landed on the wrong cycles, and its cache ignored every
setting but the folder.
"""

from pathlib import Path
from typing import Any, List

import pytest

from poriscope.plugins.conditioningloaders.NIConditioningLoader import (
    NIConditioningLoader,
)
from tests.integration.flows._triad import Triad, build_triad, named
from tests.synthetic_data.synthetic_ni import (
    ConditioningDataset,
    generate_conditioning_folder,
)

LOADER = "experiment"
GREEN = (0.0, 0.8, 0.0, 0.15)


def _loader(root: Path, **values: Any) -> NIConditioningLoader:
    loader = NIConditioningLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Folder"]["Value"] = str(root)
    settings["PSD Every N Cycles"]["Value"] = 2
    for key, value in values.items():
        settings[key]["Value"] = value
    loader.apply_settings(settings)
    return loader


@pytest.fixture
def experiment(tmp_path: Path) -> ConditioningDataset:
    return generate_conditioning_folder(tmp_path / "exp")


@pytest.fixture
def tab(qapp: Any, tmp_path: Path, experiment: ConditioningDataset) -> Triad:
    triad = build_triad("ConditioningController", tmp_path)
    triad.register(_loader(experiment.root), "MetaConditioningLoader", LOADER)
    yield triad
    triad.close()


@pytest.fixture
def panel(tab: Triad) -> List[str]:
    messages: List[str] = []
    tab.tab_controller.add_text_to_display.connect(
        lambda text, _source: messages.append(text)
    )
    return messages


def _plot(tab: Triad, channels: List[int], **changes: Any) -> bool:
    values = {
        "fit_start": 1.0,
        "fit_end": 30.0,
        "good_noise": 1e9,
        "decent_noise": 2e9,
        "psd_axis_min": 1e-4,
        "show_bands": True,
    }
    values.update(changes)
    return tab.tab_controller.plot_conditioning(LOADER, channels, **values)


def _titles(tab: Triad) -> List[str]:
    return [ax.get_title() for ax in tab.tab_view.figure.axes if ax.get_title()]


def _drawn(qtbot: Any, tab: Triad, count: int) -> None:
    qtbot.waitUntil(lambda: len(_titles(tab)) == count, timeout=60_000)


def test_the_experiment_and_its_channels_reach_the_panel(tab: Triad) -> None:
    controls = tab.tab_view.conditioningcontrols
    assert controls.loader_comboBox.currentText() == LOADER
    assert controls.channel_comboBox.getSelectedItems() == [str(c) for c in range(16)]


def test_a_plot_computes_in_the_background_then_draws_every_channel(
    qtbot: Any, tab: Triad, panel: List[str]
) -> None:
    assert _plot(tab, [2, 5, 9]) is True
    _drawn(qtbot, tab, 3)
    assert _titles(tab) == ["Channel 2 (disabled)", "Channel 5", "Channel 9"]
    assert any("Computing the 1 Hz noise of 3 channel(s)" in t for t in panel)
    assert any("PSD- at cycle 4 has 1500 samples" in t for t in panel)
    history = [entry["action"] for entry in tab.tab_controller.kept_actions()]
    assert history == ["plot_conditioning"]


def test_bands_sit_on_each_psd_recordings_own_cycle(qtbot: Any, tab: Triad) -> None:
    _plot(tab, [5])
    _drawn(qtbot, tab, 1)
    pore_axes = next(ax for ax in tab.tab_view.figure.axes if ax.get_title())
    bands = [p for p in pore_axes.patches if p.get_facecolor() == pytest.approx(GREEN)]
    centres = sorted(
        {round(p.get_x() + p.get_width() / 2, 6) for p in bands}  # type: ignore[attr-defined]
    )
    assert centres == [2.0, 4.0, 6.0]
    assert len(bands) == 6


def test_a_second_plot_of_the_same_values_draws_without_computing(
    qtbot: Any, tab: Triad, panel: List[str]
) -> None:
    _plot(tab, [5, 6])
    _drawn(qtbot, tab, 2)
    panel.clear()
    assert _plot(tab, [6], good_noise=1.0, decent_noise=2.0) is True
    assert _titles(tab) == ["Channel 6"]
    assert not any("Computing" in text for text in panel)


def test_editing_the_experiment_recomputes(
    qtbot: Any, tab: Triad, experiment: ConditioningDataset, panel: List[str]
) -> None:
    _plot(tab, [5])
    _drawn(qtbot, tab, 1)
    # An edit applies the new settings to the registered instance.
    loader = tab.controller.data_plugin_controller.model.get_plugin_instance(
        "MetaConditioningLoader", LOADER
    )
    settings = loader.get_empty_settings(standalone=True)
    settings["Folder"]["Value"] = str(experiment.root)
    settings["PSD Every N Cycles"]["Value"] = 2
    settings["Sensitivity"]["Value"] = 10.0
    loader.apply_settings(settings)
    panel.clear()
    _plot(tab, [5])
    assert any("Computing the 1 Hz noise of 1 channel(s)" in t for t in panel)
    _drawn(qtbot, tab, 1)


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"fit_start": 30.0, "fit_end": 1.0}, "fit range"),
        ({"good_noise": 100.0, "decent_noise": 10.0}, "thresholds"),
        ({"psd_axis_min": 0.0}, "axis minimum"),
    ],
)
def test_out_of_order_values_are_refused_and_not_recorded(
    tab: Triad, panel: List[str], changes: Any, reason: str
) -> None:
    assert _plot(tab, [5], **changes) is False
    assert tab.tab_controller.kept_actions() == []
    assert any(reason in text for text in panel)


def test_an_unknown_experiment_is_refused(tab: Triad, panel: List[str]) -> None:
    assert (
        tab.tab_controller.plot_conditioning(
            "nope", [1], 1.0, 30.0, 1.0, 2.0, 1e-4, True
        )
        is False
    )
    assert any("conditioning experiment" in text for text in panel)


def test_a_recorded_plot_is_written_back_to_the_panel(tab: Triad) -> None:
    values = named(
        tab, "plot_conditioning", LOADER, [4, 7], 2.0, 20.0, 5.0, 50.0, 1e-3, False
    )
    tab.tab_view.write_back("plot_conditioning", (), values)
    controls = tab.tab_view.conditioningcontrols
    assert controls.channel_comboBox.getSelectedItems() == ["4", "7"]
    parameters = {name: float(f.text()) for name, f in controls.numeric.items()}
    assert parameters == {
        "fit_start": 2.0,
        "fit_end": 20.0,
        "good_noise": 5.0,
        "decent_noise": 50.0,
        "psd_axis_min": 1e-3,
    }
    assert controls.bands_checkBox.isChecked() is False


def test_export_holds_the_plotted_values(qtbot: Any, tab: Triad) -> None:
    _plot(tab, [5])
    _drawn(qtbot, tab, 1)
    labels = tab.tab_controller.model.cache_labels
    assert "Channel 5 Pore Size (nm)" in labels
    assert "Channel 5 PSD+ 1 Hz Noise (pA^2/Hz)" in labels
    assert "Channel 5 PSD- 1 Hz Noise (pA^2/Hz)" in labels
