.. _understanding_base_classes:

Understanding Base Classes
==========================

Every plugin, whether a data plugin or an analysis tab, subclasses one of Poriscope's
``Meta*`` base classes. A base class is not a working plugin on its own: it defines what
every plugin of its kind must provide, and it already carries most of the machinery that
runs one. Methods marked ``@abstractmethod`` are the ones you implement, and Python
refuses to instantiate a subclass that leaves any of them out. The rest come ready to use,
and you override them only when you need to.

``scripts/new_plugin.py`` writes a subclass with every abstract method already stubbed;
see :ref:`build_frontend_plugin` for an analysis tab and :ref:`build_data_plugin` for a
data plugin.
