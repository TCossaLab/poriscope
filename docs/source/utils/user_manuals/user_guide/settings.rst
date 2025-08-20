.. _settings:

Settings Tab
============

The **Settings Tab** allows users to customize their experience in Poriscope. It provides access to general preferences, advanced configurations, and information about the application version and contributors.

.. image:: /_static/images/settings_icon.png
   :alt: Settings Icon Location
   :align: center

To open the settings, click the **gear icon** located on the bottom-left corner of the side menu.

General Tab
-----------

.. image:: /_static/images/SettingsView-General.png
   :alt: General Settings
   :align: center

Under the **General** section, you can configure the following:

- **Language**:  
  Use the dropdown to select your preferred interface language. (Currently only English is available.)

- **Set Data Server**:  
  Click the “Change Data Server Location” button to specify where Poriscope should look for your data files.

- **Set User Plugin Folder**:  
  Click the **Change User Plugin Location** button to specify a custom directory where Poriscope should look for plugins at runtime.

  .. note::

     By default, the **User Plugin Folder** is set to:

     ``%LOCALAPPDATA%\Poriscope\user_plugins``

     Only plugins located in this folder at application startup will be recognized.  
     **This folder is not monitored dynamically** — changes made after launch will not be reflected unless the application is restarted.

Advanced Settings Tab
---------------------

.. image:: /_static/images/SettingsView-AdvancedSettings.png
   :alt: Advanced Settings
   :align: center

The **Advanced Settings** section provides power users and developers with the following tools:

- **Logging Level**:  
  Adjust the verbosity of internal logging. Use the dropdown to select a level such as `None`, `Info`, `Debug`, etc.

- **Clear Cache**:  
  Click this red button to remove temporary files and cached analysis results.

- **Reset Settings**:  
  Click this to revert all settings back to factory defaults. Use this if you encounter configuration issues or want to start fresh.

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

----

.. tip::

   You can access the Settings at any time from the sidebar. Adjusting logging or clearing cache can help resolve runtime issues during plugin development.
