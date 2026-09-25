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

Every read is in pA: the unscaled raw-data path readers used to offer alongside
``load_data`` was removed in 2.0.0, so there is one conversion per reader to check.
"""

import dataclasses
import gc
import shutil
from pathlib import Path
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
def test_load_data_rejects_an_out_of_bounds_request(opened) -> None:
    """
    A request extending past the end of the channel raises, rather than
    silently returning fewer samples than asked for.

    Regression test: ``load_data`` used to clamp ``end_index`` down to
    ``total_samples`` *before* its own bounds check ran, so the check could
    never see an overrun and the promised ``:raises ValueError:`` was
    unreachable for this case - confirmed directly (requesting one sample
    past a channel's real end returned a shorter array with no exception,
    rather than raising) before being fixed. The exact-length request right
    below the overrun is asserted too, so this cannot pass merely by making
    every request fail.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, dataset = opened
    channel = dataset.channel

    exact = reader.load_data(0.0, dataset.duration_s, channel)
    assert exact.size > 0, "the exact-length request itself returned nothing"

    one_sample_s = 1.0 / dataset.samplerate
    with pytest.raises(ValueError):
        reader.load_data(0.0, dataset.duration_s + one_sample_s, channel)


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
@pytest.mark.parametrize("reader_cls", READERS, ids=[cls.__name__ for cls in READERS])
def test_reader_releases_its_input_file(reader_cls, tmp_path_factory) -> None:
    """
    A reader's file(s) become releasable once nothing references the reader.

    Deliberately does not use the ``opened`` fixture: it is itself a generator,
    and its paused frame would keep holding the reader live across the ``yield``
    until teardown, defeating the point of this test regardless of what happens
    below. Built directly here instead, so the only reference is the local one
    this test controls.

    ``MetaReader.close_resources``'s own docstring says a memmap-backed reader
    "need not explicitly close" it - the handle is released once the reader
    itself is collected, and confirmed empirically for all readers that release
    does not depend on ``close_resources`` being called at all, only on nothing
    referencing the reader anymore. It is still called here, once, to match the
    real lifecycle (``MainModel``/``DataPluginController`` call it on plugin
    deletion before dropping their own reference) - a future reader holding an
    OS-level resource GC alone cannot reclaim would need it to matter.

    So the contract under test is not "closed means released immediately", it
    is "once nothing references the reader, its file(s) are actually
    releasable" - the leak this catches is a hidden reference surviving
    deletion (a module-level cache, a registered callback), not a broken
    ``close_resources``.

    :param reader_cls: The reader class under test.
    :type reader_cls: Type[MetaReader]
    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    """
    out_dir = tmp_path_factory.mktemp(reader_cls.__name__)
    dataset = build_reader_dataset(reader_cls, out_dir)
    reader = build_any_reader(reader_cls, dataset)
    reader.close_resources()

    del reader
    gc.collect()
    try:
        shutil.rmtree(out_dir)
    except PermissionError as exc:
        pytest.fail(f"{reader_cls.__name__} still holds its file(s) open: {exc}")


@pytest.mark.conformance
def test_at_least_one_reader_was_discovered() -> None:
    """Guard against the discovery walk silently finding nothing."""
    assert READERS, "no concrete MetaReader subclasses were discovered"


def _copy_renamed(source_dir: Path, dest_dir: Path, old: str, new: str) -> None:
    """
    Copy every file of one recording into another folder under a different base name.

    :param source_dir: folder holding the recording to copy
    :type source_dir: Path
    :param dest_dir: folder to copy it into
    :type dest_dir: Path
    :param old: the base name the files carry
    :type old: str
    :param new: the base name to give the copies
    :type new: str
    """
    for path in source_dir.iterdir():
        shutil.copy(path, dest_dir / path.name.replace(old, new, 1))


@pytest.mark.conformance
@pytest.mark.parametrize("suffix", ["0", "_b"], ids=["exp1-exp10", "exp-exp_b"])
@pytest.mark.parametrize("reader_cls", READERS, ids=[cls.__name__ for cls in READERS])
def test_a_sibling_recording_is_not_read_as_part_of_this_one(
    reader_cls: Type[MetaReader], suffix: str, tmp_path: Path
) -> None:
    """
    A recording whose name merely starts with this one's is a different recording.

    Readers find the rest of a file set by globbing on the chosen file's base name, and
    a bare ``<base>*`` also matched ``<base>0...`` and ``<base>_b...``: the other
    recording was spliced into this one's channel, doubling its length, or crashed
    the sort when the two files carried the same timestamp.

    :param reader_cls: The reader class under test.
    :type reader_cls: Type[MetaReader]
    :param suffix: what the sibling's base name adds to this one's
    :type suffix: str
    :param tmp_path: Per-test temporary directory.
    :type tmp_path: Path
    """
    target_dir = tmp_path / "data"
    target = build_reader_dataset(reader_cls, target_dir)
    sibling_dir = tmp_path / "sibling"
    build_reader_dataset(reader_cls, sibling_dir)
    base = target.config.base_name
    _copy_renamed(sibling_dir, target_dir, base, base + suffix)

    reader = build_any_reader(reader_cls, target)
    try:
        expected = int(round(target.duration_s * target.samplerate))
        actual = reader.get_channel_length(target.channel)
    finally:
        reader.close_resources()
    assert (
        abs(actual - expected) <= 1
    ), f"read {actual} samples of a {expected} recording"


@pytest.mark.conformance
@pytest.mark.parametrize("reader_cls", READERS, ids=[cls.__name__ for cls in READERS])
def test_a_file_name_with_glob_characters_opens(
    reader_cls: Type[MetaReader], tmp_path: Path
) -> None:
    """
    Square brackets in a file name are part of the name, not a glob pattern.

    The base name went into the glob unescaped, so ``exp[1]`` matched only ``exp1`` and
    the chosen file itself was never found.

    :param reader_cls: The reader class under test.
    :type reader_cls: Type[MetaReader]
    :param tmp_path: Per-test temporary directory.
    :type tmp_path: Path
    """
    built_dir = tmp_path / "built"
    dataset = build_reader_dataset(reader_cls, built_dir)
    base = dataset.config.base_name
    renamed = base[:2] + "[1]" + base[2:]
    target_dir = tmp_path / "data"
    target_dir.mkdir()
    _copy_renamed(built_dir, target_dir, base, renamed)
    moved = dataclasses.replace(
        dataset,
        data_path=target_dir / dataset.data_path.name.replace(base, renamed, 1),
    )

    reader = build_any_reader(reader_cls, moved)
    try:
        expected = int(round(dataset.duration_s * dataset.samplerate))
        actual = reader.get_channel_length(dataset.channel)
    finally:
        reader.close_resources()
    assert (
        abs(actual - expected) <= 1
    ), f"read {actual} samples of a {expected} recording"


@pytest.mark.conformance
def test_files_with_tied_timestamps_sort_without_comparing_their_data(opened) -> None:
    """
    Two files in one channel with the same timestamp keep their order instead of crashing.

    The sort ordered ``(timestamp, data)`` pairs, so a tie fell through to comparing the
    two memmaps and raised "truth value of an array is ambiguous". It is reachable with
    TCossaLab ABF files, which sort on the part index alone: two recordings sharing a
    base, channel and part but not the 12-digit stamp tie.

    :param opened: The reader and its dataset ground truth.
    :type opened: tuple
    """
    reader, _dataset = opened
    first, second = np.zeros(4), np.ones(4)

    ordered = reader._sort_objects_by_channel_and_time([first, second], [0, 0], [7, 7])

    assert ordered[0][0] is first and ordered[0][1] is second
