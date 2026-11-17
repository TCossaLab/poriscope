MetaController as a Base Class
==============================

:ref:`MetaController` is the abstract base class that manages one view (:ref:`MetaView`) and one model (:ref:`MetaModel`) — it’s the glue that connects the two.
It’s responsible for handling user interactions, coordinating backend logic, relaying signals, and maintaining action history for each plugin tab.

This controller class does a lot behind the scenes so you can focus on your plugin’s behavior rather than reinventing core logic.

What You Get by Inheriting MetaController
-----------------------------------------

**Auto-wired connections**

As soon as you subclass and instantiate a :ref:`MetaController`, the following happens:

- A Controller slot starts a background generator with ``self.model.run_generators(key)``; the View asks the Controller rather than signalling the Model
- Signals from both the view and model are routed to log output and progress bars
- The controller listens for user commands to kill workers or save/export data
- Plugin-state changes, status messages and create/edit/delete requests are relayed to the app shell as typed signals

**Signal relay system**

No need to manually handle cross-plugin communication — :ref:`MetaController` takes care of:

- Forwarding the live data plugin instances to the Model, so a slot reaches a plugin with ``self.model.call(...)`` and uses its return value, and typed signals for asking the application to create, edit or delete one (see :ref:`CallingAPlugin`)
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

  - ``result``: one run of one plugin on one channel, such as a Find or a Fit. ``key`` names
    the two parameters that identify the run: the plugin, then the channel,
    ``key=("eventfinder", "channel")``; a newer run with the same values replaces an older one.
    A replay starts every run it can at the same time, as one click on several channels does,
    so a run must not need the output of another run. A result is recorded only once its
    run has **finished**: the click's values are held until ``MetaModel.run_finished`` says the
    run ended, and the plugin is then asked whether the channel holds a finished run
    (``get_eventfinding_status`` or ``get_eventfitting_status``; a run clears its channel as it
    starts, so this answers for the run that just ended). A run that was cancelled, failed or
    found nothing is not recorded, and the status panel says so. It cleared the channel as it
    started, so an earlier run of that plugin and channel, and every ``view`` whose
    ``depends_on`` names it, is removed from the history too
  - ``view``: a drawing that replaces what its figure showed, such as a trace. The newest per
    figure is kept. A view that shows a run's output names that run in ``depends_on``, with the
    same two parameters, ``depends_on=("eventfinder", "channel")``; any other number of names
    fails at import. With it, a replay draws the view only once that run has finished, and the
    view leaves the history when the run is repeated or its plugin is edited. Without it, a
    replay may draw the view before the run has finished. A view may compute in the background
    before it draws, as
    Conditioning's plot does; a replay waits for it (below)
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
  whole. A loaded file replays through ``start_replay``, on the event loop
  (``poriscope.utils.replay_sequence``). A replay restores what the actions produced, not the
  order they ran in: every ``result`` that nothing earlier holds back is launched at once, and
  waits only for an earlier run of its own key and the views drawn from it; every other entry
  keeps its place among the entries that are not results, and waits for the run its
  ``depends_on`` names. When the replay ends the panel and the history read as in recorded
  order. Each step first shows its recorded values in the panel through the View's
  ``write_back``, which a tab overrides to write its own widgets; a ``result`` counts as
  replayed only if its run finished with results. Any other entry that starts background runs
  waits until each of them has ended,
  then a turn of the event loop more, so the tab has drawn before the next entry or "replay
  done"; it fails if ``background_step_failure()`` then names a reason. The base names none:
  override it when your action's background work can end without its result, and say what is
  missing (``ConditioningController`` returns its "did not finish" line). An entry fails when
  its run does not finish with results, or it raises or, for a ``skip_on_false`` action,
  returns ``False``. Nothing new starts from then on, and the user is asked at once to go back
  or keep (``MetaView.ask_after_replay_failure``), while the runs already going carry on; each
  later failure is asked about in turn. Keeping lets those runs end, and the next
  ``start_replay()`` replays only the entries that did not finish. Going back stops them, then
  calls ``clear_for_replay`` and replays the history from before. Its default clears
  the View's figure (``MetaView.clear_figure``); override it if your tab keeps more, such as a
  result on its Model, and record nothing in it. While a tab replays, its status-panel lines
  are held and shown together when it ends or a step fails, and ``replay_state_changed`` tells
  the main window
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
- Each tab Poriscope ships with has a replay scenario for every declared action in
  ``tests/integration/flows/test_replay_guard_no_gui.py``: the click as the panel sends it, and a
  change to everything the panel holds; the suite fails, naming the action, for one without. A
  tab of your own is not checked there, but a scenario of the same shape is how to test that its
  actions replay

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

- No ``call()`` of its own: a Controller slot reaches a data plugin through its Model,
  ``self.model.call(metaclass, key, method, *args, **kwargs)``, which returns the result and
  raises where it fails. Neither layer should reach a plugin any other way
- ``export_plot_data()`` to save cached data as a CSV
- ``handle_kill_worker()`` and ``handle_kill_all_workers()`` to gracefully stop
  long-running operations; the second also stops the tab's replay

What You Need to Implement
--------------------------

Two methods are abstract, and the constructor calls both: ``_init``, which must assign
``self.view`` and ``self.model``, and ``_setup_connections``, which connects your View's
intent signals to your Controller's slots. Each method's contract is on the
:ref:`MetaController` reference page.
