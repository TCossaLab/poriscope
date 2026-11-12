# <audit or cleanup>: common brief for every worker

Repository: <path>. Read <the project's always-loaded instructions> first, and lessons N4, N8, N12, N15,
N16 in `planning-and-executing-changes/reference/testing.md`.

## What you are doing

<One paragraph: audit (read-only, report verdicts) or cleanup (act on the approved page at <path>).>
You own ONE slice, named in your task. <For a cleanup: act on every item of the page in your slice.>

Rulings from <owner>:
- <ruling>
- <ruling>

## Rules for each kind of item

1. DROP (a covered / b cannot meaningfully fail): name the survivor; re-run one representative mutation
   per group; if the evidence does not reproduce, keep it and say so.
2. VACUOUS (c): drop it if a stronger test catches the mutation; otherwise ARM it - tighten it until it
   fails under the mutation, and show both runs.
3. GAP: write the test first; show it fails under the mutation that demonstrates the gap.
4. Fix the stale docstrings listed for your slice.
5. Do NOT edit production code, the changelog, the decision log, the work queue or the docs - the
   coordinator does. If a fix needs a production change, stop and report it.
6. Do NOT touch these reserved tests: <list>.

## How to work

- Your own worktree on a new branch from <base commit>: `git worktree add -b <branch> <path> <base>`.
  Commit only there; never edit, stash or commit in the main checkout; do not push.
- Confirm imports resolve into your worktree before trusting a run.
- RESOURCE LIMIT: other workers share this machine. Never run the full suite and never run tests in
  parallel; run single files serially.
- Mutations through <mutation tool>; a result where the anchor was not found is not evidence. Files with
  CRLF line endings need CRLF in multi-line anchors.
- Edit with the file tools; a shell-scripted edit can turn escapes into control bytes.
- Keep your scratch files in <your own scratch folder>.
- Run every changed file serially and read its summary line before each commit; run the formatters
  first. End every commit message with <attribution trailer>.
- At the end remove your worktree and keep the branch.

## Report back (concise)

Branch and commits. Per item in your slice: dropped / armed / gap added / kept with reason, with the
mutation evidence. Anything not done and why. Tests removed and added. Any production defect found.
