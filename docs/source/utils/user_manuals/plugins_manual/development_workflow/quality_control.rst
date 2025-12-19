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

The following tools are used in Poriscope:

- **Black** – automatic Python code formatting
- **Ruff** – linting and safe automatic fixes
- **Mypy** – static type checking
- **check-added-large-files** – prevents accidental commits of large files

All tools are managed through the **pre-commit** framework.

Pre-commit Hooks (Validation)
-----------------------------

Poriscope uses *pre-commit* to run **validation checks before each commit**.

When committing code (either via the command line or GitHub Desktop), the following hooks
run automatically:

- ``ruff`` (strict mode) – validates code without modifying files
- ``mypy`` – validates static typing
- ``check-added-large-files`` – blocks files larger than 123 KB

These checks **never modify files**.

If **any hook fails**, the commit is **blocked**.

Automatic Formatting and Auto-fixes
----------------------------------

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

Summary for New Developers
--------------------------

- Pre-commit enforces consistent, high-quality code
- Hooks run automatically on commit
- GitHub Desktop enforces the same rules
- Most formatting and lint issues are auto-fixable
- Mypy errors must be resolved manually


.. important::

   **Contributors submitting pull requests from forks must run validation checks locally
   before pushing.**

   For security reasons, fork-based pull requests do **not** run auto-fix hooks
   (such as ``black`` or ``ruff --fix``) in continuous integration. CI will only run
   strict validation and will fail if formatting or lint issues are present.

   Before opening or updating a fork-based pull request, contributors must run:

   .. code-block:: bash

      pre-commit run --all-files --hook-stage manual

      pre-commit run --all-files


   Then commit the resulting changes before pushing. This ensures that fork pull requests
   pass CI validation without requiring automated fixes.

   If there are changes that cannot be fixed automatically (such as mypy errors),
   these must be resolved manually before pushing.
