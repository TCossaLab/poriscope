Which to use 
============

.. tabs::

   .. tab:: Similarities

      **Method Signature**: Both methods use the same function signature, taking parameters `metaclass`, `subclass_key`, `call_function`, `call_args`, `return_function`, and `ret_args`.

      **Error Handling**: Both methods check for the existence and callable status of the function intended to be executed (`call_function`).

      **Return Function Execution**: Both methods can execute a `return_function` with the results of `call_function`, appending `ret_args` if provided.

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

    **Different Implementation:**

        MainController: ``handle_global_signal`` vs ``handle_data_plugin_controller_signal``


    **Function Signature: handle_global_signal**
      
      .. code-block:: python

         @Slot(str, str, str, tuple, object, tuple)
         def handle_global_signal(self, metaclass: str, subclass_key: str, call_function: str, call_args: tuple, return_function: object, ret_args: tuple):
             self.logger.debug(f'received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}')
             instance = self.data_plugin_controller.get_plugin_instance(metaclass, subclass_key)

        Unique line: **instance = self.data_plugin_controller.get_plugin_instance(metaclass, subclass_key)**

    **Function Signature: handle_data_plugin_controller_signal**
      .. code-block:: python

         @log(logger=logger)
         @Slot(str, str, str, tuple, object, tuple)
         def handle_data_plugin_controller_signal(self, metaclass: str, subclass_key: str, call_function: str, call_args: tuple, return_function: object, ret_args: tuple):
             self.logger.debug(f'received signal: {metaclass}, {subclass_key}, {call_function}, {call_args}, {return_function}, {ret_args}')
             instance = self.data_plugin_controller  # this one goes to the data plugin controller directly, NOT to an actual plugin instance
    
        Unique line: **instance = self.data_plugin_controller**

   .. tab:: Summary

      - ``handle_global_signal``: More versatile in its application, dealing with a range of functions across various plugin instances. It’s about leveraging specific functionalities provided by the plugins.
      - ``handle_data_plugin_controller_signal``: More focused and narrow in scope, dealing strictly with functions that manage or configure the data plugins via the controller.
