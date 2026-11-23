# Data Collection and CSV Contract

Real pilot data will come from GiftBridge users and the college's coordinator survey/donation drive. Do not copy synthetic records into real pilot reporting. Generated files belong under `data/synthetic/`; collected or consented pilot exports belong in a separate access-controlled location and should be committed only after privacy review.

## Current synthetic pipeline

```powershell
python -m ml.data.generate_synthetic --output data/synthetic --seed 42
python -m ml.data.quality --input data/synthetic --expected-origin synthetic
```

Village names and districts in generated records are explicitly fictional. Coordinates are omitted unless both `--campus-latitude` and `--campus-longitude` are passed. If supplied, generated village points are random offsets around that point and remain synthetic, not surveyed locations. The fixed default `--as-of` date makes reruns reproducible; pass another ISO date to move the observation window.

## Files

The generator writes table-shaped CSVs: `users`, `user_roles`, `villages`, `village_coordinators`, `items`, `needs`, `recommendation_runs`, `matches`, `feedback`, and `events`, plus a `metadata.json` manifest. IDs are deterministic UUIDs for a fixed seed. The tabular schemas follow the initial database migration where practical; latitude/longitude are separate staging fields and need conversion to PostGIS `geography(Point,4326)` during import.

All rows that represent domain data have `data_origin=synthetic`. Synthetic account emails use the reserved `.invalid` domain and phone fields are blank. Do not use these accounts for authentication or contact them.

## Real collection

For the pilot, collect only fields needed to operate and evaluate matching. Use the same tables and controlled values in the data dictionary, set `data_origin=real`, obtain informed consent, and keep donor contact and pickup details out of analytics exports. Before accepting a real import, validate required columns, uniqueness, ranges, and foreign keys with the quality command. A production import path still needs authorized access controls, secure storage, and a retention schedule; the current script is a development fixture generator, not a consent or production-ingestion system.
