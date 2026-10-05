"""
Generation of synthetic Chimera VC100 recordings for testing.

Writes files a real ChimeraReaderVC100 can open: a signal whose contents are
known exactly, in the older Chimera VC100 format this reader targets.

File format
-----------
A recording is one pair of files sharing a stem, matching
``^(.*)_(\\d{8}_\\d{6})\\.log$``:

* <stem>.log: the samples, as raw native-endian int16 ADC codes with no
  header (see ChimeraReaderVC100._get_configs, which declares
  ``{"data_order": "", ...}``, i.e. native byte order).
* <stem>.mat: a MATLAB file (read via ``scipy.io.loadmat``) carrying
  ADCSAMPLERATE, SETUP_TIAgain, SETUP_preADCgain, SETUP_pAoffset,
  SETUP_mVoffset, SETUP_ADCVREF, SETUP_ADCBITS and mytimestamp - the exact
  keys ``_get_configs`` reads.

``_get_file_channel_stamps`` hardcodes channel 0 for every VC100 file
(``config["channel"]`` is always 0 in ``_get_configs``), so this format has no
real multi-headstage concept the way Chimera VC400 does; every recording is
channel 0.

Signal construction
--------------------
The reader's conversion, inverted here the same way synthetic_chimera.py
inverts ChimeraReader20240501's::

    bitmask = (2**16 - 1) - (2**(16 - adc_bits) - 1)
    closedloop_gain = tia_gain * preadc_gain
    scale  = 1e12 * 2 * adc_vref / (2**16 * closedloop_gain)
    offset = 1e12 * (i_offset - adc_vref / closedloop_gain)
    picoamps = (code_as_uint16 & bitmask) * scale + offset

Using adc_bits=16 makes the bitmask a no-op (0xFFFF), so quantisation is the
only thing distinguishing an int16 code from its recovered picoamp value -
the same reasoning synthetic_chimera.py's module docstring gives for why
tia_gain has to be realistic (order 1e9) rather than unity.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import scipy.io as sio

from tests.synthetic_data.base_synthetic_recording import (
    BaseRecordingConfig,
    BaseSyntheticRecordingWriter,
    SyntheticDataset,
    SyntheticEvent,
)

CONV_UNIT = 1e12  # picoamps per amp


@dataclass
class ChimeraVC100RecordingConfig(BaseRecordingConfig):
    """
    VC100-specific recording parameters, on top of the shared base ones.

    baseline, noise_std and event_amplitude (inherited) are in picoamps.

    :param tia_gain: Transimpedance gain in ohms. Sets the ADC quantisation
        step together with preadc_gain; must be realistic (order 1e9) for a
        picoamp-scale signal to survive the round trip.
    :type tia_gain: float
    :param preadc_gain: Gain of the pre-ADC amplifier stage.
    :type preadc_gain: float
    :param i_offset: Current offset in amps, added during conversion.
    :type i_offset: float
    :param v_offset: Voltage offset in volts, recorded as metadata only.
    :type v_offset: float
    :param adc_vref: ADC reference voltage.
    :type adc_vref: float
    :param adc_bits: Resolution of the ADC. 16 makes the reader's bitmask a
        no-op, which is what this writer assumes.
    :type adc_bits: int
    """

    tia_gain: float = 1e9
    preadc_gain: float = 1.0
    i_offset: float = 0.0
    v_offset: float = 0.0
    adc_vref: float = 5.0
    adc_bits: int = 16


def _scale_offset(config: ChimeraVC100RecordingConfig) -> Tuple[float, float]:
    """
    Compute the ADC-code-to-picoamp conversion for a given gain configuration.

    Mirrors ChimeraReaderVC100._convert_data so that generation can invert it.

    :param config: Recording parameters carrying the gain stack.
    :type config: ChimeraVC100RecordingConfig

    :return: scale and offset such that picoamps = code * scale + offset.
    :rtype: Tuple[float, float]
    """
    closedloop_gain = config.tia_gain * config.preadc_gain
    scale = CONV_UNIT * 2 * config.adc_vref / (2**16 * closedloop_gain)
    offset = CONV_UNIT * (config.i_offset - config.adc_vref / closedloop_gain)
    return scale, offset


class ChimeraVC100RecordingWriter(
    BaseSyntheticRecordingWriter[ChimeraVC100RecordingConfig]
):
    """
    Subclass of BaseSyntheticRecordingWriter for writing Chimera VC100
    .log/.mat file pairs.
    """

    def _write(
        self,
        out_dir: Path,
        config: ChimeraVC100RecordingConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Encode a picoamp trace as int16 ADC codes and write the VC100
        .log/.mat pair.

        :param out_dir: Directory to write into. Already created by the
            time this is called.
        :type out_dir: Path
        :param config: Recording parameters for this channel.
        :type config: ChimeraVC100RecordingConfig
        :param channel: Unused - VC100 files are always channel 0
            (``_get_file_channel_stamps`` hardcodes it).
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the .log/.mat pair that was written.
        :rtype: SyntheticDataset
        """
        scale, offset = _scale_offset(config)

        # Invert to the unsigned ADC code space, then reinterpret those bits
        # as int16 - _scale_data does the reverse (astype(uint16) then
        # bitwise_and) when decoding, so the round trip only holds if the raw
        # bytes on disk really do carry this bit pattern.
        codes_u = np.clip(np.round((trace - offset) / scale), 0, 65535).astype(
            np.uint16
        )
        codes = codes_u.astype(np.int16)

        stem = f"{config.base_name}_{config.timestamp}"
        log_path = out_dir / f"{stem}.log"
        mat_path = out_dir / f"{stem}.mat"

        codes.tofile(log_path)

        sio.savemat(
            mat_path,
            {
                "ADCSAMPLERATE": float(config.samplerate),
                "SETUP_TIAgain": float(config.tia_gain),
                "SETUP_preADCgain": float(config.preadc_gain),
                "SETUP_pAoffset": float(config.i_offset),
                "SETUP_mVoffset": float(config.v_offset),
                "SETUP_ADCVREF": float(config.adc_vref),
                "SETUP_ADCBITS": float(config.adc_bits),
                "mytimestamp": config.timestamp,
            },
        )

        return SyntheticDataset(
            data_path=log_path,
            metadata_path=mat_path,
            channel=0,
            config=config,
            events=events,
        )


def generate_chimera_vc100_dataset(
    out_dir: Path,
    config: ChimeraVC100RecordingConfig,
    *,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a single-channel Chimera VC100 recording with events at known
    positions.

    :param out_dir: Directory to write the .log/.mat pair into. Created if
        it does not already exist.
    :type out_dir: Path
    :param config: Recording parameters.
    :type config: ChimeraVC100RecordingConfig
    :param num_events: How many events to plant.
    :type num_events: int
    :param seed: Random seed, making the noise reproducible.
    :type seed: int

    :return: Dataset describing the files and their contents.
    :rtype: SyntheticDataset
    """
    return ChimeraVC100RecordingWriter().generate(
        out_dir, config, channel=0, num_events=num_events, seed=seed
    )
