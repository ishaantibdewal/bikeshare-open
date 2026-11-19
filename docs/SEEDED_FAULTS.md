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

_To do._
