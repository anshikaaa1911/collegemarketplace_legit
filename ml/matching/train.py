"""Train and compare baseline, LightGBM regression, and LambdaRank models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupShuffleSplit

FEATURE_COLUMNS = [
    "category_match",
    "age_compatibility",
    "condition_normalized",
    "quantity_ratio",
    "urgency_normalized",
    "waiting_normalized",
    "distance_fit",
    "seasonal_relevance",
    "distance_km",
    "distance_available",
]
FEEDBACK_RELEVANCE = {"rejected": 0, "accepted": 1, "fulfilled": 2}


def _ndcg_at_k(labels: np.ndarray, scores: np.ndarray, k: int = 5) -> float:
    if len(labels) == 0:
        return 0.0
    order = np.argsort(-scores)[:k]
    ideal = np.argsort(-labels)[:k]
    discounts = 1 / np.log2(np.arange(2, len(order) + 2))
    gains = np.power(2, labels[order]) - 1
    ideal_gains = np.power(2, labels[ideal]) - 1
    dcg = float(np.sum(gains * discounts))
    idcg = float(np.sum(ideal_gains * discounts[:len(ideal)]))
    return dcg / idcg if idcg else 0.0


def _ranking_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict[str, float]:
    scored = frame[["need_id", "relevance"]].copy()
    scored["score"] = scores
    ndcg_values: list[float] = []
    precision_values: list[float] = []
    for _, group in scored.groupby("need_id", sort=False):
        labels = group["relevance"].to_numpy(dtype=int)
        values = group["score"].to_numpy(dtype=float)
        order = np.argsort(-values)
        ndcg_values.append(_ndcg_at_k(labels, values, k=5))
        top_labels = labels[order[:3]]
        precision_values.append(float(np.count_nonzero(top_labels > 0) / 3))
    return {
        "ndcg_at_5": float(np.mean(ndcg_values)) if ndcg_values else 0.0,
        "precision_at_3": float(np.mean(precision_values)) if precision_values else 0.0,
    }


def _group_sizes(need_ids: pd.Series) -> list[int]:
    return need_ids.value_counts(sort=False).tolist()


def _prepare_dataset(data_dir: Path, expected_origin: str) -> pd.DataFrame:
    matches = pd.read_csv(data_dir / "matches.csv")
    feedback = pd.read_csv(data_dir / "feedback.csv")
    for table, frame in (("matches", matches), ("feedback", feedback)):
        origins = set(frame["data_origin"].dropna())
        if origins != {expected_origin}:
            raise ValueError(f"{table} must contain only {expected_origin!r} rows, found {sorted(origins)}")
    feedback = feedback.sort_values("created_at").drop_duplicates("match_id", keep="last")
    frame = matches.merge(feedback[["match_id", "label"]], left_on="id", right_on="match_id", how="inner")
    if frame.empty:
        raise ValueError("No matches have feedback labels; collect coordinator responses before training.")
    feature_dicts = frame["feature_snapshot"].map(json.loads)
    features = pd.json_normalize(feature_dicts)
    for column in FEATURE_COLUMNS:
        if column not in features:
            features[column] = np.nan
    frame = pd.concat([frame.reset_index(drop=True), features[FEATURE_COLUMNS].reset_index(drop=True)], axis=1)
    frame["relevance"] = frame["label"].map(FEEDBACK_RELEVANCE)
    frame = frame.dropna(subset=["relevance", "score", "need_id"]).copy()
    frame["relevance"] = frame["relevance"].astype(int)
    frame["target"] = frame["relevance"] / 2.0
    frame["distance_available"] = frame["distance_km"].notna().astype(float)
    for column in FEATURE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame


def train_and_evaluate(data_dir: str | Path, expected_origin: str = "synthetic", seed: int = 42) -> dict[str, Any]:
    """Use need-grouped holdout; synthetic labels evaluate code paths, not real utility."""
    try:
        from lightgbm import LGBMRanker, LGBMRegressor
    except ImportError as error:
        raise RuntimeError("Install project dependencies with `python -m pip install -r requirements.txt` to train LightGBM models.") from error

    frame = _prepare_dataset(Path(data_dir), expected_origin)
    if frame["need_id"].nunique() < 4:
        raise ValueError("At least four distinct needs are required for grouped train/test evaluation")
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    train_indices, test_indices = next(splitter.split(frame, frame["relevance"], groups=frame["need_id"]))
    train = frame.iloc[train_indices].sort_values(["need_id", "rank_position"]).reset_index(drop=True)
    test = frame.iloc[test_indices].sort_values(["need_id", "rank_position"]).reset_index(drop=True)
    x_train = train[FEATURE_COLUMNS]
    x_test = test[FEATURE_COLUMNS]

    regressor = LGBMRegressor(
        objective="regression", n_estimators=150, learning_rate=0.04, max_depth=4,
        num_leaves=15, min_child_samples=8, random_state=seed, verbosity=-1,
    )
    regressor.fit(x_train, train["target"])
    regression_scores = np.clip(regressor.predict(x_test), 0, 1)

    ranker = LGBMRanker(
        objective="lambdarank", metric="ndcg", eval_at=[3, 5],
        n_estimators=150, learning_rate=0.04, max_depth=4, num_leaves=15,
        min_child_samples=8, lambdarank_truncation_level=5,
        random_state=seed, verbosity=-1,
    )
    ranker.fit(x_train, train["relevance"], group=_group_sizes(train["need_id"]))
    ranker_scores = ranker.predict(x_test)
    baseline_scores = np.clip(test["score"].to_numpy(dtype=float), 0, 1)
    target = test["target"].to_numpy(dtype=float)

    metrics = {}
    for name, scores in (("weighted_baseline", baseline_scores), ("lightgbm_regression", regression_scores), ("lightgbm_lambdarank", ranker_scores)):
        metrics[name] = {
            "rmse_vs_normalized_feedback": float(np.sqrt(mean_squared_error(target, np.clip(scores, 0, 1)))),
            **_ranking_metrics(test, scores),
        }
    return {
        "data_origin": expected_origin,
        "seed": seed,
        "split": "GroupShuffleSplit by need_id; no need appears in both train and test",
        "train_needs": int(train["need_id"].nunique()),
        "test_needs": int(test["need_id"].nunique()),
        "train_candidates": int(len(train)),
        "test_candidates": int(len(test)),
        "feedback_counts": frame["label"].value_counts().to_dict(),
        "metrics": metrics,
        "models": {"regression": regressor, "ranker": ranker},
        "limitation": "Synthetic feedback is simulated from the baseline features; performance is pipeline validation only. Real evaluation requires coordinator feedback and repeated group-aware or temporal holdouts.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--origin", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--report", type=Path, default=Path("data/reports/match_model_evaluation.json"))
    args = parser.parse_args()
    result = train_and_evaluate(args.input, expected_origin=args.origin, seed=args.seed)
    report = {key: value for key, value in result.items() if key != "models"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
