"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import json
import sys

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    METRICS,
    METRICS_EX4_TEST,
    METRICS_EX4_VALID,
    PROCESSED,
    TARGET,
    TRAIN_END,
    VALID_END,
)
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score() -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, model in MODELS.items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in [("valid", valid), ("test", test)]
        }
    return results


# --- Exercise 4: target transformations for the booster -------------------
# Not part of `make all`: reports/metrics.json stays the untransformed
# pipeline. Run with `python -m src.train --ex4` (validation only) and, once,
# `python -m src.train --ex4 --score-test` after the choice is fixed.
# Each entry maps the target to what hgb learns (forward) and back (inverse),
# using only columns known at prediction time, or a trend fit on train.

def _trend(train: pd.DataFrame):
    """Linear trend of cnt on calendar day, fit on training rows only."""
    t0 = train.dteday.min()
    days = lambda part: (part.dteday - t0).dt.days.to_numpy(dtype=float)
    slope, intercept = np.polyfit(days(train), train[TARGET].to_numpy(dtype=float), 1)
    return lambda part: intercept + slope * days(part)


def target_transforms(train: pd.DataFrame) -> dict:
    trend = _trend(train)
    return {
        "A_log": (lambda y, p: np.log(y), lambda z, p: np.exp(z)),
        "B_diff_lag_1": (lambda y, p: y - p.cnt_lag_1, lambda z, p: p.cnt_lag_1 + z),
        "C_log_ratio_roll_7": (
            lambda y, p: np.log(y / p.cnt_roll_7),
            lambda z, p: p.cnt_roll_7 * np.exp(z),
        ),
        "D_detrend_linear": (lambda y, p: y - trend(p), lambda z, p: trend(p) + z),
    }


# Chosen on validation by the rule pre-registered in docs/DECISIONS.md (best
# validation R^2 among the defensible B and C). Only this one is test-scored.
EX4_CHOSEN = "C_log_ratio_roll_7"


def target_experiment(score_test: bool = False) -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)
    splits = [("valid", valid)] + ([("test", test)] if score_test else [])
    transforms = target_transforms(train)
    if score_test:
        transforms = {EX4_CHOSEN: transforms[EX4_CHOSEN]}

    def score(pred_fn):
        return {
            name: {
                "r2": round(float(r2_score(part[TARGET], pred_fn(part))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], pred_fn(part))), 1),
            }
            for name, part in splits
        }

    out = {"scored": [s for s, _ in splits]}
    for name in ["baseline_persistence", "ridge", "hgb"]:
        model = clone(MODELS[name]).fit(train[cols], train[TARGET])
        out[name] = score(lambda p, m=model: m.predict(p[cols]))
    for name, (fwd, inv) in transforms.items():
        hgb = clone(MODELS["hgb"]).fit(train[cols], fwd(train[TARGET], train))
        out[f"hgb_{name}"] = score(lambda p, m=hgb, inv=inv: np.asarray(inv(m.predict(p[cols]), p)))
    return out


if __name__ == "__main__":
    if "--ex4" in sys.argv:
        score_test = "--score-test" in sys.argv
        res = target_experiment(score_test=score_test)
        path = METRICS_EX4_TEST if score_test else METRICS_EX4_VALID
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(res, indent=2))
        print(json.dumps(res, indent=2))
        sys.exit(0)
    res = fit_and_score()
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    METRICS.write_text(json.dumps(res, indent=2))
    print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
