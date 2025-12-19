Developer Setup and Hook Installation
=====================================

Poriscope provides a helper script to install and maintain local Git hooks used for
quality control and post-merge automation.

This setup is intended for Poriscope users who want to become contributors or developers.


Overview
--------

The setup script performs two key tasks:

1. Installs and activates **pre-commit** hooks for quality control
2. Installs a **post-merge** Git hook that automates environment maintenance

These hooks work together to ensure that:

- Code quality checks run before commits
- Developer environments stay synchronized after pulls and merges


What the Setup Script Does
--------------------------

When executed, the setup script:

- Detects the repository root using ``git rev-parse --show-toplevel``
- Installs the ``pre-commit`` Python package (if missing)
- Uninstalls any existing pre-commit hooks
- Reinstalls pre-commit hooks using the repository configuration
- Copies the project’s post-merge hook into ``.git/hooks/``
- Marks the post-merge hook as executable

The script is safe to run multiple times.


Running the Setup Script
------------------------

From the repository root, run:

.. code-block:: bash

   python scripts/setup_hooks.py

This command installs both the pre-commit and post-merge hooks locally.

.. note::

   Git hooks are local to each clone and are not version-controlled.
   Each developer must run this setup script at least once.


Quality Control via Pre-commit
------------------------------

After installation, the following checks run automatically on every commit:

- **Black** – automatic code formatting
- **Ruff** – linting and safe auto-fixes
- **Mypy** – static type checking
- **check-added-large-files** – prevents committing large files

If any check fails, the commit is blocked.

For full details, see:

:doc:`quality_control`


Post-merge Automation
---------------------

After a successful ``git pull`` or ``git merge``, the post-merge hook runs automatically.

It performs tasks such as:

- Updating Python dependencies when ``requirements.txt`` changes
- Regenerating autodoc and Sphinx documentation
- Building native wavelet libraries when required

For a detailed explanation of this automation, see:

:doc:`post_merge_automation`


Using GitHub Desktop
--------------------

If a pre-commit check fails, GitHub Desktop blocks the commit and displays the error
output.


Troubleshooting
---------------

If hooks do not appear to run:

- Re-run the setup script
- Verify that ``.git/hooks/pre-commit`` and ``.git/hooks/post-merge`` exist
- Confirm that Python is available in your PATH


Summary
-------

- Run the setup script once per clone
- Pre-commit enforces quality before commits
- Post-merge keeps environments synchronized
- Both hooks improve reliability and onboarding

This setup is strongly recommended for all Poriscope developers.


Extra: Disabling Git Hooks
--------------------------

To disable pre-commit hooks locally:

.. code-block:: bash

   pre-commit uninstall

Pre-commit hooks can be re-enabled with:

.. code-block:: bash

   pre-commit install

To disable the post-merge hook, rename or remove the hook file:

.. code-block:: bash

   mv .git/hooks/post-merge .git/hooks/post-merge.disabled

The hook can be restored by reversing this change or by re-running the setup script:

.. code-block:: bash

   python scripts/setup_hooks.py
