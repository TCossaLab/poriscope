# Lesson index

Every lesson in this skill, by ID. Grep this file for a symptom or keyword, then open the linked file and
read the lesson in full - the case matters as much as the rule. IDs are unique across this skill,
planning-and-executing-changes and refactoring-codebases; the general lessons cited here (E30, N4, N11,
V13, V19) are listed in planning-and-executing-changes' own index.

## Understanding the original (A) - [understanding-the-original.md](understanding-the-original.md)

- **A1** Inventory capabilities per entry point
- **A2** Derive data formats from the sample files as well as the code
- **A3** Run the original headlessly before designing
- **A4** The original's defects, and the data it never reads, are rulings

## Mapping onto the host (A) - [mapping-onto-the-host.md](mapping-onto-the-host.md)

- **A5** Port the inputs and outputs, not the program
- **A6** "The host already does this" needs a numeric equivalence check
- **A7** Carry units across the host's contract explicitly
- **A8** A default that refuses the users' input needs their say

## Proving equivalence (A) - [proving-equivalence.md](proving-equivalence.md)

- **A9** Bring the original's outputs over as goldens, on a generator kept in the repository
- **A10** Prove each fixed defect by putting the original's behaviour back
- **A11** Finish with every value on the real data, from a clean copy
