Getting Started
===============

Welcome to Poriscope! This section helps you get up and running with the application.

Alright, ready to dive in? Here’s everything you need to get Poriscope installed and running smoothly.

Check Your Prerequisites
------------------------

Before anything else, make sure you have the following installed:

1. **Git** — Check by running:

   .. code-block:: bash

      git --version

   If Git is not installed, visit: https://git-scm.com/downloads

   Then, inside the repo do: 

   .. code-block:: bash

      git init

2. **Python 3.12.10** — Required version. Check by running:

   .. code-block:: bash

      python --version

   If you don’t have Python or it's the wrong version, download it from: https://www.python.org/downloads/release/python-31210/

   .. important::

      When installing Python, **be sure to check the box that says "Add Python to PATH"**.

   .. note::

      We recommend avoiding Conda — Poriscope is built with standard ``pip`` environments in mind. Conda may cause unexpected compatibility issues.


3. **MSYS2** — Required for compiling the Wavelet DLL used by Poriscope.

   - Download and install it from: https://www.msys2.org/

   .. note::

      You can skip installing MSYS2 if you already have a working `mingw32-make` in your system ``PATH``.
   
      To check, open a terminal and run:

      .. code-block:: bash

         mingw32-make --version

Clone the Repository
--------------------

Choose or create the folder where you want Poriscope to live. Right-click inside it and select **Open in Terminal**.

Then run:

.. code-block:: bash

   git clone https://github.com/TCossaLab/data_selection.git

Make sure you're on the correct branch (see the README if unsure).

Set Up Your Python Environment
------------------------------

Install the required Python dependencies:

.. code-block:: bash

   cd data_selection
   pip install -r requirements.txt

Post-Clone Setup
----------------

After cloning the repo and installing Python requirements, run:

.. code-block:: bash

   python scripts/setup_hooks.py

This script sets up Git hooks and other helpful tools.

**Why is this useful?**

- It automatically opens the documentation in your browser after setup.
- Every time you pull new changes, the updated docs will appear — keeping you in sync.
- You can also manually trigger this behavior at any time:

  .. code-block:: bash

     python .git/hooks/post-merge

Launch the Application
----------------------

Once everything is ready:

.. code-block:: bash

   cd app
   python main_app.py

This will launch Poriscope.

That’s it — you’re all set. Now let’s actually build something!
