# Plan - <short title>

> Summary (one screen): what changes, in what order, what is decided, how success is measured, and
> what needs the reviewer's ruling.

Reproduced / measured at `<sha>` on <date>: <what the probe showed; which inherited claims held and which moved>.

## Per site

### <file:line> - <what the defect is>

- **Real bug?** <why it is, or is not; the reachable input that triggers it>
- **Fix:** <the smallest change that fixes it>
- **Also touches this code:** <callers, other writers of the same state, other open work>
- **Tests:** <which cover it today; which will be written first and seen red>
- **Where a regression would show:** <UI action / command / output a person would see>
- **Watch out:** <behaviour something else depends on that the obvious fix would change>

## Not in this change

- <adjacent finding> - <fixed here anyway / deferred, with reason and number>

## Records to update

- Changelog: <one line, user-facing; breaking changes called out>
- Decision log / work queue / docs: <what, or "none">

Approved by <who> on <date>.
