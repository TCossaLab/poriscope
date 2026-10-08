.. _walkthrough_mixin:

WalkthroughMixin
================

The mixin behind a tab's guided walkthrough. ``MetaView`` already inherits it, so a
tab View only implements ``get_current_view`` and the method below; inherit it directly
only for a dialog or other non-tab widget. Implement :py:meth:`~poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin.get_walkthrough_steps`;
:doc:`adding_walkthrough` is the tutorial.

.. note::

   This page is hand-written rather than generated. The autodoc generators scan
   ``poriscope/utils`` and ``poriscope/plugins`` only, and this mixin lives in
   ``poriscope/views/widgets/`` because the app shell must not import *up* into a
   plugin package - which is what it did while the walkthrough modules sat under
   ``plugins/analysistabs/utils/``. The three dialog classes beside it
   (``IntroDialog``, ``Overlay`` and ``StepDialog``) are internal UI machinery a plugin
   author never instantiates, and deliberately have no page. This one does, because the
   tutorial tells you to inherit it.

.. autoclass:: poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin
   :members:
   :undoc-members:
   :show-inheritance:
