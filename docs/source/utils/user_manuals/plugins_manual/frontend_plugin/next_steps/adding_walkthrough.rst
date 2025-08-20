.. _AddWalkthrough:

Adding a Walkthrough to Your Custom MVC Plugin
================================================

This guide explains how to integrate a step-by-step walkthrough into your custom MVC plugin for Poriscope. The walkthrough system helps users understand how to interact with your plugin's interface.

Overview
--------

To enable walkthrough support in your plugin, you'll:

1. Inherit from `WalkthroughMixin` in your custom `View` or `Dialog` class.
2. Implement two key methods:

   * `get_current_view()`
   * `get_walkthrough_steps()`

Step-by-Step Instructions
--------------------------

1. **Inherit from WalkthroughMixin**

   In your custom view or dialog, inherit from `WalkthroughMixin`:

.. code-block:: python

    class MyCustomView(QWidget, WalkthroughMixin):
        def __init__(self, ...):
            super().__init__(...)
            self._init_walkthrough()
            self.init_ui()

2. **Implement get_current_view()**

   This should return a unique identifier string for your view. Make sure it matches the convention needed for the file to get detected my the app (MyCustomView)

.. code-block:: python

    def get_current_view(self):
        return "MyCustomView"


3. **Implement get_walkthrough_steps()**

   This method returns a list of tuples, each describing a walkthrough step:

.. code-block:: python

    def get_walkthrough_steps(self):
        return [
            ("Step Title", "Instructional message", "MyCustomView", lambda: [self.some_widget]),
            ("Another Step", "Another message.", "MyCustomView", lambda: [self.another_widget]),
        ]

Each tuple contains:

   * A label (str)
   * A description (str)
   * The view name (str, must match `get_current_view()`)
   * A lambda returning a list of widgets to highlight

4. **Trigger the Walkthrough**

Once you have followed the steps outlined above, Poriscope will automatically detect your walkthough and run it whenever you are in that view and click Help->Tutorial.


Best Practices
--------------------------

* Keep steps short and descriptive.
* Use `QTimer.singleShot(0, ...)` if needed to delay `dialog.show()` for smoother transitions.


Adding Walkthrough to Dialogs (Optional)
-----------------------------------------

Although walkthroughs were designed with views primarily in mind, you can extend walkthrough support to dialogs like custom configuration windows.

.. note::

   This pattern is **not recommended** unless the dialog plays a critical role in your plugin's setup workflow. Prefer walkthroughs inside main views for consistency.

To enable walkthrough support in a dialog:

.. code-block:: python

   class ClusteringSettingsDialog(QDialog, WalkthroughMixin):
       def __init__(self, ...):
           super().__init__()
           self._init_walkthrough()
           self.init_ui()

       def get_current_view(self):
           return "ClusteringSettingsDialog"

       def get_walkthrough_steps(self):
           return [
               ("Step 1", "Do something important here.", "ClusteringSettingsDialog", lambda: [self.some_widget]),
               ...
           ]

Then, from your view (e.g., `ClusteringView`), you can trigger the walkthrough once the dialog is shown:

.. code-block:: python

   dialog = ClusteringSettingsDialog(...)
   
   if self._walkthrough_active:
       self.logger.info("Launching walkthrough from _handle_clustering_settings()")
       dialog._init_walkthrough()
       dialog.launch_walkthrough()

       if dialog.walkthrough_dialog:
           dialog.finished.connect(lambda _: dialog.walkthrough_dialog.force_close())

   result = dialog.exec()

See Also
---------

* \:ref:`mainview_walkthrough`
* \:ref:`walkthrough_mixin`
