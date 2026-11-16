System Architecture
===================
Poriscope uses the same Model-View-Controller pattern at two levels: once for the
application shell, and again for each analysis tab.

The shell
---------

:ref:`MainView`
   The window itself: the menus, the sidebar, the message panel, and a stack in the centre
   where each analysis tab's View is shown.

:ref:`MainModel`
   The discovered plugin classes, the application configuration and the session files.

:ref:`MainController`
   Starts plugin discovery, opens analysis tabs, and connects each tab's signals to the
   rest of the application.

.. figure:: /_static/images/MVC_architecture_overview.png
   :alt: MVC architecture overview
   :width: 1000px
   :align: center

   **MVC Architecture Overview** - how the shell's Model, View and Controller interact.

.. figure:: /_static/images/MainView.png
   :alt: Main View layout
   :width: 1000px
   :align: center

   **MainView layout** - the top menu, the side menu and the display area.

Live data-plugin instances are held by a second, smaller triad: ``DataPluginController``,
``DataPluginModel`` and ``DataPluginView`` create, validate, rename and delete every data
plugin, whatever its family.

Analysis tabs and data plugins
------------------------------

Each analysis tab is its own Controller, Model and View, built on ``MetaController``,
``MetaModel`` and ``MetaView`` (see :ref:`build_frontend_plugin`). A tab reaches data
plugins only through its Model's ``call()``, over the instances the shell pushes to every
tab, and asks the shell to create, edit or delete one with typed signals (see
:ref:`CallingAPlugin`). A plugin file placed in the right folder is discovered at startup;
nothing in the shell needs editing to add one.

API Documentation
~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   /utils/MainMVC/MainView
   /utils/MainMVC/MainModel
   /utils/MainMVC/MainController
