FAQ
===

In this section, we cover frequently asked questions and show you how to resolve them. These are issues users often encounter in day-to-day use, especially when working across multiple datasets or returning to a project after a break.

I loaded a file, but nothing appeared. What happened?
-----------------------------------------------------

- This often happens if you closed the plugin configuration dialog without confirming.
  Make sure you clicked :guilabel:`OK` (not :guilabel:`Cancel`) after selecting your file and settings.
- Confirm you’ve selected a valid **channel** and clicked :guilabel:`Update Trace` to display the signal.

Fitting says "Fitting not started", or shows another dataset's events.
------------------------------------------------------------------------

An event fitter only ever reads the **event loader** it was created on. If the loader
selected in the Event Analysis tab is a different one, **Fit Events** is refused with a
message naming both. Select the fitter you created on that loader, or the loader that
fitter uses.

I clicked :menuselection:`Analysis -> New Analysis Tab -> EventAnalysisController` or :menuselection:`RawDataController`, but nothing changes.
----------------------------------------------------------------------------------------------------------------------------------------------

Poriscope lets you use the top menu to **open** a plugin tab the first time only.  
After it’s opened, switch back to any analysis view from the left sidebar:

:menuselection:`All Analysis Tabs` → select the tab you want.

A database will not load into the Metadata or Event Analysis tab.
-----------------------------------------------------------------

You may be loading the **wrong type** of database for that tab. Both kinds are SQLite files,
and both writers offer the same extensions (``.sqlite3``, ``.db``, ``.sqlite``):

- **Raw event database** - created in the **Raw Data** tab with :guilabel:`Commit Events`.
  Contains **unfitted** events. Load it in the **Event Analysis** tab for fitting.
- **Fitted event database** - created in the **Event Analysis** tab with
  :guilabel:`Commit Events`. Contains **fitted events and metadata**. Load it in the
  **Metadata**, **Clustering** or **Protein** tab.

.. tip::

   Name databases so the two kinds cannot be confused, e.g.::

      my_sample_events_raw.sqlite3      # created in the Raw Data tab
      my_sample_events_fitted.sqlite3   # created in the Event Analysis tab

Is Linux supported?
-------------------

Poriscope is currently beta tested on Linux through an Ubuntu VM. As a result, certain UI behaviors may differ from the native Windows experience, particularly around popup windows, which rely on compositor effects that virtual GPU drivers handle inconsistently.

Functionality is in place, and Linux-specific fixes will continue to be refined as support matures.

.. _tutorial_dataset:

Where can I find the data used in the tutorials?
-------------------------------------------------

The data used in the YouTube tutorial series is archived on the Federated Research Data Repository (FRDR):

**DOI:** `10.20383/103.01695 <https://doi.org/10.20383/103.01695>`_

The full dataset is ~9.92 GB. Individual ``.log`` and ``.json`` files can be downloaded separately from the FRDR page if you only need specific channels.

The deposit also contains the reference SQLite databases used in the tutorial (``.sqlite3``), and a ``README.txt`` giving the parameters needed to regenerate them from the recordings.
