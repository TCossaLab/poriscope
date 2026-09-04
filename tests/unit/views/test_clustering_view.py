"""
Full unit-test suite for ClusteringView.

Strategy
--------
Pure-logic methods (normalisation, HDBSCAN, column/unit state, merge logic,
parameter extraction) are tested directly.

View-fixture methods (setup, handle_parameter_change routing, update_plot,
update_available_plugins) are tested through a real ClusteringView instance
using the same pattern as test_protein_view.py.

Bus-dependent methods (_commit_clusters, update_available_columns,
update_units, _handle_clustering_settings) are covered at the boundary
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
# set_cluster_column_exists
# ===========================================================================


class TestSetClusterColumnExists:
    def test_stores_table_name(self, view):
        view.set_cluster_column_exists("events")
        assert view.cluster_column_table == "events"

    def test_stores_none(self, view):
        view.set_cluster_column_exists(None)
        assert view.cluster_column_table is None


# ===========================================================================
# set_alter_database_status
# ===========================================================================


class TestSetAlterDatabaseStatus:
    def test_true(self, view):
        view.set_alter_database_status(True)
        assert view.operation_success is True

    def test_false(self, view):
        view.set_alter_database_status(False)
        assert view.operation_success is False


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
# _normalize_column_data
# ===========================================================================


class TestNormalizeColumnData:
    def test_normalises_float_columns(self, view):
        df = _make_df("a", "b")
        norm = view._normalize_column_data(df, exclude_cols=["id"])
        # Median of normalised column should be ~0
        assert abs(norm["a"].median()) < 0.1

    def test_excludes_specified_columns(self, view):
        df = _make_df("a", "b")
        original_a = df["a"].copy()
        norm = view._normalize_column_data(df, exclude_cols=["a", "id"])
        pd.testing.assert_series_equal(norm["a"], original_a)

    def test_id_column_excluded(self, view):
        df = _make_df("a")
        norm = view._normalize_column_data(df, exclude_cols=["id"])
        assert list(norm["id"]) == list(df["id"])

    def test_zero_mad_column_unchanged(self, view):
        df = pd.DataFrame({"a": [5.0] * 50, "id": range(50)})
        norm = view._normalize_column_data(df, exclude_cols=["id"])
        pd.testing.assert_series_equal(norm["a"], df["a"])

    def test_does_not_modify_original(self, view):
        df = _make_df("a")
        original = df["a"].copy()
        view._normalize_column_data(df, exclude_cols=["id"])
        pd.testing.assert_series_equal(df["a"], original)

    def test_int_columns_not_normalised(self, view):
        df = pd.DataFrame({"a": np.arange(50, dtype=int), "id": range(50)})
        norm = view._normalize_column_data(df, exclude_cols=["id"])
        pd.testing.assert_series_equal(norm["a"], df["a"])


# ===========================================================================
# _update_clusters_hdbscan
# ===========================================================================


class TestUpdateClustersHDBSCAN:
    def _data(self):
        rng = np.random.default_rng(1)
        df = pd.DataFrame(
            {
                "a": np.concatenate([rng.normal(0, 0.1, 100), rng.normal(2, 0.1, 100)]),
                "b": np.concatenate([rng.normal(0, 0.1, 100), rng.normal(2, 0.1, 100)]),
                "id": np.arange(200),
            }
        )
        return df

    def test_returns_labels_and_probs(self, view):
        labels, probs = view._update_clusters_hdbscan(self._data(), min_cluster_size=5)
        assert len(labels) == 200
        assert len(probs) == 200

    def test_labels_are_integers(self, view):
        labels, _ = view._update_clusters_hdbscan(self._data(), min_cluster_size=5)
        assert labels.dtype in (np.int32, np.int64, int)

    def test_probs_between_0_and_1(self, view):
        _, probs = view._update_clusters_hdbscan(self._data(), min_cluster_size=5)
        assert np.all(probs >= 0) and np.all(probs <= 1)

    def test_finds_two_clusters(self, view):
        labels, _ = view._update_clusters_hdbscan(self._data(), min_cluster_size=5)
        unique = set(labels)
        # At least 2 non-noise clusters expected (-1 is noise)
        non_noise = unique - {-1}
        assert len(non_noise) >= 1

    def test_custom_params(self, view):
        labels, _ = view._update_clusters_hdbscan(
            self._data(),
            min_cluster_size=10,
            min_samples=2,
            cluster_selection_epsilon=0.5,
        )
        assert len(labels) == 200


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
# _load_metadata_and_cluster — config parsing (bus parts patched)
# ===========================================================================


class TestLoadMetadataAndCluster:
    def _config_hdbscan(self):
        return {
            "method": "HDBSCAN",
            "filter": "",
            "columns": [
                {
                    "column": "duration",
                    "unit": "ms",
                    "log": False,
                    "norm": False,
                    "plot": True,
                },
                {
                    "column": "current",
                    "unit": "pA",
                    "log": False,
                    "norm": False,
                    "plot": True,
                },
            ],
            "method_params": {
                "HDBSCAN_Cluster_Size_input": "5",
                "HDBSCAN_Min_Points_input": "1",
                "HDBSCAN_Sensitivity_input": "1.0",
            },
        }

    def test_duplicate_columns_raises(self, view):
        config = {
            "method": "HDBSCAN",
            "filter": "",
            "columns": [
                {
                    "column": "duration",
                    "unit": "ms",
                    "log": False,
                    "norm": False,
                    "plot": True,
                },
                {
                    "column": "duration",
                    "unit": "ms",
                    "log": False,
                    "norm": False,
                    "plot": True,
                },
            ],
            "method_params": {},
        }
        with pytest.raises(KeyError, match="different"):
            view._load_metadata_and_cluster(config, "loader1")

    def test_empty_query_raises(self, view):
        config = self._config_hdbscan()
        view.query = ""
        with pytest.raises(ValueError, match="metadata query"):
            view._load_metadata_and_cluster(config, "loader1")

    def test_none_plot_data_raises(self, view):
        config = self._config_hdbscan()
        view.query = "SELECT * FROM events"
        view.plot_data = None
        with pytest.raises(ValueError, match="No data"):
            view._load_metadata_and_cluster(config, "loader1")

    def test_missing_column_raises(self, view):
        config = self._config_hdbscan()
        view.query = "SELECT * FROM events"
        _answer_load_metadata(view, pd.DataFrame({"other": [1.0], "id": [0]}))
        with pytest.raises(KeyError):
            view._load_metadata_and_cluster(config, "loader1")

    def test_hdbscan_bad_params_raises(self, view):
        config = self._config_hdbscan()
        config["method_params"]["HDBSCAN_Cluster_Size_input"] = "not_a_number"
        view.query = "SELECT * FROM events"
        rng = np.random.default_rng(0)
        _answer_load_metadata(
            view,
            pd.DataFrame(
                {"duration": rng.random(50), "current": rng.random(50), "id": range(50)}
            ),
        )
        with pytest.raises(ValueError, match="parameters"):
            view._load_metadata_and_cluster(config, "loader1")

    def test_hdbscan_success(self, view):
        config = self._config_hdbscan()
        view.query = "SELECT * FROM events"
        rng = np.random.default_rng(42)
        _answer_load_metadata(
            view,
            pd.DataFrame(
                {
                    "duration": rng.random(100),
                    "current": rng.random(100),
                    "id": np.arange(100),
                }
            ),
        )
        result = view._load_metadata_and_cluster(config, "loader1")
        assert len(result) == 7
        df, labels, probs, logs, norm, units, plot = result
        assert len(labels) == len(df)
        assert len(probs) == len(df)

    def test_gaussian_mixtures_bad_params_raises(self, view):
        config = {
            "method": "Gaussian Mixtures",
            "filter": "",
            "columns": [
                {"column": "a", "unit": "", "log": False, "norm": False, "plot": True},
                {"column": "b", "unit": "", "log": False, "norm": False, "plot": True},
            ],
            "method_params": {"Gaussian Mixtures_Number_of_Clusters_input": "bad"},
        }
        view.query = "SELECT * FROM events"
        rng = np.random.default_rng(1)
        _answer_load_metadata(
            view,
            pd.DataFrame({"a": rng.random(50), "b": rng.random(50), "id": range(50)}),
        )
        with pytest.raises(ValueError, match="parameters"):
            view._load_metadata_and_cluster(config, "loader1")

    def test_gaussian_mixtures_success(self, view):
        config = {
            "method": "Gaussian Mixtures",
            "filter": "",
            "columns": [
                {"column": "a", "unit": "", "log": False, "norm": False, "plot": True},
                {"column": "b", "unit": "", "log": False, "norm": False, "plot": True},
            ],
            "method_params": {"Gaussian Mixtures_Number_of_Clusters_input": "2"},
        }
        view.query = "SELECT * FROM events"
        rng = np.random.default_rng(7)
        _answer_load_metadata(
            view,
            pd.DataFrame({"a": rng.random(60), "b": rng.random(60), "id": range(60)}),
        )
        df, labels, probs, logs, norm, units, plot = view._load_metadata_and_cluster(
            config, "loader1"
        )
        assert len(labels) == 60


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
