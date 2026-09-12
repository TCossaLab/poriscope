.. _CallingAPlugin:

Calling a Data Plugin
=====================

An analysis tab reaches a data plugin by **calling it**, through ``call()`` on its
Controller or its Model:

.. code-block:: python

   samplerate = self.model.call("MetaReader", reader_key, "get_samplerate")

That is the whole plugin-facing API a tab gets. It resolves the instance, calls the
method, and returns whatever the method returns. A failure raises where it happened.

.. important::

   **Do not use** :ref:`GlobalSignal` **for this in new code.** Since 2.0.0 no analysis
   tab in Poriscope emits on that bus; every one of them calls its plugins directly.
   The bus is still wired and still documented, because the machinery has not been
   removed, but a tab written against it today would be the only one.

Where the call goes
-------------------

``call()`` lives on ``MetaController`` and on ``MetaModel``, so both halves of a tab
have it. Which you use follows the tab's own layering: commands arrive at the
Controller, and computation belongs in the Model, so a Controller slot answering a
View intent normally calls ``self.model.call(...)``.

The plugin instances are **pushed** to every tab as they are created, renamed,
reconfigured and destroyed, so nothing is resolved lazily and nothing goes stale.

Why it replaced a signal
------------------------

The bus carried a request out and the answer back through seven hops, the last of
which parked the value on an attribute for the calling line to read on its next
statement. Three consequences, all of which ``call()`` removes:

- **A failed call was invisible.** The dispatcher logged and returned, so the caller
  read back whatever the *previous* call had left on that attribute. Not ``None``,
  which callers guarded for - stale, which they did not. Several plots drew the
  previous subset's data under this one's label for exactly this reason.
- **Correctness depended on every hop being a direct connection**, an invariant held
  by a comment. One queued connection anywhere in the chain would have silently
  broken the read-back with no error and no log line.
- **The failure had nowhere to be handled.** A plugin's exception was caught before
  it got back to the emitter, and a Qt slot's exception does not propagate to the
  emitter either - measured on PySide6 6.9.0, ``emit()`` returns normally and the
  traceback goes to ``sys.excepthook``. So a ``try``/``except`` around an emit was
  dead code.

Reporting a failure
-------------------

``call()`` raises, so the caller decides. The convention in the shipped tabs is to
log the exception and put one sentence on the status panel:

.. code-block:: python

   try:
       rows = self.model.call("MetaDatabaseLoader", loader, "load_metadata", columns)
   except Exception as e:
       self.logger.error(f"Failed to load the subset: {e!r}")
       self.add_text_to_display.emit(
           f"Could not load this subset from {loader}: {e}", self.__class__.__name__
       )
       return

Two rules go with that, both learned from defects:

- **Set the View's answers only once the whole chain has succeeded.** A View that
  clears its answer before asking can then tell "this did not run" from "this ran and
  found nothing", which is the distinction the bus destroyed.
- **Stop on a scope that did not resolve**, rather than dropping it from the query. An
  identifier that is unique only within an experiment and channel will match some
  other channel's row if the scope is quietly widened.

Arguments are spread, not tupled
--------------------------------

The bus packed a method's arguments into a tuple. ``call()`` takes them spread:

.. code-block:: python

   # the bus
   self.global_signal.emit(
       "MetaReader", key, "load_data", (start, length, channel), "set_data", ()
   )

   # the call
   data = self.model.call("MetaReader", key, "load_data", start, length, channel)

The same applies to what comes back. The bus chose, from the target's declared return
type, whether to spread the result across the return function's parameters or hand it
over whole; ``call()`` never spreads. A method declared ``-> Tuple[str, str]`` hands
you a 2-tuple, and binding it to one name is a mistake no type checker will catch when
``call()`` is declared ``-> Any``:

.. code-block:: python

   query, debug = self.model.call(
       "MetaDatabaseLoader", loader, "construct_event_data_query", conditions, scope
   )

**Read the target's real signature before writing the call**, and write any test's
expectation from that signature rather than from the call you just wrote - a mocked
model accepts any shape, so a test written the other way round pins the bug.

What stays a signal
-------------------

``call()`` replaces only the request-and-answer pattern. Genuine notifications remain
ordinary Qt signals, because nobody is waiting for a value:

- ``plugin_state_changed`` - tell the app a plugin's state changed
- ``add_text_to_display`` - put a line on the status panel
- ``update_progressbar`` - report progress from a worker
- ``create_plugin`` - ask the shell to instantiate something

So does a tab's own **intent** signal, which is how a View asks its Controller to do
something. The View emits a typed intent; the Controller's slot makes the call and
hands the result back through a setter on the View. That keeps the widget free of
plugin keys and SQL, and it is the path every converted tab now takes.
