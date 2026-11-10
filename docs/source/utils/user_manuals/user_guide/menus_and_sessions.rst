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
  Opens a previously saved session JSON file and restores its state: the plugins first, then
  the analysis tabs. A file that is not a saved session - a tab's saved actions, for instance -
  or one saved by a later version in a format this one cannot read is refused with a message
  saying why, and the current workspace is left as it was.

- **Save Session**
  Stores the current state — the readers, filters, finders, fitters, loaders and writers with
  their settings, each analysis tab's filters, and each tab's recorded actions — into a `.json`
  file. The results themselves are not saved; the actions are what rebuilds them.

Each tab's **recorded actions** are kept in the session file: the plots and runs a restored
session needs to show what you had, without the ones a later run or plot replaced. The
autosave is written whenever a tab's actions change, as well as whenever a plugin changes.
After **Load Session** or **Restore Session**, each tab holds the actions it was saved with,
and **Replay Actions** (below) replays them. Until you replay or work in a tab, the autosave
keeps those actions for it, so a Restore after a crash still offers them; once you do, the
autosave holds what that tab actually ran. A session whose tabs have no saved actions - one
saved before Poriscope 2.1 - says so when it loads.

Deleting a plugin removes the recorded actions that use it. Renaming one without changing its
settings keeps them, under the new name. Editing a setting removes them, together with those
of the plugins built on it, and the message panel says so: they would no longer replay as they
first ran.

Sessions saved by Poriscope 2.1 do not open in 2.0. A 2.0 session opens in 2.1, with its
plugins and filters but no actions; the action history 2.0 kept beside it,
``tab_action_history.json``, cannot be replayed, and the first Restore says so. That Restore
saves the autosave again in 2.1's format, says so, and the note does not appear again; Poriscope
2.0 can then no longer restore that autosave. **Load Session** never rewrites the file you
picked. A plugin cannot be given the name of an analysis tab, such as ``MetadataController``.

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

The **Replay Actions** button sits under the message panel. After **Load Session** or
**Restore Session** it replays the showing tab's saved actions; once they have all replayed it is
disabled for that tab, until **Go back** or another load. A tab replays its actions one step
at a time - Metadata's **Load Plot Configuration** does too - and while it does, its messages are
held back and shown together when it ends, so they do not mix with other tabs' messages. A step
that waits for an event finder or fitter carries on only if the run finishes with results.

If a step fails, a dialog names it and asks the question below. It is the only dialog a
replay opens: an error the step logs - a finder's or fitter's, say - goes to the log file and is
shown in this dialog under "What the step reported", not in a dialog of its own, and what the
step reports is on the message panel.

- **Go back**: the tab is cleared and redrawn as it was before the replay.
- **Keep**: what was replayed stays. **Replay Actions** is then enabled for that tab, and continues
  from the step that failed once you have fixed its cause.

The autosave holds only what a tab actually ran, so after **Keep** or **Go back** on a session's
actions the message panel says which steps it does not have: **Replay Actions** still replays
them while Poriscope stays open, and after a restart loading the session file again brings them
back.

A replay stopped by **Abort Analysis** or a tab's **❌ ALL** button also continues from where it
stopped. The button follows the page showing, and is disabled for a tab with nothing to continue.

Help Menu
---------

.. image:: /_static/images/menus/help_menu.png
   :alt: Help Menu
   :align: center

The *Help* menu has **Help**, which opens the Help Centre - links to the tutorial series, the documentation, issue reporting, the paper and how to cite Poriscope - and **Tutorial**, which opens the guided walkthrough.

