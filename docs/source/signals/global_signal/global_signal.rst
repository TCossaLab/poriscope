.. _GlobalSignal:

Global Signal
==============

This document provides an API-level overview of the ``global_signal`` used for general plugin-to-plugin communication via the ``MainController``.

.. important::

   **No analysis tab uses this any more.** Since 2.0.0 every tab reaches its data
   plugins by calling them - see :ref:`CallingAPlugin`, which is where new code
   should start. The bus is still wired and is documented here because the machinery
   has not been removed, and because the ``DataPluginController`` signal beside it
   shares its dispatcher.

It allows views and models to request actions from analysis or data plugins without needing direct access to them. This signal is relayed through the ``MetaController`` and dispatched centrally by the ``MainController``, supporting modular, decoupled function calls.

.. toctree::
   :maxdepth: 1

   overview
   example_usage
