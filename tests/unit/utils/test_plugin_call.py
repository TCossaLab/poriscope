"""
The direct plugin-call path introduced by Step 4a of the 2.0.0 refactor.

Decision A replaces the return-value signal bus with ``call`` on ``MetaController`` and
``MetaModel``, with live plugin instances **pushed** down the notification path that
already refreshes the plugin *names* a View shows in its comboboxes. The plan named
``get_plugin`` as public alongside it; it is ``_get_plugin`` instead, so that ``call()``
is the only public door - see point 3 below.

What the bus did, and why this exists, in the words of the thing it replaces: a caller
emitted ``global_signal`` with the name of a return function, and read the answer back
off an attribute **on the very next statement**. Seven hops, and
``MainController._dispatch_to`` logged and returned on four separate conditions - so a
failed dispatch left the caller reading the *previous* call's value with no error and no
log line the caller could see. That was a live bug twice: a metadata plot showing the
previous subset's rows, and a query running against the previous experiment's id.

So the two things these tests hold are the two things that were wrong with the bus:

1. **A failure raises**, at the call site, instead of being swallowed.
2. **Instances cannot go stale**, because they are pushed on the same event as the
   names rather than cached on first use. A lazy cache would need invalidating on
   rename and on re-instantiation, and those are exactly the two that get missed.
3. **``call()`` is the only public door.** ``_get_plugin`` is private, and ``call``
   refuses a method name starting with an underscore, so a tab cannot reach either a
   plugin instance or a plugin's private interface through the sanctioned API. Neither
   guard is airtight - Python has no access control - but both fail loudly, and
   ``check_mvc_boundary``'s rule 5 ratchets the ways around them at zero.

No Qt widgets: ``MetaController`` and ``MetaModel`` are built by ``__new__`` so that the
methods under test can be reached without a view, a model, or a running application.
"""

from typing import Any, Dict, Optional

import pytest

from poriscope.utils.MetaController import MetaController
from poriscope.utils.MetaModel import MetaModel

pytestmark = pytest.mark.characterization


class _Loader:
    """Stand-in for a data plugin, recording what it was asked for."""

    def __init__(self, name: str = "loader") -> None:
        """
        Build the stand-in.

        :param name: an identifier echoed back by ``describe``
        :type name: str
        """
        self.name = name
        self.calls: list = []

    def get_experiment_id_by_name(self, experiment: str) -> int:
        """
        Return a fixed id, recording the argument.

        :param experiment: the experiment name
        :type experiment: str
        :return: a fixed id
        :rtype: int
        """
        self.calls.append(experiment)
        return 7

    def load_metadata(
        self, columns: list, conditions: Optional[str] = None, rectify: bool = False
    ) -> dict:
        """
        Stand in for a plugin method with defaults deep in the signature.

        Shaped after the real ones: 48 methods on the data-plugin bases have default
        parameters, and several put them last.

        :param columns: the columns to load
        :type columns: list
        :param conditions: an optional WHERE clause
        :type conditions: Optional[str]
        :param rectify: whether to rectify the sign of the data
        :type rectify: bool
        :return: what it was asked for, so a test can assert on the binding
        :rtype: dict
        """
        return {"columns": columns, "conditions": conditions, "rectify": rectify}

    def describe(self) -> str:
        """
        Return this instance's name, so tests can tell two instances apart.

        :return: the name
        :rtype: str
        """
        return self.name

    def explode(self) -> None:
        """
        Raise, so the propagation of a plugin's own failure can be asserted.

        :raises RuntimeError: always
        """
        raise RuntimeError("the plugin itself failed")

    not_callable = "a string, not a method"


def _model(instances: Optional[Dict[str, Dict[str, object]]] = None) -> MetaModel:
    """
    Build a MetaModel without Qt, optionally with instances already pushed.

    :param instances: metaclass -> key -> instance, or None for an empty map
    :type instances: Optional[Dict[str, Dict[str, object]]]
    :return: the model
    :rtype: MetaModel
    """
    model = MetaModel.__new__(MetaModel)  # type: ignore[type-abstract]
    model._plugin_instances = {}
    if instances is not None:
        model.set_plugin_instances(instances)
    return model


def _controller(
    instances: Optional[Dict[str, Dict[str, object]]] = None,
    model: Optional[Any] = None,
) -> MetaController:
    """
    Build a MetaController without Qt, optionally with instances already pushed.

    :param instances: metaclass -> key -> instance, or None for an empty map
    :type instances: Optional[Dict[str, Dict[str, object]]]
    :param model: the model to forward to, or None
    :type model: Optional[Any]
    :return: the controller
    :rtype: MetaController
    """
    controller = MetaController.__new__(MetaController)  # type: ignore[type-abstract]
    controller._plugin_instances = {}
    controller.model = model
    if instances is not None:
        controller.set_plugin_instances(instances)
    return controller


# ===========================================================================
# _get_plugin
# ===========================================================================


class TestPrivateResolver:
    """Resolution, and what happens when it fails."""

    def test_it_returns_the_pushed_instance(self) -> None:
        """The whole point: the same object, not a copy or a proxy."""
        loader = _Loader()
        model = _model({"MetaDatabaseLoader": {"SQLiteDBLoader_0": loader}})

        assert model._get_plugin("MetaDatabaseLoader", "SQLiteDBLoader_0") is loader

    def test_an_unknown_key_raises(self) -> None:
        """
        Raises rather than returning None.

        Returning None is what the bus effectively did, and a caller could not tell it
        apart from a plugin that legitimately returned None.
        """
        model = _model({"MetaDatabaseLoader": {}})

        with pytest.raises(KeyError, match="MetaDatabaseLoader"):
            model._get_plugin("MetaDatabaseLoader", "nope")

    def test_an_unknown_metaclass_raises(self) -> None:
        """An unregistered family fails the same way as an unregistered key."""
        model = _model({})

        with pytest.raises(KeyError, match="MetaEventLoader"):
            model._get_plugin("MetaEventLoader", "anything")

    def test_the_message_names_both_the_family_and_the_key(self) -> None:
        """
        The diagnostic a stale-read bug never gave anyone.

        Both halves are needed to find the mistake: the family says which combobox,
        the key says which instance.
        """
        model = _model({})

        with pytest.raises(KeyError) as caught:
            model._get_plugin("MetaDatabaseLoader", "SQLiteDBLoader_3")

        assert "MetaDatabaseLoader" in str(caught.value)
        assert "SQLiteDBLoader_3" in str(caught.value)


# ===========================================================================
# call
# ===========================================================================


class TestCall:
    """The replacement for emit-then-read-an-attribute."""

    def test_it_returns_the_plugin_s_result(self) -> None:
        """One statement, a real return value, no attribute in between."""
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        result = model.call(
            "MetaDatabaseLoader", "L", "get_experiment_id_by_name", "exp1"
        )

        assert result == 7

    def test_it_passes_the_arguments_through(self) -> None:
        """Positional arguments reach the plugin unchanged."""
        loader = _Loader()
        model = _model({"MetaDatabaseLoader": {"L": loader}})

        model.call("MetaDatabaseLoader", "L", "get_experiment_id_by_name", "exp2")

        assert loader.calls == ["exp2"]

    def test_keyword_arguments_are_passed_through(self) -> None:
        """
        The signal bus could not do this: its ``call_args`` was a positional tuple.

        It matters because 48 methods on the data-plugin bases have default
        parameters, several of them last in the signature - positionally, setting the
        last one means passing every earlier one too.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        result = model.call(
            "MetaDatabaseLoader", "L", "load_metadata", ["a"], rectify=True
        )

        assert result == {"columns": ["a"], "conditions": None, "rectify": True}

    def test_a_default_left_alone_stays_default(self) -> None:
        """Skipping a middle argument by name does not disturb the ones around it."""
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        result = model.call("MetaDatabaseLoader", "L", "load_metadata", ["a", "b"])

        assert result == {"columns": ["a", "b"], "conditions": None, "rectify": False}

    def test_a_misspelled_keyword_raises_type_error(self) -> None:
        """
        Python's own binding error, unwrapped.

        Not something mypy can catch through a string-keyed call, so it has to be loud
        at runtime - which it is, because nothing here swallows it.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(TypeError):
            model.call("MetaDatabaseLoader", "L", "load_metadata", ["a"], rectifyy=True)

    def test_an_unknown_method_raises_attribute_error(self) -> None:
        """
        The case the bus logged and returned on.

        ``_dispatch_to`` printed "No member X.y found" and returned, so the caller read
        a stale attribute and carried on with the wrong data.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(AttributeError, match="no callable method"):
            model.call("MetaDatabaseLoader", "L", "no_such_method")

    def test_a_non_callable_attribute_raises_attribute_error(self) -> None:
        """
        Named attribute exists but is not a method.

        ``_dispatch_to`` checked this separately; the check survives the move because a
        plugin author can shadow a method with a value by mistake.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(AttributeError, match="no callable method"):
            model.call("MetaDatabaseLoader", "L", "not_callable")

    def test_a_private_method_name_is_refused(self) -> None:
        """
        ``call()`` reaches a plugin's *public* API only.

        Measured before adding the guard: all 75 bus calls in the codebase target public
        methods, so this breaks nothing and closes the same violation class boundary
        rule 3 catches for Views - reaching past an object's declared interface.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(AttributeError, match="public interface"):
            model.call("MetaDatabaseLoader", "L", "_secret")

    def test_the_private_resolver_cannot_be_reached_through_call(self) -> None:
        """
        The two guards close on each other.

        ``_get_plugin`` is private so ``call()`` is the only public door; the underscore
        guard then stops anyone opening that door and asking for the resolver itself.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(AttributeError, match="public interface"):
            model.call("MetaDatabaseLoader", "L", "_get_plugin")

    def test_an_unknown_plugin_raises_key_error(self) -> None:
        """It propagates from _get_plugin rather than being translated."""
        model = _model({"MetaDatabaseLoader": {}})

        with pytest.raises(KeyError):
            model.call("MetaDatabaseLoader", "gone", "describe")

    def test_the_plugin_s_own_exception_propagates_unchanged(self) -> None:
        """
        Not wrapped, not logged-and-swallowed.

        The bus caught everything here, so a plugin raising mid-call looked identical
        to one that succeeded and returned None.
        """
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        with pytest.raises(RuntimeError, match="the plugin itself failed"):
            model.call("MetaDatabaseLoader", "L", "explode")


# ===========================================================================
# set_plugin_instances - the anti-staleness contract
# ===========================================================================


class TestPushedInstancesCannotGoStale:
    """
    Why the instances are pushed rather than cached on first use.

    A lazy cache needs invalidating on three events and two are easy to miss: a
    **rename** leaves it pointing at a live object under a key that no longer exists,
    and a **re-instantiation** leaves it holding a dead object whose
    ``close_resources`` may already have run. With a push, the call that would have
    gone stale is the call that refreshes it.
    """

    def test_a_re_instantiation_replaces_the_object(self) -> None:
        """The second push wins; the first instance is not retained anywhere."""
        first, second = _Loader("first"), _Loader("second")
        model = _model({"MetaDatabaseLoader": {"L": first}})

        model.set_plugin_instances({"MetaDatabaseLoader": {"L": second}})

        assert model.call("MetaDatabaseLoader", "L", "describe") == "second"

    def test_a_rename_leaves_the_old_key_unresolvable(self) -> None:
        """
        The rename case, which is the one a lazy cache gets wrong silently.

        After a rename the old key must raise, not return the still-live object.
        """
        loader = _Loader()
        model = _model({"MetaDatabaseLoader": {"old_name": loader}})

        model.set_plugin_instances({"MetaDatabaseLoader": {"new_name": loader}})

        assert model._get_plugin("MetaDatabaseLoader", "new_name") is loader
        with pytest.raises(KeyError):
            model._get_plugin("MetaDatabaseLoader", "old_name")

    def test_a_deletion_leaves_nothing_behind(self) -> None:
        """A deleted plugin stops resolving rather than lingering."""
        model = _model({"MetaDatabaseLoader": {"L": _Loader()}})

        model.set_plugin_instances({"MetaDatabaseLoader": {}})

        with pytest.raises(KeyError):
            model._get_plugin("MetaDatabaseLoader", "L")

    def test_the_stored_map_is_a_copy(self) -> None:
        """
        Mutating the caller's dict afterwards must not change what is resolvable.

        ``MainController`` rebuilds this map on every lifecycle event and hands the
        same object to every tab, so a tab holding it by reference could see another
        tab's view of the world.
        """
        pushed: Dict[str, Dict[str, object]] = {"MetaDatabaseLoader": {"L": _Loader()}}
        model = _model(pushed)

        pushed["MetaDatabaseLoader"]["sneaked_in"] = _Loader("sneaky")

        with pytest.raises(KeyError):
            model._get_plugin("MetaDatabaseLoader", "sneaked_in")


# ===========================================================================
# MetaController - the same surface, plus the hand-off to the Model
# ===========================================================================


class TestControllerSurface:
    """The Controller has the same two methods and forwards the push down."""

    def test_it_resolves_and_calls(self) -> None:
        """Same behaviour as the Model's, for the cases that are Controller work."""
        controller = _controller({"MetaDatabaseLoader": {"L": _Loader()}})

        assert (
            controller.call("MetaDatabaseLoader", "L", "get_experiment_id_by_name", "e")
            == 7
        )

    def test_it_forwards_the_push_to_the_model(self) -> None:
        """
        The Model is where the calls belong, so it must receive the instances.

        This is the connection that makes ``self.call(...)`` work in a Model at all.
        """
        model = _model()
        controller = _controller(model=model)
        loader = _Loader()

        controller.set_plugin_instances({"MetaDatabaseLoader": {"L": loader}})

        assert model._get_plugin("MetaDatabaseLoader", "L") is loader

    def test_a_controller_with_no_model_yet_does_not_raise(self) -> None:
        """
        Pushed before ``_init`` has built the model.

        ``MainController`` pushes to every registered tab, and a tab's model is built
        by its own ``_init``; the ordering is not something this class controls.
        """
        controller = _controller(model=None)

        controller.set_plugin_instances({"MetaDatabaseLoader": {"L": _Loader()}})

        assert controller._get_plugin("MetaDatabaseLoader", "L") is not None

    def test_an_unknown_key_raises_on_the_controller_too(self) -> None:
        """The failure mode does not differ between the two classes."""
        controller = _controller({"MetaDatabaseLoader": {}})

        with pytest.raises(KeyError):
            controller._get_plugin("MetaDatabaseLoader", "nope")
