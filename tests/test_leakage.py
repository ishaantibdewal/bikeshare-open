"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import pandas as pd
import pytest

from src.config import FORBIDDEN, TARGET
from src.features import build_features, encode_weather, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_no_feature_restates_a_forbidden_column(feats):
    """test_no_forbidden_features checks names. This checks values, so a
    leaky column copied in under an innocent name (out["rides_adj"] =
    out.casual), rescaled, or split into two features that sum to cnt is
    still caught. Honest features peak at |corr| 0.90 (cnt_roll_7 vs
    cnt_2d_bfr), so 0.99 has margin."""
    cols = feature_columns(feats)
    forbidden = [c for c in FORBIDDEN if c in feats.columns]
    corr = feats[cols + forbidden].corr().loc[cols, forbidden].abs()
    hits = corr.stack()[lambda s: s > 0.99]
    assert hits.empty, f"features that restate a forbidden column: {hits.to_dict()}"
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            assert not (feats[a] + feats[b] == feats[TARGET]).all(), f"{a} + {b} == {TARGET}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_no_row_draws_on_a_missing_day(feats):
    """Every kept row's 7-day history must exist in the raw data, or one of
    its lag/rolling features silently spans the gap. test_lags_are_true_calendar_lags
    skips dates whose previous day is missing, and test_calendar_is_complete_before_lagging
    calls reindex_to_calendar itself, so neither notices if build_features stops
    calling it: 2011-03-11 then gets the 03-09 count as its "1-day" lag."""
    raw_dates = set(load_raw().dteday)
    bad = [
        d.date()
        for d in feats.dteday
        if any(d - pd.Timedelta(days=k) not in raw_dates for k in range(1, 8))
        and d - pd.Timedelta(days=7) >= min(raw_dates)
    ]
    assert not bad, f"rows whose lag window spans a missing day: {bad}"


def test_lag_7_is_a_true_7_day_lag(feats):
    """cnt_lag_7 for date d must equal cnt on d-7, on every row. Nothing else
    checks its value: shifting it by 6 instead of 7 left the suite green."""
    by_date = feats.set_index("dteday")[TARGET]
    raw = load_raw().set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_7.items():
        week_ago = date - pd.Timedelta(days=7)
        if week_ago in raw.index:
            assert lag == raw[week_ago], f"bad 7-day lag at {date.date()}"
            checked += 1
    assert checked == len(by_date), "every kept row should have its d-7 count in the raw data"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def test_rolling_mean_excludes_today(feats):
    """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
    by_date = feats.set_index("dteday")[TARGET]
    date = feats.dteday.iloc[200]
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    if all(d in by_date.index for d in window):
        expected = sum(by_date[d] for d in window) / 7
        assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)


def test_weather_lag_is_previous_calendar_day(feats):
    """weather_severity_lag_1 on 2011-04-17 must be the severity recorded on
    2011-04-16, a BAD day (2). The 17th itself was GOOD (0), so a missing
    .shift(1) returns 0 here and fails. Expected value is read from the raw
    CSV for the strictly earlier date, not from the feature table."""
    raw = load_raw().set_index("dteday")
    prev, date = pd.Timestamp("2011-04-16"), pd.Timestamp("2011-04-17")
    assert raw.loc[prev, "weather"] == "BAD" and raw.loc[date, "weather"] == "GOOD"
    expected = 2.0  # WEATHER_ORDER["BAD"], hand-computed from the 2011-04-16 row
    got = feats.set_index("dteday").weather_severity_lag_1[date]
    assert got == expected, f"weather_severity_lag_1 on {date.date()} = {got}, expected {expected}"


def test_weather_encoder_rejects_unknown_labels():
    """Every label in the shipped CSV is known, so no test on the real data can
    see a weakened encoder: removing its `raise` leaves the suite green while an
    unseen label (e.g. a UCI code, or a new category) silently becomes NaN and is
    later deleted by dropna(). Feed it one directly."""
    assert encode_weather(pd.Series(["GOOD", "MISTY", "BAD"])).tolist() == [0.0, 1.0, 2.0]
    with pytest.raises(ValueError, match="unmapped weather labels"):
        encode_weather(pd.Series(["GOOD", "STORM"]))


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique
