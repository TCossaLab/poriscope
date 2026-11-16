.. _build_data_plugin:

Ready to Build Your Own Data Plugin?
====================================

Data plugins are plain Python objects, outside the MVC layer: the same plugin runs in the
GUI and in your own scripts (:ref:`scripting`). Each family has a common API, fixed by its
``Meta*`` base class (:ref:`understanding_base_classes`). A data plugin is a subclass of
one of those bases, saved in a file named exactly after the class, that implements every
abstract method with the base's exact signature: argument names and order, and return
type.

.. _new_plugin_script:

Start From a Generated Skeleton
-------------------------------

You do not have to write that by hand. ``scripts/new_plugin.py`` writes a skeleton that
already satisfies it, and which passes ``ruff``, ``mypy``,
``pydoclint``, the plugin compliance suite and the settings-schema check *before you have
filled in a single method* — a much easier position to work from than discovering a
signature mismatch when a reviewer runs the suite on your pull request.

Two things a fresh skeleton does **not** pass, by design, so do not read that list as a
green test run: its unfilled methods raise ``NotImplementedError``, and the behavioural
conformance suite has no recipe for a plugin it has never seen. Both are expected, and
both say what they want — see :ref:`plugin_conformance_testing`.

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

**A new plugin** subclasses one of the nine base classes and gets a stub for every
abstract method that base declares — between 5 and 20 of them depending on the family.
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

   ``get_empty_settings`` is stubbed for you even though seven of the nine families do
   not declare it abstract, and in those seven the stub calls ``super()`` before adding
   anything. This
   matters more than it looks: those seven base implementations seed mandatory keys — the
   ``MetaReader`` an event finder depends on, the ``Output File`` a writer needs — and an
   override that forgets the ``super()`` call silently drops them. Nothing checks for it.

   The stub then seeds one example parameter, ``"My Parameter"``, marked ``# TODO`` and
   carrying no default. Replace it with the parameters your plugin actually needs, or
   delete it if it needs none. Until you do, conformance correctly reports it as a
   required parameter left unset — and that applies even in the families that otherwise
   need no recipe work at all, so it is the one step no generated plugin can skip.

.. warning::

   Plugin names must be unique across **every** family, not just within one, because the
   menus and the plugin key registry both rely on that. The generator refuses a name that
   is already taken; without it, the first sign of a clash is an error dialog at app
   startup telling you your file was ignored.

The generator also writes analysis tabs, which are a Controller/Model/View triad rather
than a single file — pass ``AnalysisTab`` as the base. See :ref:`new_tab_script`.

.. important::

   One decision is easy to overlook and expensive to get wrong: Poriscope runs **one worker
   thread per channel**, so several threads can call into your plugin instance at once. If
   yours cannot survive that, it has to say so. Read
   :ref:`serial_channel_operations` before you finish your implementation.

Most of a data plugin's behaviour lives in its base class; you fill in only what the base
cannot know about your format or algorithm, so it is worth reading how the base uses the
methods you implement. You may also override a method the base implements, keeping its
arguments, argument types, return type and the circumstances in which it raises; prefer
calling ``super()`` and extending it to replacing it. Decorate every override with
``@override``, and document it - contributions are merged once they pass the checks below,
and we are happy to help if you get stuck.

.. tip::

   The checks are specific, not a standard a reviewer applies by eye. See
   :ref:`quality_control` for exactly what runs (formatting, typing, docstring consistency, plugin interface compliance
   testing, and the behavioural conformance suite, which actually runs your plugin
   against synthetic data), and work through :ref:`pre_pr_checklist` before you open
   your pull request — it will save you a review round-trip.

   Budget for that last one: most new plugins have to add a settings recipe so the
   conformance suite can drive them, and a reader for a format not already covered
   has to add a synthetic writer for it. See :ref:`plugin_conformance_testing` for
   which families need what.

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
   meta_conditioning_loader
   serial_channel_operations
   
   
