"""
Tests for poriscope.plugins.analysistabs.ClusteringController.

Covers:
- _init creates view and model
- _setup_connections is a no-op that does not raise
- display_write_status (success and failure branches)
- load_metadata_for_clustering, which replaced relay_query and the two bus calls
  behind it: it builds the query, loads the rows, and reports either failure on the
  status panel rather than leaving the View to read a stale attribute
- check_cluster_column / commit_clusters, the Step 4a commit path: two round trips
  with the overwrite confirmation in the View between them, and a failed drop that
  stops the commit rather than writing on top of a half-deleted result
- relay_event_data_generator delegation
- relay_plot_data delegation
- relay_units delegation
- update_column_names (names provided with info log, empty list with warning log)
- update_column_units (units provided with info log, empty dict skips view)
- request_column_names / request_column_units, the Step 4a replacements for two
  ``global_signal`` round trips: they call the plugin through ``self.model.call`` and
  report a failure instead of leaving the View with the previous loader's answer
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.ClusteringController import ClusteringController

# ----------------------------- fixtures ------------------------------


@pytest.fixture
def mock_view(mocker: MockerFixture) -> MagicMock:
    """
    Provide a mocked ClusteringView.

    :param mocker: Pytest-mock fixture.
    :return: Mocked clustering view.
    """
    view: MagicMock = mocker.Mock()
    return view


@pytest.fixture
def controller(mock_view: MagicMock, mocker: MockerFixture) -> ClusteringController:
    """
    Construct a ClusteringController with view, model, and signals replaced by mocks.

    Uses ``__new__`` to bypass ``__init__`` so no real Qt objects are created.

    :param mock_view: Mocked clustering view.
    :param mocker: Pytest-mock fixture.
    :return: Controller under test.
    """
    ctrl: ClusteringController = ClusteringController.__new__(ClusteringController)  # type: ignore[type-abstract]
    ctrl.view = mock_view
    ctrl.model = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[attr-defined]
    ctrl.add_text_to_display = mocker.Mock()
    ctrl.add_text_to_display.emit = mocker.Mock()
    ctrl.global_signal = mocker.Mock()
    ctrl.global_signal.emit = mocker.Mock()
    ctrl.update_available_plugins = mocker.Mock()
    ctrl.update_available_plugins.emit = mocker.Mock()
    return ctrl


# ----------------------- _init / _setup_connections ------------------


def test_init_creates_view_and_model(mocker: MockerFixture) -> None:
    """
    Verify that _init instantiates ClusteringView and ClusteringModel on the controller.

    Patches both constructors so no real Qt objects are created.

    :param mocker: Pytest-mock fixture.
    """
    mock_view_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ClusteringController.ClusteringView"
    )
    mock_model_cls = mocker.patch(
        "poriscope.plugins.analysistabs.ClusteringController.ClusteringModel"
    )

    ctrl: ClusteringController = ClusteringController.__new__(ClusteringController)  # type: ignore[type-abstract]
    ctrl._init()

    mock_view_cls.assert_called_once()
    mock_model_cls.assert_called_once()
    assert ctrl.view is mock_view_cls.return_value
    assert ctrl.model is mock_model_cls.return_value


def test_setup_connections_does_not_raise(
    controller: ClusteringController,
) -> None:
    """
    Verify that _setup_connections is currently a no-op and does not raise.

    :param controller: Controller under test.
    """
    controller._setup_connections()


# -------------------- display_write_status ---------------------------


def test_display_write_status_emits_success_message(
    controller: ClusteringController,
) -> None:
    """
    Emit a success message when the write status is True.

    :param controller: Controller under test.
    """
    controller.display_write_status(True)
    controller.add_text_to_display.emit.assert_called_once_with(
        "Successfully wrote clustering data", "ClusteringController"
    )


def test_display_write_status_emits_failure_message(
    controller: ClusteringController,
) -> None:
    """
    Emit a failure message when the write status is False.

    :param controller: Controller under test.
    """
    controller.display_write_status(False)
    controller.add_text_to_display.emit.assert_called_once_with(
        "Failed to write clustering data", "ClusteringController"
    )


# --------------- relay_event_data_generator --------------------------


def test_relay_event_data_generator_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward an event data generator to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    gen = iter([{"id": 1}, {"id": 2}])
    controller.relay_event_data_generator(gen)
    mock_view.set_event_data_generator.assert_called_once_with(gen)


# ----------------------- relay_plot_data -----------------------------


def test_relay_plot_data_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward structured plot data to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    data = {"x": [1.0, 2.0], "y": [3.0, 4.0]}
    controller.relay_plot_data(data)
    mock_view.set_plot_data.assert_called_once_with(data)


# ------------------------- relay_units -------------------------------


def test_relay_units_delegates_to_view(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a column-to-unit mapping to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    units = {"current": "pA", "time": "s"}
    controller.relay_units(units)
    mock_view.set_units.assert_called_once_with(units)


# -------------------- load_metadata_for_clustering (Step 4a) ----------


class TestLoadMetadataForClustering:
    """
    What replaced ``relay_query`` and the two bus calls behind it.

    Both answers used to be parked on View attributes and read back on the next
    statement. That is the pattern that twice shipped a plot of the previous subset's
    rows: a dispatch that failed left the attribute holding the last successful value,
    and the ``is None`` guard read it as this subset's answer. Every test here is a case
    the old path could not distinguish.
    """

    def _config(self):
        """A minimal config, as the settings dialog produces one."""
        return {
            "method": "HDBSCAN",
            "filter": "",
            "columns": [
                {
                    "column": "duration",
                    "unit": "us",
                    "log": False,
                    "norm": True,
                    "plot": True,
                }
            ],
            "method_params": {},
        }

    def test_it_builds_the_query_then_loads_the_rows(self, controller, mocker) -> None:
        """Two calls, in order, both by key through the Model."""
        frame = mocker.Mock(empty=False)
        controller.model.call.side_effect = [("SELECT 1", "", "events"), frame]

        controller.load_metadata_for_clustering(self._config(), "L")

        assert controller.model.call.call_count == 2
        first, second = controller.model.call.call_args_list
        assert first.args[2] == "construct_metadata_query"
        assert second.args[2] == "load_metadata"

    def test_it_hands_the_rows_to_the_view(self, controller, mocker) -> None:
        """The result path: the rows arrive as an argument, not as an attribute."""
        frame = mocker.Mock(empty=False)
        config = self._config()
        controller.model.call.side_effect = [("SELECT 1", "", "events"), frame]

        controller.load_metadata_for_clustering(config, "L")

        controller.view.on_metadata_loaded.assert_called_once_with(config, "L", frame)

    def test_the_query_and_table_still_reach_the_view(self, controller, mocker) -> None:
        """
        ``set_query`` is kept: the View shows the SQL on the status panel from it.

        Only the delivery changed, not the state.
        """
        controller.model.call.side_effect = [
            ("SELECT 1", "", "events"),
            mocker.Mock(empty=False),
        ]

        controller.load_metadata_for_clustering(self._config(), "L")

        controller.view.set_query.assert_called_once_with("SELECT 1", "events")

    def test_an_empty_query_stops_and_is_reported(self, controller) -> None:
        """
        The loader could not build a query from the selected columns.

        The View used to detect this by reading back ``self.query == ""``; it is a
        return value now, and nothing is loaded.
        """
        controller.model.call.return_value = ("", "no such column", "events")

        controller.load_metadata_for_clustering(self._config(), "L")

        assert controller.model.call.call_count == 1
        controller.view.on_metadata_loaded.assert_not_called()
        assert controller.add_text_to_display.emit.called

    def test_a_debug_message_is_shown_when_the_query_is_empty(self, controller) -> None:
        """
        The loader's own explanation reaches the panel.

        This is what ``relay_query`` did, and it is the useful half of that method -
        the message is often a set of instructions for fixing the filter.
        """
        controller.model.call.return_value = ("", "unknown column: dur", "events")

        controller.load_metadata_for_clustering(self._config(), "L")

        messages = [
            c.args[0] for c in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("unknown column: dur" in m for m in messages)

    def test_an_empty_result_stops_and_is_reported(self, controller, mocker) -> None:
        """
        A query that matched nothing.

        ``.empty`` as well as None, because the loader returns an empty frame rather
        than None and clustering one raises from deep inside sklearn.
        """
        controller.model.call.side_effect = [
            ("SELECT 1", "", "events"),
            mocker.Mock(empty=True),
        ]

        controller.load_metadata_for_clustering(self._config(), "L")

        controller.view.on_metadata_loaded.assert_not_called()

    def test_none_rows_stop_and_are_reported(self, controller) -> None:
        """The other empty shape, which the old guard conflated with a failure."""
        controller.model.call.side_effect = [("SELECT 1", "", "events"), None]

        controller.load_metadata_for_clustering(self._config(), "L")

        controller.view.on_metadata_loaded.assert_not_called()

    def test_a_failing_query_build_is_reported(self, controller) -> None:
        """A raise from the plugin, which the bus swallowed entirely."""
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.load_metadata_for_clustering(self._config(), "L")

        controller.view.on_metadata_loaded.assert_not_called()
        assert controller.add_text_to_display.emit.called

    def test_a_view_side_validation_error_is_reported_not_raised(
        self, controller, mocker
    ) -> None:
        """
        Qt invoked this from a signal, so the View's raises must not escape it.

        ``on_metadata_loaded`` raises for a missing column or a malformed parameter;
        the user is told, and the slot returns.
        """
        controller.model.call.side_effect = [
            ("SELECT 1", "", "events"),
            mocker.Mock(empty=False),
        ]
        controller.view.on_metadata_loaded.side_effect = ValueError(
            "Did you forget to fill in clustering parameters?"
        )

        controller.load_metadata_for_clustering(self._config(), "L")

        messages = [
            c.args[0] for c in controller.add_text_to_display.emit.call_args_list
        ]
        assert any("clustering parameters" in m for m in messages)


# -------------------- the commit path (Step 4a) -----------------------


class TestCheckClusterColumn:
    """First of the commit path's two round trips."""

    def test_it_asks_the_model(self, controller) -> None:
        """The lookup is the Model's now, by key rather than by bus."""
        controller.model.find_cluster_column_table.return_value = "events"

        controller.check_cluster_column("L")

        controller.model.find_cluster_column_table.assert_called_once_with("L")

    def test_it_hands_the_answer_to_the_view(self, controller) -> None:
        """The View needs it to decide whether to ask the user about overwriting."""
        controller.model.find_cluster_column_table.return_value = "events"

        controller.check_cluster_column("L")

        controller.view.on_cluster_column_checked.assert_called_once_with("L", "events")

    def test_none_means_nothing_to_overwrite(self, controller) -> None:
        """
        None is a real answer, not a failure.

        It is what says the commit can proceed without a confirmation, so it must
        reach the View rather than being treated as an error.
        """
        controller.model.find_cluster_column_table.return_value = None

        controller.check_cluster_column("L")

        controller.view.on_cluster_column_checked.assert_called_once_with("L", None)

    def test_a_failure_stops_the_flow_and_tells_the_user(self, controller) -> None:
        """
        The View is not called, so no confirmation dialog appears.

        Before Step 4a this failure was swallowed inside ``_dispatch_to`` and the View
        read a stale ``cluster_column_table``, so it could ask about overwriting a
        result that was not there - or fail to ask about one that was.
        """
        controller.model.find_cluster_column_table.side_effect = KeyError("gone")

        controller.check_cluster_column("L")

        controller.view.on_cluster_column_checked.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()


class TestCommitClusters:
    """Second round trip: drop if asked, then write."""

    def test_it_writes_when_there_is_nothing_to_drop(self, controller) -> None:
        """The common path: no existing result, so straight to the write."""
        controller.model.commit_cluster_columns.return_value = True

        controller.commit_clusters("L", "frame", "events", None)

        controller.model.drop_cluster_columns.assert_not_called()
        controller.model.commit_cluster_columns.assert_called_once_with(
            "L", "frame", "events"
        )

    def test_it_drops_before_writing_when_asked(self, controller) -> None:
        """Order matters: the old columns must go before the new ones arrive."""
        controller.model.drop_cluster_columns.return_value = True
        controller.model.commit_cluster_columns.return_value = True

        controller.commit_clusters("L", "frame", "events", "events")

        controller.model.drop_cluster_columns.assert_called_once_with("L", "events")
        controller.model.commit_cluster_columns.assert_called_once()

    def test_a_failed_drop_stops_the_commit(self, controller) -> None:
        """
        The guard the View's ``operation_success`` check used to provide.

        Writing on top of a half-deleted result leaves the database in a state the
        user has to repair by hand, which is what the message says.
        """
        controller.model.drop_cluster_columns.return_value = False

        controller.commit_clusters("L", "frame", "events", "events")

        controller.model.commit_cluster_columns.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_a_raising_drop_also_stops_the_commit(self, controller) -> None:
        """A raise and a False must lead to the same place."""
        controller.model.drop_cluster_columns.side_effect = RuntimeError("locked")

        controller.commit_clusters("L", "frame", "events", "events")

        controller.model.commit_cluster_columns.assert_not_called()

    def test_the_view_is_told_the_outcome(self, controller) -> None:
        """It refreshes its own columns and notifies the other tabs on success."""
        controller.model.commit_cluster_columns.return_value = True

        controller.commit_clusters("L", "frame", "events", None)

        controller.view.on_clusters_committed.assert_called_once_with("L", True)

    def test_a_failed_write_is_reported_as_such(self, controller) -> None:
        """False reaches the View, which then does not notify anyone of a change."""
        controller.model.commit_cluster_columns.side_effect = RuntimeError("disk full")

        controller.commit_clusters("L", "frame", "events", None)

        controller.view.on_clusters_committed.assert_called_once_with("L", False)


# -------------------- request_column_names (Step 4a) ------------------


class TestRequestColumnNames:
    """
    The Step 4a replacement for a ``global_signal`` round trip.

    What it replaces mattered: the bus resolved the return function by string seven
    hops away, and ``_dispatch_to`` logged and returned on four separate conditions -
    so a loader that could not be read left the View showing the *previous* loader's
    columns, with nothing the View could detect.
    """

    def test_it_calls_the_plugin_through_the_model(
        self, controller: ClusteringController
    ) -> None:
        """One hop, by key, through the sanctioned API."""
        controller.model.call.return_value = ["duration", "current"]

        controller.request_column_names("SQLiteDBLoader_0")

        controller.model.call.assert_called_once_with(
            "MetaDatabaseLoader", "SQLiteDBLoader_0", "get_column_names_by_table"
        )

    def test_it_hands_the_result_to_the_view(
        self, controller: ClusteringController
    ) -> None:
        """The result path, which Decision B routes through the Controller."""
        controller.model.call.return_value = ["duration", "current"]

        controller.request_column_names("SQLiteDBLoader_0")

        controller.view.update_column_names.assert_called_once_with(
            ["duration", "current"]
        )

    def test_a_failure_is_reported_and_the_view_is_left_alone(
        self, controller: ClusteringController
    ) -> None:
        """
        The whole point of the change.

        The View must not be updated with anything, and the user must be told - rather
        than the failure being logged several hops away where nobody sees it.
        """
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_column_names("gone")

        controller.view.update_column_names.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()

    def test_it_does_not_raise_out_of_the_slot(
        self, controller: ClusteringController
    ) -> None:
        """
        Qt invoked this from a signal, so an exception must not escape into C++.

        ``call()`` raising is the correct behaviour one level down; catching it here is
        what turns that into something the user sees.
        """
        controller.model.call.side_effect = RuntimeError("the plugin failed")

        controller.request_column_names("SQLiteDBLoader_0")


# -------------------- request_column_units (Step 4a) ------------------


class TestRequestColumnUnits:
    """The same conversion, for one column's unit string."""

    def test_it_passes_the_column_to_the_plugin(
        self, controller: ClusteringController
    ) -> None:
        """The column name is an argument now, not a ``ret_args`` tuple."""
        controller.model.call.return_value = "ms"

        controller.request_column_units("SQLiteDBLoader_0", "duration")

        controller.model.call.assert_called_once_with(
            "MetaDatabaseLoader", "SQLiteDBLoader_0", "get_column_units", "duration"
        )

    def test_it_hands_the_unit_and_the_column_to_the_view(
        self, controller: ClusteringController
    ) -> None:
        """
        Both halves, in the order the View's setter expects.

        The bus carried the column back as ``ret_args`` appended after the result,
        which is why the receiver's parameter is still called ``axis``.
        """
        controller.model.call.return_value = "ms"

        controller.request_column_units("SQLiteDBLoader_0", "duration")

        controller.view.update_column_units.assert_called_once_with("ms", "duration")

    def test_a_failure_leaves_the_view_alone(
        self, controller: ClusteringController
    ) -> None:
        """A unit that cannot be read must not overwrite the label that is showing."""
        controller.model.call.side_effect = KeyError("no such plugin")

        controller.request_column_units("gone", "duration")

        controller.view.update_column_units.assert_not_called()


# -------------------- update_column_names ----------------------------


def test_update_column_names_updates_view_when_names_provided(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty list of column names to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_names(["col_a", "col_b"])
    mock_view.update_column_names.assert_called_once_with(["col_a", "col_b"])


def test_update_column_names_logs_info_when_names_provided(
    controller: ClusteringController,
) -> None:
    """
    Log an info message after successfully updating the view with column names.

    :param controller: Controller under test.
    """
    controller.update_column_names(["col_a", "col_b"])
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_names_skips_view_when_list_is_empty(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Do not call update_column_names on the view when the list is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_names([])
    mock_view.update_column_names.assert_not_called()


def test_update_column_names_logs_warning_when_list_is_empty(
    controller: ClusteringController,
) -> None:
    """
    Log a warning message when no column names are received.

    :param controller: Controller under test.
    """
    controller.update_column_names([])
    controller.logger.warning.assert_called_once()  # type: ignore[attr-defined]


# -------------------- update_column_units ----------------------------


def test_update_column_units_updates_view_when_units_provided(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Forward a non-empty units dict and axis identifier to the view.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_units({"voltage": "mV"}, "y")
    mock_view.update_column_units.assert_called_once_with({"voltage": "mV"}, "y")


def test_update_column_units_logs_info_when_units_provided(
    controller: ClusteringController,
) -> None:
    """
    Log an info message after successfully updating unit labels in the view.

    :param controller: Controller under test.
    """
    controller.update_column_units({"voltage": "mV"}, "y")
    controller.logger.info.assert_called_once()  # type: ignore[attr-defined]


def test_update_column_units_skips_view_when_units_empty(
    controller: ClusteringController,
    mock_view: MagicMock,
) -> None:
    """
    Do not call update_column_units on the view when the units dict is empty.

    :param controller: Controller under test.
    :param mock_view: Mocked clustering view.
    """
    controller.update_column_units({}, "x")
    mock_view.update_column_units.assert_not_called()
