API Overview
-------------

To emit a Data Plugin Controller Signal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    data_plugin_controller_signal = Signal(str, str, str, tuple, str, tuple)

- **metaclass (str)**: Passed for signature parity with ``global_signal``. It is logged, but **not** used to resolve a target here.
- **subclass_key (str)**: Likewise passed and logged, but not used to resolve a target.
- **function_to_call (str)**: The name of the ``DataPluginController`` method that will be executed.
- **args_for_function_call (tuple)**: Arguments to pass to the function specified.
- **return_function_to_call (str)**: The *name* of the method that will handle the return value. Pass ``""`` if no callback is needed, which is the common case here.
- **ret_args (tuple)**: Additional arguments appended after the return value when the return function is called.

.. important::

   The only difference from :ref:`GlobalSignal` is **what the function name is looked up
   on**: this signal targets the ``DataPluginController`` itself, rather than a plugin
   instance resolved from ``metaclass`` and ``subclass_key``. Everything after that —
   the guards, the argument rules, the return-value handling and the diagnostics — is
   literally the same code path (``MainController._dispatch_to``), so the two signals
   cannot drift apart in their behaviour.

   That means **everything in the** :ref:`GlobalSignal` **API overview applies here
   unchanged**, and is not repeated on this page:

   - ``call_args`` and ``ret_args`` must be real tuples; ``("value")`` is a string, ``("value",)`` is a tuple.
   - The return function is named by a **string** and must exist, and be callable, on your Controller.
   - Whether the result is splatted into the callback or passed whole is decided by the target's declared return type.
   - Arity is checked before the call, the target is called at most once, and nothing is retried.

.. tip::

   Because ``metaclass`` and ``subclass_key`` play no part in resolution here, they do
   not appear in this path's error messages either — a failure is reported against
   ``DataPluginController.<function_to_call>``. Do not go looking for a plugin key in
   the log for this signal; there isn't one.
