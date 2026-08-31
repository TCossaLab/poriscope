"""
Generation of synthetic ABF2 recordings for testing.

Writes a minimal but byte-exact ABF2 file that
``poriscope.plugins.datareaders.helpers.ABF2Header.ABF2Header`` (the real
parser both ABF2 readers use) can open. The real format carries a great deal
of acquisition metadata this codebase never reads; this writer supplies only
the sections and fields ``ABF2Header._read_abf2_header`` actually consumes,
zero-filling the rest of each 512-byte block.

Section layout (block size 512 bytes, block N at byte offset N*512)
---------------------------------------------------------------------
* Block 0: the file header. Fixed absolute offsets that matter:

  - bytes 0-3: the literal ``b"ABF2"`` signature.
  - byte 30 (uint16): data format marker. 0 selects int16 ADC codes, any
    other value selects float32 samples - this writer always uses float32,
    see "Why float32" below.
  - byte 76 (3x uint32/int32, "IIl"): the ProtocolSection pointer,
    (block_index, entry_size, entry_count). Only block_index is read.
  - byte 92: the ADCSection pointer, (block_index, entry_size, num_channels).
  - byte 220: the StringsSection pointer, (block_index, blob_length, unused).
  - byte 236: the DataSection pointer, (block_index, bytes_per_value,
    num_records). num_records is the sample count, not a byte count.

* Block 1: the ProtocolSection.

  - +2 (float32): fADCSequenceInterval, in microseconds between samples -
    samplerate = 1e6 / fADCSequenceInterval.
  - +110 (float32): fADCRange.
  - +118 (int32): lADCResolution. Read as a divisor, so must be nonzero;
    unused once data_type is float (see below).

* Block 2: the ADCSection, one 128-byte record per channel (only ~82 bytes
  of each are ever read; the header parser seeks to each record explicitly,
  so the stride just needs to be large enough to hold them). Every field
  ABF2Header._read_abf2_header reads, in order, is written here - most as
  inert placeholders, since only these are load-bearing: nTelegraphEnable=0
  (skips a division by fTelegraphAdditGain), fInstrumentScaleFactor=
  fSignalGain=fADCProgrammableGain=1.0 (each divided into a scale factor
  that gets discarded anyway - see below), lADCChannelNameIndex/
  lADCUnitsIndex (indices into the StringsSection blob).

* Block 3: the StringsSection. One blob holding every channel name and unit
  string, in the exact layout ABF2Header expects: a leading ``\\x00\\x00``
  so ``bytes.rfind(b"\\x00\\x00")`` lands one byte before the string list,
  then null-terminated strings. After ABF2Header's rfind/split/[1:] dance,
  string index 0 is always the empty string the marker itself produces, so
  channel/unit name indices start at 1. See _build_strings_blob.

* Block 4 onward: the DataSection. num_channels float32 values per sample,
  interleaved (current, voltage, ...), num_samples records.

Why float32
------------
ABF2Header derives each channel's scale factor from a chain of gain fields
(fInstrumentScaleFactor, fSignalGain, fADCProgrammableGain, and
fTelegraphAdditGain if telegraph is enabled) divided into fADCRange /
lADCResolution - but only when the data on disk is int16 ADC codes. For
float32 data it explicitly discards that computed value and hard-codes the
scale factor to 1.0 (see the ``if self.data_type == "f":`` branch), because
float samples are assumed to already be in physical units. That makes the
gain chain's exact values irrelevant here (they only need to be nonzero
where they're divisors, to avoid a ZeroDivisionError) and lets this writer
store the picoamp trace directly with no quantisation step at all - unlike
every int16-ADC-code format elsewhere in this package.

Channel counts and the two readers
------------------------------------
TCossaLabABFReader._get_configs requires exactly 2 ADC channels (current,
voltage) and raises otherwise; LegacyElementsReader._get_configs (its own
override) requires exactly 1. Both also require channel 0's name to contain
"I". num_channels is therefore a config field here, and the two convenience
functions below fix it to what each reader needs, along with each reader's
own filename convention:

* TCossaLabABFReader: ``_get_file_pattern`` requires the literal substring
  ``_\\d{12}_CH\\d{3}_\\d{3}.abf`` in the filename (a 12-digit timestamp, a
  3-digit channel-in-filename token, a 3-digit index).
* LegacyElementsReader: ``_get_file_pattern`` requires ``_\\d{4}.abf``
  instead (just a 4-digit token).
"""

from __future__ import annotations

import struct
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

BLOCK_SIZE = 512
ADC_RECORD_STRIDE = 128
CHANNEL_NAME_UNIT = "pA"
VOLTAGE_CHANNEL_UNIT = "mV"
VOLTAGE_CHANNEL_FILL = 200.0


@dataclass
class Abf2RecordingConfig(BaseRecordingConfig):
    """
    ABF2-specific recording parameters, on top of the shared base ones.

    baseline, noise_std and event_amplitude (inherited) are in picoamps and
    are written directly with no quantisation - see the module docstring's
    "Why float32" section.

    :param num_channels: ADC channels in the file. TCossaLabABFReader
        requires exactly 2 (current, voltage); LegacyElementsReader requires
        exactly 1 (current only).
    :type num_channels: int
    """

    num_channels: int = 2


def _build_strings_blob(num_channels: int) -> bytes:
    """
    Build the StringsSection blob and the name/unit indices into it.

    Constructs ``b"\\x00\\x00" + b"\\x00".join(entries)`` where entries starts
    with an empty placeholder followed by every channel name then every
    channel unit. ABF2Header locates the *last* ``\\x00\\x00`` pair in the
    blob and splits from there, which - because the leading two null bytes
    supply two such pairs (positions 0 and 1) - lands the split one byte
    into the marker, reproducing the leading empty placeholder as string
    index 0. Verified against the real parser in
    tests/synthetic_data/verify scripts, not just derived on paper: string
    index 0 is always "", so real content starts at index 1.

    :param num_channels: How many ADC channels to build strings for.
    :type num_channels: int

    :return: The blob to write into the StringsSection.
    :rtype: bytes
    """
    names = [f"IChannel{i}" if i == 0 else f"Aux{i}" for i in range(num_channels)]
    units = [CHANNEL_NAME_UNIT if i == 0 else VOLTAGE_CHANNEL_UNIT for i in range(num_channels)]
    entries = [b""] + [n.encode("ascii") for n in names] + [u.encode("ascii") for u in units]
    return b"\x00\x00" + b"\x00".join(entries)


def _pack_at(buf: bytearray, offset: int, fmt: str, *values: object) -> None:
    """
    Pack values into buf at offset, growing it if needed.

    :param buf: Buffer to write into, extended with zero bytes if too short.
    :type buf: bytearray
    :param offset: Byte offset to write at.
    :type offset: int
    :param fmt: A struct format string (native byte order, no alignment).
    :type fmt: str
    :param values: Values to pack, matching fmt.
    :type values: object
    """
    end = offset + struct.calcsize(fmt)
    if len(buf) < end:
        buf.extend(b"\x00" * (end - len(buf)))
    struct.pack_into(fmt, buf, offset, *values)


class Abf2RecordingWriter(BaseSyntheticRecordingWriter[Abf2RecordingConfig]):
    """
    Subclass of BaseSyntheticRecordingWriter for writing minimal, byte-exact
    ABF2 files, for TCossaLabABFReader and LegacyElementsReader.
    """

    def _write(
        self,
        out_dir: Path,
        config: Abf2RecordingConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Write an ABF2 file whose "current" channel carries trace directly.

        :param out_dir: Directory to write into. Already created by the
            time this is called.
        :type out_dir: Path
        :param config: Recording parameters, including num_channels.
        :type config: Abf2RecordingConfig
        :param channel: Unused directly - the filename is built by the
            convenience functions below, per reader's own convention.
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the .abf file that was written.
        :rtype: SyntheticDataset

        :raises ValueError: If config.num_channels is not 1 or 2 - the only
            two counts either real reader accepts.
        """
        if config.num_channels not in (1, 2):
            raise ValueError(
                f"num_channels must be 1 (LegacyElementsReader) or 2 "
                f"(TCossaLabABFReader), got {config.num_channels}"
            )

        n = config.num_channels
        protocol_block, adc_block, strings_block, data_block = 1, 2, 3, 4

        header = bytearray(BLOCK_SIZE)
        header[0:4] = b"ABF2"
        _pack_at(header, 30, "<H", 1)  # nonzero => float32 samples
        _pack_at(header, 76, "<IIl", protocol_block, 0, 0)  # ProtocolSection
        _pack_at(
            header, 92, "<IIl", adc_block, ADC_RECORD_STRIDE, n
        )  # ADCSection
        strings_blob = _build_strings_blob(n)
        _pack_at(
            header, 220, "<IIl", strings_block, len(strings_blob), 0
        )  # StringsSection
        _pack_at(
            header, 236, "<IIl", data_block, 4, trace.size
        )  # DataSection: 4 bytes/value (float32), trace.size records

        protocol = bytearray(BLOCK_SIZE)
        fADCSequenceInterval = 1.0e6 / config.samplerate
        _pack_at(protocol, 2, "<f", fADCSequenceInterval)
        _pack_at(protocol, 110, "<f", 1.0)  # fADCRange
        _pack_at(protocol, 118, "<i", 1)  # lADCResolution, must be nonzero

        adc = bytearray(ADC_RECORD_STRIDE * n)
        for i in range(n):
            name_index = 1 + i
            unit_index = 1 + n + i
            _pack_at(
                adc,
                i * ADC_RECORD_STRIDE,
                # nADCNum, nTelegraphEnable, nTelegraphInstrument,
                # fTelegraphAdditGain, fTelegraphFilter, fTelegraphMembraneCap,
                # nTelegraphMode, fTelegraphAccessResistance,
                # nADCPtoLChannelMap, nADCSamplingSeq, fADCProgrammableGain,
                # fADCDisplayAmplification, fADCDisplayOffset,
                # fInstrumentScaleFactor, fInstrumentOffset, fSignalGain,
                # fSignalOffset, fSignalLowpassFilter, fSignalHighpassFilter,
                # nLowpassFilterType, nHighpassFilterType,
                # fPostProcessLowpassFilter, nPostProcessLowpassFilterType,
                # bEnabledDuringPN, nStatsChannelPolarity,
                # lADCChannelNameIndex, lADCUnitsIndex
                "<hhh"
                "fff"
                "h"
                "f"
                "hh"
                "fffffffff"
                "BB"
                "f"
                "c"
                "B"
                "h"
                "ii",
                i,  # nADCNum
                0,  # nTelegraphEnable - disabled, skips the AdditGain divide
                0,  # nTelegraphInstrument
                1.0,  # fTelegraphAdditGain
                0.0,  # fTelegraphFilter
                0.0,  # fTelegraphMembraneCap
                0,  # nTelegraphMode
                0.0,  # fTelegraphAccessResistance
                0,  # nADCPtoLChannelMap
                0,  # nADCSamplingSeq
                1.0,  # fADCProgrammableGain - divisor, must be nonzero
                0.0,  # fADCDisplayAmplification
                0.0,  # fADCDisplayOffset
                1.0,  # fInstrumentScaleFactor - divisor, must be nonzero
                0.0,  # fInstrumentOffset
                1.0,  # fSignalGain - divisor, must be nonzero
                0.0,  # fSignalOffset
                0.0,  # fSignalLowpassFilter
                0.0,  # fSignalHighpassFilter
                0,  # nLowpassFilterType
                0,  # nHighpassFilterType
                0.0,  # fPostProcessLowpassFilter
                b"\x00",  # nPostProcessLowpassFilterType
                0,  # bEnabledDuringPN
                0,  # nStatsChannelPolarity
                name_index,  # lADCChannelNameIndex
                unit_index,  # lADCUnitsIndex
            )

        strings = bytearray(strings_blob)

        data = np.empty((trace.size, n), dtype="<f4")
        data[:, 0] = trace
        for i in range(1, n):
            data[:, i] = VOLTAGE_CHANNEL_FILL

        stem = self._filename_stem(config, channel)
        abf_path = out_dir / f"{stem}.abf"
        with open(abf_path, "wb") as f:
            for block in (header, protocol, adc, strings):
                f.write(block)
                pad = (-len(block)) % BLOCK_SIZE
                if pad:
                    f.write(b"\x00" * pad)
            data.tofile(f)

        return SyntheticDataset(
            data_path=abf_path,
            channel=channel,
            config=config,
            events=events,
        )

    def _filename_stem(self, config: Abf2RecordingConfig, channel: int) -> str:
        """
        Build a filename stem matching the target reader's pattern.

        The two readers' patterns cannot both be satisfied by one name:
        TCossaLabABFReader._get_file_pattern requires the trailing index to
        be exactly 3 digits (``_\\d{12}_CH\\d{3}_\\d{3}.abf``), while
        LegacyElementsReader._get_file_time_stamps requires exactly 4
        (``_\\d{4}.abf$``). num_channels selects which reader this file is
        for - 2 for TCossaLabABFReader, 1 for LegacyElementsReader - so it
        also selects which naming convention to use.

        For TCossaLabABFReader, ``channel`` is embedded in the ``CH###``
        token, since ``_get_file_channel_stamps`` parses the channel number
        back out of exactly that token - it must match what the caller
        expects ``SyntheticDataset.channel`` to be, or the two disagree about
        which channel the file is on. LegacyElementsReader has no such token:
        its ``_get_file_channel_stamps`` hardcodes channel 0 for every file
        regardless of filename, so ``channel`` is ignored for it.

        :param config: Recording parameters, used for the base name and to
            select the naming convention via num_channels.
        :type config: Abf2RecordingConfig
        :param channel: Channel number to embed for TCossaLabABFReader.
        :type channel: int

        :return: Filename stem, without extension.
        :rtype: str
        """
        if config.num_channels == 2:
            return f"{config.base_name}_202601010000_CH{channel:03d}_000"
        return f"{config.base_name}_0000"


def generate_abf2_modern_dataset(
    out_dir: Path,
    config: Abf2RecordingConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a 2-channel ABF2 recording, for TCossaLabABFReader.

    Forces config.num_channels to 2 - the only count TCossaLabABFReader
    accepts - regardless of what was passed in.

    :param out_dir: Directory to write the .abf file into. Created if it
        does not already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: Abf2RecordingConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the file and its contents.
    :rtype: SyntheticDataset
    """
    config.num_channels = 2
    return Abf2RecordingWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )


def generate_abf2_legacy_dataset(
    out_dir: Path,
    config: Abf2RecordingConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a 1-channel ABF2 recording, for LegacyElementsReader.

    Forces config.num_channels to 1 - the only count LegacyElementsReader
    accepts - regardless of what was passed in.

    :param out_dir: Directory to write the .abf file into. Created if it
        does not already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: Abf2RecordingConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the file and its contents.
    :rtype: SyntheticDataset
    """
    config.num_channels = 1
    return Abf2RecordingWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )
