"""Exploratory need-level tests for match outcomes; not causal estimates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

ACCEPTED = {"accepted", "pickup_scheduled", "in_transit", "delivered", "confirmed"}


def _cliffs_delta(left: np.ndarray, right: np.ndarray) -> float:
    if not len(left) or not len(right):
        return float("nan")
    comparisons = left[:, None] - right[None, :]
    return float((np.count_nonzero(comparisons > 0) - np.count_nonzero(comparisons < 0)) / comparisons.size)


def run_hypotheses(data_dir: str | Path, expected_origin: str = "synthetic") -> dict[str, Any]:
    root = Path(data_dir)
    items = pd.read_csv(root / "items.csv")
    needs = pd.read_csv(root / "needs.csv")
    matches = pd.read_csv(root / "matches.csv")
    for name, frame in (("items", items), ("needs", needs), ("matches", matches)):
        origins = set(frame["data_origin"].dropna())
        if origins != {expected_origin}:
            raise ValueError(f"{name} must contain only {expected_origin!r} rows, found {sorted(origins)}")

    matches["features"] = matches["feature_snapshot"].map(json.loads)
    top = matches.sort_values(["need_id", "rank_position"]).drop_duplicates("need_id").copy()
    top["accepted"] = top["match_status"].isin(ACCEPTED)
    top["condition_score"] = top["features"].map(lambda value: value.get("condition_normalized")) * 10
    top["distance_km"] = top["features"].map(lambda value: value.get("distance_km"))
    top = top.merge(needs[["id", "urgency", "created_at"]], left_on="need_id", right_on="id", how="left", suffixes=("", "_need"))

    condition_accepted = top.loc[top["accepted"], "condition_score"].dropna().to_numpy(dtype=float)
    condition_rejected = top.loc[~top["accepted"], "condition_score"].dropna().to_numpy(dtype=float)
    if min(len(condition_accepted), len(condition_rejected)) >= 5:
        condition_test = mannwhitneyu(condition_accepted, condition_rejected, alternative="two-sided")
        condition_result = {
            "test": "Mann-Whitney U; one top-ranked candidate per need",
            "n_accepted": int(len(condition_accepted)),
            "n_rejected": int(len(condition_rejected)),
            "median_condition_accepted": float(np.median(condition_accepted)),
            "median_condition_rejected": float(np.median(condition_rejected)),
            "cliffs_delta": _cliffs_delta(condition_accepted, condition_rejected),
            "p_value": float(condition_test.pvalue),
            "assumption": "Need outcomes are independent; distributions need not be normal. Top-ranked candidate selection limits the estimand to first recommendations.",
        }
    else:
        condition_result = {"test": "not estimable", "reason": "Fewer than five top-ranked accepted or rejected needs."}

    distance_rows = top.dropna(subset=["distance_km"])
    if len(distance_rows) >= 5 and distance_rows["accepted"].nunique() == 2:
        distance_test = spearmanr(distance_rows["distance_km"], distance_rows["accepted"].astype(int))
        distance_result = {
            "test": "Spearman rank correlation; top-ranked candidate per need",
            "n_needs": int(len(distance_rows)),
            "rho": float(distance_test.statistic),
            "p_value": float(distance_test.pvalue),
            "assumption": "Monotonic association and independent needs. This unadjusted association is not a causal distance effect.",
        }
    else:
        distance_result = {"test": "not estimable", "reason": "Coordinates unavailable or fewer than five usable needs with both outcome classes."}

    needs["created_at"] = pd.to_datetime(needs["created_at"], utc=True)
    completed = top.loc[top["match_status"] == "confirmed", ["need_id", "updated_at"]].copy()
    completed["confirmed_at"] = pd.to_datetime(completed["updated_at"], utc=True)
    completed = completed.merge(needs[["id", "urgency", "created_at"]], left_on="need_id", right_on="id", how="left")
    completed["days_to_confirmation"] = (completed["confirmed_at"] - completed["created_at"]).dt.total_seconds() / 86400
    high_urgency = completed.loc[completed["urgency"] >= 4, "days_to_confirmation"].dropna().to_numpy(dtype=float)
    lower_urgency = completed.loc[completed["urgency"] < 4, "days_to_confirmation"].dropna().to_numpy(dtype=float)
    if min(len(high_urgency), len(lower_urgency)) >= 5:
        urgency_test = mannwhitneyu(high_urgency, lower_urgency, alternative="two-sided")
        urgency_result = {
            "test": "Mann-Whitney U among confirmed needs only",
            "n_high_urgency": int(len(high_urgency)),
            "n_lower_urgency": int(len(lower_urgency)),
            "median_days_high_urgency": float(np.median(high_urgency)),
            "median_days_lower_urgency": float(np.median(lower_urgency)),
            "cliffs_delta": _cliffs_delta(high_urgency, lower_urgency),
            "p_value": float(urgency_test.pvalue),
            "assumption": "Confirmed needs are independent. Conditioning on confirmation can introduce selection bias; this does not establish that urgency causes faster fulfillment.",
        }
    else:
        urgency_result = {"test": "not estimable", "reason": "Fewer than five confirmed needs in either urgency group."}

    return {
        "data_origin": expected_origin,
        "synthetic_warning": "If data_origin is synthetic, all p-values and effect sizes describe only the simulation.",
        "tests": {
            "condition_and_acceptance": condition_result,
            "distance_and_acceptance": distance_result,
            "urgency_and_confirmation_time": urgency_result,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--origin", choices=["synthetic", "real"], default="synthetic")
    args = parser.parse_args()
    print(json.dumps(run_hypotheses(args.input, args.origin), indent=2))


if __name__ == "__main__":
    main()
