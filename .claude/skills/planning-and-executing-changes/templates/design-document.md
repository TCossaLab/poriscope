# <Feature>: design (discovery stage)

One file per feature, started at discovery step 2 and kept beside the plan it leads to. Sections in this
order; each says which discovery step fills it. A section not reached yet keeps its heading and "Not yet".

Status, <date>: what is confirmed, what is still open (ruling IDs, Q-n rows), and the next step.
Sources: the request (verbatim, or where it is kept), and the commit every "today" claim was read at.

## 1. Restatement (step 2)
`templates/restatement.md`, filled: the note's sections, "Already decided or already true", the questions,
then the Answers (A-n) and Open what-questions (Q-n) tables. Mark it "confirmed, <date>" once the user has
answered.

## 2. Today (step 4)
What exists now, each claim with `file:line` read this session (D4). Nothing planned goes here.
- Each lifecycle verb and persisted file the request touches: writer and reader, or method and counterpart
  (D5).
- Where the request names a category ("every tab"), one row per member: what it records, which controls it has.
- The architecture notes' trap questions for this area, each answered from the code.

## 3. Use cases (step 5)
One per user goal, `UC-n · <goal>`, in the user's terms (D8):
- who acts, what triggers it, what they see, the outcome;
- each step cites a note line, an answer (A-n) or a ruling ID; a step that rests on an open ruling is marked
  conditional.

Mark "confirmed, <date>" once the user has confirmed them.

## 4. Rulings register (step 6)
One row per ruling, added when it opens and updated when it is decided (D3). Delegations are recorded under the
table: who delegated, which IDs, the date.

| ID | Question | Status | Decision | Date |
|---|---|---|---|---|
| R1 | | open | | |

*Case:* a session kept its later rulings in a second table with no decision or date column. One ruling sat
there as a consequence nobody had ruled on.

## 5. Rulings (step 6)
One `templates/ruling.md` per ruling, in register order. A later explanation or revision goes under its own
ruling, dated, not in a new section.

## 6. Audit (step 7)
Before each hand-over: the date, what was audited (design, use cases, mock-up), and what the audit removed,
marked conditional or raised as a new ruling (D3).

## 7. Corrections log (from step 3 on)
Every correction as it happens, both kinds (step 3). May be its own file beside this one if it grows; then
link it here.

| # | Date | Kind: user correction / own error | Assumed or said | About: what the user wants / the codebase | Correction | Lesson candidate |
|---|---|---|---|---|---|---|
| 1 | | | | | | |

## 8. Settle (step 8)
Each lesson candidate from the log: promoted to the skill, added to the architecture notes as a trap question
(with the user's agreement), or dropped, with the reason.
