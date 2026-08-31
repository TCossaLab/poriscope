.. _serial_channel_operations:

Thread Safety and Serial Channel Operations
===========================================

Poriscope runs one worker thread per channel. When a tab starts event finding, fitting or
writing on four channels, that is four threads calling into **the same plugin instance** at
the same time. If your plugin cannot survive that, it has to say so — and this page is about
how to say it, and what happens once you do.

The declaration
---------------

Every data plugin inherits :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.force_serial_channel_operations`.
Returning ``True`` means:

    *My own operations must not overlap across channels.*

Read that precisely, because both halves matter:

- **"My own"** — the guarantee is per *instance*. Two different writer instances, pointed at
  two different output files, still run concurrently with each other. You are not asking the
  whole application to queue behind you.
- **"across channels"** — the thing being prevented is channel 1 and channel 2 of *this*
  plugin running at once.

The default is ``False``, i.e. "I am thread-safe, run my channels in parallel". Most plugins
that only read are: reading a file from disk is generally safe, so
:ref:`MetaReader`, :ref:`MetaFilter`, :ref:`MetaEventLoader` and :ref:`MetaDatabaseLoader`
all default to ``False``. Both writer bases default to ``True``, because writing is not.

How it is enforced
------------------

You do not have to do anything to make the declaration take effect. Each of the generator
methods the channel-management system drives is decorated with
:py:func:`~poriscope.utils.SerializeDecorator.serialize_channels`, which runs the generator
inside :py:meth:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.serialize_channel_operations`.
That checks your declaration and, if it is ``True``, holds **this instance's**
:py:attr:`~poriscope.utils.BaseDataPlugin.BaseDataPlugin.lock` for the run.

The five guarded entry points are:

============================  ===========================
Base class                    Guarded generator
============================  ===========================
:ref:`MetaWriter`             ``commit_events``
:ref:`MetaDatabaseWriter`     ``write_events``
:ref:`MetaEventFinder`        ``find_events``
:ref:`MetaEventFitter`        ``fit_events``
:ref:`MetaDatabaseLoader`     ``export_subset_to_csv``
============================  ===========================

.. important::

   **Writing a normal plugin? You will never apply this decorator yourself.** It sits on the
   base-class methods, above the abstract hooks you implement, so your implementation is
   already protected. Overriding ``force_serial_channel_operations`` to return ``True`` is the
   whole of your job.

   You only reach for the decorator if you are adding a *new* generator method to a ``Meta*``
   base class that the channel-management system will drive — that is, extending the framework
   rather than writing a plugin.

The lock is held for the whole run, not per iteration
-----------------------------------------------------

This surprises people, so it is worth being explicit. The guard wraps a ``yield from``, and a
generator suspended at a ``yield`` is suspended *inside* the ``with`` block. So the lock is
acquired on the generator's first advance and released only when it is exhausted, closed, or
raises — not released and re-acquired around each ``yield``.

That is deliberate: a write spanning many events is not safe to interleave halfway through.
But it has a consequence for you:

.. warning::

   Do not do slow work unrelated to the protected resource inside a guarded generator. While
   you hold the lock, every other channel of your plugin is blocked, and a worker waiting on
   the lock **cannot observe an abort request** — ``stop()`` only sets a flag that the
   generator reads on its next turn, and a generator that has not started cannot read
   anything. Keep the critical section to the work that actually needs protecting.

Dependency chains
-----------------

Plugins that depend on other plugins should defer to what they depend on rather than guessing.
:ref:`MetaEventFinder` does this by asking its reader, and :ref:`MetaEventFitter` by asking its
event loader:

.. code-block:: python

   @override
   def force_serial_channel_operations(self) -> bool:
       # I am safe in myself, but I am only as safe as what I read from
       return self.reader.force_serial_channel_operations()

.. note::

   There is a known limitation here. The guard locks the plugin that *declares*, so a finder
   declaring ``True`` because its reader is unsafe protects the finder, not the reader — and
   two different finders sharing one reader would still reach it concurrently. This is latent
   today, since no shipped reader or loader returns ``True``, but if you write a reader that
   is genuinely not thread-safe, do not rely on a finder's deferral alone. It is recorded in
   ``future_fixes.md``.

When you need a *process-wide* lock instead
--------------------------------------------

``self.lock`` is per instance. If what you are protecting is shared by every instance in the
process — most often a native library that is not re-entrant — a per-instance lock is not
enough, and you must declare your own class-level lock.

``WaveletFilter`` is the worked example. Its C library is loaded per instance but
``LoadLibrary`` hands back a shared module handle, so two instances filtering at once would
corrupt each other:

.. code-block:: python

   class WaveletFilter(MetaFilter):
       logger = logging.getLogger(__name__)
       # Process-wide, deliberately: the wavelet C library is not reentrant and every
       # instance shares one module handle.
       _dll_lock = threading.Lock()

       def _apply_filter(self, data):
           with self._dll_lock:
               self.fun(data, len(data), wavelet)

.. caution::

   Do not reuse ``self.lock`` for this and do not put a class-level ``lock`` on your plugin to
   get the old behaviour back. ``BaseDataPlugin.lock`` used to be a class attribute — one lock
   for every data plugin in the process — and is now per instance. Give a process-wide lock its
   own clearly-named attribute so the difference in scope is visible at the call site.

Filters are a special case
--------------------------

``force_serial_channel_operations()`` is **never consulted for filters**. Filters are not
dispatched through the channel-management system: they are handed out as plain callables by
``MetaFilter.get_callable_filter`` and invoked inline inside *other* plugins' generators — on
several worker threads at once, and on the GUI thread for plotting. If your filter is not
thread-safe, guard the unsafe resource directly, as ``WaveletFilter`` does. Declaring
``True`` will do nothing.

This applies to scripts too
---------------------------

Because the guard now lives on the plugin rather than in the GUI's model, it applies whenever
the plugin is used — including from a standalone script (see :ref:`scripting`). If you drive a
writer's channels from two threads of your own, they will serialise. Single-threaded scripts
are unaffected: the lock is reentrant and uncontended.

API
---

.. autofunction:: poriscope.utils.SerializeDecorator.serialize_channels

.. automethod:: poriscope.utils.BaseDataPlugin.BaseDataPlugin.serialize_channel_operations
   :no-index:

.. automethod:: poriscope.utils.BaseDataPlugin.BaseDataPlugin.force_serial_channel_operations
   :no-index:
