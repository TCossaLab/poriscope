"""
ABFReader against pyabf: every ABF shape pyabf opens reads back as pyabf reads it.

``pyabf`` is the oracle throughout. The reader takes its header from pyabf but maps and
scales the samples itself, so each test compares the reader's picoamps with pyabf's own
``data`` - the only independent reading of the same bytes - on ABF2 files from the
synthetic writer and on episodic ABF1 files from pyabf's own ``writeABF1``. The remaining
tests pin what pyabf does not decide: the exact sample rate, which ADC channel and sweep
are read, and which requests are refused.
"""

import struct
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pyabf
import pytest
from pyabf.abfWriter import writeABF1

from poriscope.plugins.datareaders.ABFReader import ABFReader
from tests.synthetic_data.synthetic_abf2 import (
    Abf2RecordingConfig,
    generate_abf2_legacy_dataset,
    generate_abf2_modern_dataset,
)

F32_CONFIG = Abf2RecordingConfig(
    base_name="abfreader",
    samplerate=500_000.0,
    duration_s=0.2,
    baseline=2000.0,
    noise_std=15.0,
)
#: Every field of the gain stack non-trivial, both offsets non-zero.
I16_CONFIG = replace(
    F32_CONFIG,
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

ABF1_SWEEPS = 3
ABF1_SWEEP_POINTS = 1000
ABF1_RATE = 250_000.0
#: Byte offset of nOperationMode in an ABF1 header.
ABF1_OPERATION_MODE_OFFSET = 8
#: Byte offset of nADCNumChannels in an ABF1 header.
ABF1_CHANNEL_COUNT_OFFSET = 120


def open_reader(path: Path, **settings: Any) -> ABFReader:
    """
    Open an ABFReader over one file, with any of its settings overridden.

    :param path: The ``.abf`` file.
    :type path: Path
    :param settings: Setting name (spaces as underscores) to value.
    :type settings: Any
    :return: The reader, settings applied and status initialised.
    :rtype: ABFReader
    """
    reader = ABFReader()
    schema = reader.get_empty_settings(standalone=True)
    schema["Input File"]["Value"] = str(path)
    for name, value in settings.items():
        schema[name.replace("_", " ")]["Value"] = value
    reader.apply_settings(schema)
    reader.report_status(init=True)
    return reader


def read_all(reader: ABFReader) -> np.ndarray:
    """
    Every sample of channel 0, in pA.

    :param reader: An open reader.
    :type reader: ABFReader
    :return: The whole channel.
    :rtype: numpy.ndarray
    """
    try:
        n = reader.get_channel_length(0)
        return reader.load_data(0.0, n / reader.get_samplerate(), 0)
    finally:
        reader.close_resources()


def write_abf1(path: Path, seed: int = 1) -> np.ndarray:
    """
    Write an episodic int16 ABF1 file with pyabf's own writer.

    :param path: Where to write it.
    :type path: Path
    :param seed: Noise seed.
    :type seed: int
    :return: The sweeps written, one row each, in pA.
    :rtype: numpy.ndarray
    """
    rng = np.random.default_rng(seed)
    sweeps = 2000.0 + rng.normal(0.0, 15.0, (ABF1_SWEEPS, ABF1_SWEEP_POINTS))
    writeABF1(sweeps, str(path), ABF1_RATE, units="pA")
    return sweeps


def relabel_units(path: Path, old: bytes, new: bytes) -> None:
    """
    Rename one units string in an ABF file's header, leaving the samples alone.

    Only the bytes before the data section are searched, since the same two bytes can
    occur by chance among the samples.

    :param path: The ``.abf`` file, rewritten in place.
    :type path: Path
    :param old: The units string to replace; it must occur exactly once in the header.
    :type old: bytes
    :param new: Its replacement, the same length.
    :type new: bytes
    """
    data = path.read_bytes()
    start = pyabf.ABF(str(path), loadData=False).dataByteStart
    header = data[:start]
    assert header.count(old) == 1 and len(new) == len(old)
    path.write_bytes(header.replace(old, new) + data[start:])


@pytest.fixture
def abf1_file(tmp_path: Path) -> Path:
    """
    An episodic ABF1 file of three int16 sweeps, written by pyabf.

    :param tmp_path: Pytest's temporary directory.
    :type tmp_path: Path
    :return: The file.
    :rtype: Path
    """
    path = tmp_path / "episodic.abf"
    write_abf1(path)
    return path


ABF2_CASES: Dict[str, Any] = {
    "2ch-f32": (generate_abf2_modern_dataset, F32_CONFIG),
    "2ch-f32-gains": (
        generate_abf2_modern_dataset,
        replace(I16_CONFIG, data_type="float32"),
    ),
    "1ch-f32": (generate_abf2_legacy_dataset, F32_CONFIG),
    "2ch-i16-offsets": (generate_abf2_modern_dataset, I16_CONFIG),
    "1ch-i16-offsets": (generate_abf2_legacy_dataset, I16_CONFIG),
}


@pytest.mark.parametrize("case", list(ABF2_CASES))
def test_an_abf2_file_reads_as_pyabf_reads_it(tmp_path: Path, case: str) -> None:
    """
    Sample for sample, the reader's current channel is pyabf's: int16 codes through
    the gain stack with the offsets added after it - pyabf's form, which a gain with the
    offsets folded into it does not match - and float32 samples unscaled, even when the
    header's gain fields are not neutral.

    pyabf scales int16 in float32, so those agree to float32 precision.
    """
    generate, config = ABF2_CASES[case]
    dataset = generate(tmp_path, replace(config), num_events=3, seed=5)
    ours = read_all(open_reader(dataset.data_path))
    theirs = pyabf.ABF(str(dataset.data_path)).data[0].astype(np.float64)

    assert ours.shape == theirs.shape
    if config.data_type == "int16":
        np.testing.assert_allclose(ours, theirs, rtol=1e-6, atol=1e-4)
    else:
        np.testing.assert_array_equal(ours, theirs)


def test_the_sample_rate_is_the_headers_interval_not_pyabfs_integer(
    tmp_path: Path,
) -> None:
    """
    A rate whose interval is not a whole number of microseconds reads back exactly as
    1e6 over the stored float32 interval, not as pyabf's rounded ``dataRate``.
    """
    rate = 3_333_333.2
    config = replace(F32_CONFIG, samplerate=rate, duration_s=0.05, edge_margin_s=0.01)
    dataset = generate_abf2_modern_dataset(tmp_path, config, num_events=1, seed=5)
    reader = open_reader(dataset.data_path)
    try:
        samplerate = reader.get_samplerate()
    finally:
        reader.close_resources()
    stored_interval = float(np.float32(1e6 / rate))
    assert samplerate == 1e6 / stored_interval
    assert samplerate != pyabf.ABF(str(dataset.data_path), loadData=False).dataRate


def test_an_episodic_abf1_file_reads_every_sweep_back_to_back(abf1_file: Path) -> None:
    """
    Sweep -1 reads all three sweeps in order, as pyabf does, and nothing after them:
    the file is padded past the data, and that padding is not read as samples.
    """
    abf = pyabf.ABF(str(abf1_file))
    assert abf.sweepCount == ABF1_SWEEPS
    padding = abf1_file.stat().st_size - abf.dataByteStart - abf.dataPointCount * 2
    assert padding > 0, "the fixture must have padding after the data to prove this"

    reader = open_reader(abf1_file)
    assert reader.get_samplerate() == ABF1_RATE
    ours = read_all(reader)

    assert ours.size == ABF1_SWEEPS * ABF1_SWEEP_POINTS
    np.testing.assert_allclose(ours, abf.data[0], rtol=1e-6, atol=1e-4)


@pytest.mark.parametrize("current_channel", [0, 1])
def test_an_abf1_interval_spans_every_channel(
    abf1_file: Path, current_channel: int
) -> None:
    """
    An ABF1 header's sampling interval is per value across the channels, so declaring a
    second channel halves each channel's rate; both columns read as pyabf reads them.
    """
    data = bytearray(abf1_file.read_bytes())
    struct.pack_into("<h", data, ABF1_CHANNEL_COUNT_OFFSET, 2)
    abf1_file.write_bytes(bytes(data))
    abf = pyabf.ABF(str(abf1_file))
    assert abf.channelCount == 2

    reader = open_reader(abf1_file, Current_Channel=current_channel)
    assert reader.get_samplerate() == ABF1_RATE / 2
    ours = read_all(reader)

    np.testing.assert_allclose(ours, abf.data[current_channel], rtol=1e-6, atol=1e-4)


@pytest.mark.parametrize("sweep", range(ABF1_SWEEPS))
def test_one_sweep_of_an_episodic_file_reads_only_that_sweep(
    abf1_file: Path, sweep: int
) -> None:
    """
    A sweep number reads that sweep alone, matching pyabf's ``sweepY`` for it.
    """
    abf = pyabf.ABF(str(abf1_file))
    abf.setSweep(sweep)
    ours = read_all(open_reader(abf1_file, Sweep=sweep))

    assert ours.size == ABF1_SWEEP_POINTS
    np.testing.assert_allclose(ours, abf.sweepY, rtol=1e-6, atol=1e-4)


def test_a_file_shorter_than_its_header_declares_is_refused(abf1_file: Path) -> None:
    """
    A file cut short inside its data section is refused rather than read as a shorter
    recording: the map covers exactly the samples the header declares.
    """
    abf = pyabf.ABF(str(abf1_file), loadData=False)
    data = abf1_file.read_bytes()
    # Five int16 samples short: the header still parses, the data section does not fit.
    abf1_file.write_bytes(data[: abf.dataByteStart + 2 * abf.dataPointCount - 10])
    assert (
        pyabf.ABF(str(abf1_file), loadData=False).dataPointCount == abf.dataPointCount
    )

    with pytest.raises(ValueError, match="shorter than its header declares"):
        open_reader(abf1_file)


def test_padding_after_the_data_is_never_read(abf1_file: Path) -> None:
    """
    Bytes after the data section are not samples, even when they do not fill a whole
    row of a two-channel file.
    """
    data = bytearray(abf1_file.read_bytes())
    struct.pack_into("<h", data, ABF1_CHANNEL_COUNT_OFFSET, 2)
    abf1_file.write_bytes(bytes(data) + bytes(2))
    abf = pyabf.ABF(str(abf1_file))
    padding = abf1_file.stat().st_size - abf.dataByteStart - abf.dataPointCount * 2
    assert (padding // 2) % 2 == 1, "an odd number of padding values, not a whole row"

    ours = read_all(open_reader(abf1_file))

    np.testing.assert_allclose(ours, abf.data[0], rtol=1e-6, atol=1e-4)


def test_a_sweep_past_the_last_is_refused(abf1_file: Path) -> None:
    """
    Asking for a sweep the file does not have is refused, naming how many it has.
    """
    with pytest.raises(ValueError, match=f"has {ABF1_SWEEPS} sweeps"):
        open_reader(abf1_file, Sweep=ABF1_SWEEPS)


def test_a_single_sweep_of_a_variable_length_file_is_refused(abf1_file: Path) -> None:
    """
    Variable-length sweeps cannot be located from the header, so one sweep is refused,
    while every sweep back to back still reads.
    """
    data = bytearray(abf1_file.read_bytes())
    struct.pack_into("<h", data, ABF1_OPERATION_MODE_OFFSET, 1)
    abf1_file.write_bytes(bytes(data))
    assert pyabf.ABF(str(abf1_file), loadData=False).nOperationMode == 1

    with pytest.raises(ValueError, match="variable-length sweeps"):
        open_reader(abf1_file, Sweep=0)
    assert read_all(open_reader(abf1_file)).size == ABF1_SWEEPS * ABF1_SWEEP_POINTS


def test_the_current_channel_setting_chooses_the_adc_channel(tmp_path: Path) -> None:
    """
    Channel 1 reads the second ADC channel's column, once its units are a current.

    The synthetic writer fills the second channel with a constant in mV; relabelling
    its units as pA lets it be read, and it reads as that constant.
    """
    dataset = generate_abf2_modern_dataset(
        tmp_path, replace(F32_CONFIG), num_events=3, seed=5
    )
    relabel_units(dataset.data_path, b"mV", b"pA")

    second = read_all(open_reader(dataset.data_path, Current_Channel=1))

    assert np.all(second == 200.0)


def test_a_channel_that_does_not_record_current_is_refused(tmp_path: Path) -> None:
    """
    Reading an ADC channel in mV is refused, naming the units, rather than read as pA.
    """
    dataset = generate_abf2_modern_dataset(
        tmp_path, replace(F32_CONFIG), num_events=3, seed=5
    )
    with pytest.raises(ValueError, match="records mV, not a current"):
        open_reader(dataset.data_path, Current_Channel=1)


def test_a_channel_past_the_last_is_refused(tmp_path: Path) -> None:
    """
    A channel index the file does not have is refused, naming how many it has.
    """
    dataset = generate_abf2_modern_dataset(
        tmp_path, replace(F32_CONFIG), num_events=3, seed=5
    )
    with pytest.raises(ValueError, match="has 2 ADC channels"):
        open_reader(dataset.data_path, Current_Channel=2)


def test_units_are_converted_to_picoamps(tmp_path: Path) -> None:
    """
    A channel recorded in nA reads as a thousand times its stored values.
    """
    dataset = generate_abf2_legacy_dataset(
        tmp_path, replace(F32_CONFIG), num_events=3, seed=5
    )
    in_pa = read_all(open_reader(dataset.data_path))
    relabel_units(dataset.data_path, b"pA", b"nA")

    in_na = read_all(open_reader(dataset.data_path))

    np.testing.assert_allclose(in_na, in_pa * 1000.0)
