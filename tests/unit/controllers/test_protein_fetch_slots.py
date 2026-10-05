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
``ProteinController``'s fetch slots: what they call, and what they report.

**Why this file exists.** ``test_protein_view``'s tests for these conversions stub the
answer - they connect to the intent and set the generator the way the Controller does -
so not one of them can see what the Controller actually asks the loader, or what it does
when the loader says no. That is how the metadata tab's first two fetch slots shipped
untested, and the same trap applies here.

Kept out of ``test_protein_controller`` because that module covers the relay methods.
"""

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.plugins.analysistabs.ProteinModel import ProteinModel
from poriscope.plugins.analysistabs.ProteinView import FIT_COLUMNS
from tests.unit.controllers._recording_model import (
    RecordingModel,
    recording_tab_model,
)

pytestmark = pytest.mark.characterization

#: The scope a protein tab request carries: one experiment, one channel.
SCOPE = {"exp1": [1]}


@pytest.fixture
def controller(mocker: MockerFixture) -> ProteinController:
    """
    A bare ``ProteinController`` with a mocked View and no Model yet.

    Built with ``__new__`` so no Qt object exists behind it, which is also why
    ``add_text_to_display`` is replaced on the instance: emitting the real class-level
    Signal from an uninitialised QObject raises "Signal source has been deleted".

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: the controller under test
    :rtype: ProteinController
    """
    ctrl = ProteinController.__new__(ProteinController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    return ctrl


def panel_text(controller: ProteinController) -> str:
    """
    Everything the controller put on the status panel, joined.

    :param controller: the controller under test
    :type controller: ProteinController
    :return: the concatenated message text
    :rtype: str
    """
    return "\n".join(
        call.args[0] for call in controller.add_text_to_display.emit.call_args_list
    )


def ids_frame() -> pd.DataFrame:
    """
    What ``query_database_directly`` returns for the id-resolution query.

    :return: primary keys alongside the ``event_id`` values they belong to
    :rtype: pd.DataFrame
    """
    return pd.DataFrame({"id": [10, 11], "event_id": [4, 7]})


# ===========================================================================
# load_event_plot_data - resolve the ids in scope, then load exactly those rows
# ===========================================================================


class TestLoadEventPlotData:
    """
    Three emits over two View methods became one intent.

    Answers are written from each loader method's real signature on
    ``MetaDatabaseLoader`` rather than from the calling code:
    ``get_experiment_id_by_name(experiment_name)``, ``query_database_directly(query)``
    and ``load_event_data(conditions, experiments_and_channels)``. The bus packed a
    method's arguments into a tuple; ``call()`` spreads them, which is the shape most
    likely to differ between the two mechanisms.
    """

    def test_the_whole_chain_runs_and_the_generator_reaches_the_view(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        generator = iter([])
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": ids_frame(),
                "load_event_data": generator,
            },
        )

        controller.load_event_plot_data("ldr", [4, 7], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("get_experiment_id_by_name") == [("exp1",)]
        assert controller.model.calls_to("query_database_directly") == [
            (
                "SELECT id FROM events WHERE event_id IN (4,7) "
                "AND experiment_id = 3 AND channel_id = 1",
            )
        ]
        assert controller.model.calls_to("load_event_data") == [
            ("e.id IN (10,11)", SCOPE)
        ]
        controller.view.set_event_plot_data_generator.assert_called_once_with(generator)

    def test_an_unresolvable_experiment_stops_the_plot(
        self, controller: ProteinController
    ) -> None:
        """
        The behaviour change this commit makes deliberately.

        ``event_id`` is unique only within an experiment and channel. The View version
        appended the scope only when the lookup had succeeded, so a failed lookup ran
        the id query with no experiment scope at all, and an ``event_id`` present in
        two channels could return the wrong channel events - the same fault
        ``MetadataController`` was given this guard for on 2026-09-09.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {"get_experiment_id_by_name": None, "query_database_directly": ids_frame()},
        )

        controller.load_event_plot_data("ldr", [4], "exp1", 1, SCOPE, "events")

        assert controller.model.calls_to("query_database_directly") == []
        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "no experiment named exp1" in panel_text(controller)

    def test_a_failed_experiment_lookup_is_reported(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel, {"get_experiment_id_by_name": RuntimeError("db gone")}
        )

        controller.load_event_plot_data("ldr", [4], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "Could not look up experiment exp1" in panel_text(controller)

    def test_a_request_with_no_scope_queries_without_one(
        self, controller: ProteinController
    ) -> None:
        """
        No experiment and no channel is a legitimate state rather than a failed
        lookup, so the query carries only the event ids.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {"query_database_directly": ids_frame(), "load_event_data": iter([])},
        )

        controller.load_event_plot_data("ldr", [4, 7], None, None, None, "events")

        assert controller.model.calls_to("query_database_directly") == [
            ("SELECT id FROM events WHERE event_id IN (4,7)",)
        ]

    def test_an_empty_request_asks_the_loader_nothing(
        self, controller: ProteinController
    ) -> None:
        """
        ``event_id IN ()`` is not valid SQL, and the View can reach here with an empty
        list through a filter that matched nothing.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(ProteinModel, {})

        controller.load_event_plot_data("ldr", [], "exp1", 1, SCOPE, "histograms")

        assert controller.model.calls == []
        assert "no histograms to plot" in panel_text(controller)

    def test_a_failed_id_query_is_reported(self, controller: ProteinController) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": RuntimeError("bad sql"),
            },
        )

        controller.load_event_plot_data("ldr", [4], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "Could not look up these events" in panel_text(controller)

    def test_no_matching_rows_names_what_was_being_plotted(
        self, controller: ProteinController
    ) -> None:
        """
        The message names the plot type rather than the ids, which is the wording
        divergence from the metadata tab copy of this chain.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": pd.DataFrame({"id": [], "event_id": []}),
            },
        )

        controller.load_event_plot_data("ldr", [4], "exp1", 1, SCOPE, "histograms")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "No data available for the requested histograms" in panel_text(
            controller
        )

    def test_rows_without_an_id_column_are_reported(
        self, controller: ProteinController
    ) -> None:
        """
        A loader answering with the wrong projection is a bug in the loader rather
        than something a user can act on, which is why this was logged and not shown.

        **Changed 2026-09-19**, see ``DECISIONS.md``: the View used to add "no data
        available for event_id N" under every empty answer, so the user saw *something*
        when this fired. It no longer does - a refusal the Controller has explained is
        silent there - so a log-only branch here is a plot that fails with nothing said
        at all. Not actionable is not the same as not worth knowing.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": pd.DataFrame({"event_id": [4]}),
            },
        )

        controller.load_event_plot_data("ldr", [4], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        controller.logger.error.assert_called_once()  # type: ignore[attr-defined]
        assert "no id column" in panel_text(controller)

    def test_a_failed_load_is_reported(self, controller: ProteinController) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": ids_frame(),
                "load_event_data": RuntimeError("no blobs"),
            },
        )

        controller.load_event_plot_data("ldr", [4, 7], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "Could not load these events" in panel_text(controller)

    def test_a_loader_that_answers_none_is_reported(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = recording_tab_model(
            ProteinModel,
            {
                "get_experiment_id_by_name": 3,
                "query_database_directly": ids_frame(),
                "load_event_data": None,
            },
        )

        controller.load_event_plot_data("ldr", [4, 7], "exp1", 1, SCOPE, "events")

        controller.view.set_event_plot_data_generator.assert_not_called()
        assert "No data available for the requested events" in panel_text(controller)


def fit_frame() -> pd.DataFrame:
    """
    The fitted columns the View hands over, keyed by event id.

    :return: one row carrying every written column
    :rtype: pd.DataFrame
    """
    frame = {"id": [1]}
    frame.update({column: [1.0] for column in FIT_COLUMNS})
    return pd.DataFrame(frame)


# ===========================================================================
# the two-phase fit commit - look first, then write what the user approved
# ===========================================================================


class TestCheckForExistingFitColumns:
    """
    Phase one. The plugin call the View used to make before its modal question.
    """

    def test_the_table_name_goes_back_to_the_view(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel({"get_table_by_column": "events"})

        controller.check_for_existing_fit_columns("ldr")

        assert controller.model.calls_to("get_table_by_column") == [("prolate_volume",)]
        controller.view.confirm_fit_commit.assert_called_once_with("ldr", "events")

    def test_no_such_column_is_reported_as_no_table(
        self, controller: ProteinController
    ) -> None:
        """
        ``None`` is the answer *and* the flag: nothing to overwrite, so the user is
        never asked.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel({"get_table_by_column": None})

        controller.check_for_existing_fit_columns("ldr")

        controller.view.confirm_fit_commit.assert_called_once_with("ldr", None)

    def test_a_lookup_that_fails_asks_the_user_nothing(
        self, controller: ProteinController
    ) -> None:
        """
        The bus swallowed this, leaving the View reading a stale table name - which
        decides whether a destructive overwrite is proposed at all.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"get_table_by_column": RuntimeError("db gone")}
        )

        controller.check_for_existing_fit_columns("ldr")

        controller.view.confirm_fit_commit.assert_not_called()
        assert "Could not check ldr for existing fit data" in panel_text(controller)


class TestCommitFits:
    """
    Phase two, reached once the database has been looked at and the user has agreed.
    """

    def test_a_first_commit_writes_without_altering_anything(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        frame = fit_frame()
        units = [None] * len(FIT_COLUMNS)
        controller.model = RecordingModel({"add_columns_to_table": True})

        controller.commit_fits("ldr", frame, units, None)

        assert controller.model.calls_to("alter_database") == []
        ((written, sent_units, table),) = controller.model.calls_to(
            "add_columns_to_table"
        )
        assert written is frame
        assert sent_units is units
        assert table == "events"
        controller.view.on_fit_commit_finished.assert_called_once_with("ldr")

    def test_an_overwrite_drops_every_written_column_first(
        self, controller: ProteinController
    ) -> None:
        """
        The DROP and DELETE statements are built from the frame the View sent, so a
        column added to the write cannot be left behind by the drop.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        # A real ProteinModel with only its plugin boundary recorded: the query
        # construction lives there, and stubbing the Model method would hide it.
        controller.model = recording_tab_model(
            ProteinModel, {"alter_database": True, "add_columns_to_table": True}
        )

        controller.commit_fits("ldr", fit_frame(), [None] * len(FIT_COLUMNS), "events")

        ((queries,),) = controller.model.calls_to("alter_database")
        assert len(queries) == 2 * len(FIT_COLUMNS)
        for column in FIT_COLUMNS:
            assert f"ALTER TABLE events DROP COLUMN {column}" in queries
            assert f"DELETE FROM columns WHERE name = '{column}'" in queries
        assert not any("id" == q.rsplit(" ", 1)[-1] for q in queries)

    def test_a_failed_drop_does_not_write_over_half_a_table(
        self, controller: ProteinController
    ) -> None:
        """
        The write has to stop, or the tab ends up with some old columns and some new.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"alter_database": False, "add_columns_to_table": True}
        )

        controller.commit_fits("ldr", fit_frame(), [None] * len(FIT_COLUMNS), "events")

        assert controller.model.calls_to("add_columns_to_table") == []
        controller.view.on_fit_commit_finished.assert_not_called()
        assert "clean it up manually" in panel_text(controller)

    def test_a_drop_that_raises_is_reported(
        self, controller: ProteinController
    ) -> None:
        """
        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"alter_database": RuntimeError("locked"), "add_columns_to_table": True}
        )

        controller.commit_fits("ldr", fit_frame(), [None] * len(FIT_COLUMNS), "events")

        assert controller.model.calls_to("add_columns_to_table") == []
        assert "clean it up manually" in panel_text(controller)

    def test_a_failed_write_still_reports_and_does_not_announce_new_columns(
        self, controller: ProteinController
    ) -> None:
        """
        Announcing columns the database refused would leave every other tab offering
        them.

        :param controller: the controller under test
        :type controller: ProteinController
        """
        controller.model = RecordingModel(
            {"add_columns_to_table": RuntimeError("read only")}
        )

        controller.commit_fits("ldr", fit_frame(), [None] * len(FIT_COLUMNS), None)

        controller.view.on_fit_commit_finished.assert_not_called()
        assert "Could not write the fit data" in panel_text(controller)
