Understanding Signals
=====================

Signals are how different parts of Poriscope talk to each other — cleanly, asynchronously, and without tight coupling.

What Is a Signal?
-----------------

In Qt (and in Poriscope), a **signal** is a way to notify that “something happened.” Think of it like shouting a message into a room — anyone listening can choose to respond, but you don’t need to know who they are.

It’s perfect for building modular apps, where components shouldn’t directly depend on one another.

Imagine a Walkie-Talkie System
------------------------------

You’re on a big hike with friends. You don’t shout — you use a walkie-talkie.

- **Channel 1** is used by the whole group (like :ref:`GlobalSignal`) 
- **Channel 2** is just for hikers who deal with maps and routes (like :ref:`DataPluginControllerSignal`)

Now, if you say "Need help!" on Channel 1, anyone can respond.  
If you say "Send new coordinates" on Channel 2, only the navigator listens.

This is exactly how Poriscope uses signals:

- :ref:`GlobalSignal` is shared across all plugins for broad, app-wide communication.
- :ref:`DataPluginControllerSignal` is focused and used to manage data plugin logic specifically.
- Each signal goes through the :ref:`MainController`, which acts like the central relay tower.

Why This Matters
----------------

You don’t want your plugin to *know* who’s listening — you just want to say, “I need the trace data,” and let the system handle the rest.

This approach:

- Keeps your code clean and modular
- Avoids tangled dependencies
- Makes your plugin easier to test, reuse, and debug

So yes — signals may seem abstract at first, but they’re your best friends when building scalable tools in Poriscope.

.. note::

   For in-depth usage and examples, see :ref:`GlobalSignal` and :ref:`DataPluginControllerSignal`.

