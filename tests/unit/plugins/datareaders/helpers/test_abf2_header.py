"""
Tests for poriscope.plugins.datareaders.helpers.ABF2Header

Strategy
--------
ABF2Header parses a real binary .abf file via struct.unpack at hardcoded
byte offsets. Rather than mocking the file object (which would not actually
exercise the byte-layout logic), these tests build small synthetic ABF2
files on disk with the exact section layout the parser expects, then parse
them for real. This validates the actual struct offsets, not just that
methods were called.

Section layout (see _read_abf2_header):
    offset 0:    4s   magic "ABF2"
    offset 30:   H    data_type (0=int16, else=float32)
    offset 76:   IIl  ProtocolSection (block_start, entry_size, count)
    offset 92:   IIl  ADCSection
    offset 220:  IIl  StringsSection
    offset 236:  IIl  DataSection

Per-channel ADC entry is 82 bytes (see _build_adc_entry below for the
exact field order/sizes).

Run with:
    pytest test_abf2header.py -v
"""

import struct
import unittest

from poriscope.plugins.datareaders.helpers.ABF2Header import ABF2Header

ADC_ENTRY_SIZE = 82


# ---------------------------------------------------------------------------
# Synthetic ABF2 file builder
# ---------------------------------------------------------------------------


def _build_adc_entry(
    adc_num=0,
    telegraph_enable=0,
    telegraph_additgain=1.0,
    adc_programmable_gain=1.0,
    instrument_scale_factor=1.0,
    instrument_offset=0.0,
    signal_gain=1.0,
    signal_offset=0.0,
    name_index=1,
    units_index=2,
):
    """Pack one 82-byte ADC channel entry matching the field order in
    ABF2Header._read_abf2_header's per-channel read loop."""
    buf = bytearray(ADC_ENTRY_SIZE)
    pos = 0

    struct.pack_into("h", buf, pos, adc_num)  # nADCNum
    pos += 2
    struct.pack_into("h", buf, pos, telegraph_enable)  # nTelegraphEnable
    pos += 2
    struct.pack_into("h", buf, pos, 0)  # nTelegraphInstrument
    pos += 2
    struct.pack_into("f", buf, pos, telegraph_additgain)  # fTelegraphAdditGain
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fTelegraphFilter
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fTelegraphMembraneCap
    pos += 4
    struct.pack_into("h", buf, pos, 0)  # nTelegraphMode
    pos += 2
    struct.pack_into("f", buf, pos, 0.0)  # fTelegraphAccessResistance
    pos += 4
    struct.pack_into("h", buf, pos, 0)  # nADCPtoLChannelMap
    pos += 2
    struct.pack_into("h", buf, pos, 0)  # nADCSamplingSeq
    pos += 2
    struct.pack_into("f", buf, pos, adc_programmable_gain)  # fADCProgrammableGain
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fADCDisplayAmplification
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fADCDisplayOffset
    pos += 4
    struct.pack_into("f", buf, pos, instrument_scale_factor)  # fInstrumentScaleFactor
    pos += 4
    struct.pack_into("f", buf, pos, instrument_offset)  # fInstrumentOffset
    pos += 4
    struct.pack_into("f", buf, pos, signal_gain)  # fSignalGain
    pos += 4
    struct.pack_into("f", buf, pos, signal_offset)  # fSignalOffset
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fSignalLowpassFilter
    pos += 4
    struct.pack_into("f", buf, pos, 0.0)  # fSignalHighpassFilter
    pos += 4
    struct.pack_into("B", buf, pos, 0)  # nLowpassFilterType
    pos += 1
    struct.pack_into("B", buf, pos, 0)  # nHighpassFilterType
    pos += 1
    struct.pack_into("f", buf, pos, 0.0)  # fPostProcessLowpassFilter
    pos += 4
    struct.pack_into("c", buf, pos, b"0")  # nPostProcessLowpassFilterType
    pos += 1
    struct.pack_into("B", buf, pos, 0)  # bEnabledDuringPN
    pos += 1
    struct.pack_into("h", buf, pos, 0)  # nStatsChannelPolarity
    pos += 2
    struct.pack_into("i", buf, pos, name_index)  # lADCChannelNameIndex
    pos += 4
    struct.pack_into("i", buf, pos, units_index)  # lADCUnitsIndex
    pos += 4

    assert pos == ADC_ENTRY_SIZE
    return bytes(buf)


def build_abf2_bytes(
    channel_names=("Ch0",),
    channel_units=("pA",),
    samplerate=100_000.0,
    instrument_scale_factor=1.0,
    signal_gain=1.0,
    adc_programmable_gain=1.0,
    telegraph_additgain=1.0,
    telegraph_enable=0,
    instrument_offset=0.0,
    signal_offset=0.0,
    adc_range=10.0,
    adc_resolution=32768,
    data_type=0,
    data_size=2,
    magic=b"ABF2",
):
    """
    Build a minimal but structurally valid synthetic ABF2 file as bytes.

    Per-channel scalar params (instrument_scale_factor, signal_gain, etc.)
    can be passed as a single value (applied to all channels) or a list
    matching len(channel_names).
    """
    n_channels = len(channel_names)
    assert len(channel_units) == n_channels

    def _as_list(v):
        return v if isinstance(v, (list, tuple)) else [v] * n_channels

    isf_list = _as_list(instrument_scale_factor)
    sg_list = _as_list(signal_gain)
    apg_list = _as_list(adc_programmable_gain)
    tag_list = _as_list(telegraph_additgain)
    io_list = _as_list(instrument_offset)
    so_list = _as_list(signal_offset)

    PROTOCOL_BLOCK = 2
    ADC_BLOCK = 3
    STRINGS_BLOCK = 4
    DATA_BLOCK = 5

    buf = bytearray(512 * 6)

    buf[0:4] = magic

    struct.pack_into("IIl", buf, 76, PROTOCOL_BLOCK, 1, 1)
    struct.pack_into("IIl", buf, 92, ADC_BLOCK, ADC_ENTRY_SIZE, n_channels)
    struct.pack_into("IIl", buf, 236, DATA_BLOCK, data_size, 1000)

    name_indices = list(range(1, 1 + n_channels))
    unit_indices = list(range(1 + n_channels, 1 + 2 * n_channels))
    all_strings = (
        [b""]
        + [n.encode("ascii") for n in channel_names]
        + [u.encode("ascii") for u in channel_units]
    )
    strings_blob = b"\x00\x00" + b"\x00".join(all_strings) + b"\x00"
    strings_size = len(strings_blob)
    struct.pack_into("IIl", buf, 220, STRINGS_BLOCK, strings_size, 1)

    strings_offset = STRINGS_BLOCK * 512
    needed = strings_offset + strings_size
    if needed > len(buf):
        buf.extend(bytearray(needed - len(buf)))
    buf[strings_offset : strings_offset + strings_size] = strings_blob

    struct.pack_into("H", buf, 30, data_type)

    adc_offset = ADC_BLOCK * 512
    needed = adc_offset + ADC_ENTRY_SIZE * n_channels
    if needed > len(buf):
        buf.extend(bytearray(needed - len(buf)))

    for i in range(n_channels):
        entry = _build_adc_entry(
            adc_num=i,
            telegraph_enable=telegraph_enable,
            telegraph_additgain=tag_list[i],
            adc_programmable_gain=apg_list[i],
            instrument_scale_factor=isf_list[i],
            instrument_offset=io_list[i],
            signal_gain=sg_list[i],
            signal_offset=so_list[i],
            name_index=name_indices[i],
            units_index=unit_indices[i],
        )
        off = adc_offset + i * ADC_ENTRY_SIZE
        buf[off : off + ADC_ENTRY_SIZE] = entry

    proto_offset = PROTOCOL_BLOCK * 512
    needed = proto_offset + 130
    if needed > len(buf):
        buf.extend(bytearray(needed - len(buf)))
    fADCSequenceInterval = 1.0e6 / samplerate
    struct.pack_into("f", buf, proto_offset + 2, fADCSequenceInterval)
    struct.pack_into("f", buf, proto_offset + 110, adc_range)
    struct.pack_into("i", buf, proto_offset + 118, adc_resolution)

    return bytes(buf)


def write_abf2_file(path, **kwargs):
    data = build_abf2_bytes(**kwargs)
    with open(path, "wb") as f:
        f.write(data)
    return path


# ---------------------------------------------------------------------------
# Single-channel, default-gain happy path
# ---------------------------------------------------------------------------


class TestSingleChannelDefaults(unittest.TestCase):
    def setUp(self):
        self.path = "test_single_channel.abf"
        write_abf2_file(
            self.path,
            channel_names=("Ch0",),
            channel_units=("pA",),
            samplerate=100_000.0,
        )
        self.header = ABF2Header(self.path)

    def tearDown(self):
        self.header.f.close()
        import os

        os.remove(self.path)

    def test_abf_version_is_abf2(self):
        self.assertEqual(self.header.get_abf_version(), "ABF2")

    def test_channel_names(self):
        self.assertEqual(self.header.get_channels(), ["Ch0"])

    def test_channel_units(self):
        self.assertEqual(self.header.get_channel_units(0), "pA")

    def test_num_channels(self):
        self.assertEqual(self.header.get_num_channels(), 1)

    def test_samplerate(self):
        self.assertAlmostEqual(self.header.get_samplerate(), 100_000.0, places=2)

    def test_scale_factor_default_gains(self):
        # all gains = 1.0, offsets = 0.0, range=10.0, resolution=32768
        # scale = (1/1/1/1) * 10 / 32768 = 10/32768
        expected = 10.0 / 32768
        self.assertAlmostEqual(self.header.get_scale_factor(0), expected, places=8)

    def test_data_format_int16(self):
        self.assertEqual(self.header.get_data_format(), "<i2")

    def test_header_bytes(self):
        # DataSection block start = 5 -> 5*512 = 2560
        self.assertEqual(self.header.get_header_bytes(), 2560)

    def test_channel_index_by_name(self):
        self.assertEqual(self.header.get_channel_index_by_name("Ch0"), 0)

    def test_channel_index_by_name_raises_for_unknown(self):
        with self.assertRaises(ValueError):
            self.header.get_channel_index_by_name("NotAChannel")


# ---------------------------------------------------------------------------
# Multi-channel files
# ---------------------------------------------------------------------------


class TestMultiChannel(unittest.TestCase):
    def setUp(self):
        self.path = "test_multi_channel.abf"
        write_abf2_file(
            self.path,
            channel_names=("Ch0", "Ch1", "Ch2"),
            channel_units=("pA", "mV", "pA"),
            samplerate=50_000.0,
            instrument_scale_factor=[1.0, 2.0, 1.0],
            signal_gain=[1.0, 1.0, 2.0],
        )
        self.header = ABF2Header(self.path)

    def tearDown(self):
        self.header.f.close()
        import os

        os.remove(self.path)

    def test_num_channels(self):
        self.assertEqual(self.header.get_num_channels(), 3)

    def test_all_channel_names(self):
        self.assertEqual(self.header.get_channels(), ["Ch0", "Ch1", "Ch2"])

    def test_all_channel_units(self):
        self.assertEqual(self.header.get_channel_units(0), "pA")
        self.assertEqual(self.header.get_channel_units(1), "mV")
        self.assertEqual(self.header.get_channel_units(2), "pA")

    def test_scale_factors_differ_per_channel(self):
        sf0 = self.header.get_scale_factor(0)
        sf1 = self.header.get_scale_factor(1)
        sf2 = self.header.get_scale_factor(2)
        # channel 1 has instrument_scale_factor=2.0 -> smaller scale factor
        self.assertLess(sf1, sf0)
        # channel 2 has signal_gain=2.0 -> smaller scale factor than ch0
        self.assertLess(sf2, sf0)

    def test_channel_index_by_name_middle_channel(self):
        self.assertEqual(self.header.get_channel_index_by_name("Ch1"), 1)

    def test_channel_index_by_name_last_channel(self):
        self.assertEqual(self.header.get_channel_index_by_name("Ch2"), 2)


# ---------------------------------------------------------------------------
# Telegraph gain handling
# ---------------------------------------------------------------------------


class TestTelegraphGain(unittest.TestCase):
    def test_telegraph_disabled_ignores_additgain(self):
        path = "test_telegraph_off.abf"
        write_abf2_file(
            path,
            telegraph_enable=0,
            telegraph_additgain=5.0,  # should be ignored
        )
        header = ABF2Header(path)
        expected = 10.0 / 32768  # default gains, additgain not applied
        self.assertAlmostEqual(header.get_scale_factor(0), expected, places=8)
        header.f.close()
        import os

        os.remove(path)

    def test_telegraph_enabled_applies_additgain(self):
        path = "test_telegraph_on.abf"
        write_abf2_file(
            path,
            telegraph_enable=1,
            telegraph_additgain=2.0,
        )
        header = ABF2Header(path)
        # scale = 1/1/1/2 * 10/32768
        expected = (10.0 / 32768) / 2.0
        self.assertAlmostEqual(header.get_scale_factor(0), expected, places=8)
        header.f.close()
        import os

        os.remove(path)


# ---------------------------------------------------------------------------
# Float data type forces scale factor to 1
# ---------------------------------------------------------------------------


class TestFloatDataType(unittest.TestCase):
    def setUp(self):
        self.path = "test_float_type.abf"
        write_abf2_file(
            self.path,
            data_type=1,  # non-zero -> float
            instrument_scale_factor=3.0,  # would normally affect scale factor
            data_size=4,
        )
        self.header = ABF2Header(self.path)

    def tearDown(self):
        self.header.f.close()
        import os

        os.remove(self.path)

    def test_data_format_is_float(self):
        self.assertEqual(self.header.get_data_format(), "<f4")

    def test_scale_factor_forced_to_one(self):
        # for float data, the parser explicitly overrides scaleFactors[i] = 1
        self.assertEqual(self.header.get_scale_factor(0), 1)


# ---------------------------------------------------------------------------
# Instrument/signal offset contributions to scale factor
# ---------------------------------------------------------------------------


class TestOffsetContributions(unittest.TestCase):
    def test_instrument_offset_added(self):
        path = "test_instr_offset.abf"
        write_abf2_file(path, instrument_offset=0.5)
        header = ABF2Header(path)
        base = 10.0 / 32768
        self.assertAlmostEqual(header.get_scale_factor(0), base + 0.5, places=6)
        header.f.close()
        import os

        os.remove(path)

    def test_signal_offset_subtracted(self):
        path = "test_signal_offset.abf"
        write_abf2_file(path, signal_offset=0.3)
        header = ABF2Header(path)
        base = 10.0 / 32768
        self.assertAlmostEqual(header.get_scale_factor(0), base - 0.3, places=6)
        header.f.close()
        import os

        os.remove(path)


# ---------------------------------------------------------------------------
# get_rescale_to_pA_factor — pure lookup, no file needed beyond instantiation
# ---------------------------------------------------------------------------


class TestRescaleToPAFactor(unittest.TestCase):
    def setUp(self):
        self.path = "test_rescale.abf"
        write_abf2_file(self.path)
        self.header = ABF2Header(self.path)

    def tearDown(self):
        self.header.f.close()
        import os

        os.remove(self.path)

    def test_fa_factor(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor("fA"), 0.001)

    def test_pa_factor(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor("pA"), 1.0)

    def test_na_factor(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor("nA"), 1000.0)

    def test_ua_factor(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor("uA"), 1_000_000.0)

    def test_ma_factor(self):
        self.assertAlmostEqual(
            self.header.get_rescale_to_pA_factor("mA"), 1_000_000_000.0
        )

    def test_unknown_unit_defaults_to_one(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor("XYZ"), 1.0)

    def test_empty_string_unit_defaults_to_one(self):
        self.assertAlmostEqual(self.header.get_rescale_to_pA_factor(""), 1.0)


# ---------------------------------------------------------------------------
# Unsupported / malformed files
# ---------------------------------------------------------------------------


class TestUnsupportedFiles(unittest.TestCase):
    def test_non_abf2_magic_raises_not_implemented(self):
        path = "test_bad_magic.abf"
        write_abf2_file(path, magic=b"ABF1")
        with self.assertRaises(NotImplementedError):
            ABF2Header(path)
        import os

        os.remove(path)

    def test_garbage_file_raises(self):
        path = "test_garbage.abf"
        with open(path, "wb") as f:
            f.write(b"NOTANABFFILE" + b"\x00" * 500)
        with self.assertRaises((NotImplementedError, struct.error)):
            ABF2Header(path)
        import os

        os.remove(path)

    def test_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            ABF2Header("this_file_does_not_exist_at_all.abf")


# ---------------------------------------------------------------------------
# Samplerate edge cases
# ---------------------------------------------------------------------------


class TestSamplerateVariants(unittest.TestCase):
    def test_high_samplerate(self):
        path = "test_high_sr.abf"
        write_abf2_file(path, samplerate=1_000_000.0)
        header = ABF2Header(path)
        self.assertAlmostEqual(header.get_samplerate(), 1_000_000.0, places=0)
        header.f.close()
        import os

        os.remove(path)

    def test_low_samplerate(self):
        path = "test_low_sr.abf"
        write_abf2_file(path, samplerate=1000.0)
        header = ABF2Header(path)
        self.assertAlmostEqual(header.get_samplerate(), 1000.0, places=2)
        header.f.close()
        import os

        os.remove(path)


# ---------------------------------------------------------------------------
# _readStruct internal helper — exercised directly
# ---------------------------------------------------------------------------


class TestReadStructHelper(unittest.TestCase):
    def setUp(self):
        self.path = "test_readstruct.abf"
        write_abf2_file(self.path)
        self.header = ABF2Header(self.path)
        # ABF2Header now closes its file handle once construction completes
        # (it's only ever used during header parsing); reopen it here since
        # these tests exercise the low-level _readStruct helper directly,
        # independent of the constructor's own read/close lifecycle.
        self.header.f = open(self.path, "rb")

    def tearDown(self):
        self.header.f.close()
        import os

        os.remove(self.path)

    def test_reads_at_explicit_offset(self):
        result = self.header._readStruct("4s", 0)
        self.assertEqual(result[0], b"ABF2")

    def test_reads_from_current_position_when_no_seek(self):
        self.header.f.seek(0)
        result = self.header._readStruct("4s")
        self.assertEqual(result[0], b"ABF2")

    def test_returns_list(self):
        result = self.header._readStruct("IIl", 76)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
