"""Time-ordered category demand forecast: seasonal-naive versus LightGBM."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def _monthly_series(needs: pd.DataFrame) -> dict[str, pd.Series]:
    frame = needs.copy()
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    frame["month"] = frame["created_at"].dt.tz_localize(None).dt.to_period("M")
    result: dict[str, pd.Series] = {}
    for category, group in frame.groupby("category"):
        series = group.groupby("month")["quantity"].sum().sort_index()
        full_index = pd.period_range(series.index.min(), series.index.max(), freq="M")
        result[str(category)] = series.reindex(full_index, fill_value=0).astype(float)
    return result


def _features(values: list[float], month: pd.Period, category_code: int) -> dict[str, float]:
    lag_1 = values[-1] if values else 0.0
    lag_3 = values[-3] if len(values) >= 3 else lag_1
    lag_12 = values[-12] if len(values) >= 12 else lag_1
    rolling_mean_3 = float(np.mean(values[-3:])) if values else 0.0
    angle = 2 * np.pi * month.month / 12
    return {
        "category_code": float(category_code),
        "month_sin": float(np.sin(angle)),
        "month_cos": float(np.cos(angle)),
        "lag_1": float(lag_1),
        "lag_3": float(lag_3),
        "lag_12": float(lag_12),
        "rolling_mean_3": rolling_mean_3,
    }


def _seasonal_naive(values: list[float], index: int) -> float:
    if index >= 12:
        return float(values[index - 12])
    return float(values[index - 1]) if index else 0.0


def forecast_demand(
    needs: pd.DataFrame,
    *,
    forecast_months: int = 3,
    validation_months: int = 3,
    seed: int = 42,
) -> dict[str, Any]:
    """Use a chronological holdout and fit a pooled LightGBM model for future estimates."""
    if forecast_months < 1 or validation_months < 1:
        raise ValueError("forecast_months and validation_months must be positive")
    origins = set(needs["data_origin"].dropna())
    if len(origins) != 1 or not origins.issubset({"synthetic", "real"}):
        raise ValueError("Forecast input must contain exactly one valid data_origin")
    data_origin = next(iter(origins))
    monthly = _monthly_series(needs)
    if not monthly or min(len(series) for series in monthly.values()) < validation_months + 3:
        raise ValueError("At least validation_months + 3 consecutive months are required for each category")
    try:
        from lightgbm import LGBMRegressor
    except ImportError as error:
        raise RuntimeError("Install project dependencies with `python -m pip install -r requirements.txt` to use LightGBM.") from error

    feature_columns = ["category_code", "month_sin", "month_cos", "lag_1", "lag_3", "lag_12", "rolling_mean_3"]
    categories = sorted(monthly)
    category_codes = {name: index for index, name in enumerate(categories)}
    train_rows: list[dict[str, float]] = []
    validation_rows: list[dict[str, float]] = []
    observed_values: dict[str, list[float]] = {}
    validation_actuals: list[float] = []
    validation_baseline: list[float] = []

    for category in categories:
        series = monthly[category]
        values = series.tolist()
        split_index = len(values) - validation_months
        observed_values[category] = values
        for index in range(1, len(values)):
            row = _features(values[:index], series.index[index], category_codes[category])
            target = float(values[index])
            if index < split_index:
                train_rows.append({**row, "target": target})
            else:
                validation_rows.append({**row, "target": target, "category": category, "period": str(series.index[index]), "index": index})
                validation_actuals.append(target)
                validation_baseline.append(_seasonal_naive(values, index))

    if len(train_rows) < 12:
        raise ValueError("Too few pre-validation observations to fit the pooled LightGBM model")
    train = pd.DataFrame(train_rows)
    validation = pd.DataFrame(validation_rows)
    model = LGBMRegressor(
        objective="regression",
        n_estimators=120,
        learning_rate=0.04,
        max_depth=3,
        num_leaves=7,
        min_child_samples=5,
        random_state=seed,
        verbosity=-1,
    )
    model.fit(train[feature_columns], train["target"])
    validation_prediction = np.maximum(0, model.predict(validation[feature_columns]))
    actual = np.asarray(validation_actuals, dtype=float)
    baseline = np.asarray(validation_baseline, dtype=float)
    residuals = actual - validation_prediction
    interval_low, interval_high = np.quantile(residuals, [0.05, 0.95])

    def metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
        denominator = max(float(np.abs(observed).sum()), 1.0)
        return {
            "mae": float(mean_absolute_error(observed, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(observed, predicted))),
            "wape": float(np.abs(observed - predicted).sum() / denominator),
        }

    validation_report = {
        "validation_months_per_category": validation_months,
        "split": "chronological; last validation_months observations held out within each category",
        "seasonal_naive": metrics(actual, baseline),
        "lightgbm": metrics(actual, validation_prediction),
        "prediction_interval_method": "pooled 5th/95th percentiles of chronological validation residuals; approximate, not calibrated coverage",
    }

    future_rows: list[dict[str, Any]] = []
    for category in categories:
        values = observed_values[category].copy()
        last_period = monthly[category].index[-1]
        for step in range(1, forecast_months + 1):
            period = last_period + step
            row = _features(values, period, category_codes[category])
            prediction = max(0.0, float(model.predict(pd.DataFrame([row], columns=feature_columns))[0]))
            future_rows.append({
                "category": category,
                "month": str(period),
                "forecast": prediction,
                "prediction_lower_approx": max(0.0, prediction + float(interval_low)),
                "prediction_upper_approx": max(0.0, prediction + float(interval_high)),
                "data_origin": data_origin,
            })
            values.append(prediction)

    return {
        "validation": validation_report,
        "future_forecast": pd.DataFrame(future_rows),
        "model": model,
        "limitation": "Short, sparse histories make LightGBM and residual intervals unstable. Use longer real pilot history, time-based backtests, and report synthetic/real results separately.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--origin", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("data/reports"))
    args = parser.parse_args()
    needs = pd.read_csv(args.input / "needs.csv")
    if set(needs["data_origin"].dropna()) != {args.origin}:
        raise ValueError(f"Input must contain only {args.origin!r} rows")
    result = forecast_demand(needs, forecast_months=args.months)
    args.output.mkdir(parents=True, exist_ok=True)
    suffix = args.origin
    result["future_forecast"].to_csv(args.output / f"demand_forecast_{suffix}.csv", index=False)
    print(pd.Series(result["validation"]).to_json(indent=2))
    print(result["limitation"])


if __name__ == "__main__":
    main()
