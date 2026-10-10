"""
Equivalence tests for analysis-tab helpers that were, or could be, merged into a base.

The duplication ratchet counts byte-identical bodies; it cannot say whether two
copies *behave* the same, and it says nothing at all about a third copy that was
inlined instead of written as a method. That is what this file is for. Each group
below is a merge into a shared base, and the merge should be a decision someone
makes about known behaviour rather than a silent change.

Ten groups:

- ``_factors`` used to exist three times - ``MetaView`` plus byte-identical overrides
  in ``RawDataView`` and ``EventAnalysisView`` that shadowed the base. The overrides
  are gone, so what is checked now is the one implementation every tab inherits.
- ``createButton`` used to exist five times, four of them byte-identical, and
  the divergence was pinned so the merge had to decide it. **The majority version
  was promoted to** ``MetaControls``, so what is checked now is that exactly
  one copy survives and that it behaves as the majority version did.
- ``format_axis_label`` exists three times, and **the third one differs**.
  ``ProteinView.py:4037`` is a module-level function, ``MetadataView.py:3645`` is
  a byte-identical method, and ``ClusteringView.py:731-742`` is an inlined loop
  that neither strips a pre-existing trailing parenthetical nor rejects a
  whitespace-only unit. The two callable copies are asserted equal here, and the
  two specific behaviours the inline copy lacks are pinned as named tests so that
  merging all three is an explicit decision.
- ``get_selected_filters`` existed twice, in ``MetadataView`` and ``ProteinView``,
  differing only in the name each tab held its controls panel under. **It was
  promoted to** ``MetaSubsetTabView``, which reaches the panel through
  ``_subset_controls`` - a one-line property each tab implements over the name it
  already holds its panel under, so there is still only one copy of the panel. Every unit test that touches this method
  mocks it, so its real body had no unit coverage at all before the promotion -
  a mocked-everywhere body is untested, which is why it is pinned here.
- ``_rebuild_event_id_cache`` existed twice and **the copies diverged three ways**.
  ``ProteinView``'s also rejected a result with no ``event_id`` column, named the
  scope in its empty-subset message, and labelled an unnamed active filter with the
  filter expression instead of the word "Filter". **Protein's was promoted, by
  decision, on all three** - and reordered its first two checks, so that a result
  with no rows is an empty subset whether or not the loader returned columns with
  it. ``MetadataView`` had six tests for its copy and ``ProteinView`` had none, so
  the three branches only Protein's version had are pinned here.
- ``_show_add_filter_dialog`` and ``show_edit_filter_dialog`` existed twice, only 14
  diff lines apart, and carried **both** of the pair's real divergences: the columns
  the throwaway validation query is built from, and whether an invalid raw filter is
  reported in a modal or on the status panel. **Both were promoted to**
  ``MetaSubsetTabView``, taking Metadata's modal by the user's choice and Protein's
  columns handling, each behind a named helper. The per-tab tests cover the modal, and
  the column selection is no longer here at all: it moved to
  ``MetaSubsetTabController.validate_filter``, which asks the loader for its *events*
  columns instead of guessing three, so ``_validation_columns`` and the tests that
  pinned its fallback are gone.
- ``_load_filter`` existed twice and diverged once: only ``ProteinView`` let a filter
  whose name ends in ``_raw`` skip validation. **Protein's was promoted**, which
  fixes the metadata tab rather than merging it - see the group below for the measured
  consequence of not bypassing.
- **Five more methods collapsed once ``_subset_controls`` existed**:
  ``replace_filter_item``, ``update_filter_name``, ``_delete_filter``,
  ``on_raw_filter_validated`` and the answer-parking setter (``relay_query_result``
  then, ``set_event_id_rows`` now). Four of them differed
  *only* in the name each tab held its controls panel under, and that setter
  differed only in its docstring; ``on_raw_filter_validated`` carried the modal-vs-
  status-panel divergence a second time and was settled the same way. ``_delete_filter``
  was **abstract** on the base for the stated reason that each tab rebuilds its own
  filter widgets - which was only ever true because of the panel name.
- ``set_event_id_input`` lives once, on ``MetaSubsetTabControls``, for both subset
  panels; that base declares ``validate_inputs`` abstract because it calls it.
- ``_shift_range_and_update_plot`` lives once, on ``MetaSubsetTabView``, for both
  subset tabs, re-plotting through each tab's ``_replot_after_shift``; the plot
  handlers snap an entered Event ID through the shared ``_snap_to_filtered``.
"""

import json
import logging
from typing import Dict, List, Optional

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout

from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.analysistabs.ProteinView import ProteinView, format_axis_label
from poriscope.plugins.analysistabs.utils.clusteringcontrols import ClusteringControls
from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.utils.MetaControls import MetaControls
from poriscope.utils.MetaSubsetTabControls import MetaSubsetTabControls
from poriscope.utils.MetaSubsetTabView import MetaSubsetTabView
from poriscope.utils.MetaView import MetaView
from tests.unit.views._qt_mocks import shadow_signals

pytestmark = pytest.mark.characterization


class _BaseOnlyView(MetaView):
    """A concrete MetaView that adds nothing, so the base's own copy is reachable."""

    def _init(self) -> None:
        """Satisfy the abstract hook."""

    def _set_control_area(self, layout: QBoxLayout) -> None:
        """Satisfy the abstract hook."""

    def _reset_actions(self, axis_type: str = "2d") -> None:
        """Satisfy the abstract hook."""

    def update_available_plugins(self, available_plugins: Dict[str, List[str]]) -> None:
        """Satisfy the abstract hook."""

    def notify_plugin_state_changed(
        self, metaclass: str, plugin_key: str, reason: str
    ) -> None:
        """Satisfy the abstract hook."""


def build(cls: type) -> object:
    """
    Build a view without constructing any Qt widget.

    :param cls: the view class to instantiate
    :type cls: type
    :return: an instance with its declared signals shadowed
    :rtype: object
    """
    instance = cls.__new__(cls)
    shadow_signals(instance, cls)
    return instance


@pytest.fixture
def factors_copies() -> dict:
    """
    An instance carrying the one ``_factors`` implementation, the base's.

    :return: the carrier, keyed by class name
    :rtype: dict
    """
    return {"MetaView": build(_BaseOnlyView)}


# ===========================================================================
# _factors - one implementation, inherited by every tab
# ===========================================================================


class TestFactorsBehaviour:
    """What the shared implementation actually computes."""

    @pytest.mark.parametrize(
        ("n", "expected"),
        [
            (1, (1, 1)),
            (2, (1, 2)),
            (4, (2, 2)),
            (5, (2, 3)),
            (6, (2, 3)),
            (7, (2, 4)),
            (9, (3, 3)),
            (12, (3, 4)),
            (13, (3, 5)),
            (16, (4, 4)),
        ],
    )
    def test_it_returns_the_nearest_square_grid(
        self, factors_copies: dict, n: int, expected: tuple
    ) -> None:
        """
        A prime is rounded *up* to the next number that factors well.

        ``_factors(5)`` is ``(2, 3)``, not ``(1, 5)``: the loop increments ``n``
        until the factor pair differs by at most 2, so the caller gets a usable
        subplot grid with a spare cell rather than a one-row strip.
        """
        assert factors_copies["MetaView"]._factors(n) == expected

    def test_the_grid_is_never_smaller_than_requested(
        self, factors_copies: dict
    ) -> None:
        """The product must still fit every subplot the caller asked for."""
        for n in range(1, 41):
            rows, cols = factors_copies["MetaView"]._factors(n)
            assert rows * cols >= n


# ===========================================================================
# format_axis_label - two identical copies and one that is not
# ===========================================================================


LABEL_CASES = [
    ("Duration", "us", "Duration (us)"),
    ("Duration", None, "Duration"),
    ("Duration", "", "Duration"),
    ("Duration (us)", "ms", "Duration (ms)"),
    ("Duration (us)", None, "Duration"),
    ("Max Amplitude", "pA", "Max Amplitude (pA)"),
    # See TestFormatAxisLabelStripsFromTheFirstParenthesis: the strip reaches back
    # to the *first* parenthesis, not the last, so everything after "A" is lost.
    ("A (nested) label (us)", "pA", "A (pA)"),
    ("", "pA", " (pA)"),
]


@pytest.fixture
def metadata_view() -> MetadataView:
    """
    A MetadataView carrying the method-shaped copy of ``format_axis_label``.

    :return: the view
    :rtype: MetadataView
    """
    return build(MetadataView)


class TestFormatAxisLabelCopiesAgree:
    """The ProteinView function and the MetadataView method are interchangeable."""

    @pytest.mark.parametrize(("label", "unit", "expected"), LABEL_CASES)
    def test_both_copies_produce_the_expected_text(
        self,
        metadata_view: MetadataView,
        label: str,
        unit: Optional[str],
        expected: str,
    ) -> None:
        """Same input, same output, and the output itself is pinned."""
        assert format_axis_label(label, unit) == expected
        assert metadata_view.format_axis_label(label, unit) == expected


class TestFormatAxisLabelDivergenceFromClusteringView:
    """
    The two behaviours ``ClusteringView``'s inlined copy does not share.

    Named individually rather than folded into the table above, because these are
    precisely the decisions to make if the three are merged. The
    inline builder at ``ClusteringView.py:731-742`` composes its label from the
    column name and appends the unit under ``unit is not None and unit != "" and
    unit != " "`` - a three-way literal check rather than ``.strip()`` - and it
    never removes an existing parenthetical because it never receives one.
    """

    def test_a_whitespace_only_unit_is_rejected(
        self, metadata_view: MetadataView
    ) -> None:
        """
        ``.strip()`` rejects any run of spaces; the inline copy only rejects one.

        ``metadatacontrols`` manufactures the single-space unit deliberately, so a
        two-space unit reaching the inline copy would render ``Label (  )``.
        """
        for blank in (" ", "  ", "\t", "\n"):
            assert format_axis_label("Label", blank) == "Label"
            assert metadata_view.format_axis_label("Label", blank) == "Label"

    def test_an_existing_trailing_parenthetical_is_replaced_not_appended(
        self, metadata_view: MetadataView
    ) -> None:
        """
        Re-labelling the same axis twice must not accumulate units.

        The inline copy has no equivalent, which is safe only because it always
        builds its label from a bare column name.
        """
        once = format_axis_label("Duration", "us")
        twice = format_axis_label(once, "ms")

        assert once == "Duration (us)"
        assert twice == "Duration (ms)"
        assert metadata_view.format_axis_label(once, "ms") == "Duration (ms)"

    def test_nothing_is_stripped_without_a_trailing_parenthesis(
        self, metadata_view: MetadataView
    ) -> None:
        """The pattern is anchored at end-of-string, so a mid-label group survives."""
        assert format_axis_label("Rate (per pore) count", "Hz") == (
            "Rate (per pore) count (Hz)"
        )
        assert metadata_view.format_axis_label("Rate (per pore) count", "Hz") == (
            "Rate (per pore) count (Hz)"
        )


class TestFormatAxisLabelStripsFromTheFirstParenthesis:
    """
    A quirk found while writing these tests, characterized rather than fixed.

    The pattern is ``\\s*\\(.*?\\)$``. The ``.*?`` is lazy, but it is anchored at
    ``$``, so the leftmost match wins and ``.*?`` expands across every intervening
    ``)``. The strip therefore reaches back to the **first** parenthesis in the
    label, not the last, whenever the label happens to end in ``)``.

    That is a live defect for any column whose name contains parentheses: a column
    called ``Rate (per pore)`` plotted with unit ``Hz`` is labelled ``Rate (Hz)``,
    silently losing ``per pore``. It is queued in ``future_fixes.md`` rather than
    fixed here - this file's job is to record what the code does today so a
    merge of the three copies is not blamed for it later.
    """

    def test_a_label_ending_in_a_parenthetical_loses_everything_from_the_first_one(
        self, metadata_view: MetadataView
    ) -> None:
        """``a (b) (c) (d)`` collapses to ``a``, not to ``a (b) (c)``."""
        assert format_axis_label("a (b) (c) (d)", "X") == "a (X)"
        assert metadata_view.format_axis_label("a (b) (c) (d)", "X") == "a (X)"

    def test_a_meaningful_parenthetical_column_name_is_truncated(
        self, metadata_view: MetadataView
    ) -> None:
        """The user-visible consequence: ``per pore`` disappears from the axis."""
        assert format_axis_label("Rate (per pore)", "Hz") == "Rate (Hz)"
        assert metadata_view.format_axis_label("Rate (per pore)", "Hz") == "Rate (Hz)"

    def test_a_label_that_is_entirely_a_parenthetical_becomes_empty(
        self, metadata_view: MetadataView
    ) -> None:
        """Leaving a leading space before the unit, which is what the axis shows."""
        assert format_axis_label("(all)", "pA") == " (pA)"
        assert metadata_view.format_axis_label("(all)", "pA") == " (pA)"


# ===========================================================================
# createButton - promoted to MetaControls
# ===========================================================================


CONTROLS_CLASSES = (
    ClusteringControls,
    EventAnalysisControls,
    MetadataControls,
    ProteinControls,
    RawDataControls,
)


class TestCreateButtonWasPromoted:
    """
    ``createButton`` used to be identical in four of five controls files, with
    ``eventAnalysisControls`` omitting the ``setStyleSheet("")`` the other four
    ended with. That divergence was pinned here so the promotion had to decide it
    rather than merge it silently.

    **It was decided: the majority version was promoted, reset included.** So the
    source-text assertions this class used to carry are gone - there is one copy
    now, and what is worth checking is that there is exactly one, and that it
    behaves the way the majority version did.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """
        No subclass may keep its own, or the promotion was partial.

        A copy left behind would still shadow the base for that one tab, which is
        the failure that would otherwise be invisible - every test below passes
        either way, because they all resolve through the MRO.
        """
        assert "createButton" in MetaControls.__dict__
        for cls in CONTROLS_CLASSES:
            assert "createButton" not in cls.__dict__, cls.__name__

    @pytest.mark.parametrize("cls", CONTROLS_CLASSES, ids=lambda c: c.__name__)
    def test_every_tab_builds_the_majority_button(
        self, qapp: object, cls: type
    ) -> None:
        """
        The four properties the old per-file tests asserted, now asserted once per
        tab through the inherited method.
        """
        widget = cls()
        button = widget.createButton(widget, "My Button")

        assert button.text() == "My Button"
        assert button.isCheckable()
        assert not button.font().bold()
        assert widget.createButton(widget, "X", bold=True).font().bold()

    @pytest.mark.parametrize("cls", CONTROLS_CLASSES, ids=lambda c: c.__name__)
    def test_the_stylesheet_reset_is_the_accepted_behaviour_change(
        self, qapp: object, cls: type
    ) -> None:
        """
        EventAnalysis's buttons now run the reset its own copy omitted.

        The measured consequence is none: ``setStyleSheet("")`` leaves the widget's
        own stylesheet exactly as an untouched widget's, and it does not block a
        parent stylesheet's cascade either - so "Resetting to default style" was
        never what the call did. That is why promoting the majority version was
        free, and this test records the reasoning rather than only the outcome.
        """
        widget = cls()
        assert widget.createButton(widget, "X").styleSheet() == ""


# ===========================================================================
# get_selected_filters - two copies, promoted to MetaSubsetTabView
# ===========================================================================


SUBSET_TABS = (MetadataView, ProteinView)

#: What ``MetaSubsetTabView`` still asks a subclass for. Asserted whole rather than
#: membership-by-membership, because the base's abstract set is published contract:
#: a promotion that quietly drops one, or a new one added without a changelog note,
#: should fail here. ``handle_parameter_change`` is declared because
#: ``MetaView._set_control_area`` had always required it without stating so.
ABSTRACT_MEMBERS = frozenset(
    {
        "_init",
        "_replot_after_shift",
        "_reset_actions",
        "_subset_controls",
        "handle_parameter_change",
        "notify_plugin_state_changed",
        "update_available_plugins",
    }
)


def build_subset_tab(view_cls: type) -> object:
    """
    A subset-tab view holding a real controls panel, without building the tab.

    ``_build_controls`` is the one place either tab constructs its panel and
    stores it under its own name, so calling it here is exactly what
    ``MetaView._set_control_area`` does, and the ``_subset_controls`` property
    then resolves the same way it does in the running app. The promoted method
    therefore runs against a real ``MultiSelectFilterComboBox`` rather than a stub.

    :param view_cls: the subset tab's view class
    :type view_cls: type
    :return: the view, with a panel built and no filters defined yet
    :rtype: object
    """
    view = build(view_cls)
    view._build_controls()
    view.subset_filters = {}
    return view


class TestGetSelectedFiltersWasPromoted:
    """
    One copy, on the base, behaving as both tabs' copies did.

    The two copies were identical but for ``self.metadatacontrols`` against
    ``self.proteincontrols``, so there was no divergence to decide - but there was
    also nothing asserting the behaviour, because all forty-odd unit tests that
    reach this method replace it with a ``Mock``. The tests below run the real
    body through a real ``MultiSelectFilterComboBox``.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """
        Neither tab may keep its own, or the promotion was partial.

        A leftover copy would shadow the base for that one tab, and every
        behavioural test below would still pass, because they resolve through the
        MRO.
        """
        assert "get_selected_filters" in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert "get_selected_filters" not in view_cls.__dict__, view_cls.__name__

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_nothing_selected_gives_nothing(self, qapp: object, view_cls: type) -> None:
        """A freshly populated combobox selects nothing, so the result is empty."""
        view = build_subset_tab(view_cls)
        view.subset_filters = {"Short": "WHERE dwell < 1"}
        view._subset_controls.update_filters(["Short"])

        assert view.get_selected_filters() == {}

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_selected_names_come_back_mapped_to_their_sql(
        self, qapp: object, view_cls: type
    ) -> None:
        """Each selected name carries the WHERE clause held in ``subset_filters``."""
        view = build_subset_tab(view_cls)
        view.subset_filters = {
            "Short": "WHERE dwell < 1",
            "Long": "WHERE dwell > 5",
            "Unpicked": "WHERE dwell > 0",
        }
        view._subset_controls.update_filters(["Short", "Long", "Unpicked"])
        view._subset_controls.filter_comboBox.selectItem("Long")

        assert view.get_selected_filters() == {"Long": "WHERE dwell > 5"}

        view._subset_controls.filter_comboBox.selectItem("Short")

        assert view.get_selected_filters() == {
            "Short": "WHERE dwell < 1",
            "Long": "WHERE dwell > 5",
        }

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_name_with_no_stored_sql_maps_to_the_empty_string(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        The ``.get(name, "")`` fallback, pinned because it is load-bearing.

        "Full Dataset" is offered in the combobox with no WHERE clause behind it,
        and the callers rely on the empty string rather than a ``KeyError`` or a
        missing key - the query builders join these clauses, so an absent entry
        and an empty one are not the same thing downstream.
        """
        view = build_subset_tab(view_cls)
        view.subset_filters = {"Long": "WHERE dwell > 5"}
        view._subset_controls.update_filters(["Full Dataset", "Long"])
        view._subset_controls.filter_comboBox.selectItem("Full Dataset")

        assert view.get_selected_filters() == {"Full Dataset": ""}


# ===========================================================================
# _rebuild_event_id_cache - two copies, three divergences, promoted to the base
# ===========================================================================


def answer_query_with(view: object, frame: object) -> None:
    """
    Make the view's next ``load_metadata`` round-trip park ``frame``.

    ``_rebuild_event_id_cache`` clears ``event_id_rows`` before it asks, precisely so
    a query that did not run cannot be read as this call's answer, so a test cannot
    simply assign the attribute up front.

    The request is the ``event_id_cache_requested`` intent, answered by
    ``MetaSubsetTabController.load_event_id_cache``. The stub stands in for that
    Controller and sets what it sets - a stub that did nothing would make every
    assertion below vacuous.

    :param view: the view whose request should be answered
    :type view: object
    :param frame: whatever the loader should appear to have returned
    :type frame: object
    """

    def deliver(*_args: object) -> None:
        view.event_id_rows = frame

    view.event_id_cache_requested.connect(deliver)


class TestRebuildEventIdCacheWasPromoted:
    """
    One copy, on the base, carrying ProteinView's answer to all three divergences.

    ``MetadataView``'s six tests for its own copy still pass unchanged and are
    left where they are; what is pinned here is the three behaviours only
    ``ProteinView``'s copy had, plus the reordering of the two failure checks.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """Neither tab may keep its own, or the promotion was partial."""
        assert "_rebuild_event_id_cache" in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert "_rebuild_event_id_cache" not in view_cls.__dict__, view_cls.__name__

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_populated_result_without_event_id_is_an_error(
        self, qapp: object, view_cls: type, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        ProteinView's guard, which MetadataView lacked.

        Metadata indexed straight into ``result["event_id"]``, so a loader that
        returned rows without that column raised a ``KeyError`` out of a Qt slot
        rather than reporting anything. The promoted copy reports it.
        """
        view = build_subset_tab(view_cls)
        answer_query_with(view, pd.DataFrame({"something_else": [1, 2]}))

        with caplog.at_level(logging.ERROR):
            assert (
                view._rebuild_event_id_cache("loader", "dwell > 1", None, None) is False
            )

        assert "Could not query event ids" in caplog.text
        view.add_text_to_display.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_no_result_at_all_is_an_error(
        self, qapp: object, view_cls: type, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``None`` means the query could not be built or run, not an empty subset."""
        view = build_subset_tab(view_cls)
        answer_query_with(view, None)

        with caplog.at_level(logging.ERROR):
            assert (
                view._rebuild_event_id_cache("loader", "dwell > 1", None, None) is False
            )

        assert "Could not query event ids" in caplog.text

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        "frame",
        [pd.DataFrame(), pd.DataFrame({"event_id": []})],
        ids=["no_columns", "with_columns"],
    )
    def test_a_result_with_no_rows_is_an_empty_subset_either_way(
        self, qapp: object, view_cls: type, frame: object
    ) -> None:
        """
        Why the two failure checks are reordered from either original copy.

        A real loader returns a zero-row frame that still carries its columns, so
        both orders agree in production - but ``MetadataView``'s own test feeds a
        bare ``pd.DataFrame()``, and under Protein's order that columnless frame
        was reported as a malformed query rather than as no matching events.
        Emptiness is the more specific fact, so it is checked first.
        """
        view = build_subset_tab(view_cls)
        answer_query_with(view, frame)

        assert view._rebuild_event_id_cache("loader", "dwell > 1", None, None) is False

        message = view.add_text_to_display.emit.call_args[0][0]
        assert message == "No filtered events found for the current scope."

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_an_unnamed_active_filter_is_labelled_with_its_expression(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        ProteinView's fallback, chosen over Metadata's placeholder word "Filter".

        The combobox can hold no selection while a filter is still in force, and
        the status line is more use naming the expression than saying "Filter".
        """
        view = build_subset_tab(view_cls)
        answer_query_with(view, pd.DataFrame({"event_id": [7, 2, 5]}))

        assert view._rebuild_event_id_cache("loader", "dwell > 1", None, None) is True

        message = view.add_text_to_display.emit.call_args[0][0]
        assert message.startswith('"dwell > 1" subset: 3 total')
        assert "first event_id: 2" in message
        assert "last event_id: 7" in message
        assert view.filtered_event_ids == [2, 5, 7]

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_the_scope_is_recorded_for_the_staleness_checks(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        The four navigation values, whose annotations are declared on the base.

        The scope is what the plot handlers compare against to decide whether the
        cache still applies, so a rebuild that populated the ids but forgot the
        scope would leave navigation reading a cache for the wrong channel.
        """
        view = build_subset_tab(view_cls)
        answer_query_with(view, pd.DataFrame({"event_id": [1, 2]}))

        view._rebuild_event_id_cache("loader", "dwell > 1", "exp1", 2)

        assert view.current_sql_filter == "dwell > 1"
        assert view.current_experiment == "exp1"
        assert view.current_channel == 2


# ===========================================================================
# the two filter dialogs - two copies each, promoted to the base
# ===========================================================================


class TestFilterDialogsWerePromoted:
    """
    One copy of each on the base, with the two divergences behind named helpers.

    ``show_edit_filter_dialog`` was also **abstract** on the base until this
    promotion. The reason recorded for that - each tab rebuilding its own filter
    widgets - belonged to ``_delete_filter``; neither copy of this method touched
    a filter widget.
    """

    @pytest.mark.parametrize(
        "name", ["_show_add_filter_dialog", "show_edit_filter_dialog"]
    )
    def test_the_base_owns_the_only_copy(self, name: str) -> None:
        """Neither tab may keep its own, or the promotion was partial."""
        assert name in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert name not in view_cls.__dict__, f"{view_cls.__name__}.{name}"

    def test_show_edit_filter_dialog_is_no_longer_abstract(self) -> None:
        """
        The base's abstract set is part of its published contract.

        A plugin subclassing ``MetaSubsetTabView`` had to implement this and now
        inherits it, so the count is asserted rather than left to be noticed.
        """
        assert "show_edit_filter_dialog" not in MetaSubsetTabView.__abstractmethods__
        assert MetaSubsetTabView.__abstractmethods__ == ABSTRACT_MEMBERS


# ===========================================================================
# _load_filter - two copies, one of them missing the raw bypass
# ===========================================================================


def write_filter_file(tmp_path: object, filters: dict) -> str:
    """
    Write a filter file for ``_load_filter`` to read back.

    :param tmp_path: pytest's per-test temporary directory
    :type tmp_path: object
    :param filters: the filter name to SQL mapping to save
    :type filters: dict
    :return: the path written
    :rtype: str
    """
    path = tmp_path / "filters.json"
    path.write_text(json.dumps(filters), encoding="utf-8")
    return str(path)


class TestLoadFilterWasPromoted:
    """
    One copy, on the base, carrying ProteinView's raw bypass.

    This is the one promotion of the four that **fixes** a tab rather than merging
    two behaviours. Without the bypass a raw filter is handed to
    ``construct_metadata_query``, which builds a WHERE clause - and measurably does
    not refuse a complete SELECT: it splices it in after ``WHERE`` and returns an
    empty debug message, so validation *succeeds* and the filter is committed as
    ``<name>_raw_assisted``, renamed and reclassified.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """Neither tab may keep its own, or the promotion was partial."""
        for name in ("_load_filter", "set_loaded_filters"):
            assert name in MetaSubsetTabView.__dict__
            for view_cls in SUBSET_TABS:
                assert name not in view_cls.__dict__, f"{view_cls.__name__}.{name}"

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_raw_filter_is_stored_without_validation(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        ProteinView's bypass, which MetadataView lacked.

        Saving a raw filter and loading it back has to return the same name, or the
        filter stops being a raw filter - nothing downstream recognises
        ``*_raw_assisted``. Reading the file is the model's now, so this drives the
        half that decides what happens to what the file held.
        """
        view = build_subset_tab(view_cls)

        view.set_loaded_filters(
            {"big_events_raw": "SELECT event_id FROM events WHERE dwell > 5"},
            "a_loader",
        )

        assert view.subset_filters == {
            "big_events_raw": "SELECT event_id FROM events WHERE dwell > 5"
        }

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_with_no_loader_everything_is_stored_unvalidated(
        self, qapp: object, view_cls: type
    ) -> None:
        """Both copies already agreed on this; it is asserted so the merge kept it."""
        view = build_subset_tab(view_cls)

        view.set_loaded_filters(
            {"long_events": "dwell > 5", "raw_one_raw": "SELECT 1"}, ""
        )

        assert view.subset_filters == {
            "long_events": "dwell > 5",
            "raw_one_raw": "SELECT 1",
        }

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_the_dialog_half_only_asks(
        self,
        qapp: object,
        view_cls: type,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Choosing the file is the widget's job and reading it is not, so the request
        half touches no filter at all - not even one the file holds.
        """
        view = build_subset_tab(view_cls)
        path = write_filter_file(tmp_path, {"long_events": "dwell > 5"})
        monkeypatch.setattr(
            "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "JSON Files (*.json)")),
        )

        view._load_filter({"db_loader": "a_loader"})

        assert view.subset_filters == {}


# ===========================================================================
# the six methods _subset_controls unlocked
# ===========================================================================


PANEL_NAME_ONLY = (
    "replace_filter_item",
    "update_filter_name",
    "_delete_filter",
    "set_event_id_rows",
    "on_raw_filter_validated",
    "restore_subset_filters",
)


class TestThePanelNameMethodsWerePromoted:
    """
    The six that collapsed once the base had a name for the controls panel.

    Five differed only in ``metadatacontrols`` against ``proteincontrols``, and the
    answer-parking one only in its docstring - so with ``_subset_controls`` in place
    there was nothing left to decide except ``on_raw_filter_validated``'s modal,
    which the filter dialogs had already settled.

    ``restore_subset_filters`` is the late one: 20 of its 21 lines were identical
    and the odd one out was the panel name, but it was missed by the first sweep.

    That answer-parking method was ``relay_query_result``, filled over the signal
    bus. ``set_event_id_rows`` replaced it, filled by
    ``MetaSubsetTabController.load_event_id_cache``; it is still a promoted method
    with one copy on the base, which is what this class checks.
    """

    @pytest.mark.parametrize("name", PANEL_NAME_ONLY)
    def test_the_base_owns_the_only_copy(self, name: str) -> None:
        """Neither tab may keep its own, or the promotion was partial."""
        assert name in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert name not in view_cls.__dict__, f"{view_cls.__name__}.{name}"

    def test_delete_filter_is_no_longer_abstract(self) -> None:
        """
        ``_delete_filter`` is one fewer thing the base asks a subclass for.

        Its abstractness was documented as each tab rebuilding its own filter
        widgets. That reduced entirely to the panel name, so the reason went away
        with it. The whole set is asserted alongside, so a later addition or removal
        shows up here rather than passing unnoticed.
        """
        assert "_delete_filter" not in MetaSubsetTabView.__abstractmethods__
        assert MetaSubsetTabView.__abstractmethods__ == ABSTRACT_MEMBERS

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_deleting_a_filter_drops_it_from_both_the_dict_and_the_combobox(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        The promoted body, run against a real combobox for both tabs.

        Asserted through the widget rather than only the dict, because the dict half
        would pass even if the promoted copy were reaching the wrong panel.
        """
        view = build_subset_tab(view_cls)
        view.subset_filters = {"keep_me": "dwell > 1", "drop_me": "dwell > 2"}
        view._subset_controls.update_filters(["keep_me", "drop_me"])

        view._delete_filter("drop_me")

        assert view.subset_filters == {"keep_me": "dwell > 1"}
        remaining = [
            view._subset_controls.filter_comboBox.listWidget.item(i).data(Qt.UserRole)
            for i in range(view._subset_controls.filter_comboBox.listWidget.count())
        ]
        assert remaining == ["keep_me"]

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_set_event_id_rows_parks_the_answer_and_can_clear_it(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        Both directions matter, because the clear is what makes the read safe.

        ``_rebuild_event_id_cache`` sets it to None before asking, precisely so that a
        query that did not run cannot be read back as this call's answer, so a version
        that ignored a None would reintroduce the stale read the clear exists to
        prevent.
        """
        view = build_subset_tab(view_cls)
        frame = pd.DataFrame({"event_id": [1, 2]})

        view.set_event_id_rows(frame)
        assert view.event_id_rows is frame

        view.set_event_id_rows(None)
        assert view.event_id_rows is None

    def test_the_parked_answer_is_declared_on_the_base(self) -> None:
        """
        The annotation moved with the method that writes it.

        Only ``MetadataView`` declared it before; ``ProteinView`` assigned it at first
        use. It is now ``event_id_rows`` with a single writer, so the
        ``getattr(..., None)`` guards that used to surround every read are gone and the
        declaration is what keeps the type stated once.
        """
        assert "event_id_rows" in MetaSubsetTabView.__annotations__
        for view_cls in SUBSET_TABS:
            assert "event_id_rows" not in view_cls.__annotations__


# ===========================================================================
# set_event_id_input - shared by both subset panels on MetaSubsetTabControls
# ===========================================================================


SUBSET_CONTROLS = (MetadataControls, ProteinControls)


class TestSetEventIdInputWasPromoted:
    """
    One copy, on the controls base, shared by both subset tabs' panels.

    Pinned: no panel keeps its own copy, and the shared one writes the field
    without re-emitting its edit signal, then revalidates.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """A copy left on a panel would shadow the shared one for that tab."""
        assert "set_event_id_input" in MetaSubsetTabControls.__dict__
        for cls in SUBSET_CONTROLS:
            assert "set_event_id_input" not in cls.__dict__, cls.__name__

    def test_validate_inputs_is_owed_by_every_panel(self) -> None:
        """``set_event_id_input`` calls it, so every panel must define it."""
        assert MetaSubsetTabControls.__abstractmethods__ == frozenset(
            {"validate_inputs"}
        )

    @pytest.mark.parametrize("cls", SUBSET_CONTROLS, ids=lambda c: c.__name__)
    def test_the_field_shows_the_latest_value(self, qapp: object, cls: type) -> None:
        """Each call replaces what the field showed, rather than appending to it."""
        panel = cls()

        panel.set_event_id_input(5)
        assert panel.event_id_lineEdit.text() == "5"

        panel.set_event_id_input(12)
        assert panel.event_id_lineEdit.text() == "12"

    @pytest.mark.parametrize("cls", SUBSET_CONTROLS, ids=lambda c: c.__name__)
    def test_writing_the_field_is_silent_and_revalidates(
        self, qapp: object, cls: type, mocker: object
    ) -> None:
        """
        Navigation writes the snapped id without re-emitting the field's edit signal.

        A ``textChanged`` here would re-enter the panel's own handlers as though the
        user had typed, which is what the signal block around ``setText`` prevents;
        the buttons still need re-enabling for the new value, hence ``validate_inputs``.
        """
        panel = cls()
        seen: List[str] = []
        panel.event_id_lineEdit.textChanged.connect(seen.append)
        validate = mocker.patch.object(panel, "validate_inputs")

        panel.set_event_id_input(7)

        assert seen == []
        validate.assert_called_once_with()


# ===========================================================================
# _shift_range_and_update_plot - shared by both subset tabs on MetaSubsetTabView
# ===========================================================================


NO_SCOPE_MESSAGE = (
    "No experiments or channels are in scope, select at least one to navigate events"
)


def build_navigable_tab(view_cls: type, mocker: object) -> object:
    """
    A subset tab whose cache already holds ``[0, 3, 5, 7]`` for the current scope.

    The scope and filter match the cache, so navigation reads it without a rebuild,
    and ``_replot_after_shift`` is replaced so the test sees what would be plotted.

    :param view_cls: the subset tab's view class
    :type view_cls: type
    :param mocker: the pytest-mock fixture
    :type mocker: object
    :return: the view
    :rtype: object
    """
    view = build_subset_tab(view_cls)
    view.selected_experiment_and_channels_by_loader = {"l": {"exp1": ["0"]}}
    view.filtered_event_ids = [0, 3, 5, 7]
    view.current_sql_filter = ""
    view.current_experiment = "exp1"
    view.current_channel = 0
    mocker.patch.object(view, "_replot_after_shift")
    return view


def navigate(view: object, event_id: int, direction: str, n_events: int = 1) -> int:
    """
    Press one arrow from ``event_id`` and return the event_id it moved to.

    :param view: a view from ``build_navigable_tab``
    :type view: object
    :param event_id: the Event ID field's value before the press
    :type event_id: int
    :param direction: ``"left"`` or ``"right"``
    :type direction: str
    :param n_events: the N Events field's value
    :type n_events: int
    :return: the event_id passed on to be plotted
    :rtype: int
    """
    view._shift_range_and_update_plot(
        {"db_loader": "l", "event_id": event_id, "n_events": n_events}, direction
    )
    return view._replot_after_shift.call_args[0][0]["event_id"]


class TestShiftRangeAndUpdatePlotIsShared:
    """
    One navigation body for both subset tabs, run against each tab's real panel.

    Pinned: wrapping at both ends, the empty-scope message, the refusal of a scope
    with more than one filter, experiment or channel, the cache rebuild on a scope
    change, and an entered id past every cached one sitting just past the end - right
    goes to the first id, left to the last, silently.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """A copy left on a tab would shadow the shared one for that tab."""
        assert "_shift_range_and_update_plot" in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert (
                "_shift_range_and_update_plot" not in view_cls.__dict__
            ), view_cls.__name__

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        ("event_id", "direction", "n_events", "expected"),
        [
            (3, "right", 1, 5),
            (5, "left", 1, 3),
            (4, "right", 1, 7),
            (7, "right", 1, 0),
            (0, "left", 1, 7),
            (0, "left", 2, 5),
            (3, "right", 3, 0),
        ],
        ids=[
            "step_right",
            "step_left",
            "snaps_to_next_id_first",
            "wraps_right_to_first",
            "wraps_left_to_last",
            "wraps_left_to_last_window",
            "wraps_right_past_end",
        ],
    )
    def test_steps_and_wraps(
        self,
        qapp: object,
        mocker: object,
        view_cls: type,
        event_id: int,
        direction: str,
        n_events: int,
        expected: int,
    ) -> None:
        """Each press moves ``n_events`` places through the cache, wrapping at both ends."""
        view = build_navigable_tab(view_cls, mocker)

        assert navigate(view, event_id, direction, n_events) == expected
        assert view._subset_controls.event_id_lineEdit.text() == str(expected)
        view.add_text_to_display.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        ("direction", "expected"),
        [("right", 0), ("left", 7)],
        ids=["right_goes_to_first", "left_goes_to_last"],
    )
    def test_an_id_past_every_cached_one_sits_just_past_the_end(
        self,
        qapp: object,
        mocker: object,
        view_cls: type,
        direction: str,
        expected: int,
    ) -> None:
        """
        Neither arrow skips an event when the entered id has no match at or after it.

        Arriving at the first or last event is ordinary wrap-around, so nothing is
        reported; the report belongs to plotting, which snaps the entered id.
        """
        view = build_navigable_tab(view_cls, mocker)

        assert navigate(view, 99, direction) == expected
        view.add_text_to_display.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        "parameters",
        [{"db_loader": "other"}, {}],
        ids=["no_scope_for_loader", "no_loader"],
    )
    def test_nothing_in_scope_is_reported(
        self, qapp: object, mocker: object, view_cls: type, parameters: dict
    ) -> None:
        """No experiment or channel for the loader means nothing to navigate."""
        view = build_navigable_tab(view_cls, mocker)

        view._shift_range_and_update_plot(parameters, "right")

        view.add_text_to_display.emit.assert_called_once_with(
            NO_SCOPE_MESSAGE, view_cls.__name__
        )
        view._replot_after_shift.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        ("scope", "filters", "message"),
        [
            (
                {"exp2": ["0"], "exp1": ["0"]},
                [],
                "Only a single experiment and channel can be used for navigating events",
            ),
            (
                {"exp1": ["1", "0"]},
                [],
                "Only a single experiment and channel can be used for navigating events",
            ),
            (
                {"exp1": ["0"]},
                ["Short", "Long"],
                "Unable to navigate more than one subset at a time, select only one "
                "filter to apply",
            ),
        ],
        ids=["two_experiments", "two_channels", "two_filters"],
    )
    def test_a_scope_plot_events_refuses_is_refused_before_anything_moves(
        self,
        qapp: object,
        mocker: object,
        view_cls: type,
        scope: dict,
        filters: list,
        message: str,
    ) -> None:
        """
        The arrows re-plot events, so they refuse the scopes Plot Events refuses.

        The refusal comes before the cache is read or the Event ID field written: a
        press that moved the field and then had its plot refused would leave the field
        naming an event that was never shown.
        """
        view = build_navigable_tab(view_cls, mocker)
        view.selected_experiment_and_channels_by_loader = {"l": scope}
        view.subset_filters = {"Short": "dwell < 1", "Long": "dwell > 5"}
        view._subset_controls.update_filters(["Short", "Long"])
        for name in filters:
            view._subset_controls.filter_comboBox.selectItem(name)
        view._subset_controls.event_id_lineEdit.setText("3")
        rebuild = mocker.patch.object(view, "_rebuild_event_id_cache")

        view._shift_range_and_update_plot(
            {"db_loader": "l", "event_id": 3, "n_events": 1}, "right"
        )

        view.add_text_to_display.emit.assert_called_once_with(
            message, view_cls.__name__
        )
        assert view._subset_controls.event_id_lineEdit.text() == "3"
        assert view.filtered_event_ids == [0, 3, 5, 7]
        rebuild.assert_not_called()
        view._replot_after_shift.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_changed_scope_rebuilds_the_cache_before_navigating(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """
        A cache built for another channel is replaced before it is read.

        Navigating the old cache would land on ids the selected channel may not have.
        """
        view = build_navigable_tab(view_cls, mocker)
        view.current_channel = 1
        answer_query_with(view, pd.DataFrame({"event_id": [10, 20, 30]}))

        assert navigate(view, 10, "right") == 20
        assert view.current_channel == 0

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_an_empty_rebuild_stops_navigation(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """Nothing is plotted when the rebuilt cache comes back empty."""
        view = build_navigable_tab(view_cls, mocker)
        view.filtered_event_ids = []
        answer_query_with(view, pd.DataFrame({"event_id": []}))

        view._shift_range_and_update_plot(
            {"db_loader": "l", "event_id": 0, "n_events": 1}, "right"
        )

        view._replot_after_shift.assert_not_called()


class TestSnapToFiltered:
    """
    Where a plot of an entered Event ID starts, for both subset tabs.

    Pinned: the first cached id at or after the entered one, and an entered id past
    every cached one snapping to the first with a status-panel message.
    """

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize(
        ("event_id", "expected_idx"),
        [(3, 1), (4, 2), (0, 0), (7, 3)],
        ids=["exact", "between", "first", "last"],
    )
    def test_an_id_in_range_snaps_silently_at_or_after(
        self,
        qapp: object,
        mocker: object,
        view_cls: type,
        event_id: int,
        expected_idx: int,
    ) -> None:
        """An entered id with a match at or after it is no surprise, so no message."""
        view = build_navigable_tab(view_cls, mocker)

        assert view._snap_to_filtered(event_id) == expected_idx
        view.add_text_to_display.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_an_id_past_every_cached_one_snaps_to_the_first_and_says_so(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """The plot starts somewhere other than the entered id, so the panel says where."""
        view = build_navigable_tab(view_cls, mocker)

        assert view._snap_to_filtered(99) == 0
        view.add_text_to_display.emit.assert_called_once_with(
            "Event ID 99 is past the last filtered event (7); "
            "wrapped around to the first filtered event (0)",
            view_cls.__name__,
        )


# ===========================================================================
# show_selection_tree - shared by both subset tabs on MetaSubsetTabView
# ===========================================================================


SCOPE_UNCHANGED = (
    "Scope unchanged: at least one experiment or channel must stay selected"
)
NO_EXPERIMENTS = "This database has no experiments to select"


def close_tree_with(view: object, mocker: object, ticked: dict) -> None:
    """
    Make the view's selection tree close with ``ticked`` checked.

    The stub returns what ``SelectionTree.show_dialog`` returns: the ticked
    experiments mapped to their ticked channels, and ``{}`` when nothing is ticked.

    :param view: a subset-tab view
    :type view: object
    :param mocker: the pytest-mock fixture
    :type mocker: object
    :param ticked: the selection the tree closes with
    :type ticked: dict
    """
    view.selection_tree = mocker.Mock()
    view.selection_tree.show_dialog.return_value = ticked


class TestShowSelectionTree:
    """
    Closing the experiment and channel tree, for both subset tabs.

    Pinned: a selection with something ticked becomes the scope; closing with nothing
    ticked keeps the previous scope, absent included, and says so, since an empty
    scope can never produce anything; a database with no experiments says that
    instead.
    """

    def test_the_base_owns_the_only_copy(self) -> None:
        """A copy left on a tab would shadow the shared one for that tab."""
        assert "show_selection_tree" in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert "show_selection_tree" not in view_cls.__dict__, view_cls.__name__

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_ticked_selection_becomes_the_scope(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """Whatever is ticked when the tree closes is what every plot then uses."""
        view = build_subset_tab(view_cls)
        view.selected_experiment_and_channels_by_loader = {"l": {"A": ["1", "2"]}}
        close_tree_with(view, mocker, {"B": ["1"]})

        view.show_selection_tree({"A": ["1", "2"], "B": ["1"]}, "l", {"A": ["1", "2"]})

        assert view.selected_experiment_and_channels_by_loader["l"] == {"B": ["1"]}
        view.add_text_to_display.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_nothing_ticked_keeps_the_previous_scope_and_says_so(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """
        An empty scope can never produce anything, so it is not stored.

        The message is what tells the user the unticking was not applied; without it
        the old ticks would simply reappear the next time the tree opens.
        """
        view = build_subset_tab(view_cls)
        view.selected_experiment_and_channels_by_loader = {"l": {"A": ["1"]}}
        close_tree_with(view, mocker, {})

        view.show_selection_tree({"A": ["1", "2"]}, "l", {"A": ["1"]})

        assert view.selected_experiment_and_channels_by_loader["l"] == {"A": ["1"]}
        view.add_text_to_display.emit.assert_called_once_with(
            SCOPE_UNCHANGED, view_cls.__name__
        )

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_nothing_ticked_leaves_an_absent_scope_absent(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """No scope is invented: a loader with none stored still has none."""
        view = build_subset_tab(view_cls)
        view.selected_experiment_and_channels_by_loader = {}
        close_tree_with(view, mocker, {})

        view.show_selection_tree({"A": ["1"]}, "l", {})

        assert "l" not in view.selected_experiment_and_channels_by_loader
        view.add_text_to_display.emit.assert_called_once_with(
            SCOPE_UNCHANGED, view_cls.__name__
        )

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_database_with_no_experiments_says_so(
        self, qapp: object, mocker: object, view_cls: type
    ) -> None:
        """There was never anything to tick, so "scope unchanged" would mislead."""
        view = build_subset_tab(view_cls)
        view.selected_experiment_and_channels_by_loader = {"l": {}}
        close_tree_with(view, mocker, {})

        view.show_selection_tree({}, "l", {})

        assert view.selected_experiment_and_channels_by_loader["l"] == {}
        view.add_text_to_display.emit.assert_called_once_with(
            NO_EXPERIMENTS, view_cls.__name__
        )
