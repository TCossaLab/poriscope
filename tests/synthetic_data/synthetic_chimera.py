"""
Generation of synthetic Chimera VC400 recordings for testing.

Writes files a real ChimeraReader20240501 can open, containing a signal
whose contents are known exactly: a flat baseline with Gaussian noise,
into which blockage events of chosen depth and duration have been placed
at chosen positions.

File format
-----------
A recording is one pair of files sharing a stem:

* <stem>.log: the samples, as raw little-endian int16 ADC codes with no
  header of any kind. The recording's length is implied by the file size.
* <stem>.json: acquisition metadata, in three blocks: "log" (version,
  headstage number, timestamp), "global" (sample rates, filter gain,
  bandwidth), and "channel" (transimpedance gain, current and voltage
  offsets).

The stem must contain a _HS<n>_ token, since that is what a reader strips
to derive the pattern it uses to find sibling channel files.

Signal construction
--------------------
The desired signal is built in physical units (picoamps) by the shared
BaseSyntheticRecordingWriter, then converted here to the ADC codes
actually stored on disk by inverting the reader's own conversion::

    picoamps = code * scale + offset

    scale  = 1e12 * ((2 * 2 * 2.048 / 2**16) / filter_gain) / tia_gain
    offset = -i_offset * 1e12

Working this way means the events land at precisely the amplitude asked
for, once read back through the reader, rather than at whatever a guessed
code value happens to correspond to.

Note that scale sets the quantisation step, so tia_gain must be realistic
(of order 1e9, a gigaohm-range feedback resistor) for small signals to
survive the round trip. At unity gain a single code step spans more than
100 nA and a 400 pA event quantises away to nothing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np

from tests.synthetic_data.base_synthetic_recording import (
    BaseRecordingConfig,
    BaseSyntheticRecordingWriter,
    SyntheticDataset,
    SyntheticEvent,
)

CONV_UNIT = 1e12  # picoamps per amp


@dataclass
class ChimeraRecordingConfig(BaseRecordingConfig):
    """
    Chimera-specific recording parameters, on top of the shared base ones.

    baseline, noise_std, and event_amplitude (inherited from
    BaseRecordingConfig) are all in picoamps for this format.

    :param adc_samplerate: Converter sample rate. Defaults to samplerate
        if left as None.
    :type adc_samplerate: Optional[float]
    :param tia_gain: Transimpedance gain in ohms. Sets the ADC
        quantisation step; see the module docstring on why this must be
        realistic.
    :type tia_gain: float
    :param i_offset: Current offset in amps, subtracted during conversion.
    :type i_offset: float
    :param filter_gain: Gain of the analog filter stage.
    :type filter_gain: float
    :param bandwidth: Filter bandwidth in Hz, recorded as metadata.
    :type bandwidth: float
    :param decimate: Decimation factor, recorded as metadata.
    :type decimate: int
    :param voffset: Voltage offset, recorded as metadata.
    :type voffset: float
    :param version: Format version string, recorded as metadata.
    :type version: str
    """

    adc_samplerate: float | None = None
    tia_gain: float = 1e9
    i_offset: float = 0.0
    filter_gain: float = 1.0
    bandwidth: float = 100_000.0
    decimate: int = 1
    voffset: float = 0.0
    version: str = "1.0"

    @property
    def resolved_adc_samplerate(self) -> float:
        """
        adc_samplerate if explicitly set, else samplerate.

        :return: Effective ADC sample rate in Hz.
        :rtype: float
        """
        return self.samplerate if self.adc_samplerate is None else self.adc_samplerate


def _scale_offset(
    tia_gain: float, i_offset: float, filter_gain: float
) -> Tuple[float, float]:
    """
    Compute the ADC-code-to-picoamp conversion for a given gain configuration.

    Mirrors the conversion a Chimera reader applies when decoding a file,
    so that generation can invert it.

    :param tia_gain: Transimpedance gain in ohms.
    :type tia_gain: float
    :param i_offset: Current offset in amps.
    :type i_offset: float
    :param filter_gain: Gain of the analog filter stage.
    :type filter_gain: float

    :return: scale and offset such that picoamps = code * scale + offset.
    :rtype: Tuple[float, float]
    """
    scale = CONV_UNIT * ((2 * 2 * 2.048 / 2**16) / filter_gain) / tia_gain
    offset = -i_offset * CONV_UNIT
    return scale, offset


class ChimeraRecordingWriter(BaseSyntheticRecordingWriter[ChimeraRecordingConfig]):
    """
    Subclass of BaseSyntheticRecordingWriter for writing Chimera VC400
    .log/.json file pairs.
    """

    def _write(
        self,
        out_dir: Path,
        config: ChimeraRecordingConfig,
        channel: int,
        trace: np.ndarray,
        events: List[SyntheticEvent],
    ) -> SyntheticDataset:
        """
        Encode a picoamp trace as int16 ADC codes and write the Chimera
        .log/.json pair.

        :param out_dir: Directory to write into. Already created by the
            time this is called.
        :type out_dir: Path
        :param config: Recording parameters for this channel.
        :type config: ChimeraRecordingConfig
        :param channel: Headstage number, embedded in the filename and
            metadata.
        :type channel: int
        :param trace: The ground-truth signal, in picoamps.
        :type trace: numpy.ndarray
        :param events: Events already planted in trace.
        :type events: List[SyntheticEvent]

        :return: Dataset describing the .log/.json pair that was written.
        :rtype: SyntheticDataset
        """
        scale, offset = _scale_offset(
            config.tia_gain, config.i_offset, config.filter_gain
        )

        # Convert picoamps back to the ADC codes stored on disk, clipping
        # to the representable int16 range.
        codes_f = (trace - offset) / scale
        codes = np.clip(np.round(codes_f), -32768, 32767).astype(np.int16)

        stem = f"{config.base_name}_HS{channel}_{config.timestamp}"
        log_path = out_dir / f"{stem}.log"
        json_path = out_dir / f"{stem}.json"

        codes.tofile(log_path)

        metadata = {
            "log": {
                "version": config.version,
                "HS": channel,
                "timestamp": config.timestamp,
            },
            "global": {
                "f_sampling": config.samplerate,
                "f_adc": config.resolved_adc_samplerate,
                "filter_gain": config.filter_gain,
                "bandwidth": config.bandwidth,
                "decimate": config.decimate,
            },
            "channel": {
                "tia_gain": config.tia_gain,
                "i_offset": config.i_offset,
                "voffset": config.voffset,
            },
        }
        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return SyntheticDataset(
            data_path=log_path,
            metadata_path=json_path,
            channel=channel,
            config=config,
            events=events,
        )


def generate_chimera_dataset(
    out_dir: Path,
    config: ChimeraRecordingConfig,
    *,
    channel: int = 3,
    num_events: int = 5,
    seed: int = 42,
) -> SyntheticDataset:
    """
    Write a single-channel Chimera recording with events at known positions.

    Convenience wrapper around ChimeraRecordingWriter().generate(...).

    :param out_dir: Directory to write the .log/.json pair into. Created
        if it does not already exist.
    :type out_dir: Path
    :param config: Recording parameters for this channel.
    :type config: ChimeraRecordingConfig
    :param channel: Headstage number, embedded in the filename and metadata.
    :type channel: int
    :param num_events: How many events to plant on this channel.
    :type num_events: int
    :param seed: Random seed, making this channel's noise reproducible.
    :type seed: int

    :return: Dataset describing the files and their contents.
    :rtype: SyntheticDataset
    """
    return ChimeraRecordingWriter().generate(
        out_dir, config, channel=channel, num_events=num_events, seed=seed
    )


if __name__ == "__main__":
    # Generate a dataset and read it back, reporting whether the planted
    # events survive the round trip through ADC quantisation.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cfg = ChimeraRecordingConfig(duration_s=2.0, baseline=2000.0)
        ds = generate_chimera_dataset(Path(tmp), cfg, num_events=5)
        print("log:", ds.data_path, ds.data_path.stat().st_size, "bytes")
        print("json:", ds.metadata_path)
        print(
            "events:", [(e.start_time_s, e.duration_s, e.amplitude) for e in ds.events]
        )

        scale, offset = _scale_offset(cfg.tia_gain, cfg.i_offset, cfg.filter_gain)
        codes = np.fromfile(ds.data_path, dtype=np.int16)
        recovered_pA = codes.astype(np.float64) * scale + offset
        print("quantisation step (pA/code):", scale)

        first = ds.events[0]
        window = recovered_pA[
            first.start_index : first.start_index + first.length_samples
        ]
        outside = recovered_pA[: first.start_index]
        print(
            "event window mean:",
            round(window.mean(), 2),
            "pA / baseline mean:",
            round(outside.mean(), 2),
            "pA",
        )
        print("expected difference:", first.amplitude, "pA")
