.. _build_frontend_plugin:

Ready to Build Your Own Plugin?
===============================

Now that you understand what base classes are and how they work, you're ready to start building your own plugins.

Let’s say you want to build an analysis tab. That means you’ll need three things:

- A Model
- A View
- A Controller

Let’s start with the **View**, because if you’re anything like me — a visual thinker — it helps to see what the user will interact with first. Once that’s clear, it’s easier to decide what logic you’ll need behind the scenes.

.. tip::

   Frontend plugin families go through the same compliance gate as data plugins:
   automated formatting/typing/docstring checks plus a plugin interface compliance
   test (see :ref:`quality_control`). Before opening a pull request, work through
   :ref:`pre_pr_checklist` — it applies just as much to a new analysis tab as it does
   to a new data plugin.

.. toctree::
   :maxdepth: 1

   metaview_base
   metamodel_base
   metacontroller_base
