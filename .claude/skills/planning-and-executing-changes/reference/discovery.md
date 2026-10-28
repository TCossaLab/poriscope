# Discovery: from a rough request to something plannable

The question this file answers: *what was actually asked, what is already decided, and which questions are
the user's to answer?* Run it before the plan when the request is a note, a relayed idea or a design
discussion.

## Contents

- Discovery is about what, not how
- The discovery steps
- D1 Restate a rough note before designing from it
- D2 Search the decision log and the work queue before designing
- D3 A question in the request is the requester's until they answer it
- D4 Label every claim about the system "today" or "planned"
- D5 Check both halves of a lifecycle verb or a persisted file
- D6 On a failure path, what the user can do next is a ruling
- D7 "Never automatic" is not "never offered"
- D8 Write use cases from the request, before the plan

## Discovery is about what, not how

For a fix, the problem is known and the plan is the implementation. For a new feature, the user first needs
to establish what they want and confirm that you understand it. Until the restatement (D1) and use cases
(D8) are confirmed, don't propose implementations. Afterwards, present ways to build it as options (D3), not
as the plan. An implementation choice the user hasn't made is a ruling, however confident you are in it.

Stay grounded throughout: check decision records (D2) and verify claims against the code (D4, D5) even while
working on "what". Collaboration without grounding produces confident errors; grounding without
collaboration produces a plan nobody asked for.

## The discovery steps

Scale the steps to the request. A small, clear change may need only a short restatement and one or two
rulings. Step 3, stop and ask, is never skipped. When you skip or reorder a step, name the step and say why
in your reply before doing it.

*Case:* asked to start the plan while rulings were still open, a session began without saying the rulings
step would be skipped. The requester stopped it: "ok dont skip it lets follow orders... so rulings firts then
what?"

1. **Load the project's architecture notes first** (in a repository with an architecture skill, that
   skill), since a rough request is phrased in the architecture's terms.
2. **Start the design document** from `templates/design-document.md`; every later step writes into it.
   **Restate** the note with `templates/restatement.md` (D1). Alongside it, search the decision log, the work
   queue and the changelog for the topic (D2), and put what you find in the restatement's "Already decided
   or already true" list.
3. **Stop and ask.** No design until the user has answered. From here on, log every correction in the
   design document's corrections log as it happens, with these fields:
   - the date;
   - the kind: a user correction, or an own error caught (a claim withdrawn, a wrong count, a reversed
     recommendation);
   - what was assumed or said, and whether it concerned what the user wants or the codebase;
   - the correction;
   - whether it's a lesson candidate (yes/no).

   *Case:* a session logged all ten of the user's corrections as they came, but not its own premature "Nothing
   is left open on what the feature should do", a wrong count, or a reversed recommendation. The first became
   a lesson only because the session remembered it.
4. **Overview:** what exists today, each claim with `file:line` (D4, D5). Where the request names a category
   ("every tab", "all operations"), tabulate each member: what it records, which controls it has (P15). If
   the project's architecture notes list trap questions for the area, answer each one here, from the code.
5. **Use cases** from the confirmed restatement and the user's answers (D8). Confirm them.
6. **Rulings:** each way to build it, and each choice with user-visible effect, as a ruling with
   `templates/ruling.md` (D3), including failure paths (D6) and any capability a design constraint would
   remove (D7).
7. **Audit** every design, use case, plan or mock-up before handing it over (D3).
8. **Settle:** review the corrections log, both kinds of entry. Each entry marked as a lesson candidate is
   promoted to this skill, with its real case, only if it is general; project facts go to the project's
   architecture notes.
   When an entry's wrong assumption was about the codebase, not about what the user wants, propose adding it
   as a trap question in the relevant area of the project's architecture notes, with its case, and ask the
   user before adding it. Then plan (planning.md).

**Completion check.** Before saying discovery is done, or that every question is answered, go through the
restatement's "Open what-questions" table (`templates/restatement.md`) row by row. Discovery is complete only
when every row is answered or deferred to someone named. A question the user asked in the note is easy to
lose once the conversation has moved on to the questions you raised.

*Case:* a session's design document said "Every "what" question is answered." One of the brief's own open
questions had never been answered: "After a session restores a tab's state, a single new click could trigger
an overwriting action and wipe the restored state. Should restored state be protected (warn, confirm, undo),
or is losing it acceptable?" The session found it only while drafting the use cases.

## D1 · Restate a rough note before designing from it

A rough note is the only record of what was asked. If you replace it with a cleaner paraphrase, every later
step builds on the paraphrase, and nobody notices where it differs from the original. Before any design
work, restate the note with `templates/restatement.md` and ask the user to confirm it.

Fill each section only from what the note says or clearly implies. If the note gives nothing for a section,
write "Not stated in the note" and add a question asking the user to state it. Don't fill a section from your
own ideas, the code, or what seems likely: an invented alternative or limitation reads as the user's and gets
built on. What the decision records or the code already settle goes in the template's separate "Already
decided or already true" list, each item cited (D2, D4), never into the note's own sections.

Then stop and ask the user to answer. Don't start design until they do. If the user has said to proceed on
assumptions, still leave empty sections marked "Not stated in the note", state which reading you chose for
each unsure point, and mark both as assumptions in the design.

Restate a terse answer back before building on it, for example: "I've read 'a' as option (a): deleting a
plugin drops the entries that use it." Then record it in the restatement's "Answers" table.

*Case:* a user replied to a list of questions with a single "a". The session said which question it took that
to answer, spelled the option out, and asked to be corrected.

One message of questions costs far less than a design built on the wrong reading.

*Case:* a note said "extend reguster acyion beyond controller". One session's design read it as moving
recording onto the Controller; another's as "Extend beyond the Views." The note also asked "is it gonan get
overwritte rela quick??", which has at least two readings: entries for the same action superseding each
other in the log, or the saved file being rewritten. Each session picked one reading of each phrase silently
and designed on it. Neither asked.

## D2 · Search the decision log and the work queue before designing

A recorded decision or a queued item is somebody's earlier discovery. Grep them for the topic before
designing, and treat what you find as claims with dates (P4): re-derive them. Put what you find in the
restatement's "Already decided or already true" list (D1), each item with its source and date, separate
from what the note says. If the design might reverse a decision, say so and name whose ruling that needs.
Whether its revisit condition is met is that person's call, not yours. Check first whether the design really
reverses the decision or only extends it. Findings you were handed and reports from subagents are inherited
claims too: re-derive them before building on them (P4).

*Case:* three sessions designed action replay. The two that never opened the decision log asserted that
session load already replays, and were corrected. The decision log recorded, with evidence, that
"`MainController.load_session` never replays", and the work queue had already posed the dedup-key and
replacement-position questions. The session that grepped both got those facts right unprompted. It then
declared that the decision's revisit condition "is now met" and framed its design as a reversal. Asked, it
conceded that a per-tab choice at load only extends the decision; only automatic replay of everything would
reverse it.

A second case, for inherited findings: a session re-checked the findings it was handed at its branch's HEAD.
It caught a subagent report that cited `MetaEventTabView.py:296` for a widget read that is at `:249`.

## D3 · A question in the request is the requester's until they answer it

A request that ends in questions ("button inn each?", "how do we decir what gets oevrwitten vs added") asks
for options, not verdicts. Answer what the code settles, with evidence (`file:line`). Turn each remaining
design choice into a ruling and wait for the user to decide. Deciding it yourself also hides the
alternatives from the person who has to defend the design to others.

For each ruling, after the restatement (D1) is confirmed, fill `templates/ruling.md`:
- who decides: the user, or a named person;
- a one-screen summary first: the question, the options still in play, those ruled out and why, and your
  recommendation with the criterion that decided it;
- the options: the user's, if the note gave any, and your own, labelled as yours;
- every issue the user flagged, checked against the code for each option;
- any option that fails a confirmed goal or constraint, ruled out with the reason;
- an impact trace for each remaining option;
- every remaining option evaluated against the same criteria, each claim cited or marked "estimate", with no
  scores or weights.

What counts as a breaking change is defined in
[collaboration-and-records.md](collaboration-and-records.md) (C6, the changelog entry).

Record each ruling in the rulings register with status "open". The register is a section of the design
document, with one row per ruling: its ID, the question, its status (open or decided), the decision, and the
date it was decided. A ruling stays open everywhere until the user decides it. A use case, plan step or
mock-up that assumes an answer has settled it as surely as saying so.

When the user delegates rulings to you, record who delegated, which ruling IDs it covers, and the date. A
delegation covers only the rulings named; ask before extending it. After deciding, send one message listing
each ruling as "decided on my recommendation" (with the choice) or "back for your confirmation" (with why).

*Case:* told "go with ur reommendations unless its a concern we have debated a lot", a session decided six
rulings and sent four back, each with its reason. Earlier it had asked whether a go-ahead for one ruling
covered the rest.

When you record a new answer or decision, re-read the earlier ones it combines with. A new answer can empty or
contradict a term an earlier one used. Rewrite that term in the register and in every use case that carries
it.

Before handing over any design, use case, plan or mock-up, audit it:
- every element cites its source: the note, a user answer, code (`file:line`) or a ruling ID;
- any element that depends on an open ruling is marked conditional, or written once per option;
- any element with no source was invented: remove it, or raise it as a new ruling;
- an example is an element too: a sample log, a dialog's wording, a file's contents. Build it from what the
  code shows today and what the user stated; any format beyond that was invented.

*Case:* one session's design document titled a section "Open questions, answered" and put a restore button
on every tab's base class. Another listed the same choice as a ruling (one session dialog or a button per
tab). It then wrote use cases in which that dialog already existed, with a checkbox per tab and two toggles
nobody had asked for, and in which load replayed every tab automatically. The user asked where the ticking
had come from. Both designs had settled the question: one openly, one inside its use cases.

A second case, for an example: asked what the status panel would show, a session drew a sample with a
summary format it had made up, a "replay finished (2 actions)" header over numbered lines. The requester
answered: "Panel log should show only what a running fitter, finder or specific plot usually shows… those
things should accumulate until it's done, so it's not a mix of finder, histogram, fitter, histogram,
scatterplot etc."

A third case, for the register: one answer said display-only steps are replayed only if they lead to the
final view, and that messages from skipped steps are not shown. A later answer kept only the last view per
tab, so the saved history held no intermediate steps to skip. The use cases still said "skipped steps show
no messages". The requester asked: "Such as? What skipped steps are is not clear."

## D4 · Label every claim about the system "today" or "planned"

Design documents describe a system that does not exist yet in the same tense as the one that does. A reader,
or the next session, cannot tell which is which. Write the "today" part first, each claim with `file:line`
read this session, and keep the design apart from it.

*Case:* a design note stated that replay calls the method by name, "bypassing `register_action`'s wrapper
entirely (deliberately: replaying mustn't re-record)". The code calls the decorated wrapper by name, so
replay re-records, and Undo depends on that to rebuild its history (`MetaView.py:425-430`,
`MetaController.py:451-452`). A later session built its argument that rollback was not feasible on the
claim. The session that wrote "Today:" first, with line numbers, planned a probe for exactly this instead.

## D5 · Check both halves of a lifecycle verb or a persisted file

"Close a tab", "restore a session" and "the history is saved" are claims about the application. Don't assume
symmetry: one half of a pair existing proves nothing about the other half. Save doesn't imply load, record
doesn't imply replay, open doesn't imply close.

For a lifecycle verb:
- find the method behind it (grep); if none exists, say so;
- read it, and check it does what the verb implies at the scope implied (one tab, or the whole workspace);
- find its counterpart (open/close, add/remove, record/replay) and check that separately.

For a persisted file:
- find the writer, and when it writes (every change, on save, on exit);
- find the reader, and when it reads;
- check the reader accepts the file: it may skip fields, refuse the file or only read it in some modes;
- compare what's written with what's read.

A file saved on every change can still have no reader.

The same check applies to a file the design itself adds. Record its writer, when it writes, and its reader in
discovery, next to its layout; don't leave them to the plan.

*Case:* use cases said an interrupted tab could be "closed" and its history restored on session load. No
per-tab close exists (only a full workspace reset clears tabs). The action history is autosaved on every
action but never read back on load, and the session-load reader explicitly refuses that file.

A second case, for record without replay: three analysis tabs record actions, but only one can replay them.
Protein and Clustering methods carry the recording decorator (`ProteinView.py:666`, `:1795`;
`ClusteringView.py:142`, its reset only), yet Save Actions, Load Actions and Undo are wired only on Metadata
(`MetadataView.py:1996-2000`, `metadatacontrols.py:481`). The replay logic sits on the shared base classes,
so reading the bases suggests every tab can replay; reading each tab's controls shows that only one can.

A third case, for a file the design adds: a design split a saved session into two files, one for plugins and
one for actions, and recorded the layout as decided. It had checked the writer and reader of every existing
file, but not when the new actions file would be written. The requester asked: "How come you didn't ask me
when to write to actions.json?"

## D6 · On a failure path, what the user can do next is a ruling

A failure use case must say three things:
- what state is left behind: verify it in the code (`file:line`), don't assume it;
- what the user is told;
- what the user can do next.

The last is a product decision with costs. Raise it as a ruling (D3) with options such as keep the partial
state, roll back, or retry, instead of silently picking the cheapest one.

*Case:* two independent designs had a failed replay stop and report, leaving the tab half-restored. Neither
offered a choice between keeping the partial state and going back to retry, and neither asked. The user
raised it: "would u like to keep aprtial state or go back to before restore and try again?" The stated reason
rollback was hard rested on a false claim about the mechanism (see D4).

## D7 · "Never automatic" is not "never offered"

A guarantee that the system won't do something on its own says nothing about whether the user may choose to
do it. When a design rules out an automatic behaviour, check the request for a user-initiated version of the
same thing. If the request asks for it, keep it; if it's unclear, ask (D3).

The same applies to any constraint a design adds for its own reasons (cost, simplicity, safety): before it
removes a capability, check whether the request asked for that capability.

*Case:* a design made replay per-tab and never automatic, to keep restore cheap, and so ruled out a "restore
everything" action. The note had said "full state cna be recovered" and "option to select only specific
tabs". Both modes were wanted.

## D8 · Write use cases from the request, before the plan

Use cases are the requester's goals in their own terms, which makes them the check on a plan. Derived from
the plan, they inherit its assumptions and can no longer catch them. Write them from the confirmed
restatement (D1) and the user's answers, before any plan, then check the plan against them.

Write each use case in terms of what the user does and sees:
- who acts, what triggers it, what they see, what the outcome is;
- no class names, methods or mechanisms;
- each step traces to the note, a user answer or a ruling (D3); a step that depends on an open ruling is
  marked conditional, or the use case is written once per option.

If a use case only makes sense with an implementation detail, that detail is an open ruling: raise it, don't
write it in.

*Case:* one design session wrote use cases only when asked, after its plan, and derived them from it. They
carried the plan's invented checkbox dialog and its "every tab" generalisation: an Undo use case written for
all tabs when only one tab has an Undo button, and a load flow that replayed everything when the note asked
for an "option to select only specific tabs". Another session derived its use cases from an earlier design
document and inherited that document's errors the same way.
