.. _quality_control.rst:

Quality Control and Developer Workflow
======================================

Poriscope uses automated **quality control checks** to ensure that all contributed code
is consistent, correct, and maintainable.

These checks are enforced through continuous integration (CI) but can also be enforced locally using **Git hooks**.

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

Pre-commit Hooks
----------------

Poriscope uses *pre-commit* to run quality checks **before each commit**.

When committing code (either via the command line or GitHub Desktop), the following hooks
run automatically:

- ``black`` – formats Python code
- ``ruff --fix`` – applies safe lint fixes
- ``mypy`` – validates static typing
- ``check-added-large-files`` – blocks files larger than 123 KB

If **any hook fails**, the commit is **blocked**.

Automatic installation (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In most cases, **pre-commit is installed automatically** when you run the Poriscope
setup script:

.. code-block:: bash

   python scripts/setup_hooks.py

This installs ``pre-commit`` (if needed) and registers all configured Git hooks
for the current repository clone.

Manual installation (fallback)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If the setup script was not run, or if Git hooks were removed or reset, you can
install ``pre-commit`` manually from the repository root:

.. code-block:: bash

   python -m pip install pre-commit
   pre-commit install

This installs the hooks into the ``.git/hooks/`` directory.

Verification
^^^^^^^^^^^^

To verify that pre-commit is active, run:

.. code-block:: bash

   pre-commit run --all-files

If any checks fail, commits will be blocked until the issues are resolved.

What Happens on Commit
----------------------

When a commit is created, the following steps occur automatically:

1. Black reformats Python source files.
2. Ruff applies safe lint fixes.
3. Mypy checks type correctness.
4. Large files are rejected.

If any check fails, the commit is aborted and error output is shown.

Using GitHub Desktop
--------------------

GitHub Desktop enforces Poriscope’s Git hooks when configured to use **System Git**.
If a pre-commit check fails, the commit is blocked and an error message is shown.

Verifying Hook Enforcement
^^^^^^^^^^^^^^^^^^^^^^^^^^

To confirm that pre-commit hooks are active in GitHub Desktop, you can intentionally
introduce a small, temporary issue that violates one of the configured checks
(for example, a type mismatch detected by the type checker).

For example, temporarily add the following function to any tracked Python file:

.. code-block:: python

   def _pre_commit_test() -> int:
       return "not an int"

Attempt to commit the change using GitHub Desktop:

- If the commit is **blocked** and an error is reported, the hooks are working correctly.
- If the commit is **not blocked** , as a first step, re-run the setup script from the repository root:

  .. code-block:: bash

     python scripts/setup_hooks.py

  This will reinstall and refresh both the ``pre-commit`` and ``post-merge`` hooks.

  If the issue persists, you can manually reinstall the pre-commit hooks:

  .. code-block:: bash

     pre-commit uninstall
     pre-commit install

After verification, revert the temporary change before continuing development.


Running Quality Checks Manually
-------------------------------

Run all pre-commit hooks on all files:

.. code-block:: bash

   pre-commit run --all-files

Run individual tools:

.. code-block:: bash

   pre-commit run black
   pre-commit run ruff
   pre-commit run mypy
   pre-commit run check-added-large-files

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

.. note::

   Even if tools such as ``black`` or ``ruff`` are configured to automatically
   apply fixes during the continuous integration (CI) run, the CI job will still
   be marked as **failed** when such fixes are required.

   For this reason, it is strongly recommended to run ``pre-commit`` locally
   before pushing changes to the remote repository. Doing so ensures that all
   formatting and linting issues are resolved upfront, avoids unnecessary CI
   failures, and keeps the development workflow efficient.
