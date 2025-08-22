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
- Plugins can communicate with each other (and the app as a whole) via global or data-specific signals

**Signal relay system**

No need to manually handle cross-plugin communication — :ref:`MetaController` takes care of:

- :ref:`GlobalSignal` and :ref:`DataPluginControllerSignal` relays for calling functions across plugin boundaries
- Routing return values back to the appropriate function using ``ret_args``
- Updating the main display with log messages via ``add_text_to_display``

**Action history tracking**

- Built-in support for tracking user actions per tab
- Can save and reload these actions from a JSON file
- Undo logic included (with safety checks and filtering)

**Utility methods already set up**

- ``export_plot_data()`` to save cached data as a CSV
- ``update_plot_data()`` to push processed data to the view
- ``set_generator()`` to forward generators from controller to model
- ``stop_workers()`` and ``handle_kill_worker()`` to gracefully stop long-running operations

What You Need to Implement
--------------------------

Only two methods are abstract, and both are called automatically during setup.

.. note::

   Want the technical breakdown?  
   Check the :ref:`MetaController` section of this manual — it walks through each method’s purpose and parameters.
