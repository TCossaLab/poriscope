"""
Full unit-test suite for ClusteringView.

Strategy
--------
Pure-logic methods (normalisation, HDBSCAN, column/unit state, merge logic,
parameter extraction) are tested directly.

View-fixture methods (setup, handle_parameter_change routing, update_plot,
update_available_plugins) are tested through a real ClusteringView instance
using the same pattern as test_protein_view.py.

Step 4a converted this tab's bus calls to ``call()``, so ``set_cluster_column_exists``
and ``set_alter_database_status`` no longer exist - they were parking spots for answers
that arrived from a bus callback, and the answers are return values now. Their tests went
with them; the commit path they served is covered in
``tests/unit/controllers/test_clustering_controller.py``.

The remaining bus-dependent methods (_load_metadata_and_request_clustering,
_handle_clustering_settings) are covered at the boundary
via patching.

Run with:
    pytest test_clustering_view.py -v
    pytest test_clustering_view.py --cov=poriscope --cov-report=html
"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from poriscope.plugins.analysistabs.ClusteringView import ClusteringView

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def view(qt_app):
    """Fully-initialised ClusteringView."""
    v = ClusteringView()
    container = QWidget()
    layout = QVBoxLayout(container)
    v._set_custom_display_area(layout)
    v._set_control_area(layout)
    v._test_container = container
    container.show()
    qt_app.processEvents()
    return v


# ===========================================================================
# Helpers
# ===========================================================================


def _answer_load_metadata(view, plot_data):
    """
    Connect a stand-in for the signal bus that answers a load_metadata call.

    _load_metadata_and_cluster clears plot_data before emitting and reads it
    back on the next statement, so that a dispatch which never returns cannot
    be mistaken for a successful one. A test therefore has to answer the emit
    the way main_controller._dispatch_to does - by calling the named return
    function - rather than pre-assigning the attribute and relying on the emit
    being a no-op.
    """

    def _dispatch(metaclass, key, call_function, call_args, return_function, ret_args):
        if call_function == "load_metadata":
            view.update_plot_data(plot_data)

    view.global_signal.connect(_dispatch)
    # Held so the connection outlives this call for the rest of the test.
    view._test_bus = _dispatch


def _make_df(*cols):
    """Small DataFrame with the given column names (float data)."""
    rng = np.random.default_rng(42)
    data = {c: rng.random(50).astype(float) for c in cols}
    data["id"] = np.arange(50)
    return pd.DataFrame(data)


def _make_cluster_data(n=50):
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "duration": rng.random(n),
            "current": rng.random(n),
            "id": np.arange(n),
            "cluster_label": np.tile([0, 1], n // 2),
            "cluster_confidence": np.ones(n),
        }
    )
    return df


# ===========================================================================
# _init
# ===========================================================================


class TestInit:
    def test_cluster_data_none(self, view):
        assert view.cluster_data is None

    def test_query_empty(self, view):
        assert view.query == ""


# ===========================================================================
# set_query
# ===========================================================================


class TestSetQuery:
    def test_stores_query_and_table(self, view):
        view.set_query("SELECT * FROM events", "events")
        assert view.query == "SELECT * FROM events"
        assert view.table_name == "events"

    def test_empty_query(self, view):
        view.set_query("", "events")
        assert view.query == ""


# ===========================================================================
# set_units
# ===========================================================================


class TestSetUnits:
    def test_stores_units(self, view):
        view.set_units({"duration": "ms", "current": "pA"})
        assert view.units == {"duration": "ms", "current": "pA"}

    def test_list_units(self, view):
        view.set_units(["ms", "pA"])
        assert view.units == ["ms", "pA"]


# ===========================================================================
# update_column_names
# ===========================================================================


class TestUpdateColumnNames:
    def test_stores_columns(self, view):
        view.update_column_names(["duration", "voltage"])
        assert view.columns == ["duration", "voltage"]

    def test_empty_list(self, view):
        view.update_column_names([])
        assert view.columns == []


# ===========================================================================
# update_column_units
# ===========================================================================


class TestUpdateColumnUnits:
    def test_stores_unit_for_column(self, view):
        view.update_column_units("ms", "duration")
        assert view.units["duration"] == "ms"

    def test_multiple_columns(self, view):
        view.update_column_units("ms", "duration")
        view.update_column_units("pA", "current")
        assert view.units["duration"] == "ms"
        assert view.units["current"] == "pA"

    def test_creates_units_dict_if_missing(self, view):
        if hasattr(view, "units"):
            del view.units
        view.update_column_units("nm", "size")
        assert view.units["size"] == "nm"

    def test_overwrites_existing(self, view):
        view.update_column_units("ms", "duration")
        view.update_column_units("s", "duration")
        assert view.units["duration"] == "s"


# ===========================================================================
# get_current_view
# ===========================================================================


class TestGetCurrentView:
    def test_returns_clustering_view(self, view):
        assert view.get_current_view() == "ClusteringView"


# ===========================================================================
# get_walkthrough_steps
# ===========================================================================


class TestGetWalkthroughSteps:
    def test_returns_list(self, view):
        assert isinstance(view.get_walkthrough_steps(), list)

    def test_has_six_steps(self, view):
        assert len(view.get_walkthrough_steps()) == 6

    def test_each_step_is_four_tuple(self, view):
        for step in view.get_walkthrough_steps():
            assert len(step) == 4

    def test_widget_callables_return_lists(self, view):
        for _, _, _, fn in view.get_walkthrough_steps():
            result = fn()
            assert isinstance(result, list)
            assert len(result) >= 1


# ===========================================================================
# _handle_other_actions
# ===========================================================================


class TestHandleOtherActions:
    def test_raises_not_implemented(self, view):
        with pytest.raises(NotImplementedError, match="unknown_action"):
            view._handle_other_actions("unknown_action", {})


# ===========================================================================
# _merge_clusters
# ===========================================================================


class TestMergeClusters:
    def _setup(self, view):
        view.cluster_data = _make_cluster_data()
        view.logs = [False, False]
        view.normalized = [False, False]
        view.units = {"duration": "ms", "current": "pA"}
        view.plot_units = ["ms", "pA"]
        view.plot = [True, True]

    def test_no_cluster_data_returns_early(self, view):
        view.cluster_data = None
        with patch.object(view, "update_plot") as mock:
            view._merge_clusters(0, 1)
        mock.assert_not_called()

    def test_invalid_types_returns_early(self, view):
        view.cluster_data = _make_cluster_data()
        with patch.object(view, "update_plot") as mock:
            view._merge_clusters(None, None)
        mock.assert_not_called()

    def test_merges_label_1_into_0(self, view):
        self._setup(view)
        with patch.object(view, "_reset_actions"), patch.object(view, "update_plot"):
            view._merge_clusters(0, 1)
        # All rows previously labelled 1 should now be 0
        assert (view.cluster_data["cluster_label"] == 1).sum() == 0

    def test_merged_rows_get_confidence_1(self, view):
        self._setup(view)
        with patch.object(view, "_reset_actions"), patch.object(view, "update_plot"):
            view._merge_clusters(0, 1)
        # Rows that were 1 now have confidence 1
        assert (view.cluster_data["cluster_confidence"] == 1).all()

    def test_calls_update_plot_after_merge(self, view):
        self._setup(view)
        with (
            patch.object(view, "_reset_actions"),
            patch.object(view, "update_plot") as mock_plot,
        ):
            view._merge_clusters(0, 1)
        mock_plot.assert_called_once()


# ===========================================================================
# _load_metadata_and_request_clustering / on_metadata_loaded
# ===========================================================================


class TestColumnsBeforeAnyLoaderAnswers:
    """
    ``self.columns`` must exist from construction, not from the first callback.

    It used to be created only by ``update_column_names``, so a loader whose columns
    could not be read left ``_handle_clustering_settings`` raising
    ``AttributeError: 'ClusteringView' object has no attribute 'columns'`` - a modal
    traceback instead of a settings dialog with an empty column list. Step 4a surfaced
    it by making a failed column fetch stop early instead of leaving stale values, but
    the fragility predated that.
    """

    def test_columns_exists_on_a_fresh_view(self, view) -> None:
        """Present and empty, so the settings dialog can open and say nothing is there."""
        assert view.columns == []

    def test_a_failed_fetch_leaves_it_usable(self, view) -> None:
        """
        Nothing arrives, and reading it is still safe.

        This is the exact state the reported traceback was in.
        """
        assert isinstance(view.columns, list)

    def test_a_successful_fetch_replaces_it(self, view) -> None:
        """The normal path still populates it."""
        view.update_column_names(["duration", "current"])

        assert view.columns == ["duration", "current"]


class TestLoadMetadataRequest:
    """
    The first half: validate what the user selected, then ask for the rows.

    Step 4a took the two ``global_signal`` emits out of this method, so it no longer
    needs a bus stand-in at all - it asks, and the rows come back as an argument. The
    tests got simpler because the design did.
    """

    def _config_hdbscan(self):
        """A valid HDBSCAN configuration, as the settings dialog produces one."""
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
                },
                {
                    "column": "current",
                    "unit": "nA",
                    "log": False,
                    "norm": True,
                    "plot": True,
                },
            ],
            "method_params": {
                "HDBSCAN_Cluster_Size_input": "5",
                "HDBSCAN_Min_Points_input": "1",
                "HDBSCAN_Sensitivity_input": "0.5",
            },
        }

    def test_it_asks_the_controller_for_the_rows(self, view, qtbot):
        """One emit now, carrying the config rather than a bus call description."""
        config = self._config_hdbscan()

        with qtbot.waitSignal(view.metadata_load_requested, timeout=5000) as caught:
            view._load_metadata_and_request_clustering(config, "loader1")

        assert caught.args == [config, "loader1"]

    def test_duplicate_columns_raises_before_anything_is_loaded(self, view):
        """
        Validation of the user's own selection stays in the View.

        And it happens before the request, so a meaningless plot costs no query.
        """
        config = self._config_hdbscan()
        config["columns"][1]["column"] = "duration"

        with pytest.raises(KeyError, match="different"):
            view._load_metadata_and_request_clustering(config, "loader1")


class TestOnMetadataLoaded:
    """
    The second half: filter the rows, then ask for them to be clustered.

    The rows are a parameter, so none of this reads ``self.plot_data`` - and the
    clear-before-emit guard that used to protect that read went with the read.
    """

    def _config_hdbscan(self):
        """A valid HDBSCAN configuration."""
        return TestLoadMetadataRequest._config_hdbscan(self)

    def _rows(self, n=100, a="duration", b="current"):
        """Rows shaped like the loader's answer, with an id column."""
        rng = np.random.default_rng(42)
        return pd.DataFrame({a: rng.random(n), b: rng.random(n), "id": np.arange(n)})

    def test_it_emits_a_cluster_request_with_parsed_params(self, view, qtbot):
        """
        The parameters the user typed as strings arrive as int and float.

        The clustering itself is ``ClusteringModel``'s and is covered in
        ``tests/unit/models/test_clustering_model.py``.
        """
        config = self._config_hdbscan()

        with qtbot.waitSignal(view.cluster_requested, timeout=5000) as caught:
            view.on_metadata_loaded(config, "loader1", self._rows())

        frame, exclude_cols, method, params = caught.args
        assert len(frame) == 100
        assert "id" in exclude_cols
        assert method == "HDBSCAN"
        assert isinstance(params["min_cluster_size"], int)
        assert isinstance(params["cluster_selection_epsilon"], float)

    def test_gaussian_mixtures_params_are_parsed_too(self, view, qtbot):
        """The other branch, same shape."""
        config = {
            "method": "Gaussian Mixtures",
            "filter": "",
            "columns": [
                {"column": "a", "unit": "", "log": False, "norm": False, "plot": True},
                {"column": "b", "unit": "", "log": False, "norm": False, "plot": True},
            ],
            "method_params": {"Gaussian Mixtures_Number_of_Clusters_input": "2"},
        }

        with qtbot.waitSignal(view.cluster_requested, timeout=5000) as caught:
            view.on_metadata_loaded(config, "loader1", self._rows(60, "a", "b"))

        _, _, method, params = caught.args
        assert method == "Gaussian Mixtures"
        assert params == {"n_components": 2}

    def test_a_missing_column_raises(self, view):
        """
        The loader returned rows without a column that was asked for.

        Raised rather than plotted, because the zips downstream are index-aligned with
        the per-column flag lists and would silently truncate.
        """
        config = self._config_hdbscan()

        with pytest.raises(KeyError, match="must be present"):
            view.on_metadata_loaded(
                config, "loader1", self._rows(50, "duration", "something_else")
            )

    def test_bad_hdbscan_params_raise(self, view):
        """
        Parsing stays in the View, so the message names the form the user filled in.

        The Controller catches this and reports it on the status panel.
        """
        config = self._config_hdbscan()
        config["method_params"]["HDBSCAN_Cluster_Size_input"] = "bad"

        with pytest.raises(ValueError, match="parameters"):
            view.on_metadata_loaded(config, "loader1", self._rows())

    def test_bad_gaussian_mixtures_params_raise(self, view):
        """The other branch's parsing failure."""
        config = {
            "method": "Gaussian Mixtures",
            "filter": "",
            "columns": [
                {"column": "a", "unit": "", "log": False, "norm": False, "plot": True},
                {"column": "b", "unit": "", "log": False, "norm": False, "plot": True},
            ],
            "method_params": {"Gaussian Mixtures_Number_of_Clusters_input": "bad"},
        }

        with pytest.raises(ValueError, match="parameters"):
            view.on_metadata_loaded(config, "loader1", self._rows(50, "a", "b"))

    def test_an_unknown_method_raises(self, view):
        """
        Refused before any parsing, so the message is about the method not the params.

        The Model refuses it too; both sides checking means a disagreement between them
        fails loudly rather than clustering by some default.
        """
        config = self._config_hdbscan()
        config["method"] = "K Means"

        with pytest.raises(ValueError, match="Unknown clustering method"):
            view.on_metadata_loaded(config, "loader1", self._rows())


class TestSetClusteringResult:
    """
    The other half of ``cluster_requested``, introduced by Step 4c.

    ``_handle_clustering_settings`` used to do all of this inline after the clustering
    call returned; it now happens when the Controller hands the answer back.
    """

    def _request(self, view):
        """Put a request in flight so a result has display context to read."""
        view._pending_cluster_display = (
            "HDBSCAN",
            [False, False],
            [True, True],
            ["s", "nA"],
            [True, True],
        )

    def test_it_plots_the_result(self, view, mocker):
        """The plot is the point of the whole round trip."""
        self._request(view)
        update_plot = mocker.patch.object(view, "update_plot")
        data = _make_cluster_data(20)

        view.set_clustering_result(
            data, data["cluster_label"], data["cluster_confidence"]
        )

        update_plot.assert_called_once()

    def test_it_resets_the_axes_before_plotting(self, view, mocker):
        """
        Ordering matters: the axes are cleared, then drawn.

        Reversed, the new plot would be wiped by the reset.
        """
        self._request(view)
        calls = []
        mocker.patch.object(
            view, "_reset_actions", side_effect=lambda *a, **k: calls.append("reset")
        )
        mocker.patch.object(
            view, "update_plot", side_effect=lambda *a, **k: calls.append("plot")
        )
        data = _make_cluster_data(20)

        view.set_clustering_result(
            data, data["cluster_label"], data["cluster_confidence"]
        )

        assert calls == ["reset", "plot"]

    def test_a_result_with_no_request_outstanding_is_refused(self, view, mocker):
        """
        Nothing is plotted, and it is logged as an error.

        The display context lives on the View between the emit and the answer, so a
        result arriving without one means the two have got out of step - which must
        not silently plot against another run's column flags.
        """
        view._pending_cluster_display = None
        update_plot = mocker.patch.object(view, "update_plot")
        data = _make_cluster_data(20)

        view.set_clustering_result(
            data, data["cluster_label"], data["cluster_confidence"]
        )

        update_plot.assert_not_called()

    def test_the_request_context_is_consumed(self, view, mocker):
        """
        One answer per request.

        Cleared on read, so a second result cannot reuse the first request's flags.
        """
        self._request(view)
        mocker.patch.object(view, "update_plot")
        data = _make_cluster_data(20)

        view.set_clustering_result(
            data, data["cluster_label"], data["cluster_confidence"]
        )

        assert view._pending_cluster_display is None


# ===========================================================================
# handle_parameter_change — routing
# ===========================================================================


class TestHandleParameterChange:
    def _p(self, extra=None):
        params = {"db_loader": "ldr"}
        if extra:
            params.update(extra)
        return params

    def test_routes_export_plot_data(self, view):
        received = []
        view.export_plot_data.connect(lambda: received.append(True))
        view.handle_parameter_change("M", "export_plot_data", (self._p(),))
        assert received == [True]

    def test_routes_loader_changed(self, view):
        view.columns = []
        with patch.object(view, "update_available_columns") as mock:
            view.handle_parameter_change("M", "loader_changed", (self._p(),))
        mock.assert_called_once_with("ldr")

    def test_routes_open_cluster_settings(self, view):
        view.columns = []
        with (
            patch.object(view, "_handle_clustering_settings") as mock,
            patch.object(view, "update_available_columns"),
        ):
            view.handle_parameter_change("M", "open_cluster_settings", (self._p(),))
        mock.assert_called_once()

    def test_routes_merge_clusters(self, view):
        with patch.object(view, "_merge_clusters") as mock:
            p = self._p({"label_x": 0, "label_y": 1})
            view.handle_parameter_change("M", "merge_clusters", (p,))
        mock.assert_called_once_with(0, 1)

    def test_routes_commit_clusters(self, view):
        with patch.object(view, "_commit_clusters") as mock:
            view.handle_parameter_change("M", "commit_clusters", (self._p(),))
        mock.assert_called_once_with("ldr")

    def test_routes_unknown_to_other_actions(self, view):
        with pytest.raises(NotImplementedError):
            view.handle_parameter_change("M", "unknown", (self._p(),))

    def test_loader_changed_updates_units_per_column(self, view):
        view.columns = ["duration", "current"]
        with (
            patch.object(view, "update_available_columns"),
            patch.object(view, "update_units") as mock_units,
        ):
            view.handle_parameter_change("M", "loader_changed", (self._p(),))
        assert mock_units.call_count == 2


# ===========================================================================
# update_available_plugins
# ===========================================================================


class TestUpdateAvailablePlugins:
    def test_updates_loaders_combobox(self, view):
        view.update_available_plugins({"MetaDatabaseLoader": ["db1", "db2"]})
        assert view.clusteringcontrols.db_loader_comboBox.count() == 2

    def test_empty_plugins_no_error(self, view):
        view.update_available_plugins({})

    def test_missing_key_no_error(self, view):
        view.update_available_plugins({"SomeOtherPlugin": ["x"]})


# ===========================================================================
# update_plot — 2-D and 3-D paths
# ===========================================================================


class TestUpdatePlot:
    def _make_labelled_df(self):
        rng = np.random.default_rng(5)
        df = pd.DataFrame(
            {
                "duration": rng.random(30).astype(float),
                "current": rng.random(30).astype(float),
                "id": np.arange(30),
            }
        )
        labels = np.tile([0, 1], 15)
        confidence = np.ones(30)
        return df, labels, confidence

    def _setup_axes(self, view, axis_type="2d"):
        # Directly assign a real matplotlib axes object, bypassing _reset_actions
        # and all its decorators/side-effects entirely.
        view.figure.clear()
        if axis_type == "2d":
            view.axes = view.figure.add_subplot(1, 1, 1)
        else:
            view.axes = view.figure.add_subplot(1, 1, 1, projection="3d")

    def test_2d_plot_no_error(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )

    def test_stores_cluster_data(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )
        assert view.cluster_data is not None

    def test_stores_labels(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )
        np.testing.assert_array_equal(view.labels, labels)

    def test_invalid_plot_dims_returns_early(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw") as mock_draw,
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[False, False, False],
            )
        mock_draw.assert_not_called()

    def test_log_flag_reflected_in_label(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[True, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )
        assert "Log10" in view.axes.get_xlabel()

    def test_norm_flag_reflected_in_label(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[True, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )
        assert "Normalized" in view.axes.get_xlabel()

    def test_unit_in_label(self, view):
        df, labels, conf = self._make_labelled_df()
        self._setup_axes(view)
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False],
                normalized=[False, False],
                units=["ms", "pA"],
                plot=[True, True, False],
            )
        assert "ms" in view.axes.get_xlabel()

    def test_3d_plot_no_error(self, view):
        rng = np.random.default_rng(9)
        df = pd.DataFrame(
            {
                "a": rng.random(20).astype(float),
                "b": rng.random(20).astype(float),
                "c": rng.random(20).astype(float),
                "id": np.arange(20),
            }
        )
        labels = np.tile([0, 1], 10)
        conf = np.ones(20)
        self._setup_axes(view, axis_type="3d")
        with (
            patch.object(view.canvas, "draw"),
            patch.object(view, "_update_cache"),
            patch.object(view, "_commit_cache"),
        ):
            view.update_plot(
                df,
                labels,
                conf,
                logs=[False, False, False],
                normalized=[False, False, False],
                units=["", "", ""],
                plot=[True, True, True, False],
            )


# ===========================================================================
# _commit_clusters — boundary test (no DB)
# ===========================================================================


class TestCommitClusters:
    def test_raises_when_no_cluster_data(self, view):
        view.cluster_data = None
        with pytest.raises(AttributeError, match="cluster data has not been set"):
            view._commit_clusters("loader1")

    def test_proceeds_with_cluster_data(self, view):
        view.cluster_data = pd.DataFrame(
            {
                "id": [1, 2],
                "cluster_label": [0, 1],
                "cluster_confidence": [1.0, 0.9],
            }
        )
        view.table_name = "events"
        view.cluster_column_table = None  # no existing columns → skip overwrite dialog
        # global_signal.emit is a Qt signal with no connected slots — no crash expected
        view._commit_clusters("loader1")


# ===========================================================================
# _reset_actions
# ===========================================================================


class TestResetActions:
    def test_2d_no_error(self, view):
        with patch.object(view.canvas, "draw"):
            view._reset_actions(axis_type="2d")

    def test_3d_no_error(self, view):
        with patch.object(view.canvas, "draw"):
            view._reset_actions(axis_type="3d")

    def test_clears_allowed_cols(self, view):
        view.allowed_cols = ["a"]
        with patch.object(view.canvas, "draw"):
            view._reset_actions()
        assert view.allowed_cols is None

    def test_clears_allowed_logs(self, view):
        view.allowed_logs = [True]
        with patch.object(view.canvas, "draw"):
            view._reset_actions()
        assert view.allowed_logs is None
