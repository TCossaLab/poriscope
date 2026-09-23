MetaController as a Base Class
==============================

:ref:`MetaController` is the abstract base class that manages one view (:ref:`MetaView`) and one model (:ref:`MetaModel`) — it’s the glue that connects the two.
It’s responsible for handling user interactions, coordinating backend logic, relaying signals, and maintaining action history for each plugin tab.

This controller class does a lot behind the scenes so you can focus on your plugin’s behavior rather than reinventing core logic.

What You Get by Inheriting MetaController
-----------------------------------------

**Auto-wired connections**

As soon as you subclass and instantiate a :ref:`MetaController`, the following happens:

- The view’s request to start a generator connects directly to the model's ``run_generators`` method
- Signals from both the view and model are routed to log output and progress bars
- The controller listens for user commands to kill workers or save/export data
- Plugin-state changes, status messages and create/edit/delete requests are relayed to the app shell as typed signals

**Signal relay system**

No need to manually handle cross-plugin communication — :ref:`MetaController` takes care of:

- ``call()`` for reaching a data plugin, and typed signals for asking the application to create, edit or delete one
- Returning the plugin's result directly from ``call()`` - there is no return function to route
- Updating the main display with log messages via ``add_text_to_display``

**Action history tracking**

- Built-in support for tracking user actions per tab
- Can save and reload these actions from a JSON file
- Undo logic included (with safety checks and filtering)

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
