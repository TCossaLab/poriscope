.. _build_frontend_plugin:

Ready to Build Your Own Plugin?
===============================

An analysis tab is three classes - a Model, a View and a Controller - plus the controls
panel its View shows under the plot.

.. _new_tab_script:

Start From a Generated Triad
----------------------------

You do not have to write the triad by hand. ``scripts/new_plugin.py`` writes all
three files and the tab's controls panel, already carrying every abstract method each base declares, with signatures and
docstrings copied verbatim out of those bases:

.. code-block:: bash

   python scripts/new_plugin.py AnalysisTab MyTab           # into this repository
   python scripts/new_plugin.py AnalysisTab MyTab --user    # into your user plugin folder
   python scripts/new_plugin.py --list AnalysisTab          # what the triad's files will hold

That writes four files: ``MyTabController.py``, ``MyTabModel.py``, ``MyTabView.py`` and the
controls panel. Into this repository the panel goes to ``analysistabs/utils/mytabcontrols.py``,
where every shipped tab keeps its own; anywhere else it is ``MyTabControls.py`` beside the
other three. The result **starts as a working tab**: restart Poriscope and
``MyTabController`` appears in the Analysis menu, opening a tab with a plot canvas above a
control panel whose one button acknowledges itself on the status panel. Filling in the
stubs is then a matter of changing a tab that works rather than getting one to work.

:ref:`HelloWorld` walks through what the generator writes: which bodies are written for
you and why, the controls panel, and what to change first. :ref:`SimpleCalc` is the same
output filled in as a complete tab.

.. warning::

   Class names must be unique across **every** plugin family, analysis tabs included, so
   all four generated names are checked before anything is written. Give the tab's name
   without a role suffix — ``MyTab``, not ``MyTabView`` — and the generator appends
   ``Controller``, ``Model``, ``View`` and ``Controls`` itself.

   Keep that pairing if you rename anything: the application predicts the page a tab will
   open from the controller's name (``MyTabController`` opens ``MyTabView``) before the tab
   exists, so a View named differently from its Controller is refused or allowed against the
   wrong page while the guided walkthrough is running. The tabs shipped with Poriscope are
   checked for this by a test.

.. note::

   A tab generated into your user plugin folder imports its View and Model by their bare
   file names — ``from MyTabView import MyTabView`` — because Poriscope puts that folder
   on the import path for you. A tab generated into this repository imports them through
   ``poriscope.plugins.analysistabs`` instead, the way the six shipped tabs do. Either
   way the rule that a file is named exactly for the class it defines is what makes the
   import work, so rename all four together or not at all.

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
