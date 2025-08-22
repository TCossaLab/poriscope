.. _build_data_plugin:

Ready to Build Your Own Data Plugin?
====================================

In many ways data plugins are simpler than frontend plugins, in that they are standalone python elements that exist outside of the MVC context and can be used without the GUI as part of custom workflows. Unlike frontend plughins, data plugins are pure python objects, and are intended to be usable both as part of the poriscope gui and as standalone scripting elements. To make this possible, each type of data plugin has a well-defined common API that must be respected by any user-created plugin, enforced through the use of base classes and tests applied to contributions to the code base, as already explained in :ref:`understanding base classes <understanding_base_classes>`.

To build a data plugin, you must:

1. Create a subclass that inherits from one of the poriscope base classes
2. Save that as a .py file with a filename that exactly matches the name of your subclass
3. Provide an implementation for all abstract classes required by that base classes that respects the API defined in the base class
4. Comply exactly with the API (argument names, order of arguments, and return types) required by the base class

.. note::

	Implementation of a data plugin will feel incomplete - it is! Much of the functionality is held together in the base class itself. All you are doing is filling in the blanks where the poriscope developers cannot reasonable predict how a particular piece of information can be extracted without knowing the specific thing you are trying to build. While not strictly required, we encourage plugin developers to familiarize themselves with all of the functinality in the base class - it may help with your implementation to know how the functions you are filling in are being used, and if you're lucky, you may find a bug that we missed.

As long as the API is respected (order and type of arguments, return type, and any limits on the circumstances in which your plugin should `Raise`), it is sometimes acceptable to override functions that are implemented in the base class. That being said, while we have done our best to predict common behaviors, it is possible that overrides of non-anstract classes will be necessary. If you do, however, be sure that you understand the base class implementation. In many cases, it is strongly suggested that you call ``super().[function_name](...)`` and extend the implementation from there, rather than overriding completely or duplicating code, and never, ever change the arguments, argument types, or return types of public functions.

To assist with quality control, any contributions to the poriscope repository will need to pass our tests and type checks. To assist with this, functions should be decorated with the ``@override`` tag to tell our type checker what to expect, and should have detailed docstrings that explain the you are doing in your function. Plugins will only be added to the repository when fully compliant, but we are happy to help if you get stuck in the process.

.. toctree::
   :maxdepth: 1

   base_data_plugin
   meta_reader
   meta_filter
   meta_event_finder
   meta_event_writer
   meta_event_loader
   meta_event_fitter
   meta_database_writer
   meta_database_loader
   
   
