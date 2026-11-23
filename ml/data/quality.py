"""Schema-aware validation for GiftBridge table-shaped CSV extracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "users": {"id", "email", "data_origin"},
    "user_roles": {"user_id", "role_key"},
    "villages": {"id", "name", "district", "data_origin"},
    "village_coordinators": {"village_id", "user_id", "data_origin"},
    "items": {"id", "donor_id", "category", "quantity", "condition_score", "data_origin"},
    "needs": {"id", "village_id", "created_by", "category", "quantity", "urgency", "data_origin"},
    "recommendation_runs": {"id", "model_stage", "data_origin"},
    "matches": {"id", "recommendation_run_id", "item_id", "need_id", "score", "data_origin"},
    "feedback": {"match_id", "actor_id", "label", "data_origin"},
    "events": {"event_type", "entity_type", "entity_id", "data_origin", "occurred_at"},
}
ID_COLUMNS = {"users": "id", "villages": "id", "items": "id", "needs": "id", "recommendation_runs": "id", "matches": "id"}


def validate_dataset(dataset_dir: str | Path, expected_origin: str | None = None) -> dict[str, Any]:
    root = Path(dataset_dir)
    issues: list[dict[str, str]] = []
    tables: dict[str, pd.DataFrame] = {}

    def issue(severity: str, table: str, message: str) -> None:
        issues.append({"severity": severity, "table": table, "message": message})

    for table, required in REQUIRED_COLUMNS.items():
        path = root / f"{table}.csv"
        if not path.exists():
            issue("error", table, f"Missing required file: {path.name}")
            continue
        try:
            frame = pd.read_csv(path, keep_default_na=False)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as error:
            issue("error", table, f"Could not read CSV: {error}")
            continue
        missing = sorted(required - set(frame.columns))
        if missing:
            issue("error", table, f"Missing columns: {', '.join(missing)}")
            continue
        tables[table] = frame

    for table, id_column in ID_COLUMNS.items():
        frame = tables.get(table)
        if frame is None:
            continue
        if frame[id_column].eq("").any():
            issue("error", table, f"{id_column} contains blank values")
        duplicates = int(frame[id_column].duplicated().sum())
        if duplicates:
            issue("error", table, f"{duplicates} duplicate {id_column} value(s)")

    for table, frame in tables.items():
        if "data_origin" not in frame:
            continue
        origins = set(frame["data_origin"].astype(str))
        invalid = origins - {"synthetic", "real"}
        if invalid:
            issue("error", table, f"Invalid data_origin value(s): {', '.join(sorted(invalid))}")
        if expected_origin and origins - {expected_origin}:
            issue("error", table, f"Expected only {expected_origin!r} rows, found: {', '.join(sorted(origins))}")
        if frame["data_origin"].eq("").any():
            issue("error", table, "data_origin contains blank values")

    for table, frame, column, parent in [
        ("items", tables.get("items"), "donor_id", "users"),
        ("needs", tables.get("needs"), "created_by", "users"),
        ("needs", tables.get("needs"), "village_id", "villages"),
        ("village_coordinators", tables.get("village_coordinators"), "user_id", "users"),
        ("village_coordinators", tables.get("village_coordinators"), "village_id", "villages"),
        ("matches", tables.get("matches"), "item_id", "items"),
        ("matches", tables.get("matches"), "need_id", "needs"),
        ("matches", tables.get("matches"), "recommendation_run_id", "recommendation_runs"),
        ("feedback", tables.get("feedback"), "match_id", "matches"),
        ("feedback", tables.get("feedback"), "actor_id", "users"),
    ]:
        parent_frame = tables.get(parent)
        if frame is not None and parent_frame is not None and column in frame and "id" in parent_frame:
            unknown = set(frame[column].astype(str)) - set(parent_frame["id"].astype(str)) - {""}
            if unknown:
                issue("error", table, f"{column} references {len(unknown)} unknown {parent} id(s)")

    _check_numeric(tables, issues, "items", "quantity", minimum=1)
    _check_numeric(tables, issues, "items", "condition_score", minimum=1, maximum=10, allow_blank=True)
    _check_numeric(tables, issues, "needs", "quantity", minimum=1)
    _check_numeric(tables, issues, "needs", "urgency", minimum=1, maximum=5)
    _check_numeric(tables, issues, "matches", "score", minimum=0, maximum=1)

    matches = tables.get("matches")
    if matches is not None:
        if matches.duplicated(["recommendation_run_id", "item_id", "need_id"]).any():
            issue("error", "matches", "Duplicate recommendation_run_id/item_id/need_id candidate")
        for parent_col, table_name in [("item_id", "items"), ("need_id", "needs"), ("recommendation_run_id", "recommendation_runs")]:
            parent = tables.get(table_name)
            if parent is not None and "data_origin" in matches and "data_origin" in parent:
                origins = parent.set_index("id")["data_origin"].to_dict()
                mismatch = matches.apply(lambda row: origins.get(row[parent_col]) not in (None, row["data_origin"]), axis=1)
                if mismatch.any():
                    issue("error", "matches", f"{int(mismatch.sum())} {parent_col} reference(s) cross data_origin")

    for table in ("items", "needs", "events"):
        frame = tables.get(table)
        if frame is not None and "created_at" in frame:
            bad_dates = pd.to_datetime(frame["created_at"], errors="coerce", utc=True).isna().sum()
            if bad_dates:
                issue("error", table, f"{int(bad_dates)} invalid created_at value(s)")
    events = tables.get("events")
    if events is not None:
        bad_dates = pd.to_datetime(events["occurred_at"], errors="coerce", utc=True).isna().sum()
        if bad_dates:
            issue("error", "events", f"{int(bad_dates)} invalid occurred_at value(s)")

    return {
        "dataset_dir": str(root),
        "expected_origin": expected_origin,
        "passed": not any(row["severity"] == "error" for row in issues),
        "row_counts": {table: len(frame) for table, frame in tables.items()},
        "issues": issues,
    }


def _check_numeric(
    tables: dict[str, pd.DataFrame],
    issues: list[dict[str, str]],
    table: str,
    column: str,
    *,
    minimum: float,
    maximum: float | None = None,
    allow_blank: bool = False,
) -> None:
    frame = tables.get(table)
    if frame is None or column not in frame:
        return
    values = pd.to_numeric(frame[column].replace("", pd.NA), errors="coerce")
    invalid = values.isna() & ~frame[column].eq("")
    if invalid.any() or (not allow_blank and values.isna().any()):
        issues.append({"severity": "error", "table": table, "message": f"{column} contains missing or non-numeric values"})
    out_of_range = values.notna() & (values < minimum)
    if maximum is not None:
        out_of_range |= values.notna() & (values > maximum)
    if out_of_range.any():
        issues.append({"severity": "error", "table": table, "message": f"{column} outside valid range [{minimum}, {maximum}]"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--expected-origin", choices=["synthetic", "real"])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = validate_dataset(args.input, expected_origin=args.expected_origin)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
