"""
``MetaSubsetTabController``'s shared surface, as Step 4a leaves it.

Two things live here: ownership assertions for the methods promoted onto the base, and
the behaviour of the two validation methods that step added when it converted the
View's ``global_signal`` round trips into direct ``call()`` invocations.

The behavioural coverage already exists and did not move: ``test_metadata_controller``
has fifteen tests for ``relay_query`` and ``test_protein_controller`` several more, and
after the promotion they all resolve through the MRO to the one copy on
``MetaSubsetTabController``. What none of them can see is whether a *second* copy
survived - a leftover would shadow the base for that one tab and every one of those
tests would still pass, which is the failure this file exists to catch.

Kept separate from ``tests/unit/views/test_duplicated_helpers.py``, which does the same
job for the View-side promotions, because that file lives under ``tests/unit/views`` and
these are Controllers.
"""

import pytest
from pytest_mock import MockerFixture

from poriscope.plugins.analysistabs.MetadataController import MetadataController
from poriscope.plugins.analysistabs.ProteinController import ProteinController
from poriscope.utils.MetaSubsetTabController import MetaSubsetTabController

pytestmark = pytest.mark.characterization

SUBSET_CONTROLLERS = (MetadataController, ProteinController)

#: Promoted in Step 4a. ``relay_query`` was recorded on the base itself as deliberately
#: unshareable, because "the two tabs' copies differ" and each reached into its own
#: View's pending-filter state. The copies differed by a single blank line, and the
#: pending state had already been declared on ``MetaSubsetTabView``, so neither half of
#: the recorded reason held.
PROMOTED = ("relay_query",)


@pytest.mark.parametrize("name", PROMOTED)
def test_the_base_owns_the_only_copy(name: str) -> None:
    """
    Neither Controller may keep its own, or the promotion was partial.

    :param name: the promoted method's name
    :type name: str
    :return: None
    :rtype: None
    """
    assert name in MetaSubsetTabController.__dict__
    for controller_cls in SUBSET_CONTROLLERS:
        assert name not in controller_cls.__dict__, f"{controller_cls.__name__}.{name}"


@pytest.mark.parametrize("name", PROMOTED)
def test_both_tabs_resolve_to_the_same_function(name: str) -> None:
    """
    Stated as identity rather than as absence, so the two halves agree.

    ``__dict__`` absence and MRO identity can in principle disagree - a metaclass or a
    decorator applied at class creation would satisfy one and not the other - and it is
    the identity that the behavioural tests are actually relying on.

    :param name: the promoted method's name
    :type name: str
    :return: None
    :rtype: None
    """
    base = getattr(MetaSubsetTabController, name)
    for controller_cls in SUBSET_CONTROLLERS:
        assert getattr(controller_cls, name) is base, controller_cls.__name__


def test_the_base_no_longer_calls_relay_query_unshareable() -> None:
    """
    The docstring claim went with the method.

    ``MetaSubsetTabController``'s class docstring listed ``relay_query`` under what a
    subclass owes it, with a reason that had stopped being true. A stale contract in a
    published base's docstring is worth a test, because nothing else reads it.

    :return: None
    :rtype: None
    """
    doc = MetaSubsetTabController.__doc__ or ""
    assert "deliberately *not* shared" not in doc
    assert "relay_query" in doc


# ===========================================================================
# validate_filter / validate_raw_filter - Step 4a's converted round trips
# ===========================================================================


class RecordingModel:
    """
    A Model whose ``call`` records its arguments and replays canned answers.

    The answers are keyed by plugin method name and written from each method's real
    signature on ``MetaDatabaseLoader`` - ``get_column_names_by_table`` returns
    ``Optional[List[str]]``, ``construct_metadata_query`` a ``Tuple[str, str, str]``
    and ``validate_filter_query`` a ``Tuple[bool, str]``. Writing them from the
    signature rather than from the calling code is what keeps the test from pinning
    the shape the caller happens to assume.
    """

    def __init__(self, answers: dict) -> None:
        """
        :param answers: plugin method name to answer, or to an exception to raise
        :type answers: dict
        """
        self.answers = answers
        self.calls: list = []

    def call(self, metaclass: str, key: str, method: str, *args: object) -> object:
        """
        Record one plugin call and return its canned answer.

        :param metaclass: the plugin family
        :type metaclass: str
        :param key: the plugin instance's key
        :type key: str
        :param method: the method being called on it
        :type method: str
        :param args: the positional arguments, spread rather than tupled
        :type args: object
        :return: whatever this method's canned answer is
        :rtype: object
        """
        self.calls.append((metaclass, key, method, args))
        answer = self.answers[method]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def controller(mocker: MockerFixture) -> MetaSubsetTabController:
    """
    A bare subset-tab Controller with a mocked View and a recording Model.

    :param mocker: pytest-mock's fixture
    :type mocker: MockerFixture
    :return: the controller under test
    :rtype: MetaSubsetTabController
    """
    ctrl = MetadataController.__new__(MetadataController)  # type: ignore[type-abstract]
    ctrl.view = mocker.Mock()
    ctrl.logger = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.add_text_to_display = mocker.Mock()  # type: ignore[assignment,method-assign]
    ctrl.relay_query = mocker.Mock()  # type: ignore[method-assign]
    return ctrl


EVENTS_COLUMNS = ["dwell_time", "amplitude", "area"]


class TestValidateFilter:
    """
    The assisted path: resolve columns, build a throwaway query, relay the answer.
    """

    def test_it_validates_against_one_events_column(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        The join fix, asserted at its cause rather than at its symptom.

        The View used to hand over a hardcoded
        ``["sublevel_current", "voltage", "duration"]`` - one column from each of the
        three tables - so the built query joined all three every time, even with no
        conditions. Asking for the *events* columns and passing one gives exactly the
        joins the filter itself needs. Asserted as "one column, from the events
        table" because that is the property that holds; which column it is is the
        database's business.
        """
        controller.model = RecordingModel(
            {
                "get_column_names_by_table": EVENTS_COLUMNS,
                "construct_metadata_query": ("SELECT 1", "", "events"),
            }
        )

        controller.validate_filter("ldr", "duration < 300", "validate_new_filter")

        lookup, build = controller.model.calls
        assert lookup[2] == "get_column_names_by_table"
        assert lookup[3] == ("events",)
        assert build[2] == "construct_metadata_query"
        columns, conditions, scope = build[3]
        assert len(columns) == 1
        assert columns[0] in EVENTS_COLUMNS
        assert conditions == "duration < 300"
        assert scope is None

    def test_the_answer_and_the_intent_reach_relay_query(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        The three-tuple is unpacked here now, not splatted by the bus.

        ``MainController._unpack_result`` used to spread
        ``construct_metadata_query``'s ``Tuple[str, str, str]`` across
        ``relay_query``'s parameters, decided by the callee's declared return type. A
        direct call returns the tuple whole, so this method unpacks it itself - and
        getting that wrong is exactly the defect that shipped once already.
        """
        controller.model = RecordingModel(
            {
                "get_column_names_by_table": EVENTS_COLUMNS,
                "construct_metadata_query": ("SELECT 1", "", "events"),
            }
        )

        controller.validate_filter("ldr", "duration < 300", "validate_edited_filter")

        controller.relay_query.assert_called_once_with(
            "SELECT 1", "", "events", "validate_edited_filter"
        )

    def test_a_debug_message_is_relayed_rather_than_swallowed(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        A filter that cannot be built is still ``relay_query``'s business.

        It shows the modal and clears the pending state, so this method must not
        intercept the empty-query-with-debug answer on its way there.
        """
        controller.model = RecordingModel(
            {
                "get_column_names_by_table": EVENTS_COLUMNS,
                "construct_metadata_query": ("", "no such column: dwel", "events"),
            }
        )

        controller.validate_filter("ldr", "dwel < 300", "validate_new_filter")

        controller.relay_query.assert_called_once_with(
            "", "no such column: dwel", "events", "validate_new_filter"
        )

    def test_a_raising_build_is_reported_and_clears_the_pending_state(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        The defect this conversion fixes, and it was silent before.

        ``construct_metadata_query`` **raises** ``ValueError`` for a column it cannot
        map to a table. Under the bus, ``_dispatch_to`` swallowed it, so the filter
        vanished with nothing but a log line. Both halves are asserted: the user is
        told, and the pending name and text are dropped - without the clear, the next
        validation to succeed would commit them under the wrong name.
        """
        controller.model = RecordingModel(
            {
                "get_column_names_by_table": EVENTS_COLUMNS,
                "construct_metadata_query": ValueError(
                    "The following columns could not be mapped to tables: dwel"
                ),
            }
        )

        controller.validate_filter("ldr", "dwel < 300", "validate_new_filter")

        controller.relay_query.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()
        assert (
            "could not be mapped" in controller.add_text_to_display.emit.call_args[0][0]
        )
        controller.view.clear_pending_filter_state.assert_called_once()

    def test_a_loader_with_no_events_columns_is_refused(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        Refusing beats guessing.

        There is nothing to build a query around, so nothing can be validated. The
        hardcoded triple this replaced would have "validated" against three columns
        that may not exist in the database either, which is the failure mode being
        removed rather than one to preserve.
        """
        controller.model = RecordingModel({"get_column_names_by_table": None})

        controller.validate_filter("ldr", "duration < 300", "validate_new_filter")

        assert len(controller.model.calls) == 1
        controller.relay_query.assert_not_called()
        controller.add_text_to_display.emit.assert_called_once()
        controller.view.clear_pending_filter_state.assert_called_once()

    def test_a_loader_that_cannot_be_read_is_refused(
        self, controller: MetaSubsetTabController
    ) -> None:
        """A failing column lookup is reported, not allowed to escape a Qt slot."""
        controller.model = RecordingModel(
            {"get_column_names_by_table": RuntimeError("database is locked")}
        )

        controller.validate_filter("ldr", "duration < 300", "validate_new_filter")

        controller.relay_query.assert_not_called()
        assert (
            "database is locked" in controller.add_text_to_display.emit.call_args[0][0]
        )
        controller.view.clear_pending_filter_state.assert_called_once()


class TestValidateRawFilter:
    """The raw path: the loader checks the SELECT without a query being built."""

    def test_a_valid_answer_reaches_the_view(
        self, controller: MetaSubsetTabController
    ) -> None:
        """The ``Tuple[bool, str]`` is unpacked here, as the bus used to splat it."""
        controller.model = RecordingModel({"validate_filter_query": (True, "")})

        controller.validate_raw_filter("ldr", "SELECT 1 LIMIT 0")

        assert controller.model.calls[0][2] == "validate_filter_query"
        assert controller.model.calls[0][3] == ("SELECT 1 LIMIT 0",)
        controller.view.on_raw_filter_validated.assert_called_once_with(True, "")

    def test_an_invalid_answer_carries_its_message(
        self, controller: MetaSubsetTabController
    ) -> None:
        """The loader's explanation is what the View puts in its modal."""
        controller.model = RecordingModel(
            {"validate_filter_query": (False, "near SELEC: syntax error")}
        )

        controller.validate_raw_filter("ldr", "SELEC 1 LIMIT 0")

        controller.view.on_raw_filter_validated.assert_called_once_with(
            False, "near SELEC: syntax error"
        )

    def test_a_raising_validation_is_reported_as_invalid(
        self, controller: MetaSubsetTabController
    ) -> None:
        """
        Also previously swallowed.

        Reported as invalid rather than merely logged, because the View's handler is
        what clears the pending state - returning silently would leave the refused
        filter parked and committable by the next success.
        """
        controller.model = RecordingModel(
            {"validate_filter_query": RuntimeError("no such table: events")}
        )

        controller.validate_raw_filter("ldr", "SELECT 1 LIMIT 0")

        controller.view.on_raw_filter_validated.assert_called_once()
        valid, message = controller.view.on_raw_filter_validated.call_args[0]
        assert valid is False
        assert "no such table" in message
