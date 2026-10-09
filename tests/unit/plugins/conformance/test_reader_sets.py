"""
Readers beyond the single-file happy path: multi-file sets, mismatched rates, real gains.

The reader conformance suite opens one synthetic file per channel. Recordings in the lab
are sets of files per channel, their sample rate is a per-file header field that must
agree across the set, and ABF files carry integer ADC codes behind a stack of gains and
offsets rather than ready-made picoamps. These tests plant each of those and read it back.

What is pinned, and why each is red or green today (2026-10-05):

- A two-file Chimera set concatenates in timestamp order and reads across the file
  boundary at the planted baseline. Green.
- A second file in the same channel at a different sample rate is refused, and the
  message names the file. Green since ``MetaReader._set_sample_rate`` checks every file
  of every channel; until then it compared only each channel's first file, and the set
  was read at that file's rate.
- An int16 ABF file with non-trivial gains and both offsets reads back the planted
  picoamps through the shipped reader. Green, and it pins the arithmetic: codes times the
  gain, with the offsets added after it as pyabf applies them (step 2b's ruling, which
  replaced folding the offsets into the gain).
"""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.datareaders.TCossaLabABFReader import TCossaLabABFReader
from tests.synthetic_data.synthetic_abf2 import (
    Abf2RecordingConfig,
    generate_abf2_modern_dataset,
)
from tests.synthetic_data.synthetic_chimera import (
    ChimeraRecordingConfig,
    generate_chimera_dataset,
)
from tests.unit.plugins.conformance._recipes import (
    READER_BASELINE_PA,
    READER_EVENT_AMPLITUDE_PA,
    READER_NOISE_STD_PA,
    build_any_reader,
)
from tests.unit.plugins.conformance.test_readers import MEAN_TOLERANCE_PA

pytestmark = pytest.mark.conformance

CHIMERA_CHANNEL = 3
CHIMERA_SAMPLERATE_HZ = 4_000_000.0
FILE_DURATION_S = 0.25


def chimera_config(timestamp: str, samplerate: float = CHIMERA_SAMPLERATE_HZ):
    """
    A Chimera recording config for one file of a set.

    :param timestamp: the file's timestamp, which orders it within the set
    :type timestamp: str
    :param samplerate: the file's sample rate
    :type samplerate: float
    :return: the config
    :rtype: ChimeraRecordingConfig
    """
    return ChimeraRecordingConfig(
        base_name="synthetic_set",
        timestamp=timestamp,
        samplerate=samplerate,
        duration_s=FILE_DURATION_S,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=0.0005,
    )


@pytest.fixture
def two_file_set(tmp_path: Path):
    """
    Two Chimera files for one channel, written a second apart, in one directory.

    :param tmp_path: pytest's per-test directory
    :type tmp_path: Path
    :return: the two datasets, in timestamp order
    :rtype: tuple
    """
    first = generate_chimera_dataset(
        tmp_path, chimera_config("20260101_120000"), channel=CHIMERA_CHANNEL, seed=1
    )
    second = generate_chimera_dataset(
        tmp_path, chimera_config("20260101_120001"), channel=CHIMERA_CHANNEL, seed=2
    )
    return first, second


def test_a_two_file_set_is_read_as_one_recording(two_file_set) -> None:
    """The channel is the two files end to end, and the boundary is seamless."""
    first, second = two_file_set
    reader = build_any_reader(ChimeraReader20240501, first)
    try:
        samples_per_file = int(CHIMERA_SAMPLERATE_HZ * FILE_DURATION_S)
        assert reader.get_channel_length(CHIMERA_CHANNEL) == 2 * samples_per_file

        # A window straddling the boundary: the second half of the first file and the
        # first half of the second. Both halves sit at the planted baseline, give or
        # take the few events planted in them.
        window_s = 0.02
        data = reader.load_data(
            FILE_DURATION_S - window_s / 2, window_s, CHIMERA_CHANNEL
        )
        half = data.size // 2
        assert data.size == int(CHIMERA_SAMPLERATE_HZ * window_s)
        for name, part in (
            ("end of file 1", data[:half]),
            ("start of file 2", data[half:]),
        ):
            assert part.mean() == pytest.approx(
                READER_BASELINE_PA, abs=MEAN_TOLERANCE_PA
            ), f"{name}: mean {part.mean():.1f} pA"
        assert np.all(np.isfinite(data))
    finally:
        reader.close_resources()


def test_a_file_at_a_different_sample_rate_is_refused(tmp_path: Path) -> None:
    """Two files of one channel that disagree on sample rate cannot be one recording."""
    first = generate_chimera_dataset(
        tmp_path, chimera_config("20260101_120000"), channel=CHIMERA_CHANNEL, seed=1
    )
    generate_chimera_dataset(
        tmp_path,
        chimera_config("20260101_120001", samplerate=CHIMERA_SAMPLERATE_HZ / 2),
        channel=CHIMERA_CHANNEL,
        seed=2,
    )
    with pytest.raises(ValueError, match="120001") as refused:
        reader = build_any_reader(ChimeraReader20240501, first)
        reader.close_resources()
    assert "samplerate" in str(refused.value)


#: Gains chosen so 2000 pA of baseline and a -400 pA event fit comfortably in int16 at
#: about a tenth of a picoamp per code, with every field of the stack non-trivial.
INT16_ABF_CONFIG = Abf2RecordingConfig(
    base_name="synthetic_int16",
    samplerate=500_000.0,
    duration_s=0.2,
    baseline=READER_BASELINE_PA,
    noise_std=READER_NOISE_STD_PA,
    event_amplitude=READER_EVENT_AMPLITUDE_PA,
    event_duration_s=0.0005,
    data_type="int16",
    adc_range=10.0,
    adc_resolution=32768,
    instrument_scale_factor=0.5,
    signal_gain=2.0,
    adc_programmable_gain=4.0,
    telegraph_enable=1,
    telegraph_addit_gain=0.001,
    instrument_offset=0.02,
    signal_offset=0.005,
)


def test_the_int16_abf_config_exercises_every_gain_field() -> None:
    """
    The recipe is only worth having if no field is at its neutral value and the
    resulting resolution is fine enough to see a 15 pA noise floor.
    """
    c = INT16_ABF_CONFIG
    assert c.instrument_scale_factor != 1.0
    assert c.signal_gain != 1.0
    assert c.adc_programmable_gain != 1.0
    assert c.telegraph_enable and c.telegraph_addit_gain != 1.0
    assert c.instrument_offset != 0.0 and c.signal_offset != 0.0
    # 1/(0.5*2*4*0.001) * 10/32768 = about 0.0763 pA/code, which puts a 2000 pA baseline
    # near 26k codes and the 15 pA noise at 200 codes.
    assert 0.05 < c.pa_per_code() < 0.5, c.pa_per_code()
    # And the offsets are visible: 0.02 - 0.005 = 0.015 pA is about a fifth of a code, so
    # a reader that drops or folds them leaves samples off the whole-code grid.
    in_codes = c.pa_offset() / c.pa_per_code()
    assert abs(in_codes - round(in_codes)) > 0.1, in_codes


def test_an_int16_abf_file_reads_back_the_planted_picoamps(tmp_path: Path) -> None:
    """
    The shipped reader reconstructs picoamps from codes through the full gain stack, the
    offsets added after it as pyabf applies them.
    """
    dataset = generate_abf2_modern_dataset(
        tmp_path, INT16_ABF_CONFIG, num_events=5, seed=3
    )
    reader = build_any_reader(TCossaLabABFReader, dataset)
    try:
        data = reader.load_data(0.0, dataset.duration_s, dataset.channel)
        assert data.dtype == np.float64
        baseline_mask = np.ones(data.size, dtype=bool)
        for event in dataset.events:
            baseline_mask[
                event.start_index : event.start_index + event.length_samples
            ] = False
        baseline_mean = data[baseline_mask].mean()
        assert baseline_mean == pytest.approx(
            READER_BASELINE_PA, abs=MEAN_TOLERANCE_PA
        ), f"baseline {baseline_mean:.1f} pA"
        event = dataset.events[0]
        event_mean = data[
            event.start_index : event.start_index + event.length_samples
        ].mean()
        assert event_mean == pytest.approx(
            READER_BASELINE_PA + READER_EVENT_AMPLITUDE_PA, abs=MEAN_TOLERANCE_PA
        ), f"event {event_mean:.1f} pA"
        # Quantisation shows: every sample is a whole number of codes plus the offset.
        codes = (data - INT16_ABF_CONFIG.pa_offset()) / INT16_ABF_CONFIG.pa_per_code()
        assert np.allclose(codes, np.round(codes), atol=1e-6)
    finally:
        reader.close_resources()


def test_the_float32_abf_recipe_ignores_the_gain_fields(tmp_path: Path) -> None:
    """
    With float data the parser forces the scale to 1, so the same gains change nothing.

    This is why the int16 recipe exists: the float one, which the conformance suite uses,
    could never have detected a wrong gain.
    """
    config = replace(INT16_ABF_CONFIG, data_type="float32", base_name="synthetic_f32")
    dataset = generate_abf2_modern_dataset(tmp_path, config, num_events=5, seed=3)
    reader = build_any_reader(TCossaLabABFReader, dataset)
    try:
        data = reader.load_data(0.0, dataset.duration_s, dataset.channel)
        assert data.mean() == pytest.approx(READER_BASELINE_PA, abs=MEAN_TOLERANCE_PA)
    finally:
        reader.close_resources()
