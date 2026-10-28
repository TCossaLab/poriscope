# Restatement: <request>, <date>

Fill each section only from what the note says or clearly implies (D1). Where the note gives nothing, write
"Not stated in the note" and add a question under "Questions for the user".

## Goal
What the user wants to be possible when this is done.

## Constraint
Limits the note states or clearly implies.

## Approach
The method the note proposes, if it proposes one.

## What this requires
The changes the approach depends on.

## Contemplated alternatives
Other approaches the note mentions or rules out, and why.

## Expected issues/limitations
Problems the note anticipates (its "tricky part", "gotta be clever").

## Unsure points
Every phrase that has more than one plausible reading. For each:
- the phrase, quoted exactly as written
- each plausible reading
- what changes in the design depending on which is right

## Already decided or already true
Not from the note. What the decision log, the work queue, the changelog (D2) or the code (D4, D5) already
settles, each item with its source (`file:line`, or the record and its date). Facts for the user to check,
not part of the request.

## Questions for the user
- one for each section marked "Not stated in the note"
- one for each unsure point
- one for each "Already decided" item the note seems to conflict with

## Answers
The user's answers, one row each, kept apart from "Already decided or already true" (records and code).
Use cases cite these IDs.

| ID | Question it answers | Answer, in the user's words | Date |
|---|---|---|---|
| A1 | | | |

*Case:* a session kept every answer as a numbered row and cited it in each use-case step, so the audit could
check each step against what the user actually said.

## Open what-questions
Every question from the note or brief goes here at the start, then each one raised during discovery.
Discovery's completion check runs on this table (discovery.md, "Completion check").

| ID | Question | Status: answered by A-n / open / deferred to <name> | Source: note / brief / discovery |
|---|---|---|---|
| Q1 | | | |

*Case:* a brief listed five open questions that were never tracked as rows; one was still unanswered when the
session declared every question answered.
