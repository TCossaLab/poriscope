"""
NIConditioningLoader: a LabVIEW / NI DAQ conditioning experiment folder, read through the
MetaConditioningLoader API.

The ground truth is what ``tests/synthetic_data/synthetic_ni.py`` wrote into the folder, and,
for the pore sizes, what the conditioning app this was ported from reads out of the same
folder (``conditioning_original_app_goldens.json``, captured from its ``read_csv``). Several
CSVs are read as one, in the order of the stamps in their names; each PSD recording is read
by an NIBinaryReader the loader owns, so its samples come back in pA.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from poriscope.plugins.conditioningloaders.NIConditioningLoader import (
    NIConditioningLoader,
)
from tests.synthetic_data.synthetic_ni import (
    ConditioningDataset,
    generate_conditioning_folder,
)

GOLDENS = json.loads(
    (
        Path(__file__).parents[3]
        / "synthetic_data"
        / "conditioning_original_app_goldens.json"
    ).read_text(encoding="utf-8")
)


def _loader(root: Path, **values: Any) -> NIConditioningLoader:
    loader = NIConditioningLoader()
    settings = loader.get_empty_settings(standalone=True)
    settings["Folder"]["Value"] = str(root)
    for key, value in values.items():
        settings[key]["Value"] = value
    loader.apply_settings(settings)
    return loader


@pytest.fixture
def experiment(tmp_path: Path) -> ConditioningDataset:
    return generate_conditioning_folder(tmp_path / "exp")


@pytest.fixture
def loader(experiment: ConditioningDataset) -> NIConditioningLoader:
    return _loader(experiment.root, **{"PSD Every N Cycles": experiment.psd_every_n})


class TestPoreSizes:
    def test_cycles_count_from_one(
        self, loader: NIConditioningLoader, experiment: ConditioningDataset
    ) -> None:
        np.testing.assert_array_equal(
            loader.get_cycles(), np.arange(1, experiment.cycles + 1)
        )
        assert loader.get_cycles().tolist() == GOLDENS["cycles"]

    def test_channels_count_from_zero(self, loader: NIConditioningLoader) -> None:
        assert loader.get_channels() == list(range(16))

    def test_pore_sizes_match_the_original_app(
        self, loader: NIConditioningLoader
    ) -> None:
        for channel in loader.get_channels():
            sizes = loader.get_pore_sizes(channel)
            for name in ("measured", "max_target", "min_target"):
                expected = [row[channel] for row in GOLDENS[name]]
                np.testing.assert_array_equal(sizes[name], expected)

    def test_a_caller_cannot_change_the_kept_sizes(
        self, loader: NIConditioningLoader
    ) -> None:
        loader.get_pore_sizes(5)["measured"][:] = -1.0
        assert (loader.get_pore_sizes(5)["measured"] > 0).all()

    def test_several_csvs_are_joined_in_the_order_of_their_stamps(
        self, tmp_path: Path, experiment: ConditioningDataset
    ) -> None:
        # The later file sorts first by name, so only the stamps give the right order.
        split = generate_conditioning_folder(
            tmp_path / "split",
            csv_split=(("B_Cond", "20261110_100000"), ("A_Cond", "20261110_120000")),
        )
        loader = _loader(split.root)
        for channel in (4, 15):
            np.testing.assert_array_equal(
                loader.get_pore_sizes(channel)["measured"],
                experiment.measured[:, channel],
            )

    def test_several_csvs_without_stamps_are_refused_by_name(
        self, tmp_path: Path
    ) -> None:
        split = generate_conditioning_folder(
            tmp_path / "split",
            csv_split=(("first", "a"), ("second", "b")),
        )
        with pytest.raises(ValueError, match="first_a.csv, second_b.csv"):
            _loader(split.root)

    def test_a_tab_separated_csv_is_read(self, tmp_path: Path) -> None:
        tabbed = generate_conditioning_folder(tmp_path / "tabbed", sep="\t")
        loader = _loader(tabbed.root)
        np.testing.assert_array_equal(
            loader.get_pore_sizes(6)["measured"], tabbed.measured[:, 6]
        )

    def test_a_csv_with_the_wrong_column_count_is_refused(
        self, experiment: ConditioningDataset
    ) -> None:
        with pytest.raises(ValueError, match="12 channels need 36"):
            _loader(experiment.root, **{"Number of Channels": 12})

    def test_a_folder_that_is_not_an_experiment_is_refused(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match="no 'Conditioning' folder"):
            _loader(tmp_path)


class TestPsdRecordings:
    def test_both_polarities_are_found_with_their_cycles(
        self, loader: NIConditioningLoader, experiment: ConditioningDataset
    ) -> None:
        assert loader.get_psd_polarities() == ["+", "-"]
        for polarity, name in (("+", "Pos"), ("-", "Neg")):
            count = loader.get_psd_segment_count(polarity)
            assert count == len(experiment.psd[name].paths)
            cycles = [loader.get_psd_cycle(polarity, i) for i in range(count)]
            assert cycles == GOLDENS["default"][name]["cycles"]

    def test_rate_and_points_come_from_each_file_name(
        self, loader: NIConditioningLoader, experiment: ConditioningDataset
    ) -> None:
        for polarity, name in (("+", "Pos"), ("-", "Neg")):
            series = experiment.psd[name]
            assert loader.get_psd_samplerate(polarity, 0) == series.samplerate
            assert loader.get_psd_points_per_average(polarity, 0) == series.points

    def test_typed_rate_and_points_override_the_file_names(
        self, experiment: ConditioningDataset
    ) -> None:
        loader = _loader(
            experiment.root, **{"Sampling Rate": 5_000.0, "Points per Average": 500}
        )
        assert loader.get_psd_samplerate("-", 2) == 5_000.0
        assert loader.get_psd_points_per_average("+", 1) == 500

    def test_each_recording_reads_back_in_pa(
        self, experiment: ConditioningDataset
    ) -> None:
        loader = _loader(experiment.root, Sensitivity=2000.0)
        for polarity, name in (("+", "Pos"), ("-", "Neg")):
            for index, data in enumerate(experiment.psd[name].data_mv):
                for channel in (0, 9, 15):
                    np.testing.assert_allclose(
                        loader.load_psd_segment(polarity, index, channel),
                        data[:, channel] * 2.0,
                        rtol=1e-15,
                    )

    def test_a_short_recording_reads_its_own_length_and_is_reported_by_name(
        self, loader: NIConditioningLoader, experiment: ConditioningDataset
    ) -> None:
        assert len(loader.load_psd_segment("-", 1, 3)) == 1_500
        report = loader.report_status(init=True)
        short = experiment.psd["Neg"].paths[1].name
        assert f"PSD- recording {short} (cycle 4) has 1500 samples" in report
        assert "PSD+ recording" not in report

    def test_a_missing_polarity_is_left_out(self, tmp_path: Path) -> None:
        positive_only = generate_conditioning_folder(
            tmp_path / "pos", polarities=("Pos",), truncate=None
        )
        loader = _loader(positive_only.root)
        assert loader.get_psd_polarities() == ["+"]
        assert loader.get_psd_segment_count("-") == 0

    def test_a_sensitivity_of_zero_is_refused(
        self, experiment: ConditioningDataset
    ) -> None:
        with pytest.raises(ValueError, match="Sensitivity"):
            _loader(experiment.root, Sensitivity=0.0)

    def test_closing_twice_is_safe_and_releases_every_recording(
        self, loader: NIConditioningLoader
    ) -> None:
        loader.close_resources()
        loader.close_resources()
        assert loader.get_psd_polarities() == []
