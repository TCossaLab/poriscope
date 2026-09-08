.. _code_ownership:

Code Ownership
==============

Poriscope keeps a ``CODEOWNERS`` file at ``.github/CODEOWNERS`` mapping paths in the
repository to the people who maintain them.

Its only purpose is **routing**: when you open a pull request, GitHub reads that file and
automatically requests a review from whoever maintains the files you touched, so the
person most likely to spot a problem hears about the change without anyone having to
remember to tag them.

.. important::

   ``CODEOWNERS`` in Poriscope is **advisory, not a gate**. It is a guideline, not a hard
   edit limit, and it is deliberately **not** a barrier to contribution.

   GitHub offers a branch-protection setting called *Require review from Code Owners*
   that turns the file into a merge block. That setting is switched **off** on purpose,
   for every branch. Nothing in ``CODEOWNERS`` prevents you from merging, and if you are
   contributing a plugin from a fork you do **not** need a listed owner's approval.

   If you touch a file someone else maintains, they will simply be asked to look. That is
   the whole mechanism.

Why This Is Advisory
--------------------

Poriscope is designed to accept plugin contributions from outside the lab —
``.github/workflows/ci-fork-pr.yml`` exists specifically to run validation on
fork-originated pull requests. A required-owner-review rule would put a single named
individual in front of every one of those contributions, including files whose maintainer
happens to be busy, on leave, or no longer with the lab.

Correctness is the job of the automated gates described in :doc:`quality_control`, which
every pull request must pass. Those are the checks that block. ``CODEOWNERS`` sits
alongside them as a courtesy to reviewers, not as an additional hurdle.

Who Owns What
-------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Path
     - Maintainer(s)
   * - Everything not listed below
     - Kyle Briggs
   * - ``poriscope/controllers/``, ``poriscope/models/``, ``poriscope/utils/``
     - Kyle Briggs
   * - ``poriscope/views/``
     - Kyle Briggs, Carolina González
   * - ``poriscope/plugins/analysistabs/``
     - Kyle Briggs, Carolina González
   * - ``poriscope/plugins/analysistabs/utils/``
     - Carolina González
   * - All other ``poriscope/plugins/`` families
     - Kyle Briggs
   * - ``PeakFinder.py``, ``Basic_PeakFinder.py``, ``SQLitePeakDBLoader.py``
     - Nada Kerrouri, Kyle Briggs
   * - ``tests/``
     - Carolina González
   * - ``.github/``
     - Carolina González, Kyle Briggs
   * - ``scripts/``
     - Kyle Briggs, Carolina González
   * - ``docs/``
     - Carolina González, Kyle Briggs

Where more than one name is listed, both are asked to review; because the file is
advisory, neither is required to respond before a merge.

The PeakFinder family carries one extra convention that is worth knowing if you are
working through the maintenance queue rather than contributing a plugin: the *logic* in
``PeakFinder.py`` and ``Basic_PeakFinder.py`` belongs to its maintainer and is left to
her, while docstring, signature and type-hint changes to those files are ordinary work.
That policy is recorded in ``future_fixes.md``.

Relationship to the ``# Contributors:`` Headers
-----------------------------------------------

Every source file under ``poriscope/`` and ``scripts/`` opens with the MIT licence header
followed by a ``# Contributors:`` block naming the people who wrote it.
``scripts/new_plugin.py`` fills that block in from your Git author name when it generates
a new plugin, so it stays accurate for new code automatically.

Those headers and ``CODEOWNERS`` answer two different questions and will not always
agree:

- The header records **who wrote the file**. It is attribution, and it is permanent.
- ``CODEOWNERS`` records **who maintains the file now**. It changes as people join the
  lab, move between areas, or leave it.

Two consequences follow. First, files written by contributors who have since left the lab
pass to Kyle Briggs, so their ``CODEOWNERS`` entry no longer names the original author
even though the header still does — and rightly so, since the header is a record of
authorship. Second, the test suites under ``tests/`` carry no headers at all but do have a
maintainer, so the two sources cannot be derived from one another in either direction.

Changing an Ownership Entry
---------------------------

Edit ``.github/CODEOWNERS`` in a normal pull request. Two things to keep in mind:

- **Patterns are last-match-wins.** The most specific rule must come last, which is why
  the global ``*`` fallback sits at the top of the file rather than the bottom.
- **A name only works if it has write access to the repository.** GitHub silently ignores
  a line naming anyone else, which means a mistyped handle does not raise an error — it
  just quietly stops requesting anybody.
