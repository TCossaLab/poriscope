Which to use 
============

.. tabs::

   .. tab:: Similarities

      **Method Signature**: Both methods use the same function signature, taking parameters `metaclass`, `subclass_key`, `call_function`, `call_args`, `return_function`, and `ret_args`.

      **Shared implementation**: Beyond resolving their target, both handlers run *the same code* — ``MainController._dispatch_to`` — so their guards, their argument rules, their return-value handling and their log messages are identical by construction and cannot drift apart. The two were previously copies of one another and had already diverged in their error handling.

      **Error Handling**: The shared body checks that `call_function` exists and is callable, then checks that `call_args` will bind to its signature *before* calling it. A call that cannot bind is reported and never attempted; the target is called at most once; a `TypeError` raised inside the target is reported as such, with a traceback, rather than being mistaken for an argument mismatch.

      **Return Function Execution**: Both execute a `return_function` with the result of `call_function` followed by `ret_args`. Whether the result is spread across the callback's parameters or passed as a single argument is decided by the target's declared return type — see the :ref:`GlobalSignal` API overview.

   .. tab:: Differences

      **Target Instance**

      - **Global Signal**: The ``handle_global_signal`` method retrieves an instance of a plugin directly using ``self.data_plugin_controller.get_plugin_instance(metaclass, subclass_key)`` -> It interacts directly with plugin instances managed by ``DataPluginController``.
      - **Data Plugin Controller Signal**: The ``handle_data_plugin_controller_signal`` method interacts with the ``DataPluginController`` itself, not with a specific plugin instance -> Actions relate to broader management tasks within the ``DataPluginController``.

      **Functional Context**

      - **Global Signal**: General-purpose, cross-plugin use
        - Designed to facilitate general actions across the system that may involve various plugins and their functionalities -> Invokes specific functionalities of individual plugins.

      - **DP Controller Signal**: Narrow scope, for administrative/config purposes.
        - Handles tasks that involve the configuration or state management within the ``DataPluginController``, making it more about administrative or configurational control rather than direct plugin functionality.

   .. tab:: Classes

    **Same Implementation:**

        - MetaController
        - MetaModel
        - MetaView
        - MainController: both slots delegate to the same ``_dispatch_to``

    **The only difference is what each slot resolves as the target**, after which they
    hand off to identical code:

    **handle_global_signal** — resolves a plugin instance:

      .. code-block:: python

         target_label = f"{metaclass}/{subclass_key}"
         instance = self.data_plugin_controller.get_plugin_instance(metaclass, subclass_key)
         if instance is None:
             ...log and return...
         self._dispatch_to(instance, target_label, call_function, call_args, return_function, ret_args)

    **handle_data_plugin_controller_signal** — the target *is* the controller:

      .. code-block:: python

         target_label = "DataPluginController"
         self._dispatch_to(self.data_plugin_controller, target_label, call_function, call_args, return_function, ret_args)

    Both wrap that in a guard that logs with a traceback and swallows, because the slots
    are invoked from C++ and an exception must not escape into the Qt caller. In
    ``handle_global_signal`` the resolution itself is inside the guard: looking up an
    unregistered ``metaclass`` raises ``KeyError`` rather than returning ``None``.

    ``target_label`` is what you will see naming the target in every log message on that
    path — a plugin key for one, the literal ``DataPluginController`` for the other.

   .. tab:: Summary

      - ``handle_global_signal``: More versatile in its application, dealing with a range of functions across various plugin instances. It’s about leveraging specific functionalities provided by the plugins.
      - ``handle_data_plugin_controller_signal``: More focused and narrow in scope, dealing strictly with functions that manage or configure the data plugins via the controller.
