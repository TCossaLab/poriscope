.. _GlobalSignal:

Global Signal (removed)
=======================

``global_signal`` no longer exists. It was removed in 2.0.0, along with its relays
and the dispatcher behind it.

This page is kept so that a search for the name lands somewhere useful rather than
nowhere.

What it was
-----------

A tab that needed something from a data plugin — a sample rate, an event count, a
status — emitted ``global_signal`` naming the plugin, the method, its arguments,
and the name of a *callback* to hand the answer to. The signal travelled from the
View or Model up through ``MetaController`` to ``MainController``, which resolved
the plugin and called the method, then called the named callback, which set an
attribute on the View. The caller read that attribute on its next statement.

What to use instead
-------------------

**Call the plugin.** See :ref:`CallingAPlugin`:

.. code-block:: python

   samplerate = self.model.call("MetaReader", reader_key, "get_samplerate")

The answer is the return value. There is no callback and no attribute to read
back.

Why it went
-----------

The round trip was seven hops, and the dispatcher logged-and-returned on four
separate conditions. A dispatch that failed therefore left the previous call's
value sitting on the attribute, and the caller read *that* — with no error, and
no log line the caller could see. It caused two real bugs: a metadata plot showing
the previous subset's rows, and a query running against the previous experiment's
id.

``call()`` raises where the failure happens, so a failed call stops the thing it
should stop.

If you are porting code
-----------------------

An emit with a callback becomes a call whose return value you use directly. An
emit *without* a callback — one that only asked for something to be done — becomes
either a direct call or, for creating, editing and deleting data plugins, one of
the typed signals described in :ref:`DataPluginControllerSignal`.
