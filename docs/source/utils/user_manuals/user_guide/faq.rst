FAQ
===

In this section, we cover frequently asked questions and show you how to resolve them. These are issues users often encounter in day-to-day use, especially when working across multiple datasets or returning to a project after a break.

I loaded a file, but nothing appeared. What happened?
-----------------------------------------------------

- This often happens if you closed the plugin configuration dialog without confirming.
  Make sure you clicked :guilabel:`OK` (not :guilabel:`Cancel`) after selecting your file and settings.
- Confirm you’ve selected a valid **channel** and clicked :guilabel:`Update Trace` to display the signal.

I'm fitting my events, but it shows the fit from a previous dataset.
---------------------------------------------------------------------

This usually means the wrong **reader** or **event fitter** plugin is selected.

Make sure that:

- The event fitter **instance you just created** is selected in the dropdown.
- The **reader** you want to apply the events to is **active**.
- You aren’t mixing configurations from a different session.

Otherwise you may apply one dataset’s events to another, leading to mismatched results.

I clicked :menuselection:`Analysis -> New Analysis Tab -> EventAnalysisController` or :menuselection:`RawDataController`, but nothing changes.
----------------------------------------------------------------------------------------------------------------------------------------------

Poriscope lets you use the top menu to **open** a plugin tab the first time only.  
After it’s opened, switch back to any analysis view from the left sidebar:

:menuselection:`All Analysis Tabs` → select the tab you want.

I'm trying to load a database into Metadata View or Event Analysis View, but it says the format is unsupported.
---------------------------------------------------------------------------------------------------------------

You may be loading the **wrong type** of ``.db`` file for that tab. Both databases use ``.db`` but serve different purposes:

- **Raw Event database** — created in **Raw Data View** via :guilabel:`Commit Events`.  
  Contains **unfitted** events. Load this **in Event Analysis View** for fitting.
- **Fitted Event database** — created in **Event Analysis View** via :guilabel:`Commit`.  
  Contains **fitted events and metadata**. Load this **in Metadata View** or **Clustering View**.

**In short:**

- Use **Raw Event ``.db``** → **Event Analysis**  
- Use **Fitted Event ``.db``** → **Metadata / Clustering**

.. tip::

   Name databases clearly to avoid confusion, e.g.::

      my_sample_events_raw.db      # created in Raw Data View
      my_sample_events_fitted.db   # created in Event Analysis View

   You can also adopt a suffix system that matches your workflow (e.g., ``.db`` for raw, ``.sqlite`` for metadata).

Is Linux supported?
-------------------

Disclaimer: Poriscope is currently beta tested on Linux through an Ubuntu VM. As a result, certain UI behaviors may differ from the native Windows experience, particularly around popup windows, which rely on compositor effects that virtual GPU drivers handle inconsistently.

Functionality is in place, and Linux-specific fixes will continue to be refined as support matures.