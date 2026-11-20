---
name: seed-fault
description: Seed a deliberate fault, record whether the tests and the leakage hook catch it, then fix it with the red and green evidence committed. Use when asked to seed, plant or inject a fault, or to check whether the suite would catch a given bug.
argument-hint: <description of the fault>
allowed-tools: Read, Edit, Bash(make*), Bash(python -m pytest*), Bash(git status*), Bash(git diff*), Bash(git add*), Bash(git commit*), Bash(git checkout -- data/raw/*), Bash(shasum*), Bash(bash .claude/skills/seed-fault/run_hook.sh*)
---

# Seed a fault: $ARGUMENTS

Starting state (must be a clean tree and a green suite):
!`git status --short; python -m pytest tests/ -q 2>&1 | tail -1`

If the tree is dirty or any test fails, stop and say so. A fault seeded on a
red suite proves nothing.

1. **Predict first.** In one sentence, state the exact change. In a second
   sentence, name the test you expect to fail, or say "none" and why.
2. **Seed it** with the smallest possible change, in one Edit. Never edit
   `data/raw/`; see "Raw-data faults" below.
3. **Observe and keep the output.**
   - Run `make test` and keep the failing lines verbatim.
   - Run `bash .claude/skills/seed-fault/run_hook.sh <edited file>` and keep
     the exit code and stderr verbatim.
   - The hook runs only `tests/test_leakage.py`, and only after `src/*.py`
     edits. A fault caught only by `test_contract.py` shows exit 0 there.
     Record that; it is a finding, not an error.
4. **Commit the seed:** `Seed fault: <description> (tests red)`, or
   `(tests GREEN: not caught)`.
5. **If the suite stayed green, the fault is a gap. Close it.**
   - Write the smallest test that fails on this fault. Put it in
     `tests/test_leakage.py` if the hook should see it.
   - The test must check behaviour. A test that re-asserts what a helper
     already guarantees cannot fail.
   - Confirm it goes red for the right reason, re-run the hook, then commit
     `Add <test>: catches <fault> (red)`.
6. **Fix it.** Count the turns from seeing red to a green `make test`. Confirm
   the hook exits 0, then commit `Fix fault: <description> (<N> turns)`.
   `git diff` on `src/` should then match the state before step 2.
7. **Record it** in `docs/SEEDED_FAULTS.md`:
   - a section with the diff, the red output, the hook's exit code and
     stderr, the turn count, and whether your prediction held;
   - a row in its summary table.

   Paste real output only; never retype or tidy it. If step 5 added a test,
   add one line to `docs/DECISIONS.md`. Then commit.

## Raw-data faults

`data/raw/bike_daily.csv` is immutable; graders check that its sha256 begins
`a6bed1577f6e4de5`.
- Build the tampered copy outside the repo, then `cp` it in. The `cp` will
  ask for permission; that friction is intended.
- Run `make test`. Then restore the file with
  `git checkout -- data/raw/bike_daily.csv` and confirm the hash with
  `shasum -a 256` before doing anything else.
- Never commit anything under `data/raw/`.

## Rules
- Never amend, squash or rebase the seed and fix commits. That history is
  the evidence.
- Do not run `make train` or look at test-set scores. A fault check needs
  `make test` only.
