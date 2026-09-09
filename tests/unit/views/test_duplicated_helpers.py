"""
Equivalence tests for the helpers Step 3 is about to merge into a shared base.

The duplication ratchet counts byte-identical bodies; it cannot say whether two
copies *behave* the same, and it says nothing at all about a third copy that was
inlined instead of written as a method. That is what this file is for. Each group
below is merged by Step 3 or Step 4, and the merge should be a decision someone
makes about known behaviour rather than a silent change.

Eight groups:

- ``_factors`` exists three times - ``MetaView.py:139`` plus byte-identical
  overrides in ``RawDataView.py:109`` and ``EventAnalysisView.py:121`` that shadow
  the base they could simply inherit. Step 3c deletes the two overrides. Nothing
  today asserts the three agree; each is tested separately in its own module.
- ``createButton`` used to exist five times, four of them byte-identical, and
  the divergence was pinned so Step 3a had to decide it. **3a promoted the
  majority version to** ``MetaControls``, so what is checked now is that exactly
  one copy survives and that it behaves as the majority version did.
- ``format_axis_label`` exists three times, and **the third one differs**.
  ``ProteinView.py:4037`` is a module-level function, ``MetadataView.py:3645`` is
  a byte-identical method, and ``ClusteringView.py:731-742`` is an inlined loop
  that neither strips a pre-existing trailing parenthetical nor rejects a
  whitespace-only unit. The two callable copies are asserted equal here, and the
  two specific behaviours the inline copy lacks are pinned as named tests so that
  merging all three is an explicit decision.
- ``get_selected_filters`` existed twice, in ``MetadataView`` and ``ProteinView``,
  differing only in the name each tab held its controls panel under. **Step 4a
  promoted it to** ``MetaSubsetTabView``, which reaches the panel through
  ``_subset_controls`` - a one-line property each tab implements over the name it
  already holds its panel under, so there is still only one copy of the panel. Every unit test that touches this method
  mocks it, so its real body had no unit coverage at all before the promotion -
  which is exactly the shape rule 43 warns about, and why it is pinned here.
- ``_rebuild_event_id_cache`` existed twice and **the copies diverged three ways**.
  ``ProteinView``'s also rejected a result with no ``event_id`` column, named the
  scope in its empty-subset message, and labelled an unnamed active filter with the
  filter expression instead of the word "Filter". **Step 4a promoted Protein's, by
  decision, on all three** - and reordered its first two checks, so that a result
  with no rows is an empty subset whether or not the loader returned columns with
  it. ``MetadataView`` had six tests for its copy and ``ProteinView`` had none, so
  the three branches only Protein's version had are pinned here.
- ``_show_add_filter_dialog`` and ``show_edit_filter_dialog`` existed twice, only 14
  diff lines apart, and carried **both** of the pair's real divergences: the columns
  the throwaway validation query is built from, and whether an invalid raw filter is
  reported in a modal or on the status panel. **Step 4a promoted both to**
  ``MetaSubsetTabView``, taking Metadata's modal by the user's choice and Protein's
  columns handling, each behind a named helper. The per-tab tests cover the modal, and
  the column selection is no longer here at all: Step 4a's conversion moved it to
  ``MetaSubsetTabController.validate_filter``, which asks the loader for its *events*
  columns instead of guessing three, so ``_validation_columns`` and the tests that
  pinned its fallback are gone.
- ``_load_filter`` existed twice and diverged once: only ``ProteinView`` let a filter
  whose name ends in ``_raw`` skip validation. **Step 4a promoted Protein's**, which
  fixes the metadata tab rather than merging it - see the group below for the measured
  consequence of not bypassing.
- **Five more methods collapsed once ``_subset_controls`` existed**:
  ``replace_filter_item``, ``update_filter_name``, ``_delete_filter``,
  ``on_raw_filter_validated`` and ``relay_query_result``. Four of them differed *only*
  in the name each tab held its controls panel under, and ``relay_query_result``
  differed only in its docstring; ``on_raw_filter_validated`` carried the modal-vs-
  status-panel divergence a second time and was settled the same way. ``_delete_filter``
  was **abstract** on the base for the stated reason that each tab rebuilds its own
  filter widgets - which was only ever true because of the panel name.
"""

import json
import logging
from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout

from poriscope.plugins.analysistabs.EventAnalysisView import EventAnalysisView
from poriscope.plugins.analysistabs.MetadataView import MetadataView
from poriscope.plugins.analysistabs.ProteinView import ProteinView, format_axis_label
from poriscope.plugins.analysistabs.RawDataView import RawDataView
from poriscope.plugins.analysistabs.utils.clusteringcontrols import ClusteringControls
from poriscope.plugins.analysistabs.utils.eventAnalysisControls import (
    EventAnalysisControls,
)
from poriscope.plugins.analysistabs.utils.metadatacontrols import MetadataControls
from poriscope.plugins.analysistabs.utils.proteincontrols import ProteinControls
from poriscope.plugins.analysistabs.utils.rawdatacontrols import RawDataControls
from poriscope.utils.MetaControls import MetaControls
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
    One instance per class carrying a ``_factors`` implementation.

    :return: the three carriers, keyed by class name
    :rtype: dict
    """
    return {
        "MetaView": build(_BaseOnlyView),
        "RawDataView": build(RawDataView),
        "EventAnalysisView": build(EventAnalysisView),
    }


# ===========================================================================
# _factors - three copies, two of them shadowing the base
# ===========================================================================


class TestFactorsAgree:
    """The three copies must return the same grid for the same input."""

    @pytest.mark.parametrize("n", list(range(1, 41)))
    def test_all_three_copies_agree(self, factors_copies: dict, n: int) -> None:
        """
        Swept rather than spot-checked, because the loop grows ``n`` until it can
        factor it nearly squarely, and a divergence could hide at any one value.
        """
        results = {name: view._factors(n) for name, view in factors_copies.items()}
        assert len(set(results.values())) == 1, results

    def test_the_overrides_are_not_merely_inherited(self) -> None:
        """
        The two subclasses genuinely redefine it rather than inheriting it.

        If this ever fails, Step 3c's deletion has already happened and the
        agreement tests above become trivially true - which is the point at which
        this test should be removed rather than repaired.
        """
        assert "_factors" in RawDataView.__dict__
        assert "_factors" in EventAnalysisView.__dict__


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
    precisely the decisions Step 3 has to make when the three are merged. The
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
    fixed here - this file's job is to record what the code does today so Step 3's
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
# createButton - promoted to MetaControls by Step 3a
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
    ended with. That divergence was pinned here so Step 3a had to decide it rather
    than merge it silently.

    **3a decided it: the majority version was promoted, reset included.** So the
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
# get_selected_filters - two copies, promoted by Step 4a
# ===========================================================================


SUBSET_TABS = (MetadataView, ProteinView)

#: What ``MetaSubsetTabView`` still asks a subclass for. Asserted whole rather than
#: membership-by-membership, because the base's abstract set is published contract:
#: a promotion that quietly drops one, or a new one added without a changelog note,
#: should fail here. Step 4a took it from seven to five.
ABSTRACT_MEMBERS = frozenset(
    {
        "_init",
        "_reset_actions",
        "_subset_controls",
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
# _rebuild_event_id_cache - two copies, three divergences, promoted by Step 4a
# ===========================================================================


def answer_query_with(view: object, frame: object) -> None:
    """
    Make the view's next ``load_metadata`` round-trip park ``frame``.

    ``_rebuild_event_id_cache`` clears ``relayed_query_result`` before it emits,
    precisely so a failed dispatch cannot be read as this call's answer, so a
    test cannot simply assign the attribute up front. Step 4a's next commit
    replaces the emit with a direct call and this helper goes with it.

    :param view: the view whose bus round-trip should be answered
    :type view: object
    :param frame: whatever the loader should appear to have returned
    :type frame: object
    """

    def deliver(*_args: object) -> None:
        view.relayed_query_result = frame

    view.global_signal.emit.side_effect = deliver


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
        The four navigation values, whose annotations moved to the base in 2a.

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
# the two filter dialogs - two copies each, promoted by Step 4a
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
        assert "_load_filter" in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert "_load_filter" not in view_cls.__dict__, view_cls.__name__

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_raw_filter_is_stored_without_validation(
        self,
        qapp: object,
        view_cls: type,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        ProteinView's bypass, which MetadataView lacked.

        Saving a raw filter and loading it back has to return the same name, or the
        filter stops being a raw filter - nothing downstream recognises
        ``*_raw_assisted``.
        """
        view = build_subset_tab(view_cls)
        path = write_filter_file(
            tmp_path, {"big_events_raw": "SELECT event_id FROM events WHERE dwell > 5"}
        )
        monkeypatch.setattr(
            "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "JSON Files (*.json)")),
        )

        view._load_filter({"db_loader": "a_loader"})

        assert view.subset_filters == {
            "big_events_raw": "SELECT event_id FROM events WHERE dwell > 5"
        }
        view.global_signal.emit.assert_not_called()

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_an_assisted_filter_is_still_sent_for_validation(
        self,
        qapp: object,
        view_cls: type,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        The bypass must not swallow the ordinary path.

        A filter without the suffix still goes through
        ``construct_metadata_query``, and is only committed once the round-trip
        returns - which is why nothing is in ``subset_filters`` yet.
        """
        view = build_subset_tab(view_cls)
        path = write_filter_file(tmp_path, {"long_events": "dwell > 5"})
        monkeypatch.setattr(
            "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "JSON Files (*.json)")),
        )

        emitted: list = []
        view.filter_validation_requested.connect(lambda *args: emitted.append(args))

        view._load_filter({"db_loader": "a_loader"})

        assert view.subset_filters == {}
        assert emitted == [("a_loader", "dwell > 5", "validate_new_filter")]
        view.global_signal.emit.assert_not_called()
        assert view._pending_filter_name == "long_events"

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_with_no_loader_everything_is_stored_unvalidated(
        self,
        qapp: object,
        view_cls: type,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Both copies already agreed on this; it is asserted so the merge kept it."""
        view = build_subset_tab(view_cls)
        path = write_filter_file(
            tmp_path, {"long_events": "dwell > 5", "raw_one_raw": "SELECT 1"}
        )
        monkeypatch.setattr(
            "poriscope.utils.MetaSubsetTabView.QFileDialog.getOpenFileName",
            staticmethod(lambda *a, **k: (path, "JSON Files (*.json)")),
        )

        view._load_filter({"db_loader": None})

        assert view.subset_filters == {
            "long_events": "dwell > 5",
            "raw_one_raw": "SELECT 1",
        }
        view.global_signal.emit.assert_not_called()


# ===========================================================================
# the five methods _subset_controls unlocked - promoted by Step 4a
# ===========================================================================


PANEL_NAME_ONLY = (
    "replace_filter_item",
    "update_filter_name",
    "_delete_filter",
    "relay_query_result",
    "on_raw_filter_validated",
)


class TestThePanelNameMethodsWerePromoted:
    """
    The five that collapsed once the base had a name for the controls panel.

    Four differed only in ``metadatacontrols`` against ``proteincontrols``, and
    ``relay_query_result`` only in its docstring - so with ``_subset_controls`` in
    place there was nothing left to decide except ``on_raw_filter_validated``'s
    modal, which the filter dialogs had already settled.
    """

    @pytest.mark.parametrize("name", PANEL_NAME_ONLY)
    def test_the_base_owns_the_only_copy(self, name: str) -> None:
        """Neither tab may keep its own, or the promotion was partial."""
        assert name in MetaSubsetTabView.__dict__
        for view_cls in SUBSET_TABS:
            assert name not in view_cls.__dict__, f"{view_cls.__name__}.{name}"

    def test_delete_filter_is_no_longer_abstract(self) -> None:
        """
        The base asks a subclass for five things now, not six.

        ``_delete_filter``'s abstractness was documented as each tab rebuilding its
        own filter widgets. That reduced entirely to the panel name, so the reason
        went away with it.
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
    def test_an_invalid_raw_filter_is_reported_in_a_modal_on_both_tabs(
        self, qapp: object, view_cls: type, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        The protein tab's behaviour change, and the reason this group exists.

        It used to put the rejection on the status panel. The promoted copy uses
        Metadata's modal, consistently with the filter dialogs, so the same
        rejection reads the same way wherever it comes from.
        """
        view = build_subset_tab(view_cls)
        view._pending_filter_name = "f1_raw"
        view._pending_filter_text = "SELECT 1"
        view._pending_old_filter_name = None
        warned = MagicMock()
        monkeypatch.setattr(
            "poriscope.utils.MetaSubsetTabView.QMessageBox.warning",
            staticmethod(warned),
        )

        view.on_raw_filter_validated(False, "no such column: dwel")

        warned.assert_called_once()
        assert "no such column: dwel" in warned.call_args[0][2]
        assert view.subset_filters == {}
        assert view._pending_filter_name is None

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_a_valid_raw_filter_is_committed_and_selected(
        self, qapp: object, view_cls: type
    ) -> None:
        """The add path: stored under its pending name, and checked in the combobox."""
        view = build_subset_tab(view_cls)
        view._pending_filter_name = "f1_raw"
        view._pending_filter_text = "SELECT event_id FROM events"
        view._pending_old_filter_name = None

        view.on_raw_filter_validated(True, "")

        assert view.subset_filters == {"f1_raw": "SELECT event_id FROM events"}
        assert view.get_selected_filters() == {"f1_raw": "SELECT event_id FROM events"}
        assert view._pending_filter_name is None

    @pytest.mark.parametrize("view_cls", SUBSET_TABS, ids=lambda c: c.__name__)
    def test_relay_query_result_parks_the_answer_and_can_clear_it(
        self, qapp: object, view_cls: type
    ) -> None:
        """
        Both directions matter, because the clear is what makes the read safe.

        Every caller sets it to None before dispatching, precisely so that a failed
        call cannot be read back as this call's answer, so a version that ignored a
        None would reintroduce the stale read this whole step exists to remove.
        """
        view = build_subset_tab(view_cls)
        frame = pd.DataFrame({"event_id": [1, 2]})

        view.relay_query_result(frame)
        assert view.relayed_query_result is frame

        view.relay_query_result(None)
        assert view.relayed_query_result is None

    def test_the_parked_answer_is_declared_on_the_base(self) -> None:
        """
        The annotation moved with the method that writes it.

        Only ``MetadataView`` declared it before; ``ProteinView`` assigned it at first
        use, and every read guards with ``getattr(..., None)``. Both ``_init``s now set
        it, so those guards are belt-and-braces - worth stating before someone removes
        one and finds out which reads still depend on them.
        """
        assert "relayed_query_result" in MetaSubsetTabView.__annotations__
        for view_cls in SUBSET_TABS:
            assert "relayed_query_result" not in view_cls.__annotations__
