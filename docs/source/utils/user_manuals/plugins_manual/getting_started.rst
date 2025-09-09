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

Installation
------------

As a developer, install Poriscope in *editable* mode:

.. code-block:: bash

   git clone https://github.com/TCossaLab/poriscope.git
   cd poriscope
   pip install -e .

This allows live code edits without reinstallation.

.. note::

   If you have a previous version of Poriscope installed, uninstall it first::

      pip uninstall poriscope

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

Documentation
-------------

The official documentation is available at:

   https://tcossalab.github.io/poriscope/

You're all set — time to explore Poriscope!
