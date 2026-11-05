"""
A fitter post-processes each channel on its own, as that channel's fitting ends.

``_post_process_events`` exists for work that needs every event of a channel at once -
PeakFinder fits its classifiers to the channel's distributions. Channels are
independent: the hook runs for one channel when its last event is fitted, sees only
that channel, and runs whether or not any other channel is being fitted. It runs before
the channel is marked fitted and before its generator yields 1.0, so a progress bar
stays up, and a database write or an event plot waits, until the channel's own
post-processing is done. An aborted or failed channel is not post-processed.
"""

import threading
from pathlib import Path
from typing import Any, Iterator, List

import pytest

from poriscope.plugins.eventfitters.CUSUM import CUSUM
from poriscope.utils.MetaEventFitter import MetaEventFitter
from tests.synthetic_data.synthetic_events_db import (
    generate_multichannel_events_database,
)
from tests.unit.plugins.conformance._recipes import (
    build_event_fitter,
    build_event_loader,
)


class ChannelRecorder:
    """Stands in for a fitter's post-processing hook and records each call's channel."""

    def __init__(self) -> None:
        self.channels: List[int] = []

    def __call__(self, channel: int) -> None:
        """
        :param channel: what the base passed the hook
        :type channel: int
        """
        self.channels.append(channel)


@pytest.fixture
def fitter(tmp_path: Path) -> Iterator[MetaEventFitter]:
    """
    A CUSUM fitter over a two-channel events file, its post-processing hook recorded.

    :param tmp_path: per-test scratch directory
    :type tmp_path: Path
    :return: the fitter, with ``recorder`` attached
    :rtype: Iterator[MetaEventFitter]
    """
    database = generate_multichannel_events_database(
        tmp_path / "two_channels.sqlite3",
        channels=[0, 1],
        num_events_per_channel=5,
    )
    loader = build_event_loader(str(database.db_path))
    fitter = build_event_fitter(CUSUM, loader)
    recorder = ChannelRecorder()
    fitter._post_process_events = recorder  # type: ignore[method-assign]
    fitter.recorder = recorder  # type: ignore[attr-defined]
    yield fitter
    loader.close_resources()


def drain(generator: Any) -> None:
    """
    Run one channel's fit to the end, as a worker does.

    :param generator: the generator ``fit_events`` returned
    :type generator: Any
    """
    for _progress in generator:
        pass


def test_each_channel_is_post_processed_as_its_own_fit_ends(fitter) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)

    drain(first)
    assert fitter.recorder.channels == [0], "channel 0 waited for channel 1"
    drain(second)
    assert fitter.recorder.channels == [0, 1]


def test_channels_fitted_in_parallel_are_each_post_processed_once(fitter) -> None:
    generators = [fitter.fit_events(channel) for channel in (0, 1)]
    workers = [threading.Thread(target=drain, args=(g,)) for g in generators]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert sorted(fitter.recorder.channels) == [0, 1]


def test_an_aborted_channel_is_not_post_processed_and_the_other_still_is(
    fitter,
) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    next(second)
    with pytest.raises(StopIteration):
        second.send(True)
        next(second)
    drain(first)

    assert fitter.recorder.channels == [0]
    assert fitter.get_eventfitting_status(1) is False
    drain(fitter.fit_events(1))
    assert fitter.recorder.channels == [0, 1]


def test_a_failed_channel_is_not_post_processed(fitter, monkeypatch) -> None:
    monkeypatch.setattr(
        fitter.eventloader,
        "get_num_events",
        lambda channel: (_ for _ in ()).throw(OSError("the file went away")),
    )
    with pytest.raises(OSError):
        drain(fitter.fit_events(0))
    monkeypatch.undo()

    assert fitter.recorder.channels == []
    assert fitter.get_eventfitting_status(0) is False
    drain(fitter.fit_events(0))
    assert fitter.recorder.channels == [0]


# A worker turns each yielded fraction into a percentage, and the tab removes a channel's
# progress bar when it reaches 100, which is the only "done" a user sees. So 1.0 must not
# be reported, nor the channel marked fitted - which is what lets a database write or an
# event plot read it - until the channel's own post-processing has finished.


def test_no_progress_reaches_complete_until_the_fit_ends(fitter) -> None:
    values = [p for p in fitter.fit_events(0)]

    assert values[-1] == 1.0
    assert all(p < 1.0 for p in values[:-1]), values
    assert len(values) > 1, "the channel reported no progress while fitting"


def test_complete_is_reported_only_after_the_channels_post_processing(fitter) -> None:
    values = [(p, len(fitter.recorder.channels)) for p in fitter.fit_events(0)]

    assert values[-1] == (1.0, 1), "1.0 was not the last value, after the hook"
    assert all(hook_runs == 0 for _p, hook_runs in values[:-1]), values


def test_a_channel_is_fitted_once_its_own_post_processing_is_done(fitter) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)

    assert fitter.get_eventfitting_status(0) is True, "channel 0 waited for channel 1"
    assert fitter.get_eventfitting_status(1) is False
    assert "good fits" in fitter.report_status(0)
    assert "incomplete" in fitter.report_status(1)
    drain(second)
    assert fitter.get_eventfitting_status(1) is True


def test_a_channel_is_not_fitted_while_its_post_processing_runs(fitter) -> None:
    seen = []

    def hook(channel: int) -> None:
        seen.append(fitter.get_eventfitting_status(channel))

    fitter._post_process_events = hook
    drain(fitter.fit_events(0))

    assert seen == [False], "the channel was writable mid-step"
    assert fitter.get_eventfitting_status(0) is True


def test_a_failed_post_processing_step_leaves_the_channel_unfitted(fitter) -> None:
    def hook(channel: int) -> None:
        raise RuntimeError("the classifier did not converge")

    fitter._post_process_events = hook
    with pytest.raises(RuntimeError, match="did not converge"):
        drain(fitter.fit_events(0))

    assert fitter.get_eventfitting_status(0) is False
    assert "incomplete" in fitter.report_status(0)


def test_an_aborted_channel_still_ends_at_complete_and_is_not_fitted(fitter) -> None:
    generator = fitter.fit_events(0)
    next(generator)

    assert generator.send(True) == 1.0
    with pytest.raises(StopIteration):
        next(generator)
    assert fitter.get_eventfitting_status(0) is False


def test_a_silent_fit_reports_only_that_it_is_complete(fitter) -> None:
    assert list(fitter.fit_events(0, silent=True)) == [1.0]
    assert fitter.get_eventfitting_status(0) is True
    assert fitter.recorder.channels == [0]


def test_the_base_hook_does_nothing_and_needs_no_override() -> None:
    assert "_post_process_events" not in MetaEventFitter.__abstractmethods__
    assert "_post_process_events" not in vars(CUSUM)
