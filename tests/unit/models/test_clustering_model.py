"""
Unit-test suite for ClusteringModel.

Step 4c moved the clustering computation off ``ClusteringView`` and onto this model:
``normalize_column_data`` and ``cluster_hdbscan`` came across verbatim (they were
``_normalize_column_data`` and ``_update_clusters_hdbscan``), and the Gaussian-mixture
branch of the View's ``_load_metadata_and_cluster`` became ``cluster_gaussian_mixture``
beside them. ``cluster`` is the single entry point the Controller calls.

The eleven tests for the two moved methods came from
``tests/unit/views/test_clustering_view.py`` with their assertions unchanged - only the
receiver moved, from ``view`` to ``model``. The tests for ``cluster`` and
``cluster_gaussian_mixture`` are new, because neither existed as a callable unit before:
the mixture branch was inline in a 136-line View method and had no direct coverage at
all.

No Qt anywhere. That is the point of the step - this used to need a constructed
``QWidget`` to reach.
"""

import numpy as np
import pandas as pd
import pytest

from poriscope.plugins.analysistabs.ClusteringModel import ClusteringModel
from poriscope.utils.MetaModel import MetaModel


@pytest.fixture
def model() -> ClusteringModel:
    """
    A ClusteringModel.

    :return: the model under test
    :rtype: ClusteringModel
    """
    return ClusteringModel()


def _make_df(*cols: str) -> pd.DataFrame:
    """
    Small DataFrame with the given column names, float data plus an ``id``.

    :param \\*cols: the float column names to build
    :type \\*cols: str
    :return: the frame
    :rtype: pd.DataFrame
    """
    rng = np.random.default_rng(42)
    data: dict = {c: rng.random(50).astype(float) for c in cols}
    data["id"] = np.arange(50)
    return pd.DataFrame(data)


def _two_clusters(n: int = 200) -> pd.DataFrame:
    """
    A frame with two well-separated blobs, so clustering has a right answer.

    :param n: total row count, split evenly between the two blobs
    :type n: int
    :return: the frame
    :rtype: pd.DataFrame
    """
    rng = np.random.default_rng(1)
    half = n // 2
    return pd.DataFrame(
        {
            "a": np.concatenate([rng.normal(0, 0.1, half), rng.normal(2, 0.1, half)]),
            "b": np.concatenate([rng.normal(0, 0.1, half), rng.normal(2, 0.1, half)]),
            "id": np.arange(n),
        }
    )


# ===========================================================================
# Construction / inheritance
# ===========================================================================


class TestConstruction:
    """It is still a MetaModel, now with behaviour of its own."""

    def test_instantiates_without_error(self, model: ClusteringModel) -> None:
        """No Qt, no view, no controller."""
        assert model is not None

    def test_is_instance_of_meta_model(self, model: ClusteringModel) -> None:
        """The base contract is unchanged by Step 4c."""
        assert isinstance(model, MetaModel)


# ===========================================================================
# normalize_column_data - moved verbatim from ClusteringView
# ===========================================================================


class TestNormalizeColumnData:
    """MAD-based normalization of float columns, leaving ints and exclusions alone."""

    def test_normalises_float_columns(self, model: ClusteringModel) -> None:
        """Median of a normalised column should be about zero."""
        df = _make_df("a", "b")
        norm = model.normalize_column_data(df, exclude_cols=["id"])

        assert abs(norm["a"].median()) < 0.1

    def test_excludes_specified_columns(self, model: ClusteringModel) -> None:
        """An excluded column comes back untouched."""
        df = _make_df("a", "b")
        original_a = df["a"].copy()
        norm = model.normalize_column_data(df, exclude_cols=["a", "id"])

        pd.testing.assert_series_equal(norm["a"], original_a)

    def test_id_column_excluded(self, model: ClusteringModel) -> None:
        """Row identity must survive normalization."""
        df = _make_df("a")
        norm = model.normalize_column_data(df, exclude_cols=["id"])

        assert list(norm["id"]) == list(df["id"])

    def test_zero_mad_column_unchanged(self, model: ClusteringModel) -> None:
        """A constant column has zero MAD, and dividing by it is guarded."""
        df = pd.DataFrame({"a": [5.0] * 50, "id": range(50)})
        norm = model.normalize_column_data(df, exclude_cols=["id"])

        pd.testing.assert_series_equal(norm["a"], df["a"])

    def test_does_not_modify_original(self, model: ClusteringModel) -> None:
        """It copies first; the caller's frame is not mutated."""
        df = _make_df("a")
        original = df["a"].copy()
        model.normalize_column_data(df, exclude_cols=["id"])

        pd.testing.assert_series_equal(df["a"], original)

    def test_int_columns_not_normalised(self, model: ClusteringModel) -> None:
        """Only float columns are touched, which is what keeps ``id`` intact."""
        df = pd.DataFrame({"a": np.arange(50, dtype=int), "id": range(50)})
        norm = model.normalize_column_data(df, exclude_cols=["id"])

        pd.testing.assert_series_equal(norm["a"], df["a"])

    def test_none_excludes_nothing(self, model: ClusteringModel) -> None:
        """
        The default normalizes every float column.

        Documented by the signature and worth pinning, since every caller in the app
        passes an explicit list including ``id``.
        """
        df = pd.DataFrame({"a": np.arange(50, dtype=float), "id": range(50)})
        norm = model.normalize_column_data(df)

        assert abs(norm["a"].median()) < 0.1


# ===========================================================================
# cluster_hdbscan - moved verbatim from ClusteringView
# ===========================================================================


class TestClusterHDBSCAN:
    """Labels and probabilities, one per row, with ``id`` kept out of the fit."""

    def test_returns_labels_and_probs(self, model: ClusteringModel) -> None:
        """One of each per row."""
        labels, probs = model.cluster_hdbscan(_two_clusters(), min_cluster_size=5)

        assert len(labels) == 200
        assert len(probs) == 200

    def test_labels_are_integers(self, model: ClusteringModel) -> None:
        """Labels index clusters, with -1 for noise."""
        labels, _ = model.cluster_hdbscan(_two_clusters(), min_cluster_size=5)

        assert labels.dtype in (np.int32, np.int64, int)

    def test_probs_between_0_and_1(self, model: ClusteringModel) -> None:
        """Confidences are probabilities."""
        _, probs = model.cluster_hdbscan(_two_clusters(), min_cluster_size=5)

        assert np.all(probs >= 0) and np.all(probs <= 1)

    def test_finds_two_clusters(self, model: ClusteringModel) -> None:
        """Two well-separated blobs are found as clusters rather than as noise."""
        labels, _ = model.cluster_hdbscan(_two_clusters(), min_cluster_size=5)
        non_noise = set(labels) - {-1}

        assert len(non_noise) >= 1

    def test_custom_params(self, model: ClusteringModel) -> None:
        """All three parameters are accepted and still return a label per row."""
        labels, _ = model.cluster_hdbscan(
            _two_clusters(),
            min_cluster_size=10,
            min_samples=2,
            cluster_selection_epsilon=0.5,
        )

        assert len(labels) == 200


# ===========================================================================
# cluster_gaussian_mixture - extracted from the View's inline branch
# ===========================================================================


class TestClusterGaussianMixture:
    """
    The mixture branch, which had no direct coverage before Step 4c.

    It was fifteen lines inline in a 136-line View method, reachable only by
    constructing the widget and answering two bus emits.
    """

    def test_returns_one_label_and_one_confidence_per_row(
        self, model: ClusteringModel
    ) -> None:
        """The shape contract the plotting code depends on."""
        labels, probs = model.cluster_gaussian_mixture(_two_clusters(60), 2)

        assert len(labels) == 60
        assert len(probs) == 60

    def test_finds_the_requested_number_of_components(
        self, model: ClusteringModel
    ) -> None:
        """``n_components`` is honoured, unlike HDBSCAN which decides for itself."""
        labels, _ = model.cluster_gaussian_mixture(_two_clusters(60), 2)

        assert len(set(labels)) == 2

    def test_is_seeded(self, model: ClusteringModel) -> None:
        """
        Two runs on the same rows agree.

        1.9.0 fixed the unseeded version; this pins that the fix survived the move.
        """
        first, _ = model.cluster_gaussian_mixture(_two_clusters(60), 2)
        second, _ = model.cluster_gaussian_mixture(_two_clusters(60), 2)

        assert np.array_equal(first, second)

    def test_id_is_not_a_feature(self, model: ClusteringModel) -> None:
        """
        ``id`` is carried for row identity and must not influence the fit.

        Asserted by clustering the same blobs twice with the ids reversed: a fit that
        used ``id`` as a feature would partition on it and give a different answer.
        """
        frame = _two_clusters(60)
        reversed_ids = frame.assign(id=frame["id"].to_numpy()[::-1])

        first, _ = model.cluster_gaussian_mixture(frame, 2)
        second, _ = model.cluster_gaussian_mixture(reversed_ids, 2)

        assert np.array_equal(first, second)


# ===========================================================================
# cluster - the entry point the Controller calls
# ===========================================================================


class TestCluster:
    """Normalize, then dispatch on the method name."""

    def test_hdbscan_returns_frame_labels_and_confidence(
        self, model: ClusteringModel
    ) -> None:
        """The three-tuple ``ClusteringController.cluster`` unpacks."""
        frame, labels, probs = model.cluster(
            _two_clusters(), ["id"], "HDBSCAN", {"min_cluster_size": 5}
        )

        assert len(frame) == 200
        assert len(labels) == 200
        assert len(probs) == 200

    def test_gaussian_mixtures_returns_frame_labels_and_confidence(
        self, model: ClusteringModel
    ) -> None:
        """The other branch, same shape."""
        frame, labels, probs = model.cluster(
            _two_clusters(60), ["id"], "Gaussian Mixtures", {"n_components": 2}
        )

        assert len(frame) == 60
        assert len(labels) == 60
        assert len(probs) == 60

    def test_the_returned_frame_is_normalized(self, model: ClusteringModel) -> None:
        """
        It returns the frame it clustered, not the one it was given.

        The View plots this frame, so it has to be the normalized one - plotting the
        raw frame against labels computed from the normalized one would put points in
        the wrong places.
        """
        raw = _make_df("a", "b")
        frame, _, _ = model.cluster(raw, ["id"], "HDBSCAN", {"min_cluster_size": 5})

        assert abs(frame["a"].median()) < 0.1
        assert not np.allclose(frame["a"].to_numpy(), raw["a"].to_numpy())

    def test_exclusions_are_honoured(self, model: ClusteringModel) -> None:
        """An excluded column reaches the clusterer unnormalized."""
        raw = _make_df("a", "b")
        original_a = raw["a"].copy()
        frame, _, _ = model.cluster(
            raw, ["a", "id"], "HDBSCAN", {"min_cluster_size": 5}
        )

        pd.testing.assert_series_equal(frame["a"], original_a)

    def test_an_unknown_method_raises(self, model: ClusteringModel) -> None:
        """
        The Controller catches this and reports it on the status panel.

        The View also rejects an unknown method before emitting, so reaching this
        means the two have disagreed - which is worth failing loudly rather than
        silently clustering by some default.
        """
        with pytest.raises(ValueError, match="Unknown clustering method"):
            model.cluster(_make_df("a"), ["id"], "K Means", {})
