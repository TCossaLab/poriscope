"""
The lab's real recordings read back at their recorded rates, lengths and currents.

The synthetic recipes prove a reader reads what a writer that mirrors its parser wrote.
These tests open recordings the instruments themselves produced, one per shipped
reader and format variant, and pin what the shipped conversion reports for each: the
sample rate, the channels, every channel's length and file count, and the median of the
first second, the last second and (for a multi-file set) a second straddling the first
file boundary, in picoamps. The medians are the goldens a replacement parser must
match - the pyabf wrapper the ABF readers are moving to, in particular.

The recordings are gigabytes each and never enter the repository. The tests carry the
``real_data`` marker and take the ``real_data_dir`` fixture, which resolves the directory
``PORISCOPE_REAL_DATA_DIR`` names and skips the whole tier when it is unset, so CI skips
them and a developer with the recordings runs them by pointing the variable at the
directory that holds the six subdirectories listed in ``RECORDINGS``. A recording whose
subdirectory is missing skips on its own, so a partial copy still runs the rest.

Figures recorded 2026-10-06 through the shipped readers (``MetaReader.load_data``). Two
facts about the data itself, so nobody re-investigates them: the four channel files of
the Chimera 2024-05 set are byte-identical copies of one recording, which is why its
channels report the same statistics; and the two ABF sets report non-integer sample
rates because the format stores a sampling interval in microseconds.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Type

import numpy as np
import pytest

from poriscope.plugins.datareaders.BinaryReader1X import BinaryReader1X
from poriscope.plugins.datareaders.ChimeraReader20240101 import ChimeraReader20240101
from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from poriscope.plugins.datareaders.LegacyElementsReader import LegacyElementsReader
from poriscope.plugins.datareaders.TCossaLabABFReader import TCossaLabABFReader
from poriscope.utils.MetaReader import MetaReader

pytestmark = [pytest.mark.conformance, pytest.mark.real_data]

# A median is a sample value, so two readings of the same conversion agree to float
# precision; the tolerance only has to absorb printing.
MEDIAN_TOLERANCE_PA = 0.01


@dataclass(frozen=True)
class RealRecording:
    """
    One real recording and what the shipped reader reports for it.

    :param name: Short identifier, used as the test id.
    :type name: str
    :param subdir: Directory under ``PORISCOPE_REAL_DATA_DIR`` holding the files.
    :type subdir: str
    :param reader_cls: The reader that opens this format.
    :type reader_cls: Type[MetaReader]
    :param first_file: Glob, within ``subdir``, for the file handed to the reader.
    :type first_file: str
    :param samplerate: The reported sample rate in Hz.
    :type samplerate: float
    :param lengths: Samples per channel.
    :type lengths: Dict[int, int]
    :param file_counts: Files per channel.
    :type file_counts: Dict[int, int]
    :param first_second_median: Median of the first second per channel, in pA.
    :type first_second_median: Dict[int, float]
    :param last_second_median: Median of the last second per channel, in pA.
    :type last_second_median: Dict[int, float]
    :param boundary_median: Median of the second straddling the first file boundary
        (starting half a second before it) per channel, for multi-file sets.
    :type boundary_median: Dict[int, float]
    """

    name: str
    subdir: str
    reader_cls: Type[MetaReader]
    first_file: str
    samplerate: float
    lengths: Dict[int, int]
    file_counts: Dict[int, int]
    first_second_median: Dict[int, float]
    last_second_median: Dict[int, float]
    boundary_median: Dict[int, float] = field(default_factory=dict)


RECORDINGS = [
    RealRecording(
        name="binary_1x",
        subdir="binary_1x",
        reader_cls=BinaryReader1X,
        first_file="*_500000Hz.bin",
        samplerate=500_000.0,
        lengths={0: 326_000_000},
        file_counts={0: 1},
        first_second_median={0: -17.99},
        last_second_median={0: -25253.70},
    ),
    RealRecording(
        name="chimera_2024_05",
        subdir="vc400/v2024_05",
        reader_cls=ChimeraReader20240501,
        first_file="*_HS1_*.log",
        samplerate=5_000_000.0,
        lengths={ch: 1_652_555_776 for ch in (1, 2, 3, 4)},
        file_counts={ch: 1 for ch in (1, 2, 3, 4)},
        first_second_median={ch: -4323.45 for ch in (1, 2, 3, 4)},
        last_second_median={ch: -4471.59 for ch in (1, 2, 3, 4)},
    ),
    RealRecording(
        name="chimera_2024_01",
        subdir="vc400/v2024_01",
        reader_cls=ChimeraReader20240101,
        first_file="*_HS1_20240313_171429.log",
        samplerate=5_000_000.0,
        lengths={1: 182_976_512, 2: 244_842_496},
        file_counts={1: 6, 2: 8},
        first_second_median={1: 77890.51, 2: 6352.85},
        last_second_median={1: 78538.53, 2: 6642.08},
        boundary_median={1: 77704.62, 2: 6526.86},
    ),
    RealRecording(
        name="abf_e4x10",
        subdir="e4x10",
        reader_cls=TCossaLabABFReader,
        first_file="*_CH001_000.abf",
        samplerate=3333333.2008785727,
        lengths={1: 66_666_666, 2: 66_666_666},
        file_counts={1: 2, 2: 2},
        first_second_median={1: 12.21, 2: -39.67},
        last_second_median={1: 6.10, 2: 167.85},
        boundary_median={1: 9.16, 2: -180.06},
    ),
    RealRecording(
        name="abf_elements_4ch",
        subdir=(
            "Mock Server/Elements multichannel event data/"
            "4x_2kb_n200mV_7M_nanopores_231002155532_ch1yassine"
        ),
        reader_cls=TCossaLabABFReader,
        first_file="*_CH001_000.abf",
        samplerate=6666666.401757145,
        lengths={ch: 1_397_791_232 for ch in (1, 2, 3, 4)},
        file_counts={ch: 21 for ch in (1, 2, 3, 4)},
        first_second_median={1: 9.16, 2: -9.16, 3: -24.41, 4: -3.05},
        last_second_median={1: -13956.11, 2: -3375.35, 3: -1116.98, 4: -2209.54},
        boundary_median={1: -13943.91, 2: -3332.62, 3: -1770.07, 4: -192.27},
    ),
    RealRecording(
        name="abf_legacy_joey",
        subdir="Mock Server/Joey",
        reader_cls=LegacyElementsReader,
        first_file="*.abf",
        samplerate=500_000.0,
        lengths={0: 1_581_070_848},
        file_counts={0: 1},
        first_second_median={0: 7804.26},
        last_second_median={0: 7791.44},
    ),
]


def open_recording(real_data_dir: Path, recording: RealRecording) -> MetaReader:
    """
    Open a real recording through its shipped reader, or skip if it is not on disk.

    :param real_data_dir: The directory ``PORISCOPE_REAL_DATA_DIR`` names.
    :type real_data_dir: pathlib.Path
    :param recording: Which recording to open.
    :type recording: RealRecording
    :return: The reader, with settings applied and channel status initialised.
    :rtype: MetaReader
    """
    directory = real_data_dir / recording.subdir
    if not directory.is_dir():
        pytest.skip(f"{directory} is not present")
    files = sorted(directory.glob(recording.first_file))
    if not files:
        pytest.skip(f"nothing in {directory} matches {recording.first_file}")
    reader = recording.reader_cls()
    settings = reader.get_empty_settings(standalone=True)
    settings["Input File"]["Value"] = str(files[0])
    reader.apply_settings(settings)
    reader.report_status(init=True)
    return reader


@pytest.fixture(params=RECORDINGS, ids=[r.name for r in RECORDINGS])
def opened(request, real_data_dir: Path):
    """
    The reader over one real recording, and the figures recorded for it.

    :param request: Pytest request, carrying the parametrised recording.
    :type request: pytest.FixtureRequest
    :param real_data_dir: The directory ``PORISCOPE_REAL_DATA_DIR`` names.
    :type real_data_dir: pathlib.Path
    :return: The reader and its recorded figures.
    :rtype: tuple
    """
    recording: RealRecording = request.param
    reader = open_recording(real_data_dir, recording)
    yield reader, recording
    reader.close_resources()


def one_second(reader: MetaReader, start_sample: int, channel: int) -> np.ndarray:
    """
    Read one second starting at a sample index.

    :param reader: The reader to read from.
    :type reader: MetaReader
    :param start_sample: The first sample of the second.
    :type start_sample: int
    :param channel: The channel to read.
    :type channel: int
    :return: The second, in pA.
    :rtype: numpy.ndarray
    """
    samplerate = reader.get_samplerate()
    whole_second = int(samplerate)
    return reader.load_data(
        start_sample / samplerate, whole_second / samplerate, channel
    )


def check_second(data: np.ndarray, expected_median: float, where: str) -> None:
    """
    A second of real data is finite float64 at the recorded median.

    :param data: The second that was read.
    :type data: numpy.ndarray
    :param expected_median: The recorded median, in pA.
    :type expected_median: float
    :param where: Which second, for the failure message.
    :type where: str
    """
    assert data.dtype == np.float64, f"{where}: dtype {data.dtype}"
    assert np.isfinite(data).all(), f"{where}: non-finite samples"
    median = float(np.median(data))
    assert median == pytest.approx(
        expected_median, abs=MEDIAN_TOLERANCE_PA
    ), f"{where}: median {median:.2f} pA, recorded {expected_median:.2f} pA"


def test_reports_the_recorded_shape(opened) -> None:
    """
    Sample rate, channels, and every channel's length and file count are as recorded.

    :param opened: The reader and its recorded figures.
    :type opened: tuple
    """
    reader, recording = opened
    assert reader.get_samplerate() == pytest.approx(recording.samplerate, rel=1e-9)
    assert reader.get_channels() == sorted(recording.lengths)
    for channel, length in recording.lengths.items():
        assert reader.get_channel_length(channel) == length, f"channel {channel}"
        assert (
            len(reader.datafiles[channel]) == recording.file_counts[channel]
        ), f"channel {channel} file count"


def test_the_first_and_last_seconds_read_back_as_recorded(opened) -> None:
    """
    The first and last second of every channel are finite and at the recorded median.

    :param opened: The reader and its recorded figures.
    :type opened: tuple
    """
    reader, recording = opened
    whole_second = int(reader.get_samplerate())
    for channel, length in recording.lengths.items():
        first = one_second(reader, 0, channel)
        assert first.size == whole_second
        check_second(
            first, recording.first_second_median[channel], f"ch {channel} first"
        )
        last = one_second(reader, length - whole_second, channel)
        assert last.size == whole_second
        check_second(last, recording.last_second_median[channel], f"ch {channel} last")


def test_a_read_across_the_first_file_boundary_is_continuous(opened) -> None:
    """
    A second straddling a multi-file set's first boundary reads back at the recorded median.

    :param opened: The reader and its recorded figures.
    :type opened: tuple
    """
    reader, recording = opened
    if not recording.boundary_median:
        pytest.skip(f"{recording.name} is a single file per channel")
    whole_second = int(reader.get_samplerate())
    for channel, expected in recording.boundary_median.items():
        boundary = reader.file_start_indices[channel][1]
        across = one_second(reader, boundary - whole_second // 2, channel)
        assert across.size == whole_second
        check_second(
            across, expected, f"ch {channel} across the boundary at {boundary}"
        )
