=====================================
Welcome to Poriscope's documentation!
=====================================

:mod:`poriscope` is a modular analysis package for nanopore data that can be easily extended through user-supplied plugins that conform to the poriscope API. It is both a graphical desktop app that facilitates most common solid-state nanopore analysis tasks, and a set of python objects that can be used to build custom workflows in your own python scripts. This documentation package provides complete guides for users who want to analyze nanopore data, developers who want to contribute plugins to the :mod:`poriscope` repository, and a complete set of API references. 

If you are interested in contributing to :mod:`poriscope`, `fork the repository <https://github.com/TCossaLab/poriscope/fork>`_ and use the guides below to get started. 

:mod:`poriscope` is an actively developed community project. If you find bugs, or if you have questions that are not anwered in this guide, feel free to reach out to the `TCossaLab <https://www.tcossalab.net/contact_us/>`_ or `submit an issue <https://github.com/TCossaLab/poriscope/issues>`_ with the details. 

.. toctree::
	:maxdepth: 2
	:caption: User Manuals:
   
	utils/user_manuals/user_guide/index
	utils/user_manuals/plugins_manual/plugin_manual_index
	
.. toctree::
	:maxdepth: 2
	:caption: Base Classes:
   
	autodoc/metaclasses/metaclasses_index
	
.. toctree::
	:maxdepth: 2
	:caption: Plugins:
	
	autodoc/plugins/plugins_index

.. toctree::
	:maxdepth: 2
	:caption: Signals:
	
	signals/signals_index
	
.. toctree::
	:maxdepth: 2
	:caption: Logging Decorators:
   
	utils/loggers_index

	
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
