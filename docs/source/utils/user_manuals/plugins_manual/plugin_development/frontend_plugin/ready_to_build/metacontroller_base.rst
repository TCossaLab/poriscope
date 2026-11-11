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

- Built-in support for tracking user actions per tab: decorate a Controller method with
  ``@register_action("name", kind=...)`` and each call is recorded as
  ``{"action": name, "args": ..., "kwargs": ...}``, so the method can be renamed or moved
  without breaking a saved history. Name each action once per tab. Only Controller methods are
  recorded and replayed: a decorated View method is neither, so a View asks its Controller
  (as ``MetadataView._reset_actions`` asks for ``MetadataController.reset``)
- Every recorded action declares its ``kind``, which says what a restored session keeps of it.
  The declaration lives on the decorator only; nothing of it is saved in the entry:

  - ``result``: a background run of one plugin on one channel, such as Find or Fit. ``key`` names
    its plugin parameter, then its channel parameter, ``key=("eventfinder", "channel")``; a
    newer run with the same values replaces an older one. A result is recorded only once its
    run has **finished**: the click's values are held until ``MetaModel.run_finished`` says the
    run ended, and the plugin is then asked whether the channel holds a finished run
    (``get_eventfinding_status`` or ``get_eventfitting_status``; a run clears its channel as it
    starts, so this answers for the run that just ended). A run that was cancelled, failed or
    found nothing is not recorded, and the status panel says so. It cleared the channel as it
    started, so an earlier run of that plugin and channel, and every ``view`` whose
    ``depends_on`` names it, is removed from the history too
  - ``view``: a drawing that replaces what its figure showed, such as a trace. The newest per
    figure is kept. ``depends_on`` names the parameters whose values are the key of the result
    it draws from, ``depends_on=("eventfinder", "channel")``; a view drawn from a result that was
    run again later is dropped
  - ``additive``: a drawing added to its figure, such as an overlay; kept until a later reset or
    view on that figure
  - ``reset``: clears its figure, and drops everything earlier on it

  Every kind but ``result`` names its figure, either ``figure="plot"`` or, when a parameter
  says which, ``figure_from="mode"``. Figure names only need to agree within one tab. A
  declaration with a wrong field or a name that is not a parameter fails when the module is
  imported, with a message naming the action
- ``plugin_args`` names every parameter whose value is a data plugin's key,
  ``plugin_args=("reader", "data_filter")``, so that deleting, renaming or editing a plugin finds
  the entries that name it. A test fails any recorded action whose ``reader``, ``eventfinder``,
  ``eventfitter``, ``loader`` or ``data_filter`` parameter is not listed
- Every value is saved under its parameter name in ``kwargs``, defaults included, however the
  call passed it, so a saved file says what each value is. Keep a recorded method's parameters
  nameable: a method with ``*args`` or a positional-only parameter is saved as it was called.
  Renaming a parameter of a recorded method stops older files from replaying that action: those
  entries are reported and skipped
- A method that can do nothing - refused, or with nothing to show - opts out of recording with
  ``@register_action("name", skip_on_false=True)`` and returns ``False`` when it did nothing. That
  call is not recorded, so it never replaces a good run in the saved actions, which keep only the
  latest run of each plugin and channel. The live history keeps every entry, for Undo; entries leave
  it only through Undo, ``discard_last_tab_action``, a tab's Reset (``set_history_aside``), a
  plugin delete or edit (``rewrite_plugin_entries``), and a Find or Fit rerun that does not finish,
  which removes the earlier run of that plugin and channel
- Replay goes through the tab's registry of declared actions, ``MetaController.action_registry``:
  a name that is not declared, an entry from an older file, or one whose saved values no longer
  fit its action's parameters, is reported on the status panel and not called
- Can save and reload these actions as a plot configuration: ``save_tab_actions(file)`` saves
  ``kept_actions()`` through the Model (``MetaModel.save_plot_configuration``), in a file that
  names its format, version and tab, and ``load_actions_from_json`` reads it back through
  ``MetaModel.read_plot_configuration``, which refuses an earlier, foreign or other tab's file
  whole. A loaded file replays through ``start_replay``, one entry at a time on the event loop
  (``poriscope.utils.replay_sequence``). Each step first shows its recorded values in the panel
  through the View's ``write_back``, which a tab overrides to write its own widgets;
  a ``result`` entry waits for its run to end and carries on only if the run finished with
  results, and the replay stops at the first entry that raises or, for a ``skip_on_false``
  action, returns ``False``. The user is then asked to go back or keep (``MetaView.ask_after_replay_failure``);
  going back calls ``clear_for_replay`` and replays the history from before. Its default clears
  the View's figure (``MetaView.clear_figure``); override it if your tab keeps more, such as a
  result on its Model, and record nothing in it. While a tab replays, its status-panel lines
  are held and shown together when it ends, and ``replay_state_changed`` tells the main window
  whether **Replay Actions** can continue it
- Undo logic included (with safety checks and filtering): Undo replays the history from
  the last reset onward, and ``discard_last_tab_action`` drops a record without
  replaying anything, for an action that was refused and changed nothing. A tab's own
  Reset button can call ``set_history_aside`` to empty the history: Undo straight after
  brings it back, and anything recorded first drops it (Metadata's ``clear_history``)
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
- The tab's recorded actions are saved beside that state, as ``actions``, without going through
  ``get_session_state``: ``kept_actions()`` gives the entries a restore replays. At a load,
  MainController hands the tab its saved actions once, through ``hold_session_actions``; with
  nothing stopped to continue, ``start_replay()`` replays them, and ``replay_available()`` says
  whether **Replay Actions** has anything to do. After a load the main window offers every tab
  whose ``replay_available()`` is True in its restore dialog and starts the ticked ones with
  ``start_replay(restore=True)``; ``history_change_from_restore_replay()`` tells it which history
  changes that replay made, so the session's last tab stays where the user last acted. Deleting, renaming or editing a plugin reaches
  every copy a tab holds through ``rewrite_plugin_entries``, by the parameters each action
  declares in ``plugin_args``

**Utility methods already set up**

- ``call(metaclass, key, method, *args, **kwargs)`` to run a method on a data plugin and
  get its result back, raising where it fails rather than logging somewhere else. This is
  the whole plugin-facing API a Controller gets; ``MetaModel.call`` is the same method for
  the Model's use, and neither layer should reach a plugin any other way
- ``export_plot_data()`` to save cached data as a CSV
- ``update_plot_data()`` to push processed data to the view
- ``set_generator()`` to forward generators from controller to model
- ``handle_kill_worker()`` and ``handle_kill_all_workers()`` to gracefully stop
  long-running operations; the second also stops the tab's replay

What You Need to Implement
--------------------------

Only two methods are abstract, and both are called automatically during setup.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaController` section of this manual — it walks through each method’s purpose and parameters.
