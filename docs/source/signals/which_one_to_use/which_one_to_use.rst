Which to use
============

This page used to compare the two signal buses with each other. Both were removed
in 2.0.0, so the question has changed: it is no longer *which bus*, but **whether
you are asking a question or announcing something**.

The rule
--------

.. tabs::

   .. tab:: Asking a question

      **Call the plugin.** You want a value back — a sample rate, an event count,
      a status, some data.

      .. code-block:: python

         n = self.model.call("MetaEventFinder", finder_key, "get_num_events_found", channel)

      The answer is the return value, on the same line. A failure raises here,
      where you can see it. See :ref:`CallingAPlugin`.

      ``call()`` is on both ``MetaController`` and ``MetaModel``, so either half
      of a tab can use it. Which one follows the tab's own layering: commands
      arrive at the Controller, computation belongs in the Model.

   .. tab:: Announcing something

      **Emit a signal.** Something happened and others may care, but you are not
      waiting on an answer.

      .. code-block:: python

         self.add_text_to_display.emit(text, source)
         self.update_tab_action_history.emit(actions, False)

      Each is a plain typed Qt signal with a named purpose. Nobody hands you a
      result, and nothing is read back afterwards.

   .. tab:: Managing a data plugin

      **Emit one of the three typed plugin signals** — create, edit or delete.
      These are announcements too; the application acts on them.

      .. code-block:: python

         self.create_plugin.emit(metaclass, subclass)
         self.edit_plugin.emit(metaclass, key)
         self.delete_plugin.emit(metaclass, key)

      See :ref:`DataPluginControllerSignal`.

Why the distinction matters
---------------------------

The removed bus blurred it. It used a *signal* — a fire-and-forget announcement —
to ask a question, then needed a callback and an attribute to smuggle the answer
back to the caller's next line. That is what made a failed request
indistinguishable from a stale answer, and it caused real bugs.

Keeping the two apart is the whole design:

- a question has a return value and raises when it fails
- an announcement has neither, and nobody waits on it

If you find yourself emitting a signal and then reading something back, you want
a call.
