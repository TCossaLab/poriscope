.. _getting_started:

Getting Started
===============

This page sets up a development checkout. To install Poriscope only to use it, see
:ref:`user_installation`.

Prerequisites
-------------

1. **Python >=3.12**, set up as described in :ref:`user_installation`.

2. **Git** (``git --version`` to check): https://git-scm.com/downloads

3. **MSYS2 (Optional)**

   Required **only if you need to compile the Wavelet DLL manually**.

   - Download and install from: https://www.msys2.org/

   To check if you already have a compatible build tool installed::

      mingw32-make --version

Installation
------------

As a developer, install Poriscope in *editable* mode:

.. code-block:: bash

   git clone https://github.com/TCossaLab/poriscope.git
   cd poriscope
   pip install -e ".[dev,docs]"
   python scripts/setup_hooks.py

This allows live code edits without reinstallation. ``[dev]`` adds the test and lint tools
and ``[docs]`` adds Sphinx, which the post-merge hook uses to rebuild the documentation;
``setup_hooks.py`` installs the Git hooks - see :doc:`development_workflow/developer_setup`.

.. note::

   If you have a previous version of Poriscope installed, uninstall it first::

      pip uninstall poriscope

Launch it with ``poriscope``, or ``python -m poriscope.main_app`` from the interpreter
you installed into; see :ref:`user_installation` if the command is not found.
