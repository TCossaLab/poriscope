"""
Pytest fixtures providing synthetic Chimera recordings as test data.

Each fixture writes a real .log/.json pair to a temporary directory and
returns a description of what was written, including the exact position
and amplitude of every event planted in the signal. Tests can therefore
assert against known ground truth (how many events should be detected,
where they should be) rather than settling for "something was found".

Generation happens per test, so nothing is checked into the repository
and there is no shared state between tests.

Default signal parameters
--------------------------
The defaults describe a plausible open-pore recording with clean, obvious
blockage events:

* Baseline 2000 pA. Event finders reject any chunk whose baseline
  magnitude fails to clear both a few standard deviations of noise and
  the configured detection threshold (a recording sitting near zero
  reads as "no voltage applied" and is skipped entirely). A realistic
  open-pore current avoids that.
* Noise 15 pA RMS, small enough that 400 pA events stand well clear of
  it, so detection outcomes reflect the code under test rather than luck.
* Events -400 pA deep, 500 us long, comfortably inside the duration
  bounds a finder is typically configured with.
"""

from __future__ import annotations

from typing import Dict

import pytest
from base_synthetic_recording import MultichannelSyntheticDataset, SyntheticDataset
from multichannel_chimera import generate_multichannel_chimera_dataset
from synthetic_chimera import ChimeraRecordingConfig, generate_chimera_dataset

DEFAULT_BASELINE_PA = 2000.0
DEFAULT_NOISE_STD_PA = 15.0
DEFAULT_EVENT_AMPLITUDE_PA = -400.0
DEFAULT_EVENT_DURATION_S = 0.0005
DEFAULT_SAMPLERATE_HZ = 4_000_000.0


def _default_config(**overrides) -> ChimeraRecordingConfig:
    """
    Build a ChimeraRecordingConfig with this module's default signal
    parameters, letting individual fixtures/tests override any field.

    :param overrides: Field values to override on top of the defaults.
    :type overrides: Any

    :return: A config ready to pass to generate_chimera_dataset() or
        generate_multichannel_chimera_dataset().
    :rtype: ChimeraRecordingConfig
    """
    params = dict(
        base_name="synthetic",
        samplerate=DEFAULT_SAMPLERATE_HZ,
        duration_s=2.0,
        baseline=DEFAULT_BASELINE_PA,
        noise_std=DEFAULT_NOISE_STD_PA,
        event_amplitude=DEFAULT_EVENT_AMPLITUDE_PA,
        event_duration_s=DEFAULT_EVENT_DURATION_S,
    )
    params.update(overrides)
    return ChimeraRecordingConfig(**params)


@pytest.fixture
def synthetic_chimera_dataset(tmp_path) -> SyntheticDataset:
    """
    A single-channel recording with five evenly spaced events.

    Two seconds at 4 MHz on channel 3. Suitable for any test that needs
    one channel of well-behaved data.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Dataset describing the files written and the events planted
        in them.
    :rtype: SyntheticDataset
    """
    return generate_chimera_dataset(
        tmp_path / "synthetic_data",
        _default_config(),
        channel=3,
        num_events=5,
        seed=42,
    )


@pytest.fixture
def make_synthetic_chimera_dataset(tmp_path):
    """
    Build single-channel recordings with custom parameters.

    Use when a test needs something the default fixture doesn't provide
    (a different event count, a longer recording, an empty channel)::

        def test_handles_no_events(make_synthetic_chimera_dataset):
            ds = make_synthetic_chimera_dataset(num_events=0)

    Config fields (baseline, noise_std, samplerate, ...) and generation
    arguments (channel, num_events, seed) can both be overridden by
    keyword; config fields are recognized automatically. Each call writes
    to its own directory, so a test may create several datasets without
    them colliding.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: A factory accepting any field of ChimeraRecordingConfig plus
        channel, num_events, and seed.
    :rtype: Callable[..., SyntheticDataset]
    """
    config_fields = set(ChimeraRecordingConfig.__dataclass_fields__)

    def _make(**overrides) -> SyntheticDataset:
        config_overrides = {k: v for k, v in overrides.items() if k in config_fields}
        gen_overrides = {k: v for k, v in overrides.items() if k not in config_fields}

        gen_params = dict(channel=3, num_events=5, seed=42)
        gen_params.update(gen_overrides)

        out_dir = tmp_path / f"synthetic_data_{len(list(tmp_path.glob('synthetic_data_*')))}"
        return generate_chimera_dataset(out_dir, _default_config(**config_overrides), **gen_params)

    return _make


@pytest.fixture
def synthetic_multichannel_dataset(tmp_path) -> MultichannelSyntheticDataset:
    """
    A three-channel recording with differing event counts per channel.

    Channels 1, 2 and 3 carry zero, four and six events respectively. The
    empty channel is deliberate: it exercises the case where a reader
    exposes a channel that yields no events, alongside channels that do.

    Readers discover the whole set from any one of its files, so a test
    typically opens one channel's .log path and gets all three.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: Dataset describing every channel's files and planted events::

            datasets = synthetic_multichannel_dataset
            assert datasets[1].num_events == 0
            reader_input = datasets[2].data_path   # reader finds all channels
    :rtype: MultichannelSyntheticDataset
    """
    return generate_multichannel_chimera_dataset(
        tmp_path / "synthetic_multichannel",
        _default_config(),
        channels=[1, 2, 3],
        num_events_per_channel={1: 0, 2: 4, 3: 6},
    )


@pytest.fixture
def make_synthetic_multichannel_dataset(tmp_path):
    """
    Build multi-channel recordings with custom parameters.

    Use when a test needs a different channel layout than the default::

        def test_four_channels(make_synthetic_multichannel_dataset):
            datasets = make_synthetic_multichannel_dataset(
                channels=[1, 2, 3, 4],
                num_events_per_channel={1: 0, 2: 3, 3: 3, 4: 8},
            )

    Config fields and generation arguments (channels, num_events_per_channel,
    seed_base) can both be overridden by keyword; config fields are
    recognized automatically.

    :param tmp_path: Pytest-provided temporary directory, unique per test.
    :type tmp_path: pathlib.Path

    :return: A factory accepting any field of ChimeraRecordingConfig plus
        channels, num_events_per_channel, and seed_base.
    :rtype: Callable[..., MultichannelSyntheticDataset]
    """
    config_fields = set(ChimeraRecordingConfig.__dataclass_fields__)

    def _make(**overrides) -> MultichannelSyntheticDataset:
        config_overrides = {k: v for k, v in overrides.items() if k in config_fields}
        gen_overrides = {k: v for k, v in overrides.items() if k not in config_fields}

        gen_params: Dict = dict(
            channels=[1, 2, 3], num_events_per_channel={1: 0, 2: 4, 3: 6}
        )
        gen_params.update(gen_overrides)

        n_prior = len(list(tmp_path.glob("synthetic_multichannel_*")))
        out_dir = tmp_path / f"synthetic_multichannel_{n_prior}"
        return generate_multichannel_chimera_dataset(
            out_dir, _default_config(**config_overrides), **gen_params
        )

    return _make
