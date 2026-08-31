.. _user_installation:

User Installation
=================

Prerequisites
-------------

**Python >=3.12.10**

   Required version. Check by running::

      python --version

   If not installed, download it here: https://www.python.org/downloads/

   .. important::

      During installation, **make sure to check** the box that says **"Add Python to PATH"**.
      This is required for the ``poriscope`` command to be available globally/as a convenience command.

   .. note::

      **Conda is not supported.** You can make it work, but you're on your own.
      Poriscope is built for standard ``pip`` environments.

Stable Release (Recommended)
-----------------------------

Poriscope is available on `PyPI <https://pypi.org/project/poriscope/>`_ and can be installed
directly using ``pip``:

.. code-block:: bash

   pip install poriscope

This will automatically install all required dependencies and register the ``poriscope`` command
globally, provided Python has been added to your system ``PATH``.

To upgrade to the latest release:

.. code-block:: bash

   pip install --upgrade poriscope

.. note::

   If you have multiple Python versions installed, use ``pip3.12`` instead of ``pip`` to ensure
   the package is installed under the correct interpreter.

Latest Unreleased Version (Advanced)
-------------------------------------

To install directly from the latest commit on GitHub (does not track future updates unless reinstalled manually):

.. code-block:: bash

   python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@main"

.. note::

   The latest commit on ``main`` should always reflect the latest PyPI release.
   This is an alternative for users who wish to install directly from the repository or 
   to get a bugfix that has not been cut into a release yet.
   To install from a specific branch, replace ``@main`` with the desired branch name.

.. note::

   This installs the package from source but does **not** give you an editable codebase.
   If you want to browse or modify the code locally, refer to :ref:`getting_started`
   for the full developer setup using ``git clone`` and ``pip install -e .``.

Launching Poriscope
-------------------

Once everything is installed, run the application from any terminal:

.. code-block:: bash

   poriscope

.. seealso::

   For details on how to install Poriscope as a developer, including editable mode,
   pre-commit hooks, and working with the codebase, refer to :ref:`getting_started`.