"""
Behavioural conformance for every discovered ``MetaReader``.

A reader is the entry point every other family ultimately depends on -
filters, finders and writers all trace back to one - and it is the one family
whose "fixture" is not settings tuned against a shared database but a
different *on-disk file format* per plugin, since that is the whole thing a
reader varies over. ``tests/synthetic_data`` gained five new format writers
for this module: ``synthetic_binary.py`` (BinaryReader1X, SingleBinaryDecoder),
``synthetic_chimera_vc100.py`` (ChimeraReaderVC100), a Chimera 2024-01
embedded-header writer added to ``synthetic_chimera.py``
(ChimeraReader20240101), and ``synthetic_abf2.py`` (TCossaLabABFReader,
LegacyElementsReader) - each reverse-engineered against the real parsing code
rather than guessed, and independently verified to round-trip a known signal
before being wired in here. See each module's docstring for the format.

Before this module, only ChimeraReader20240501 had ever been driven against
real data (by ``tests/integration/flows`` and ``tests/e2e/raw_data``); the
other six readers had compliance and settings-schema coverage only.

The raw-data path deserves a note on what is and is not meaningful to assert
here. ``MetaReader.load_data`` always finishes its raw-data branch with
``data.astype(self.get_raw_dtype())`` before returning, so
``load_data(raw_data=True).dtype == get_raw_dtype()`` holds by construction
for every reader - it is not a per-plugin invariant and asserting it proves
nothing. What genuinely varies per plugin, and is worth checking, is that
``get_raw_dtype()`` itself resolves to a real, usable numpy dtype, and that
the raw-data call succeeds and returns an array of the same length as the
non-raw call. A byte-for-byte "raw reconstructs non-raw via scale/offset"
check was considered and rejected: `ChimeraReaderVC100._convert_data`
reinterprets the raw code through a bitmask/uint16 step that (scale, offset)
alone does not capture, so a literal ``raw*scale+offset`` formula is only
valid for *some* readers, not the family in general - confirmed directly
against the real reader rather than assumed.
"""

from typing import List, Type

import numpy as np
import pytest

from poriscope.utils.MetaReader import MetaReader
from tests.unit.plugins.conformance._recipes import (
    READER_BASELINE_PA,
    READER_EVENT_AMPLITUDE_PA,
    build_any_reader,
    build_reader_dataset,
    discover_concrete,
)

READERS: List[Type[MetaReader]] = discover_concrete(MetaReader)

# How close a noisy synthetic mean has to land to its target to count as
# correct. Generous relative to the 15 pA noise std these fixtures use, so
# this catches a wrong scale/offset/quantisation rather than flagging normal
# sampling variation.
MEAN_TOLERANCE_PA = 25.0


@pytest.fixture(params=READERS, ids=[cls.__name__ for cls in READERS])
def opened(request, tmp_path_factory):
    """
    Build the reader under test over a synthetic recording made for it.

    Each reader gets its own directory: several formats glob their directory
    for sibling channel files, so recordings for different readers cannot
    share one.

    :param request: Pytest request, carrying the parametrised reader class.
    :type request: pytest.FixtureRequest
    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: The reader and the dataset ground truth it was built from.
    :rtype: tuple
    """
    reader_cls = request.param
    out_dir = tmp_path_factory.mktemp(reader_cls.__name__)
    dataset = build_reader_dataset(reader_cls, out_dir)
    reader = build_any_reader(reader_cls, dataset)
    yield reader, dataset
    reader.close_resources()


@pytest.mark.conformance
def test_reports_the_recording_shape(opened) -> None:
    """
    A reader agrees with the fixture about channels, sample rate and length.

    These drive every downstream consumer's notion of how much data exists
    and at what rate, so a reader that mis-parsed any of them would corrupt
    everything built on top of it without necessarily raising.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, dataset = opened

    channels = reader.get_channels()
    assert (
        dataset.channel in channels
    ), f"expected channel {dataset.channel} among {channels}"
    assert reader.get_samplerate() == pytest.approx(dataset.samplerate, rel=1e-6)

    expected_length = int(round(dataset.duration_s * dataset.samplerate))
    actual_length = reader.get_channel_length(dataset.channel)
    # Within one sample: some formats derive length from file size divided by
    # record size, which can round differently than duration_s * samplerate.
    assert (
        abs(actual_length - expected_length) <= 1
    ), f"channel length {actual_length} vs expected {expected_length}"


@pytest.mark.conformance
def test_load_data_matches_the_planted_signal(opened) -> None:
    """
    ``load_data`` returns the planted baseline and event depth, in picoamps.

    This is the check that would catch a wrong gain, a wrong sign, or a
    scale/offset transposition - the class of defect a reader can have while
    still satisfying every structural check above.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, dataset = opened
    channel = dataset.channel

    data = reader.load_data(0.0, dataset.duration_s, channel)
    assert isinstance(data, np.ndarray)
    assert data.dtype == np.float64, f"load_data dtype is {data.dtype}, not float64"
    assert data.size > 0

    baseline_mask = np.ones(data.size, dtype=bool)
    for event in dataset.events:
        baseline_mask[event.start_index : event.start_index + event.length_samples] = (
            False
        )
    baseline_mean = data[baseline_mask].mean()
    assert baseline_mean == pytest.approx(
        READER_BASELINE_PA, abs=MEAN_TOLERANCE_PA
    ), f"baseline mean {baseline_mean:.1f} pA, planted {READER_BASELINE_PA} pA"

    assert dataset.events, "fixture planted no events to check event depth against"
    event = dataset.events[0]
    window = data[event.start_index : event.start_index + event.length_samples]
    expected_event_mean = READER_BASELINE_PA + READER_EVENT_AMPLITUDE_PA
    assert window.mean() == pytest.approx(
        expected_event_mean, abs=MEAN_TOLERANCE_PA
    ), f"event window mean {window.mean():.1f} pA, expected {expected_event_mean} pA"


@pytest.mark.conformance
def test_raw_data_path_is_self_consistent(opened) -> None:
    """
    ``get_raw_dtype()`` is usable, and the raw-data path returns matching shape.

    See the module docstring for why this stops short of a
    reconstruct-via-scale-and-offset check: that formula is not valid for
    every reader in the family (ChimeraReaderVC100's bitmask step is not
    representable by (scale, offset) alone), so asserting it here would be
    testing this test's assumption, not the plugin.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, dataset = opened
    channel = dataset.channel

    raw_dtype = reader.get_raw_dtype()
    assert np.dtype(raw_dtype) is not None  # raises TypeError if unusable

    non_raw = reader.load_data(0.0, dataset.duration_s, channel)
    raw, scale, offset = reader.load_data(
        0.0, dataset.duration_s, channel, raw_data=True
    )

    assert (
        raw.size == non_raw.size
    ), f"raw path returned {raw.size} samples, non-raw returned {non_raw.size}"
    assert isinstance(scale, (int, float, np.floating, np.integer))
    assert isinstance(offset, (int, float, np.floating, np.integer))


@pytest.mark.conformance
def test_reports_base_file_and_experiment(opened) -> None:
    """
    A reader can name the file it was opened from and its experiment stub.

    Both surface in the GUI (the plugin manager and tab titles), so a reader
    that raised or returned something unusable here would break silently
    outside of any test that actually opens a file.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, _dataset = opened

    base_file = reader.get_base_file()
    assert base_file, "get_base_file returned something falsy"

    experiment_name = reader.get_base_experiment_name()
    assert (
        isinstance(experiment_name, str) and experiment_name
    ), f"get_base_experiment_name returned {experiment_name!r}"


@pytest.mark.conformance
def test_reset_and_close_are_safe(opened) -> None:
    """
    A reader can be reset and closed twice without raising, and still reads.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, dataset = opened
    channel = dataset.channel

    first = reader.load_data(0.0, dataset.duration_s, channel)
    reader.reset_channel(channel)
    second = reader.load_data(0.0, dataset.duration_s, channel)
    np.testing.assert_allclose(
        second, first, err_msg="loading is not repeatable across reset_channel"
    )

    reader.close_resources()
    reader.close_resources()


@pytest.mark.conformance
def test_at_least_one_reader_was_discovered() -> None:
    """Guard against the discovery walk silently finding nothing."""
    assert READERS, "no concrete MetaReader subclasses were discovered"
