"""
Generation of synthetic raw-binary recordings for testing.

Two readers in this codebase read data with (almost) no header at all:
BinaryReader1X, whose format is fixed, and SingleBinaryDecoder, whose format is
entirely settings-driven. Both are covered here as two writers over the same
BaseSyntheticRecordingWriter framework the Chimera writer uses, since neither
needs anything from a real on-disk vendor header - the "format" is just
"some bytes, optionally offset by a header, in a declared dtype".

BinaryReader1X format
----------------------
* <stem>_<samplerate>Hz.bin: no header. Samples are stored as interleaved
  big-endian float64 pairs, (current, junk) - see its _get_configs, which
  hardcodes ``{"data_order": ">", "data_type": "f", "data_size": 8}`` and a
  structured dtype of two same-sized fields, of which only "current" is
  read back. The samplerate is not stored in the file; it is parsed from
  the filename itself via the ``_(\\d+)Hz\\.bin$`` pattern, so it must be an
  integer number of Hz.
* No scaling is applied on read (_convert_data uses scale=1.0, offset=0.0),
  so the picoamp trace is written directly as the "current" field.

SingleBinaryDecoder format
----------------------------
Every structural choice - header size, byte order, data type/size, and
whether multiple interleaved arrays are present - is a user setting rather
than something inferred from the file, so "the format" is whatever settings
say it is. The default settings (used here) are: no header, little-endian
float64, one array, scale 1.0/offset 0.0/no bitmask - i.e. the picoamp trace
written directly, with no encoding step needed at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

import numpy as np

from tests.synthetic_data.base_synthetic_recording import (
    BaseRecordingConfig,
    BaseSyntheticRecordingWriter,
    SyntheticDataset,
    SyntheticEvent,
)


@dataclass
class BinaryReader1XConfig(BaseRecordingConfig):
    """
    Recording parameters for the BinaryReader1X format.

    baseline, noise_std and event_amplitude (inherited) are in picoamps.
    samplerate is rounded to the nearest whole Hz when building the filename,
    since the reader parses it back out of the filename as an integer.
    """


class BinaryReader1XWriter(BaseSyntheticRecordingWriter[BinaryReader1XConfig]):
    """
    Subclass of BaseSyntheticRecordingWriter for writing BinaryReader1X's
    headerless, big-endian-float64, interleaved-with-junk ``.bin`` format.
    """

    def _write(
        self,
        out_dir: Path,
        config: BinaryReader1XConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Write the picoamp trace as interleaved big-endian float64 pairs.

        The reader discards every second value ("junk"), so it is filled with
        NaN here - any test that accidentally reads it instead of "current"
        fails loudly rather than looking like a shifted-but-plausible signal.

        :param out_dir: Directory to write into. Already created by the time
            this is called.
        :type out_dir: Path
        :param config: Recording parameters for this channel.
        :type config: BinaryReader1XConfig
        :param channel: Unused - BinaryReader1X has no headstage concept and
            always reports channel 0 (``_get_file_channel_stamps`` returns
            ``[0]`` unconditionally).
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the ``.bin`` file that was written.
        :rtype: SyntheticDataset
        """
        interleaved = np.empty(trace.size * 2, dtype=">f8")
        interleaved[0::2] = trace
        interleaved[1::2] = np.nan

        samplerate_hz = int(round(config.samplerate))
        data_path = out_dir / f"{config.base_name}_{samplerate_hz}Hz.bin"
        interleaved.tofile(data_path)

        return SyntheticDataset(
            data_path=data_path,
            channel=0,
            config=config,
            events=events,
        )


def generate_binary_1x_dataset(
    out_dir: Path,
    config: BinaryReader1XConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a BinaryReader1X-format recording with events at known positions.

    :param out_dir: Directory to write the ``.bin`` file into. Created if it
        does not already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: BinaryReader1XConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the file and its contents.
    :rtype: SyntheticDataset
    """
    return BinaryReader1XWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )


@dataclass
class SingleBinaryConfig(BaseRecordingConfig):
    """
    Recording parameters for the default SingleBinaryDecoder settings.

    baseline, noise_std and event_amplitude (inherited) are in picoamps and
    are written directly with no encoding, matching this writer's default
    settings of scale=1.0/offset=0.0/no bitmask.
    """


class SingleBinaryWriter(BaseSyntheticRecordingWriter[SingleBinaryConfig]):
    """
    Subclass of BaseSyntheticRecordingWriter for writing the plain
    little-endian-float64, headerless, single-array layout that
    SingleBinaryDecoder's default settings expect.
    """

    def _write(
        self,
        out_dir: Path,
        config: SingleBinaryConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Write the picoamp trace as raw little-endian float64 samples.

        :param out_dir: Directory to write into. Already created by the time
            this is called.
        :type out_dir: Path
        :param config: Recording parameters for this channel.
        :type config: SingleBinaryConfig
        :param channel: Unused - SingleBinaryDecoder reads a single
            user-specified file with no headstage concept.
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the ``.bin`` file that was written.
        :rtype: SyntheticDataset
        """
        data_path = out_dir / f"{config.base_name}.bin"
        trace.astype("<f8").tofile(data_path)

        return SyntheticDataset(
            data_path=data_path,
            channel=0,
            config=config,
            events=events,
        )


def generate_single_binary_dataset(
    out_dir: Path,
    config: SingleBinaryConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a SingleBinaryDecoder-format recording with events at known positions.

    :param out_dir: Directory to write the ``.bin`` file into. Created if it
        does not already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: SingleBinaryConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the file and its contents.
    :rtype: SyntheticDataset
    """
    return SingleBinaryWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )
