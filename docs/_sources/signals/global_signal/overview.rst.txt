API Overview
=============

To emit a global signal:
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    global_signal = Signal(str, str, str, tuple, str, tuple)

- **metaclass (str)**: The type of the metaclass associated with the signal.
- **subclass key (str)**: A specific identifier for a subclass of the metaclass.
- **function to call (str)**: The name of the function to be executed.
- **args for function (tuple)**: Arguments to pass to the function specified.
- **return function to call (str)**: The *name* of the method that will handle the return value. Pass ``""`` if no callback is needed.
- **ret args (tuple)**: Additional arguments appended after the return value when the return function is called.

.. important::

   The fifth argument is a **string**, not a callable, when you emit from a
   ``MetaView`` or a ``MetaModel``. ``MetaController`` resolves that name against
   **itself** with ``getattr`` and re-emits the bound method to ``MainController``,
   which is why the signal is declared with ``object`` in that position on
   ``MetaController`` and ``str`` on the view and model.

   The practical consequence: **your return function must be defined on your
   Controller, not on your View.** The controller then forwards to the view. A name
   that is not an attribute of the controller, or that names something not callable,
   is rejected at the relay with a warning and the whole call is abandoned.

Both argument tuples really are tuples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``call_args`` and ``ret_args`` are splatted into their respective calls, so they must
be tuples of positional arguments. A very easy mistake is to write a parenthesised
value and expect it to behave as a one-element tuple:

.. code-block:: python

    ("cluster_label")    # WRONG - this is just a string
    ("cluster_label",)   # right - a one-element tuple

    (queries)            # WRONG - this is just the list
    (queries,)           # right - one argument, which happens to be a list

Use ``()`` when the target takes no arguments. The dispatcher does not guess at a bare
value passed in place of a tuple; a call whose arguments do not match the target's
signature is reported and **never attempted**.

How the return value reaches your callback
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The dispatcher decides whether to spread the return value across your callback's
parameters or pass it as a single argument by reading the **declared return type** of
the function it called. This cannot be decided from the value itself: a method
returning a pair and a method returning two values produce exactly the same object.

- Target annotated ``-> Tuple[...]``: the result is splatted, then ``ret_args`` follow.
- Target annotated anything else: the result is passed as **one** argument, then
  ``ret_args`` follow. This includes ``None`` — an ``Optional`` return that resolved to
  nothing still occupies its argument slot.

So when you write a plugin method that the bus will call, **its return annotation is the
callback contract**. Annotate ``-> Tuple[str, str]`` and callbacks receive two
parameters; annotate ``-> Optional[str]`` and they receive one.

.. code-block:: python

    # MetaDatabaseLoader.get_column_units is `-> Optional[str]`, so one argument:
    self.global_signal.emit(
        "MetaDatabaseLoader", loader, "get_column_units", (column,),
        "update_column_units", (axis,),
    )
    # calls, on your controller:
    #     update_column_units(units, axis)
    #     update_column_units(None, axis)   <- when the loader has no unit for it

    # MetaDatabaseLoader.construct_metadata_query is `-> Tuple[str, str, str]`, so splatted:
    self.global_signal.emit(
        "MetaDatabaseLoader", loader, "construct_metadata_query",
        (columns, sql_filter, None),
        "relay_query", ("validate_new_filter",),
    )
    # calls, on your controller:
    #     relay_query(query, debug, table_name, "validate_new_filter")

A target that declares a tuple return and produces something else has broken its own
contract; that is logged and the value passed as a single argument rather than coerced.

What happens when something is wrong
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every failure is logged and swallowed — the handlers are Qt slots and must not let an
exception escape into the C++ caller — so the log is where you look. Arity is checked
against the resolved signature *before* the call, and the reason comes from Python
itself:

.. code-block:: text

    Not calling MetaDatabaseLoader/my_loader.get_column_units:
      (column: str) -> Optional[str] cannot accept arguments ():
      missing a required argument: 'column'

Your target method is called **at most once**. If it raises ``TypeError`` from inside
its own body, that is reported as what it is, with a traceback:

.. code-block:: text

    MetaDatabaseLoader/my_loader.get_column_units raised while executing
    with arguments ('duration',)

.. note::

   Earlier versions caught that ``TypeError`` and retried the call with a single
   ``None`` as arity recovery. Because a mismatch at the call boundary and an error
   inside the callee are both ``TypeError``, a method that had already run could be
   run a second time with different arguments — and any target whose parameters are
   all optional would accept the ``None`` and quietly return a wider result than was
   asked for. Nothing is retried now.
