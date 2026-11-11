"""
Generation of synthetic NI DAQ binary recordings and conditioning experiment folders.

NI binary format
----------------
The NI DAQ acquisition software writes one headerless file per measurement: big-endian
float64 samples, every channel interleaved frame by frame, in millivolts. The file name
carries the acquisition settings, ``<stem>_PSD-<points>_<averages>_<samplerate>Hz_<date>_<time>.bin``,
where ``points`` is the number of samples per PSD average. With the amplifier's
sensitivity in pA/V, a sample in mV is ``sensitivity / 1000`` pA, so at the default
sensitivity of 1000 pA/V a millivolt value reads back as the same number of picoamps.

Conditioning experiment folder
------------------------------
A conditioning experiment is one folder::

    <root>/
        Conditioning/      one or more CSVs, rows are cycles
        Cond PSD Pos/      one NI binary file per PSD taken at positive bias (optional)
        Cond PSD Neg/      the same at negative bias (optional)

Each CSV has three blocks of one column per channel: ``Pore Size CHn`` (the measured pore
size, nm), ``Target CHn`` (the upper target) and ``MinTarget CHn`` (the lower target). A
PSD is taken every ``psd_every_n`` cycles, so PSD file ``i`` (0-based, in time order)
belongs to cycle ``(i + 1) * psd_every_n``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from tests.synthetic_data.base_synthetic_recording import (
    BaseRecordingConfig,
    BaseSyntheticRecordingWriter,
    SyntheticDataset,
    SyntheticEvent,
)

#: Channels in every NI file this module writes.
NI_CHANNELS = 16

#: The folder names a conditioning experiment uses.
CONDITIONING_FOLDER = "Conditioning"
PSD_FOLDERS = {"Pos": "Cond PSD Pos", "Neg": "Cond PSD Neg"}


def ni_file_name(
    stem: str, points: int, averages: int, samplerate: int, stamp: datetime
) -> str:
    """
    Build an NI binary file name in the acquisition software's convention.

    :param stem: The experiment stem, e.g. ``TS1_M1-M4``.
    :type stem: str
    :param points: Samples per PSD average.
    :type points: int
    :param averages: Number of averages.
    :type averages: int
    :param samplerate: Sample rate in Hz.
    :type samplerate: int
    :param stamp: Acquisition time.
    :type stamp: datetime
    :return: The file name.
    :rtype: str
    """
    return f"{stem}_PSD-{points}_{averages}_{samplerate}Hz_{stamp:%Y%m%d_%H%M%S}.bin"


def write_ni_binary(path: Path, data_mv: np.ndarray) -> None:
    """
    Write a frames x channels array of millivolts as an NI binary file.

    :param path: Where to write.
    :type path: Path
    :param data_mv: Samples in mV, shape (frames, channels).
    :type data_mv: np.ndarray
    """
    np.ascontiguousarray(data_mv, dtype=">f8").tofile(path)


def noise_mv(
    frames: int, samplerate: float, rng: np.random.Generator, channels: int
) -> np.ndarray:
    """
    Build per-channel noise with a low-frequency excess, so a 1/f fit has a slope to find.

    Each channel is white noise plus a scaled random walk, with both scales growing with
    the channel index, so every channel has a different 1 Hz value.

    :param frames: Samples per channel.
    :type frames: int
    :param samplerate: Sample rate in Hz.
    :type samplerate: float
    :param rng: Random generator, for reproducibility.
    :type rng: np.random.Generator
    :param channels: Number of channels.
    :type channels: int
    :return: Noise in mV, shape (frames, channels).
    :rtype: np.ndarray
    """
    scale = 1.0 + np.arange(channels, dtype=np.float64)
    white = rng.standard_normal((frames, channels)) * 0.05 * scale
    walk = np.cumsum(rng.standard_normal((frames, channels)), axis=0)
    walk *= 0.2 * scale / np.sqrt(samplerate)
    return white + walk


@dataclass
class NIBinaryConfig(BaseRecordingConfig):
    """
    Recording parameters for one NI binary file holding a planted trace on channel 0.

    baseline, noise_std and event_amplitude (inherited) are in picoamps. The trace is
    written as millivolts unchanged, which reads back as the same picoamps at the
    reader's default sensitivity of 1000 pA/V. ``samplerate`` must be a whole number of
    Hz, since the reader parses it back out of the file name.
    """


class NIBinaryWriter(BaseSyntheticRecordingWriter[NIBinaryConfig]):
    """
    Subclass of BaseSyntheticRecordingWriter for the NI binary format: the planted trace
    on channel 0, and zeros on the other fifteen channels.
    """

    def _write(
        self,
        out_dir: Path,
        config: NIBinaryConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Write the trace interleaved into a 16-channel big-endian float64 file.

        :param out_dir: Directory to write into. Already created by the time this is called.
        :type out_dir: Path
        :param config: Recording parameters.
        :type config: NIBinaryConfig
        :param channel: Unused - the trace is always written to channel 0.
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the ``.bin`` file that was written.
        :rtype: SyntheticDataset
        """
        frames = np.zeros((trace.size, NI_CHANNELS), dtype=np.float64)
        frames[:, 0] = trace
        stamp = datetime.strptime(config.timestamp, "%Y%m%d_%H%M%S")
        name = ni_file_name(
            config.base_name, trace.size, 1, int(round(config.samplerate)), stamp
        )
        data_path = out_dir / name
        write_ni_binary(data_path, frames)
        return SyntheticDataset(
            data_path=data_path,
            channel=0,
            config=config,
            events=events,
        )


def generate_ni_binary_dataset(
    out_dir: Path,
    config: NIBinaryConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write an NI binary recording with events at known positions on channel 0.

    :param out_dir: Directory to write the ``.bin`` file into. Created if it does not
        already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: NIBinaryConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the file and its contents.
    :rtype: SyntheticDataset
    """
    return NIBinaryWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )


@dataclass
class PsdSeries:
    """
    The PSD files written for one polarity.

    :param samplerate: Sample rate of every file, in Hz.
    :type samplerate: int
    :param points: Samples per PSD average, as written in the file names.
    :type points: int
    :param paths: The files, in time order.
    :type paths: List[Path]
    :param data_mv: Each file's samples in mV, shape (frames, channels), in time order.
    :type data_mv: List[np.ndarray]
    """

    samplerate: int
    points: int
    paths: List[Path] = field(default_factory=list)
    data_mv: List[np.ndarray] = field(default_factory=list)


@dataclass
class ConditioningDataset:
    """
    A conditioning experiment folder and the ground truth written into it.

    :param root: The experiment folder.
    :type root: Path
    :param measured: Pore size per cycle, shape (cycles, channels), nm.
    :type measured: np.ndarray
    :param max_target: Upper target per cycle, shape (cycles, channels), nm.
    :type max_target: np.ndarray
    :param min_target: Lower target per cycle, shape (cycles, channels), nm.
    :type min_target: np.ndarray
    :param psd_every_n: A PSD was taken every this many cycles.
    :type psd_every_n: int
    :param psd: The PSD files per polarity, keyed ``Pos``/``Neg``.
    :type psd: Dict[str, PsdSeries]
    :param csv_paths: The CSVs written, in time order.
    :type csv_paths: List[Path]
    """

    root: Path
    measured: np.ndarray
    max_target: np.ndarray
    min_target: np.ndarray
    psd_every_n: int
    psd: Dict[str, PsdSeries]
    csv_paths: List[Path]

    @property
    def cycles(self) -> int:
        """
        :return: The number of conditioning cycles.
        :rtype: int
        """
        return int(self.measured.shape[0])

    @property
    def channels(self) -> int:
        """
        :return: The number of channels.
        :rtype: int
        """
        return int(self.measured.shape[1])


def _csv_header(channels: int) -> List[str]:
    """
    The CSV header the acquisition software writes.

    :param channels: Number of channels.
    :type channels: int
    :return: Column names.
    :rtype: List[str]
    """
    return (
        [f"Pore Size CH{c + 1}" for c in range(channels)]
        + [f"Target CH{c + 1}" for c in range(channels)]
        + [f"MinTarget CH{c + 1}" for c in range(channels)]
    )


def _write_csv(path: Path, rows: np.ndarray, channels: int, sep: str) -> None:
    """
    Write a block of conditioning rows with its header.

    :param path: Where to write.
    :type path: Path
    :param rows: Shape (cycles, 3 * channels).
    :type rows: np.ndarray
    :param channels: Number of channels.
    :type channels: int
    :param sep: The column separator.
    :type sep: str
    """
    lines = [sep.join(_csv_header(channels))]
    for row in rows:
        lines.append(sep.join(f"{value:g}" for value in row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_conditioning_folder(
    root: Path,
    *,
    cycles: int = 6,
    psd_every_n: int = 2,
    channels: int = NI_CHANNELS,
    disabled: Sequence[int] = (0, 1, 2, 3),
    polarities: Sequence[str] = ("Pos", "Neg"),
    pos: Tuple[int, int] = (10_000, 2_000),
    neg: Tuple[int, int] = (1_000, 2_000),
    truncate: Optional[Tuple[str, int, int]] = ("Neg", 1, 1_500),
    csv_split: Sequence[Tuple[str, str]] = (("TS1_M1-M4_Cond", "20261110_153919"),),
    sep: str = ",",
    seed: int = 7,
) -> ConditioningDataset:
    """
    Write a complete conditioning experiment folder with known contents.

    :param root: The experiment folder to create.
    :type root: Path
    :param cycles: Number of conditioning cycles.
    :type cycles: int
    :param psd_every_n: A PSD is taken every this many cycles.
    :type psd_every_n: int
    :param channels: Number of channels.
    :type channels: int
    :param disabled: Channels whose measured pore size is 0 in every cycle.
    :type disabled: Sequence[int]
    :param polarities: Which PSD folders to write.
    :type polarities: Sequence[str]
    :param pos: Sample rate and points per average of the positive-bias files.
    :type pos: Tuple[int, int]
    :param neg: Sample rate and points per average of the negative-bias files.
    :type neg: Tuple[int, int]
    :param truncate: Polarity, file index and frame count of one file to cut short,
        or None.
    :type truncate: Optional[Tuple[str, int, int]]
    :param csv_split: One (stem, timestamp) per CSV; the rows are divided evenly between
        them in this order, which is their time order.
    :type csv_split: Sequence[Tuple[str, str]]
    :param sep: The CSV column separator.
    :type sep: str
    :param seed: Random seed, making the noise reproducible.
    :type seed: int
    :return: The dataset and its ground truth.
    :rtype: ConditioningDataset
    """
    rng = np.random.default_rng(seed)
    root = Path(root)
    (root / CONDITIONING_FOLDER).mkdir(parents=True, exist_ok=True)

    cycle_index = np.arange(1, cycles + 1, dtype=np.float64)[:, None]
    channel_index = np.arange(channels, dtype=np.float64)[None, :]
    measured = np.round(1.0 + 0.5 * cycle_index + 0.1 * channel_index, 3)
    measured[:, list(disabled)] = 0.0
    max_target = np.full((cycles, channels), 18.0)
    max_target[:, 0] = 20.0
    min_target = np.zeros((cycles, channels))
    rows = np.hstack([measured, max_target, min_target])

    csv_paths: List[Path] = []
    blocks = np.array_split(rows, len(csv_split))
    for (stem, stamp), block in zip(csv_split, blocks):
        path = root / CONDITIONING_FOLDER / f"{stem}_{stamp}.csv"
        _write_csv(path, block, channels, sep)
        csv_paths.append(path)

    psd: Dict[str, PsdSeries] = {}
    files = cycles // psd_every_n
    start = datetime(2026, 11, 10, 15, 40, 0)
    for polarity in polarities:
        samplerate, points = pos if polarity == "Pos" else neg
        series = PsdSeries(samplerate=samplerate, points=points)
        folder = root / PSD_FOLDERS[polarity]
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(files):
            frames = points
            if truncate is not None and truncate[:2] == (polarity, index):
                frames = truncate[2]
            data = noise_mv(frames, samplerate, rng, channels)
            stamp = start + timedelta(
                minutes=index, seconds=1 if polarity == "Neg" else 0
            )
            path = folder / ni_file_name("TS1_M1-M4", points, 1, samplerate, stamp)
            write_ni_binary(path, data)
            series.paths.append(path)
            series.data_mv.append(data)
        psd[polarity] = series

    return ConditioningDataset(
        root=root,
        measured=measured,
        max_target=max_target,
        min_target=min_target,
        psd_every_n=psd_every_n,
        psd=psd,
        csv_paths=csv_paths,
    )
