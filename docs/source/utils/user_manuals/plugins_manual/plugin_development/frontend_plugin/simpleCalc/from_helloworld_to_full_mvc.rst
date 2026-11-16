.. _SimpleCalc:

From HelloWorld to a Full MVC Analysis Tab
===========================================

SimpleCalc is the :ref:`HelloWorld` tab filled in: a two-number calculator that lists and
plots its results. It is small enough to read whole, and it uses every part of the pattern
the shipped tabs use - a controls panel, the View's action dispatch, an intent signal, a
recorded Controller action and a Model that does the computation. It uses no data plugins
and no worker threads.

It was generated with ``python scripts/new_plugin.py AnalysisTab SimpleCalc`` and then
filled in. The four files live at ``docs/source/_static/examples/simple_calc/``, and every
code block on this page is included from them. To try it, copy them into your user plugin
folder (see :ref:`settings`) and restart Poriscope; ``SimpleCalcController`` is then in the
Analysis menu.

.. figure:: /_static/images/SimpleCalcInAction.png
   :alt: The SimpleCalc tab after three calculations
   :width: 700px
   :align: center

   **SimpleCalc after three calculations** - two number fields, an operator, **Add
   Calculation** and **Reset**, with the results listed under the fields and plotted above.

Type two numbers, pick ``+`` or ``-`` and press **Add Calculation**. Up to five results are
kept; a sixth is refused with a line on the status panel until you press **Reset**.

How a click travels
-------------------

Only the Controller holds both the View and the Model, so it is the only class that
connects them. The View never calls the Model, and the Model never touches a widget.

**1. The panel reads its widgets and emits an action.** ``collect_parameters`` reads the
fields at the moment of the click, and ``actionTriggered`` carries them out of the panel:

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcControls.py
   :language: python
   :pyobject: SimpleCalcControls.collect_parameters

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcControls.py
   :language: python
   :pyobject: SimpleCalcControls._on_calculate_requested

**2. The View turns the action into an intent.** ``MetaView`` has already connected
``actionTriggered`` to ``handle_parameter_change``, which dispatches on the action name and
emits one of the View's typed intent signals:

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcView.py
   :language: python
   :start-at: calculate_requested = Signal
   :end-at: reset_requested = Signal

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcView.py
   :language: python
   :pyobject: SimpleCalcView.handle_parameter_change
   :start-at: parameters = args[0]

**3. The Controller connects the intent to a slot,** in ``_setup_connections``:

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcController.py
   :language: python
   :pyobject: SimpleCalcController._setup_connections
   :start-at: self.view.calculate_requested

**4. The slot asks the Model, then hands the answer to the View:**

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcController.py
   :language: python
   :pyobject: SimpleCalcController.calculate

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcModel.py
   :language: python
   :pyobject: SimpleCalcModel.compute

**5. The View draws what it was given.** ``show_results`` fills the panel's results line
and redraws the plot; it computes nothing:

.. literalinclude:: /_static/examples/simple_calc/SimpleCalcView.py
   :language: python
   :pyobject: SimpleCalcView.show_results

Recording and replay
--------------------

``calculate`` and ``reset`` are decorated with ``@register_action``, so each call is recorded
in the tab's history. That history is what **Save Session**, **Replay Actions** and Undo
work from - see :doc:`../ready_to_build/metacontroller_base`.

- ``calculate`` is ``kind="additive"``: each call adds to the ``results`` figure, and a
  restored session keeps every one since the last reset. ``skip_on_false=True`` keeps a
  refused calculation out of the history; the method returns ``False`` for it.
- ``reset`` is ``kind="reset"`` on the same figure, so a saved session drops the
  calculations before it.
- ``clear_for_replay`` is overridden because this tab keeps its results on the Model, not
  only in the figure; a replay that goes back must forget them too. It records nothing.
- ``write_back`` shows a replayed calculation's numbers in the panel, so the panel ends a
  replay showing the last calculation it ran.

The recorded methods take every value they use as an argument and read no widget, which is
what lets a replay reproduce them.

The full code
-------------

The canvas, its toolbar, the control-area layout and the wiring of the panel's signals all
come from the base classes; none of it appears below.

.. tabs::

   .. tab:: SimpleCalcController

      .. literalinclude:: /_static/examples/simple_calc/SimpleCalcController.py
         :language: python
         :start-at: import logging

   .. tab:: SimpleCalcModel

      .. literalinclude:: /_static/examples/simple_calc/SimpleCalcModel.py
         :language: python
         :start-at: import logging

   .. tab:: SimpleCalcView

      .. literalinclude:: /_static/examples/simple_calc/SimpleCalcView.py
         :language: python
         :start-at: import logging

   .. tab:: SimpleCalcControls

      .. literalinclude:: /_static/examples/simple_calc/SimpleCalcControls.py
         :language: python
         :start-at: import logging

The ``@log(logger=logger)`` decorator on most methods logs each call's arguments and
return value at ``DEBUG``; see :ref:`Logging`.
