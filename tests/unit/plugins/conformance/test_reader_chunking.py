"""
Chunked reads reassemble the recording sample for sample.

``MetaReader.continuous_read`` walks a channel in integer sample indices, converts each
chunk's start and length to seconds, and hands them to ``load_data``, which converts them
back. Both event-finder read paths (``MetaEventFinder.find_events`` and
``get_single_event_data``) build their seconds the same way, from integer sample counts
divided by the sample rate. The round trip is only exact if the conversion back rounds:
``_slice_request`` truncates, so ``int((i / sr) * sr)`` lands on ``i - 1`` for about one
index in nineteen at 100 kHz, the chunk that should start at ``i`` starts a sample early,
and the concatenation of the chunks duplicates one sample and loses another at that
boundary.

What is pinned, and why each is red or green today (2026-10-06):

- A one-sample request at ``i / sr`` returns sample ``i``, for every index in the first
  thousand and a stride across the rest. Red: ``_slice_request`` truncates. Strict expected
  failure until the request rounds (2.1 step 2).
- The chunks ``continuous_read`` yields concatenate to the whole recording exactly. Red for
  a chunk length whose boundary falls on a truncating index, which the test chooses on
  purpose; green for one whose boundaries happen to convert exactly, which is why a
  boundary that looks right is no evidence. Strict expected failure on the red case.
- The tail-chunk rule: a remainder shorter than half a chunk is absorbed into the last
  chunk rather than yielded on its own, and a longer one is its own chunk. Green; named
  here so the rule has a test that would fail if it moved.

The ground truth is read straight from the ``.bin`` file ``generate_binary_1x_dataset``
wrote, not through the reader: the format is big-endian float64 of the planted trace with
no gain or offset, so every comparison is exact rather than within a tolerance.
"""

from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

from poriscope.plugins.datareaders.BinaryReader1X import BinaryReader1X
from poriscope.utils.MetaReader import MetaReader
from tests.synthetic_data.synthetic_binary import (
    BinaryReader1XConfig,
    generate_binary_1x_dataset,
)
from tests.unit.plugins.conformance._recipes import (
    READER_BASELINE_PA,
    READER_EVENT_AMPLITUDE_PA,
    READER_EVENT_DURATION_S,
    READER_NOISE_STD_PA,
    build_any_reader,
)

pytestmark = pytest.mark.conformance

SAMPLERATE_HZ = 100_000.0
DURATION_S = 2.0
TOTAL_SAMPLES = int(DURATION_S * SAMPLERATE_HZ)

# Every index in this prefix is tried one by one; 7 is the first that truncates.
EXHAUSTIVE_PREFIX = 1_000
# Beyond the prefix a prime stride samples the rest without a pattern that could
# happen to dodge the truncating indices.
SWEEP_STRIDE = 97

# 0.19 s is 19,000 samples, and its third boundary, 57,000, converts to 56,999 through
# a truncating round trip; 0.3 s is 30,000 samples and every boundary of it converts
# exactly, which is the comparison case.
TRUNCATING_CHUNK_S = 0.19
EXACT_CHUNK_S = 0.3

TRUNCATION_DEFECT = (
    "MetaReader._slice_request truncates a seconds request to samples, so a chunk "
    "starting at an index whose seconds form rounds down starts one sample early "
    "(2.1 step 2)"
)


@pytest.fixture(scope="module")
def recording(tmp_path_factory) -> Tuple[MetaReader, np.ndarray]:
    """
    A two-second binary recording at 100 kHz, the reader over it, and its samples.

    :param tmp_path_factory: Pytest's session-scoped temporary directory factory.
    :type tmp_path_factory: pytest.TempPathFactory
    :return: The opened reader and the planted trace read straight from the file.
    :rtype: Tuple[MetaReader, numpy.ndarray]
    """
    out_dir: Path = tmp_path_factory.mktemp("chunking")
    config = BinaryReader1XConfig(
        samplerate=SAMPLERATE_HZ,
        duration_s=DURATION_S,
        baseline=READER_BASELINE_PA,
        noise_std=READER_NOISE_STD_PA,
        event_amplitude=READER_EVENT_AMPLITUDE_PA,
        event_duration_s=READER_EVENT_DURATION_S,
    )
    dataset = generate_binary_1x_dataset(out_dir, config, num_events=5)
    truth = np.fromfile(dataset.data_path, dtype=">f8")[0::2].astype(np.float64)
    assert truth.size == TOTAL_SAMPLES
    reader = build_any_reader(BinaryReader1X, dataset)
    assert reader.get_samplerate() == SAMPLERATE_HZ
    assert reader.get_channel_length(0) == TOTAL_SAMPLES
    yield reader, truth
    reader.close_resources()


def indices_to_try() -> List[int]:
    """
    The sample indices the one-sample test requests.

    :return: Every index in the exhaustive prefix, then a prime stride to the end.
    :rtype: List[int]
    """
    return list(range(EXHAUSTIVE_PREFIX)) + list(
        range(EXHAUSTIVE_PREFIX, TOTAL_SAMPLES, SWEEP_STRIDE)
    )


@pytest.mark.xfail(strict=True, reason=TRUNCATION_DEFECT)
def test_a_one_sample_request_returns_that_sample(recording) -> None:
    """
    ``load_data(i / sr, 1 / sr)`` returns exactly sample ``i``.

    :param recording: The reader and the planted trace.
    :type recording: Tuple[MetaReader, numpy.ndarray]
    """
    reader, truth = recording
    wrong: List[Tuple[int, int]] = []
    for i in indices_to_try():
        data = reader.load_data(i / SAMPLERATE_HZ, 1 / SAMPLERATE_HZ, 0)
        assert data.size == 1, f"one-sample request at {i} returned {data.size} samples"
        if data[0] != truth[i]:
            # The trace is noise, so the sample that came back identifies itself.
            matches = np.flatnonzero(truth[max(0, i - 2) : i + 3] == data[0])
            landed = int(matches[0]) + max(0, i - 2) if matches.size else -1
            wrong.append((i, landed))
    assert not wrong, (
        f"{len(wrong)} of {len(indices_to_try())} one-sample requests landed on the "
        f"wrong sample; first few (requested, returned): {wrong[:8]}"
    )


@pytest.mark.parametrize(
    "chunk_length_s",
    [
        pytest.param(
            TRUNCATING_CHUNK_S,
            marks=pytest.mark.xfail(strict=True, reason=TRUNCATION_DEFECT),
            id="boundary-truncates",
        ),
        pytest.param(EXACT_CHUNK_S, id="boundaries-exact"),
    ],
)
def test_continuous_read_chunks_concatenate_to_the_recording(
    recording, chunk_length_s: float
) -> None:
    """
    The chunks of a full-channel ``continuous_read`` concatenate to the recording.

    :param recording: The reader and the planted trace.
    :type recording: Tuple[MetaReader, numpy.ndarray]
    :param chunk_length_s: The chunk length to walk the channel with, in seconds.
    :type chunk_length_s: float
    """
    reader, truth = recording
    chunks = list(reader.continuous_read(0.0, 0.0, 0, chunk_length_s))
    joined = np.concatenate(chunks)
    assert (
        joined.size == truth.size
    ), f"chunks total {joined.size} samples, recording has {truth.size}"
    differing = np.flatnonzero(joined != truth)
    assert differing.size == 0, (
        f"{differing.size} samples differ after reassembly, the first at index "
        f"{int(differing[0])}; chunk sizes {[c.size for c in chunks]}"
    )


@pytest.mark.parametrize(
    "chunk_length_s, expected_sizes",
    [
        pytest.param(
            0.45, [45_000, 45_000, 45_000, 65_000], id="short-remainder-absorbed"
        ),
        pytest.param(
            0.3, [30_000] * 6 + [20_000], id="long-remainder-is-its-own-chunk"
        ),
    ],
)
def test_the_tail_chunk_rule(
    recording, chunk_length_s: float, expected_sizes: List[int]
) -> None:
    """
    A remainder shorter than half a chunk joins the last chunk; a longer one stands alone.

    200,000 samples in 45,000-sample chunks leave 20,000, under half a chunk, so the
    fourth chunk takes them; in 30,000-sample chunks they leave 20,000 again, now over
    half a chunk, so they are yielded as a seventh.

    :param recording: The reader and the planted trace.
    :type recording: Tuple[MetaReader, numpy.ndarray]
    :param chunk_length_s: The chunk length to walk the channel with, in seconds.
    :type chunk_length_s: float
    :param expected_sizes: The chunk sizes the rule produces.
    :type expected_sizes: List[int]
    """
    reader, _ = recording
    sizes = [
        chunk.size for chunk in reader.continuous_read(0.0, 0.0, 0, chunk_length_s)
    ]
    assert sizes == expected_sizes
