.. _user_installation:

.. _getting_started_general_user:

Installation
============

Prerequisites
-------------

**Python >=3.12**

   Required version. Check by running::

      python --version

   If not installed, download it here: https://www.python.org/downloads/

   .. important::

      During installation, **make sure to check** the box that says **"Add Python to PATH"**.
      This is required for the ``poriscope`` command to be available globally/as a convenience command.

   .. note::

      **Conda is not supported.** You can make it work, but you're on your own.
      Poriscope is built for standard ``pip`` environments.

.. _stable_release:

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

To get changes that have not been released yet, install the ``develop`` branch from GitHub
(this needs `Git <https://git-scm.com/downloads>`_, and does not track later updates unless
you run it again):

.. code-block:: bash

   python -m pip install -U "git+https://github.com/TCossaLab/poriscope.git@develop"

``main`` holds the latest release, the same code as PyPI; replace ``@develop`` with any
other branch name to install that branch. This does **not** give you an editable codebase:
to browse or modify the code, follow the developer setup in :ref:`getting_started`.

Launching Poriscope
-------------------

Once everything is installed, run the application from any terminal:

.. code-block:: bash

   poriscope

If the command is not found, your Python environment's ``Scripts/`` (Windows) or ``bin/``
(Linux/macOS) folder is not on your ``PATH``. You can still start Poriscope, and import it
in your own scripts, with the same interpreter you installed it into:

.. code-block:: bash

   python -m poriscope.main_app