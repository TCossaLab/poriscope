Developer Setup and Hook Installation
=====================================

Poriscope provides a helper script to install and maintain local Git hooks used for
quality control and post-merge automation.

This setup is intended for Poriscope users who want to become contributors or developers.


Running the Setup
-----------------

From a clone of the repository, install the project with its development and
documentation extras, then run the setup script:

.. code-block:: bash

   pip install -e ".[dev,docs]"
   python scripts/setup_hooks.py

``[dev]`` adds the test and lint tools and ``[docs]`` adds Sphinx, which the post-merge
hook uses. The setup script, which is safe to run more than once:

- installs the ``pre-commit`` package if it is missing, and reinstalls its hooks from the
  repository configuration;
- copies the project's post-merge hook into ``.git/hooks/`` and marks it executable;
- sets ``gitflow.prefix.versiontag`` to ``v``, so ``git flow release finish <version>``
  tags the release ``v<version>``.

.. note::

   The release tag prefix matters because the CD workflow
   (``.github/workflows/release.yml``) triggers on tags matching ``v*``. git flow leaves
   ``gitflow.prefix.versiontag`` empty by default, which would tag a release
   ``1.7.0`` rather than ``v1.7.0`` and so miss that trigger. Like git hooks, git config
   is local to each clone, which is why every developer runs the setup script once rather
   than the repository carrying it.


What the Hooks Do
-----------------

- **pre-commit** runs the validation hooks on every commit and blocks the commit if any
  fails; formatting runs only when you ask for it. See :doc:`quality_control`.
- **post-merge** refreshes dependencies when ``requirements.txt`` changes and regenerates
  the documentation after every ``git pull`` or ``git merge``. See
  :doc:`post_merge_automation`.


Using GitHub Desktop
--------------------

GitHub Desktop enforces the pre-commit hooks when configured to use **System Git**: a
failing check blocks the commit and shows its output. To confirm the hooks are active,
temporarily add a type error to any tracked Python file under ``poriscope/``:

.. code-block:: python

   def _pre_commit_test() -> int:
       return "not an int"

If the commit is blocked, the hooks work; if not, re-run the setup script. Revert the
change afterwards.


Troubleshooting
---------------

If hooks do not appear to run:

- Re-run the setup script
- Verify that ``.git/hooks/pre-commit`` and ``.git/hooks/post-merge`` exist
- Confirm that Python is available in your PATH


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
