.. _walkthrough_mixin:

WalkthroughMixin
================

The mixin behind a tab's guided walkthrough. Inherit it alongside your view's base
class and implement :py:meth:`~poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin.get_walkthrough_steps`;
:doc:`adding_walkthrough` is the tutorial.

.. note::

   This page is hand-written rather than generated. The autodoc generators scan
   ``poriscope/utils`` and ``poriscope/plugins`` only, and Step 3f of the 2.0.0
   refactor moved ``walkthrough_mixin.py`` into ``poriscope/views/widgets/`` to fix a
   layering inversion - the app shell was importing *up* into a plugin package. The
   three dialog classes that moved with it (``IntroDialog``, ``Overlay`` and
   ``StepDialog``) are internal UI machinery a plugin author never instantiates, and
   deliberately have no page. This one does, because the tutorial tells you to inherit
   it.

.. autoclass:: poriscope.views.widgets.walkthrough_mixin.WalkthroughMixin
   :members:
   :undoc-members:
   :show-inheritance:
