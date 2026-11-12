"""
NIBinaryReader: one NI DAQ binary file, read as SingleBinaryDecoder would with the format fixed.

The NI DAQ acquisition software writes headerless big-endian float64 samples, every channel
interleaved, in mV, and names the file ``..._PSD-<points>_<averages>_<samplerate>Hz_...bin``.
The reader takes the sample rate from that name unless one is typed in, and converts mV to
pA with the amplifier's sensitivity in pA/V. ``SingleBinaryDecoder`` configured by hand for
the same file is the oracle: the variant fixes its settings, it does not read differently.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from poriscope.plugins.datareaders.NIBinaryReader import NIBinaryReader
from poriscope.plugins.datareaders.SingleBinaryDecoder import SingleBinaryDecoder
from tests.synthetic_data.synthetic_ni import (
    NI_CHANNELS,
    ni_file_name,
    noise_mv,
    write_ni_binary,
)

SAMPLERATE = 10_000
POINTS = 4_000


@pytest.fixture
def recording(tmp_path: Path) -> Dict[str, Any]:
    data = noise_mv(POINTS, SAMPLERATE, np.random.default_rng(11), NI_CHANNELS)
    name = ni_file_name("TS1", POINTS, 1, SAMPLERATE, datetime(2026, 11, 10, 15, 40))
    path = tmp_path / name
    write_ni_binary(path, data)
    return {"path": path, "data": data}


def _reader(path: Path, **values: Any) -> NIBinaryReader:
    reader = NIBinaryReader()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(path)
    for key, value in values.items():
        settings[key]["Value"] = value
    reader.apply_settings(settings)
    return reader


def test_the_dialog_offers_only_what_varies_between_ni_files() -> None:
    settings = NIBinaryReader().get_empty_settings(standalone=True)
    assert set(settings) == {
        "Input File",
        "Number of Arrays",
        "Sampling Rate",
        "Sensitivity",
    }
    assert settings["Number of Arrays"]["Value"] == NI_CHANNELS
    assert settings["Sensitivity"]["Value"] == 1000.0
    assert settings["Sensitivity"]["Units"] == "pA/V"


def test_every_channel_reads_back_in_pa(recording: Dict[str, Any]) -> None:
    reader = _reader(recording["path"])
    assert reader.get_channels() == list(range(NI_CHANNELS))
    for channel in range(NI_CHANNELS):
        data = reader.load_data(0.0, POINTS / SAMPLERATE, channel)
        np.testing.assert_array_equal(data, recording["data"][:, channel])


def test_sensitivity_scales_millivolts_to_picoamps(
    recording: Dict[str, Any],
) -> None:
    reader = _reader(recording["path"], Sensitivity=2500.0)
    data = reader.load_data(0.0, POINTS / SAMPLERATE, 5)
    np.testing.assert_allclose(data, recording["data"][:, 5] * 2.5, rtol=1e-15)


def test_it_matches_single_binary_decoder_configured_by_hand(
    recording: Dict[str, Any],
) -> None:
    variant = _reader(recording["path"], Sensitivity=1800.0)
    decoder = SingleBinaryDecoder()
    settings = decoder.get_empty_settings(standalone=True)
    values = {
        "Input File": str(recording["path"]),
        "Sampling Rate": float(SAMPLERATE),
        "Number of Arrays": NI_CHANNELS,
        "Byte Order": ">",
        "Data Type": "Floating Point",
        "Data Bytes": 8,
        "Scale": 1.8,
    }
    for key, value in values.items():
        settings[key]["Value"] = value
    decoder.apply_settings(settings)
    assert variant.get_samplerate() == decoder.get_samplerate()
    for channel in (0, 7, 15):
        np.testing.assert_array_equal(
            variant.load_data(0.0, POINTS / SAMPLERATE, channel),
            decoder.load_data(0.0, POINTS / SAMPLERATE, channel),
        )


def test_the_sample_rate_comes_from_the_file_name(
    recording: Dict[str, Any],
) -> None:
    assert _reader(recording["path"]).get_samplerate() == float(SAMPLERATE)


def test_a_typed_sample_rate_overrides_the_file_name(
    recording: Dict[str, Any],
) -> None:
    reader = _reader(recording["path"], **{"Sampling Rate": 20_000.0})
    assert reader.get_samplerate() == 20_000.0


def test_points_per_average_comes_from_the_file_name(
    recording: Dict[str, Any],
) -> None:
    assert _reader(recording["path"]).get_points_per_average() == POINTS


def test_a_name_without_settings_needs_a_typed_sample_rate(
    tmp_path: Path, recording: Dict[str, Any]
) -> None:
    renamed = tmp_path / "plain.bin"
    renamed.write_bytes(recording["path"].read_bytes())
    with pytest.raises(ValueError, match="Sampling Rate"):
        _reader(renamed)
    reader = _reader(renamed, **{"Sampling Rate": float(SAMPLERATE)})
    assert reader.get_samplerate() == float(SAMPLERATE)
    with pytest.raises(ValueError, match="points per average"):
        reader.get_points_per_average()


def test_a_sensitivity_of_zero_is_refused(recording: Dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Sensitivity"):
        _reader(recording["path"], Sensitivity=0.0)


def test_a_short_file_reads_its_own_length(tmp_path: Path) -> None:
    data = noise_mv(1_500, SAMPLERATE, np.random.default_rng(2), NI_CHANNELS)
    path = tmp_path / ni_file_name(
        "TS1", POINTS, 1, SAMPLERATE, datetime(2026, 11, 10, 15, 41)
    )
    write_ni_binary(path, data)
    reader = _reader(path)
    assert reader.get_channel_length(3) == 1_500
    np.testing.assert_array_equal(
        reader.load_data(0.0, 1_500 / SAMPLERATE, 3), data[:, 3]
    )
