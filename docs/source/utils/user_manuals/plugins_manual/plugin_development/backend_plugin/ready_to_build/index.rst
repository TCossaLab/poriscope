.. _build_data_plugin:

Ready to Build Your Own Data Plugin?
====================================

In many ways data plugins are simpler than frontend plugins, in that they are standalone python elements that exist outside of the MVC context and can be used without the GUI as part of custom workflows. Unlike frontend plughins, data plugins are pure python objects, and are intended to be usable both as part of the poriscope gui and as standalone scripting elements. To make this possible, each type of data plugin has a well-defined common API that must be respected by any user-created plugin, enforced through the use of base classes and tests applied to contributions to the code base, as already explained in :ref:`understanding base classes <understanding_base_classes>`.

To build a data plugin, you must:

1. Create a subclass that inherits from one of the poriscope base classes
2. Save that as a .py file with a filename that exactly matches the name of your subclass
3. Provide an implementation for all abstract classes required by that base classes that respects the API defined in the base class
4. Comply exactly with the API (argument names, order of arguments, and return types) required by the base class

.. _new_plugin_script:

Start From a Generated Skeleton
-------------------------------

You do not have to do any of the four steps above by hand. ``scripts/new_plugin.py``
writes a skeleton that already satisfies all four, and which passes ``ruff``, ``mypy``,
``pydoclint``, the plugin compliance suite and the settings-schema check *before you have
filled in a single method*. Every failure you see after that is one you introduced, which
is a much easier position to work from than discovering a signature mismatch when a
reviewer runs the suite on your pull request.

Run it with no arguments and it will ask what you are building:

.. code-block:: bash

   python scripts/new_plugin.py

Or say so directly. The first argument is what you are subclassing and the second is the
name of your plugin:

.. code-block:: bash

   python scripts/new_plugin.py --list                     # show what you can subclass
   python scripts/new_plugin.py MetaEventFinder MyFinder   # a new plugin from a base class
   python scripts/new_plugin.py MetaFilter MyFilter --user # into your user plugin folder

There are two things you might be doing, and the tool covers both.

**A new plugin** subclasses one of the eight base classes and gets a stub for every
abstract method that base declares — between 6 and 21 of them depending on the family.
``--list`` prints the count for each, which is worth looking at before you commit to one.

**A variant of a plugin that already ships** subclasses that plugin instead, and inherits
a fully working implementation. Name the methods you want to change with ``--override``
and only those are stubbed, each one delegating to ``super()`` so your plugin behaves
exactly like its parent until you start narrowing it:

.. code-block:: bash

   python scripts/new_plugin.py --list ClassicBlockageFinder
   python scripts/new_plugin.py ClassicBlockageFinder MyFinder --override _filter_events

What you get either way is a file in the right folder, named after its class, carrying the
MIT header, with each method's **signature and docstring copied verbatim out of the base
class**. That copying is not a convenience — the compliance suite compares signatures for
exact equality and generic annotations such as ``Tuple[List[int], List[int], bool]`` by
equality too, so retyping one by hand is a coin flip. The docstrings come along because
they are the contract: what your method is handed, what it must give back, and what it
must raise.

Methods where doing nothing is a legitimate implementation are stubbed with ``pass``;
methods that owe a return value raise ``NotImplementedError``. That split is deliberate,
and it means your plugin **instantiates and appears in the Poriscope menus immediately** —
you can confirm the plumbing works before writing any of the algorithm.

.. note::

   ``get_empty_settings`` is stubbed for you even though seven of the eight families do
   not declare it abstract, and the stub calls ``super()`` before adding anything. This
   matters more than it looks: those seven base implementations seed mandatory keys — the
   ``MetaReader`` an event finder depends on, the ``Output File`` a writer needs — and an
   override that forgets the ``super()`` call silently drops them. Nothing checks for it.

.. warning::

   Plugin names must be unique across **every** family, not just within one, because the
   menus and the plugin key registry both rely on that. The generator refuses a name that
   is already taken; without it, the first sign of a clash is an error dialog at app
   startup telling you your file was ignored.

The generator covers data plugins only. Analysis tab plugins are a
Controller/Model/View triad rather than a single file — see
:ref:`build_frontend_plugin` for those.

.. important::

   One decision is easy to overlook and expensive to get wrong: Poriscope runs **one worker
   thread per channel**, so several threads can call into your plugin instance at once. If
   yours cannot survive that, it has to say so. Read
   :ref:`serial_channel_operations` before you finish your implementation.

.. note::

	Implementation of a data plugin will feel incomplete - it is! Much of the functionality is held together in the base class itself. All you are doing is filling in the blanks where the poriscope developers cannot reasonable predict how a particular piece of information can be extracted without knowing the specific thing you are trying to build. While not strictly required, we encourage plugin developers to familiarize themselves with all of the functinality in the base class - it may help with your implementation to know how the functions you are filling in are being used, and if you're lucky, you may find a bug that we missed.

As long as the API is respected (order and type of arguments, return type, and any limits on the circumstances in which your plugin should `Raise`), it is sometimes acceptable to override functions that are implemented in the base class. That being said, while we have done our best to predict common behaviors, it is possible that overrides of non-anstract classes will be necessary. If you do, however, be sure that you understand the base class implementation. In many cases, it is strongly suggested that you call ``super().[function_name](...)`` and extend the implementation from there, rather than overriding completely or duplicating code, and never, ever change the arguments, argument types, or return types of public functions.

To assist with quality control, any contributions to the poriscope repository will need to pass our tests and type checks. To assist with this, functions should be decorated with the ``@override`` tag to tell our type checker what to expect, and should have detailed docstrings that explain the you are doing in your function. Plugins will only be added to the repository when fully compliant, but we are happy to help if you get stuck in the process.

.. tip::

   "Our tests and type checks" means something specific and checkable, not a vague
   standard a reviewer applies by eye. See :ref:`quality_control` for exactly what
   runs (formatting, typing, docstring consistency, and plugin interface compliance
   testing), and work through :ref:`pre_pr_checklist` before you open your pull
   request — it will save you a review round-trip.

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
   serial_channel_operations
   
   
