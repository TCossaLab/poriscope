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
- **Mypy** – static type checking
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
   pre-commit run check-added-large-files

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

   ``pydoclint`` does **not** require every function to have a docstring, and does
   **not** require type hints in every function signature — Poriscope's plugin code
   base has a lot of legacy functions without full type annotations, and that's
   currently expected. It only holds a docstring accountable *if one already exists*.
   If you didn't write a docstring, ``pydoclint`` has nothing to check.

Running it locally
^^^^^^^^^^^^^^^^^^^

``pre-commit run --all-files`` already runs ``pydoclint`` on your behalf, so most
contributors will meet it there rather than by invoking it directly. If you want to
check just the docstring/signature rules on their own:

.. code-block:: bash

   pydoclint --baseline=.pydoclint-baseline.txt poriscope

.. tip::

   If a result is coded ``DOC108``, don't panic — it means your function's signature
   already has type hints, even though the project's current docstring policy
   doesn't strictly require them there. That's a harmless policy nag, not a real
   defect, and safe to ignore.

Why is there a "baseline" file?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When ``pydoclint`` was first introduced, a large amount of existing code already had
docstring mismatches that predated the tool. Rather than blocking every future commit
on cleaning up the entire history at once, those pre-existing violations were
recorded in ``.pydoclint-baseline.txt`` and are allowed to remain for now. Only *new*
mismatches that you introduce will fail the check.

If your change happens to fix a docstring that was sitting in that baseline, you must
regenerate it — otherwise the baseline keeps "forgiving" a problem that no longer
exists in that exact form, which defeats the point:

.. code-block:: bash

   pydoclint --generate-baseline=True --baseline=.pydoclint-baseline.txt poriscope

Commit the updated ``.pydoclint-baseline.txt`` alongside your fix.

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
above if a pydoclint failure doesn't make sense.

☐ **3. If you added or modified a plugin (or a ``Meta*`` base class), run the plugin
compliance suite.**

.. code-block:: bash

   pytest tests/unit/plugins/test_plugin_compliance.py

See :ref:`plugin_compliance_testing` above for what this actually checks.

☐ **4. Run the fast test suite** — the same subset continuous integration runs on
every branch push:

.. code-block:: bash

   pytest -m "not e2e and not slow"

If you have time, running the **full** suite (``pytest``, no marker filter) locally
before a large or risky change is even better, but step 4 is the minimum expected.

☐ **5. Update the changelog.**

Add a short, plain-language entry to ``changelog.md`` describing what changed, under
the appropriate existing heading.

.. warning::

   **If you are contributing from a fork** (the typical path for an external/
   community contribution), steps 1–4 above must be completed *before you push*.
   Fork-originated pull requests run in a restricted, read-only CI workflow that
   performs strict validation and the fast test suite only — it deliberately cannot
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
- Mypy and pydoclint issues must be resolved manually
- New or modified plugins must also pass ``test_plugin_compliance.py`` — see
  :ref:`plugin_compliance_testing`
- Before opening a pull request, work through :ref:`pre_pr_checklist` in full
