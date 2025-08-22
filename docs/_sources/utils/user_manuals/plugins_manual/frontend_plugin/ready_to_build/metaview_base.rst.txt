MetaView as a Base Class
========================

:ref:`MetaView`   is the abstract base class for any analysis tab's view. It defines the shared structure and functionality all views should have.

What You Get by Inheriting MetaView
-----------------------------------

**Shared UI layout**

You get a built-in plot canvas, a navigation toolbar, and a dedicated control area layout.

**Abstract methods** — You’ll have to implement these yourself:

- ``_init``
- ``_set_control_area``
- ``_reset_actions``
- ``update_plot``
- ``update_available_plugins``

**Reusable features:**

- Built-in support for progress bars
- Caching logic for efficiency
- Signal definitions to connect with your controller
- Helper functions like ``handle_kill_all``, ``_setup_canvas``, and ``_commit_cache``

By default, every time you inherit from :ref:`MetaView` you get a ready-to-use display area right out of the box:


.. image:: /_static/images/MetaView.png
   :alt: MetaView default layout
   :width: 1000px
   :align: center

On top of that, there’s a control area already set up to appear just below the display.
If you want to use it or add your own widgets to it, it’s all ready for you — no extra setup needed.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaModel` section of this manual — it walks through each method’s purpose and parameters.
