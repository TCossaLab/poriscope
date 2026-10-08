Understanding Signals
=====================

Poriscope's parts talk to each other in two ways, and telling them apart is most
of what you need to know: you either **ask a question** and use the answer, or
you **announce something** and carry on.

Asking: call the plugin
-----------------------

When your tab needs something from a data plugin — the sample rate, how many
events were found, a chunk of data — you call it:

.. code-block:: python

   samplerate = self.model.call("MetaReader", reader_key, "get_samplerate")

You name the plugin family, the instance's key and the method. You get the return
value. If it fails, it raises, right there.

That is the whole plugin-facing API a tab gets. You never hold a reference to
another plugin, and you never import another tab. See :ref:`CallingAPlugin`.

Announcing: emit a signal
-------------------------

When something has happened that others may care about, you emit a Qt signal and
move on:

.. code-block:: python

   self.add_text_to_display.emit("Loaded 4,812 events", self.__class__.__name__)

Nobody hands you a result. You are not waiting. Whoever is connected will react —
and if nobody is, nothing breaks.

This is the walkie-talkie half: you say it into the room, and anyone listening
responds. It is the right tool precisely *because* you do not need an answer.

Why the two are kept apart
--------------------------

Earlier versions had a signal bus that did both at once. A tab asked a question
by *emitting*, naming a callback to receive the answer; the callback parked the
value on an attribute, and the asking code read that attribute on its very next
line.

It broke in a way worth understanding, because it is the reason for the rule. The
dispatch could fail quietly — an unknown plugin, a misspelled method name, bad
arguments — and when it did, the attribute still held **the previous answer**. The
caller read a stale value and could not tell. That shipped two real bugs: a plot
showing the previous selection's rows, and a query run against the previous
experiment.

A call cannot do that. The value comes back on the same line or an exception does.

So:

- **need a value?** call it — :ref:`CallingAPlugin`
- **just reporting?** emit a signal
- **want a plugin created, edited or deleted?** emit one of the three typed
  plugin signals — :ref:`DataPluginControllerSignal`

If you ever find yourself emitting and then reading something back, that is the
old mistake reappearing, and what you want is a call.

.. note::

   The old bus was called ``global_signal``, with
   ``data_plugin_controller_signal`` beside it. Both were removed in 2.0.0. If you
   meet either name in an old branch or an out-of-tree tab, :ref:`GlobalSignal`
   explains what it did and what replaces it.
