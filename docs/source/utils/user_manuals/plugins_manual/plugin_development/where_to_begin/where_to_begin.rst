Where to Begin
==============

First decide which kind of plugin you are building:

- **An analysis tab** is a new tab in the window: a Model, a View, a Controller and a
  controls panel. Generate one with ``python scripts/new_plugin.py AnalysisTab MyTab``,
  then see :ref:`build_frontend_plugin`.
- **A data plugin** reads, filters, finds, fits, writes or loads data, with no UI of its
  own: a single class that subclasses one of the nine data-plugin base classes. Generate
  one with ``python scripts/new_plugin.py <base> MyPlugin`` (``--list`` shows the bases),
  then see :ref:`build_data_plugin`.

