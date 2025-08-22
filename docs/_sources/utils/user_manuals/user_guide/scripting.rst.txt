.. _scripting:

Scripting with Poriscope
========================

While poriscope provides an :ref:`easily extensible<build_frontend_plugin>` graphical interface that makes it easy to analyze data, you do not need to use the graphical interface at all in order to get the full benefit of poriscope. The GUI is great for exploring data and working with experiments with up to ~10 channels, but in cases where you eed to do batch analysis on a large number of experiments or are working with a large number of channels, it is likely more efficient to write custom workflow scripts, and only engage with the GUI for :ref:`postprocessing and visualizing<metadata-tab>` of the fits. In such cases, all of the :ref:`backend data plugins<plugins_index>` (except for analysis tabs) can be used as standalone python objects in custom analysis pipelines.

In this tutorial, we walk you through writing a custom script that reproduces the full poriscope analysis workflow, from reading raw data to loading a database of fitted event metadata.

.. note::
    Throughout this tutorial we only use those parts of the API that are necessary for a bare-bones analysis workflow, but there are lots more operations that can be done with the plugins we will demonstrate. For a full API reference, see the Public Methods section of each entry in the list of :ref:`metaclasses_index`


Setting up our workspace
------------------------

First, we need to import all the plugins we are going use. For this example we'll take the following plugins, but you can swap out any plugin of the appropriate base class for your own analysis, as long as you take care to update the required settings later in the script. We will also import the logger and configure it to only give us warning-level output.

.. code:: python

    from poriscope import (
                            ABF2Reader,             #inherits from MetaReader
                            BesselFilter,           #inherits from MetaFilter
                            ClassicBlockageFinder,  #inherits from MetaEventFinder
                            SQLiteEventWriter,      #inherits from MetaWriter
                            SQLiteEventLoader,      #inherits from MetaEventLoader
                            CUSUM,                  #inherits from MetaEventFitter
                            SQLiteDBWriter,         #inherits from MetaDatabaseWriter
                            SQLiteDBLoader          #inherits from MetaDatabaseLoader
                          )
    import logging
    logging.basicConfig(level=None)

    logging.basicConfig(level=None)
    formatter = logging.Formatter(
            "%(asctime)s: %(levelname)s: %(threadName)s(%(thread)d): %(name)s: %(message)s"
        )

    #log at level WARNING
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)

    #log to the console for simple debugging
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(formatter)
    root_logger.addHandler(consoleHandler)

.. note::
    Poriscope uses the python logging module for error handling and information exchange with the user. If you do not configure the logger properly, it is likely that errors will pass silently, making it much more difficult to debug. The logging configuration above will suffice for the vast majority of scripting tasks. We suggest using log level``WARNING`` in most cases. ``DEBUG`` mode can be used for the obvious purpose, but the density of logged output will significantly slow down execution of your script.


Loading raw data
----------------

When using plugins in scripting mode, instantiation proceeds in two steps:

1. Create an instance of the plugin and (optionally) print out its empty settings dictionary to learn what settings you must supply to it
2. Fill in and apply the settings dictionary to the plugin instance

We will print out the settings for the first plugin to illustrate how it is done, and skip that step for subsequent ones.

.. code:: python

    raw_data = ABF2Reader()

    data_settings = raw_data.get_empty_settings(standalone=True) #stadnalone=True tells our plugin  that it is not part of a GUI

    #print the settings dict:
    for key, value in data_settings.items():
        print(key)
        for k, v in value.items():
            print(f'{k}: {v}')


    #clearly, data settings have only a single settings key "Input File", for which we must add a "Value"  keyword to the sub-dictionary:
    data_settings["Input File"]["Value"] = "<<Path to your ABF input file>>"

    # apply the settings
    raw_data.apply_settings(data_settings)


    # we can print out a brief report on the channels to check that everything worked well:
    print(raw_data.report_channel_status(init=True))

.. note::

    It is possible to supple the settings dict directly to the class constructor if you prefer, in which case you can skip step 2. This just requires that you have your settings dict ready to go and properly formatted. Doing it in two steps gives you the option to print out the required settings in cases where you are using a new plugin type and are unsure of the settings (and haven't read the docs for that plugin, in which case this note probably won't help you either).

Create a filter
---------------

Before trying to find events, we will probably need a low-pass filter. For this tutorial we'll use a Bessel filter. Make sure you update the cutoff to work with your own data!

.. code:: python

    data_filter = BesselFilter()
    filter_settings = data_filter.get_empty_settings()
    filter_settings["Cutoff"]["Value"] = 250000.0
    filter_settings["Samplerate"]["Value"] = raw_data.get_samplerate() #pull the sampling rate directly from the reader plugin we already instantiated
    data_filter.apply_settings(filter_settings)

.. note::

    If you are working with multiple datasets with different sampling rates, be sure to create dedicated filter objects for each one. Bessel filters in particular require a samplerate parameter that may result in issues if applied to a dataset with a mismatched sampling rate. The plugin will not check this for you.

Finding events
--------------

Next, we must create an eventfinder object that is associated to our data reader.

.. code:: python

    # create an event finder
    event_finder = ClassicBlockageFinder()
    event_finder_settings = event_finder.get_empty_settings(standalone=True)
    event_finder_settings["MetaReader"]["Value"] = raw_data  # tell it where to find the raw data in which to find events
    event_finder_settings["Threshold"]["Value"] = 1000.0
    event_finder_settings["Min Duration"]["Value"] = 10.0
    event_finder_settings["Max Duration"]["Value"] = 10000.0
    event_finder_settings["Min Separation"]["Value"] = 10.0
    event_finder.apply_settings(event_finder_settings)

This eventfinder is now locked to our current reader and will only pull data from that reader. If you need ot analyze multiple raw datasets, you would need an additional eventfinder object for each one. Note that we have not locked the filter object to either the reader or the eventfinder. Filters are intended to be mixed and  matched as needed and are not specific to any one dataset.

We now have everything we need to find events in our dataset. To actually find events, we must

1. Create the filter function we will use to preprocess data
2. Create a ``generator`` object for each channel in our eventfinder that will loop over all the data in that channel and flag events for us while reporting progress so that we can keep track of it
3. Actually loop over the generator

.. note::

    In python, a generator is an object that essentially wraps a repeated operation such that every iteration of that operation returns some sort of feedback to the calleer. In this case, the generator iterates through the data one second at a time, and at each iteration  reports progress through the file. This provides some ongoing feedback to the user (and to the poriscope GUI, when it is used there) that the operation is still continuing and has not frozen. If you don't care to see the output and are content to wait, you can always simply ignore the output in the examples that follows.

.. code:: python

    channels = event_finder.get_channels()

    for channel in channels:
        print(f"Finding events in channel {channel}")
        # eventfinders need a channel argument, a list of (start, end) pairs to set which parts of the data to look at, the length in second of the chunk of data to load, and the function to use to filter the data
        # this  particular eventfinder is threadsafe by channels so you could also do this in parallel by channel, but for simplicity we are doing it serially in this example.
        # [(0,0)] for start, end means to just read the whole channel
        eventfinder_generator = event_finder.find_events(
            channel, [(0, 0)], 1.0, data_filter.filter_data
        )
        while True:
            try:
                print(next(eventfinder_generator)) #the value returned here is a fraction 0-1 showing progress over the data in the given channel. Each call to next() advances the eventfiunder 1 second through the data.
            except StopIteration:
                # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
    print(event_finder.report_channel_status())

.. note::

    Using a filter with a plugin as in the above example involves passing in the actual function (``data_filter.filter_data``) to the generator as an argument to be repeatedly applied as the generator progressed. If you were using the filter directly on an array of data, you would instead call ``data_filter.filter_data(data)`` as one would intuitively expect

Saving an event database
------------------------

Once this loop is complete, our eventfinder will have flagged and built an internal list of all the locations at which events occurred according to your settings, but it has not saved or printed them, yet. To save them, we must create a writer object that links to an eventfinder that has completed its task in the loop above, and write a database of the events it found to disk for later analysis. As with the eventfinding step, writing to a database involves using a generator to iterate through the events found and write them to disk. As always, replace the values here with ones appropriate to your data.

.. code:: python

    # Now that we have found all our events we need to write them to a database
    writer = SQLiteEventWriter()
    writer_settings = writer.get_empty_settings(standalone=True)
    writer_settings["MetaEventFinder"]["Value"] = event_finder
    writer_settings["Conductivity"]["Value"] = 10.0
    writer_settings["Voltage"]["Value"] = 200.0
    writer_settings["Membrane Thickness"]["Value"] = 10.0
    writer_settings["Experiment Name"]["Value"] = "script_demo"
    # replace this with your own output file target
    writer_settings["Output File"]["Value"] = "<<Your output file path>>/<<your database name>>.sqlite3"
    writer.apply_settings(writer_settings)

    # writing to a database is a serial operation, and also proceeds by generator

    for channel in channels:
        print(f"Writing data for channel {channel}")
        # eventfinders need a channel argument, a list of (start, end) pairs to set which parts of the data to look at, the length in second of the chunk of data to load, and the function to use to filter the data
        # you could also do this in parallel by channel
        # [(0,0)] for start, end means to just read the whole channel
        writer_generator = writer.commit_events(channel)
        while True:
            try:
                print(next(writer_generator))
            except StopIteration:
                # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(writer.report_channel_status())

.. note::
    The plugin above writes to an sqlite3 format. You can view the resulting file structure using the :mod:`sqlite3` module in python, or you can open it directly using a program like the `DB Browser for SQLite <https://sqlitebrowser.org/>`_. We encourage you to familiarize yourself with the structure of this database, as it will be useful in your own scripting work in case you want to do custom analysis from here.

This point in the script represents completion of the operation of the :ref:`RawDataView` plugin if you were using the poriscope GUI.

Loading an event database
-------------------------

To proceed further takes us into the realm of the :ref:`EventAnalysisView` plugin, which begins by loading the database that we just wrote. We will continue scripting, but you could pass to the GUI at this point if you wanted to.

.. code:: python

    # next up, we load the event database we just wrote
    event_loader = SQLiteEventLoader()
    loader_settings = event_loader.get_empty_settings(standalone=True)
    loader_settings["Input File"]["Value"] = "<<Your output file path>>/<<your database name>>.sqlite3"
    event_loader.apply_settings(loader_settings)
    print(event_loader.report_channel_status(init=True))

You should see printed a message reporting the number of events in each channel that is consistent with what was written in the previous step.

.. note::

    An obvious question to ask is "why not have event loader hook directly into event finders instead of bothering with the step of writing to disk?". This is a design choice predicated on the idea that as nanopore datasets get larger and larger there will be a need to compress data on disk, and event writers throw out unnecessary baseline, reducing the size of datasets by a factor of up to 1000 compared to the raw data itself in some cases. It also allows modularity in workflows: a user to separate identification of interesting events from the fitting step, so that if fitting improves down the road, it is not necessary to repeat the entire workflow from scratch, without requiring the original massive dataset as the basis for updated analysis.

Fitting events
--------------

Now we get to the main challenge: given our nanopore events, how do we extract physical insight from them. Poriscope offers several options, and here we demonstrate use of CUSUM, which you may be familiar with from MOSAIC or previous work from this lab. Just like with event finding, fitting proceeds through the use of generators that report progress en route. CUSUM, like most plugins that read data, is threadsafe, but we demonstrate serial operation here for simplicity.

.. code:: python

    fitter = CUSUM()
    fitter_settings = fitter.get_empty_settings(standalone=True)
    fitter_settings["MetaEventLoader"]["Value"] = event_loader
    fitter_settings["Max Sublevels"]["Value"] = 10
    fitter_settings["Rise Time"]["Value"] = 10.0
    fitter_settings["Step Size"]["Value"] = 1000.0
    fitter.apply_settings(fitter_settings)

    # we could run this one in parallel in principle but for demo purposes we will keep it simple

    # #we already know the channels, but let's double check on principle'
    channels = fitter.get_channels()

    for channel in channels:
        print(f"Fitting events for channel {channel}")
        fitter_generator = fitter.fit_events(
            channel, data_filter=data_filter.filter_data
        )
        while True:
            try:
                print(next(fitter_generator))
            except StopIteration:
                # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(fitter.report_channel_status())

In the event that fits fail or events are rejected for any reason, the report printed at the end will detail why it happened, assuming the person who built the plugin complied with the appropriate guidelines when doing so.

Saving event metadata
---------------------

At this point, the events are fitted and the ``fitter`` object has stored the metadata for each event, but it has not been saved anywhere. To save, we need to create a database writer object that will save our metadata to a predefined format, in this case :mod:`sqlite3` again. Note that this is a serial operation - writing to an :mod:`sqlite3` database is not threadsafe.

Of particular note here is that it is possible to write many experiments to a single sqlite3 database. If you have a previously written metadata database and you want to append to it a new experiment, simply give the existing filename of the database as the output file. The :ref:`SQLiteDBWriter` object can house as many experiments, each with as many channels and events within channels, as need be. Doing so makes it possible to analyze replicates of experiments together in one place using standard SQL queries.

.. code:: python

    metadata_writer = SQLiteDBWriter()
    metadata_writer_settings = metadata_writer.get_empty_settings(standalone=True)
    metadata_writer_settings["MetaEventFitter"]["Value"] = fitter
    metadata_writer_settings["Conductivity"]["Value"] = 10.0
    metadata_writer_settings["Voltage"]["Value"] = 200.0
    metadata_writer_settings["Membrane Thickness"]["Value"] = 10.0
    metadata_writer_settings["Experiment Name"]["Value"] = "script_demo"
    metadata_writer_settings["Output File"]["Value"] = "<<your output path>>/<<your database name>>.sqlite3"
    metadata_writer.apply_settings(metadata_writer_settings)

    # writing to a database is a serial operation

    for channel in channels:
        print(f"Writing metadata for channel {channel}")
        metadata_writer_generator = metadata_writer.write_events(channel)
        while True:
            try:
                print(next(metadata_writer_generator))
            except StopIteration:
                # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(metadata_writer.report_channel_status())

The printed report at the end will detail any problems that occurred. This brings us to the end of the tasks that are covered by the :ref:`EventAnalysisView` tab in the :mod:`poriscope` GUI

Loading event metadata
----------------------

Having written our metadata, we now need to interact with it. For this final task, we use the paired :ref:`SQLiteDBLoader` plugin:

.. code:: python

    metadata_loader = SQLiteDBLoader()
    metadata_loader_settings = metadata_loader.get_empty_settings(standalone=True)
    metadata_loader_settings["Input File"][
        "Value"
    ] = "C:/Users/kbriggs/OneDrive - University of Ottawa/Documents/data/Mock Server/Script Demo/script_demo_event_metadata.sqlite3"
    metadata_loader.apply_settings(metadata_loader_settings)
    print(metadata_loader.report_channel_status(init=True))

From here, we have at our disposal the full :ref:`MetaDatabaseLoader` API with which to interact with the database. You can also use :mod:`sqlite3` or the `DB Browser for SQLite <https://sqlitebrowser.org/>`_ to interact more directly with the database if you prefer. Poriscope is quite flexible with respect to operations performed on this database, and will allow creation of new columns within existing tables as long as the relationships between the various tables are respected. You can find a full database schema in the :ref:`MetaDatabaseWriter` source code.

.. note::

    In case you are unfamiliar with SQL syntax, :ref:`MetaDatabaseLoader` subclasses have the :py:meth:`~poriscope.utils.MetaDatabaseLoader.MetaDatabaseLoader.get_llm_prompt` method that will return a string that describes the database schema in the form an LLM can understand. Pasting this string into your favorite LLM will then allow you to ask it to construct SQL queries for you. Take care to review its output and take it as an opportunity to learn SQL rather than trusting it blindly. LLMs in our experience get it right about 80% of the time.

