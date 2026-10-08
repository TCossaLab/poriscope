MetaView as a Base Class
========================

:ref:`MetaView`   is the abstract base class for any analysis tab's view. It defines the shared structure and functionality all views should have.

What You Get by Inheriting MetaView
-----------------------------------

**Shared UI layout**

You get a built-in plot canvas, a navigation toolbar, and a dedicated control area layout.

**Abstract methods** — You’ll have to implement these yourself:

- ``_init``
- ``_reset_actions``
- ``handle_parameter_change``
- ``notify_plugin_state_changed``
- ``update_available_plugins``

``update_plot`` is **not** one of them and is not on ``MetaView`` at all: each tab
declares its own, taking whatever its plot types need, and wires it to its own control
panel. ``notify_plugin_state_changed`` is called whenever any plugin's state changes
elsewhere in the application — new columns committed to a loader's table, say — and a tab
with nothing to react to implements it as ``pass``, which ``MetaEventTabView`` does for
both event tabs.

**Building your control area.** ``_set_control_area`` is *not* abstract. It builds the
control-area layout for you: it calls ``_build_controls()``, connects the four signals
every controls panel carries — ``actionTriggered``, ``add_processed``,
``edit_processed`` and ``delete_processed`` — and places the widget. Three of those four
land on handlers ``MetaView`` already implements; ``actionTriggered`` lands on
``handle_parameter_change``, which is why that one is abstract and you have to write it.
The connection is made while the View is still being constructed, so a tab that omits it
would fail inside ``__init__`` rather than when a button is first pressed — declaring it
abstract is what turns that into a refusal to instantiate the class, naming the method.

So the usual thing to write is ``_build_controls``, returning your ``MetaControls``
subclass:

.. code-block:: python

   def _build_controls(self) -> MyTabControls:
       self.mytabcontrols = MyTabControls()
       return self.mytabcontrols

``_build_controls`` is not abstract either; the default returns an empty panel. If your
tab lays out its own control area rather than using a ``MetaControls`` panel, override
``_set_control_area`` directly and ignore ``_build_controls`` entirely — in that case
nothing connects to ``handle_parameter_change``, and implementing it as ``pass`` is
correct.

**Reusable features:**

- Built-in support for progress bars
- Caching logic for efficiency
- Signal definitions to connect with your controller
- Helper functions like ``handle_kill_all``, ``_setup_canvas``, and ``_commit_cache``

**What does not belong in a View**

Drawing, axes and canvas lifecycle, widget state and file dialogs are the View's. Turning
data into other data is not: ``MetaView`` imports no computation library at all, and a tab
that needs rows filtered, log-scaled, binned or fitted asks its Controller, which asks the
Model — see :doc:`metamodel_base`. The shared filtering and log scaling every plot uses is
``MetaModel.logscale_and_filter_columns``, and a plot's time axis comes from
``MetaModel.time_bases``.

By default, every time you inherit from :ref:`MetaView` you get a ready-to-use display area right out of the box:


.. image:: /_static/images/MetaView.png
   :alt: MetaView default layout
   :width: 1000px
   :align: center

On top of that, there’s a control area already set up to appear just below the display.
If you want to use it or add your own widgets to it, it’s all ready for you — no extra setup needed.

.. note::

   The control area accepts any PySide6 widget — buttons, dropdowns, sliders, etc.
   You can also organize them using layouts, add menus, dialogs, and much more.
   If you're new to PySide6, `pythonguis.com <https://www.pythonguis.com/pyside6/>`_ is a great place to start.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaView` section of this manual — it walks through each method’s purpose and parameters.
