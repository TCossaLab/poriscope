From HelloWorld to a Full MVC Analysis Tab
===========================================

Now that you've explored your first Poriscope plugin with HelloWorld, it's time to look at a complete example of a fully implemented MVC Analysis Tab.

We'll walk through :ref:`SimpleCalc`, a lightweight but fully functional plugin that demonstrates the core responsibilities of the View, Model, and Controller.

This is not just an abstract demo — :ref:`SimpleCalc` shows you exactly:

- How a tab is registered
- How signals are emitted and received
- How user input drives model logic
- How the UI dynamically updates with the result

What This Plugin Does
---------------------

SimpleCalc lets users:

- Input two numeric values
- Select an operation: addition (+) or subtraction (-)
- Click **Add** to compute and display the result
- View up to five results displayed
- Click **Plot** to visualize all results
- Click **Reset** to clear results and reset the interface

This example focuses on interactivity, signals, layout, and plotting — without involving file I/O or multithreading.

How the :ref:`SimpleCalc` Plugin Works (Step-by-Step)
-----------------------------------------------------

The plugin kicks off from the :class:`SimpleCalcController`, which does two important things right away:

- Creates an instance of :class:`SimpleCalcView` — the user interface
- Creates an instance of :class:`SimpleCalcModel` — the logic and data handler

Because the controller holds both of these, it can access their methods.

.. important::

   This is key to the MVC structure: only the controller connects view and model.  
   If the view calls the model directly (or vice versa), you're likely breaking MVC modularity.

.. tabs::

   .. tab:: SimpleCalcModel

      **The Model: Doing the Math**

      When the controller calls the model’s :meth:`compute` method, the model processes the operation and tracks the results internally.

      Once the result is calculated, it's returned to the controller.  
      The controller then tells the view: “Here’s the result, go show it.”

      That’s it — the controller is the bridge. The view handles UI. The model handles logic.  
      The controller connects them both.

      You've now built a complete MVC Analysis Tab — and you're ready to build plugins that go way beyond simple math.

   .. tab:: SimpleCalcView

      **The View: What the User Sees and Does**

      Let’s look at the view (:class:`SimpleCalcView`). 

      .. figure:: /_static/images/SimpleCalcView.png
         :alt: SimpleCalcView layout
         :width: 700px
         :align: center

         SimpleCalc View — user inputs and control buttons.

         
      It defines all the components the user interacts with:

      - A line edit (for the first value)
      - A combo box (for selecting + or -)
      - Another line edit (for the second value)
      - A button labeled “Add calculation”
      - A row underneath to show results
      - Two more buttons at the bottom: **Plot** and **Reset**

      All of this is set up inside the control area using PySide6 layouts.

      .. tip::

         Check ``SimpleCalcView.py`` in :ref:`SimpleCalc` for the exact structure using Qt widgets.

      The view also defines the behavior for those buttons. For example:

      - ``_on_add_calculation()`` handles what happens when the user clicks Add Calculation
      - ``_on_reset()`` clears everything

      These methods are implemented in the view because they need direct access to the input fields.  
      Once the values are ready, the view emits a signal — it does **not** perform the calculation itself.

   .. tab:: SimpleCalcController

      **Signals: Talking to the Controller**

      The view emits three key signals:

      - ``calculate_operation`` — triggered with the left value, operator, and right value
      - ``request_plot`` — user clicked Plot
      - ``request_reset`` — user clicked Reset

      The last two don’t need extra info, but ``calculate_operation`` includes data the user entered.

      The view emits the signal, and the controller listens for it.

      **The Controller: Connecting and Handling**

      Inside the controller’s ``_setup_connections()`` method, we connect those signals to specific handler functions:

      - ``handle_add()`` — for calculations
      - ``handle_plot()`` — to update the graph
      - ``handle_reset()`` — to clear the state

      These handlers live in the controller, because the controller manages the flow:

      - It receives user input via signals
      - It decides what to do (typically by calling the model)

      .. figure:: /_static/images/SimpleCalcInAction.png
         :alt: SimpleCalcView in action
         :width: 700px
         :align: center

         **SimpleCalcView in Action** — This is what users see after adding calculations and plotting results.

That was super simple — Why Do I Even Need Base Classes?
--------------------------------------------------------

Well… ask yourself this:

- Did you ever tell the application where to put your canvas?
- Did you explicitly lay out your control panel?
- Did you even create the canvas yourself — do you even know what a canvas is?

Exactly. You didn’t — and you didn’t have to.

All those low-level details — like initializing a ``matplotlib`` canvas, embedding it into the layout, handling signals, making sure your tab even shows up — that’s all handled by the base classes and the MVC structure.

You don’t need to write that boilerplate. You don’t even need to fully understand it.

But you **do** need to respect it.

.. admonition:: Pro Tip

   Take the time to read the functions defined in the base class that best fits your needs.  
   They already include useful helpers — and more importantly, they let your plugin work with just a few hundred lines of your own code instead of thousands of lines of infrastructure.

So yes — base classes do the heavy lifting behind the scenes.

But this manual explains the parts that do concern you — and believe me, you’ll be glad you read and remember them.

.. toctree::
   :maxdepth: 1

   simpleCalc_code
