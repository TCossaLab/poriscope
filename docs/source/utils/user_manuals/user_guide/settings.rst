.. _settings:

Settings
========

The **Settings** window holds general preferences, advanced tools, and the application
version and contributors.

.. image:: /_static/images/settings_icon.png
   :alt: Settings Icon Location
   :align: center

To open it, click the **gear icon** at the bottom-left of the side menu, or choose
**File → Settings**.

General Tab
-----------

.. image:: /_static/images/SettingsView-General.png
   :alt: General Settings
   :align: center

Under the **General** section, you can configure the following:

- **Language**:  
  Use the dropdown to select your preferred interface language. (Currently only English is available.)

- **Set Data Server**:  
  Click the **Change Data Server Location** button to choose the folder that file dialogs open in, which is also the default for a plugin's ``Folder`` setting. It starts as your home folder.

- **Set User Plugin Folder**:  
  Click the **Change User Plugin Location** button to specify a custom directory where Poriscope should look for plugins at runtime.

  .. note::

     By default, the **User Plugin Folder** is set to:

     ``%LOCALAPPDATA%\Poriscope\user_plugins``

     Only plugins located in this folder at application startup will be recognized.
     **This folder is not monitored dynamically** — changes made after launch will not be reflected unless the application is restarted.

  .. note::

     A plugin's name is unique across the whole application. If a file in this folder has
     the same name as a plugin that ships with Poriscope, or as another plugin already
     found, it is **not loaded**, and an error at startup names the file that was ignored.
     Rename it to load it.

Advanced Settings Tab
---------------------

.. image:: /_static/images/SettingsView-AdvancedSettings.png
   :alt: Advanced Settings
   :align: center

The **Advanced Settings** section provides power users and developers with the following tools:

- **Logging Level**:
  How much is written to the console and the log file: ``None``, ``Debug``, ``Info``,
  ``Warning`` (the default), ``Error`` or ``Critical``, for the whole application. It does
  not change which problems open a dialog - errors always do, warnings never do. To raise
  the logging of a single plugin, run it from a script; see :ref:`scripting`.

- **Clear Cache**:  
  Click this red button to empty the application log file. Past diagnostic output cannot be recovered.

- **Reset Settings**:  
  Restores the data server location, user plugin folder and logging level to their defaults. Configured plugins and saved sessions are not affected, and a changed plugin folder takes effect at the next start.

About Tab
---------

.. image:: /_static/images/SettingsView-About.png
   :alt: About Tab
   :align: center

The **About** section contains important information about Poriscope:

- **Application Version**:  
  Indicates the current installed version of the software.

- **Developer Information**:  

  - Kyle Briggs  
  - Alejandra Carolina González González
