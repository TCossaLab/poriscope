System Architecture
===================
Poriscope is built using a modular MVC (Model-View-Controller) architecture, designed to simplify the integration of new plugins and support scalable development.

Core Components
---------------

:ref:`Mainview`   
Manages the user interface layout, including persistent components like the top and side menus, and the logging console.

:ref:`MainModel`  
Handles the application's shared data and global resources.

:ref:`MainController`   
Acts as the brain of the application, coordinating all logic and interaction between models and views.

.. figure:: /_static/images/MVC_architecture_overview.png
   :alt: MVC architecture overview
   :width: 1000px
   :align: center

   **MVC Architecture Overview** — A visual summary of how the Model, View, and Controller interact in Poriscope.

Overview Pages
~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1

   mainview_overview
   mainmodel_overview
   maincontroller_overview

API Documentation
~~~~~~~~~~~~~~~~~

.. toctree::
   :maxdepth: 1
   
   ../../../../../utils/MainMVC/MainView
   ../../../../../utils/MainMVC/MainModel
   ../../../../../utils/MainMVC/MainController

.. note::

   Additionally, there is a ``DataPluginMVC`` architecture layer that manages plugin integration.
   You don’t need to understand the internal workings of the MainMVC or DataPluginMVC in detail — just know that they exist and handle the behind-the-scenes logic.
   Your plugin will interact with them, but that interaction is **not your responsibility** (seriously — treat it like a black box so you can stay focused on building great functionality).


   