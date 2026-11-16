.. _CallingAPlugin:

Calling Plugins and Emitting Signals
====================================

A tab's parts talk in two ways, and the rule is whether you need an answer:

- **Asking a question** - a sample rate, an event count, some data: **call the plugin**,
  and use the return value. A failure raises on that line.
- **Announcing something** - a status line, a plugin's state changed, a request to create
  a plugin: **emit a signal** and carry on. Nobody hands you a result.

If you find yourself emitting a signal and then reading something back, you want a call.

Calling a data plugin
---------------------

An analysis tab reaches a data plugin through ``call()`` on its Model:

.. code-block:: python

   samplerate = self.model.call("MetaReader", reader_key, "get_samplerate")

That is the whole plugin-facing API a tab gets. It resolves the instance, calls the
method, and returns whatever the method returns. A failure raises where it happened.

``call()`` lives on ``MetaModel`` only. Commands arrive at the Controller and computation
belongs in the Model, so a Controller slot answering a View intent calls
``self.model.call(...)``. ``MetaController`` only forwards the instances it is handed to
its Model; it keeps no copy and has no ``call()`` of its own.

The plugin instances are **pushed** to every tab as they are created, renamed,
reconfigured and destroyed, so nothing is resolved lazily and nothing goes stale.

Reporting a failure
-------------------

``call()`` raises, so the caller decides. The convention in the shipped tabs is to
log the exception and put one sentence on the status panel:

.. code-block:: python

   try:
       rows = self.model.call("MetaDatabaseLoader", loader, "load_metadata", columns)
   except Exception as e:
       self.logger.error(f"Failed to load the subset: {e!r}")
       self.add_text_to_display.emit(
           f"Could not load this subset from {loader}: {e}", self.__class__.__name__
       )
       return

Two rules go with that, both learned from defects:

- **Set the View's answers only once the whole chain has succeeded.** A View that
  clears its answer before asking can then tell "this did not run" from "this ran and
  found nothing".
- **Stop on a scope that did not resolve**, rather than dropping it from the query. An
  identifier that is unique only within an experiment and channel will match some
  other channel's row if the scope is quietly widened.

Arguments and return values
---------------------------

``call()`` takes the method's arguments spread, exactly as you would pass them to the
method itself, and hands back its return value whole:

.. code-block:: python

   data = self.model.call("MetaReader", key, "load_data", start, length, channel)

   query, debug = self.model.call(
       "MetaDatabaseLoader", loader, "construct_event_data_query", conditions, scope
   )

``call()`` is declared ``-> Any``, so no type checker will notice a 2-tuple bound to one
name. **Read the target's real signature before writing the call**, and write any test's
expectation from that signature rather than from the call you just wrote - a mocked
model accepts any shape, so a test written the other way round pins the bug.

Emitting a signal
-----------------

Genuine notifications are ordinary typed Qt signals, because nobody is waiting for a
value:

.. code-block:: python

   self.add_text_to_display.emit("Loaded 4,812 events", self.__class__.__name__)

- ``add_text_to_display`` - put a line on the status panel
- ``plugin_state_changed`` - tell the app a plugin's state changed
- ``update_progressbar`` - report progress from a worker
- ``run_finished`` - a plugin's run on a channel has ended

A tab's own **intent** signals are announcements too: a View emits a typed intent, and
the Controller's slot makes the call and hands the result back through a setter on the
View. That keeps the widget free of plugin keys and SQL. :ref:`SimpleCalc` shows the
whole path.

.. _DataPluginControllerSignal:

Creating, editing and deleting a data plugin
--------------------------------------------

A tab asks the application to manage a data plugin with one of three typed signals, each
carrying the metaclass and the plugin's key (the subclass, for ``create_plugin``):

.. code-block:: python

   self.create_plugin.emit(metaclass, subclass)   # add a new plugin
   self.edit_plugin.emit(metaclass, key)          # open its settings dialog
   self.delete_plugin.emit(metaclass, key)        # remove it

They are declared on ``MetaView`` and relayed by ``MetaController`` to ``MainController``,
which connects each one directly to the matching ``DataPluginController`` method. A tab
emits; it does not name a method or supply a callback. The plus, pencil and trash buttons
``MetaControls`` builds beside a plugin combobox already emit them.

.. _GlobalSignal:

Removed in 2.0.0: ``global_signal`` and ``data_plugin_controller_signal``
--------------------------------------------------------------------------

Before 2.0.0 a tab asked a data plugin a question by emitting ``global_signal`` with the
plugin, the method, a tuple of arguments and the name of a callback, and read the answer
back from an attribute the callback set. ``data_plugin_controller_signal`` did the same for
creating, editing and deleting plugins. Both are gone. If you are porting a tab that uses
them:

- an emit with a callback becomes a ``call()`` whose return value you use directly, with
  the arguments spread rather than tupled;
- an emit without a callback becomes a direct call, or for creating, editing and
  deleting plugins one of the three typed signals above.
