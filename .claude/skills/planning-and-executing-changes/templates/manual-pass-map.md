# Manual pass map - <branch>

Derived from call sites, not function names. One row per changed function or path.
Commits that change no application behaviour are listed as "no app risk".

| Commit | Changed code | Reached from (UI action) | Preconditions (state the guards require) | What you would see if broken | Result (date) |
|---|---|---|---|---|---|
| 1 | `<Class.method>` | <menu -> dialog -> button> | <exactly one channel selected; DB loaded> | <empty plot / dialog does not open / status line X> | |

Covered by automated tests instead (cannot be staged by hand): <failure paths needing a raise, corrupt file, missing resource>.
Read status panels from the top, not the last line.
