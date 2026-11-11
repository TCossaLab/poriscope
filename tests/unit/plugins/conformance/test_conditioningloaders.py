"""
Behavioural conformance for every discovered ``MetaConditioningLoader``.

The Conditioning tab reads any experiment through the family's API alone, so these are the
promises it relies on: cycles counted from 1 with one pore size per cycle on every channel,
PSD recordings at the polarities the family names with a cycle, a sample rate and points
per average each, samples in pA as finite floats, and the status report in both its forms.
Accuracy against a known experiment belongs to each loader's own tests, not here.
"""

from pathlib import Path
from typing import List, Type

import numpy as np
import pytest

from poriscope.utils.MetaConditioningLoader import MetaConditioningLoader
from tests.unit.plugins.conformance._recipes import (
    assert_reports_whole_and_each_channel,
    build_conditioning_loader,
    discover_concrete,
)

LOADERS: List[Type[MetaConditioningLoader]] = discover_concrete(MetaConditioningLoader)

loader_cases = pytest.mark.parametrize(
    "loader_cls", LOADERS, ids=[cls.__name__ for cls in LOADERS]
)


@pytest.mark.conformance
@loader_cases
def test_every_channel_has_one_pore_size_per_cycle(
    loader_cls: Type[MetaConditioningLoader], tmp_path: Path
) -> None:
    loader = build_conditioning_loader(loader_cls, tmp_path)
    try:
        cycles = loader.get_cycles()
        assert list(cycles) == list(range(1, len(cycles) + 1))
        assert loader.get_channels() == sorted(set(loader.get_channels()))
        for channel in loader.get_channels():
            sizes = loader.get_pore_sizes(channel)
            assert set(sizes) == {"measured", "max_target", "min_target"}
            for name, values in sizes.items():
                assert np.asarray(values).shape == cycles.shape, name
    finally:
        loader.close_resources()


@pytest.mark.conformance
@loader_cases
def test_every_recording_says_what_the_tab_needs_and_reads_in_pa(
    loader_cls: Type[MetaConditioningLoader], tmp_path: Path
) -> None:
    loader = build_conditioning_loader(loader_cls, tmp_path)
    try:
        polarities = loader.get_psd_polarities()
        assert set(polarities) <= set(MetaConditioningLoader.POLARITIES)
        assert polarities, "the recipe's experiment should have PSD recordings"
        for polarity in polarities:
            count = loader.get_psd_segment_count(polarity)
            cycles = [loader.get_psd_cycle(polarity, i) for i in range(count)]
            assert all(cycle >= 1 for cycle in cycles)
            assert cycles == sorted(cycles)
            for index in range(count):
                assert loader.get_psd_samplerate(polarity, index) > 0
                assert loader.get_psd_points_per_average(polarity, index) > 0
                segment = loader.load_psd_segment(
                    polarity, index, loader.get_channels()[-1]
                )
                assert segment.dtype == np.float64 and segment.ndim == 1
                assert np.isfinite(segment).all()
    finally:
        loader.close_resources()


@pytest.mark.conformance
@loader_cases
def test_the_status_report_covers_the_experiment_and_each_channel(
    loader_cls: Type[MetaConditioningLoader], tmp_path: Path
) -> None:
    loader = build_conditioning_loader(loader_cls, tmp_path)
    try:
        for channel in loader.get_channels():
            assert_reports_whole_and_each_channel(loader, channel, init=True)
    finally:
        loader.close_resources()


@pytest.mark.conformance
@loader_cases
def test_reset_and_close_are_safe_to_repeat(
    loader_cls: Type[MetaConditioningLoader], tmp_path: Path
) -> None:
    loader = build_conditioning_loader(loader_cls, tmp_path)
    loader.reset_channel(0)
    loader.close_resources()
    loader.close_resources()
