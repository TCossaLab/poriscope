# Commit series - <step name>

Premise re-measured at `<sha>` on <date>: <what held, what moved>.
Starting state: suite <N passed / M skipped>; gates <values>; all hooks green.

| # | Commit | Changes | Metric simulated before | Metric after (fill in) | App risk / manual check |
|---|---|---|---|---|---|
| 0 | docs: record the approved series | plan only | - | - | none |
| 1 | <leaves first> | <methods> | dup 1,889 -> 1,802 (-87); fns 143 -> 128 | | <UI actions to exercise> |
| 2 | ... | | | | |
| n | docs: step landed | plan, live table | - | - | none |

Ordering reason: <dependency graph: a promoted method may only call what is already on the base>.
Gates expected NOT to move, and why: <e.g. boundary allowlist stays 111: destination unscanned by any rule>.
New mechanisms in this series (test-first, red then green): <list or "none">.
Tests expected to break and how they will be rewritten: <patch targets, receiver renames>.
Approved by <who> on <date>.
