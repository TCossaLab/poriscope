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


# A worker turns each yielded fraction into a percentage, and the tab removes a channel's
# progress bar when it reaches 100, which is the only "done" a user sees. So 1.0 must not
# be reported, nor the channel marked fitted - which is what lets a database write or an
# event plot read it - until the run-wide step that refines its results has finished.


def progress_with_hook_state(generator: Any, fitter: MetaEventFitter) -> List[Any]:
    """
    Run one channel's fit to the end, noting whether the run-wide step had run at each value.

    :param generator: the generator ``fit_events`` returned
    :type generator: Any
    :param fitter: the fitter, with ``recorder`` attached
    :type fitter: MetaEventFitter
    :return: ``(fraction, runs recorded so far)`` per yielded value
    :rtype: List[Any]
    """
    return [(p, len(fitter.recorder.runs)) for p in generator]


def test_no_progress_reaches_complete_until_the_fit_ends(fitter) -> None:
    values = [p for p in fitter.fit_events(0)]

    assert values[-1] == 1.0
    assert all(p < 1.0 for p in values[:-1]), values
    assert len(values) > 1, "the channel reported no progress while fitting"


def test_the_last_channel_reports_complete_only_after_the_run_wide_step(fitter) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)

    values = progress_with_hook_state(second, fitter)

    assert values[-1] == (1.0, 1), "1.0 was not the last value, after the step"
    assert all(p < 1.0 for p, _runs in values[:-1]), values


def test_a_channel_that_finishes_first_is_not_fitted_until_its_run_ends(fitter) -> None:
    # The run-wide step may rewrite any channel of the run, so one that finished
    # early is not done - nor readable by a database write - until the run is over.
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)

    assert fitter.get_eventfitting_status(0) is False
    drain(second)
    assert fitter.get_eventfitting_status(0) is True
    assert fitter.get_eventfitting_status(1) is True


def test_a_channel_waiting_for_its_run_reports_that_it_is_waiting(fitter) -> None:
    # The tab shows report_status(channel) as each channel's worker ends; a channel
    # that fitted cleanly and is only waiting for its run must not read as incomplete.
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)

    waiting = fitter.report_status(0)
    assert "incomplete" not in waiting, waiting
    assert "waiting" in waiting, waiting
    drain(second)
    assert "good fits" in fitter.report_status(0)


def test_a_channel_refitted_and_aborted_mid_run_is_not_marked_at_its_end(
    fitter,
) -> None:
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    again = fitter.fit_events(0)
    next(again)
    again.send(True)
    drain(second)

    assert (
        fitter.get_eventfitting_status(0) is False
    ), "an aborted, reset channel was marked"
    assert "incomplete" in fitter.report_status(0)


def test_a_failed_run_reports_its_channels_as_incomplete(fitter) -> None:
    def hook(channels: List[int]) -> None:
        raise RuntimeError("the classifier did not converge")

    fitter._post_process_events = hook
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    with pytest.raises(RuntimeError):
        drain(second)

    assert "incomplete" in fitter.report_status(0)


def test_no_channel_of_the_run_is_fitted_while_the_run_wide_step_runs(fitter) -> None:
    seen = []

    def hook(channels: List[int]) -> None:
        seen.append({ch: fitter.get_eventfitting_status(ch) for ch in channels})
        fitter.recorder.runs.append(channels)

    fitter._post_process_events = hook
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    drain(second)

    assert seen == [{0: False, 1: False}], "a channel was writable mid-step"
    assert fitter.get_eventfitting_status(0) and fitter.get_eventfitting_status(1)


def test_a_failed_run_wide_step_leaves_the_run_unfitted(fitter) -> None:
    def hook(channels: List[int]) -> None:
        raise RuntimeError("the classifier did not converge")

    fitter._post_process_events = hook
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    with pytest.raises(RuntimeError, match="did not converge"):
        drain(second)

    assert fitter.get_eventfitting_status(0) is False
    assert fitter.get_eventfitting_status(1) is False


def test_a_run_with_an_aborted_channel_marks_the_finished_ones_as_it_ends(
    fitter,
) -> None:
    # With the run-wide step skipped, nothing more will change the finished channels.
    first = fitter.fit_events(0)
    second = fitter.fit_events(1)
    drain(first)
    next(second)
    second.send(True)

    assert fitter.get_eventfitting_status(0) is True
    assert fitter.get_eventfitting_status(1) is False


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


def test_the_base_hook_does_nothing_and_needs_no_override() -> None:
    assert "_post_process_events" not in MetaEventFitter.__abstractmethods__
    assert "_post_process_events" not in vars(CUSUM)
