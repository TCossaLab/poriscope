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
# Alejandra Carolina González González
# Kyle Briggs


import logging
import os
import sys
import warnings
from typing import Any, Dict, List, Tuple, Union

import hdbscan
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from mpl_toolkits.mplot3d import Axes3D
from pandas.api.types import is_float_dtype
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QMessageBox
from sklearn.mixture import GaussianMixture
from typing_extensions import override

from poriscope.plugins.analysistabs.utils.clusteringcontrols import ClusteringControls
from poriscope.plugins.analysistabs.utils.walkthrough_mixin import WalkthroughMixin
from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log, register_action
from poriscope.utils.MetaView import MetaView
from poriscope.views.widgets.clustering_settings_widget import ClusteringSettingsDialog

# Check if running on Windows
if sys.platform == "win32":
    os.environ["OMP_NUM_THREADS"] = "2"

# Silence sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")


@inherit_docstrings
class ClusteringView(MetaView, WalkthroughMixin):
    """
    Subclass of MetaView for displaying and interacting with clustering analysis.

    Handles plotting, user input, and signal exchanges.
    """

    logger = logging.getLogger(__name__)
    request_plugin_refresh = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init()
        self._init_walkthrough()

    @log(logger=logger)
    @override
    def _init(self):
        """
        Initializes the ClusteringView's internal state and clears cache.
        """
        self._clear_cache()
        self.cluster_data = None
        self.query = ""

    @log(logger=logger)
    @override
    def _set_control_area(self, layout):
        """
        Sets up the left-hand control area for the clustering plugin.

        :param layout: The parent layout to which controls are added.
        :type layout: QLayout
        """

        self.clusteringcontrols = ClusteringControls()
        self.clusteringcontrols.actionTriggered.connect(self.handle_parameter_change)
        self.clusteringcontrols.edit_processed.connect(self.handle_edit_triggered)
        self.clusteringcontrols.add_processed.connect(self.handle_add_triggered)
        self.clusteringcontrols.delete_processed.connect(self.handle_delete_triggered)

        controlsAndAnalysisLayout = QHBoxLayout()
        controlsAndAnalysisLayout.setContentsMargins(0, 0, 0, 0)

        # Add the rawdatacontrols directly to the main layout
        controlsAndAnalysisLayout.addWidget(self.clusteringcontrols, stretch=1)

        layout.setSpacing(0)
        layout.addLayout(controlsAndAnalysisLayout, stretch=1)

    @log(logger=logger)
    def get_save_filename(self):
        """
        Opens a file dialog to select a location for saving a CSV file.

        :return: The selected file path.
        :rtype: str
        """
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save CSV File",
            os.path.expanduser("~"),
            "CSV Files (*.csv);;All Files (*)",
        )
        return file_name

    @log(logger=logger)
    @register_action()
    @override
    def _reset_actions(self, axis_type="2d"):
        """
        Clears the figure and reinitializes axes. This will also add a flag to the tab action history if @register_action is being used to keep track of actions. Only actions applied after the most recent call to this function will be recreated if the related file is loaded.

        :param axis_type: Either '2d' or '3d' to determine plot projection.
        :type axis_type: str
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                self.figure.clear()
            except AttributeError:
                pass
            self._clear_cache()
        if axis_type == "2d":
            self.axes = self.figure.add_subplot(1, 1, 1)
        else:
            self.axes = self.figure.add_subplot(1, 1, 1, projection="3d")
        self.figure.set_constrained_layout(True)
        self.canvas.draw()
        self.allowed_cols = None
        self.allowed_logs = None
        self.allowed_plot_type = None

    @log(logger=logger)
    @Slot(str, str, tuple)
    def handle_parameter_change(self, submodel_name, action_name, args):
        """
        Handles actions triggered by the control panel.

        :param submodel_name: Name of the submodel.
        :type submodel_name: str
        :param action_name: Action to perform (e.g., 'merge_clusters').
        :type action_name: str
        :param args: Parameters passed with the action.
        :type args: tuple
        """
        parameters = args[0]
        if action_name == "export_plot_data":
            self.export_plot_data.emit()
        elif action_name == "loader_changed":
            loader = parameters["db_loader"]
            self.update_available_columns(loader)
            self.units: Dict[str, str] = {}
            for col in getattr(self, "columns", []):
                self.update_units(loader, col)
        elif action_name == "open_cluster_settings":
            loader = parameters["db_loader"]
            self.update_available_columns(loader)
            self.units = {}
            for col in getattr(self, "columns", []):
                self.update_units(loader, col)
            self._handle_clustering_settings(parameters)

        elif action_name == "merge_clusters":
            keep = parameters["label_x"]
            merge = parameters["label_y"]
            self._merge_clusters(keep, merge)
        elif action_name == "commit_clusters":
            loader = parameters["db_loader"]
            self._commit_clusters(loader)
        else:
            self._handle_other_actions(action_name, parameters)

    @log(logger=logger)
    def _merge_clusters(self, keep, merge):
        """
        Merges two clusters by reassigning the label.

        :param keep: Cluster label to keep.
        :type keep: int
        :param merge: Cluster label to merge into the keep label.
        :type merge: int
        """
        if self.cluster_data is None:
            self.logger.error("No clusters defined, unable to merge")
            return
        else:
            try:
                keep = int(keep)
                merge = int(merge)
            except TypeError:
                self.logger.error(
                    f"cluster selections {keep} and {merge} cannot be converted to ints"
                )
                return
            self.cluster_data.loc[
                self.cluster_data["cluster_label"] == merge, "cluster_confidence"
            ] = 1
            self.cluster_data.loc[
                self.cluster_data["cluster_label"] == merge, "cluster_label"
            ] = keep

        self._reset_actions()
        self.update_plot(
            self.cluster_data,
            self.cluster_data["cluster_label"].values,
            self.cluster_data["cluster_confidence"].values,
            self.logs,
            self.normalized,
            self.units,
            self.plot,
        )

    @log(logger=logger)
    def set_cluster_column_exists(self, exists_in_table):
        """
        Sets the status indicating if cluster columns already exist.

        :param exists_in_table: Name of table where columns exist or None.
        :type exists_in_table: str or None
        """
        self.cluster_column_table = exists_in_table

    @log(logger=logger)
    def set_alter_database_status(self, status):
        """
        Sets the success status of a database operation.

        :param status: True if successful, False otherwise.
        :type status: bool
        """
        self.operation_success = status

    @log(logger=logger)
    def _commit_clusters(self, loader):
        """
        Commits clustered data to the database, optionally overwriting existing clustering columns.

        :param loader: Name or ID of the database loader plugin.
        :type loader: str
        """
        if self.cluster_data is None:
            raise AttributeError("cluster data has not been set, unable to commit")
        cluster_data = self.cluster_data[["id", "cluster_label", "cluster_confidence"]]
        units = [None, None]
        table_name = self.table_name

        self.cluster_column_table = None
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "get_table_by_column",
            ("cluster_label"),
            "check_cluster_column_exists",
            (),
        )
        if self.cluster_column_table is not None:
            reply = QMessageBox.question(
                self,
                "Confirm Overwrite",
                "Clustering data already exists, are you sure you want to overwrite? This action cannot be undone.",
                QMessageBox.Ok | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Ok:
                self.operation_success = False
                queries = [
                    f"ALTER TABLE {self.cluster_column_table} DROP COLUMN cluster_label",
                    f"ALTER TABLE {self.cluster_column_table} DROP COLUMN cluster_confidence",
                    "DELETE FROM columns WHERE name = 'cluster_label'",
                    "DELETE FROM columns WHERE name = 'cluster_confidence'",
                ]

                self.global_signal.emit(
                    "MetaDatabaseLoader",
                    loader,
                    "alter_database",
                    (queries),
                    "alter_database_status",
                    (),
                )
                if self.operation_success is not True:
                    self.add_text_to_display.emit(
                        "Unable to delete clustering data, you will have to clean it up manually",
                        self.__class__.__name__,
                    )
                    return
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "add_columns_to_table",
            (cluster_data, units, table_name),
            "display_write_status",
            (),
        )
        self.request_plugin_refresh.emit()

    @log(logger=logger)
    def set_query(self, query, table_name):
        """
        Sets the SQL query and target table name.

        :param query: SQL query string.
        :type query: str
        :param table_name: Name of the target table.
        :type table_name: str
        """
        self.query = query
        self.table_name = table_name

    @log(logger=logger)
    def set_units(self, units):
        """
        Sets the column units for current clustering configuration.

        :param units: List or dict of column units.
        :type units: list[str] or dict
        """
        self.units = units

    @log(logger=logger)
    def update_available_columns(self, loader):
        """
        Requests updated column names from the specified database loader.

        :param loader: Identifier for the loader plugin.
        :type loader: str
        """
        try:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_column_names_by_table",
                (),
                "update_column_names",
                (),
            )
        except Exception as e:
            self.logger.error(f"Failed to request column data: {repr(e)}")

    @log(logger=logger)
    def update_units(self, loader, column):
        """
        Requests units for a specific column from the database loader.

        :param loader: Plugin name or ID.
        :type loader: str
        :param column: Name of the column.
        :type column: str
        """
        try:
            self.global_signal.emit(
                "MetaDatabaseLoader",
                loader,
                "get_column_units",
                (column,),
                "update_column_units",
                (column,),
            )
        except Exception as e:
            self.logger.error(f"Failed to request units for column {column}: {repr(e)}")

    @log(logger=logger)
    def update_column_names(self, column_names):
        """
        Updates the list of available column names.

        :param column_names: List of column names returned from the loader.
        :type column_names: list[str]
        """
        self.columns = column_names

    @log(logger=logger)
    def update_column_units(self, unit, column):
        """
        Updates the unit for a specific column.

        :param unit: Unit of the column (e.g., 'ms').
        :type unit: str
        :param column: Name of the column.
        :type column: str
        """
        if not hasattr(self, "units"):
            self.units = {}

        self.units[column] = unit
        self.logger.info(f"Received unit for {column}: {unit}")

    @log(logger=logger)
    def _handle_other_actions(self, action_name, parameters):
        """
        Placeholder for handling custom or unrecognized actions.

        :param action_name: Name of the unhandled action.
        :type action_name: str
        :param parameters: Parameters passed with the action.
        :type parameters: dict
        :raises NotImplementedError: Always
        """
        raise NotImplementedError(f"{action_name} handler not implemented")

    @log(logger=logger)
    def _handle_clustering_settings(self, parameters):
        """
        Opens the clustering settings dialog, handles clustering logic, and updates the view.

        :param parameters: Configuration and loader ID for clustering.
        :type parameters: dict
        """
        title = parameters.get("db_loader", "Clustering Settings")

        # Initialize config storage
        if not hasattr(self, "clustering_config_map"):
            self.clustering_config_map: Dict[
                str,
                Dict[
                    str,
                    Union[
                        str,
                        List[str],
                        bool,
                        List[bool],
                        int,
                        List[int],
                        float,
                        List[float],
                        None,
                    ],
                ],
            ] = {}

        # Restore config based on the title aka selected DB
        config_for_title = self.clustering_config_map.get(title, None)

        # Create dialog
        dialog = ClusteringSettingsDialog(
            dynamic_title=title,
            available_columns=self.columns,
            available_methods=["HDBSCAN", "Gaussian Mixtures"],
            method_parameters={
                "HDBSCAN": [
                    {"name": "Cluster Size", "type": "int"},
                    {"name": "Min Points", "type": "int"},
                    {"name": "Sensitivity", "type": "float"},
                ],
                "Gaussian Mixtures": [{"name": "Number of Clusters", "type": "int"}],
            },
            column_units=self.units,
            preselected_config=config_for_title,
        )

        if self._walkthrough_active:
            self.logger.info("Launching walkthrough from _handle_clustering_settings()")
            dialog._init_walkthrough()
            dialog.launch_walkthrough()

            # Force close the walkthrough if dialog closes (reject or otherwise)
            if dialog.walkthrough_dialog:
                dialog.finished.connect(
                    lambda _: dialog.walkthrough_dialog.force_close()
                )

        result = dialog.exec()

        if result == QDialog.Accepted:
            config_result = dialog.get_result()

            # Save under title
            self.clustering_config_map[title] = config_result
            self.logger.debug(
                f"Clustering parameters updated for '{title}': {config_result}"
            )
            try:
                clustered_data, labels, confidence, logs, norm, units, plot = (
                    self._load_metadata_and_cluster(config_result, title)
                )
            except (ValueError, KeyError, TypeError) as e:
                self.logger.error(f"Unable to cluster data: {repr(e)}")
                return
            if clustered_data is None:
                self.logger.error("Unable to cluster data: dataframe came back empty")
                return

            self.add_text_to_display.emit(
                f"{config_result['method']} applied to {len(clustered_data)} rows",
                self.__class__.__name__,
            )
            self._reset_actions()
            self.update_plot(
                clustered_data, labels, confidence, logs, norm, units, plot
            )
        else:
            self.logger.debug("Clustering dialog cancelled.")

    @log(logger=logger)
    def _load_metadata_and_cluster(self, config, loader) -> Tuple[
        Any,  # clustering_data (likely a DataFrame)
        Any,  # labels (e.g. ndarray or list)
        Any,  # probs (e.g. ndarray or list)
        List[Any],  # logs
        List[Any],  # norm
        List[Any],  # units
        List[Any],  # plot
    ]:
        """
        Loads metadata from the database and performs clustering.

        :param config: Dictionary with selected columns and method configuration.
        :type config: dict
        :param loader: Identifier of the loader plugin.
        :type loader: str
        :return: Tuple containing clustered data, labels, confidence, logs, normalized flags, units, and plot flags.
        :rtype: tuple
        """
        columns = [val["column"] for val in config["columns"]]
        units = [val["unit"] for val in config["columns"]]
        logs = [val["log"] for val in config["columns"]]
        norm = [val["norm"] for val in config["columns"]]
        plot = [val["plot"] for val in config["columns"]]

        seen = set()
        for col in columns:
            if col in seen:
                raise KeyError("All columns should be different for a meaningful plot")
            seen.add(col)

        sql_filter = config["filter"]
        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "construct_metadata_query",
            (columns, sql_filter),
            "relay_query",
            (),
        )
        if self.query == "":
            raise ValueError(
                "Unable to generate metadata query, double check your solumn selections"
            )

        self.global_signal.emit(
            "MetaDatabaseLoader",
            loader,
            "load_metadata",
            (columns, sql_filter),
            "update_plot_data",
            (),
        )

        if self.plot_data is None:
            raise ValueError("No data matches the given query")

        if not all(col in self.plot_data.columns for col in columns):
            raise KeyError(
                f"All columns {columns} must be present in the provided dataframe"
            )

        columns.append("id")
        clustering_data = self.plot_data[columns]
        clustering_data = self._logscale_and_filter_dataframe(
            clustering_data, log_columns=[c for c, b in zip(columns, logs) if b]
        )
        exclude_cols = [c for c, b in zip(columns, norm) if not b]
        exclude_cols.append("id")
        clustering_data = self._normalize_column_data(
            clustering_data, exclude_cols=[c for c, b in zip(columns, norm) if not b]
        )

        if config["method"] == "HDBSCAN":
            try:
                min_cluster_size = int(
                    config["method_params"]["HDBSCAN_Cluster_Size_input"]
                )
                min_samples = int(config["method_params"]["HDBSCAN_Min_Points_input"])
                cluster_selection_epsilon = float(
                    config["method_params"]["HDBSCAN_Sensitivity_input"]
                )
            except ValueError:
                raise ValueError("Did you forget to fill in clustering parameters?")
            labels, probs = self._update_clusters_hdbscan(
                clustering_data,
                min_cluster_size=min_cluster_size,
                min_samples=min_samples,
                cluster_selection_epsilon=cluster_selection_epsilon,
            )
        elif config["method"] == "Gaussian Mixtures":
            try:
                n_components = int(
                    config["method_params"][
                        "Gaussian Mixtures_Number_of_Clusters_input"
                    ]
                )
            except ValueError:
                raise ValueError("Did you forget to fill in clustering parameters?")
            clusterer = GaussianMixture(n_components=n_components, n_init=100)
            labels = clusterer.fit_predict(clustering_data)
            probs = clusterer.predict_proba(clustering_data)
            probs = np.max(probs, axis=1) / np.sum(probs, axis=1)
        return clustering_data, labels, probs, logs, norm, units, plot

    @log(logger=logger)
    def update_plot(self, data, labels, confidence, logs, normalized, units, plot):
        """
        Updates the plot with clustered data and redraws it.

        :param data: DataFrame with clustering results.
        :type data: pd.DataFrame
        :param labels: Cluster labels for each row.
        :type labels: list or np.ndarray
        :param confidence: Cluster confidence values.
        :type confidence: list or np.ndarray
        :param logs: Flags indicating if each column is log-scaled.
        :type logs: list[bool]
        :param normalized: Flags indicating if each column is normalized.
        :type normalized: list[bool]
        :param units: Units for each column.
        :type units: list[str]
        :param plot: Flags indicating if a column should be plotted.
        :type plot: list[bool]
        """
        self.labels = labels
        self.logs = logs
        self.normalized = normalized
        self.units = units
        self.plot = plot

        dims = sum(plot)
        plot_cols = [col for col, p in zip(data.columns, plot) if p]
        cols_no_id = [
            col
            for col in data.columns
            if col != "id" and col != "cluster_label" and col != "cluster_confidence"
        ]
        if dims < 2 or dims > 3:
            self.logger.error(
                f"Must plot 2 or 3 columns, but you are trying to plot {sum(plot)}"
            )
            return
        col_labels = {}
        for col, log_flag, norm, unit in zip(cols_no_id, logs, normalized, units):
            col_label = ""
            if norm:
                col_label = "Normalized "
            if log_flag:
                col_label = col_label + f"Log10 {col}"
            else:
                col_label = col_label + f"{col}"
            if unit is not None and unit != "" and unit != " ":
                col_label = col_label + f" ({unit})"
            col_labels[col] = col_label

        data["cluster_label"] = labels
        data["cluster_confidence"] = confidence

        ax = self.axes
        unique_clusters = data["cluster_label"].unique()
        for cluster_value in sorted(unique_clusters):
            subset = data[data["cluster_label"] == cluster_value]
            alpha = (subset["cluster_confidence"] + 0.3333) / 1.3333
            if dims == 2:
                ax.scatter(
                    subset[plot_cols[0]],
                    subset[plot_cols[1]],
                    s=3,
                    alpha=alpha.values,
                    label=cluster_value,
                )
                ax.set_xlabel(col_labels[plot_cols[0]])
                ax.set_ylabel(col_labels[plot_cols[1]])
            elif dims == 3:
                if not isinstance(ax, Axes3D):
                    self._reset_actions(axis_type="3d")
                    ax = self.axes
                color = cm.tab10(
                    cluster_value % 10
                )  # Pick a base color from a colormap
                base_color = mcolors.to_rgba_array([color] * len(subset))
                base_color[:, -1] = (
                    alpha.values
                )  # Replace alpha channel with your custom alpha

                ax.scatter(
                    subset[plot_cols[0]],
                    subset[plot_cols[1]],
                    subset[plot_cols[2]],
                    color=base_color,
                    label=cluster_value,
                    s=3,
                )
                ax.set_xlabel(col_labels[plot_cols[0]])
                ax.set_ylabel(col_labels[plot_cols[1]])
                ax.set_zlabel(col_labels[plot_cols[2]])

        self.clusteringcontrols.update_clusters(sorted(unique_clusters))
        ax.legend(loc="best")
        self.canvas.draw()
        col_labels["cluster_label"] = "cluster_label"
        col_labels["cluster_confidence"] = "cluster_confidence"
        col_labels["id"] = "id"
        self.cluster_data = data
        cache_data = [(data[col].values, col_labels[col]) for col in data.columns]
        self._update_cache(*cache_data)
        self._commit_cache()

    @log(logger=logger)
    @override
    def update_available_plugins(self, available_plugins):
        """
        Called whenever a new plugin is instantiated elsewhere in the app, to keep an up-to-date list of possible data sources for use by this plugin.

        :param available_plugins: dict of lists keyed by MetaClass, listing the identifiers of all instantiated plugins throughout the app.
        :type available_plugins: Dict[str, List[str]]
        """
        super().update_available_plugins(available_plugins)

        try:
            loaders = available_plugins.get("MetaDatabaseLoader", [])
            self.clusteringcontrols.update_loaders(loaders)
            self.logger.info("ComboBoxes updated with available databases")
        except Exception as e:
            self.logger.info(f"Updating ComboBoxes failed: {repr(e)}")

    @log(logger=logger)
    def _normalize_column_data(self, df, exclude_cols=[]):
        """
        Applies MAD-based normalization to float columns in the dataframe.

        :param df: Input DataFrame.
        :type df: pd.DataFrame
        :param exclude_cols: List of columns to exclude from normalization.
        :type exclude_cols: list[str]
        :return: Normalized DataFrame.
        :rtype: pd.DataFrame
        """
        df = df.copy()  # avoid SettingWithCopyWarning
        datatypes = df.dtypes
        for col, dt in datatypes.items():
            if col not in exclude_cols and is_float_dtype(dt):  # leave int types alone
                median = df[col].median()
                mad = (df[col] - median).abs().median()
                if mad != 0:
                    df.loc[:, col] = (df[col] - median) / mad
        return df

    @log(logger=logger)
    def _update_clusters_hdbscan(
        self,
        df: pd.DataFrame,
        min_cluster_size: int = 30,
        min_samples: int = 1,
        cluster_selection_epsilon: float = 1,
    ):
        """
        Performs HDBSCAN clustering on the provided data.

        :param df: DataFrame to cluster.
        :type df: pd.DataFrame
        :param min_cluster_size: Minimum size of clusters.
        :type min_cluster_size: int
        :param min_samples: Minimum samples per cluster.
        :type min_samples: int
        :param cluster_selection_epsilon: Epsilon value to influence cluster boundaries.
        :type cluster_selection_epsilon: float
        :return: Cluster labels and probabilities.
        :rtype: tuple[np.ndarray, np.ndarray]
        """
        columns_except_id = df.columns[df.columns != "id"]
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            cluster_selection_epsilon=cluster_selection_epsilon,
        ).fit(df[columns_except_id])
        labels = clusterer.labels_
        probs = clusterer.probabilities_
        return labels, probs

    def get_current_view(self):
        return "ClusteringView"

    def get_walkthrough_steps(self):
        return [
            (
                "Clustering Tab",
                "Click the '+' button to load your metadata database, or select a previously loaded one from the dropdown.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.db_loader_add_button],
            ),
            (
                "Clustering Tab",
                "Click to configure your clustering settings.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.cluster_settings_button],
            ),
            (
                "Clustering Tab",
                "The Clustering tab also allows you to merge clusters. First, select the group whose label you want to keep.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.label_x_comboBox],
            ),
            (
                "Clustering Tab",
                "Then, select the group you want to combine it with.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.label_y_comboBox],
            ),
            (
                "Clustering Tab",
                "If you're happy with your selection, click 'Merge'. The selected clusters will be combined under the first group's label.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.merge_button],
            ),
            (
                "Clustering Tab",
                "Finally, click 'Commit' to apply the changes to the loaded database. A new column called 'cluster_label' will be added.",
                "ClusteringView",
                lambda: [self.clusteringcontrols.commit_button],
            ),
        ]
