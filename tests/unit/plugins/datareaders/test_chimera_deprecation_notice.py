"""
``ChimeraReader20240101`` says it is deprecated where its users will see it.

The changelog carries the notice too, but that reaches whoever reads changelogs, not
whoever opens a 2024-01 Chimera file every day. The sidebar status text a reader reports
when it is created is the one place every user of it looks, so the notice goes there -
once per channel, and only at creation, not on every later status refresh.
"""

import gc

import pytest

from poriscope.plugins.datareaders.ChimeraReader20240101 import ChimeraReader20240101
from poriscope.plugins.datareaders.ChimeraReader20240501 import ChimeraReader20240501
from tests.unit.plugins.conformance._recipes import (
    build_any_reader,
    build_reader_dataset,
)

NOTICE = "ChimeraReader20240101 is deprecated"


@pytest.fixture
def reader_2024_01(tmp_path):
    """
    A ``ChimeraReader20240101`` over a synthetic 2024-01 recording.

    :param tmp_path: Pytest's per-test temporary directory.
    :type tmp_path: pathlib.Path
    :yield: The opened reader and the channel its recording holds.
    """
    dataset = build_reader_dataset(ChimeraReader20240101, tmp_path)
    reader = build_any_reader(ChimeraReader20240101, dataset)
    yield reader, reader.get_channels()[0]
    reader.close_resources()
    del reader
    gc.collect()


@pytest.fixture
def reader_2024_05(tmp_path):
    """
    A ``ChimeraReader20240501`` over a synthetic 2024-05 recording.

    :param tmp_path: Pytest's per-test temporary directory.
    :type tmp_path: pathlib.Path
    :yield: The opened reader and the channel its recording holds.
    """
    dataset = build_reader_dataset(ChimeraReader20240501, tmp_path)
    reader = build_any_reader(ChimeraReader20240501, dataset)
    yield reader, reader.get_channels()[0]
    reader.close_resources()
    del reader
    gc.collect()


def test_the_creation_report_names_the_deprecation_and_the_replacement(
    reader_2024_01,
):
    reader, channel = reader_2024_01
    report = reader.report_channel_status(channel, init=True)
    assert NOTICE in report
    assert "ChimeraReader20240501" in report
    # The ordinary duration and samplerate line is kept, not replaced.
    assert f"Ch{channel}:" in report and "Hz" in report


def test_a_later_status_refresh_does_not_repeat_it(reader_2024_01):
    reader, channel = reader_2024_01
    assert reader.report_channel_status(channel, init=False) == ""


def test_the_all_channels_report_carries_one_notice_per_channel(reader_2024_01):
    reader, _ = reader_2024_01
    report = reader.report_channel_status(None, init=True)
    assert report.count(NOTICE) == len(reader.get_channels())


def test_the_supported_reader_reports_no_notice(reader_2024_05):
    reader, channel = reader_2024_05
    assert "deprecated" not in reader.report_channel_status(channel, init=True)
