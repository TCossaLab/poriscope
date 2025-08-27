# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs

import struct


class ABF2Header:
    def __init__(self, filename):
        self.f = open(filename, "rb")
        self._read_sections()

    def get_abf_version(self):
        return self.abf_version

    def get_channels(self):
        return self.channel_names

    def get_channel_units(self, channel_index):
        return self.channel_units[channel_index]

    def get_scale_factor(self, channel_index):
        return self.scaleFactors[channel_index]

    def get_num_channels(self):
        if self.abf_version == "ABF2":
            return self.ADCSection[2]
        else:
            # return self.nADCNumChannels[0]
            raise ValueError(
                "File version is not supported, only ABF2 files are supported"
            )

    def get_data_format(self):
        return "{0}{1}{2}".format(self.byte_order, self.data_type, self.data_size)

    def get_header_bytes(self):
        if self.abf_version == "ABF2":
            return self.DataSection[0] * 512
        else:
            # return self.dataByteStart
            raise ValueError(
                "File version is not supported, only ABF2 files are supported"
            )

    def get_channel_index_by_name(self, channel_name):
        return self.channel_names.index(channel_name)

    def get_samplerate(self):
        return self.samplerate

    def get_rescale_to_pA_factor(self, unit):
        rescale_dict = {
            "fA": 0.001,
            "pA": 1.0,
            "nA": 1000.0,
            "uA": 1000000.0,
            "mA": 1000000000.0,
        }
        try:
            return rescale_dict[unit]
        except KeyError:
            return 1.0

    def _read_abf2_header(self):
        self.ProtocolSection = self._readStruct("IIl", 76)
        self.ADCSection = self._readStruct("IIl", 92)
        self.DataSection = self._readStruct("IIl", 236)
        self.StringsSection = self._readStruct("IIl", 220)
        self.indexedStrings = self._readStruct(
            "{0}s".format(self.StringsSection[1]), self.StringsSection[0] * 512
        )[
            0
        ]  ##only the first entry is meaningful
        self.indexedStrings = self.indexedStrings[
            self.indexedStrings.rfind(b"\x00\x00") :
        ]
        self.indexedStrings = self.indexedStrings.replace(b"\xb5", b"\x75")
        self.indexedStrings = self.indexedStrings.split(b"\x00")[1:]
        self.indexedStrings = [
            x.decode("ascii", errors="replace").strip() for x in self.indexedStrings
        ]

        ## self.DACSection = self._readStruct("IIl", 108) #not used
        ## self.EpochSection = self._readStruct("IIl", 124) #not used
        ## self.ADCPerDACSection = self._readStruct("IIl", 140) #not used
        ## self.EpochPerDACSection = self._readStruct("IIl", 156) #not used
        ## self.TagSection = self._readStruct("IIl", 252) #not used

        # many of these are not directly used, but may be useful in the future and so are kept for reference, and we keep them here to avoid needing to seek to each one for now
        nADCNum = []  # 0
        nTelegraphEnable = []  # 2
        nTelegraphInstrument = []  # 4 #not used
        fTelegraphAdditGain = []  # 6
        fTelegraphFilter = []  # 10 #not used
        fTelegraphMembraneCap = []  # 14 #not used
        nTelegraphMode = []  # 18 #not used
        fTelegraphAccessResistance = []  # 20 #not used
        nADCPtoLChannelMap = []  # 24 #not used
        nADCSamplingSeq = []  # 26 #not used
        fADCProgrammableGain = []  # 28
        fADCDisplayAmplification = []  # 32  #not used
        fADCDisplayOffset = []  # 36 #not used
        fInstrumentScaleFactor = []  # 40
        fInstrumentOffset = []  # 44
        fSignalGain = []  # 48
        fSignalOffset = []  # 52
        fSignalLowpassFilter = []  # 56 #not used
        fSignalHighpassFilter = []  # 60 #not used
        nLowpassFilterType = []  # 64 #not used
        nHighpassFilterType = []  # 65 #not used
        fPostProcessLowpassFilter = []  # 66 #not used
        nPostProcessLowpassFilterType = []  # 70 #not used
        bEnabledDuringPN = []  # 71 #not used
        nStatsChannelPolarity = []  # 72 #not used
        self.lADCChannelNameIndex = []  # 74
        self.lADCUnitsIndex = []  # 78

        # many of these are not directly used, but may be useful in the future and so are kept for reference
        for i in range(self.ADCSection[2]):
            self.f.seek(self.ADCSection[0] * 512 + i * self.ADCSection[1])
            nADCNum.append(struct.unpack("h", self.f.read(2))[0])  # 0
            nTelegraphEnable.append(struct.unpack("h", self.f.read(2))[0])  # 2
            nTelegraphInstrument.append(struct.unpack("h", self.f.read(2))[0])  # 4
            fTelegraphAdditGain.append(struct.unpack("f", self.f.read(4))[0])  # 6
            fTelegraphFilter.append(struct.unpack("f", self.f.read(4))[0])  # 10
            fTelegraphMembraneCap.append(struct.unpack("f", self.f.read(4))[0])  # 14
            nTelegraphMode.append(struct.unpack("h", self.f.read(2))[0])  # 18
            fTelegraphAccessResistance.append(
                struct.unpack("f", self.f.read(4))[0]
            )  # 20
            nADCPtoLChannelMap.append(struct.unpack("h", self.f.read(2))[0])  # 24
            nADCSamplingSeq.append(struct.unpack("h", self.f.read(2))[0])  # 26
            fADCProgrammableGain.append(struct.unpack("f", self.f.read(4))[0])  # 28
            fADCDisplayAmplification.append(struct.unpack("f", self.f.read(4))[0])  # 32
            fADCDisplayOffset.append(struct.unpack("f", self.f.read(4))[0])  # 36
            fInstrumentScaleFactor.append(struct.unpack("f", self.f.read(4))[0])  # 40
            fInstrumentOffset.append(struct.unpack("f", self.f.read(4))[0])  # 44
            fSignalGain.append(struct.unpack("f", self.f.read(4))[0])  # 48
            fSignalOffset.append(struct.unpack("f", self.f.read(4))[0])  # 52
            fSignalLowpassFilter.append(struct.unpack("f", self.f.read(4))[0])  # 56
            fSignalHighpassFilter.append(struct.unpack("f", self.f.read(4))[0])  # 60
            nLowpassFilterType.append(int(struct.unpack("B", self.f.read(1))[0]))  # 64
            nHighpassFilterType.append(int(struct.unpack("B", self.f.read(1))[0]))  # 65
            fPostProcessLowpassFilter.append(
                struct.unpack("f", self.f.read(4))[0]
            )  # 66
            nPostProcessLowpassFilterType.append(
                struct.unpack("c", self.f.read(1))[0].decode("ascii", errors="ignore")
            )  # 70
            bEnabledDuringPN.append(int(struct.unpack("B", self.f.read(1))[0]))  # 71
            nStatsChannelPolarity.append(struct.unpack("h", self.f.read(2))[0])  # 72
            self.lADCChannelNameIndex.append(
                struct.unpack("i", self.f.read(4))[0]
            )  # 74
            self.lADCUnitsIndex.append(struct.unpack("i", self.f.read(4))[0])  # 78

        self.f.seek(
            self.ProtocolSection[0] * 512 + 2
        )  ##there are many more entries in these sections but we don't need them
        fADCSequenceInterval = struct.unpack("f", self.f.read(4))[0]
        self.f.seek(self.ProtocolSection[0] * 512 + 110)
        fADCRange = struct.unpack("f", self.f.read(4))[0]
        self.f.seek(self.ProtocolSection[0] * 512 + 118)
        lADCResolution = struct.unpack("i", self.f.read(4))[0]

        self.scaleFactors = []
        for i in range(self.ADCSection[2]):
            self.scaleFactors.append(1)
            self.scaleFactors[i] /= fInstrumentScaleFactor[i]
            self.scaleFactors[i] /= fSignalGain[i]
            self.scaleFactors[i] /= fADCProgrammableGain[i]
            if nTelegraphEnable[0]:
                self.scaleFactors[i] /= fTelegraphAdditGain[i]
            self.scaleFactors[i] *= fADCRange
            self.scaleFactors[i] /= lADCResolution
            self.scaleFactors[i] += fInstrumentOffset[i]
            self.scaleFactors[i] -= fSignalOffset[i]

        self.byte_order = "<"
        self.data_size = self.DataSection[1]
        self.data_type = self._readStruct("H", 30)[0]
        self.data_type = "i" if self.data_type == 0 else "f"

        for i in range(self.ADCSection[2]):
            if self.data_type == "f":
                self.scaleFactors[i] = 1

        self.channel_names = []
        if self.indexedStrings != []:
            for name in self.lADCChannelNameIndex:
                self.channel_names.append("{0}".format(self.indexedStrings[name]))

        self.channel_units = []
        if self.indexedStrings != []:
            for unit in self.lADCUnitsIndex:
                self.channel_units.append("{0}".format(self.indexedStrings[unit]))

        self.samplerate = 1.0e6 / fADCSequenceInterval

    def _read_sections(self):
        self.abf_version = self._readStruct("4s", 0)[0]
        self.abf_version = self.abf_version.decode("ascii", errors="ignore")
        if self.abf_version == "ABF2":
            self._read_abf2_header()
        else:
            raise NotImplementedError("ABF1 files are not supported")

    def _readStruct(self, structFormat, seekTo=-1):
        if seekTo >= 0:
            self.f.seek(seekTo)
        byteCount = struct.calcsize(structFormat)
        byteString = self.f.read(byteCount)
        value = struct.unpack(structFormat, byteString)
        return list(value)
