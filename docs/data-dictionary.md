# Data Dictionary (Phase 1)

PostgreSQL types and constraints are authoritative in [the initial migration](../db/migrations/001_initial_schema.sql). `id` columns are UUID primary keys unless noted. Timestamps are UTC `timestamptz`. `data_origin` is `synthetic` or `real`; analytics and training must preserve this provenance.

## Identity and geography

| Table | Columns and meaning |
|---|---|
| `users` | `id`; `auth_subject` external identity-provider subject; `email` college or verified account email; `phone` private contact; `display_name`; `account_status` pending/active/suspended/disabled; `recipient_verified_at`; `data_origin`; `created_at`, `updated_at`. No password is stored. |
| `roles` | `id`; unique `role_key` (`donor`, `coordinator`, `volunteer`, `admin`); display `name`. |
| `user_roles` | Composite key `user_id`, `role_id`; grants an account a role. |
| `villages` | `id`; `name`, `district`, `state`; `location` PostGIS geography point (WGS84); `data_origin`; `created_at`. Coordinates are used for distance and maps. |
| `village_coordinators` | `village_id`, `user_id`, `data_origin`; scoped coordinator assignment and `assigned_at`. |

## Supply, demand, matching

| Table | Columns and meaning |
|---|---|
| `items` | `id`; `donor_id`; `category`; positive `quantity` (defaults to 1); editable `title`, `description`; `age_group`; `condition_score` from 1-10; `item_status`; `data_origin`; `created_at`, `updated_at`. Donor contact details are deliberately not duplicated here. |
| `item_pickup_details` | `item_id`; private `address_text`, optional PostGIS `location`, optional `access_instructions`; `created_at`, `updated_at`. Restrict access to the donor, authorized admin, and volunteer assigned to the corresponding pickup. |
| `item_images` | `id`; `item_id`; private `storage_key`; `mime_type`; `size_bytes`; `sort_order` 1-4; optional `sha256`; `created_at`. The allowed sort range and per-item uniqueness cap each item at four images. |
| `needs` | `id`; `village_id`, `created_by`; `category`; positive `quantity`; `age_group`; `urgency` 1-5; optional `deadline`; original `notes` and `input_language`; `need_status`; `data_origin`; `created_at`, `updated_at`. Structured fields must be coordinator-confirmed before matching. |
| `recommendation_runs` | `id`; `model_stage` baseline/regression/ranker; `model_name`, `model_version`; `data_origin`; `parameters` JSONB; `candidate_count`; `created_at`. Identifies reproducible scoring runs. |
| `matches` | `id`; `recommendation_run_id`; `item_id`, `need_id`; `score` 0-1; `rank_position`; `feature_snapshot` JSONB; plain-language `reason`; `match_status`; `accepted_by`, `rejection_reason`; lifecycle timestamps; `data_origin`; `created_at`, `updated_at`. Unique per run/item/need. |

## Logistics, outcomes, and operations

| Table | Columns and meaning |
|---|---|
| `pickups` | `id`; claiming `volunteer_id`; `pickup_status`; optional `scheduled_at`, `completed_at`; `created_at`. A pickup can batch multiple items. Exact donor address is not included in this shared task record. |
| `pickup_items` | Composite key `pickup_id`, `item_id`; items included in a pickup. |
| `deliveries` | `id`; unique `match_id`; `pickup_id`; destination `village_id`; `delivery_status`; `delivered_at`, `confirmed_at`, optional `confirmed_by`; `created_at`. |
| `donations_history` | `id`; unique `delivery_id`; `item_id`, `need_id`, `village_id`; `confirmed_at`; `data_origin`. Insert only after recipient confirmation; source for fulfilled-impact counts. |
| `feedback` | `id`; `match_id`; `actor_id`; `label` accepted/rejected/fulfilled; `data_origin`; optional `reason_code` and `comment`; `created_at`. Rejection reasons become labeled training/evaluation data. |
| `notifications` | `id`; `user_id`; `channel` email/whatsapp/sms; `template_key`; `delivery_status`; provider reference; `created_at`, optional `sent_at`. Do not store message secrets or unnecessary personal content. |
| `events` | `id`; optional `actor_id`; `event_type`; `entity_type`, `entity_id`; `data_origin`; JSONB `payload`; `occurred_at`. Append-only domain event trail for funnels and timelines. |
| `audit_log` | `id`; optional `actor_id`; `action`; `entity_type`, `entity_id`; JSONB `details`; `occurred_at`. Restricted security/admin audit trail; never store credentials or full private contact payloads. |

## Controlled values

- Categories: `clothes`, `books`, `stationery`, `toys`, `utensils`, `blankets`, `electronics`, `other`.
- Age groups: `infant`, `child`, `teen`, `adult`, `all_ages`, `unspecified`.
- Item status: `draft`, `submitted`, `needs_review`, `approved`, `rejected`, `reserved`, `donated`, `archived`.
- Need status: `open`, `paused`, `fulfilled`, `expired`, `cancelled`.
- Match status: `suggested`, `accepted`, `rejected`, `pickup_scheduled`, `in_transit`, `delivered`, `confirmed`.
- Dataset origin: `synthetic`, `real`. Do not infer this from account email, dates, or other fields.

## Quality and privacy rules

- Required fields, numeric bounds, enum values, foreign keys, and uniqueness are database checked. Duplicate detection for similar text/images is a later pipeline concern.
- `item_images.size_bytes` is limited to 10 MiB per image in this initial schema; HTTP and image-decoding limits must also be enforced before object storage.
- The database limits each item to four image rows through a unique per-item `sort_order` constrained to 1-4; the upload service should still provide a clear validation error before inserting a fifth image.
- Pickup details are sensitive personal data. Encrypt them at rest, return them only through an authorized assigned-pickup workflow, and delete or redact them under the retention policy.
- Composite foreign keys ensure a match and its recommendation run, item, and need all share the same `data_origin`.
- Use lowercased email normalization before insert and a unique case-insensitive index. Do not return `users.email` or `users.phone` outside authorized account/admin workflows.
- Event payloads and feedback comments may contain personal data if unconstrained. Validate, minimize, redact, and define retention before production use.
- Synthetic rows must be generated with `data_origin='synthetic'`; pilot imports and user actions use `real`. Exclude or separately report synthetic records when publishing impact metrics.
