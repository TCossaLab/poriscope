.. _DataPluginControllerSignal:

Data Plugin Controller Signal (replaced)
========================================

``data_plugin_controller_signal`` no longer exists. It was removed in 2.0.0
alongside :ref:`GlobalSignal`, with which it shared a dispatcher.

This page is kept so that a search for the name lands somewhere useful, and
because what replaced it is what you want if you are adding a plugin control to a
tab.

What it was
-----------

A tab that wanted the application to *manage* a data plugin — create one, edit its
settings, delete it — emitted this signal naming the ``DataPluginController``
method to run and packing its arguments into a tuple. It shared its dispatcher
with ``global_signal`` and was resolved the same way, by string, at emit time.

What to use instead
-------------------

**Three typed signals**, one per action, each carrying the metaclass and the
plugin's key (the subclass, for ``create_plugin``):

.. code-block:: python

   self.create_plugin.emit(metaclass, subclass)   # add a new plugin
   self.edit_plugin.emit(metaclass, key)          # open its settings dialog
   self.delete_plugin.emit(metaclass, key)        # remove it

They are declared on ``MetaView`` and relayed by ``MetaController`` to
``MainController``, which connects each one directly to the matching
``DataPluginController`` method. A tab emits; it does not name a method, pack a
tuple, or supply a callback.

Why this is better
------------------

Nothing here ever needed an answer. All three actions were emitted with an empty
return function, so the whole return-value half of the bus was dead weight on
this path.

The shell connects each signal to a named ``DataPluginController`` method
(``main_controller.py``), so a renamed or removed method fails with
``AttributeError`` when the tab is opened, instead of a string lookup failing
silently at emit time. Qt does not check the argument count when connecting,
so a slot with the wrong arity still surfaces only at emit.

And ``DataPluginController`` is a singleton, built once and never replaced, so
there was nothing for a dispatcher to resolve in the first place.

``create_plugin`` already worked this way before the others did; the change
simply made all three consistent.
