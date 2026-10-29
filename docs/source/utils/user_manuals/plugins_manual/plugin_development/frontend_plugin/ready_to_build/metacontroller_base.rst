MetaController as a Base Class
==============================

:ref:`MetaController` is the abstract base class that manages one view (:ref:`MetaView`) and one model (:ref:`MetaModel`) — it’s the glue that connects the two.
It’s responsible for handling user interactions, coordinating backend logic, relaying signals, and maintaining action history for each plugin tab.

This controller class does a lot behind the scenes so you can focus on your plugin’s behavior rather than reinventing core logic.

What You Get by Inheriting MetaController
-----------------------------------------

**Auto-wired connections**

As soon as you subclass and instantiate a :ref:`MetaController`, the following happens:

- A Controller slot starts a background generator with ``self.model.run_generators(key)``; the View asks the Controller rather than signalling the Model (the ``run_generators`` signal on ``MetaView`` was removed in 2.0.0)
- Signals from both the view and model are routed to log output and progress bars
- The controller listens for user commands to kill workers or save/export data
- Plugin-state changes, status messages and create/edit/delete requests are relayed to the app shell as typed signals

**Signal relay system**

No need to manually handle cross-plugin communication — :ref:`MetaController` takes care of:

- Forwarding the live data plugin instances to the Model, so a slot reaches a plugin with ``self.model.call(...)``, and typed signals for asking the application to create, edit or delete one
- Returning the plugin's result directly from ``call()`` - there is no return function to route
- Updating the main display with log messages via ``add_text_to_display``

**Action history tracking**

- Built-in support for tracking user actions per tab: decorate a method with
  ``@register_action("name")`` and each call is recorded as
  ``{"action": name, "args": ..., "kwargs": ...}``, so the method can be renamed or moved
  without breaking a saved history. Name each action once per tab
- Every value is saved under its parameter name in ``kwargs``, defaults included, however the
  call passed it, so a saved file says what each value is. Keep a recorded method's parameters
  nameable: a method with ``*args`` or a positional-only parameter is saved as it was called.
  Renaming a parameter of a recorded method stops older files from replaying that action: those
  entries are reported and skipped
- A method that can do nothing - refused, or with nothing to show - opts out of recording with
  ``@register_action("name", skip_on_false=True)`` and returns ``False`` when it did nothing. That
  call is not recorded: recording adds one entry per call to the tab's history, so a call that did
  nothing can never stand in for an earlier call that succeeded. Only Undo and
  ``discard_last_tab_action`` remove entries
- Replay goes through the tab's registry of declared actions, ``MetaController.action_registry``:
  a name that is not declared, an entry from an older file, or one whose saved values no longer
  fit its action's parameters, is reported on the status panel and not called
- Can save and reload these actions from a JSON file
- Undo logic included (with safety checks and filtering): Undo replays the history from
  the last reset onward, and ``discard_last_tab_action`` drops a record without
  replaying anything, for an action that was refused and changed nothing
- A recorded action must be a pure function of its recorded arguments, so put anything
  it reads from the widgets - a selection, say - into its parameters before calling it,
  as ``MetaSubsetTabView._record_selection`` does. A replay refuses a read of a controls panel
  (``ReplayWidgetReadError``), and a static test fails a declared action that reads a widget or
  takes plotted data; see :ref:`recorded_actions_read_no_widgets`

**Session state**

- ``get_session_state()`` / ``restore_session_state()`` let a tab opt in to persisting
  state that MainController has no other way to see — the default implementations do
  nothing
- Override both if your tab keeps state entirely on the view (as ``MetaSubsetTabController`` does
  for the Metadata and Protein tabs' subset filter lists): return whatever needs to survive
  a save from ``get_session_state()``, and apply it back in ``restore_session_state()``
- MainController calls these automatically on every open tab whenever it writes session
  history to disk, and again on a freshly-restored tab right after Load/Restore Session;
  you never call them yourself

**Utility methods already set up**

- ``call(metaclass, key, method, *args, **kwargs)`` to run a method on a data plugin and
  get its result back, raising where it fails rather than logging somewhere else. This is
  the whole plugin-facing API a Controller gets; ``MetaModel.call`` is the same method for
  the Model's use, and neither layer should reach a plugin any other way
- ``export_plot_data()`` to save cached data as a CSV
- ``update_plot_data()`` to push processed data to the view
- ``set_generator()`` to forward generators from controller to model
- ``handle_kill_worker()`` and ``handle_kill_all_workers()`` to gracefully stop
  long-running operations

What You Need to Implement
--------------------------

Only two methods are abstract, and both are called automatically during setup.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaController` section of this manual — it walks through each method’s purpose and parameters.
