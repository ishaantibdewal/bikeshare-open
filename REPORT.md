# Forecasting daily bikeshare demand: report

## Results

_To do: written after the final `make all`; must match `reports/metrics.json` to the printed digit._

## Headline finding

_To do._

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

_To do: open by naming the model(s) used._
