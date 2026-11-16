Understanding Signals
=====================

Poriscope's parts talk to each other in two ways, and telling them apart is most
of what you need to know:

- **Ask a question and use the answer: call the plugin.** A tab reaches a data plugin
  only through its Model, ``self.model.call("MetaReader", reader_key, "get_samplerate")``,
  and gets the return value or an exception on that line. You never hold a reference to
  another plugin, and you never import another tab.
- **Announce something and carry on: emit a signal.** A status line, a plugin's state
  changing, or a request to create, edit or delete a data plugin is a typed Qt signal;
  nobody hands you a result.

:ref:`CallingAPlugin` covers both, and what replaced the ``global_signal`` bus that
code written before 2.0.0 may still use.
