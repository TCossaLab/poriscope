API Overview
-------------

To emit a Data Plugin Controller Signal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    data_plugin_controller_signal = Signal(str, str, str, tuple, object, tuple)

- **metaclass (str)**: The type of the metaclass associated with this signal.
- **subclass_key (str)**: A specific identifier for a subclass of the metaclass.
- **function_to_call (str)**: The name of the function that will be executed.
- **args_for_function_call (tuple)**: Arguments to pass to the function specified.
- **return_function_to_call (object)**: The function that will handle the return of the called function.
- **ret_args (tuple)**: Additional arguments that might be passed to the return function.
