"""
One reader opens both Chimera VC400 file layouts.

The earlier layout embeds its acquisition settings as JSON at the start of each ``.log``
file, ending in ``<END HEADER>``; the later one keeps them in a companion ``.json`` with the
same stem. Which one a file uses is told from the file itself, by looking for the marker.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from poriscope.plugins.datareaders.ChimeraReaderVC400 import (
    ChimeraReaderVC400 as Reader,
)
from tests.synthetic_data.synthetic_chimera import (
    ChimeraRecordingConfig,
    generate_chimera_20240101_dataset,
    generate_chimera_dataset,
)

BASELINE_PA = 1000.0
EVENT_AMPLITUDE_PA = -400.0
NOISE_PA = 5.0
MEAN_TOLERANCE_PA = 2.0
CHANNEL = 3


def recording_config() -> ChimeraRecordingConfig:
    """
    A short recording with deep, long events, so a mean over one is tight.

    :return: the configuration both layouts are written from
    """
    return ChimeraRecordingConfig(
        samplerate=4_000_000.0,
        duration_s=0.5,
        baseline=BASELINE_PA,
        noise_std=NOISE_PA,
        event_amplitude=EVENT_AMPLITUDE_PA,
        event_duration_s=0.001,
    )


def open_reader(log_file: Path) -> Reader:
    reader = Reader()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(log_file)
    reader.apply_settings(settings)
    return reader


def test_a_recording_with_an_embedded_header_reads_the_planted_signal(
    tmp_path: Path,
) -> None:
    dataset = generate_chimera_20240101_dataset(
        tmp_path, recording_config(), channel=CHANNEL, num_events=3
    )
    assert not list(tmp_path.glob("*.json")), "this layout has no companion file"

    reader = open_reader(dataset.data_path)
    data = reader.load_data(0.0, dataset.duration_s, CHANNEL)

    quiet = np.ones(data.size, dtype=bool)
    for event in dataset.events:
        quiet[event.start_index : event.start_index + event.length_samples] = False
    assert data[quiet].mean() == pytest.approx(BASELINE_PA, abs=MEAN_TOLERANCE_PA)
    first = dataset.events[0]
    inside = data[first.start_index : first.start_index + first.length_samples]
    assert inside.mean() == pytest.approx(
        BASELINE_PA + EVENT_AMPLITUDE_PA, abs=MEAN_TOLERANCE_PA
    )
    reader.close_resources()


def test_both_layouts_give_the_same_samples(tmp_path: Path) -> None:
    """Same signal, same seed, written both ways: the header must not shift a sample."""
    embedded = generate_chimera_20240101_dataset(
        tmp_path / "embedded", recording_config(), channel=CHANNEL, seed=7
    )
    companion = generate_chimera_dataset(
        tmp_path / "companion", recording_config(), channel=CHANNEL, seed=7
    )

    from_embedded = open_reader(embedded.data_path)
    from_companion = open_reader(companion.data_path)
    a = from_embedded.load_data(0.0, embedded.duration_s, CHANNEL)
    b = from_companion.load_data(0.0, companion.duration_s, CHANNEL)

    assert a.size == b.size
    assert np.array_equal(a, b)
    assert from_embedded.get_samplerate() == from_companion.get_samplerate()
    from_embedded.close_resources()
    from_companion.close_resources()


def test_an_embedded_header_is_used_even_with_a_companion_file_beside_it(
    tmp_path: Path,
) -> None:
    """
    A stray ``.json`` must not make the header's bytes be read as samples, nor replace
    the file's own settings with another's.
    """
    dataset = generate_chimera_20240101_dataset(
        tmp_path, recording_config(), channel=CHANNEL, num_events=3
    )
    header_end = dataset.data_path.read_bytes().index(b"<END HEADER>")
    own = json.loads(dataset.data_path.read_bytes()[:header_end])
    wrong = json.loads(json.dumps(own))
    wrong["channel"]["tia_gain"] = own["channel"]["tia_gain"] * 10
    dataset.data_path.with_suffix(".json").write_text(json.dumps(wrong))

    reader = open_reader(dataset.data_path)
    data = reader.load_data(0.0, dataset.duration_s, CHANNEL)

    quiet = np.ones(data.size, dtype=bool)
    for event in dataset.events:
        quiet[event.start_index : event.start_index + event.length_samples] = False
    assert data[quiet].mean() == pytest.approx(BASELINE_PA, abs=MEAN_TOLERANCE_PA)
    reader.close_resources()


def test_a_file_with_neither_a_header_nor_a_companion_names_the_missing_file(
    tmp_path: Path,
) -> None:
    dataset = generate_chimera_dataset(tmp_path, recording_config(), channel=CHANNEL)
    companion = dataset.data_path.with_suffix(".json")
    companion.unlink()

    with pytest.raises(FileNotFoundError) as refused:
        open_reader(dataset.data_path)

    assert companion.name in str(refused.value)


def embedded_recording(tmp_path: Path) -> Path:
    """
    Write a recording with its settings embedded, and return its ``.log`` file.

    :param tmp_path: the directory to write into
    :return: the path of the ``.log`` file
    """
    dataset = generate_chimera_20240101_dataset(
        tmp_path, recording_config(), channel=CHANNEL, num_events=3
    )
    return dataset.data_path


def test_a_damaged_marker_leaves_a_file_that_needs_a_companion(
    tmp_path: Path,
) -> None:
    """Without its marker the file is not told as embedded, and nothing else describes it."""
    log_file = embedded_recording(tmp_path)
    data = log_file.read_bytes()
    log_file.write_bytes(data.replace(b"<END HEADER>", b"<XXXX XXXXXX>"))

    with pytest.raises(FileNotFoundError) as refused:
        open_reader(log_file)

    assert log_file.with_suffix(".json").name in str(refused.value)


def test_a_file_cut_inside_its_header_is_refused(tmp_path: Path) -> None:
    log_file = embedded_recording(tmp_path)
    header_end = log_file.read_bytes().index(b"<END HEADER>")
    log_file.write_bytes(log_file.read_bytes()[: header_end // 2])

    with pytest.raises(FileNotFoundError):
        open_reader(log_file)


def test_settings_that_are_not_json_are_refused(tmp_path: Path) -> None:
    log_file = embedded_recording(tmp_path)
    data = log_file.read_bytes()
    log_file.write_bytes(b"not json at all" + data[data.index(b"<END HEADER>") :])

    with pytest.raises(json.JSONDecodeError):
        open_reader(log_file)


def test_a_recording_cut_short_reports_the_length_it_can_deliver(
    tmp_path: Path,
) -> None:
    """The header's bytes are not counted as samples, whatever is left after them."""
    log_file = embedded_recording(tmp_path)
    data = log_file.read_bytes()
    header_bytes = data.index(b"<END HEADER>") + len(b"<END HEADER>")
    kept_samples = 1000
    log_file.write_bytes(data[: header_bytes + 2 * kept_samples])

    reader = open_reader(log_file)
    length = reader.get_channel_length(CHANNEL)
    delivered = reader.load_data(0.0, length / reader.get_samplerate(), CHANNEL)

    assert length == kept_samples
    assert delivered.size == kept_samples
    reader.close_resources()
