"""
ConditioningModel: the 1 Hz noise of every PSD recording, computed per channel and kept.

The oracle is the conditioning app the tab was ported from: its ``process_psd_folder`` was run
on the same synthetic experiment and its 1 Hz values saved as
``tests/synthetic_data/conditioning_original_app_goldens.json``, for two settings. The app
read the recordings in V and scaled their PSD by the sensitivity squared; Poriscope reads them
in pA, so the two agree to rounding, not bit for bit.

What the app got wrong is pinned the other way: it kept values keyed only by the folder, so a
changed sensitivity redrew stale noise.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

from poriscope.plugins.analysistabs.ConditioningModel import ConditioningModel
from poriscope.plugins.conditioningloaders.NIConditioningLoader import (
    NIConditioningLoader,
)
from tests.synthetic_data.synthetic_ni import (
    ConditioningDataset,
    generate_conditioning_folder,
)

GOLDENS = json.loads(
    (
        Path(__file__).parents[2]
        / "synthetic_data"
        / "conditioning_original_app_goldens.json"
    ).read_text(encoding="utf-8")
)

KEY = "Experiment"


def _loader(root: Path, **values: Any) -> NIConditioningLoader:
    loader = NIConditioningLoader(key=KEY)
    settings = loader.get_empty_settings(standalone=True)
    settings["Folder"]["Value"] = str(root)
    settings["PSD Every N Cycles"]["Value"] = 2
    for key, value in values.items():
        settings[key]["Value"] = value
    loader.apply_settings(settings)
    return loader


def _model(loader: NIConditioningLoader) -> ConditioningModel:
    model = ConditioningModel()
    model.set_plugin_instances({"MetaConditioningLoader": {KEY: loader}})
    model.update_available_plugins({"MetaConditioningLoader": [KEY]})
    model.forget_stale_results(KEY)
    return model


def _run(
    model: ConditioningModel, channels: List[int], fit: tuple = (1.0, 30.0)
) -> List[float]:
    progress: List[float] = []
    for channel in channels:
        progress.extend(model.one_hz_run(KEY, channel, *fit))
    return progress


@pytest.fixture
def experiment(tmp_path: Path) -> ConditioningDataset:
    return generate_conditioning_folder(tmp_path / "exp")


@pytest.mark.parametrize(
    "case", ["default", "sensitivity_2000_fit_2_20"], ids=["default", "changed"]
)
def test_one_hz_noise_matches_the_original_app(
    experiment: ConditioningDataset, case: str
) -> None:
    golden: Dict[str, Any] = GOLDENS[case]
    model = _model(_loader(experiment.root, Sensitivity=golden["sensitivity"]))
    fit = (golden["fit_start"], golden["fit_end"])
    channels = list(range(16))
    _run(model, channels, fit)
    data = model.plot_data(KEY, channels, *fit)
    for entry in data:
        channel = entry["channel"]
        for polarity, name in (("+", "Pos"), ("-", "Neg")):
            result = entry["psd"][polarity]
            assert result["cycles"].tolist() == golden[name]["cycles"]
            expected = [row[channel] for row in golden[name]["one_hz"]]
            np.testing.assert_allclose(result["one_hz"], expected, rtol=1e-9)


def test_progress_rises_to_one_over_every_recording(
    experiment: ConditioningDataset,
) -> None:
    model = _model(_loader(experiment.root))
    progress = _run(model, [5])
    assert progress == pytest.approx([i / 6 for i in range(1, 7)])


def test_only_uncomputed_channels_are_missing(
    experiment: ConditioningDataset,
) -> None:
    model = _model(_loader(experiment.root))
    _run(model, [4, 6])
    assert model.missing_channels(KEY, [4, 5, 6], 1.0, 30.0) == [5]
    assert model.missing_channels(KEY, [4], 2.0, 30.0) == [4]


def test_a_stopped_run_keeps_nothing(experiment: ConditioningDataset) -> None:
    model = _model(_loader(experiment.root))
    run = model.one_hz_run(KEY, 7, 1.0, 30.0)
    next(run)
    with pytest.raises(StopIteration):
        run.send(True)
    assert model.missing_channels(KEY, [7], 1.0, 30.0) == [7]


def test_changed_experiment_settings_drop_what_was_kept(
    experiment: ConditioningDataset,
) -> None:
    model = _model(_loader(experiment.root))
    _run(model, [8])
    model.forget_stale_results(KEY)
    assert model.missing_channels(KEY, [8], 1.0, 30.0) == []
    model.set_plugin_instances(
        {"MetaConditioningLoader": {KEY: _loader(experiment.root, Sensitivity=500.0)}}
    )
    model.forget_stale_results(KEY)
    assert model.missing_channels(KEY, [8], 1.0, 30.0) == [8]


def test_a_short_recording_is_noted_once(experiment: ConditioningDataset) -> None:
    model = _model(_loader(experiment.root))
    _run(model, [4, 5])
    notes = model.take_notes(KEY)
    assert notes == [
        "PSD- at cycle 4 has 1500 samples, fewer than its 2000 points per average, "
        "so its PSD is one shorter segment"
    ]
    assert model.take_notes(KEY) == []


def test_a_fit_range_without_two_bins_names_the_recording(
    experiment: ConditioningDataset,
) -> None:
    model = _model(_loader(experiment.root))
    with pytest.raises(ValueError, match=r"PSD\+ at cycle 2: 0 frequency bins"):
        _run(model, [4], (1.0, 4.0))


def test_plot_data_marks_unmeasured_channels_disabled(
    experiment: ConditioningDataset,
) -> None:
    model = _model(_loader(experiment.root))
    data = model.plot_data(KEY, [2, 9], 1.0, 30.0)
    assert [entry["disabled"] for entry in data] == [True, False]
    assert data[1]["psd"] == {}
    np.testing.assert_array_equal(data[1]["measured"], experiment.measured[:, 9])
