"""
Characterization tests for ``notify_plugin_state_changed`` across all five tabs.

In every View this method's body executes under the e2e suites, but no test named it, so nothing asserted
which notifications it acts on and which it ignores. It was a five-way duplicate
slated for merging, so the behaviour had to be pinned before the copies were
touched.

Two of the five share one implementation - refresh this tab's column list, but
*only* when a ``MetaDatabaseLoader``'s columns changed and the loader that changed
is the one currently selected here. The filtering is the whole method; a merge that
loosened any of the three conditions would make every tab refetch its columns on
every unrelated plugin event, which is invisible in a test that only checks the
happy path.

**Not a redundant override.** ``notify_plugin_state_changed`` is
``@abstractmethod`` on ``MetaView``, so the do-nothing bodies of the inert tabs are
required by the ABC, not redundant; deleting them would make those classes
uninstantiable. The recorded abstract surface in
``tests/unit/plugins/test_mvc_base_contracts.py`` is what fails if the base stops
declaring it abstract.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from poriscope.plugins.analysistabs.ClusteringView import ClusteringView
from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization

#: The two tabs that react, paired with the attribute holding their controls
#: widget - the only thing that differs between the two otherwise-identical
#: implementations.
REACTING = (
    (ClusteringView, "clusteringcontrols"),
    (MetadataView, "metadatacontrols"),
)

#: The tabs whose correct response is to do nothing. Protein reads no column names,
#: so the one notification the app sends - a loader gaining columns - is not its concern.
INERT = (EventAnalysisView, RawDataView, ProteinView)


def build(cls: type, controls_attr: str = "", selected: str = "") -> Any:
    """
    Build a view with only what ``notify_plugin_state_changed`` reads.

    :param cls: the view class
    :type cls: type
    :param controls_attr: name of the controls attribute to populate, if any
    :type controls_attr: str
    :param selected: the loader name the controls combobox should report
    :type selected: str
    :return: the view
    :rtype: Any
    """
    instance = cls.__new__(cls)
    shadow_signals(instance, cls)
    if controls_attr:
        controls = MagicMock()
        controls.db_loader_comboBox.currentText.return_value = selected
        setattr(instance, controls_attr, controls)
    return instance


class TestTabsThatRefreshTheirColumns:
    """Clustering and Metadata both act on the same narrow condition."""

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_a_matching_notification_refreshes_the_columns(
        self, cls: type, controls_attr: str, mocker
    ) -> None:
        """The one case that should do something: right metaclass, reason and key."""
        view = build(cls, controls_attr, selected="loader-a")
        refresh = mocker.patch.object(view, "update_available_columns")

        view.notify_plugin_state_changed("MetaDatabaseLoader", "loader-a", "columns")

        refresh.assert_called_once_with("loader-a")

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_another_metaclass_is_ignored(
        self, cls: type, controls_attr: str, mocker
    ) -> None:
        """A reader or a writer changing state is none of this tab's business."""
        view = build(cls, controls_attr, selected="loader-a")
        refresh = mocker.patch.object(view, "update_available_columns")

        view.notify_plugin_state_changed("MetaReader", "loader-a", "columns")

        refresh.assert_not_called()

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_another_reason_is_ignored(
        self, cls: type, controls_attr: str, mocker
    ) -> None:
        """Only a columns change matters; the loader can change in other ways."""
        view = build(cls, controls_attr, selected="loader-a")
        refresh = mocker.patch.object(view, "update_available_columns")

        view.notify_plugin_state_changed("MetaDatabaseLoader", "loader-a", "settings")

        refresh.assert_not_called()

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_a_loader_this_tab_is_not_showing_is_ignored(
        self, cls: type, controls_attr: str, mocker
    ) -> None:
        """
        The condition that actually costs something to get wrong.

        Several tabs can be open on different loaders at once. Without this check
        every tab would refetch its column list whenever any loader anywhere
        committed new columns.
        """
        view = build(cls, controls_attr, selected="loader-a")
        refresh = mocker.patch.object(view, "update_available_columns")

        view.notify_plugin_state_changed("MetaDatabaseLoader", "loader-b", "columns")

        refresh.assert_not_called()

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_the_selection_is_read_at_notification_time(
        self, cls: type, controls_attr: str, mocker
    ) -> None:
        """
        The comparison uses the combobox's current text, not a cached value.

        Pinned because tab state lives on the Model, and a cached copy
        would go stale exactly when the user switches loaders.
        """
        view = build(cls, controls_attr, selected="loader-b")
        refresh = mocker.patch.object(view, "update_available_columns")

        view.notify_plugin_state_changed("MetaDatabaseLoader", "loader-b", "columns")

        refresh.assert_called_once_with("loader-b")
        getattr(view, controls_attr).db_loader_comboBox.currentText.assert_called()

    @pytest.mark.parametrize(("cls", "controls_attr"), REACTING)
    def test_it_returns_none(self, cls: type, controls_attr: str, mocker) -> None:
        """It is a notification sink; the caller ignores any return."""
        view = build(cls, controls_attr, selected="loader-a")
        mocker.patch.object(view, "update_available_columns")

        assert (
            view.notify_plugin_state_changed(
                "MetaDatabaseLoader", "loader-a", "columns"
            )
            is None
        )


class TestTabsThatDeliberatelyDoNothing:
    """RawData, EventAnalysis and Protein react to no notification at all."""

    @pytest.mark.parametrize("cls", INERT)
    def test_it_is_a_no_op_for_every_notification(self, cls: type) -> None:
        """
        Including the one the other two act on, which is the point.

        These tabs have no column list to refresh. If a future change gives them
        one, this test failing is the reminder to implement the hook rather than
        leave it a silent ``pass``.
        """
        view = build(cls)

        for metaclass in ("MetaDatabaseLoader", "MetaReader", ""):
            for reason in ("columns", "settings", ""):
                assert (
                    view.notify_plugin_state_changed(metaclass, "any", reason) is None
                )
