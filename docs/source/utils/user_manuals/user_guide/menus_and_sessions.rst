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
  Reloads the most recently autosaved session.

- **Load Session**  
  Opens a previously saved session JSON file and restores its state. A file that is not a
  saved session - a tab's saved actions, for instance - is refused with an error, and the
  current workspace is left as it was.

- **Save Session**
  Stores the current state — including datasets, filters, readers, writers, and analysis results — into a `.json` file.

- **Reset Session**
  Closes every open analysis tab and removes every configured plugin, returning the workspace to the same clean state as a fresh launch — without restarting Poriscope. Your saved session files are left untouched, so **Restore Session** still brings the workspace back, as long as it is the next thing you do; opening a tab or adding a plugin afterward replaces what Restore would have loaded.

.. image:: /_static/images/jsonFile.png
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
  in every open analysis tab, and stops a tab's replay. Each tab confirms what it stopped in
  the message panel on the right-hand side of the main window, and says so there if it had
  nothing running.

.. _replay_actions:

Replay Actions
--------------

The **Replay Actions** button sits under the message panel. A tab replays its actions one step
at a time - Metadata's **Load Plot Configuration** does - and while it does, its messages are held
back and shown together when it ends, so they do not mix with other tabs' messages. A step that
waits for an event finder or fitter carries on only if the run finishes with results.

If a step fails, a dialog names it and asks:

- **Go back**: the tab is cleared and redrawn as it was before the replay.
- **Keep**: what was replayed stays. **Replay Actions** is then enabled for that tab, and continues
  from the step that failed once you have fixed its cause.

A replay stopped by **Abort Analysis** or a tab's **❌ ALL** button also continues from where it
stopped. The button follows the page showing, and is disabled for a tab with nothing to continue.

Help Menu
---------

.. image:: /_static/images/menus/help_menu.png
   :alt: Help Menu
   :align: center

The *Help* menu has **Help**, which opens the Help Centre - links to the tutorial series, the documentation, issue reporting, the paper and how to cite Poriscope - and **Tutorial**, which opens the guided walkthrough.

