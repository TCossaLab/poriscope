MainModel Overview
==================

The MainModel manages the application’s shared state and acts as the central data repository.

It stores global resources like loaded datasets, reader instances, and analysis results, ensuring that all plugins operate on consistent and synchronized data.

By maintaining a clean separation between logic (controller) and display (view), the MainModel plays a crucial role in ensuring data integrity across Poriscope’s modular environment.
