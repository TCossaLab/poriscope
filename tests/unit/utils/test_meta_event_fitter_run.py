"""
A fitter's run-wide post-processing runs once, after every channel of the run has finished.

``_post_process_events`` exists for work that needs the whole run - PeakFinder fits its
classifiers to every event from every channel. It used to be called per channel, so a
fitter needing the whole run had to guess whether the channel finishing was the last,
from the other channels' status flags; two channels finishing together could each see
the other unfinished, and the run-wide work never ran.

A run is the channels whose fits are in flight together. A channel joins when
``fit_events`` is *called* - the Event Analysis tab calls it for every channel before
starting any worker - so no channel can finish before its siblings have joined. The
hook runs once when the last of them ends, and only if every one of them finished: an
aborted or failed channel cancels the run-wide work for that run.
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


class RunRecorder:
    """Stands in for a fitter's run-wide hook and records each call's channels."""

    def __init__(self) -> None:
        self.runs: List[List[int]] = []

    def __call__(self, channels: Any) -> None:
        """
        :param channels: what the base passed the hook
        :type channels: Any
        """
        self.runs.append(list(channels))


@pytest.fixture
def fitter(tmp_path: Path) -> Iterator[MetaEventFitter]:
    """
    A CUSUM fitter over a two-channel events file, its run-wide hook recorded.

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
    recorder = RunRecorder()
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


def test_two_channels_requested_together_get_one_run_wide_pass(fitter) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)

    drain(first)
    assert fitter.recorder.runs == [], "ran before the other channel of its run"
    drain(second)

    assert fitter.recorder.runs == [[0, 1]]


def test_channels_fitted_in_parallel_get_one_run_wide_pass(fitter) -> None:
    generators = [fitter.fit_events(channel) for channel in (0, 1)]
    workers = [threading.Thread(target=drain, args=(g,)) for g in generators]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert fitter.recorder.runs == [[0, 1]]


def test_channels_fitted_one_after_another_are_runs_of_their_own(fitter) -> None:
    drain(fitter.fit_events(0))
    drain(fitter.fit_events(1))

    assert fitter.recorder.runs == [[0], [1]]


def test_an_aborted_channel_cancels_its_runs_pass(fitter) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    next(second)
    with pytest.raises(StopIteration):
        second.send(True)
        next(second)

    assert fitter.recorder.runs == []
    drain(fitter.fit_events(1))
    assert fitter.recorder.runs == [[1]], "the next run was not freed by the abort"


def test_a_failed_channel_cancels_its_runs_pass(fitter, monkeypatch) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    monkeypatch.setattr(
        fitter.eventloader,
        "get_num_events",
        lambda channel: (_ for _ in ()).throw(OSError("the file went away")),
    )
    with pytest.raises(OSError):
        drain(second)
    monkeypatch.undo()

    assert fitter.recorder.runs == []
    drain(fitter.fit_events(0))
    assert fitter.recorder.runs == [[0]], "the next run was not freed by the failure"


def test_the_base_hook_does_nothing_and_needs_no_override() -> None:
    assert "_post_process_events" not in MetaEventFitter.__abstractmethods__
    assert "_post_process_events" not in vars(CUSUM)
