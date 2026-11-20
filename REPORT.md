# Forecasting daily bikeshare demand: report

## Results

Train = 2011 (348 days), validation = H1 2012 (182), test = H2 2012 (184), split by date. "After"
rows are `reports/metrics.json` from `make all` on the final code (15 features, including
`weather_severity_lag_1`). "Before" rows are the same pipeline at commit `89a9966`, the last commit
before the feature (14 features). Run `git checkout 89a9966 && make all` to reproduce them.

| Model | Feature | Valid R^2 | Valid MAE | Test R^2 | Test MAE |
|---|---|---|---|---|---|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_mean | after | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| ridge | after | 0.667 | 803.9 | 0.6124 | 910.6 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| hgb | after | 0.2437 | 1275.2 | -0.4687 | 1950.4 |

The baselines do not use the new feature, so their rows are unchanged. The test set was first
scored in the single Exercise 4 run (commit `5ffe8fd` fixed the choice beforehand), after all feature
work was decided. No feature, model or setting was changed in response to a test number. Printed
evidence for the explanation below: `cnt` spans 431-6,043 in train, 1,027-8,362 in validation and
22-8,714 in test. 71 of 182 validation days and 104 of 184 test days are above the 2011 maximum.
The naive model in `python -m src.leakage_demo` prints `Test R^2 = 1.000000`.

## Headline finding

Not "our model achieved R^2 = 0.61". A naive model handed `casual` and `registered` scores 1.000,
and that score is invalid: the two columns sum to `cnt` by definition. Under a split by date, the
2011 mean scores -2.14 on late 2012, because ridership grew about 60%. Against that moving target, a
standardised ridge on calendar, weather and lagged demand reaches a test R^2 of 0.61. "Yesterday
again" reaches 0.51, and it beats ridge on MAE (840 against 911 rides). Gradient boosting scores
-0.47. It beats the mean baseline but fails because trees cannot predict above the 2011 maximum of
6,043, and 104 of the 184 test days exceed it. My feature, yesterday's weather severity, raised
ridge's validation R^2 from 0.6475 to 0.667 (+0.0195) and hgb's from 0.2185 to 0.2437 (+0.0252),
both above the 0.01 noise threshold, so I kept it. On test it moved ridge from 0.5833 to 0.6124.

## Exercise 4: target transformation

**Why hgb loses.** The booster is trained on 2011, whose highest day is 6,043 rides. A tree predicts
an average of training targets, so it cannot go above that. 71 of the 182 validation days do. Plain
hgb's highest validation prediction is 5,580, and it under-predicts by 1,178 rides a day on
average. Ridge extrapolates the lagged-demand level linearly, so it is not capped.

**What was tried.** Four targets were fixed in `docs/DECISIONS.md` before any run, along with the
rule for choosing among them. Each was fit with the same booster (`max_iter=300`, `random_state=0`)
and the same 15 features, then inverted back to counts. Code: `python -m src.train --ex4`
(validation only) and `--ex4 --score-test`. Neither is part of `make all`, so
`reports/metrics.json` stays the untransformed pipeline.

| Target hgb learns | Valid R^2 | Valid MAE | Max valid prediction | Mean error |
|---|---|---|---|---|
| `cnt` (untransformed) | 0.2437 | 1275.2 | 5,580 | -1,178 |
| A. `log(cnt)` (control) | 0.1721 | 1337.8 | 5,670 | -1,277 |
| B. `cnt - cnt_lag_1` | 0.6254 | 804.3 | 8,307 | -371 |
| **C. `log(cnt / cnt_roll_7)`** | **0.7161** | **724.5** | 8,537 | -393 |
| D. residual from a 2011 linear trend | 0.7601 | 654.3 | 7,293 | +56 |
| _ridge, for reference_ | _0.6670_ | _803.9_ | _7,153_ | _-479_ |
| _persistence, for reference_ | _0.4507_ | _900.6_ | | |

The control confirms the mechanism. A log transform still caps the booster at the 2011 maximum, so
it does not help. B, C and D help because each takes the level from somewhere other than the trees:
B from yesterday, C from the last seven days, D from a time trend.

**Chosen: C**, by the pre-registered rule (best validation R^2 among B and C). The test set was
scored once, for C only, after that choice was committed (`5ffe8fd`):

| | Valid R^2 | Valid MAE | Test R^2 | Test MAE |
|---|---|---|---|---|
| hgb, `log(cnt / cnt_roll_7)` | 0.7161 | 724.5 | **0.6137** | **854.4** |
| ridge | 0.6670 | 803.9 | 0.6124 | 910.6 |
| hgb, untransformed | 0.2437 | 1275.2 | -0.4687 | 1950.4 |
| persistence | 0.4507 | 900.6 | 0.5099 | 840.1 |

On test, the transformed booster competes with ridge: R^2 is level (0.6137 against 0.6124) and MAE is
56 rides lower. It does not beat it convincingly. Its 0.049 validation lead shrank to 0.001,
partly because it was the best of two candidates on the same 182 days, and partly because H2 2012
is harder (it includes Hurricane Sandy). Persistence still has the lowest test MAE.

**Defensible, or just a way to win?**
- **C is defensible.** Its target and its inverse use only `cnt_roll_7`, which is known before the
  day. It assumes nothing about where the trend goes next: it predicts how today compares with last
  week, and the trees learn that from weather and calendar.
- **C has a known weakness.** After an anomaly the reference is wrong for seven days. A week after
  Sandy, `cnt_roll_7` still includes the 22-ride day, so C scales its predictions down.
- **D is the way to win.** It has the best validation score of all, and it gets it by assuming
  2011's growth line continues. That is the bet `src/config.py` refuses when it excludes time-index
  features. It happened to hold in H1 2012, which is why D's mean error is about zero. It would fail
  without warning if growth stalled, and nothing in the data available at prediction time would show
  it. D was never a candidate for selection and was not scored on test.

## Exercise 5: ridge vs persistence

Ridge is not worth deploying over persistence as trained. Its test R^2 lead (0.6124 against 0.5099) comes from a few days. On the 17 test days when demand moved more than 2,000 rides from the day before, ridge's MAE is 1,844 against persistence's 3,019, and it misses by more than 2,000 rides on 7 days against 17. On the other 167 days persistence is better (MAE 618 against 816; median miss 506 against 878), and it is closer on 109 of 184 days, so it wins overall MAE (840 against 911). The cause is that ridge learned 2011's level and under-predicts every 2012 day by 523 rides on average (persistence: +16). Validation shows the same pattern (bias -479; ridge closer on only 92 of 182 days). Removing that bias in hindsight would bring ridge's test MAE to 703, but that correction uses the test set, so it shows what a fix could do, not what the model does. Keep persistence deployed. Promote ridge only once it is refit on recent data (e.g. 2011 plus H1 2012) and beats persistence on MAE, not only R^2, on a holdout it has not seen. Numbers are from `python -m src.train --ex5`, run after the test set was scored, with nothing tuned on it.

## Attribution

**Model:** Claude Opus 5.5 (hosted, Anthropic) in Claude Code 2.1.126 did all coding-agent work.
I switched to it from the local `qwen3.5:9b` via Ollama (`bikeshare-coder`, 64k context) after a
2-turn task took 13 min 50 s on the local model; see `docs/DECISIONS.md`. The local model was set
up and kept for the `agent/audit.py` self-audit only. Results from the two models are not compared
with each other.

**What the agent generated** (I reviewed the output; the agent wrote it):
- `src/features.py`: the `weather_severity_lag_1` feature.
- `src/config.py`: `RAW_SHA256`, `RAW_FEATURE_COLS`, `ENCODED_COLS`, `REDUNDANT_COLS`, `DATE_COL`,
  `METRICS_EX4_VALID`, `METRICS_EX4_TEST`.
- `src/train.py`: `target_transforms`, `_trend`, `target_experiment`, `EX4_CHOSEN`,
  `error_breakdown`, and the `--ex4`, `--score-test` and `--ex5` flags.
- `tests/test_leakage.py`: `test_weather_lag_is_previous_calendar_day`,
  `test_weather_encoder_rejects_unknown_labels`, `test_no_feature_restates_a_forbidden_column`,
  `test_no_row_draws_on_a_missing_day`, `test_lag_7_is_a_true_7_day_lag`.
- `tests/test_contract.py`: `test_raw_csv_is_unmodified`, `test_every_raw_column_is_classified`.
- `.claude/skills/seed-fault/`: `SKILL.md` and `run_hook.sh`.
- Edits to `CLAUDE.md`, `README.md`, the `Makefile` `model` target and `.gitignore`.
- All prose in `REPORT.md`, `docs/SEEDED_FAULTS.md` and `docs/AUDIT.md` (including the verdict), and
  the `docs/DECISIONS.md` lines after the starter's five.
- The Exercise 3 audit of the teammate repo: a subagent run with `leakage-auditor.md` verbatim.

**Decisions that were mine:**
- **Inherited from the starter, then checked:** predict daily `cnt`; leakage means `casual` and
  `registered`, with time indexes and the unverified `cnt_2d_bfr` excluded too; split 2011 / H1 2012
  / H2 2012 by date; report the mean and persistence baselines. These trace to the starter's five
  lines in `DECISIONS.md`.
- **Made by me, choosing between options the agent laid out:**
  - which feature to add: yesterday's weather, from three candidates;
  - keeping it after a +0.0195 / +0.0252 validation gain;
  - moving agent work from the local model to Claude Opus 5.5;
  - the Exercise 5 position: do not deploy ridge as trained.

  Each has a dated `DECISIONS.md` line.
- **Delegated:** I asked the agent to finish the assignment acting for me. It therefore proposed,
  and I accepted without changing them:
  - the Exercise 4 candidate set and selection rule;
  - the judgement that the log ratio is defensible and the time trend is not;
  - the extra tests;
  - the `CLAUDE.md` rules;
  - the Exercise 3 verdict;
  - the judgement that these results are believable.

  Each is logged in `DECISIONS.md`. I am accountable for all of them as claims, but I did not reach
  them independently.

Exercise 6 (optional) was not done.
