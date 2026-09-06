"""
Characterization tests for ``notify_plugin_state_changed`` across all five tabs.

The refactor-coverage audit reported this method as ``RUNS ONLY`` in every View:
its body executes under the e2e suites, but no test named it, so nothing asserted
which notifications it acts on and which it ignores. It is a five-way duplicate
that Step 3 merges, so the behaviour has to be pinned before the copies are
touched.

Three of the five share one implementation - refresh this tab's column list, but
*only* when a ``MetaDatabaseLoader``'s columns changed and the loader that changed
is the one currently selected here. The filtering is the whole method; a merge that
loosened any of the three conditions would make every tab refetch its columns on
every unrelated plugin event, which is invisible in a test that only checks the
happy path.

**A correction to the plan.** ``refactor_2.0.0.md`` Step 3c says RawData and
EventAnalysis "re-override ``_factors`` and ``notify_plugin_state_changed``,
shadowing base versions they could inherit - delete". That is true of ``_factors``,
which is concrete on ``MetaView``, and **false of this method**, which is
``@abstractmethod`` there. Their ``pass`` bodies are required by the ABC, not
redundant, and deleting them would make both classes uninstantiable. That is
asserted below so the claim cannot be acted on by mistake.
"""

from typing import Any

import pytest
from PySide6.QtWidgets import QBoxLayout

from poriscope.plugins.analysistabs.ClusteringView import ClusteringView
from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.analysistabs.ProteinView import ProteinView
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.utils.MetaView import MetaView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization

#: The three tabs that react, paired with the attribute holding their controls
#: widget - the only thing that differs between the three otherwise-identical
#: implementations.
REACTING = (
    (ClusteringView, "clusteringcontrols"),
    (MetadataView, "metadatacontrols"),
    (ProteinView, "proteincontrols"),
)

#: The two tabs whose correct response is to do nothing.
INERT = (EventAnalysisView, RawDataView)


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
    from unittest.mock import MagicMock

    instance = cls.__new__(cls)
    shadow_signals(instance, cls)
    if controls_attr:
        controls = MagicMock()
        controls.db_loader_comboBox.currentText.return_value = selected
        setattr(instance, controls_attr, controls)
    return instance


class TestTabsThatRefreshTheirColumns:
    """Clustering, Metadata and Protein all act on the same narrow condition."""

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

        Pinned because Step 4d moves tab state to the Model, and a cached copy
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
    """RawData and EventAnalysis react to no notification at all."""

    @pytest.mark.parametrize("cls", INERT)
    def test_it_is_a_no_op_for_every_notification(self, cls: type) -> None:
        """
        Including the one the other three act on, which is the point.

        These tabs have no column list to refresh. If a future change gives them
        one, this test failing is the reminder to implement the hook rather than
        leave it a silent ``pass``.
        """
        view = build(cls)

        for metaclass in ("MetaDatabaseLoader", "MetaReader", ""):
            for reason in ("columns", "settings", ""):
                assert view.notify_plugin_state_changed(metaclass, "any", reason) is None


class TestTheHookIsRequiredByTheBase:
    """
    Guards a claim in the plan that is wrong, so it cannot be acted on by mistake.

    Step 3c lists ``notify_plugin_state_changed`` alongside ``_factors`` as an
    override that shadows an inheritable base version. ``_factors`` is concrete on
    ``MetaView``; this one is abstract, and its own docstring says it "must be
    implemented by subclasses, even if the correct" response is to do nothing.
    """

    def test_the_base_declares_it_abstract(self) -> None:
        """So the two `pass` bodies are mandatory, not redundant."""
        assert "notify_plugin_state_changed" in MetaView.__abstractmethods__

    def test_factors_by_contrast_is_concrete_on_the_base(self) -> None:
        """The half of the Step 3c claim that does hold."""
        assert "_factors" not in MetaView.__abstractmethods__
        assert "_factors" in MetaView.__dict__

    def test_a_subclass_omitting_the_hook_cannot_be_instantiated(self) -> None:
        """
        The concrete consequence: deleting the `pass` bodies breaks both tabs.

        Instantiating is what raises, so this builds a subclass that implements
        every other abstract method and checks the ABC still refuses it.
        """

        class _MissingHook(MetaView):
            def _init(self) -> None:
                """Present."""

            def _set_control_area(self, layout: QBoxLayout) -> None:
                """Present."""

            def _reset_actions(self, axis_type: str = "2d") -> None:
                """Present."""

            def update_available_plugins(self, available_plugins: dict) -> None:
                """Present."""

        with pytest.raises(TypeError, match="notify_plugin_state_changed"):
            _MissingHook()
