.. _AddWalkthrough:

Adding a Walkthrough to Your Custom MVC Plugin
================================================

A walkthrough is a sequence of popups that highlight your tab's widgets one at a time when
the user chooses **Help → Tutorial**. An analysis-tab View inherits ``WalkthroughMixin``
through ``MetaView``, which also initialises it, so a View only implements two methods.

1. **Implement get_current_view()**

   Return your View's class name (``MyCustomView``), the name the application uses for
   the page.

.. code-block:: python

    def get_current_view(self):
        return "MyCustomView"


2. **Implement get_walkthrough_steps()**

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
   * The view name (str, must match ``get_current_view()``)
   * A lambda returning a list of widgets to highlight

That is all: Poriscope runs your walkthrough whenever your tab is showing and the user
chooses **Help → Tutorial**.

.. note::

   A walkthrough runs inside your tab only. Poriscope's own guided tour moves through
   Raw Data, Event Analysis, Metadata and Clustering in a fixed order, and a tab you add
   is not part of it, so finishing your walkthrough does not lead on to another tab.
   While it runs, Poriscope refuses to switch to another page and does not open the
   Settings page, the analysis-tabs list or the Help window. The walkthrough ends when
   the user finishes its last step (the button reads Done) or clicks the ✕ on the
   walkthrough dialog. Esc does not dismiss it.


Keep steps short, and use ``QTimer.singleShot(0, ...)`` if a dialog needs to be shown
before its step.

Adding a walkthrough to a dialog
--------------------------------

Do this only when the dialog plays a critical role in your tab's workflow; prefer
walkthrough steps on the View. A dialog is not a ``MetaView``, so it inherits
``WalkthroughMixin`` itself and calls ``_init_walkthrough()`` in its constructor, as
Poriscope's own clustering settings dialog does:

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

Then, from your View (``ClusteringView`` here), launch it when the dialog opens during a
walkthrough:

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

* :ref:`MainView` - the shell view that hosts a tab's walkthrough
* :ref:`walkthrough_mixin` - the mixin's own API reference
