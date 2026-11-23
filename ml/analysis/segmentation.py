"""Reproducible donor and village segmentation for exploratory campaign planning."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def _fit_clusters(frame: pd.DataFrame, features: list[str], seed: int, maximum_clusters: int = 3) -> pd.Series:
    if len(frame) < 2:
        return pd.Series([0] * len(frame), index=frame.index, dtype="int64")
    cluster_count = min(maximum_clusters, len(frame))
    scaled = StandardScaler().fit_transform(frame[features].fillna(0))
    labels = KMeans(n_clusters=cluster_count, random_state=seed, n_init=20).fit_predict(scaled)
    return pd.Series(labels, index=frame.index, dtype="int64")


def segment_donors(items: pd.DataFrame, as_of: str | pd.Timestamp, seed: int = 42) -> pd.DataFrame:
    as_of_timestamp = pd.Timestamp(as_of, tz="UTC") if pd.Timestamp(as_of).tzinfo is None else pd.Timestamp(as_of).tz_convert("UTC")
    donations = items.copy()
    donations["created_at"] = pd.to_datetime(donations["created_at"], utc=True)
    donors = donations.groupby("donor_id").agg(
        item_count=("id", "nunique"),
        quantity_total=("quantity", "sum"),
        last_donation=("created_at", "max"),
    )
    donors["recency_days"] = (as_of_timestamp - donors["last_donation"]).dt.days.clip(lower=0)
    donors["frequency_per_month"] = donors["item_count"] / max(((as_of_timestamp - donations["created_at"].min()).days / 30.4375), 1)
    features = ["recency_days", "item_count", "quantity_total", "frequency_per_month"]
    donors["cluster"] = _fit_clusters(donors, features, seed)
    cluster_order = donors.groupby("cluster")["quantity_total"].mean().sort_values().index.tolist()
    names = {cluster: label for cluster, label in zip(cluster_order, ["one_time_or_small", "regular_donor", "high_volume_champion"])}
    donors["segment"] = donors["cluster"].map(names)
    return donors.reset_index()


def segment_villages(needs: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    demand = needs.copy()
    fulfilled = demand["need_status"].eq("fulfilled").astype(float)
    demand["fulfilled_flag"] = fulfilled
    village_summary = demand.groupby("village_id").agg(
        total_need_units=("quantity", "sum"),
        need_count=("id", "nunique"),
        fulfillment_rate=("fulfilled_flag", "mean"),
    )
    category_units = pd.pivot_table(demand, index="village_id", columns="category", values="quantity", aggfunc="sum", fill_value=0)
    category_units.columns = [f"category_{name}" for name in category_units.columns]
    features = village_summary.join(category_units).fillna(0)
    features["cluster"] = _fit_clusters(features, list(features.columns), seed)
    category_columns = [column for column in features.columns if column.startswith("category_")]
    if category_columns:
        cluster_profile = features.groupby("cluster")[category_columns].mean()
        cluster_labels = cluster_profile.idxmax(axis=1).str.replace("category_", "", regex=False).to_dict()
        features["dominant_need_category"] = features["cluster"].map(cluster_labels)
    else:
        features["dominant_need_category"] = "none"
    return features.reset_index()


def segment_dataset(data_dir: str | Path, expected_origin: str = "synthetic", seed: int = 42) -> dict[str, pd.DataFrame]:
    root = Path(data_dir)
    items = pd.read_csv(root / "items.csv")
    needs = pd.read_csv(root / "needs.csv")
    for table, frame in (("items", items), ("needs", needs)):
        if set(frame["data_origin"].dropna()) != {expected_origin}:
            raise ValueError(f"{table} contains records outside expected origin {expected_origin!r}")
    if (root / "metadata.json").exists():
        import json
        as_of = json.loads((root / "metadata.json").read_text(encoding="utf-8"))["as_of"]
    else:
        as_of = pd.Timestamp.now(tz="UTC")
    return {
        "donors": segment_donors(items, as_of, seed),
        "villages": segment_villages(needs, seed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--origin", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/reports"))
    args = parser.parse_args()
    results = segment_dataset(args.input, args.origin, args.seed)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, frame in results.items():
        frame.to_csv(args.output / f"{name}_segments_{args.origin}.csv", index=False)
        print(f"{name}: {len(frame)} rows")


if __name__ == "__main__":
    main()
