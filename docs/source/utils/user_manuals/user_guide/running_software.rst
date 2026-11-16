.. _running_software:

Running the Software
====================

This page is a **verification walkthrough**, not a feature reference: concrete inputs in
the **Raw Data** tab with known outputs, so you can confirm that Poriscope is installed
and working. It uses the same dataset as the YouTube tutorial series, and follows
`Part 2: Section 2 - Exploring the Raw Data Tab
<https://www.youtube.com/watch?v=LdFBJ6Agwhs&t=775s>`_, so you can compare your results
with the video. For what each control does, see :ref:`rawdata-tab`.

Start Poriscope (see :ref:`getting_started_general_user`) and open a Raw Data tab with
**Analysis → New Analysis Tab → RawDataController**.

Loading Data
------------

1. Click the **➕** beside **READER**.
2. Select **ChimeraReader20240501**.
3. Click **Select Input File** and choose any ``.log`` file from the tutorial dataset
   (see :ref:`tutorial_dataset`).

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

If needed, add a filter with the **➕** beside **FILTER** before event detection. The
tutorial series uses a **BesselFilter** with these settings:

.. image:: /_static/images/filter_settings.png
   :alt: Bessel filter parameters
   :align: center

Event Finding
-------------

1. Once you are satisfied with the filtered trace, click the **➕** beside **EVENTFINDER**.
2. Select **ClassicBlockageFinder**.
3. Click **OK**.

.. image:: /_static/images/finder_settings.png
   :alt: EventFinder parameters
   :align: center

Channel Selection Notes
-----------------------

- Select the channel (or channels) on which you want to find events.
- If you select **Channel 2**, event detection will be incomplete (Channel 2 is empty)
- To restrict the time range used for event detection, use the **⏱** button beside
  **Find Events**.

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

1. Add a writer with the **➕** beside **WRITER**.
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