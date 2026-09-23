MainModel Overview
==================

The MainModel manages the application’s shared state and acts as the central data repository.

It holds the discovered plugin classes, the application configuration and the session state. Live data-plugin instances are held separately, by ``DataPluginModel``.

By maintaining a clean separation between logic (controller) and display (view), the MainModel plays a crucial role in ensuring data integrity across Poriscope’s modular environment.
