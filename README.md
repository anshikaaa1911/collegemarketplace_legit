# CMP

CMP is a college donation-matching platform for connecting donated goods with verified village, school, anganwadi, and NGO needs in Himachal Pradesh. The project is being built in phases so the data-science lifecycle remains reproducible and visible, not hidden behind the application.

## Phase status

- Phase 1: architecture, initial PostgreSQL/PostGIS schema, and data dictionary.
- Phase 2: deterministic synthetic data, provenance-aware quality checks, coordinator intake prototype, and initial quality/EDA notebooks.
- Remaining: inferential analysis, segmentation, forecasting, trained match models, production API/PWA, dashboards, deployment, and pilot operations.

## Phase 1 decisions

- PostgreSQL with PostGIS is the system of record. Images live in private object storage; only storage keys and metadata are stored in PostgreSQL.
- Synthetic and real records carry an explicit `data_origin`; production analyses and model training must filter or report by origin.
- Donor contact details are private account data. Public and recipient-facing API responses must not serialize donor phone, email, or address.
- Matching recommendations are versioned runs with feature snapshots. Feedback and lifecycle events are retained for evaluation and future training.
- The first model is a deterministic rules baseline. Regression and ranking are later phases and must be compared with time/group-aware validation.

## Current artifacts

- [Architecture and system boundaries](docs/architecture.md)
- [Schema data dictionary](docs/data-dictionary.md)
- [Initial database migration](db/migrations/001_initial_schema.sql)
- [Data collection and CSV contract](data/README.md)
- [Data collection prototype notebook](notebooks/00_data_collection_app.ipynb)
- [Data quality notebook](notebooks/01_data_quality.ipynb)
- [EDA notebook](notebooks/02_eda.ipynb)

## Run the Data Pipeline

Install the Python dependencies with `python -m pip install -r requirements.txt`, then generate and validate a reproducible synthetic fixture:

```powershell
python -m ml.data.generate_synthetic --output data/synthetic --seed 42
python -m ml.data.quality --input data/synthetic --expected-origin synthetic
```

The generated village labels are fictional. Coordinates are omitted unless explicitly supplied with both campus coordinate arguments. Real pilot intake entered through the notebook is saved under `data/collected/`, which is excluded from Git; review and protect those files before sharing or exporting.

## Database prerequisite

The initial migration targets PostgreSQL 15+ with PostGIS installed and available to the database role. Apply it once to a new database using your normal migration runner or `psql`; it is not an application yet. API, Docker Compose, and runnable data pipelines are intentionally deferred to their planned phases.

## Assumptions and limitations

Phase 1 assumes one college tenant, multiple villages and recipient organizations, and one item matched to one need per recommendation record. The SQL schema establishes core entities and constraints; role enforcement, state-transition rules, four-image limits, private-field response filtering, rate limits, and audit immutability also require application permissions and tests. No real coordinator or donor data is included.
