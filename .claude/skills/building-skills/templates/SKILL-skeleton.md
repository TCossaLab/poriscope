---
name: <skill-name, matching the folder>
description: <What it does, first. Then "Use whenever ..." with every stage and situation, in the user's words, including ones where they would not name it. Name sibling skills to load with it. <= 1,024 characters.>
---

# <Title>

<The failure this skill prevents, in two or three sentences. Where its lessons came from: the work, its
size, the dates. "Every lesson carries the case that produced it.">

<If it builds on another skill: "Load `<other>` first." and what this one adds.>

## The stance, in <N> sentences

1. **<The skill compressed into one sentence>** (<IDs>).
2. ...

## Reference files - read the one for what you are doing

| File | Read when |
|---|---|
| [reference/<activity>.md](reference/<activity>.md) | <the situation the reader is in> |
| [reference/lesson-index.md](reference/lesson-index.md) | Looking up a lesson by ID or symptom (grep it) |

## The procedure

Copy this checklist into your working notes and keep it current:

```
<Name> progress:
- [ ] 0. <step>
- [ ] 1. <step>
```

### 0 · <Step>

<Two to five bullets, each citing its lesson IDs.>

## Standing rules

1. **<A rule that holds throughout the task>** (<ID>).

## Red flags - stop and check

| You notice | Check | Lesson |
|---|---|---|
| <a symptom observable in the moment> | <what to check> | <ID> |

## Scripts and templates

<Stdlib-only Python 3.9+. Run each with `--help`; execute rather than read.>

| Script | Purpose |
|---|---|
| `scripts/<name>.py` | <the failure it catches> |

| Template | Use |
|---|---|
| `templates/<name>.md` | <the artefact it is the skeleton of> |
