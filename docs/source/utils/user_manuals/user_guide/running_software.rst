.. _running_software:

Running the Software
====================

Purpose of the *Running the Software* Section
---------------------------------------------

The user guide already contains detailed instructions describing the
functionality and usage of each tab in the application. In addition, Poriscope
includes an in-application walkthrough (tutorial mode) that can be enabled to
guide users interactively through the interface.

For an overview of the complete workflow, see :ref:`workflow_overview`.
Step-by-step guidance is also available in the interactive tutorial
(:ref:`tutorial`) and in the dedicated sections for each tab, including
:ref:`rawdata-tab`, :ref:`eventAnalysis-tab`, :ref:`metadata-tab`, and
:ref:`clustering-tab`.

The *Running the Software* section serves a different purpose. Rather than
explaining every feature in detail, it provides **concrete inputs and expected
outputs** that allow users to confirm that the software is installed correctly
and functioning as expected.

This section focuses on a practical, end-to-end validation workflow that
primarily exercises the **Raw Data** tab. By following the steps, users should
be able to reproduce specific, known results (for example, a fixed number of
detected events over a given time range), which acts as a sanity check for the
entire processing pipeline.

Relationship to the Tutorial Series
-----------------------------------

The workflow demonstrated here aligns with the **YouTube Tutorial Series –  
Part 2: The Core Workflow**:

https://youtube.com/playlist?list=PLfD-cE09U9g7vCuUbn_Nugd-F30eMWzHB&si=EbuBGlf_gyLCN1R9

Notably, the tutorial series uses the **same dataset throughout all steps** of
the workflow (from raw data loading to event writing). The *Running the
Software* section mirrors this approach by reusing a consistent input file,
making it easier for users to compare their results directly with those shown
in the videos.

In summary, this section is intended as a **verification walkthrough**, not a
feature reference: if users obtain the same intermediate views and final
outputs, they can be confident that Poriscope is operating correctly.

Once you have installed **Poriscope** as described in the installation guide
(see :ref:`getting_started_general_user`), you can launch the application by following the
steps below.

Launching Poriscope
-------------------

1. Open a terminal.
2. Run the following command::

      poriscope

Loading Data
------------

1. Click **Add Reader**.
2. Select **ChimeraReader20240501**.
3. Click **Select Input File** and choose any ``.log`` file from the data
   directory:

   `<insert link placeholder>`

.. image:: /_static/images/reader_settings.png
   :alt: Reader parameters
   :align: center


4. Click **OK**.

You should now see the loaded data in the right-side panel.

.. image:: /_static/images/reader_output.png
   :alt: Loaded data
   :align: center

Visualizing a Trace
-------------------

1. Select a channel.
2. Enter a duration.
3. Click **Update Trace** to visualize the signal.

Filtering the Signal
--------------------

If needed, apply a filter before event detection.

In the tutorial series, a **BesselFilter** is used with the following settings:

.. image:: /_static/images/filter_settings.png
   :alt: Bessel filter parameters
   :align: center

Event Finding
-------------

1. Once you are satisfied with the filtered trace, click **Add Event Finder**.
2. Select **ClassicBlockageFinder**.
3. Click **OK**.

.. image:: /_static/images/finder_settings.png
   :alt: EventFinder parameters
   :align: center

Channel Selection Notes
-----------------------

- Select the channel (or channels) on which you want to find events.
- If you select **Channel 2**, event detection will be incomplete (Channel 2 is empty)
- Refer to *Time Event Finding* if you want to restrict the time range
  used for event detection.

Example
-------

- Using a time range of ``0–50`` on **Channel 3** should return **15 events**.
- After detection, enter ``0–14`` and plot the events.

.. image:: /_static/images/finder_output.png
    :alt: Number of events found
    :align: center

.. image:: /_static/images/plot_events.png
    :alt: Plot events
    :align: center

Writing Results
---------------

To save the results:

1. Add a **Writer**.
2. Enter the parameters as shown below:

   .. image:: /_static/images/writer_settings.png
      :alt: Writer parameters
      :align: center

3. Select the channel you want to save.

If you select **Channel 3**, you should see **15 events** saved in the
right-side panel.

   .. image:: /_static/images/writer_output.png
      :alt: Events written
      :align: center