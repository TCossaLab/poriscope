.. _HelloWorld:

Keeping It Minimal: HelloWorld Tutorial
=======================================

If you just want to get started and make sure everything works, the :ref:`HelloWorld` tab is
a good place to begin. It is the smallest analysis tab that is still a *real* one: it loads,
it appears in the Analysis menu, it draws a plot canvas, and its single button travels the
whole path a real control takes and reports that it got there.

You do not write it. ``scripts/new_plugin.py`` does:

.. code-block:: bash

   python scripts/new_plugin.py AnalysisTab HelloWorld --user

``--user`` writes into your user plugin folder, so nothing lands in the repository and you
can delete it afterwards by deleting four files. Restart Poriscope and
``HelloWorldController`` is in the Analysis menu.

.. note::

   Every code block on this page is included directly from the files the generator writes,
   which live at ``docs/source/_static/examples/analysis_tabs/``. They are the real output,
   checked by the same ``black`` and ``ruff`` runs as the rest of the repository — not a
   transcription that can drift away from what the tool actually produces.

What You Get
------------

Four files. The first three are the MVC triad described in :ref:`build_frontend_plugin`; the
fourth is the panel of controls that sits under the plot.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - File
     - What it is for
   * - ``HelloWorldController.py``
     - Owns the tab. The only one of the four Poriscope instantiates directly.
   * - ``HelloWorldModel.py``
     - Holds the tab's data and does its computation. Empty here — there is none yet.
   * - ``HelloWorldView.py``
     - Lays out the widgets and draws the plot.
   * - ``HelloWorldControls.py``
     - The controls panel: the widgets a user actually operates.

Every method carries the docstring copied out of the base class that declares it, so the
contract you have to satisfy is in front of you rather than in another file.

The Controller
--------------

The Controller is the file to open first, because it names the other two thirds of the
triad. ``_init`` is written for you rather than left as a ``# TODO``: ``MetaController``
connects the View and the Model to each other the instant ``_init`` returns, so a tab that
does not build them both cannot be constructed at all.

.. literalinclude:: /_static/examples/analysis_tabs/HelloWorldController.py
   :language: python
   :pyobject: HelloWorldController

``_setup_connections`` is where your View's own signals meet your Controller's slots. It is
empty here because this tab has no logic to connect yet.

The View
--------

Two of the View's methods are written out rather than stubbed. The first is
``_build_controls``, which hands your controls panel back to the base — the base then wires
its four signals and places it for you:

.. literalinclude:: /_static/examples/analysis_tabs/HelloWorldView.py
   :language: python
   :pyobject: HelloWorldView._build_controls

The second is ``handle_parameter_change``, which is where a control action arrives. Every
shipped tab writes it the same way — read ``args[0]`` into ``parameters``, then branch on
``action_name`` — and the generated one has a single branch matching the single action the
panel emits:

.. literalinclude:: /_static/examples/analysis_tabs/HelloWorldView.py
   :language: python
   :pyobject: HelloWorldView.handle_parameter_change

The ``else`` matters more than it looks. Renaming an action in the panel and forgetting to
rename it here is the one mistake this dispatch shape invites, and without the ``else`` the
press would simply do nothing.

The remaining View methods — ``_init``, ``_reset_actions``, ``update_available_plugins`` and
``notify_plugin_state_changed`` — are stubs marked ``# TODO``, each carrying the contract it
has to satisfy. See :doc:`ready_to_build/metaview_base` for what each one is for.

The controls panel
------------------

``HelloWorldControls`` is the one generated file that is not copied out of a base class.
``MetaControls`` is a plain ``QWidget`` that gives you widget factories and signals but
declares none of the methods it expects you to write, so the generator writes them out:

.. literalinclude:: /_static/examples/analysis_tabs/HelloWorldControls.py
   :language: python
   :pyobject: HelloWorldControls.setupUi

.. literalinclude:: /_static/examples/analysis_tabs/HelloWorldControls.py
   :language: python
   :pyobject: HelloWorldControls._on_action_requested

``actionTriggered`` is the signal that carries work out of the panel, and
``MetaView._set_control_area`` has already connected it to your View's
``handle_parameter_change``. That connection is the one link in the chain you do not write.

What You'll See
---------------

.. figure:: /_static/images/HelloWorldInAnalysisMenu.png
   :alt: Hello World Tab appears as an option in the analysis menu
   :width: 1000px
   :align: center

   **HelloWorld in the Analysis Menu** — once the plugin is loaded, it appears as a
   selectable tab in the analysis menu.

Open it and you get a plot canvas with the controls panel beneath it. Press **DO SOMETHING**
and a line appears on the status panel naming the action and the (empty) parameters that
came with it.

That message is the point of the whole example. It means the panel was built, the base
connected it, the signal carried, your View's handler ran, and the message it emitted was
relayed all the way back to the shell. Every one of those links is working before you have
edited a line.

What to Change First
--------------------

In order, because each step depends on the one before it:

1. **Put your own controls in** ``HelloWorldControls.setupUi``, replacing the button. The
   base's ``createLabel``, ``create_comboBox`` and ``createButton`` build the plain widgets
   with the font and sizing already applied.
2. **Read them in** ``collect_parameters``, which is called as the action is emitted — a
   request has to carry what was on screen when it was made, not what is there by the time
   it is handled.
3. **Add a branch per action** in ``HelloWorldView.handle_parameter_change``.
4. **Give the Model something to do**, and connect the two in
   ``HelloWorldController._setup_connections``. Computation belongs in the Model, not the
   View — see :doc:`ready_to_build/metamodel_base`.

.. note::

   If you are new to PySide6 widgets and layouts,
   `pythonguis.com <https://www.pythonguis.com/pyside6/>`_ is a good place to start.

When your tab outgrows this, :doc:`simpleCalc/from_helloworld_to_full_mvc` walks through a
complete tab with real logic in all three layers.
