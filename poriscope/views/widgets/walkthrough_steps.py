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
# Alejandra Carolina González González


# walkthrough_steps.py


def get_global_walkthrough_steps(pages, get_analysis_highlight):
    return [
        (
            "New Analysis Tab",
            "Click on 'Analysis' → 'New Analysis Tab' → 'RawDataController' to continue.",
            "MainView",
            lambda: [get_analysis_highlight()],
        ),
        # Raw Data Tab
        (
            "Raw Data Tab",
            "You're now in the 'Raw Data' tab. Click the '+' button to add a reader.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.readers_add_button],
        ),
        (
            "Raw Data Tab",
            "Great! A reader has been added. Now, select a channel from the dropdown menu to proceed.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.channel_comboBox],
        ),
        (
            "Raw Data Tab",
            "Perfect. Click the '+' button to add a filter.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.filters_add_button],
        ),
        (
            "Raw Data Tab",
            "Now, enter a valid start time to prepare your trace.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.start_time_lineEdit
            ],
        ),
        (
            "Raw Data Tab",
            "Click 'Update Trace' to visualize your raw data.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.update_trace_pushButton
            ],
        ),
        (
            "Raw Data Tab",
            "Need to check the noise across frequencies? Click 'Update PSD' to view the power spectral density.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.update_psd_pushButton
            ],
        ),
        (
            "Raw Data Tab",
            "Click the '+' button to add an event finder.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.eventfinders_add_button
            ],
        ),
        (
            "Raw Data Tab",
            "Then, click 'Find Events' to begin detection.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.find_events_pushButton
            ],
        ),
        (
            "Raw Data Tab",
            "To refine performance, restrict the time range using the timer button.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.timer_pushButton],
        ),
        (
            "Raw Data Tab",
            "If events have been successfully found — you can confirm this on the right-side panel — you may now enter the event indices you wish to inspect.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.event_index_lineEdit
            ],
        ),
        (
            "Raw Data Tab",
            "Now click 'Plot Events' to see the result.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.plot_events_pushButton
            ],
        ),
        (
            "Raw Data Tab",
            "Use these arrows to quickly browse between plotted events.",
            "RawDataView",
            lambda: [
                pages["RawDataView"]["widget"].rawdatacontrols.left_plot_arrow_button,
                pages["RawDataView"]["widget"].rawdatacontrols.right_plot_arrow_button,
            ],
        ),
        (
            "Raw Data Tab",
            "If you are happy with your events, you can now click the '+' button to add a writer.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.writers_add_button],
        ),
        (
            "Raw Data Tab",
            "Finally, click 'Commit Events' to save your findings into an events database.",
            "RawDataView",
            lambda: [pages["RawDataView"]["widget"].rawdatacontrols.commit_btn],
        ),
        (
            "Raw Data Tab",
            "Note: At any time, you can click 'Export Plot Data' to save your graph.",
            "RawDataView",
            lambda: [
                pages["RawDataView"][
                    "widget"
                ].rawdatacontrols.export_plot_data_pushButton
            ],
        ),
        # Event Analysis Tab Walkthrough
        (
            "Ready to analyze your events ?",
            "Click on 'Analysis' → 'New Analysis Tab' → 'EventAnalysisController' to continue.",
            "RawDataView",
            lambda: [get_analysis_highlight()],
        ),
        (
            "Event Analysis Tab",
            "Welcome to Event Analysis! Click the '+' button to load your event database.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.loaders_add_button
            ],
        ),
        (
            "Event Analysis Tab",
            "Select the channel you'd like to work with from the dropdown menu.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.channel_comboBox
            ],
        ),
        (
            "Event Analysis Tab",
            "Now, select one of your previously created filters from the list.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.filters_comboBox
            ],
        ),
        (
            "Event Analysis Tab",
            "If you'd like to confirm you've loaded the correct event database, enter the range(s) or index(es) to plot.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.event_index_lineEdit
            ],
        ),
        (
            "Event Analysis Tab",
            "Then, click 'Plot Events' to visualize the selected entries.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.plot_events_pushButton
            ],
        ),
        (
            "Event Analysis Tab",
            "Ready to fit the events? Click the '+' button to add a fitter.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.eventfitters_add_button
            ],
        ),
        (
            "Event Analysis Tab",
            "Click 'Fit Events' to begin. Once complete, fitted and rejected events will appear on the side panel.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.fit_events_pushButton
            ],
        ),
        (
            "Event Analysis Tab",
            "You can now enter new indices to inspect the fitted results.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.event_index_lineEdit
            ],
        ),
        (
            "Event Analysis Tab",
            "Click 'Plot Events' again to view the newly selected fitter events.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.plot_events_pushButton
            ],
        ),
        (
            "Event Analysis Tab",
            "Satisfied with the fits? Add a writer by clicking the '+' icon.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"][
                    "widget"
                ].eventAnalysisControls.writers_add_button
            ],
        ),
        (
            "Event Analysis Tab",
            "Click 'Commit' to save the results to your event database.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"]["widget"].eventAnalysisControls.commit_btn
            ],
        ),
        (
            "Event Analysis Tab",
            "Click 'Commit' to save the results to your event database.",
            "EventAnalysisView",
            lambda: [
                pages["EventAnalysisView"]["widget"].eventAnalysisControls.commit_btn
            ],
        ),
        # Meta Data Tab
        (
            "Let's proceed to visualize your data ! ",
            "Click on 'Analysis' → 'New Analysis Tab' → 'MetadataController' to continue.",
            "EventAnalysisView",
            lambda: [get_analysis_highlight()],
        ),
        # Metadata Tab Walkthrough
        (
            "Metadata Tab",
            "Click the '+' button to load your metadata database.",
            "MetadataView",
            lambda: [
                pages["MetadataView"]["widget"].metadatacontrols.db_loader_add_button
            ],
        ),
        (
            "Metadata Tab",
            "Choose the type of plot you'd like to generate from this dropdown.",
            "MetadataView",
            lambda: [
                pages["MetadataView"]["widget"].metadatacontrols.plot_type_comboBox
            ],
        ),
        (
            "Metadata Tab",
            "Specify the number of bins for your plot. Use 'x,y' format for heatmaps.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.bins_lineEdit],
        ),
        (
            "Metadata Tab",
            "Use this to select the data for the x-axis.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.x_axis_comboBox],
        ),
        (
            "Metadata Tab",
            "Check this box if you want to use a log scale for the x-axis.",
            "MetadataView",
            lambda: [
                pages["MetadataView"][
                    "widget"
                ].metadatacontrols.x_axis_logscale_checkbox
            ],
        ),
        (
            "Metadata Tab",
            "Once you're ready, click 'Update Plot' to generate the visualization.",
            "MetadataView",
            lambda: [
                pages["MetadataView"]["widget"].metadatacontrols.update_plot_button
            ],
        ),
        (
            "Metadata Tab",
            "Not happy with the changes? Click 'Undo' to revert to the previous state at any point.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.undo_button],
        ),
        (
            "Metadata Tab",
            "Apply filters to your dataset using this text area. Use val.....",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.filter_textEdit],
        ),
        (
            "Metadata Tab",
            "Click here to save the current plot to file.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.save_plot_button],
        ),
        (
            "Metadata Tab",
            "Reload previously saved configurations using the 'Load' button.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.load_button],
        ),
        (
            "Metadata Tab",
            "Click 'Reset' to clear all changes and restore default settings.",
            "MetadataView",
            lambda: [pages["MetadataView"]["widget"].metadatacontrols.reset_button],
        ),
        (
            "Metadata Tab",
            "Use 'Export Subset' to save only the filtered data you're working with.",
            "MetadataView",
            lambda: [
                pages["MetadataView"]["widget"].metadatacontrols.export_subset_button
            ],
        ),
        # Clustering Tab
        (
            "Now, let's cluster!",
            "Click on 'Analysis' → 'New Analysis Tab' → 'ClusteringController' to continue.",
            "EventAnalysisView",
            lambda: [get_analysis_highlight()],
        ),
        (
            "Clustering Tab",
            "Click the '+' button to load your metadata database, or select a previously loaded one from the dropdown.",
            "ClusteringView",
            lambda: [
                pages["ClusteringView"]["widget"].clusteringcontrols.db_loader_comboBox
            ],
        ),
        (
            "Clustering Tab",
            "Click the 'Cluster Settings' button to specify your clustering configuration.\n\n",
            "ClusteringView",
            lambda: [
                pages["ClusteringView"][
                    "widget"
                ].clusteringcontrols.cluster_settings_button
            ],
        ),
        (
            "Clustering Tab – Merge Clusters",
            "The Clustering tab also allows you to merge clusters. First, select the group whose label you want to keep.",
            "ClusteringView",
            lambda: [
                pages["ClusteringView"]["widget"].clusteringcontrols.label_x_comboBox
            ],
        ),
        (
            "Select Group to Merge",
            "Then, select the group you want to combine it with.",
            "ClusteringView",
            lambda: [
                pages["ClusteringView"]["widget"].clusteringcontrols.label_y_comboBox
            ],
        ),
        (
            "Merge Clusters",
            "If you're happy with your selection, click 'Merge'. The selected clusters will be combined under the first group's label.",
            "ClusteringView",
            lambda: [pages["ClusteringView"]["widget"].clusteringcontrols.merge_button],
        ),
        (
            "Commit Changes",
            "Finally, click 'Commit' to apply the changes to the loaded database. A new column called 'cluster_label' will be added.",
            "ClusteringView",
            lambda: [
                pages["ClusteringView"]["widget"].clusteringcontrols.commit_button
            ],
        ),
    ]
