# Audit (Exercise 3)

## Teammate repo audited with `/leakage-auditor`

- **Repo:** https://github.com/m1petersen/bikeshare-michael
- **Commit audited:** `6566d16` ("Add REPORT.md: results, headline finding, Exercises 4 and 5, attribution"), 2026-11-19
- **Diff under review:** `git diff 7a70abc HEAD`, i.e. everything changed since the unmodified starter (22 files)
- **How it was run:** the auditor definition in `.claude/agents/leakage-auditor.md` was given verbatim to a
  fresh Claude Code subagent (Claude Opus 5.5, `model: inherit`), with tools Read, Grep, Glob and Bash. The
  run used a local clone and this repo's pinned venv. The local `bikeshare-coder` model was not used
  because of its speed on this machine (see `docs/SEEDED_FAULTS.md`). The subagent was told that the
  teammate's docs are claims to verify, not evidence. It could run code, but could not commit or push.

### Auditor output (verbatim)

> All five checks pass on `git diff 7a70abc HEAD`: no feature restates `cnt` at time t, and the `log(cnt / cnt_roll_7)` target is built and inverted using only `cnt_roll_7` (counts from d-1 to d-7). Splits are by date and every `.fit()` sees training rows only. The 2011-03-10 gap is reindexed, so no lag spans it. The 14 dropped rows are exactly the bound the tests enforce. Mean and persistence baselines are reported next to every model score in `reports/metrics.json`.
>
> ## Auditor run notes
>
> - **Starting state:** `git log`, `git status --short` and `git diff 7a70abc HEAD --stat` showed a clean tree at HEAD 6566d16, with 22 files changed since the starter. The code changes are in `src/config.py`, `src/features.py` (`cnt_roll_3`), `src/train.py` (`LogRatioTarget`, `--valid-only`), `tests/`, `agent/audit.py` and `Makefile`.
> - **Test suite:** `python -m pytest tests/ -q` gave `24 passed in 1.79s`.
> - **Pipeline rerun:** `python -m src.features` printed `OK features: 714 rows, 15 features`. I copied the committed metrics to scratch, ran `python -m src.train`, then ran `diff reports/metrics.json <copy>`. The result was **IDENTICAL**, so the committed metrics reproduce exactly.
> - **Probe script** (scratch `probe.py`, run with `PYTHONPATH=<repo>`):
>   - **Row loss:** `raw 728 feats 714 lost 14`. That is the 7 warm-up days plus the 7 days after the 2011-03-10 gap. `test_only_expected_rows_are_dropped` allows at most 14.
>   - **Calendar gap:** the rows near the gap are 03-08, 03-09, then 03-18 onward. The days 03-11 to 03-17 are dropped, so no lag spans the missing day.
>   - **Target leakage, by perturbation:** I tripled `cnt`, `casual` and `registered` on 2012-03-15, 2012-09-20 and 2012-12-01, rebuilt the features and predicted with `hgb_log_ratio` (fit on 2011).
>     - The same-day prediction did not change. For example, 2012-09-20 stayed at 7638.56 before and after.
>     - The next-day prediction did change (7450.31 to 9736.84), which is what a lag should do.
>     - So nothing from day t reaches the transformed target's features or its inverse.
>   - **Correlation with `cnt`:** the highest feature is `cnt_roll_7` at 0.849. OLS on all 15 features fits the full sample with R^2 0.83, so no column or linear combination restates the target.
>   - **`cnt_roll_7` as divisor:** its minimum is 1022.7, so there are no zero or negative divisors.
>   - **Validation-only check:** `test_beats_the_mean_baseline` fits ridge on training rows and scores validation only.
>   - **2011 maximum:** the training maximum is 6043. 71 of 182 validation days and 104 of 184 test days exceed it, which matches the repo's claim.
>   - **Exercise 4 target table:** I recomputed the five ratio and difference targets on validation and all match REPORT.md. `log/cnt_roll_7` gave (0.745, 687.9), `log/cnt_roll_3` (0.6886, 751.2), `log/cnt_lag_1` (0.6148, 831.8), `diff cnt_roll_7` (0.7209, 722.4) and `diff cnt_lag_1` (0.6251, 805.4).
>   - **Persistence against `hgb_log_ratio`:** test MAE is 840.08 against 850.17, and `hgb_log_ratio` is closer on 79 of 184 days. This matches REPORT.md's own statement that it does not beat persistence on MAE.
> - **Ridge without same-day weather:** an inline check gave validation R^2 0.4644 and MAE 1035.5, which matches REPORT.md. Ridge's mean error is -508 (validation) and -551 (test), which also matches.
> - **Cleanup:** `git status --short` was empty before cleanup, since the rerun wrote byte-identical metrics. I then ran `git -C /Users/ishaantibdewal/Desktop/DSC180A/audit/bikeshare-michael checkout -- .`, and `git status --short` was still empty afterwards. Only gitignored files remain: `data/processed/`, `.pytest_cache/` and `__pycache__/`. I did not modify `data/raw/` or `bikeshare-open`, and made no commits, pushes or remote changes.

### Verdict

No finding changes a number. The auditor reported none, and I agree with its all-pass conclusion
on the evidence it produced. Most of that evidence comes from running the code, not reading it:
- the committed `metrics.json` reproduces byte-for-byte;
- the perturbation test shows tripling a day's counts leaves that same day's prediction unchanged, so the
  Exercise 4 target `log(cnt / cnt_roll_7)` uses only d-1..d-7;
- row loss is exactly the 14-row bound.

I re-ran the 24 tests at `6566d16` myself (24 passed). Two observations fall outside the auditor's five checks and
change no number, but I would raise them with the teammate:
- **The committed metrics include the transformed model.** `reports/metrics.json` carries an
  `hgb_log_ratio` row next to the untransformed `ridge` and `hgb`, and the assignment asks for the
  committed metrics to be the untransformed pipeline.
- **The 0.745 validation R^2 is optimistic.** It was chosen as the best of five targets on the same
  182 validation days. The honest figure for that model is its once-scored test R^2, 0.6169, which
  REPORT.md does report.

## Own repo audited with `agent/audit.py`

_To do: run on the finished repo; output goes to `reports/audit.jsonl`._
