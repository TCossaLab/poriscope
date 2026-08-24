# Decisions

Short records of choices made deliberately, especially choices *not* to do something.
The point is to stop the same question being re-litigated from scratch. Each entry is
context, the decision, the evidence behind it, and what would make it worth revisiting.

Detail about work that *was* done lives in `changelog.md` and in git history; this file
is only for the reasoning that would otherwise be lost.

---

## 2026-08-24 - Leave two of the three unguarded `Optional` Qt accessors alone

**Context.** The type-annotation pass flagged three families of Qt accessor that return
`Optional` and are used without a `None` check: `QApplication.instance()`,
`QComboBox.lineEdit()`, and `QTreeWidgetItem.child(i)`/`topLevelItem(i)`.

**Decision.** Only `lineEdit()` was changed. It is now bound once in `__init__`,
immediately after the `setEditable(True)` that makes it non-`None`, because that
guarantee previously sat hundreds of lines away from the uses depending on it. The other
two need no action and should not be "fixed" later:

- `QApplication.instance()` is called inside a `QWidget.__init__`. A `QWidget` cannot be
  constructed before a `QApplication` exists, so `None` is unreachable there.
- `item.child(j)` / `topLevelItem(i)` are always called inside
  `for j in range(...childCount())`, so the index is always valid. This is mypy being
  unable to connect `range(n)` with "valid index", not a defect.

**Revisit if.** Either call moves somewhere that is not a widget constructor, or an
index stops being derived from the matching count.

---

## 2026-08-24 - `@log` erases decorated signatures, which caps what step 7 can buy

**Context.** `LogDecorator.log` is declared `-> Callable`, i.e. `Callable[..., Any]`.
Applying it therefore replaces the decorated method's type with `Any` from the caller's
point of view. Verified with `reveal_type` against the project mypy: for a method
`decorated(self, x: int) -> str`, `reveal_type(p.decorated)` is `Any` and
`reveal_type(p.decorated(1))` is `Any`, while the undecorated twin reveals
`def (x: int) -> str` and `str`. A deliberately wrong call - `p.decorated("not an int")`
- raises no error, where the same call on the undecorated twin does.

**Why it matters.** `@log(logger=logger)` is applied to **935 methods across 71 files**.
So the type-annotation pass has made every *body* checkable, but call sites into any
decorated method are still unchecked. Turning on `disallow_untyped_defs` in step 7 will
not change that.

**Decision.** Not fixed as part of the annotation pass, which was scoped to hints and
docstrings. Recorded as a prerequisite for getting full value from step 7. The fix is
standard and small: give `log` a `TypeVar` bound to `Callable` (or `ParamSpec`) so it
returns the same type it was handed, instead of a bare `Callable`.

**Revisit if.** Step 7 is picked up - this should be done first, or the flip will look
like it verified far more than it did.

---

## 2026-08-24 - Leave the PySide6 short-form enum accesses alone

**Context.** A stub-aware `mypy poriscope` reports 191 `attr-defined` errors of the form
`"type[QSizePolicy]" has no attribute "Expanding"` across ~11 files, because the bundled
PySide6 stubs no longer declare the unscoped enum members.

**Decision.** Do not rewrite them to the scoped form (`QSizePolicy.Policy.Expanding`).

**Evidence.** On the installed PySide6 6.9.0, `QSizePolicy.Expanding` emits no warning of
any kind, and `QSizePolicy.Expanding is QSizePolicy.Policy.Expanding` is `True` - as is
the equivalent for `Qt.AlignCenter`. These are the identical objects, not lookalike
aliases, so this is a stub omission rather than a code defect. A 191-site mechanical
rename with no behavioural change would make review harder, not easier: it buries real
changes and rewrites `git blame` across eleven files. The tempting justification - that
clearing them makes a stub-aware mypy usable as a review tool - does not hold either,
because of the 377 errors that run reports, roughly 308 are noise from other sources
(34 `import-untyped`, 38 `MetaController.view`/`model`, 34 numpy stub pedantry, 11
known-accepted `sublevel_starts`), so clearing the enums alone still leaves ~117 noise
items against a handful of real findings.

**Revisit if.** PySide6 deprecates or removes forgiving-enum mode. Waiting costs nothing:
on the day it changes, every site fails loudly at widget construction and the fix is a
mechanical find-and-replace with the failures pointing at each location.

---

## 2026-08-24 - Accept that the pre-commit mypy hook cannot see project dependencies

**Context.** The `mirrors-mypy` hook runs in an isolated virtualenv containing only mypy,
with `additional_dependencies: []` and upstream default args
`["--ignore-missing-imports", "--scripts-are-modules"]`. PySide6, numpy, pandas, scipy
and sklearn therefore all resolve to `Any` under the gate. Concretely,
`reveal_type(button_mapping.get(button_type, lambda: None))` where
`button_mapping: Dict[str, QPushButton]` prints `Any` under the hook and
`QPushButton | (def ())` under the project venv's mypy - which is why the gate could not
see the `on_button_clicked` fallback bug.

**Decision.** Do not add stubs to the hook. Do not treat this as a blocker for flipping
the type-policy flags.

**Evidence.** See the composition breakdown in the entry above: the genuine signal was 11
`union-attr` findings, all one narrow class (a Qt getter that can return `None`), of
which three were the `button_mapping` bug and eight remain in `SelectionTree.py` and
`MetaView.__init__`. Against that, closing the gap means suppressing or fixing ~191 enum
sites first and then keeping pinned stub versions in sync with the runtime PySide6
forever - and stub drift is what produced that noise in the first place. The hook still
checks all first-party logic and the whole `Meta*` plugin contract, which is the
load-bearing part of this architecture.

**Cheaper alternative if wanted.** Run `mypy poriscope` in the dev venv periodically and
review by hand - possible today with no config change - or add it to the pre-PR
checklist, rather than making it block commits.

**Revisit if.** The `union-attr` class of bug starts recurring in production, or the enum
noise is cleared for other reasons.

---

## 2026-08-24 - The walkthrough `moveEvent` hook is not the cause of the test-suite segfault

**Context.** Running `pytest tests/unit/views tests/unit/plugins` (views first) segfaults
the interpreter inside
`test_walkthrough_mixin.py::test_no_valid_widgets_logs_error`. Commit `bc09de7` had just
replaced a `moveEvent` monkey-patch with a real class-level override on `StepDialog`,
which was a plausible cause: it puts a Python virtual on the move path, `StepDialog`
starts a 300 ms `reposition_timer` that calls `move()`, and the file already carries a
documented `Overlay`/`StepDialog` double-delete hazard (two tests are skipped for
"Qt object lifetime makes this unreliable across platforms").

**Decision.** `bc09de7` is exonerated. Do not revert it, and do not re-derive this
theory.

**Evidence.** The same subset was re-run with `walkthrough.py` and `walkthrough_mixin.py`
checked back to `0e9433c` (pre-`bc09de7`, `on_move` absent from both files, verified) and
the views-first ordering held constant. It crashed identically - same access violation,
same test, same point in the run. The real cause is pre-existing Qt state leakage that
only manifests when `tests/unit/views` runs before `tests/unit/plugins`; pytest executes
explicitly listed paths in the order given, and natural alphabetical collection puts
`plugins` first, which is why CI and the full suite never see it.

**Revisit if.** The crash appears under natural collection order, which would mean it is
a different problem.

**Resolved 2026-08-24.** Bisected to `tests/unit/views/widgets/test_multiselect_filter.py`
-> `TestClearSelectionList` -> the single `listWidget.clear()` call, and fixed by disposing
of widgets with `deleteLater()` plus a drained event loop instead of `QWidget.destroy()`.
See `changelog.md`. The exoneration above stands and is kept because the `moveEvent` hook
is exactly the kind of change this crash would be blamed on again.
