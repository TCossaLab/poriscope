Post-merge Automation
=====================

Poriscope uses a **post-merge Git hook** that runs after a successful ``git pull`` or
``git merge`` and keeps the local development environment in step with the repository.

.. important::

   The hook is triggered only by merges run with the system Git command line. Merges and
   pulls made through GitHub Desktop do **not** trigger it; run it by hand instead, as
   described at the end of this page.

How It Works
------------

The installed hook, ``.git/hooks/post-merge``, is a launcher that picks a Python
interpreter (see below) and runs ``scripts/hooks/post-merge.py``. That script changes to
the repository root and runs each sub-hook in ``scripts/hooks/`` in turn, stopping at the
first one that fails, so a failure is reported rather than leaving a half-updated
environment silently. Fix the cause and re-run it by hand (see the end of this page).


Post-merge Sub-hooks
--------------------

Updating Python Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If ``requirements.txt`` changed in the merge, the hook runs
``pip install -r requirements.txt``; otherwise it skips this step.


Regenerating Documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^

After every merge, the hook:

- Removes previous Sphinx build artifacts
- Regenerates autodoc ``.rst`` files. Each generator clears its own output directory
  first, so a page for a module that has since been deleted is pruned rather than left
  behind as an orphan document that would fail the ``-W`` build below. Everything under
  ``docs/source/autodoc/`` is generated and gitignored — do not hand-edit it, and do not
  expect anything you put there to survive a run
- Builds the HTML documentation using Sphinx, with ``-W --keep-going`` so warnings are
  errors and all of them are reported in one pass
- Opens the generated documentation in a web browser

.. note::

   The ``-W`` flag matches the **Docs Render Check** workflow that runs on every pull
   request, so a rendering problem introduced by a merge surfaces here rather than
   waiting for CI. If the hook fails at this step, the docs genuinely do not build —
   see :ref:`docs_render_check` for how to reproduce and fix it.


The Wavelet Native Library
^^^^^^^^^^^^^^^^^^^^^^^^^^

The hook **does not build the wavelet library**. The libraries are built by CI instead and committed under
``poriscope/cdlls/wavelet/dist/``, so a checkout always has them:

- ``wavelet.dll`` for Windows and ``wavelet.so`` for Linux, built by the
  **Build Wavelet** workflow whenever the C source or its ``Makefile`` changes on
  ``develop``. The DLL is linked without timestamps, so rebuilding unchanged source
  produces the same bytes and commits nothing.
- **No macOS library is shipped.** On macOS, build one with ``make dylib`` in
  ``poriscope/cdlls/wavelet/`` and either leave it in ``dist/`` or set
  ``PORISCOPE_WAVELET_PATH`` to the file.

To rebuild by hand after changing the C source, run ``python scripts/build_wavelet.py``,
which builds whichever library the current platform can.


Which Python the Hook Uses
--------------------------

The installed hook is a ``/bin/sh`` launcher that tries ``python3``, then ``python``, then
``py -3``, and uses the first one that can run ``import poriscope.exposed``. Every sub-hook
inherits that choice through ``sys.executable``.

Two weaker checks are not enough. A candidate that merely starts may be the wrong Python:
under Git Bash with MSYS2 installed, ``python3`` resolves to MSYS2's interpreter, which has
none of the project's dependencies. ``import poriscope`` is not enough either, because
``poriscope/__init__.py`` deliberately swallows a failed ``from .exposed import *`` so that a
half-installed dependency set cannot break ``pip install``.

If no candidate passes, the hook prints what it skipped and exits without running anything.
Install the project with ``pip install -e ".[dev,docs]"`` and re-run it by hand.


Installing and Re-running the Hook
----------------------------------

``python scripts/setup_hooks.py`` copies the launcher into ``.git/hooks/`` and marks it
executable (see :doc:`developer_setup`). Git hooks are local to each clone, so every
developer runs it once. The documentation rebuild can take several minutes.

To re-run everything the hook does - after merging through GitHub Desktop, or after fixing
whatever made a step fail - run, from the repository root:

.. code-block:: bash

   python scripts/hooks/post-merge.py

It is safe to run repeatedly. Each sub-hook in ``scripts/hooks/`` can also be run on its own.
