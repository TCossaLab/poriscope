Example Usage: editing plugin settings from a view
---------------------------------------------------

.. code-block:: python

   @log(logger=logger)
   def handle_edit_triggered(self, metaclass: str, key: str) -> None:
      # A tuple of the arguments expected by DataPluginController.edit_plugin_settings,
      # whose signature is (self, metaclass: str, key: str) -> None
      call_args = (metaclass, key)
      self.data_plugin_controller_signal.emit(
         metaclass, key, "edit_plugin_settings", call_args, "", ()
      )

This is the real shape used by ``MetaView``, and it shows the two things worth copying:

#. ``call_args`` is built to match the *target's* signature — here two positional
   ``str`` arguments — and is a genuine tuple. Note that the same ``metaclass`` and
   ``key`` appear twice: once in the first two signal arguments, where they are only
   logged, and once inside ``call_args``, where they are the actual arguments to
   ``edit_plugin_settings``. This signal does not use the first two to find anything.

#. The return function is ``""``. ``edit_plugin_settings`` drives the settings dialog
   itself and there is nothing to hand back, so no callback is registered and
   ``ret_args`` is empty. Supplying a callback is optional on this path and usually
   unnecessary.

``delete_plugin`` is emitted identically, with ``"delete_plugin"`` in place of
``"edit_plugin_settings"``.

Detailed Explanation
~~~~~~~~~~~~~~~~~~~~~

This function in a specific view, needs to edit the “selected” plugin settings. 

#. **User Interaction**: The user interacts with a dropdown menu in the ``RawDataControls`` widget located within the ``RawDataView``. This dropdown menu allows the user to select a PluginKey which uniquely identifies a plugin.

#. **Data Fetching**: The ``RawDataControls`` widget reads a *JSON* file to fetch current plugins' *metadata*, including metaclass and pluginKey (identifying which plugin the user wishes to manipulate). 

#. **Signal Emission**: Upon selection and info button activation within the ``RawDataControls``, a signal is emitted. This signal triggers the data_plugin_controller_signal within ``RawDataView``. The purpose of this signal is to initiate the plugin editing process via a dedicated function ``edit_plugin_settings``.

#. **Function Invocation**: The ``edit_plugin_settings`` function is called. This function is designed to manage the editing of plugin settings effectively and is structured following abbr: **MVC** (Model-View-Controller) principles:

    - **Model**: Handles data manipulation and business logic -> get,set,unregister,etc

    - **View**: Manages the presentation and user interaction layer -> Edit Settings

    - **Controller**: Acts as an intermediary, coordinating actions between the model and the view.

#. **View Interaction**: The editing interface for the plugin settings is handled within the abbr: DPView (DataPluginView). This approach prevents the unnecessary spread of data across components that do not require direct access to it, ensuring that each plugin's settings are isolated and managed within a controlled environment.

#. **Data Update and Signal Processing**: Post interaction in the ``DPView``, methods are executed to update the plugins based on the changes made. These updates are propagated back to the system, ensuring all components that depend on these plugins are aware of the new settings.

.. note::

    **It would not be possible to use the global signal to perform this action**:
    
    #. Using a global signal for specific plugin settings adjustments is inefficient as it involves complex routing that doesn't terminate at the ``DPController`` but extends to individual plugin instances.
        
    #. The ``data_plugin_controller_signal`` offers a streamlined pathway for direct communication with the ``DPController``, enabling:
        - **Direct Action Execution**: Immediate effect on plugin settings without traversing through multiple (without this signal, single signals would have to be scaled up to the ``MainController``, then access the ``DPController``) and specific signals depending on the particular instance to be affected/data retrieved.
           
        - **Optional Return Handling**: The signal supports an optional return function, enhancing flexibility by allowing operations that do not require post-execution feedback (edit plugins does not need to trigger another action in the view, could do it, but is not necessary, it just gets the updated data.).

.. tip::

    - The ``data_plugin_controller_signal`` in the ``MainController`` facilitates targeted communication between **Analysis Tabs** and the ``DataPluginController`` -> It optimizes plugin management by focusing on centralized interactions

    - Using this dedicated signal prevents the inefficiencies of cascading requests through the system's hierarchy— a process that would typically scaling up to **Main MVC** and down to the **DPMVC** manually-resulting in delayed actions. This method not only simplifies maintenance but also supports easier scalability
