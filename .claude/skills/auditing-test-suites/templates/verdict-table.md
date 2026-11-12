# <slice> - test verdicts

Standard: (a) covered - a named survivor fails under the same production mutation; (b) cannot
meaningfully fail; (c) vacuous - a mutation survives. Default is keep.

| Test (node id) | Verdict | Std | Mutation (file: what was changed) | Candidate | Survivor (node id) | Coverage lost |
|---|---|---|---|---|---|---|
| <tests/...::test_name> | <drop / arm / gap / bug / keep> | <a / b / c> | <file.py: what> | <failed / passed> | <tests/...::survivor, failed> | <none / what> |

## Tests that freeze a known bug

| Test | The defect | Ruling needed |
|---|---|---|
| <node id> | <what the code does wrong, with numbers> | <the choice for the owner> |

## Judgement calls for the owner

| Group | For dropping | For keeping |
|---|---|---|
| <tests> | <evidence> | <evidence> |

## Suspicions that did not survive checking

- <suspicion> - <what disproved it>
