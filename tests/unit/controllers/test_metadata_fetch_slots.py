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

"""
``MetadataController``'s Step 4a fetch slots: what they call, and what they report.

These are the methods that answer the metadata tab's intents by calling the loader
directly - the two subset loaders, the two single-value lookups, the event-plot chain
and the CSV export. Every one of them replaced a ``global_signal`` round trip whose
failures the bus swallowed, so the behaviour worth pinning is as much *which failure
is reported* as it is the happy path.

**Why this file exists.** The View-side tests for these conversions stub the answer -
``test_metadata_view``'s ``canned_*`` values stand in for the Controller - so not one
of them can see what the Controller actually asks the loader, or what it does when the
loader says no. ``load_metadata_subset`` and ``load_event_subset`` landed with no test
that could: a wrong call signature or a swallowed failure would have satisfied the
whole suite. They are covered here alongside the four slots added with them.

Kept out of ``test_metadata_controller`` because that module covers the relay methods
this step is deleting, and out of ``test_promoted_controller_methods`` because none of
these is shared with the protein tab - ``ProteinView`` never builds a metadata query.
"""

import numpy as np
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.MetadataModel import MetadataModel
from tests.unit.controllers._recording_model import (
    RecordingModel,
    recording_tab_model,
)

pytestmark = pytest.mark.characterization

#: The scope a metadata tab request carries: one experiment, one channel.
SCOPE = {"exp1": [1]}


@pytest.fixture
def controller(mocker: MockerFixture) -> MetadataController:
    """
    A bare ``MetadataController`` with a mocked View and no Model yet.

    Built with ``__new__`` so no Qt object exists behind it, which is also why
    ``add_text_to_display`` is replaced on the instance: emitting the real class-level
    Signal from an uninitialised QObject raises "Signal source has been deleted".

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: the controller under test
    :rtype: MetadataController
    """
    ctrl = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    return ctrl


def panel_text(controller: MetadataController) -> str:
    """
    Everything the controller put on the status panel, joined.

    :param controller: the controller under test
    :type controller: MetadataController
    :return: the concatenated message text
    :rtype: str
    """
    return "\n".join(
        call.args[0] for call in controller.add_text_to_display.emit.call_args_list
    )


# ===========================================================================
# load_metadata_subset - the query, the rows and the units, or none of them
# ===========================================================================


class TestLoadMetadataSubset:
    """
    Landed in Step 4a's ``_overlay_plot`` commit with no Controller-side test.
    """

    ANSWERS = {
        "construct_metadata_query": ("SELECT duration FROM events", "", "events"),
        "load_metadata": pd.DataFrame({"duration": [1.0, 2.0]}),
        "get_column_units": "ms",
    }

    def test_it_hands_over_query_rows_and_units_together(
        self, controller: MetadataController
    ) -> None:
        """
        All three answers, and one units lookup per column.
        """
        controller.model = RecordingModel(dict(self.ANSWERS))

        controller.load_metadata_subset("ldr", ["duration", "amplitude"], "", SCOPE)

        controller.view.set_query.assert_called_once_with(
            "SELECT duration FROM events", "events"
        )
        controller.view.update_plot_data.assert_called_once()
        controller.view.set_column_units.assert_called_once_with(["ms", "ms"])
        assert len(controller.model.calls_to("get_column_units")) == 2

    def test_the_columns_and_scope_reach_the_loader_unchanged(
        self, controller: MetadataController
    ) -> None:
        """
        Spread as positional arguments now, where the bus passed one tuple.
        """
        controller.model = RecordingModel(dict(self.ANSWERS))

        controller.load_metadata_subset("ldr", ["duration"], "duration < 300", SCOPE)

        (built,) = controller.model.calls_to("construct_metadata_query")
        assert built == (["duration"], "duration < 300", SCOPE)

    def test_a_failed_build_reports_and_sets_nothing(
        self, controller: MetadataController
    ) -> None:
        """
        The fault the commit fixed: the View used to read the previous subset's query
        back off an attribute and plot those rows under this subset's label.
        """
        controller.model = RecordingModel(
            {"construct_metadata_query": ValueError("no such column: dwel")}
        )

        controller.load_metadata_subset("ldr", ["dwel"], "", SCOPE)

        controller.view.set_query.assert_not_called()
        controller.view.update_plot_data.assert_not_called()
        controller.view.set_column_units.assert_not_called()
        assert "dwel" in panel_text(controller)

    def test_an_empty_query_reports_the_loaders_own_reason(
        self, controller: MetadataController
    ) -> None:
        """
        ``construct_metadata_query`` returns its complaint in the debug slot rather
        than raising, so that message is what the panel should carry.
        """
        controller.model = RecordingModel(
            {"construct_metadata_query": ("", "the filter names no known column", "")}
        )

        controller.load_metadata_subset("ldr", ["duration"], "bad", SCOPE)

        assert "the filter names no known column" in panel_text(controller)
        controller.view.set_query.assert_not_called()

    def test_a_failed_load_sets_nothing_either(
        self, controller: MetadataController
    ) -> None:
        """
        A half-set bundle would break the View's "not fetched" versus "fetched and
        empty" distinction, so the query is not handed over on its own.
        """
        controller.model = RecordingModel(
            {
                "construct_metadata_query": ("SELECT 1", "", "events"),
                "load_metadata": RuntimeError("database is locked"),
            }
        )

        controller.load_metadata_subset("ldr", ["duration"], "", SCOPE)

        controller.view.set_query.assert_not_called()
        assert "database is locked" in panel_text(controller)

    def test_the_query_that_ran_is_echoed_once(
        self, controller: MetadataController
    ) -> None:
        """
        Deduplicated because one plot builds a query per experiment and channel, and
        replotting the same subset is the common case.
        """
        controller.model = RecordingModel(dict(self.ANSWERS))

        controller.load_metadata_subset("ldr", ["duration"], "", SCOPE)
        controller.load_metadata_subset("ldr", ["duration"], "", SCOPE)

        echoes = [
            call
            for call in controller.add_text_to_display.emit.call_args_list
            if call.args[0].startswith("SQL (events):")
        ]
        assert len(echoes) == 1
        assert "SELECT duration FROM events" in echoes[0].args[0]


# ===========================================================================
# build_all_points_histogram - the event-data fetch and its tally
# ===========================================================================


class TestBuildAllPointsHistogram:
    """
    The event-data fetch, and the tally it now feeds.

    Step 4's closeout replaced ``load_event_subset``: the generator used to be handed
    to the View, which walked it twice inside the widget. The Controller keeps it and
    passes it to the Model, so what has to be pinned here is that the query and the
    counts arrive together and that every way the round trip can fail leaves the query
    unset - which is the only thing the View has to tell a failure by.
    """

    #: One event, whose first three samples are the pre-event baseline.
    EVENT = {
        "raw_data": np.array([5.0, 5.0, 5.0, 12.0, 13.0, 14.0]),
        "filtered_data": np.array([7.0, 7.0, 7.0, 20.0, 21.0, 22.0]),
        "padding_before": 300.0,  # 300 us * 10 kHz / 1e6 = 3 samples
        "padding_after": 0.0,
        "samplerate": 10000.0,
    }

    def test_the_query_and_the_counts_reach_the_view(
        self, controller: MetadataController
    ) -> None:
        """
        The happy path, against the real Model rather than a stub of it.
        """
        controller.model = recording_tab_model(
            MetadataModel,
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": iter([dict(self.EVENT)]),
            },
        )

        controller.build_all_points_histogram(
            "ldr",
            "duration < 300",
            SCOPE,
            "Raw All Points Histogram",
            [4],
            False,
            None,
            None,
            "a label",
        )

        controller.view.set_event_query.assert_called_once_with("SELECT * FROM events")
        controller.view.set_all_points_histogram.assert_called_once()
        args = controller.view.set_all_points_histogram.call_args[0]
        assert len(args[0]) == 4
        assert args[1].sum() == 6
        assert args[4] == "Raw All Points Histogram"
        assert args[5] == "a label"

    def test_the_limits_it_was_given_are_widened_not_replaced(
        self, controller: MetadataController
    ) -> None:
        """
        The shared limits are what makes overlaid subsets comparable, so a second
        subset inside an existing range must not shrink it.
        """
        controller.model = recording_tab_model(
            MetadataModel,
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": iter([dict(self.EVENT)]),
            },
        )

        controller.build_all_points_histogram(
            "ldr",
            "",
            SCOPE,
            "Raw All Points Histogram",
            [4],
            False,
            -100.0,
            100.0,
            "a label",
        )

        args = controller.view.set_all_points_histogram.call_args[0]
        assert args[2] == -100.0
        assert args[3] == 100.0

    def test_a_query_the_loader_refuses_to_build_stops_the_plot(
        self, controller: MetadataController
    ) -> None:
        """
        ``construct_event_data_query`` reports a filter it cannot build by returning
        ``("", debug)``, and that refusal has to stop the plot and reach the user.

        The guard reading ``if not query`` was written against the whole return value
        rather than against the query half, and a 2-tuple is always truthy - so the
        refusal was invisible and the tab went on to load and plot.
        """
        controller.model = RecordingModel(
            {
                "construct_event_data_query": ("", "no such column: nope"),
                "load_event_data": iter([]),
            }
        )

        controller.build_all_points_histogram(
            "ldr",
            "nope > 1",
            SCOPE,
            "Raw All Points Histogram",
            [4],
            False,
            None,
            None,
            "a label",
        )

        assert controller.model.calls_to("load_event_data") == []
        controller.view.set_event_query.assert_not_called()
        controller.view.set_all_points_histogram.assert_not_called()
        assert "no such column: nope" in panel_text(controller)

    def test_a_failed_load_reports_and_draws_nothing(
        self, controller: MetadataController
    ) -> None:
        """
        The View clears the query before asking, so not setting it is what refuses
        the plot: before Step 4a a failed load replotted the previous subset.
        """
        controller.model = RecordingModel(
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": RuntimeError("no such table: events"),
            }
        )

        controller.build_all_points_histogram(
            "ldr",
            "",
            SCOPE,
            "Raw All Points Histogram",
            [4],
            False,
            None,
            None,
            "a label",
        )

        controller.view.set_event_query.assert_not_called()
        controller.view.set_all_points_histogram.assert_not_called()
        assert "no such table: events" in panel_text(controller)

    def test_a_tally_that_raises_is_reported_rather_than_escaping(
        self, controller: MetadataController
    ) -> None:
        """
        A bin request the Model refuses used to raise out of a Qt slot, because
        nothing between ``_overlay_plot`` and the widget caught it. An empty bins
        list is the reachable case: ``build_all_points_histogram`` raises ValueError
        on it rather than guessing.
        """
        controller.model = recording_tab_model(
            MetadataModel,
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": iter([dict(self.EVENT)]),
            },
        )

        controller.build_all_points_histogram(
            "ldr",
            "",
            SCOPE,
            "Raw All Points Histogram",
            [],
            False,
            None,
            None,
            "a label",
        )

        controller.view.set_event_query.assert_not_called()
        controller.view.set_all_points_histogram.assert_not_called()
        assert "Invalid bins entry" in panel_text(controller)


# ===========================================================================
# build_event_overlay - the other half of the event-data fetch
# ===========================================================================


class TestBuildEventOverlay:
    """
    The same fetch, reduced to one normalised trace per event.
    """

    EVENT = {
        "raw_data": np.array([5.0, 5.0, 5.0, 12.0, 13.0, 5.0]),
        "filtered_data": np.array([7.0, 7.0, 7.0, 20.0, 21.0, 7.0]),
        "padding_before": 300.0,
        "padding_after": 100.0,
        "samplerate": 10000.0,
    }

    def test_the_traces_reach_the_view(self, controller: MetadataController) -> None:
        """
        One pair per event, and the query alongside them.
        """
        controller.model = recording_tab_model(
            MetadataModel,
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": iter([dict(self.EVENT), dict(self.EVENT)]),
            },
        )

        controller.build_event_overlay("ldr", "", SCOPE, "Raw Event Overlay")

        controller.view.set_event_query.assert_called_once_with("SELECT * FROM events")
        traces = controller.view.set_event_overlay.call_args[0][0]
        assert len(traces) == 2
        time, data = traces[0]
        assert len(time) == len(data) == 6
        # The event proper starts where the padding ends, which is time zero.
        assert time[3] == pytest.approx(0.0)

    def test_a_failed_load_reports_and_draws_nothing(
        self, controller: MetadataController
    ) -> None:
        """
        The same refusal as the histogram's, through the same shared fetch.
        """
        controller.model = RecordingModel(
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": RuntimeError("no such table: events"),
            }
        )

        controller.build_event_overlay("ldr", "", SCOPE, "Raw Event Overlay")

        controller.view.set_event_query.assert_not_called()
        controller.view.set_event_overlay.assert_not_called()
        assert "no such table: events" in panel_text(controller)

    def test_an_unknown_plot_type_is_reported_rather_than_escaping(
        self, controller: MetadataController
    ) -> None:
        """
        Neither trace is named by an unrecognised plot type, which the Model refuses
        rather than silently redrawing the previous event's samples - which is what
        the two-branch ``if`` it replaced did, from the second event onwards.
        """
        controller.model = recording_tab_model(
            MetadataModel,
            {
                "construct_event_data_query": ("SELECT * FROM events", ""),
                "load_event_data": iter([dict(self.EVENT)]),
            },
        )

        controller.build_event_overlay("ldr", "", SCOPE, "Sideways Event Overlay")

        controller.view.set_event_overlay.assert_not_called()
        assert "Unknown plot_type" in panel_text(controller)


# ===========================================================================
# request_column_type - the categorical-histogram guard's input
# ===========================================================================


class TestRequestColumnType:
    """
    One lookup, whose failure must read as "not categorical".
    """

    def test_the_type_reaches_the_view(self, controller: MetadataController) -> None:
        """ """
        controller.model = RecordingModel({"get_column_type": "TEXT"})

        controller.request_column_type("ldr", "category")

        controller.view.set_column_type.assert_called_once_with("TEXT")

    def test_a_failed_lookup_leaves_the_view_cleared(
        self, controller: MetadataController
    ) -> None:
        """
        The View cleared it to None before asking, and the guard refuses a None type,
        so declining to answer is what stops the plot.
        """
        controller.model = RecordingModel(
            {"get_column_type": RuntimeError("no such column")}
        )

        controller.request_column_type("ldr", "nope")

        controller.view.set_column_type.assert_not_called()
        assert controller.logger.error.called


# ===========================================================================
# load_event_plot_data - the three-emit chain, run in one place
# ===========================================================================


class TestLoadEventPlotData:
    """
    Resolve the experiment, resolve the ids within scope, load exactly those rows.
    """

    ANSWERS = {
        "get_experiment_id_by_name": 7,
        "query_database_directly": pd.DataFrame({"id": [11, 12]}),
        "load_event_data": iter([{"event_id": 5}]),
    }

    def test_the_id_query_is_scoped_to_experiment_and_channel(
        self, controller: MetadataController
    ) -> None:
        """
        The reason the middle query exists: ``event_id`` is unique only within a
        channel, so an unscoped match returns another channel's rows.
        """
        controller.model = recording_tab_model(MetadataModel, dict(self.ANSWERS))

        controller.load_event_plot_data("ldr", [5, 10], "exp1", 1, SCOPE, "events")

        (resolved,) = controller.model.calls_to("query_database_directly")
        query = resolved[0]
        assert "event_id IN (5,10)" in query
        assert "experiment_id = 7" in query
        assert "channel_id = 1" in query

    def test_the_resolved_ids_become_the_load_filter(
        self, controller: MetadataController
    ) -> None:
        """
        ``e.id IN (...)`` is what ``load_event_data`` is given, with the scope beside
        it, exactly as the bus passed them.
        """
        answers = dict(self.ANSWERS)
        generator = iter([{"event_id": 5}])
        answers["load_event_data"] = generator
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        (loaded,) = controller.model.calls_to("load_event_data")
        assert loaded == ("e.id IN (11,12)", SCOPE)
        controller.view.set_event_plot_data_generator.assert_called_once_with(generator)

    def test_an_unresolvable_experiment_stops_the_plot(
        self, controller: MetadataController
    ) -> None:
        """
        The behaviour change. The bus swallowed the failure, the id came back None and
        the query ran *unscoped*, returning whatever channel happened to share the
        event_id - the same fault class as plotting the previous subset.
        """
        answers = dict(self.ANSWERS)
        answers["get_experiment_id_by_name"] = None
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("query_database_directly") == []
        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "exp1" in panel_text(controller)

    def test_a_raising_experiment_lookup_stops_the_plot(
        self, controller: MetadataController
    ) -> None:
        """ """
        answers = dict(self.ANSWERS)
        answers["get_experiment_id_by_name"] = RuntimeError("database is locked")
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("query_database_directly") == []
        assert "database is locked" in panel_text(controller)

    def test_no_matching_rows_is_reported_as_no_data(
        self, controller: MetadataController
    ) -> None:
        """
        The message the View used to make, made here now, so the View can return
        without saying the same thing twice.
        """
        answers = dict(self.ANSWERS)
        answers["query_database_directly"] = pd.DataFrame()
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("load_event_data") == []
        assert "No data available" in panel_text(controller)

    def test_rows_without_an_id_column_are_a_logged_fault(
        self, controller: MetadataController
    ) -> None:
        """
        Distinct from an empty subset: the loader returned rows but not the column it
        was asked for, which would have raised on the read. Taken from the resolution
        ``_rebuild_event_id_cache``'s promotion settled on.
        """
        answers = dict(self.ANSWERS)
        answers["query_database_directly"] = pd.DataFrame({"event_id": [5]})
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("load_event_data") == []
        controller.view.set_event_plot_data_generator.assert_not_called()
        assert controller.logger.error.called

    def test_a_failed_load_hands_over_nothing(
        self, controller: MetadataController
    ) -> None:
        """ """
        answers = dict(self.ANSWERS)
        answers["load_event_data"] = RuntimeError("cannot read event blob")
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "cannot read event blob" in panel_text(controller)

    def test_no_generator_is_reported_rather_than_passed_on(
        self, controller: MetadataController
    ) -> None:
        """
        ``load_event_data`` returns None when it could not build its own query.
        """
        answers = dict(self.ANSWERS)
        answers["load_event_data"] = None
        controller.model = recording_tab_model(MetadataModel, answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "No data available" in panel_text(controller)

    def test_a_missing_experiment_name_scopes_by_channel_alone(
        self, controller: MetadataController
    ) -> None:
        """
        The experiment is optional in the request, and the channel is scoped
        independently of it - where the bus's version appended the channel only
        *inside* the branch that had resolved an experiment id.
        """
        controller.model = recording_tab_model(MetadataModel, dict(self.ANSWERS))

        controller.load_event_plot_data("ldr", [5], None, 1, SCOPE, "events")

        assert controller.model.calls_to("get_experiment_id_by_name") == []
        (resolved,) = controller.model.calls_to("query_database_directly")
        assert "experiment_id" not in resolved[0]
        assert "channel_id = 1" in resolved[0]


# ===========================================================================
# request_plot_features
# ===========================================================================


class TestRequestPlotFeatures:
    """
    One lookup per plotted event, whose failure must not abandon the plot.
    """

    FEATURES = (
        [1.0, 2.0],
        [3.0],
        [(4.0, 5.0)],
        ["start", "end"],
        ["baseline"],
        ["peak"],
    )

    def test_the_six_features_reach_the_view(
        self, controller: MetadataController
    ) -> None:
        """
        Unpacked here now, where the bus splatted the tuple across the callback's
        parameters based on the loader's declared return type.
        """
        controller.model = RecordingModel({"get_plot_features": self.FEATURES})

        controller.request_plot_features("ldr", 7, 1, 5)

        controller.view.update_plot_features.assert_called_once_with(*self.FEATURES)
        (asked,) = controller.model.calls_to("get_plot_features")
        assert asked == (7, 1, 5)

    def test_a_failed_lookup_is_logged_and_the_view_left_alone(
        self, controller: MetadataController
    ) -> None:
        """
        The View clears the six before each event and reads them back after, so an
        event whose lookup failed is plotted without features rather than with the
        previous event's.
        """
        controller.model = RecordingModel(
            {"get_plot_features": KeyError("no such event")}
        )

        controller.request_plot_features("ldr", 7, 1, 5)

        controller.view.update_plot_features.assert_not_called()
        assert controller.logger.error.called

    def test_mismatched_labels_do_not_escape_the_slot(
        self, controller: MetadataController
    ) -> None:
        """
        ``update_features``' own validation raises, and one fitter returning labels
        that do not match its features should cost that event, not the plot. An
        exception escaping here would not reach the View either - a Qt slot's does not
        propagate back to the emitter - it would just vanish into ``sys.excepthook``.
        """
        controller.model = RecordingModel(
            {"get_plot_features": ([1.0, 2.0], None, None, ["only one"], None, None)}
        )

        controller.request_plot_features("ldr", 7, 1, 5)

        controller.view.update_plot_features.assert_not_called()
        assert controller.logger.error.called


# ===========================================================================
# export_csv_subset
# ===========================================================================


class TestExportCsvSubset:
    """
    Not an emit-then-read: the plugin returns a progress generator to be run.
    """

    def test_the_generator_is_staged_under_the_export_index_and_run(
        self, controller: MetadataController
    ) -> None:
        """
        The index, the loader key and the metaclass travelled as the bus's
        ``ret_args`` into ``set_generator``; they are arguments now.
        """
        generator = iter([0.5, 1.0])
        controller.model = RecordingModel(
            {"count_subset_events": 12, "export_subset_to_csv": generator}
        )
        staged: list = []
        ran: list = []
        controller.model.set_generator = (  # type: ignore[attr-defined]
            lambda *args: staged.append(args)
        )
        controller.model.run_generators = (  # type: ignore[attr-defined]
            lambda key: ran.append(key)
        )

        controller.export_csv_subset(
            "ldr", "/out", "Subset_3", "duration < 300", SCOPE, 3
        )

        (exported,) = controller.model.calls_to("export_subset_to_csv")
        assert exported == ("/out", "Subset_3", "duration < 300", SCOPE)
        assert staged == [(generator, 3, "ldr", "MetaDatabaseLoader")]
        assert ran == ["ldr"]
        controller.view.on_subset_export_started.assert_called_once()

    def test_the_subset_is_counted_before_anything_is_staged(
        self, controller: MetadataController
    ) -> None:
        """
        The count has to run against the same filter and scope the export gets, or it
        is answering a question about a different subset.

        Written from ``MetaDatabaseLoader.count_subset_events(conditions,
        experiments_and_channels)`` rather than from the calling code - it takes the
        filter and the scope, and *not* the folder or the subset name that
        ``export_subset_to_csv`` also takes.
        """
        controller.model = RecordingModel(
            {"count_subset_events": 12, "export_subset_to_csv": iter([1.0])}
        )
        controller.model.set_generator = lambda *args: None  # type: ignore[attr-defined]
        controller.model.run_generators = lambda key: None  # type: ignore[attr-defined]

        controller.export_csv_subset(
            "ldr", "/out", "Subset_3", "duration < 300", SCOPE, 3
        )

        assert controller.model.calls_to("count_subset_events") == [
            ("duration < 300", SCOPE)
        ]
        assert [name for _, _, name, _ in controller.model.calls] == [
            "count_subset_events",
            "export_subset_to_csv",
        ]

    def test_an_empty_subset_is_refused_before_a_worker_is_started(
        self, controller: MetadataController
    ) -> None:
        """
        The regression this guard exists for.

        ``export_subset_to_csv`` is a generator, so its own empty-subset check fires on
        the worker's first advance - after the export index has already advanced and
        the progress bar has been created. Counting first is what lets the tab decline
        before any of that happens, and the message has to say the name survived,
        because the user's next dialog will offer it again.
        """
        controller.model = RecordingModel({"count_subset_events": 0})
        staged: list = []
        controller.model.set_generator = (  # type: ignore[attr-defined]
            lambda *args: staged.append(args)
        )

        controller.export_csv_subset(
            "ldr", "/out", "Subset_0", "duration < 0", SCOPE, 0
        )

        assert staged == []
        assert controller.model.calls_to("export_subset_to_csv") == []
        controller.view.on_subset_export_started.assert_not_called()
        message = panel_text(controller)
        assert "No events match Subset_0" in message
        assert "still available" in message

    def test_a_count_that_fails_stages_nothing_and_says_why(
        self, controller: MetadataController
    ) -> None:
        """
        An unknown experiment raises ``KeyError`` out of the count, which the bus used
        to swallow - leaving the export index consumed and no worker running, with
        nothing said.
        """
        controller.model = RecordingModel(
            {
                "count_subset_events": KeyError(
                    "Could not find experiment ID(s) for: exp"
                )
            }
        )
        staged: list = []
        controller.model.set_generator = (  # type: ignore[attr-defined]
            lambda *args: staged.append(args)
        )

        controller.export_csv_subset("ldr", "/out", "Subset_0", None, SCOPE, 0)

        assert staged == []
        assert controller.model.calls_to("export_subset_to_csv") == []
        controller.view.on_subset_export_started.assert_not_called()
        assert "Could not find experiment" in panel_text(controller)

    def test_a_refused_export_stages_nothing_and_says_why(
        self, controller: MetadataController
    ) -> None:
        """
        A non-empty subset whose export still cannot be constructed is reported too.

        This is the arm that survives the count: ``call()`` itself failing to resolve
        or build the generator, rather than anything inside the generator's body.
        """
        controller.model = RecordingModel(
            {
                "count_subset_events": 12,
                "export_subset_to_csv": ValueError("no matching data"),
            }
        )
        staged: list = []
        controller.model.set_generator = (  # type: ignore[attr-defined]
            lambda *args: staged.append(args)
        )

        controller.export_csv_subset("ldr", "/out", "Subset_0", None, SCOPE, 0)

        assert staged == []
        controller.view.on_subset_export_started.assert_not_called()
        assert "no matching data" in panel_text(controller)
