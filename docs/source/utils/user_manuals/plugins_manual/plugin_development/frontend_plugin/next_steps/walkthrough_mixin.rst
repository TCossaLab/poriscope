.. Hand-written, not generated: the autodoc generators scan poriscope/utils and
   poriscope/plugins only, and this mixin lives in poriscope/views/widgets/.

.. _walkthrough_mixin:

WalkthroughMixin
================

The mixin behind a tab's guided walkthrough. ``MetaView`` already inherits it, so a
tab View only implements ``get_current_view`` and the method below; inherit it directly
only for a dialog or other non-tab widget. Implement :py:meth:`~poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin.get_walkthrough_steps`;
:doc:`adding_walkthrough` is the tutorial.

.. autodata:: poriscope.views.widgets.walkthrough_mixin.WalkthroughStep

.. autoclass:: poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin
   :members:
   :undoc-members:
   :show-inheritance:
