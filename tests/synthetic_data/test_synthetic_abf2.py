"""
Self-tests for the synthetic ABF2 writer: its files are ABF2 that pyabf can open.

The writer began as a mirror of the readers' own header parser, supplying only the
fields that parser reads, so a file it wrote proved nothing about the format. These tests
open every fixture shape with ``pyabf``, an independent ABF reader, and check that it sees
the recording the writer describes - one gap-free sweep, the configured channels, names,
units and rate, a data section counting every value - and reads the same picoamps as the
shipped reader. Only zero-offset configs are compared sample by sample: with a non-zero
offset the shipped parser and pyabf apply it differently.
"""

from dataclasses import replace
from pathlib import Path
from typing import Callable, Type

import numpy as np
import pyabf
import pytest

from poriscope.plugins.datareaders.LegacyElementsReader import LegacyElementsReader
from poriscope.plugins.datareaders.TCossaLabABFReader import TCossaLabABFReader
from poriscope.utils.MetaReader import MetaReader
from tests.synthetic_data.base_synthetic_recording import SyntheticDataset
from tests.synthetic_data.synthetic_abf2 import (
    Abf2RecordingConfig,
    generate_abf2_legacy_dataset,
    generate_abf2_modern_dataset,
)
from tests.unit.plugins.conformance._recipes import build_any_reader

FLOAT_CONFIG = Abf2RecordingConfig(
    base_name="selftest",
    samplerate=500_000.0,
    duration_s=0.2,
    baseline=2000.0,
    noise_std=15.0,
)
#: Every gain field non-trivial and both offsets zero, so the two conversions agree.
INT16_CONFIG = replace(
    FLOAT_CONFIG,
    data_type="int16",
    adc_range=10.0,
    adc_resolution=32768,
    instrument_scale_factor=0.5,
    signal_gain=2.0,
    adc_programmable_gain=4.0,
    telegraph_enable=1,
    telegraph_addit_gain=0.001,
)

CASES = [
    pytest.param(
        generate_abf2_modern_dataset, FLOAT_CONFIG, TCossaLabABFReader, id="2ch-f32"
    ),
    pytest.param(
        generate_abf2_legacy_dataset, FLOAT_CONFIG, LegacyElementsReader, id="1ch-f32"
    ),
    pytest.param(
        generate_abf2_modern_dataset, INT16_CONFIG, TCossaLabABFReader, id="2ch-i16"
    ),
    pytest.param(
        generate_abf2_legacy_dataset, INT16_CONFIG, LegacyElementsReader, id="1ch-i16"
    ),
]


@pytest.mark.parametrize("generate, config, reader_cls", CASES)
def test_pyabf_reads_the_recording_the_writer_describes(
    tmp_path: Path,
    generate: Callable[..., SyntheticDataset],
    config: Abf2RecordingConfig,
    reader_cls: Type[MetaReader],
) -> None:
    """
    pyabf opens the file and its header agrees with the config the writer was given.
    """
    dataset = generate(tmp_path, replace(config), num_events=3, seed=7)
    n = dataset.config.num_channels
    samples = int(round(config.samplerate * config.duration_s))

    abf = pyabf.ABF(str(dataset.data_path), loadData=False)

    assert abf.abfVersion["major"] == 2
    assert abf.nOperationMode == 3, "gap-free"
    assert abf.sweepCount == 1
    assert abf.channelCount == n
    assert abf.dataPointCount == samples * n, "the data section counts every value"
    assert abf.adcUnits[0] == "pA"
    assert "I" in abf.adcNames[0]
    assert abf._nDataFormat == (0 if config.data_type == "int16" else 1)
    assert 1e6 / abf._protocolSection.fADCSequenceInterval == pytest.approx(
        config.samplerate, rel=1e-6
    )


@pytest.mark.parametrize("generate, config, reader_cls", CASES)
def test_pyabf_reads_the_same_picoamps_as_the_shipped_reader(
    tmp_path: Path,
    generate: Callable[..., SyntheticDataset],
    config: Abf2RecordingConfig,
    reader_cls: Type[MetaReader],
) -> None:
    """
    Sample for sample, pyabf's current channel equals what the shipped reader returns.

    pyabf scales in float32, so int16 data agrees to float32 precision; float32 data is
    stored unscaled and agrees exactly.
    """
    dataset = generate(tmp_path, replace(config), num_events=3, seed=7)
    abf = pyabf.ABF(str(dataset.data_path))
    reader = build_any_reader(reader_cls, dataset)
    try:
        ours = reader.load_data(0.0, config.duration_s, dataset.channel)
    finally:
        reader.close_resources()
    theirs = abf.data[0].astype(np.float64)

    assert theirs.shape == ours.shape
    if config.data_type == "int16":
        np.testing.assert_allclose(theirs, ours, rtol=1e-6, atol=1e-3)
    else:
        np.testing.assert_array_equal(theirs, ours)
    assert ours.mean() == pytest.approx(config.baseline, abs=10.0)
