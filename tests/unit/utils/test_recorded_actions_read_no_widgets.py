"""
A recorded action reads no widget and takes no plotted data.

A replay has to reproduce what the user did, not press the button again against whatever
the panel shows now (``DECISIONS.md`` 2026-09-17, rule 5), and a recorded action takes
intent, never the data already on the plot (rule 4). This test walks every declared action
of every analysis tab, and everything it calls on its own class (and, for a Controller
action, on its View through ``self.view``), and fails on:

1. a widget-value call with no arguments: ``.text()``, ``.currentText()``, ``.getSelectedItems()`` and the like;
2. a call to a helper that reads a controls panel;
3. a reach into a controls panel: an attribute named ``*controls``;
4. a read of state a widget handler sets, listed below with its reason;
5. a parameter annotated with a matplotlib or data-array type.

It reads source with ``ast`` and needs no Qt object. The runtime tripwire
(``poriscope.utils.ReplayGuard``) covers the seven helpers while a replay runs; this test
is what covers a direct ``.text()`` call, which nothing can intercept at runtime.

A property read is followed into its getter, so state read behind a property is found too.
A known exception goes in ``ALLOWED`` with its reason and the condition that removes it. An
entry that no longer trips is a failure, so the list cannot grow stale.
"""

import ast
import importlib
import inspect
import pkgutil
import sys
import textwrap
import typing
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pytest
from matplotlib.axes import Axes
from numpy.typing import NDArray

import poriscope.plugins.analysistabs as analysistabs_package
from poriscope.plugins.analysistabs.ClusteringView import ClusteringView
from poriscope.utils.LogDecorator import register_action
from poriscope.utils.MetaController import MetaController, declared_actions

#: Calls that read the value of a widget. A read takes no arguments, which is what tells
#: ``QLineEdit.text()`` from the drawing call ``Axes.text(x, y, s)``.
WIDGET_VALUE_CALLS = {
    "text",
    "currentText",
    "currentIndex",
    "currentData",
    "isChecked",
    "value",
    "toPlainText",
    "getSelectedItems",
}

#: Helpers that read a controls panel; calling one from an action is the leak itself.
HELPER_CALLS = {"collect_parameters", "get_selected_filters", "_get_event_index_text"}

#: State a widget handler sets, which an action must take from its arguments instead.
WIDGET_DERIVED_ATTRIBUTES = {
    "_analysis_mode": "set by the Individual/Ensemble mode buttons",
    "selected_experiment_and_channels_by_loader": "set by the scope tree dialog",
    "subset_filters": "edited through the filter dialogs and the filter combobox",
    "analysis_time_limits": "set by the Timer dialog",
    "clustering_config_map": "set by the clustering settings dialog",
    "_last_event_action": "set by whichever event button was last clicked",
}

#: Annotation names that mean a recorded action was handed plotted data.
DATA_TYPES = {"Axes", "Figure", "NDArray", "ndarray", "DataFrame", "Series"}

_EVENT_ID_QUESTION = (
    "the question whether to add event_id to a raw filter is never asked while a saved "
    "action is replayed (ReplayGuard.is_replaying), and the click asks it before the "
    "action is recorded, so the entry holds the text that ran; pinned by "
    "test_a_replay_never_asks_and_refuses_an_entry_without_event_id"
)

#: (action, rule, detail) -> the reason it is allowed.
ALLOWED: Dict[Tuple[str, str, str], str] = {
    (
        action,
        "widget-derived state",
        f"{method} reads subset_filters",
    ): _EVENT_ID_QUESTION
    for action in ("MetadataController.overlay_plot",)
    for method in ("offer_event_id", "revert_event_id_offer")
}


@dataclass(frozen=True)
class Finding:
    action: str
    rule: str
    detail: str

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.action, self.rule, self.detail)


def _source_tree(function: Callable[..., Any]) -> Optional[ast.FunctionDef]:
    try:
        source = textwrap.dedent(inspect.getsource(inspect.unwrap(function)))
    except (OSError, TypeError):
        return None
    tree = ast.parse(source)
    node = tree.body[0]
    return node if isinstance(node, ast.FunctionDef) else None


def _annotation_names(annotation: Optional[ast.expr]) -> Set[str]:
    names: Set[str] = set()
    if annotation is None:
        return names
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # a quoted annotation: read the string as an expression
            try:
                names |= _annotation_names(ast.parse(node.value, mode="eval").body)
            except SyntaxError:
                pass
    return names


def _self_call(node: ast.Call) -> Optional[Tuple[str, bool]]:
    """Return (method name, on the view) for ``self.m()`` and ``self.view.m()``, else None."""
    func = node.func
    if not isinstance(func, ast.Attribute):
        return None
    receiver = func.value
    if isinstance(receiver, ast.Name) and receiver.id == "self":
        return func.attr, False
    if (
        isinstance(receiver, ast.Attribute)
        and receiver.attr == "view"
        and isinstance(receiver.value, ast.Name)
        and receiver.value.id == "self"
    ):
        return func.attr, True
    return None


def findings_for(
    action_name: str, owner: type, method: str, view: Optional[type] = None
) -> List[Finding]:
    """
    Walk one action and everything it calls on its own class, and report each rule it breaks.

    :param action_name: how to name the action in a finding
    :param owner: the class that declares the action
    :param method: the action's method name on ``owner``
    :param view: the View class, when ``owner`` is a Controller whose ``self.view`` calls are followed
    :return: the findings, in the order met
    """
    found: List[Finding] = []
    seen: Set[Tuple[type, str]] = set()

    def visit(cls: type, name: str, is_action: bool) -> None:
        if (cls, name) in seen:
            return
        seen.add((cls, name))
        function = getattr(cls, name, None)
        if isinstance(function, property):
            function = function.fget  # a property read runs its getter
        tree = _source_tree(function) if function is not None else None
        if tree is None:
            return
        if is_action:
            arguments = tree.args.args + tree.args.kwonlyargs
            for argument in arguments:
                bad = _annotation_names(argument.annotation) & DATA_TYPES
                for type_name in sorted(bad):
                    found.append(
                        Finding(
                            action_name,
                            "data parameter",
                            f"{argument.arg}: {type_name}",
                        )
                    )
        # A panel that is only the receiver of a call written as a bare statement is being
        # written to: the call's result is thrown away, so no value can reach the action.
        discarded = {
            id(statement.value.func.value)
            for statement in ast.walk(tree)
            if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and isinstance(statement.value.func.value, ast.Attribute)
            and statement.value.func.value.attr.lower().endswith("controls")
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = (
                    node.func.attr if isinstance(node.func, ast.Attribute) else None
                )
                if called in WIDGET_VALUE_CALLS and not node.args and not node.keywords:
                    found.append(
                        Finding(
                            action_name, "widget value", f"{name} calls .{called}()"
                        )
                    )
                if called in HELPER_CALLS:
                    found.append(
                        Finding(action_name, "panel helper", f"{name} calls {called}")
                    )
                    continue
                target = _self_call(node)
                if target is not None:
                    called_name, on_view = target
                    if called_name in HELPER_CALLS:
                        continue
                    if on_view:
                        if view is not None:
                            visit(view, called_name, False)
                    else:
                        visit(cls, called_name, False)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                if node.attr.lower().endswith("controls") and id(node) not in discarded:
                    found.append(
                        Finding(action_name, "panel reach", f"{name} reads {node.attr}")
                    )
                if node.attr in WIDGET_DERIVED_ATTRIBUTES:
                    found.append(
                        Finding(
                            action_name,
                            "widget-derived state",
                            f"{name} reads {node.attr}",
                        )
                    )
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                    and isinstance(getattr(cls, node.attr, None), property)
                ):
                    visit(cls, node.attr, False)  # the getter may read widget state too

    visit(owner, method, True)
    unique: Dict[Tuple[str, str, str], Finding] = {}
    for finding in found:
        unique.setdefault(finding.key, finding)
    return list(unique.values())


def _view_class(controller: type) -> Optional[type]:
    annotation = controller.__dict__.get("__annotations__", {}).get("view")
    if isinstance(annotation, str):
        annotation = sys.modules[controller.__module__].__dict__.get(annotation)
    return annotation if isinstance(annotation, type) else None


def _analysis_tab_controllers() -> List[type]:
    controllers: List[type] = []
    for _finder, module_name, _is_package in pkgutil.walk_packages(
        analysistabs_package.__path__, analysistabs_package.__name__ + "."
    ):
        module = importlib.import_module(module_name)
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, MetaController)
                and cls.__module__ == module_name
                and cls not in controllers
            ):
                controllers.append(cls)
    return controllers


def _real_actions() -> List[Tuple[str, type, str, Optional[type]]]:
    """(label, declaring class, method, view for self.view calls) for every declared action."""
    actions: List[Tuple[str, type, str, Optional[type]]] = []
    for controller in _analysis_tab_controllers():
        view = _view_class(controller)
        for attribute, name in declared_actions(controller):
            actions.append(
                (f"{controller.__name__}.{name}", controller, attribute, view)
            )
        if view is not None:
            for attribute, name in declared_actions(view):
                actions.append((f"{view.__name__}.{name}", view, attribute, None))
    return actions


REAL_ACTIONS = _real_actions()


def _violations(
    label: str, owner: type, method: str, view: Optional[type]
) -> List[Finding]:
    return [f for f in findings_for(label, owner, method, view) if f.key not in ALLOWED]


class TestTheRealTabs:
    def test_the_walk_finds_the_actions_recorded_today(self) -> None:
        """So the test below cannot pass by finding nothing to check."""
        labels = {label.split(".", 1)[1] for label, *_ in REAL_ACTIONS}

        assert {"reset", "overlay_plot", "update_ensemble_distribution"} <= labels

    @pytest.mark.parametrize(
        "label, owner, method, view",
        REAL_ACTIONS,
        ids=[label for label, *_ in REAL_ACTIONS],
    )
    def test_a_recorded_action_reads_no_widget(
        self, label: str, owner: type, method: str, view: Optional[type]
    ) -> None:
        assert _violations(label, owner, method, view) == []

    def test_every_allowed_entry_still_trips(self) -> None:
        live = {
            finding.key
            for label, owner, method, view in REAL_ACTIONS
            for finding in findings_for(label, owner, method, view)
        }

        assert [key for key in ALLOWED if key not in live] == []


class TestTheRulesFireOnDoubles:
    """Each rule is seen to fail against a double that breaks it."""

    def test_a_panel_helper_call_is_caught(self) -> None:
        class Leaky:
            @register_action("leaky")
            def leaky(self, parameters: Dict[str, Any]) -> None:
                self.get_selected_filters()

        assert [f.rule for f in findings_for("Leaky.leaky", Leaky, "leaky")] == [
            "panel helper"
        ]

    def test_a_widget_value_read_two_calls_down_is_caught(self) -> None:
        class Deep:
            @register_action("deep")
            def deep(self) -> None:
                self._outer()

            def _outer(self) -> None:
                self._inner()

            def _inner(self) -> None:
                self.box.currentText()

        found = findings_for("Deep.deep", Deep, "deep")

        assert [(f.rule, f.detail) for f in found] == [
            ("widget value", "_inner calls .currentText()")
        ]

    def test_a_reach_into_a_controls_panel_is_caught(self) -> None:
        class Reach:
            @register_action("reach")
            def reach(self) -> None:
                self.metadatacontrols.bins_lineEdit

        assert [f.rule for f in findings_for("Reach.reach", Reach, "reach")] == [
            "panel reach"
        ]

    def test_a_panel_call_whose_result_is_discarded_is_a_write_not_a_read(
        self,
    ) -> None:
        """No value comes back from a bare-statement call, so none can reach the action."""

        class Refill:
            @register_action("refill")
            def refill(self) -> None:
                self.clusteringcontrols.update_clusters([1, 2])

        assert findings_for("Refill.refill", Refill, "refill") == []

    def test_a_panel_call_whose_result_is_used_is_still_caught(self) -> None:
        class Used:
            @register_action("used")
            def used(self) -> None:
                labels = self.clusteringcontrols.update_clusters([1])
                print(labels)

        assert [f.rule for f in findings_for("Used.used", Used, "used")] == [
            "panel reach"
        ]

    def test_a_call_through_the_panel_on_one_of_its_widgets_is_still_caught(
        self,
    ) -> None:
        """Only a call made on the panel itself is exempt; one made on a widget it holds is not."""

        class Through:
            @register_action("through")
            def through(self) -> None:
                self.clusteringcontrols.label_x_comboBox.clear()

        assert [
            f.rule for f in findings_for("Through.through", Through, "through")
        ] == ["panel reach"]

    def test_the_clustering_redraw_that_refills_the_label_dropdowns_is_clean(
        self,
    ) -> None:
        """
        ``update_plot`` ends with ``clusteringcontrols.update_clusters(...)``, a write.

        Only the panel rule is asked about: ``update_plot`` is reached from recorded actions,
        not recorded itself, so the rule about a recorded action's parameters does not apply.
        """
        found = findings_for("update_plot", ClusteringView, "update_plot")

        assert [f for f in found if f.rule == "panel reach"] == []

    def test_widget_derived_state_is_caught(self) -> None:
        class Mode:
            @register_action("mode")
            def mode(self) -> None:
                if self._analysis_mode == "individual":
                    pass

        assert [f.rule for f in findings_for("Mode.mode", Mode, "mode")] == [
            "widget-derived state"
        ]

    def test_the_stored_clustering_settings_are_widget_derived_state(self) -> None:
        """The settings dialog stores them, as the Timer dialog stores RawData's limits."""

        class Stored:
            @register_action("stored")
            def stored(self, loader: str) -> None:
                self.clustering_config_map.get(loader)

        assert [f.rule for f in findings_for("Stored.stored", Stored, "stored")] == [
            "widget-derived state"
        ]

    def test_writing_widget_derived_state_is_not_a_read(self) -> None:
        class Writer:
            @register_action("writer")
            def writer(self) -> None:
                self._last_event_action = "plot_events"

        assert findings_for("Writer.writer", Writer, "writer") == []

    def test_a_data_parameter_is_caught(self) -> None:
        class Takes:
            @register_action("takes")
            def takes(self, ax: Axes, columns: typing.Sequence[NDArray]) -> None:
                pass

        found = findings_for("Takes.takes", Takes, "takes")

        assert sorted(f.detail for f in found) == ["ax: Axes", "columns: NDArray"]

    def test_a_controller_action_is_followed_into_its_view(self) -> None:
        class View:
            def draw(self) -> None:
                self.plot_type_box.currentText()

        class Controller:
            view: View

            @register_action("run")
            def run(self) -> None:
                self.view.draw()

        found = findings_for("Controller.run", Controller, "run", View)

        assert [(f.rule, f.detail) for f in found] == [
            ("widget value", "draw calls .currentText()")
        ]

    def test_a_clean_action_has_no_findings(self) -> None:
        class Clean:
            @register_action("clean")
            def clean(self, parameters: Dict[str, Any]) -> None:
                self.value_from_arguments = parameters["x"]

        assert findings_for("Clean.clean", Clean, "clean") == []

    def test_state_read_behind_a_property_is_caught(self) -> None:
        class Behind:
            @property
            def figure(self) -> str:
                return "one" if self._analysis_mode == "individual" else "other"

            @register_action("behind")
            def behind(self) -> None:
                self.figure.clear()

        found = findings_for("Behind.behind", Behind, "behind")

        assert [(f.rule, f.detail) for f in found] == [
            ("widget-derived state", "figure reads _analysis_mode")
        ]

    def test_a_drawing_call_that_takes_arguments_is_not_a_widget_read(self) -> None:
        """``Axes.text(x, y, s)`` writes; ``QLineEdit.text()`` reads. Only the second takes no arguments."""

        class Draws:
            @register_action("draws")
            def draws(self, ax) -> None:  # type: ignore[no-untyped-def]
                ax.text(0.98, 0.95, "label")
                ax.text(x=0.1, y=0.2, s="keywords")

        assert findings_for("Draws.draws", Draws, "draws") == []

    def test_an_argument_less_text_call_is_still_a_widget_read(self) -> None:
        class Reads:
            @register_action("reads")
            def reads(self) -> None:
                self.field.text()

        found = findings_for("Reads.reads", Reads, "reads")

        assert [(f.rule, f.detail) for f in found] == [
            ("widget value", "reads calls .text()")
        ]
