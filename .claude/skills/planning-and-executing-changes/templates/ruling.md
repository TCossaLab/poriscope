## R<n> · <the question>
Status: open | decided <date>, by <who>, as <option>
Who decides: the user | <named person>. If delegated: delegated by <who>, on <date>, covering <ruling IDs>
(D3).

*Case:* answering one ruling, a requester said a colleague had let them make the decisions. The session asked
whether that covered the other rulings before treating them as the requester's.

When this ruling opens, add its row to the design document's rulings register (`templates/design-document.md`,
D3): ID, question, status "open". When the user decides it, update the row with the decision and the date.

### Summary (one screen)
- The question, in one line.
- Options still in play, one line each, with what separates them.
- Ruled out, one line each, with the reason.
- Recommendation, the criterion that decided it, and the criteria the user might weigh differently.

### Options
The user's, if the note gave any, and mine, each labelled with whose it is.

### Issues the user flagged
For each issue (the restatement's "Expected issues/limitations", and any raised since), for each option:
- how the option handles it, or that it doesn't;
- the issue checked against the code, with `file:line`. If the code contradicts it, say so and ask; don't
  override it. If it can't be verified, mark it "user-stated, unverified" and keep it.

### Ruled out
An option that fails a confirmed goal or constraint, with the reason. Ruled-out options get no impact trace.

### Impact trace (options still in play only)
Where the user flagged nothing, before evaluating:
- every call site and subclass of what the option changes;
- the public contracts that change, and whether that is breaking (collaboration-and-records.md, C6);
- effects on existing behaviour (for example undo, recording, loading), each cited;
- conflicts with decision records, each cited;
- what the trace found, as issues with citations, or that it found none and what was traced.

### Evaluation
The same criteria for every option still in play:

| Criterion | <option> | <option> |
|---|---|---|
| Confirmed goal and constraints | | |
| Existing decisions (conflict cited; extends or reverses) | | |
| Code impact (files, public contracts, breaking?) | | |
| Interactions with existing behaviour (cited) | | |
| User-facing behaviour | | |
| Rulings this forces or rules out | | |

Every claim cites its source or is marked "estimate". No scores or weights.
