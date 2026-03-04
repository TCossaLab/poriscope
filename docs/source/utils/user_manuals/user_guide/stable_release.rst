.. _stable_release:

Stable Release Installation
===========================

Prerequisites
-------------

**Python >=3.12.10**

   Required version. Check by running::

      python --version

   If not installed, download it here: https://www.python.org/downloads/release/python-31210/

   .. important::

      During installation, **make sure to check** the box that says **"Add Python to PATH"**.
      This is required for the ``poriscope`` command to be available globally/as a covenience command.

   .. note::

      **Conda is not supported.** You can make it work, but you're on your own.
      Poriscope is built for standard ``pip`` environments.

Installation
------------

Poriscope is available on `PyPI <https://pypi.org/project/poriscope/>`_ and can be installed
directly using ``pip``:

.. code-block:: bash

   pip install poriscope

This is the **recommended installation method for regular users**. It will automatically
install all required dependencies and register the ``poriscope`` command globally,
provided Python has been added to your system ``PATH``.

To upgrade to the latest release:

.. code-block:: bash

   pip install --upgrade poriscope

.. note::

   If you have multiple Python versions installed, use ``pip3.12`` instead of ``pip`` to ensure
   the package is installed under the correct interpreter.

.. seealso::

   For details on how to install poriscope as a developer see: :doc:`getting_started`.