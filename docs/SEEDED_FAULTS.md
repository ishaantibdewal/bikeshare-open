# Seeded faults

## Exercise 1: failing test written before the feature

Test `tests/test_leakage.py::test_weather_lag_is_previous_calendar_day` was
committed before `weather_severity_lag_1` existed in `src/features.py`.
It fails because the column is absent (the right reason), and the other
14 tests still pass:

```
$ make test
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_weather_lag_is_previous_calendar_day - Att...
1 failed, 14 passed in 1.30s
make: *** [test] Error 1

$ python -m pytest tests/test_leakage.py::test_weather_lag_is_previous_calendar_day -q --tb=line
E   AttributeError: 'DataFrame' object has no attribute 'weather_severity_lag_1'. Did you mean: 'weather_severity'?
FAILED tests/test_leakage.py::test_weather_lag_is_previous_calendar_day - Att...
1 failed in 0.22s
```

## Exercise 2: seeded faults

### How this was run

- **Agent:** Claude Opus 5.5 in Claude Code (hosted), not the local
  `bikeshare-coder`. On this machine (24 GB, `qwen3.5:9b`, 64k context)
  Claude Code's ~42.6k-token prompt made the local model take 13 min 50 s
  and 2 turns just to answer "run make test and say how many passed".
  Three fault-fix loops would have taken hours.
- **Hook output:** the agent session was not started inside this repo, so
  `.claude/settings.json` was not loaded. To get the hook's real stderr, I
  ran `.claude/hooks/check_leakage.sh` by hand, feeding it the same
  PostToolUse JSON Claude Code sends after an Edit:
  `{"hook_event_name":"PostToolUse","tool_name":"Edit","tool_input":{"file_path":"<repo>/src/features.py"}}`.
  Exit code and stderr below are what the script printed.
- **Turns:** agent tool calls from seeing the red output to a green
  `make test`.
- **Commits:** each fault is its own commit (tests red), followed by its fix.

| # | Fault | Caught by | Hook | Turns to fix |
|---|---|---|---|---|
| 1 | `casual` let through `feature_columns` | `test_no_forbidden_features` | exit 2 | 2 |
| 2 | `.shift(1)` deleted from `cnt_roll_7` | `test_rolling_mean_excludes_today` | exit 2 | 2 |
| 3 | `raise` removed from `encode_weather` | **nothing** (suite green), until `test_weather_encoder_rejects_unknown_labels` was added | exit 0, then exit 2 | 2 |
| 4 | `cp` of a tampered CSV into `data/raw/` | **nothing**, until `test_raw_csv_is_unmodified` was added | never runs | n/a (restored with `git checkout`) |

### Fault 1: forbidden column added to `feature_columns`

Commits `f8a170b` (seed) and `dc58a97` (fix).

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN - {"casual"}]
```

Red test output (`make test`):

```
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 14 passed in 1.33s
make: *** [test] Error 1
```

Hook stderr (exit code 2):

```
Leakage tests failed after editing /Users/ishaantibdewal/Desktop/DSC180A/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 weather_severity_lag_1
0   2011-01-10     10.0  WINTER  ....       1.0
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571                    0.0

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 0.23s
```

Fix: **2 turns** (one Edit restoring `FORBIDDEN`, one `make test` run: 15 passed; hook exit 0).

### Fault 2: `.shift(1)` deleted from `cnt_roll_7`

Commits `fa7c34b` (seed) and `df9060a` (fix).

```diff
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
```

Red test output (`make test`):

```
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 14 passed in 1.04s
make: *** [test] Error 1
```

Hook stderr (exit code 2):

```
Leakage tests failed after editing /Users/ishaantibdewal/Desktop/DSC180A/bikeshare-open/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 0.22s
```

Fix: **2 turns** (one Edit restoring `.shift(1)`, one `make test` run: 15 passed; hook exit 0).

Weakness noticed: this test checks a single date (`iloc[200]`) and passes
vacuously if that date's 7-day window crosses a gap (`if all(...)`). It
caught this fault, but a fault that only corrupted dates near 2011-03-10
would not be seen.

### Fault 3: the weather encoder's `raise` removed

Commits `2bf8ca0` (seed), `242c244` (new test, red) and `fa310f5` (fix).

```diff
     known = series.dropna()
     unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
```

**The suite stayed green and the hook was silent:**

```
$ make test
...............                                                          [100%]
15 passed in 1.05s

hook exit code: 0   (stderr empty)

$ python -c "import pandas as pd; from src.features import encode_weather; print(encode_weather(pd.Series(['GOOD','STORM','BAD'])).tolist())"
[0.0, nan, 2.0]
```

Why: every label in the shipped CSV is GOOD/MISTY/BAD, so no test that runs
on the real data can tell a strict encoder from a lenient one. The fault only
matters on data the tests never see: a UCI copy with codes 1-4, or a new
category. There the unknown label becomes NaN and `dropna()` deletes the row
without a word. That is the exact failure the encoder's docstring describes.

What catches it: a new test in `tests/test_leakage.py` (so the PostToolUse
hook runs it) that feeds the encoder an unseen label directly. With the fault
still in place:

```
$ make test
E       Failed: DID NOT RAISE ValueError
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 15 passed in 1.53s
make: *** [test] Error 1
```

Hook stderr (exit code 2):

```
Leakage tests failed after editing /Users/ishaantibdewal/Desktop/DSC180A/bikeshare-open/src/features.py:
......F..                                                                [100%]
=================================== FAILURES ===================================
_________________ test_weather_encoder_rejects_unknown_labels __________________

    def test_weather_encoder_rejects_unknown_labels():
        """Every label in the shipped CSV is known, so no test on the real data can
        see a weakened encoder: removing its `raise` leaves the suite green while an
        unseen label (e.g. a UCI code, or a new category) silently becomes NaN and is
        later deleted by dropna(). Feed it one directly."""
        assert encode_weather(pd.Series(["GOOD", "MISTY", "BAD"])).tolist() == [0.0, 1.0, 2.0]
>       with pytest.raises(ValueError, match="unmapped weather labels"):
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:79: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 8 passed in 0.23s
```

Fix: **2 turns** (one Edit restoring the `raise`, one `make test` run: 16 passed; hook exit 0).

### Fault 4: a `cp` into `data/raw/` that the hook cannot see

The change: a copy of `bike_daily.csv` with one day (2012-03-15, in the
validation set) altered. Weather was relabelled GOOD -> MISTY and `temp`
lowered by 10 (18.2025 -> 8.2025). It was then copied over the original from Bash:

```
$ cp <scratch>/bike_daily_tampered.csv data/raw/bike_daily.csv
$ shasum -a 256 data/raw/bike_daily.csv
a806b651a6dbd3e34f99e62e2871dae12ab91d5880d0996905b8bcb8e73e7295  data/raw/bike_daily.csv
```

What happened:

- **Permissions did not stop it.** The deny rules `Write(./data/raw/**)` and
  `Edit(./data/raw/**)` bind the Edit and Write tools only. `Bash(cp ...)` is
  a different tool and matches neither rule.
- **The hook never ran.** Its matcher is `Edit|Write`, so a Bash call is not
  routed to it, and the script itself also exits 0 for any path outside
  `src/` (fed a Bash payload, it printed nothing and exited 0).
- **Every test stayed green:** `16 passed in 1.48s`. The changed cells keep
  `casual + registered == cnt`, the shape, and the known labels intact.
- **The numbers moved silently.** `make all` validation R^2: ridge
  0.6670 -> 0.6644, hgb 0.2437 -> 0.2410 (valid MAE ridge 803.9 -> 808.4).
  Nothing in the output says the input changed.

What would catch it:

1. **A hash check (implemented).** `RAW_SHA256` in `src/config.py`, and
   `tests/test_contract.py::test_raw_csv_is_unmodified` compares the file's
   sha256 against it. With the tampered file in place:

   ```
   E       AssertionError: bike_daily.csv changed (sha256 a806b651a6dbd3e3, expected a6bed1577f6e4de5). Restore it with: git checkout -- data/raw/bike_daily.csv
   E       assert 'a806b651a6db...8bcb8e73e7295' == 'a6bed1577f6e...0c86a0b5ad9dc'
   E         
   E         - a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc
   E         + a806b651a6dbd3e34f99e62e2871dae12ab91d5880d0996905b8bcb8e73e7295
   FAILED tests/test_contract.py::test_raw_csv_is_unmodified - AssertionError: b...
   1 failed, 16 passed in 1.29s
   make: *** [test] Error 1
   ```

   Restored with `git checkout -- data/raw/bike_daily.csv`. The hash is back to
   `a6bed1577f6e4de5...`, 17 passed, and validation R^2 is back to 0.6670 / 0.2437.
2. **A Stop hook running `make test`** (not implemented). The hash test only
   helps if something runs it. A Stop hook would refuse to let the agent
   finish while it is red. The PostToolUse hook alone would not, because a
   Bash `cp` never triggers it.
3. **A PreToolUse hook on Bash** (not implemented) that blocks commands
   writing under `data/raw/`. It is brittle, because any command can write
   anywhere (`cp`, `mv`, `sed -i`, `python -c`, `>`).
4. **Filesystem permission:** `chmod -R a-w data/raw`. Cheap and covers every
   tool, but the agent's own Bash can undo it.
