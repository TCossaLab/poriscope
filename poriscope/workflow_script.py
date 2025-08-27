# MIT License
#
# Copyright (c) 2025 TCossaLab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Contributors:
# Kyle Briggs
# Alejandra Carolina González González

## This script replicates a basic poriscope workflow in script form,
## In this model, all parameters to plugins must be defined up front,
## This allows single-click run-through of an entire analysis pipeline
## The cost is that it all needs to be set up in advance

import logging

from poriscope import (
    CUSUM,
    ABF2Reader,
    BesselFilter,
    ClassicBlockageFinder,
    SQLiteDBLoader,
    SQLiteDBWriter,
    SQLiteEventLoader,
    SQLiteEventWriter,
)

logging.basicConfig(level=None)

formatter = logging.Formatter(
    "%(asctime)s: %(levelname)s: %(threadName)s(%(thread)d): %(name)s: %(message)s"
)

# log at level WARNING
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

# log to the console for simple debugging
consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(formatter)
root_logger.addHandler(consoleHandler)


def main():
    # create a reader object to load our data file. Here we use ABF2Reader, but any other type could be substituted
    raw_data = ABF2Reader()

    # pull the settings dict. Standalone=True is needed to tell it that this is in a script and not in the GUI
    data_settings = raw_data.get_empty_settings(standalone=True)
    input_data_file = ""  # replace with the path to your input file
    # print the settings dict:
    for key, value in data_settings.items():
        print(key)
        for k, v in value.items():
            print(f"\t{k}: {v}")

    exit()
    # for this plugin we need only specify the input file location. Replace this example with the location of any file from your dataset
    data_settings["Input File"]["Value"] = input_data_file

    # apply the settings
    raw_data.apply_settings(data_settings)
    # our data reader in ready to be used. See the documentation for a full interface description.
    # We will only use the parts of it that are necessary for this tutorial script here.
    # if you wanted to plot data, you could get some by calling raw_data.load_data(), for example.
    # we can print out a brief report on the channels to check:
    print(raw_data.report_channel_status(init=True))

    # set up a filter object that we will use to filter our data
    data_filter = BesselFilter()
    filter_settings = data_filter.get_empty_settings()
    filter_settings["Cutoff"]["Value"] = 250000.0
    filter_settings["Samplerate"]["Value"] = raw_data.get_samplerate()
    data_filter.apply_settings(filter_settings)

    # create an event finder
    event_finder = ClassicBlockageFinder()
    event_finder_settings = event_finder.get_empty_settings(standalone=True)
    event_finder_settings["MetaReader"][
        "Value"
    ] = raw_data  # tell it where to find the raw data in which to find events
    event_finder_settings["Threshold"][
        "Value"
    ] = 1000.0  # fill in what you think is the correct blockage depth
    event_finder_settings["Min Duration"]["Value"] = 10.0
    event_finder_settings["Max Duration"]["Value"] = 10000.0
    event_finder_settings["Min Separation"]["Value"] = 10.0
    event_finder.apply_settings(event_finder_settings)
    # our eventfinder is ready to use

    # when finding events, we create what is called a generator for each channel.
    # A generator allows us to track progress, since it will process a chunk of data, then tell us how far it has come and wait for us to tell it to proceed. Each cell to next gives us the progress fraction.
    # First, we need to know how many channels there are

    channels = event_finder.get_channels()

    for channel in channels:
        print(f"Find event in channel {channel}")
        # eventfinders need a channel argument, a list of (start, end) pairs to set which parts of the data to look at, the length in second of the chunk of data to load, and the function to use to filter the data
        # you could also do this in parallel by channel
        # [(0,0)] for start, end means to just read the whole channel
        eventfinder_generator = event_finder.find_events(
            channel, [(0, 0)], 1.0, data_filter.filter_data
        )
        while True:
            try:
                print(next(eventfinder_generator))
            except (
                StopIteration
            ):  # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break

    # Now that we have found all our events we need to write them to a database
    event_output_file_path = ""  # replace with the path to where you want your event database file to be written
    writer = SQLiteEventWriter()
    writer_settings = writer.get_empty_settings(standalone=True)
    writer_settings["MetaEventFinder"]["Value"] = event_finder
    writer_settings["Conductivity"]["Value"] = 10.0
    writer_settings["Voltage"]["Value"] = 200.0
    writer_settings["Membrane Thickness"]["Value"] = 10.0
    writer_settings["Experiment Name"]["Value"] = "script_demo"
    # replace this with your own output file target
    writer_settings["Output File"]["Value"] = event_output_file_path
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
            except (
                StopIteration
            ):  # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(writer.report_channel_status())

    # next up, we load the event database we just wrote
    event_loader = SQLiteEventLoader()
    loader_settings = event_loader.get_empty_settings(standalone=True)
    loader_settings["Input File"]["Value"] = event_output_file_path
    event_loader.apply_settings(loader_settings)
    print(event_loader.report_channel_status(init=True))

    # now we need to fit the events
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
            except (
                StopIteration
            ):  # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(fitter.report_channel_status())

    # now we write the fits to a database
    metadata_output_file_path = ""  # replace with the path to where you want your metadata database to be written
    metadata_writer = SQLiteDBWriter()
    metadata_writer_settings = metadata_writer.get_empty_settings(standalone=True)
    metadata_writer_settings["MetaEventFitter"]["Value"] = fitter
    metadata_writer_settings["Conductivity"]["Value"] = 10.0
    metadata_writer_settings["Voltage"]["Value"] = 200.0
    metadata_writer_settings["Membrane Thickness"]["Value"] = 10.0
    metadata_writer_settings["Experiment Name"]["Value"] = "script_demo"
    metadata_writer_settings["Output File"]["Value"] = metadata_output_file_path
    metadata_writer.apply_settings(metadata_writer_settings)

    # writing to a database is a serial operation

    for channel in channels:
        print(f"Writing metadata for channel {channel}")
        metadata_writer_generator = metadata_writer.write_events(channel)
        while True:
            try:
                print(next(metadata_writer_generator))
            except (
                StopIteration
            ):  # once we run out of data to process, generators raise StopIteration, so you can catch that and move on to the next channel
                break
        print(metadata_writer.report_channel_status())

    # finally, you load your database and can then perform SQL or visualization operations at your convenience
    metadata_loader = SQLiteDBLoader()
    metadata_loader_settings = metadata_loader.get_empty_settings(standalone=True)
    metadata_loader_settings["Input File"]["Value"] = metadata_output_file_path
    metadata_loader.apply_settings(metadata_loader_settings)
    print(metadata_loader.report_channel_status(init=True))

    # your analysis code goes here now
    ...


if __name__ == "__main__":
    main()
