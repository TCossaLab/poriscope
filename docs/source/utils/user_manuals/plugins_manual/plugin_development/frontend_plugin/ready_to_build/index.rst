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

That writes four files: ``MyTabController.py``, ``MyTabModel.py``, ``MyTabView.py`` and
``MyTabControls.py``. The result **starts as a working tab**: restart Poriscope and
``MyTabController`` appears in the Analysis menu, opening a tab with a plot canvas above a
control panel holding one button. Pressing it travels the whole path a real control takes
and **acknowledges itself on the status panel**: the panel emits ``actionTriggered``, the
base has connected that to your View's ``handle_parameter_change``, your override
dispatches on the action name, and the message it emits is relayed to the shell. Filling in
the stubs is then a matter of changing a tab that works rather than getting one to work.

Four of the generated bodies are written for you rather than left as a ``# TODO``, because
in each case the base's own code depends on them and a stub would fail at runtime, or not
fail at all:

- ``MyTabController._init`` builds ``MyTabView()`` and ``MyTabModel()``. ``MetaController``
  connects the two to each other the moment ``_init`` returns, so a tab that does not
  build them cannot be constructed.
- ``MyTabView.update_available_plugins`` calls ``super()`` before anything else, because
  the base implementation is what records the available plugins on the View.
- ``MyTabView._build_controls`` returns ``MyTabControls()``. This one is not abstract and
  would not otherwise be stubbed at all — and its default returns an *empty* panel, which
  is legal and leaves a new tab showing a blank strip with nothing to say which method
  fills it.
- ``MyTabView.handle_parameter_change`` carries the ``parameters = args[0]`` then
  branch-on-``action_name`` shape every shipped tab uses, with one branch answering the one
  action the generated panel emits, and an ``else`` that names an action nothing handles.
  Renaming the action at one end and not the other is the mistake this shape invites.

``MyTabControls`` is the one generated file that is not copied out of a base class.
``MetaControls`` is a plain ``QWidget`` that declares none of what it asks a subclass for —
``setupUi``, ``connect_signals``, ``validate_inputs``, ``collect_parameters`` and
``placeholder_texts`` live only in its class docstring — so the generator writes them out
in full. Replace the button in ``setupUi`` with the controls your tab needs, and read them
in ``collect_parameters``.

Everything else is a stub marked ``# TODO`` carrying the contract it has to satisfy. The
Controller is the file to open first: it is the only one of the four the application
instantiates directly, and it names the other two thirds of the triad.

.. warning::

   Class names must be unique across **every** plugin family, analysis tabs included, so
   all three generated names are checked before anything is written. Give the tab's name
   without a role suffix — ``MyTab``, not ``MyTabView`` — and the generator appends
   ``Controller``, ``Model`` and ``View`` itself.

.. note::

   A tab generated into your user plugin folder imports its View and Model by their bare
   file names — ``from MyTabView import MyTabView`` — because Poriscope puts that folder
   on the import path for you. A tab generated into this repository imports them through
   ``poriscope.plugins.analysistabs`` instead, the way the five shipped tabs do. Either
   way the rule that a file is named exactly for the class it defines is what makes the
   import work, so rename all three together or not at all.

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
