.. _getting_started_general_user:

Getting Started
===============

Welcome to Poriscope! This section helps you get up and running with the application.

Alright, ready to dive in? Here’s everything you need to get Poriscope installed and running smoothly.

Prerequisites
-------------

Before installing Poriscope, make sure you have the following installed:

1. **Git**

   Check by running::

      git --version

   If Git is not installed, download it here: https://git-scm.com/downloads

2. **Python 3.12.10**

   Required version. Check by running::

      python --version

   If not installed, download it here: https://www.python.org/downloads/release/python-31210/

   .. important::

      During installation, **make sure to check** the box that says **"Add Python to PATH"**.

   .. note::

      **Conda is not supported.** You can make it work, but you're on your own.  
      Poriscope is built for standard ``pip`` environments.

3. **MSYS2 (Optional)**

   Required **only if you need to compile the Wavelet DLL manually**.

   - Download and install from: https://www.msys2.org/

   To check if you already have a compatible build tool installed::

      mingw32-make --version


Installing the Stable Version
-----------------------------

To install the **latest stable version** (recommended for general users — **does not track future updates unless reinstalled manually**):

.. code-block:: bash

   python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@main"

Launching Poriscope
-------------------

Once everything is installed, run the application using:

From **any terminal**::

   poriscope

Or from the local repo directly::

   cd app
   python main_app.py

If the command is not found, make sure your Python environment's ``Scripts/``
(Windows) or ``bin/`` (Linux/macOS) folder is added to your system ``PATH``.

.. warning::

   **Installation vs PATH**

   - If you **don’t install** Poriscope (skip ``python -m pip install -e .`` or the GitHub install),
     it won’t be importable and you can’t launch it.
   - If Python is **not on PATH**, only the convenience command ``poriscope`` will fail.
     You can still run ``python -m poriscope`` and import Poriscope in your scripts,
     as long as it’s installed in the **same Python interpreter** you use.

.. tip::

   To keep things in sync, if you have multiple python versions, make sure you always use the same interpreter for install and run.

Documentation
-------------

The official documentation is available at:

   https://tcossalab.github.io/poriscope/

You're all set — time to explore Poriscope!
