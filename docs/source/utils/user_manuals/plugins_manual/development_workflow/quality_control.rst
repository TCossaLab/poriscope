.. _quality_control:

Quality Control and Developer Workflow
======================================

Poriscope uses automated **quality control checks** to ensure that all contributed code
is consistent, correct, and maintainable.

These checks are enforced through continuous integration (CI) and can also be enforced
locally using **Git hooks**.

This section explains what checks exist, when they run, and how developers should work
with them.

Overview of Quality Controls
----------------------------

.. note::

   New to "automated quality control"? The short version: instead of asking a human
   reviewer to manually check formatting, typos in docstrings, or whether your new
   plugin actually implements the right methods, Poriscope runs small programs that
   check these things for you, every time, in seconds. This section explains what
   each one does and why it exists — you don't need any prior experience with these
   tools to follow along.

The following tools are used in Poriscope:

- **Black** – automatic Python code formatting
- **Ruff** – linting and safe automatic fixes
- **Mypy** – static type checking. Every function under ``poriscope/`` must carry
  parameter and return type hints; see :ref:`type_checking_policy` below
- **pydoclint** – checks that a docstring's documented parameters, return type, and
  raised exceptions actually match the function's real signature and body (see
  :ref:`docstring_consistency` below)
- **check-added-large-files** – prevents accidental commits of large files
- **Ruff security rules** – a second, separately scoped Ruff pass over
  ``poriscope/plugins/`` only, flagging code execution, unsafe deserialization and
  process spawning; see :ref:`plugin_trust_boundary` below
- **plugin module-level code check** – rejects code that runs when a plugin is merely
  discovered; see :ref:`plugin_trust_boundary` below

All seven are managed through the **pre-commit** framework.

Two further gates are not pre-commit hooks but are enforced just as strictly:

- a dedicated automated test — :ref:`plugin_compliance_testing` below — checks that any
  plugin you add or modify actually implements the interface its base class requires. It
  runs as part of the normal test suite, but for anyone contributing a plugin it is just
  as much a compliance gate as the tools above, and often the one that matters most. A
  companion test, :ref:`settings_schema_checking`, does the same for the settings schema
  your plugin declares.
- the **documentation render check** — :ref:`docs_render_check` below — rebuilds the
  Sphinx documentation on every pull request with warnings treated as errors. pydoclint
  checks that a docstring *describes the right things*; it does not check that the
  docstring is valid reStructuredText. Those are different failure modes, and only this
  gate catches the second one.

Pre-commit Hooks (Validation)
-----------------------------

Poriscope uses *pre-commit* to run **validation checks before each commit**.

When committing code (either via the command line or GitHub Desktop), the following hooks
run automatically:

- ``ruff`` (strict mode) – validates code without modifying files
- ``ruff-plugin-security`` – security-relevant rules, plugin tree only
- ``mypy`` – validates static typing
- ``pydoclint`` – validates that docstrings match real signatures and behavior
- ``plugin-module-level`` – blocks import-time code in a data plugin
- ``check-added-large-files`` – blocks files larger than 123 KB

``mypy`` and ``pydoclint`` are both scoped to ``poriscope/`` and do not run against
``tests/``. ``ruff-plugin-security`` is scoped to ``poriscope/plugins/`` and
``plugin-module-level`` more narrowly still, to the eight data-plugin families.
Everything else runs against every tracked file.

These checks **never modify files**.

If **any hook fails**, the commit is **blocked**.

Automatic Formatting and Auto-fixes
-----------------------------------

Automatic formatting and safe lint fixes are intentionally excluded from the
commit stage.

The following tools run **only when explicitly requested**:

- ``black`` – reformats Python code
- ``ruff --fix`` – applies safe automatic lint fixes

To run these tools manually on all files, use:

.. code-block:: bash

   pre-commit run --all-files --hook-stage manual

Any files modified by this command must be reviewed and committed manually.

This design ensures that:

- Commits never change files unexpectedly
- Developers stay in control of formatting changes
- CI behavior matches local expectations

Installing Pre-commit
---------------------

Automatic installation (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In most cases, **pre-commit is installed automatically** when you run the Poriscope
setup script:

.. code-block:: bash

   python scripts/setup_hooks.py

Manual installation (fallback)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the setup script was not run, or if Git hooks were removed or reset, you can
install ``pre-commit`` manually from the repository root:

.. code-block:: bash

   python -m pip install pre-commit
   pre-commit install

Verification
^^^^^^^^^^^^

To verify that pre-commit is active, run:

.. code-block:: bash

   pre-commit run --all-files

If this succeeds, the repository meets all required quality checks.

Using GitHub Desktop
--------------------

GitHub Desktop enforces Poriscope’s Git hooks when configured to use **System Git**.
If a validation check fails, the commit is blocked and an error message is shown.

Verifying Hook Enforcement
^^^^^^^^^^^^^^^^^^^^^^^^^^

To confirm that hooks are active in GitHub Desktop, temporarily introduce a small
type error in any tracked Python file:

.. code-block:: python

   def _pre_commit_test() -> int:
       return "not an int"

Attempt to commit the change:

- If the commit is **blocked**, the hooks are working correctly.
- If the commit is **not blocked**, re-run the setup script:

  .. code-block:: bash

     python scripts/setup_hooks.py

After verification, revert the temporary change.

.. note::

   In Poriscope’s current workflow, formatting tools such as black and
   ruff --fix are executed in a dedicated auto-fix step before strict
   validation.

   During continuous integration (CI), these tools may automatically modify
   files and commit the fixes back to the branch. After auto-fixing, all
   quality checks (including strict ruff validation and mypy) are
   re-run, and the CI job only fails if unresolved issues remain.

   A commit will not be blocked locally unless strict validation hooks fail.

Running Quality Checks Manually
-------------------------------

Run all **validation hooks** (the same checks enforced during commits and CI):

.. code-block:: bash

   pre-commit run --all-files

Run individual validation tools:

.. code-block:: bash

   pre-commit run ruff
   pre-commit run mypy
   pre-commit run pydoclint
   pre-commit run check-added-large-files

.. warning::

   Use ``pre-commit run mypy`` rather than a bare ``mypy poriscope``. The hook runs
   mypy in an isolated environment with no project dependencies, which is exactly what
   CI does. Running mypy directly from your own virtual environment sees the real
   PySide6/numpy/pandas type stubs, and it will report several hundred additional
   messages that the gate does not care about. Those are not failures you need to fix —
   they are a different tool configuration answering a different question.
   **The hook is the gate.**

   The version is pinned in two places and they are deliberately kept equal:
   ``.pre-commit-config.yaml`` runs mirrors-mypy ``rev: v1.17.1``, and
   ``pyproject.toml``'s ``[dev]`` extra and ``requirements-dev.txt`` both declare
   ``mypy==1.17.1``. If you bump one, bump the other in the same commit — the two drifted
   apart until 2026-09-04, and the resulting version gap was mistaken for the dependency
   blindness described above. See ``DECISIONS.md``.

.. _docs_render_check:

Checking That the Documentation Still Renders
---------------------------------------------

Most of Poriscope's documentation is generated from the docstrings you write, so a
malformed directive or a broken cross-reference in a docstring is a documentation bug.
``pydoclint`` will not catch it: it verifies that the parameters, return type and
exceptions a docstring documents match the real function, not that the surrounding
reStructuredText is well formed. Sphinx catches it, so Sphinx is a gate.

Every pull request targeting ``main``, ``develop`` or a ``release/*`` branch runs the
**Docs Render Check** workflow, which regenerates the autodoc ``.rst`` files and builds
the HTML with ``-W`` — warnings are errors. To run exactly what it runs:

.. code-block:: bash

   python scripts/generate_all_autodoc_rst.py
   sphinx-build -W --keep-going -b html docs/source docs/build

``--keep-going`` reports every warning in one pass instead of stopping at the first, so
you can fix them all in a single edit. The ``post-merge`` git hook uses the same flags
(see :doc:`post_merge_automation`), so if hooks are installed you will usually see a
rendering problem the moment you merge rather than when you open a pull request.

.. note::

   The generator step is not optional. ``docs/source/autodoc/`` is git-ignored and
   regenerated from the source tree, so a build without it fails on missing table-of-
   contents entries rather than on anything you did.

.. note::

   **The build imports the real package, PySide6 included.** ``autodoc`` does not mock
   Qt - ``docs/source/conf.py`` explains at length why mocking it is not an option here -
   so ``sphinx-build`` needs an environment in which ``import poriscope`` works fully. On
   a development machine with the project installed that is automatic. In CI both docs
   workflows install ``libegl1``, ``libgl1`` and ``libxkbcommon0`` first: those are the
   libraries the bundled ``libQt6Gui``/``libQt6Widgets``/``libQt6Svg`` link against that
   the runner image does not already provide, and the dynamic loader resolves all three
   the moment the module is imported. Without them the import fails halfway through
   ``poriscope.exposed`` and the build fills with unrelated autodoc errors. Xvfb and the
   ``libxcb-*`` packages the test workflows install are not needed, since those load with
   the xcb platform plugin and a docs build never instantiates a ``QApplication``.

Running Auto-fix Hooks Manually
-------------------------------

To apply all automatic formatting and safe fixes:

.. code-block:: bash

   pre-commit run --all-files --hook-stage manual

After running:

1. Review the changes
2. Stage the modified files
3. Commit manually

.. note::

   **Ruff runs in two modes**:

   - **Auto-fix mode (manual stage)**: fixes code and modifies files
   - **Validation mode (commit & CI)**: checks only, fails on violations

.. note::

   **Which rules are enabled.** Ruff's default rule set is in force and
   ``pyproject.toml`` uses ``extend-select``, which adds to those defaults rather
   than replacing them. That matters more than it looks: several conventions this
   project cares about are already enforced without appearing anywhere in the
   config. The one worth knowing is ``E722``, **no bare** ``except:`` -- narrow to
   ``except Exception:`` at minimum, so that the exceptions you are actually
   swallowing can be named in a ``:raises:`` docstring section.

   On top of the defaults, ``pyproject.toml`` selects:

   - ``I`` -- import ordering (isort).
   - ``B006`` -- a mutable data structure used as an argument default. A ``[]`` or
     ``{}`` default is built once, when the function is defined, and then shared by
     every call, so anything that mutates it leaks state between calls. Use ``None``
     and create the container inside the function.
   - ``B020`` -- a loop control variable that shadows the iterable it iterates over.
     It does not break the loop, because the iterator is created before the first
     assignment, but it makes the original sequence unreachable for the rest of the
     loop body and forces the parameter to be annotated loosely.

   The other ``flake8-bugbear`` and ``bandit`` rules are deliberately **not** enabled
   *project-wide*, and this is settled rather than pending. Each of ``B905``, ``B904``,
   ``B007``, ``S110``, ``S112`` and ``S101`` was run once as an audit and its findings in
   maintained code fixed. What keeps each one from becoming a gate differs by rule.
   ``S101`` would flag every ``assert`` in the test suite, where 2,243 of its 2,250 sites
   are, so suppressing it there would suppress essentially all of it. ``B905`` needs a
   per-site ``strict=`` judgement, and at least one call cannot be proven equal-length in
   advance. The handful of sites left for ``B904``, ``B007``, ``S110`` and ``S112`` are
   spread across the test suite, the ``scripts/autodoc/`` generators and the fitter
   plugins another developer maintains. In each case enabling the rule would require a
   ``per-file-ignores`` entry that hides a real check rather than satisfying it. The
   reasoning, and the separate acceptance of the ``S608`` hardcoded-SQL sites, are
   recorded in ``DECISIONS.md``; what each audit found is in ``changelog.md``. Please do
   not re-propose them without reading that entry first.

   **This is a different question from the security rules that do run on the plugin
   tree.** ``ruff-plugin-security`` selects a separate, narrower set of ``S`` rules and
   applies them only under ``poriscope/plugins/`` -- see
   :ref:`plugin_trust_boundary`. The two do not overlap: none of the audited-and-declined
   rules above is in that selection, and ``S608`` is not either.

.. _plugin_trust_boundary:

Plugin Code Runs on Your Machine
--------------------------------

Two of the hooks exist for one reason: **plugin discovery executes every Python file it
finds.** ``MainModel.populate_available_plugins()`` walks ``poriscope/plugins/`` and your
configured user-plugin folder recursively, and for each file it calls
``spec.loader.exec_module()``. Python runs module-level code unconditionally, before
anything has inspected the class -- so a plugin file is a code-execution boundary in a way
that the rest of the application is not.

For code written inside the lab that is an accepted convenience. For a plugin arriving in
a pull request from outside it is worth a check, so two hooks police it:

``ruff-plugin-security``
   A second Ruff pass over ``poriscope/plugins/``, selecting only rules a
   nanopore-analysis plugin has no legitimate reason to trip: ``exec`` and ``eval``
   (``S102``, ``S307``), unsafe deserialization (``S301`` pickle, ``S302`` marshal,
   ``S506`` yaml), process spawning (``S601``--``S607``, ``S609``), and network or
   temp-file risks (``S310`` urlopen, ``S306`` mktemp).

``plugin-module-level``
   Rejects any module-level statement in a data plugin that runs code. The rule is that
   **module-level assignment is fine but module-level invocation is not**, so a type alias
   such as ``Numeric = Union[int, float, np.number]`` passes while
   ``logger = logging.getLogger(__name__)`` does not -- move that kind of thing into a
   method. Only imports, constants, classes and functions belong at the top level of a
   plugin. Decorators on a class or function are not examined, since ``@log`` is part of
   the plugin pattern.

   Run it yourself on the plugin you are writing::

      python scripts/check_plugin_module_level.py poriscope/plugins/eventfinders/MyFinder.py

Both are measured at zero findings on the shipped tree, so neither has a baseline or any
exemptions -- if one fires on your plugin, it has found something real.

.. important::

   These checks raise the bar against a careless submission. They are **not** a sandbox
   and not a defence against a determined adversary: a plugin can still do as it likes
   inside a method body that only runs once the plugin is instantiated, and neither hook
   sees a file you drop straight into your user-plugin folder without a pull request.
   Plugins are reviewed by a human before they are merged, and that review remains the
   real gate.


Skipping Hooks (Advanced Use Only)
----------------------------------

In exceptional cases:

.. code-block:: bash

   git commit --no-verify

This should only be used in emergencies. Regular use undermines code quality and consistency.

.. warning::

   Skipping local verification does **not** bypass automated checks in the continuous
   integration (CI) pipeline. All enforced quality checks are re-run on GitHub, and
   commits that fail CI will not be merged. In practice, using ``--no-verify`` only
   delays failure and should be avoided.

.. _docstring_consistency:

Docstring and Signature Consistency (pydoclint)
------------------------------------------------

.. note::

   This is a "docstring linter." If that phrase is new to you: a *linter* is a
   program that reads your code without running it and flags things that look wrong.
   Most linters (like Ruff) look at style. ``pydoclint`` instead compares your
   docstring's claims against what the function's code actually does.

Think of a docstring like the label on a bottle of reagent: it tells the next person
(possibly a future version of yourself) what's inside, how much to use, and what to
watch out for. A label that doesn't match the contents is arguably *worse* than no
label at all, because people trust it and act on it anyway. ``pydoclint`` exists to
catch exactly that mismatch — automatically, before it ships.

Concretely, for every documented function, ``pydoclint`` checks that:

- every parameter named in the docstring actually exists in the function signature
  (and vice versa — no undocumented parameters, no documented parameters that don't
  exist),
- the documented return type matches what the function actually returns,
- the exceptions listed in a ``Raises`` section match the exceptions the function can
  actually raise.

.. important::

   ``pydoclint`` does **not** require every function to have a docstring. It only
   holds a docstring accountable *if one already exists* — if you didn't write one,
   ``pydoclint`` has nothing to check.

   It *does* require that a documented function's signature carry type hints, and
   that those hints agree with the docstring's ``:type:`` and ``:rtype:`` fields. The
   signature is the source of truth; where the two disagree, fix the docstring.
   (Separately, ``mypy`` now requires type hints on **every** function under
   ``poriscope/``, documented or not — see :ref:`type_checking_policy`.)

Running it locally
^^^^^^^^^^^^^^^^^^^

``pre-commit run --all-files`` already runs ``pydoclint`` on your behalf, so most
contributors will meet it there rather than by invoking it directly. If you want to
check just the docstring/signature rules on their own:

.. code-block:: bash

   pydoclint --baseline=.pydoclint-baseline.txt poriscope

.. tip::

   A ``DOC105`` ("type hints do not match") that makes no sense is usually a
   formatting problem rather than a real mismatch. ``pydoclint`` folds any prose that
   trails a ``:type:`` field into that field's value, so a docstring written with the
   parameter list first and the descriptive paragraph last reports a spurious
   ``DOC105`` against whichever parameter happens to be documented last. Put the
   description **first**, then the ``:param:``/``:type:``/``:return:``/``:rtype:``
   fields, and it goes away.

Why is there a "baseline" file?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``pydoclint`` was first introduced, roughly 1,090 pre-existing docstring
mismatches predated the tool. Rather than blocking every future commit on cleaning up
the entire history at once, they were recorded in ``.pydoclint-baseline.txt`` and
allowed to remain while they were worked through.

.. important::

   **That cleanup is finished.** ``.pydoclint-baseline.txt`` is now an empty,
   zero-byte file, and it should stay that way. There is nothing left to forgive, so
   every violation the hook reports is a real one in code you touched, and it will
   fail the commit.

   In particular, **do not** regenerate the baseline to make a failure go away:

   .. code-block:: bash

      # Don't do this to silence a failure - fix the docstring instead.
      pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope

   Re-populating the baseline would silently re-open the door to exactly the
   mismatches the cleanup closed. Fix the docstring the tool is complaining about.

.. _type_checking_policy:

Type Annotation Policy (mypy)
------------------------------

Every function under ``poriscope/`` carries parameter and return type hints, with no
exclusions, and ``mypy.ini`` enforces that:

- ``disallow_untyped_defs = True`` — a function with no annotations is an error rather
  than being silently skipped. **New code must be annotated.**
- ``check_untyped_defs = True`` — function bodies are type-checked even where the
  checker cannot fully resolve their types.
- ``strict_equality = True`` — catches comparisons between types that can never be
  equal, such as a display string compared against an integer channel id.
- ``python_version = 3.12`` — fixes the language and standard-library level mypy checks
  against. Without it mypy assumes whatever interpreter happens to run it, so a
  contributor on a newer Python could see a different verdict from CI. Only
  ``MAJOR.MINOR`` is valid here; the patch-level floor is ``requires-python`` in
  ``pyproject.toml``, which is a separate concern.

.. note::

   If you are adding a plugin, the simplest and most reliable way to annotate its
   methods is to **copy the signature from the ``Meta*`` base class verbatim**, rather
   than inferring types from your implementation. The compliance test in
   :ref:`plugin_compliance_testing` compares your override against the base, and for
   generic types such as ``List[str]`` it compares them by *equality* — so a
   reasonable-looking widening of the base's type will fail it.

.. _plugin_compliance_testing:

Test Suite Configuration
-------------------------

``pytest.ini`` is the only pytest configuration in the repository. Three settings there are
worth knowing about before you add tests:

- ``timeout = 300`` — a per-test backstop in seconds, supplied by ``pytest-timeout``. It
  exists because a hung Qt test otherwise runs to GitHub Actions' six-hour job limit. It
  is not a performance budget: the slowest unit test measures about 1.4 seconds, and the
  explicit ``@pytest.mark.timeout`` markers under ``tests/e2e/`` and
  ``tests/integration/`` are all 90 seconds or less and still override the default. **If
  your test trips this value, that is a finding about the test, not a reason to raise
  the number.**
- ``--strict-markers`` — an unregistered marker name is a collection error rather than an
  expression that matches nothing. Register any new marker in the ``markers`` list.
- ``pythonpath = .`` — puts the repository root on ``sys.path`` so the shared test helpers
  (``tests/unit/views/_qt_mocks.py``, ``tests/e2e/_helpers.py``, the
  ``tests/synthetic_data/`` generators) are importable as ``tests.<module>``. The editable
  install exposes only ``poriscope``, so without this setting those imports resolve only
  when a conftest higher up the tree happens to be collected first — which made running a
  single test file on its own fail with ``No module named 'tests'`` while the same file
  passed in a full run.

.. note::

   If you add a dev dependency, it must go in **both** ``pyproject.toml``'s ``[dev]`` extra
   and ``requirements-dev.txt``. They are byte-for-byte mirrors of each other and nothing
   enforces that, but different CI workflows read different ones: ``ci-branches.yml`` and
   ``ci-fork-pr.yml`` install only from ``requirements-dev.txt``, while ``release.yml``
   installs only ``.[dev]``. Adding it to one file alone breaks half of CI. Pin it exactly
   with ``==``, as every other entry in both files is.

Coverage is measured with ``pytest-cov``, which is declared in the ``[dev]`` extra but is
**not** wired into ``addopts``:

.. code-block:: bash

   pytest --cov=poriscope --cov-report=term-missing

Run it deliberately when you want the number. The plain ``pytest`` invocation is the
pre-commit gate and stays free of coverage instrumentation. ``ci-internal-pr.yml`` runs
the coverage variant and prints the line rate as a GitHub notice; nothing fails on a
drop, so treat it as information rather than a gate.

Plugin Interface Compliance Testing
------------------------------------

Recall from :ref:`understanding base classes <understanding_base_classes>` that every
``MetaXXXX`` base class is a blueprint: it defines exactly which methods a plugin
*must* implement, with which arguments, in which order, and returning what type.
Writing a plugin that follows the blueprint isn't optional — it's how Poriscope's GUI
and scripting layer both know how to talk to your plugin without any extra
configuration.

Continuing that analogy: if the base class is the blueprint, then
``tests/unit/plugins/test_plugin_compliance.py`` is the building inspector. It doesn't
care about interior decorating (that's your algorithm's business) — it walks through
every plugin in the codebase and checks that the load-bearing structure the blueprint
demanded is actually there.

Concretely, this test:

1. recursively imports every module under ``poriscope.plugins`` so that every plugin
   class actually gets loaded,
2. finds every concrete subclass of each ``Meta*``/``BaseDataPlugin`` base,
3. checks that each one implements every method its base class marks as
   ``@abstractmethod``,
4. checks that overridden methods keep the same argument names, the same argument
   order, and (where type hints are present) a compatible type signature.

Run it locally with:

.. code-block:: bash

   pytest tests/unit/plugins/test_plugin_compliance.py

This is exactly the test referred to in :ref:`build_data_plugin` and
:ref:`build_frontend_plugin` when they say a contribution must "pass our tests and
type checks" — **a plugin cannot be merged if this test fails against it**, no matter
how good the underlying science is.

.. tip::

   If you're building a new plugin, don't wait until you're "done" to run this test.
   Stub out the required methods first (even with just ``pass`` in the body), run the
   test, and fix any interface mismatches immediately. It is much cheaper to fix a
   wrong argument name before you've written 200 lines of logic around it than after.

.. _settings_schema_checking:

Settings-Schema Checking
-------------------------

Interface compliance above checks the *methods* your plugin implements. A separate check
covers the *settings schema* it declares — the dict your ``get_empty_settings()`` returns,
where each parameter carries a ``Type`` and optionally a ``Value``, ``Options``, ``Min``,
``Max`` and ``Units``.

The reason this needs its own check is that nothing else looks at the schema until a user
tries to use your plugin. ``BaseDataPlugin`` validates a *supplied* settings dict at
instantiation, so a contradiction baked into the schema itself — a ``Min`` above its
``Max``, an ``Options`` list whose entries are not of the declared ``Type``, a default that
is not among its own ``Options`` — surfaces as a ``TypeError`` or ``ValueError`` raised
from inside the base class, with nothing pointing at your schema as the cause.

The single most common version of this, and the one that caught real plugins in the
codebase when the check was introduced, is declaring ``"Type": float`` and then writing an
int default:

.. code-block:: python

   settings["Min Height"] = {"Type": float, "Value": 500}     # wrong
   settings["Min Height"] = {"Type": float, "Value": 500.0}   # right

The runtime check is a bare ``isinstance``, and ``isinstance(500, float)`` is ``False``.

Run the check over every plugin, or just yours:

.. code-block:: bash

   python scripts/check_plugin_schemas.py
   python scripts/check_plugin_schemas.py MyEventFinder

It is also part of the normal test suite, as
``tests/unit/plugins/test_plugin_settings_schema.py``, so CI enforces it whether or not
you run the script. To call the check on a schema directly — from your own test, say —
use ``poriscope.utils.settings_schema.validate_settings_schema()``, which takes a schema
and returns a list of human-readable problems.

.. note::

   Omitting ``Value`` entirely is fine and means the same as ``Value: None``: no default,
   the user must supply one. Most shipped readers do exactly this. What is *not* fine is
   supplying a ``Value`` that contradicts the ``Type`` beside it.

.. _duplication_ratchet:

Analysis-Tab Duplication Ratchet
---------------------------------

This one only affects you if you edit the analysis tabs — the five ``*View.py`` and
``*Controller.py`` files under ``poriscope/plugins/analysistabs/`` or the five
``*controls.py`` under its ``utils/``. Those three families carry a large amount of
byte-identical duplication, and the 2.0.0 refactor is removing it. The ratchet exists so
that removal is *demonstrated* rather than asserted.

``scripts/measure_duplication.py`` counts, per family, how many function bodies are
byte-identical across more than one file and how many lines would be deleted by promoting
one copy to a shared base. ``.duplication-baseline.json`` records those counts, and
``tests/unit/scripts/test_duplication_ratchet.py`` fails if the measurement disagrees.

.. code-block:: bash

   python scripts/measure_duplication.py             # the table
   python scripts/measure_duplication.py --verbose   # every duplicate group, largest first
   python scripts/measure_duplication.py --check     # compare against the baseline

**The check is exact, not "no worse than".** A rise means duplication was added. A fall is
a win — and it fails too, so the win is recorded in the same commit that earned it. Under
a "no worse than" rule the baseline would quietly overstate the duplication still present
and the slack would accumulate unnoticed. If your change legitimately removed duplication,
rerun with ``--update`` and commit the new baseline alongside it.

.. warning::

   Read the failure message before running ``--update``. Byte identity is brittle in one
   direction: editing a few characters in *one* copy of a five-way duplicate drops that
   copy out of its group, so the removable count falls by a whole copy's worth while
   nothing was deduplicated — and the duplication is actually *worse*, five near-identical
   bodies instead of five identical ones. The check tells the two apart without any
   similarity measure, because promoting a method to a base **deletes** the copies, so the
   function count falls too, while an edit into divergence leaves it untouched. When it
   sees that shape it says so explicitly.

   If you are fixing a bug in one of these methods, the fix almost certainly belongs in
   every copy.

.. _pre_pr_checklist:

Pre-Pull-Request Compliance Checklist
---------------------------------------

.. important::

   This is the section to bookmark. Before opening or updating a pull request —
   especially one adding a new data plugin or frontend plugin family — walk through
   these steps in order. They mirror exactly what CI will check, so a clean run here
   means CI should pass too, and a maintainer won't send your PR back with something
   you could have caught yourself in thirty seconds.

.. tip::

   If you are *starting* a data plugin rather than finishing one, generate it with
   ``python scripts/new_plugin.py`` — see :ref:`new_plugin_script`. Every step below
   passes against the generated skeleton before you have written any of your own code,
   which means the first failure you see is one you actually caused. Getting a signature
   or a docstring field wrong by hand is by far the most common reason a first plugin PR
   comes back, and the generator copies both verbatim out of the base class.

☐ **1. Apply automatic formatting and safe fixes.**

.. code-block:: bash

   pre-commit run --all-files --hook-stage manual

This runs ``black`` and ``ruff --fix`` and may modify your files. Review the diff,
then stage the changes.

☐ **2. Run strict validation.**

.. code-block:: bash

   pre-commit run --all-files

This runs ``ruff`` (strict), ``mypy``, ``pydoclint``, and ``check-added-large-files``.
Nothing here is auto-fixed for you — if ``mypy`` or ``pydoclint`` report a problem,
you need to edit the code or docstring yourself. See :ref:`docstring_consistency`
above if a pydoclint failure doesn't make sense, and :ref:`type_checking_policy` for
what mypy expects of new code.

.. note::

   Neither failure can be waived. There is no baseline left for ``pydoclint`` to
   forgive a new violation with, and the ``mypy`` annotation flags are on, so an
   unannotated function you add will fail here even though it would once have been
   skipped.

☐ **3. If you added or modified a plugin (or a ``Meta*`` base class), run the plugin
compliance suite and the settings-schema check.**

.. code-block:: bash

   pytest tests/unit/plugins/test_plugin_compliance.py
   python scripts/check_plugin_schemas.py

See :ref:`plugin_compliance_testing` and :ref:`settings_schema_checking` above for what
these actually check. The first covers the methods your plugin implements, the second the
settings schema it declares; they catch different mistakes.

☐ **4. Run the test suite** — the same suite continuous integration runs on every
branch push:

.. code-block:: bash

   pytest

There is no subset and no marker filter, at under 10 minutes, e2e tests are worth their cost. CI runs the whole suite everywhere, e2e
tests included. 

For per-marker counts and mean
durations, run ``pytest --marker-stats``.

☐ **5. Check that the documentation still renders.**

.. code-block:: bash

   python scripts/generate_all_autodoc_rst.py
   sphinx-build -W --keep-going -b html docs/source docs/build

Warnings are errors here, and the same build runs on your pull request. See
:ref:`docs_render_check` above for why this is a separate gate from ``pydoclint``.

☐ **6. Update the changelog.**

Add a plain-language entry to ``changelog.md`` describing what changed, under the
appropriate existing heading — **one line per change, and no more**. The changelog is
written for users, so it carries the essential user-facing information and nothing else:
no sub-bullets, no measurements, and no explanation of why the change was made or what was
rejected along the way. A breaking change is still called out explicitly as breaking,
because that *is* user-facing. Reasoning that needs preserving belongs in ``DECISIONS.md``
instead.

.. warning::

   **If you are contributing from a fork** (the typical path for an external/
   community contribution), steps 1–5 above must be completed *before you push*.
   Fork-originated pull requests run in a restricted, read-only CI workflow that
   performs strict validation and the full test suite — it deliberately cannot
   auto-fix formatting or push corrections back to your branch, for security reasons.
   If you skip step 1 or 2 locally, CI will simply fail on something a maintainer has
   no way to fix for you, and you'll need to push a follow-up commit anyway.

Once all six boxes are checked, you're ready to open (or re-request review on) your
pull request.

Summary for New Developers
--------------------------

- Pre-commit enforces consistent, high-quality code
- Hooks run automatically on commit
- GitHub Desktop enforces the same rules
- Most formatting and lint issues are auto-fixable
- Mypy and pydoclint issues must be resolved manually — neither has a baseline or
  waiver left to fall back on
- All new code under ``poriscope/`` must carry type hints; see
  :ref:`type_checking_policy`
- New or modified plugins must also pass ``test_plugin_compliance.py`` — see
  :ref:`plugin_compliance_testing`
- Docstrings must render, not just describe the right parameters — every pull request
  rebuilds the docs with warnings as errors; see :ref:`docs_render_check`
- Before opening a pull request, work through :ref:`pre_pr_checklist` in full
