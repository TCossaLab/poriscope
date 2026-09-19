.. _GlobalSignal:

Global Signal
==============

This document provides an API-level overview of the ``global_signal`` used for general plugin-to-plugin communication via the ``MainController``.

.. important::

   **No analysis tab uses this any more, and the bus is being removed.** Since 2.0.0
   every tab reaches its data plugins by calling them - see :ref:`CallingAPlugin`,
   which is where new code should start. This page documents machinery that is still
   wired only because it has not been deleted yet: 2.0.0 removes the signal, its
   relays and its dispatcher, along with the ``DataPluginController`` signal beside it
   that shares that dispatcher. Do not build anything on it.

It allows views and models to request actions from analysis or data plugins without needing direct access to them. This signal is relayed through the ``MetaController`` and dispatched centrally by the ``MainController``, supporting modular, decoupled function calls.

.. toctree::
   :maxdepth: 1

   overview
   example_usage
