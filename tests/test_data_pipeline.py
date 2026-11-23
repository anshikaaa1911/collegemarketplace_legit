from __future__ import annotations

from pathlib import Path

import pandas as pd

from ml.data.generate_synthetic import generate_dataset
from ml.data.quality import validate_dataset


def _generate(path: Path) -> None:
    generate_dataset(
        path,
        seed=17,
        months=6,
        village_count=3,
        donor_count=8,
        volunteer_count=2,
        item_count=80,
        need_count=24,
    )


def test_generated_dataset_passes_quality_checks(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "synthetic"
    _generate(dataset_dir)

    report = validate_dataset(dataset_dir, expected_origin="synthetic")

    assert report["passed"] is True
    assert report["issues"] == []
    assert report["row_counts"]["items"] == 80
    assert report["row_counts"]["needs"] == 24


def test_generation_is_deterministic_for_fixed_seed(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _generate(first)
    _generate(second)

    for csv_path in first.glob("*.csv"):
        assert csv_path.read_bytes() == (second / csv_path.name).read_bytes()


def test_quality_checks_detect_invalid_values_and_mixed_origins(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "synthetic"
    _generate(dataset_dir)
    items_path = dataset_dir / "items.csv"
    items = pd.read_csv(items_path)
    items.loc[0, "condition_score"] = 12
    items.to_csv(items_path, index=False)
    matches_path = dataset_dir / "matches.csv"
    matches = pd.read_csv(matches_path)
    matches.loc[0, "data_origin"] = "real"
    matches.to_csv(matches_path, index=False)

    report = validate_dataset(dataset_dir, expected_origin="synthetic")
    messages = [issue["message"] for issue in report["issues"]]

    assert report["passed"] is False
    assert any("condition_score" in message for message in messages)
    assert any("Expected only 'synthetic'" in message for message in messages)
