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

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from tests.unit.controllers._recording_model import RecordingModel

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
# load_event_subset
# ===========================================================================


class TestLoadEventSubset:
    """
    The same shape, for the event-data plot types.
    """

    def test_it_hands_over_the_query_and_the_generator(
        self, controller: MetadataController
    ) -> None:
        """
        Both were unguarded reads before Step 4a.
        """
        generator = iter([{"event_id": 1}])
        controller.model = RecordingModel(
            {
                "construct_event_data_query": "SELECT * FROM events",
                "load_event_data": generator,
            }
        )

        controller.load_event_subset("ldr", "duration < 300", SCOPE)

        controller.view.set_event_query.assert_called_once_with("SELECT * FROM events")
        controller.view.set_event_data_generator.assert_called_once_with(generator)

    def test_a_failed_load_leaves_the_previous_generator_alone(
        self, controller: MetadataController
    ) -> None:
        """
        The View clears it before asking, so not setting it is the whole fix: before,
        a failed load left the previous subset's generator and replotted its events.
        """
        controller.model = RecordingModel(
            {
                "construct_event_data_query": "SELECT * FROM events",
                "load_event_data": RuntimeError("no such table: events"),
            }
        )

        controller.load_event_subset("ldr", "", SCOPE)

        controller.view.set_event_data_generator.assert_not_called()
        assert "no such table: events" in panel_text(controller)


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
        controller.model = RecordingModel(dict(self.ANSWERS))

        controller.load_event_plot_data("ldr", [5, 10], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

        assert controller.model.calls_to("query_database_directly") == []
        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "exp1" in panel_text(controller)

    def test_a_raising_experiment_lookup_stops_the_plot(
        self, controller: MetadataController
    ) -> None:
        """ """
        answers = dict(self.ANSWERS)
        answers["get_experiment_id_by_name"] = RuntimeError("database is locked")
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

        assert controller.model.calls_to("load_event_data") == []
        controller.view.set_event_plot_data_generator.assert_not_called()
        assert controller.logger.error.called

    def test_a_failed_load_hands_over_nothing(
        self, controller: MetadataController
    ) -> None:
        """ """
        answers = dict(self.ANSWERS)
        answers["load_event_data"] = RuntimeError("cannot read event blob")
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(answers)

        controller.load_event_plot_data("ldr", [5], "exp1", 1, SCOPE)

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
        controller.model = RecordingModel(dict(self.ANSWERS))

        controller.load_event_plot_data("ldr", [5], None, 1, SCOPE)

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
        controller.model = RecordingModel({"export_subset_to_csv": generator})
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

    def test_a_refused_export_stages_nothing_and_says_why(
        self, controller: MetadataController
    ) -> None:
        """
        ``export_subset_to_csv`` raises ``ValueError`` for a filter that matches no
        data and ``KeyError`` for an unknown experiment, both of which the bus
        swallowed - leaving the export index consumed and no worker running, with
        nothing said.
        """
        controller.model = RecordingModel(
            {"export_subset_to_csv": ValueError("no matching data")}
        )
        staged: list = []
        controller.model.set_generator = (  # type: ignore[attr-defined]
            lambda *args: staged.append(args)
        )

        controller.export_csv_subset("ldr", "/out", "Subset_0", None, SCOPE, 0)

        assert staged == []
        controller.view.on_subset_export_started.assert_not_called()
        assert "no matching data" in panel_text(controller)
