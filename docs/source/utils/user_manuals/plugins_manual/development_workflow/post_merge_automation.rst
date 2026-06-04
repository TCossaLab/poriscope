Post-merge Automation
=====================

Poriscope uses a **post-merge Git hook** to automatically synchronize the local
development environment after repository updates.

This hook runs **after** a successful ``git pull`` or ``git merge`` and performs
a series of maintenance and setup tasks to keep the developer environment in a
working and up-to-date state.

.. important::

   The post-merge hook is triggered only when merge operations are performed using
   the system Git command line (for example via ``git pull`` or ``git merge``).
   Merge and pull operations initiated through GitHub Desktop do **not** trigger
   this hook.

   However, the post-merge automation can be **run manually at any time**, which is
   the recommended approach when working primarily through GitHub Desktop.
   The steps to run the post-merge tasks manually are described below.

What Is the Post-merge Hook?
----------------------------

The ``post-merge`` hook is a standard Git hook executed automatically after new
changes are merged into the working tree.

In Poriscope, the post-merge hook acts as an **orchestrator** that runs several
project-specific maintenance scripts.

The hook itself lives in:

::

   .git/hooks/post-merge

and delegates work to scripts stored under:

::

   scripts/hooks/


High-level Behavior
-------------------

After a merge or pull, the post-merge hook performs the following actions:

1. Detects the repository root
2. Executes a sequence of post-merge maintenance scripts
3. Aborts immediately if any script fails

This ensures that the local environment is never left in a partially updated
state.


Post-merge Orchestrator
-----------------------

The main post-merge hook script:

- Determines the repository root using ``git rev-parse``
- Changes into the repository root directory
- Executes a predefined list of sub-hooks
- Supports both ``.py`` and ``.sh`` scripts
- Stops execution on the first failure

Each sub-hook is executed sequentially, and failures propagate immediately.


Post-merge Sub-hooks
--------------------

The following post-merge sub-hooks are currently executed.

Updating Python Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If ``requirements.txt`` changed during the merge, dependencies are updated
automatically using ``pip``.

This prevents runtime errors caused by missing or outdated Python packages.

If ``requirements.txt`` was not modified, dependency installation is skipped.


Regenerating Documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^

After a merge, the documentation build directories are cleaned and regenerated.

This process:

- Removes previous Sphinx build artifacts
- Regenerates autodoc ``.rst`` files
- Builds the HTML documentation using Sphinx
- Opens the generated documentation in a web browser

This ensures that documentation always reflects the current codebase.


Building the Wavelet Native Library
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The post-merge hook checks whether a platform-specific wavelet binary already
exists.

If not present, it automatically:

- Detects the operating system
- Verifies required toolchains
- Builds the appropriate shared library:
  - ``.dll`` on Windows
  - ``.so`` on Linux
  - ``.dylib`` on macOS

On Windows, MSYS2 and MinGW are used to build the DLL when available.


Platform-specific Behavior
--------------------------

Windows
^^^^^^^

- Detects MSYS2 installations automatically
- Installs missing toolchains if required
- Uses MinGW to build native extensions
- Ensures the correct Python interpreter is used

Linux and macOS
^^^^^^^^^^^^^^^

- Uses available system compilers
- Builds only supported binary formats
- Skips unavailable targets gracefully


Failure Handling
----------------

If any post-merge sub-hook fails:

- Execution stops immediately
- An error message is displayed
- The developer can fix the issue and re-run the script manually

This prevents silent failures and incomplete setups.


Installing the Post-merge Hook
------------------------------

The post-merge hook is installed automatically by Poriscope’s setup script.

Developers can install or reinstall it manually by running:

.. code-block:: bash

   python scripts/setup_hooks.py

This copies the post-merge hook into ``.git/hooks/`` and marks it as executable.


Important Notes
---------------

- Git hooks are **local** and not version-controlled
- Each developer must install hooks in their own clone
- The post-merge hook is safe to run multiple times
- Long-running tasks (such as native builds) may take several minutes


When to Re-run Manually
-----------------------

Developers may manually re-run post-merge tasks when:

- Toolchains were installed after a failed build
- Documentation generation failed due to missing dependencies
- Environment setup was interrupted or partially completed

Individual post-merge scripts can be executed directly from
``scripts/hooks/`` if only a specific task needs to be re-run.

Alternatively, the full post-merge automation can be executed manually
from the repository root:

.. code-block:: bash

   python .git/hooks/post-merge

This runs the same sequence of tasks as the automatic post-merge hook and
is the recommended approach when using GitHub Desktop or when multiple
post-merge steps need to be refreshed.


Summary
-------

- The post-merge hook runs automatically after merges and pulls
- It keeps dependencies, documentation, and native libraries in sync
- It reduces manual setup and environment drift
- It improves onboarding for new contributors

Developers are encouraged to keep the post-merge hook enabled at all times.
