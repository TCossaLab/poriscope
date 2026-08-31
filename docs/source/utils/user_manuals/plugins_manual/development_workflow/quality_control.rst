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

All five are managed through the **pre-commit** framework.

Alongside these, a dedicated automated test — :ref:`plugin_compliance_testing` below —
checks that any plugin you add or modify actually implements the interface its base
class requires. It isn't a pre-commit hook (it runs as part of the normal test suite),
but for anyone contributing a plugin, it is just as much a compliance gate as the
tools above, and often the one that matters most.

Pre-commit Hooks (Validation)
-----------------------------

Poriscope uses *pre-commit* to run **validation checks before each commit**.

When committing code (either via the command line or GitHub Desktop), the following hooks
run automatically:

- ``ruff`` (strict mode) – validates code without modifying files
- ``mypy`` – validates static typing
- ``pydoclint`` – validates that docstrings match real signatures and behavior
- ``check-added-large-files`` – blocks files larger than 123 KB

``mypy`` and ``pydoclint`` are both scoped to ``poriscope/`` and do not run against
``tests/``. Everything else runs against every tracked file.

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
   mypy in an isolated environment with a pinned version and no project dependencies,
   which is exactly what CI does. Running mypy directly from your own virtual
   environment uses a different version *and* sees the real PySide6/numpy/pandas type
   stubs, and it will report several hundred additional messages that the gate does
   not care about. Those are not failures you need to fix — they are a different tool
   configuration answering a different question. **The hook is the gate.**

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

   **Which rules are enabled.** On top of Ruff's default rule set,
   ``pyproject.toml`` selects:

   - ``I`` -- import ordering (isort).
   - ``B006`` -- a mutable data structure used as an argument default. A ``[]`` or
     ``{}`` default is built once, when the function is defined, and then shared by
     every call, so anything that mutates it leaks state between calls. Use ``None``
     and create the container inside the function.
   - ``B020`` -- a loop control variable that shadows the iterable it iterates over.
     It does not break the loop, because the iterator is created before the first
     assignment, but it makes the original sequence unreachable for the rest of the
     loop body and forces the parameter to be annotated loosely.

   The other ``flake8-bugbear`` rules are deliberately **not** enabled yet. The
   measured backlog and the case for adopting them are recorded in
   ``future_fixes.md``.


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

.. _plugin_settings_schema_testing:

Settings Schema Checking
-------------------------

The inspector above reads the blueprint. ``tests/unit/plugins/test_settings_schema.py``
reads the *parts list*: the dict your plugin returns from
:py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.get_empty_settings`.

That method's docstring is a contract, not a suggestion. ``Min``, ``Max`` and
``Options`` are optional, but **``Type`` and ``Value`` are required on every
parameter, and any value you supply must be consistent with its ``Type``.** This test
instantiates each plugin, asks it for its schema, and checks that:

* every parameter declares both ``Type`` and ``Value``, and ``Type`` is a real class,
* ``Min <= Max`` wherever both are given,
* every entry in ``Options`` is an instance of the declared ``Type``,
* any default you *do* ship would survive your own plugin's validators - it is fed
  straight to ``_validate_param_types`` and ``_validate_param_ranges``.

Two mistakes this catches that nothing else does, because both are invisible through
the GUI - the settings dialog reads values with ``.get("Value")`` and coerces each one
through its declared ``Type`` before you ever see it:

* **Omitting ``Value``** for a parameter the user must fill in. Write
  ``"Value": None`` explicitly. Leaving the key out raises a bare
  ``KeyError: 'Value'`` from the validator instead of a message naming your
  parameter, and it breaks any script that drives your plugin without the GUI.
* **An ``int`` default on a ``float`` parameter** - ``{"Type": float, "Value": 500}``.
  The validator uses ``isinstance``, under which ``isinstance(500, float)`` is
  ``False``, so your plugin rejects its own default. Write ``500.0``.

.. code-block:: bash

   pytest tests/unit/plugins/test_settings_schema.py

.. _plugin_conformance_testing:

Behavioural Conformance Testing
--------------------------------

Compliance and schema checking are both static: they never run your algorithm. A
plugin can satisfy each of them completely and still fail on the first real event.

``tests/unit/plugins/conformance/`` closes that gap. It builds your plugin the way the
application does - real settings, a real parent plugin, a real file - drives it over
synthetic data from ``tests/synthetic_data/``, and checks it behaves like a
well-formed member of its family. All eight families are covered, each with checks
written for what that family's output is actually used for:

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - Family
     - What conformance asks of it
   * - ``MetaReader``
     - Agrees with the recording about channels, sample rate and length; ``load_data``
       recovers the planted baseline and event depth in picoamps, not just a plausible
       shape; ``get_raw_dtype()`` resolves to a real dtype and the raw-data path returns
       the same sample count as the normal one.
   * - ``MetaFilter``
     - Shape and dtype preserved, output finite, the data actually changed but the
       blockage still detectable, and ``get_callable_filter()`` agreeing with
       ``filter_data()``.
   * - ``MetaEventFinder``
     - Locates exactly the planted events - neither missing any nor reporting noise -
       with boundaries ordered, in-bounds and non-overlapping, landing on the
       plantings, and ``get_single_event_data()`` carrying the documented keys.
   * - ``MetaEventFitter``
     - Fits every planted event rather than silently rejecting them all, and every
       metadata column it produces is declared in ``get_event_metadata_types()``
       **and** ``get_event_metadata_units()`` so the database writer has a type for
       it. Also ``get_single_event_metadata()`` returning usable arrays.
   * - ``MetaEventLoader``
     - Agrees with the database about channels, event count and sample rate, and every
       loaded event carries the exact keys ``get_event_generator``'s docstring
       specifies, with padding that leaves room for a blockage.
   * - ``MetaWriter``, ``MetaDatabaseWriter``
     - Driven through a real chain, then the output is checked for SQLite integrity,
       the expected row count, and - the part that matters - being readable back by
       the matching loader.
   * - ``MetaDatabaseLoader``
     - Reports its experiments, channels and per-channel event counts correctly, can
       type every column it lists, and discriminates a valid filter query from an
       invalid one.

Every family is also asked that ``reset_channel`` and ``close_resources`` are safe
after use, including twice; the writers additionally have to release their output file,
which on Windows is a genuine handle-leak check because an open handle blocks
``os.unlink``.

Like the compliance test, it is parametrised over *discovered* classes, so your plugin
is covered the moment you drop the file in. The suite cannot guess valid settings on
its own - ``Options`` on a file parameter is a dialog filter glob rather than a list of
values, most numeric parameters declare no ``Max`` to interpolate against, and a
parameter naming a parent plugin needs a live instance - so whether *you* need to add
anything depends on which family your plugin belongs to:

* **``MetaFilter``, ``MetaEventFinder``, ``MetaEventFitter``: yes, always.** Each of
  these is looked up by class name in a dict in ``_recipes.py``
  (``FILTER_SETTINGS``, ``EVENT_FINDER_SETTINGS``, ``EVENT_FITTER_SETTINGS``).
  A new subclass with no entry fails immediately with
  ``KeyError: No conformance recipe for YourPlugin. Add one to ...`` - add one entry
  covering just the parameters your plugin adds beyond its base.
* **``MetaWriter``, ``MetaDatabaseWriter``, ``MetaDatabaseLoader``, ``MetaEventLoader``:
  usually nothing.** These build generically from the file parameter every plugin in
  the family already has, plus (for the two writers) the four experiment-metadata
  parameters every writer shares. If your plugin needs nothing beyond that, it is
  covered with zero recipe work. If it declares an extra required parameter with no
  default, you will see
  ``ValueError: YourPlugin's conformance recipe leaves ['Your Param'] unset`` -
  extend that family's override in ``_recipes.py`` to cover it.
* **``MetaReader``: always, and it is the one real piece of work.** A reader's
  "recipe" is not settings - it is a synthetic file in its actual on-disk format,
  since that is the entire thing a reader varies over. Every existing format lives
  under ``tests/synthetic_data/`` (``synthetic_chimera.py``,
  ``synthetic_chimera_vc100.py``, ``synthetic_binary.py``, ``synthetic_abf2.py``),
  each a subclass of ``BaseSyntheticRecordingWriter`` that only has to implement
  ``_write()``, and each derived directly from the real parsing code rather than
  guessed - see each module's docstring for that derivation. A new reader for an
  existing format needs nothing; a new reader for a new format needs a new writer
  module and an entry in ``READER_DATASET_BUILDERS`` in ``_recipes.py``, which fails
  the same way the other families do if missing.

The recipe values themselves are deliberately kept in test code rather than on the
plugin class. They are only meaningful against the specific synthetic signal the
fixtures build (2000 pA baseline, 15 pA noise, -400 pA events) - a value like
``Threshold: 200.0`` is a statement about that fixture, not about your plugin, and it
would need retuning the moment the fixture's noise or amplitude changed. Keeping every
family's values in one file also made two of the three unit traps below easy to
spot - they show up as one outlying line next to its siblings, which they would not if
scattered across plugin files.

.. code-block:: bash

   pytest -m conformance

.. note::

   One gap remains, limited by a synthetic fixture rather than by the harness.
   ``tests/synthetic_data`` plants flat rectangular blockages, which suits step- and
   level-based fitters but gives a peak-based one nothing to find, so ``PeakFinder``
   and ``Basic_PeakFinder`` are skipped with that reason recorded.

.. tip::

   Watch the units. Two plugins in this codebase declare a parameter in sigma where
   their siblings use picoamps - ``ThresholdBlockageFinder``'s ``Threshold`` and
   ``ClassicCUSUM``'s ``Step Size`` - so a recipe value copied from a sibling silently
   detects nothing. Read the parameter's ``Units`` entry rather than the sibling's
   number. Declaring ``Units`` on your own parameters is what makes this checkable.

.. tip::

   If you're implementing a new ``MetaReader``, don't try to assert
   ``load_data(raw_data=True).dtype == get_raw_dtype()``. It looks like the obvious
   check, but ``MetaReader.load_data`` itself finishes the raw-data branch with
   ``.astype(self.get_raw_dtype())`` right before returning, so that equality holds by
   construction for every reader - it would pass even if your ``_set_raw_dtype()``
   declared something with no relationship to the file's actual on-disk type. What
   conformance checks instead is that ``get_raw_dtype()`` resolves to a real, usable
   dtype and that the raw-data call returns the same number of samples as the normal
   one - the parts that genuinely can go wrong per plugin.

.. _pre_pr_checklist:

Pre-Pull-Request Compliance Checklist
---------------------------------------

.. important::

   This is the section to bookmark. Before opening or updating a pull request —
   especially one adding a new data plugin or frontend plugin family — walk through
   these steps in order. They mirror exactly what CI will check, so a clean run here
   means CI should pass too, and a maintainer won't send your PR back with something
   you could have caught yourself in thirty seconds.

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

☐ **3. If you added or modified a plugin (or a ``Meta*`` base class), run the three
plugin gates.**

.. code-block:: bash

   pytest tests/unit/plugins

That covers all three: interface compliance, settings-schema consistency, and
behavioural conformance. See :ref:`plugin_compliance_testing`,
:ref:`plugin_settings_schema_testing` and :ref:`plugin_conformance_testing` above for
what each one actually checks. A new filter, event finder or event fitter needs a
settings recipe added to ``tests/unit/plugins/conformance/_recipes.py`` - conformance
fails with a message telling you exactly where; the other plugin families usually need
nothing added. See :ref:`plugin_conformance_testing` above for the full breakdown.

☐ **4. Run the test suite** — the same suite continuous integration runs on every
branch push:

.. code-block:: bash

   pytest

There is no subset and no marker filter, at under 10 minutes, e2e tests are worth their cost. CI runs the whole suite everywhere, e2e
tests included. 

For per-marker counts and mean
durations, run ``pytest --marker-stats``.

☐ **5. Update the changelog.**

Add a short, plain-language entry to ``changelog.md`` describing what changed, under
the appropriate existing heading.

.. warning::

   **If you are contributing from a fork** (the typical path for an external/
   community contribution), steps 1–4 above must be completed *before you push*.
   Fork-originated pull requests run in a restricted, read-only CI workflow that
   performs strict validation and the full test suite — it deliberately cannot
   auto-fix formatting or push corrections back to your branch, for security reasons.
   If you skip step 1 or 2 locally, CI will simply fail on something a maintainer has
   no way to fix for you, and you'll need to push a follow-up commit anyway.

Once all five boxes are checked, you're ready to open (or re-request review on) your
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
- Before opening a pull request, work through :ref:`pre_pr_checklist` in full
