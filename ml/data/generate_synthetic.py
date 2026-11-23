"""Generate deterministic, explicitly synthetic GiftBridge CSV fixtures."""

from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd

DATA_ORIGIN = "synthetic"
CATEGORIES = ["clothes", "books", "stationery", "toys", "utensils", "blankets", "electronics", "other"]
AGE_GROUPS = ["infant", "child", "teen", "adult", "all_ages", "unspecified"]
BASE_WEIGHTS = np.array([0.19, 0.15, 0.16, 0.10, 0.10, 0.12, 0.08, 0.10], dtype=float)
WINTER_CATEGORIES = {"clothes", "blankets"}
SCHOOL_CATEGORIES = {"books", "stationery"}
REJECTION_REASONS = ["condition_mismatch", "quantity_mismatch", "age_group_mismatch", "distance_or_transport", "need_already_met"]


def _id(seed: int, entity: str, key: Any) -> str:
    return str(uuid5(NAMESPACE_URL, f"giftbridge:{seed}:{entity}:{key}"))


def _iso(value: datetime | date) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _seasonal_weights(month: int, profile: int = 0) -> np.ndarray:
    weights = BASE_WEIGHTS.copy()
    if month in (11, 12, 1, 2):
        for category in WINTER_CATEGORIES:
            weights[CATEGORIES.index(category)] *= 2.1
    if month in (5, 6, 7, 8):
        for category in SCHOOL_CATEGORIES:
            weights[CATEGORIES.index(category)] *= 1.8
    if month in (9, 10, 11):
        weights[CATEGORIES.index("toys")] *= 1.35
    preferred = profile % len(CATEGORIES)
    weights[preferred] *= 2.6
    weights[(preferred + 1) % len(CATEGORIES)] *= 1.35
    return weights / weights.sum()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(value))


def _weighted_score(features: dict[str, Any]) -> float:
    weights = {
        "category_match": 0.20,
        "age_compatibility": 0.15,
        "condition_normalized": 0.18,
        "quantity_ratio": 0.15,
        "urgency_normalized": 0.10,
        "waiting_normalized": 0.08,
        "distance_fit": 0.08,
        "seasonal_relevance": 0.06,
    }
    present = {key: weight for key, weight in weights.items() if features.get(key) is not None}
    denominator = sum(present.values())
    return sum(features[key] * weight for key, weight in present.items()) / denominator


def _timestamp(rng: np.random.Generator, start: datetime, end: datetime) -> datetime:
    span = max(1, int((end - start).total_seconds()))
    return start + timedelta(seconds=int(rng.integers(0, span)))


def generate_dataset(
    output_dir: str | Path,
    *,
    seed: int = 42,
    months: int = 12,
    as_of: date = date(2026, 10, 31),
    village_count: int = 8,
    donor_count: int = 60,
    volunteer_count: int = 10,
    item_count: int = 1200,
    need_count: int = 320,
    campus_latitude: float | None = None,
    campus_longitude: float | None = None,
) -> dict[str, pd.DataFrame]:
    """Generate normalized table-shaped fixture CSVs with stable UUIDs and a fixed seed."""
    if months < 1 or village_count < 1 or donor_count < 1 or volunteer_count < 1:
        raise ValueError("months, village_count, donor_count, and volunteer_count must be positive")
    if item_count < 1 or need_count < 1:
        raise ValueError("item_count and need_count must be positive")
    if (campus_latitude is None) != (campus_longitude is None):
        raise ValueError("provide both campus_latitude and campus_longitude, or neither")
    if campus_latitude is not None and not (-90 <= campus_latitude <= 90 and -180 <= campus_longitude <= 180):
        raise ValueError("campus coordinates are outside valid latitude/longitude ranges")

    rng = np.random.default_rng(seed)
    as_of_dt = datetime.combine(as_of, time(23, 59, tzinfo=timezone.utc))
    start_dt = as_of_dt - timedelta(days=round(months * 30.4375))
    villages: list[dict[str, Any]] = []
    users: list[dict[str, Any]] = []
    user_roles: list[dict[str, Any]] = []
    coordinators: list[dict[str, Any]] = []

    for index in range(village_count):
        village_id = _id(seed, "village", index)
        latitude = longitude = None
        if campus_latitude is not None and campus_longitude is not None:
            latitude = float(np.clip(campus_latitude + rng.normal(0, 0.18), -90, 90))
            longitude = float(np.clip(campus_longitude + rng.normal(0, 0.22), -180, 180))
        villages.append({
            "id": village_id,
            "name": f"Synthetic Village {index + 1:02d}",
            "district": f"Synthetic District {index + 1:02d}",
            "state": "Himachal Pradesh",
            "latitude": latitude,
            "longitude": longitude,
            "data_origin": DATA_ORIGIN,
            "created_at": _iso(start_dt),
        })

    def add_user(kind: str, index: int, role: str) -> str:
        user_id = _id(seed, kind, index)
        created_at = _iso(start_dt)
        users.append({
            "id": user_id,
            "auth_subject": f"synthetic:{user_id}",
            "email": f"{kind}-{index + 1:04d}@example.invalid",
            "phone": "",
            "display_name": f"Synthetic {kind.title()} {index + 1:04d}",
            "account_status": "active",
            "recipient_verified_at": created_at if role == "coordinator" else "",
            "data_origin": DATA_ORIGIN,
            "created_at": created_at,
            "updated_at": created_at,
        })
        user_roles.append({"user_id": user_id, "role_key": role, "granted_at": created_at})
        return user_id

    donor_ids = [add_user("donor", i, "donor") for i in range(donor_count)]
    coordinator_ids = [add_user("coordinator", i, "coordinator") for i in range(village_count)]
    volunteer_ids = [add_user("volunteer", i, "volunteer") for i in range(volunteer_count)]
    for index, village in enumerate(villages):
        coordinators.append({
            "village_id": village["id"],
            "user_id": coordinator_ids[index],
            "data_origin": DATA_ORIGIN,
            "assigned_at": _iso(start_dt),
        })

    items: list[dict[str, Any]] = []
    items_by_category: dict[str, list[dict[str, Any]]] = {category: [] for category in CATEGORIES}
    for index in range(item_count):
        created_at = _timestamp(rng, start_dt, as_of_dt)
        category = str(rng.choice(CATEGORIES, p=_seasonal_weights(created_at.month)))
        condition = int(np.clip(round(rng.normal(7.2, 1.8)), 1, 10))
        item = {
            "id": _id(seed, "item", index),
            "donor_id": donor_ids[int(rng.integers(0, len(donor_ids)))],
            "category": category,
            "quantity": int(rng.integers(1, 13)),
            "title": f"{category.title()} donation {index + 1:04d}",
            "description": f"Synthetic {category} listing for pipeline testing.",
            "age_group": str(rng.choice(AGE_GROUPS)),
            "condition_score": condition,
            "item_status": str(rng.choice(["approved", "submitted", "needs_review"], p=[0.86, 0.09, 0.05])),
            "data_origin": DATA_ORIGIN,
            "created_at": _iso(created_at),
            "updated_at": _iso(created_at),
        }
        items.append(item)
        if item["item_status"] == "approved":
            items_by_category[category].append(item)

    needs: list[dict[str, Any]] = []
    village_profiles = [int(rng.integers(0, len(CATEGORIES))) for _ in villages]
    for index in range(need_count):
        created_at = _timestamp(rng, start_dt, as_of_dt)
        village_index = int(rng.integers(0, village_count))
        category = str(rng.choice(CATEGORIES, p=_seasonal_weights(created_at.month, village_profiles[village_index])))
        urgency = int(rng.choice([1, 2, 3, 4, 5], p=[0.04, 0.10, 0.21, 0.31, 0.34]))
        deadline = (created_at.date() + timedelta(days=int(rng.integers(14, 91)))).isoformat()
        needs.append({
            "id": _id(seed, "need", index),
            "village_id": villages[village_index]["id"],
            "created_by": coordinator_ids[village_index],
            "category": category,
            "quantity": int(rng.integers(2, 31)),
            "age_group": str(rng.choice(AGE_GROUPS)),
            "urgency": urgency,
            "deadline": deadline,
            "notes": f"Synthetic {category} request; confirm details with coordinator.",
            "input_language": str(rng.choice(["hi", "en", "mixed"], p=[0.45, 0.35, 0.20])),
            "need_status": "open",
            "data_origin": DATA_ORIGIN,
            "created_at": _iso(created_at),
            "updated_at": _iso(created_at),
        })

    run_id = _id(seed, "recommendation-run", "baseline-v1")
    run = {
        "id": run_id,
        "model_stage": "baseline",
        "model_name": "synthetic-weighted-baseline",
        "model_version": "1.0.0",
        "data_origin": DATA_ORIGIN,
        "parameters": json.dumps({"seed": seed, "synthetic_only": True}, sort_keys=True),
        "candidate_count": 0,
        "created_at": _iso(as_of_dt),
    }
    matches: list[dict[str, Any]] = []
    feedback: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for item in items:
        events.append({
            "actor_id": item["donor_id"], "event_type": "item.uploaded", "entity_type": "item",
            "entity_id": item["id"], "data_origin": DATA_ORIGIN, "payload": "{}", "occurred_at": item["created_at"],
        })
    for need in needs:
        events.append({
            "actor_id": need["created_by"], "event_type": "need.created", "entity_type": "need",
            "entity_id": need["id"], "data_origin": DATA_ORIGIN, "payload": "{}", "occurred_at": need["created_at"],
        })

    village_by_id = {village["id"]: village for village in villages}
    for need in needs:
        pool = [item for item in items_by_category[need["category"]] if item["created_at"] <= need["created_at"]]
        if not pool:
            pool = items_by_category[need["category"]]
        if not pool:
            continue
        candidate_count = min(4, len(pool))
        candidate_indices = rng.choice(len(pool), size=candidate_count, replace=False)
        village = village_by_id[need["village_id"]]
        scored: list[tuple[float, dict[str, Any], dict[str, Any], datetime]] = []
        need_created = datetime.fromisoformat(need["created_at"].replace("Z", "+00:00"))
        suggested_at = min(need_created + timedelta(days=int(rng.integers(0, 4))), as_of_dt)
        waiting_days = max(0, (suggested_at.date() - need_created.date()).days)
        for candidate_index in candidate_indices:
            item = pool[int(candidate_index)]
            age_match = item["age_group"] == need["age_group"] or item["age_group"] in ("all_ages", "unspecified") or need["age_group"] in ("all_ages", "unspecified")
            ratio = min(item["quantity"], need["quantity"]) / max(item["quantity"], need["quantity"])
            distance_km = None
            distance_fit = None
            if village["latitude"] is not None:
                distance_km = _haversine_km(campus_latitude, campus_longitude, village["latitude"], village["longitude"])
                distance_fit = math.exp(-distance_km / 60)
            month = need_created.month
            seasonal = 1.0 if (need["category"] in WINTER_CATEGORIES and month in (11, 12, 1, 2)) or (need["category"] in SCHOOL_CATEGORIES and month in (5, 6, 7, 8)) else 0.45
            features = {
                "category_match": 1.0,
                "age_compatibility": 1.0 if age_match else 0.25,
                "condition_normalized": item["condition_score"] / 10,
                "quantity_ratio": ratio,
                "urgency_normalized": need["urgency"] / 5,
                "waiting_normalized": min(waiting_days / 14, 1),
                "distance_fit": distance_fit,
                "distance_km": round(distance_km, 2) if distance_km is not None else None,
                "seasonal_relevance": seasonal,
            }
            score = _weighted_score(features)
            scored.append((score, item, features, suggested_at))

        scored.sort(key=lambda row: (-row[0], row[1]["id"]))
        for rank, (score, item, features, suggestion_time) in enumerate(scored, start=1):
            linear = -1.5 + 4.1 * score + 0.16 * (need["urgency"] - 3) + 0.12 * (item["condition_score"] - 6)
            if features["distance_km"] is not None:
                linear -= 0.45 * (features["distance_km"] / 50)
            acceptance_probability = 1 / (1 + math.exp(-linear))
            accepted = bool(rng.random() < acceptance_probability)
            status = "rejected"
            rejection_reason = str(rng.choice(REJECTION_REASONS)) if not accepted else ""
            coordinator_id = need["created_by"]
            accepted_at = ""
            rejected_at = _iso(suggestion_time) if not accepted else ""
            updated_at = suggestion_time
            match_id = _id(seed, "match", f"{need['id']}:{item['id']}")
            match_events = [{"event_type": "match.suggested", "at": suggestion_time, "actor_id": None}]
            if accepted:
                updated_at = min(suggestion_time + timedelta(days=1), as_of_dt)
                accepted_at = _iso(updated_at)
                status = "accepted"
                match_events.append({"event_type": "match.accepted", "at": updated_at, "actor_id": coordinator_id})
                elapsed = (as_of_dt - updated_at).days
                stage = int(rng.choice([0, 1, 2, 3, 4], p=[0.12, 0.16, 0.18, 0.20, 0.34]))
                stage = min(stage, max(0, elapsed // 2))
                stage_statuses = ["accepted", "pickup_scheduled", "in_transit", "delivered", "confirmed"]
                stage_events = ["", "pickup.scheduled", "delivery.in_transit", "delivery.delivered", "delivery.confirmed"]
                status = stage_statuses[stage]
                for offset in range(1, stage + 1):
                    event_at = updated_at + timedelta(days=offset * 2)
                    updated_at = event_at
                    match_events.append({"event_type": stage_events[offset], "at": event_at, "actor_id": volunteer_ids[int(rng.integers(0, len(volunteer_ids)))] if offset < 4 else coordinator_id})
                if status in ("delivered", "confirmed"):
                    need["need_status"] = "fulfilled" if status == "confirmed" else "open"
            else:
                match_events.append({"event_type": "match.rejected", "at": suggestion_time, "actor_id": coordinator_id})
            final_actor = coordinator_id
            matches.append({
                "id": match_id,
                "recommendation_run_id": run_id,
                "item_id": item["id"],
                "need_id": need["id"],
                "score": round(score, 5),
                "rank_position": rank,
                "feature_snapshot": json.dumps(features, sort_keys=True),
                "reason": _reason(features, need),
                "match_status": status,
                "accepted_by": coordinator_id if accepted else "",
                "rejection_reason": rejection_reason,
                "accepted_at": accepted_at,
                "rejected_at": rejected_at,
                "data_origin": DATA_ORIGIN,
                "created_at": _iso(suggestion_time),
                "updated_at": _iso(updated_at),
            })
            label = "rejected" if not accepted else "fulfilled" if status == "confirmed" else "accepted"
            feedback.append({
                "match_id": match_id,
                "actor_id": final_actor,
                "label": label,
                "data_origin": DATA_ORIGIN,
                "reason_code": rejection_reason,
                "comment": "Synthetic feedback; not a real recipient statement.",
                "created_at": _iso(updated_at),
            })
            for event in match_events:
                events.append({
                    "actor_id": event["actor_id"] or "",
                    "event_type": event["event_type"],
                    "entity_type": "match",
                    "entity_id": match_id,
                    "data_origin": DATA_ORIGIN,
                    "payload": json.dumps({"synthetic": True}, sort_keys=True),
                    "occurred_at": _iso(event["at"]),
                })
    run["candidate_count"] = len(matches)

    frames = {
        "users": pd.DataFrame(users),
        "user_roles": pd.DataFrame(user_roles),
        "villages": pd.DataFrame(villages),
        "village_coordinators": pd.DataFrame(coordinators),
        "items": pd.DataFrame(items),
        "needs": pd.DataFrame(needs),
        "recommendation_runs": pd.DataFrame([run]),
        "matches": pd.DataFrame(matches),
        "feedback": pd.DataFrame(feedback),
        "events": pd.DataFrame(events),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for table, frame in frames.items():
        frame.to_csv(output / f"{table}.csv", index=False)
    metadata = {
        "data_origin": DATA_ORIGIN,
        "seed": seed,
        "as_of": as_of.isoformat(),
        "months": months,
        "campus_coordinates_provided": campus_latitude is not None,
        "row_counts": {table: len(frame) for table, frame in frames.items()},
        "warning": "All records are synthetic and must never be reported as real-world impact.",
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return frames


def _reason(features: dict[str, Any], need: dict[str, Any]) -> str:
    parts = ["same category"]
    if features["age_compatibility"] >= 1:
        parts.append("age group fits")
    if need["urgency"] >= 4:
        parts.append("urgent need")
    if features["distance_km"] is not None and features["distance_km"] <= 25:
        parts.append("close to campus")
    return "; ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 31))
    parser.add_argument("--villages", type=int, default=8)
    parser.add_argument("--donors", type=int, default=60)
    parser.add_argument("--volunteers", type=int, default=10)
    parser.add_argument("--items", type=int, default=1200)
    parser.add_argument("--needs", type=int, default=320)
    parser.add_argument("--campus-latitude", type=float)
    parser.add_argument("--campus-longitude", type=float)
    args = parser.parse_args()
    frames = generate_dataset(
        args.output,
        seed=args.seed,
        months=args.months,
        as_of=args.as_of,
        village_count=args.villages,
        donor_count=args.donors,
        volunteer_count=args.volunteers,
        item_count=args.items,
        need_count=args.needs,
        campus_latitude=args.campus_latitude,
        campus_longitude=args.campus_longitude,
    )
    print(f"Wrote {sum(len(frame) for frame in frames.values())} synthetic rows to {args.output}")


def _main_guard() -> None:
    main()


if __name__ == "__main__":
    _main_guard()
