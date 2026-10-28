# Collaboration and records during a refactor

Every collaboration and records lesson (C1-C12) is in the general skill's
[collaboration-and-records.md](../../planning-and-executing-changes/reference/collaboration-and-records.md): approved plans, ownership asks
with an exit, one branch per piece of work, one plan in the repository and a shared page, handoffs,
putting each kind of information in one place, keeping the wrong turns, replacing documentation for a
removed mechanism, treating delegated work as claims, and reporting outcomes faithfully.

What a refactor adds:

- **The plan document is long-lived and has a fixed shape** (`templates/plan.md`): a live gate table
  updated in every commit that moves a gate, each step's status dated, the re-verification log, the
  owners and their asks, and a method-notes section that accumulates the lessons.
- **Each step's commit series is approved and recorded before its first commit**
  (`templates/commit-series.md`), with the simulated metric per commit and the manual-pass map.
- **The plan is deleted when the release ships**, so nothing that ships may cite it (X4), and its
  method notes are moved into the skills before it goes.
