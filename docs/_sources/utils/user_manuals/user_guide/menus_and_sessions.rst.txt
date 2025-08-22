.. _menus_and_sessions:

Menus and Session Management
============================

Poriscope offers built-in session management through the **File** menu. You can save your progress, restore previous work, or reload a saved configuration using `.json` session files.

.. image:: /_static/images/menus/file_menu_save.png
   :alt: File Menu Options
   :align: center

Session Options Overview
------------------------

- **Restore Session**  
  Automatically reloads the last active session when you launch the application.

- **Load Session**  
  Opens a previously saved session JSON file and restores its state.

- **Save Session**  
  Stores the current state — including datasets, filters, readers, writers, and analysis results — into a `.json` file.

.. image:: /_static/images/jsonFIle.png
   :alt: Saving Session as JSON
   :align: center

.. note::

   If the original file paths referenced in the session JSON are no longer valid (e.g., files were moved, renamed, or deleted), the session may not load correctly.

Settings Access
---------------

From the same **File** menu, you can also access:

- **Settings** – Configure general preferences, logging behavior, plugin folders, and more. 

.. seealso::
   For instructions on configuring user preferences and data/plugin directories, refer to :ref:`settings`.

Data Menu
---------

.. image:: /_static/images/menus/data_menu.png
   :alt: Data Menu
   :align: center


The *Data* menu provides quick access to the same loaders as the "+" buttons in the control panels:

- Load Timeseries
- Load Events
- Load Event Database
- Load Writer
- Load Database Writer

Analysis Menu
-------------

.. image:: /_static/images/menus/analysis_menu.png
   :alt: Analysis Menu
   :align: center

The *Analysis* menu allows you to:

- Add filters, event finders, fitters, and new analysis tabs
- **Abort Analysis**: forcibly stops any active processes (identified by active progress bars)

Help Menu
---------

.. image:: /_static/images/menus/help_menu.png
   :alt: Help Menu
   :align: center

The *Help* menu includes a link to the tutorial. Note that the help system is **not yet implemented**.

