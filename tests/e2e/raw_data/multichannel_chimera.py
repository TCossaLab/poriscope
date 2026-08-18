"""
Chimera-flavored convenience wrapper around the generic multichannel
generator.

A Chimera experiment spanning several headstages is stored as one
.log/.json pair per channel, all sitting in the same directory. Opening
any one of those files gives a reader the whole experiment: it derives a
filename pattern from the file it was given and globs the containing
directory for its siblings, and requires every sibling to agree on
sample rate.

The actual looping-over-channels logic lives in
generate_multichannel_dataset(), which works for any
BaseSyntheticRecordingWriter subclass (this module just supplies the
Chimera writer and config type, so callers do not have to).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from base_synthetic_recording import (
    MultichannelSyntheticDataset,
    generate_multichannel_dataset,
)
from synthetic_chimera import ChimeraRecordingConfig, ChimeraRecordingWriter


def generate_multichannel_chimera_dataset(
    out_dir: Path,
    config: ChimeraRecordingConfig,
    *,
    channels: List[int],
    num_events_per_channel: Dict[int, int] | int = 5,
    seed_base: int = 100,
) -> MultichannelSyntheticDataset:
    """
    Write one Chimera file pair per channel into a single directory.

    :param out_dir: Directory to write all channels into. Readers glob
        this directory to find the full set, so the files must not be
        split across subdirectories.
    :type out_dir: Path
    :param config: Recording parameters shared by every channel.
    :type config: ChimeraRecordingConfig
    :param channels: Headstage numbers to generate, e.g. [1, 2, 3].
    :type channels: List[int]
    :param num_events_per_channel: Either one count used for all channels,
        or a dict mapping channel number to its own count. Channels absent
        from the dict fall back to five events.
    :type num_events_per_channel: Union[Dict[int, int], int]
    :param seed_base: First random seed; each channel uses the next value up.
    :type seed_base: int

    :return: Dataset describing every channel's files and planted events.
    :rtype: MultichannelSyntheticDataset
    """
    return generate_multichannel_dataset(
        ChimeraRecordingWriter(),
        out_dir,
        config,
        channels=channels,
        num_events_per_channel=num_events_per_channel,
        seed_base=seed_base,
    )


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        cfg = ChimeraRecordingConfig(duration_s=2.0, baseline=2000.0)
        experiment = generate_multichannel_chimera_dataset(
            Path(tmp), cfg, channels=[1, 2, 3], num_events_per_channel=4
        )
        for ch, ds in experiment.channels.items():
            print(f"HS{ch}: {ds.data_path.name}, {ds.num_events} events")
        print("total events:", experiment.total_num_events)
