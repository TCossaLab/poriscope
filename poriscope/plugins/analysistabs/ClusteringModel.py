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
from typing import Any, Dict, List, Optional, Tuple, override

import hdbscan
import numpy as np
import pandas as pd
from pandas.api.types import is_float_dtype
from sklearn.mixture import GaussianMixture

from poriscope.utils.DocstringDecorator import inherit_docstrings
from poriscope.utils.LogDecorator import log
from poriscope.utils.MetaModel import MetaModel


@inherit_docstrings
class ClusteringModel(MetaModel):
    """
    Subclass of MetaModel for handling clustering-related data processing.

    Owns the clustering computation itself. Step 4c moved it here out of
    ``ClusteringView``, which had been importing ``hdbscan``,
    ``sklearn.mixture.GaussianMixture`` and ``pandas.api.types.is_float_dtype`` into a
    ``QWidget``; none of those names appears in the View any more.

    The View asks for a result by emitting ``cluster_requested``;
    ``ClusteringController`` calls :meth:`cluster` and hands what comes back to
    ``ClusteringView.set_clustering_result``. That is Decision B's command/result path,
    and ``RawDataController.calculate_psd`` is the same shape.
    """

    logger = logging.getLogger(__name__)

    @log(logger=logger)
    @override
    def _init(self) -> None:
        pass

    @log(logger=logger)
    def cluster(
        self,
        frame: pd.DataFrame,
        exclude_cols: List[str],
        method: str,
        params: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """
        Normalize the given columns and cluster the frame by the named method.

        The single entry point the Controller calls. ``params`` carries values the View
        has already parsed and validated - integers and floats, not the raw strings from
        the settings dialog - so a malformed entry is reported to the user where they
        typed it rather than raised from in here.

        :param frame: the rows to cluster, carrying an ``id`` column for row identity
        :type frame: pd.DataFrame
        :param exclude_cols: columns to leave un-normalized, ``id`` among them
        :type exclude_cols: List[str]
        :param method: either ``"HDBSCAN"`` or ``"Gaussian Mixtures"``
        :type method: str
        :param params: the method's already-parsed parameters
        :type params: Dict[str, Any]
        :return: the normalized frame, the cluster labels, and the confidences
        :rtype: Tuple[pd.DataFrame, np.ndarray, np.ndarray]
        :raises ValueError: if the method is not one this model implements
        """
        frame = self.normalize_column_data(frame, exclude_cols=exclude_cols)

        if method == "HDBSCAN":
            labels, probs = self.cluster_hdbscan(frame, **params)
        elif method == "Gaussian Mixtures":
            labels, probs = self.cluster_gaussian_mixture(frame, **params)
        else:
            raise ValueError(f"Unknown clustering method: {method!r}")

        return frame, labels, probs

    @log(logger=logger)
    def normalize_column_data(
        self, df: pd.DataFrame, exclude_cols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Applies MAD-based normalization to float columns in the dataframe.

        :param df: Input DataFrame.
        :type df: pd.DataFrame
        :param exclude_cols: Columns to exclude from normalization. None means exclude nothing.
        :type exclude_cols: Optional[List[str]]
        :return: Normalized DataFrame.
        :rtype: pd.DataFrame
        """
        if exclude_cols is None:
            exclude_cols = []
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
    def cluster_hdbscan(
        self,
        df: pd.DataFrame,
        min_cluster_size: int = 30,
        min_samples: int = 1,
        cluster_selection_epsilon: float = 1,
    ) -> Tuple[np.ndarray, np.ndarray]:
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
        :rtype: Tuple[np.ndarray, np.ndarray]
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

    @log(logger=logger)
    def cluster_gaussian_mixture(
        self, df: pd.DataFrame, n_components: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fit a Gaussian mixture to the data and return its labels and confidences.

        Seeded (``random_state=42``, ``n_init=100``) so that re-running on the same rows
        gives the same answer, which 1.9.0 fixed and this move preserves.

        :param df: DataFrame to cluster.
        :type df: pd.DataFrame
        :param n_components: Number of mixture components to fit.
        :type n_components: int
        :return: Cluster labels and per-row confidences.
        :rtype: Tuple[np.ndarray, np.ndarray]
        """
        columns_except_id = df.columns[df.columns != "id"]
        clusterer = GaussianMixture(
            n_components=n_components, n_init=100, random_state=42
        )
        labels = clusterer.fit_predict(df[columns_except_id])
        probs = clusterer.predict_proba(df[columns_except_id])
        probs = np.max(probs, axis=1) / np.sum(probs, axis=1)
        return labels, probs
