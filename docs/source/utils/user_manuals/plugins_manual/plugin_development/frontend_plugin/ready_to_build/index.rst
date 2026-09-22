.. _build_frontend_plugin:

Ready to Build Your Own Plugin?
===============================

Now that you understand what base classes are and how they work, you're ready to start building your own plugins.

Let’s say you want to build an analysis tab. That means you’ll need three things:

- A Model
- A View
- A Controller

Let’s start with the **View**, because if you’re anything like me — a visual thinker — it helps to see what the user will interact with first. Once that’s clear, it’s easier to decide what logic you’ll need behind the scenes.

.. _new_tab_script:

Start From a Generated Triad
----------------------------

You do not have to write the three files by hand. ``scripts/new_plugin.py`` writes all
three, already carrying every abstract method each base declares, with signatures and
docstrings copied verbatim out of those bases:

.. code-block:: bash

   python scripts/new_plugin.py AnalysisTab MyTab           # into this repository
   python scripts/new_plugin.py AnalysisTab MyTab --user    # into your user plugin folder
   python scripts/new_plugin.py --list AnalysisTab          # what the three files will hold

That writes ``MyTabController.py``, ``MyTabModel.py`` and ``MyTabView.py``. The result
**starts as a working tab**: restart Poriscope and ``MyTabController`` appears in the
Analysis menu, opening an empty tab with a plot canvas and a control area. Filling in the
stubs is then a matter of changing a tab that runs rather than getting one to run.

Two of the generated bodies are written for you rather than left as a ``# TODO``, because
in both cases the base's own code depends on them and a stub would fail at runtime rather
than at review:

- ``MyTabController._init`` builds ``MyTabView()`` and ``MyTabModel()``. ``MetaController``
  connects the two to each other the moment ``_init`` returns, so a tab that does not
  build them cannot be constructed.
- ``MyTabView.update_available_plugins`` calls ``super()`` before anything else, because
  the base implementation is what records the available plugins on the View.

Everything else is a stub marked ``# TODO`` carrying the contract it has to satisfy. The
Controller is the file to open first: it is the only one of the three the application
instantiates directly, and it names the other two.

.. warning::

   Class names must be unique across **every** plugin family, analysis tabs included, so
   all three generated names are checked before anything is written. Give the tab's name
   without a role suffix — ``MyTab``, not ``MyTabView`` — and the generator appends
   ``Controller``, ``Model`` and ``View`` itself.

.. tip::

   Frontend plugin families go through the same compliance gate as data plugins:
   automated formatting/typing/docstring checks plus a plugin interface compliance
   test (see :ref:`quality_control`). Before opening a pull request, work through
   :ref:`pre_pr_checklist` — it applies just as much to a new analysis tab as it does
   to a new data plugin.

Before you start, :ref:`choosing_a_base` covers which of the shipped base classes your
tab should inherit from, and why - the answer is different for a tab that queries a
results database than for one that finds events in a raw signal.

.. toctree::
   :maxdepth: 1

   choosing_a_base
   metaview_base
   metamodel_base
   metacontroller_base
