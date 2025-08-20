API Overview
=============

To emit a global signal:
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    global_signal = Signal(str, str, str, tuple, object, tuple)

- **metaclass (str)**: The type of the metaclass associated with the signal.
- **subclass key (str)**: A specific identifier for a subclass of the metaclass.
- **function to call (str)**: The name of the function to be executed.
- **args for function (tuple)**: Arguments to pass to the function specified.
- **return function to call (object)**: The function that will handle the return of the called function.
- **ret args (tuple)**: Additional arguments that might be passed to the return function.
