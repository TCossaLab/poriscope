.. _GlobalSignal:

Global Signal
==============

This document provides an API-level overview of the ``global_signal`` used for general plugin-to-plugin communication via the ``MainController``.

It allows views and models to request actions from analysis or data plugins without needing direct access to them. This signal is relayed through the ``MetaController`` and dispatched centrally by the ``MainController``, supporting modular, decoupled function calls.

.. toctree::
   :maxdepth: 1

   overview
   example_usage
