# Comprehensive Project Execution Guide & Technical Reference

**LPDG Innovation Hub Selection Challenge 2026**
Part 1: Deterministic Prioritization Pipeline · Part 2: Track B — Software Development REST Web Service

This guide provides a complete, step-by-step walkthrough for running, testing, demonstrating, and evaluating the codebase.

---

## 1. Project Context & Economic Foundation

| Parameter | Operational Value | Economic Rationale |
| :--- | :--- | :--- |
| Fleet Scale | ~320 Utility Radio Gateways | Deployed in rooftops, basements, and plant rooms across Germany. |
| Meters per Gateway | 40 to 900 meters | Gateway failures cause silent unread meter cascades and billing delays. |
| Field Visit Constraint | 15 visits / week | Hard operational capacity constraint (120 total visits across 8 weeks). |
| Evaluation Period | 8 Scored Weeks | Mondays from `2026-02-02` through `2026-03-23`. |
| Technician Visit Cost | €380 fixed | Cost incurred for each dispatched field investigation. |
| Unattended Fault Penalty | €600 / week | Recurring penalty for every week a faulty gateway remains unvisited. |
| Episode Economics | First visit halts penalty | Subsequent visits to the same ongoing continuous fault yield €0 incremental savings and waste a €380 slot. |

---

## 2. Step-by-Step Command Execution Guide

### Step 1 — Environment Setup & Dependencies

```bash
pip install -r requirements.txt
```

- **What it does:** Installs core data science and web service libraries: `pandas`, `pyarrow`, `fastapi`, `uvicorn`, `pydantic`, and `pytest`.
- **Why it is run:** Ensures all data parsing, REST endpoint schemas, and automated test runners execute identically across operating systems.
- **Expected output:** `Successfully installed ...`

---

### Step 2 — Run the Prioritization Pipeline (Part 1)

```bash
python run.py --data data --out predictions.csv
```

- **What it does:** Loads all raw datasets from `data/`, enforces the strict Monday 00:00 UTC temporal cutoff, filters in-service gateways, calculates multi-source risk scores, applies multi-week episode cooldowns, and writes the canonical 120-row output to `predictions.csv`.
- **Why it is run:** Generates the official deliverable required by the challenge.

**Alternative run commands:**
```bash
make run
./run.sh                # Linux / macOS / Git Bash
docker compose up       # Isolated container
```

**Expected output:**
```text
Loading datasets from data using ranker 'composite_multi_source'...
Telemetry loaded: 1433387 rows across 320 gateways.
Successfully generated predictions.csv with 120 rows.
```

---

### Step 3 — Validate the Submission Output

```bash
python validate_submission.py predictions.csv
```

- **What it does:** Runs the official challenge validator script to check schema conformity, column names, row counts, week date sequences, rank bounds (1–15), gateway ID formats, and character length limits on reason text (≤ 300 chars).
- **Why it is run:** Guarantees that the submission will be accepted by the automated grading engine with exit code 0.
- **Alternative command:** `make validate`

**Expected output:**
```text
predictions.csv: OK
  15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
```

---

### Step 4 — Execute the Automated Test Suite

```bash
pytest -v
```

- **What it does:** Discovers and executes all 29 unit and integration tests across 6 test modules.
- **Why it is run:** Proves temporal leak prevention, schema integrity, algorithmic determinism, ID normalization, and REST API functionality.
- **Alternative command:** `make test`

**Test breakdown (29 tests total):**

| Test file | Tests | Coverage |
| :--- | :---: | :--- |
| `tests/test_temporal_cutoff.py` | 2 | Asserts strictly zero data leakage past Monday 00:00 UTC and validates withholding of the mid-February engineer review sheet. |
| `tests/test_schema_and_validation.py` | 2 | Tests synthetic fixtures and official validator compliance. |
| `tests/test_reproducibility.py` | 1 | Verifies bit-for-bit deterministic reproducibility across back-to-back runs. |
| `tests/test_components.py` | 3 | Tests ID normalizer, reason length limits, and multi-week cooldown decay. |
| `tests/test_ranker_interface.py` | 3 | Validates polymorphic `BaseRanker` interface and dynamic ranker swapping. |
| `tests/test_api.py` | 18 | Comprehensive REST API suite: liveness probes, fleet health summaries, rankings queries, dynamic `latest` partition discovery, date validation, single-gateway diagnostics, 8-week history trends, concurrent run locking (409 Conflict), dynamic disk reload without restart, and default canonical `POST /run` generation. |

**Expected output:**
```text
============================= 29 passed in ...s =============================
```

---

### Step 5 — Start the FastAPI REST Web Service (Part 2 — Track B)

```bash
python run.py --serve --host 127.0.0.1 --port 8000
```

- **What it does:** Launches the production Uvicorn ASGI server hosting the FastAPI prioritization service.
- **Why it is run:** Fulfills Part 2 (Track B: Software Development), providing real-time HTTP endpoints for operations managers and field dispatchers.
- **Alternative command:** `make serve`

**Interactive documentation:**
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 3. REST API Endpoints Reference (Part 2)

| Method & Path | Query / Path Parameters | Purpose & Rationale | Example Request |
| :--- | :--- | :--- | :--- |
| `GET /health` | None | Liveness and health probe reporting active data directory, available weeks, and registered ranker algorithms. | `curl http://127.0.0.1:8000/health` |
| `GET /fleet/summary` | `?week=YYYY-MM-DD` | Macro operational health overview across the entire fleet for a given week (active gateways, 3σ breach count, silent units count, and average meter fail rate). | `curl "http://127.0.0.1:8000/fleet/summary?week=2026-02-02"` |
| `GET /rankings` | `?week=YYYY-MM-DD`, `?week=latest`, `?ranker=composite\|baseline` | Returns top 15 prioritized gateways for field dispatch with scores and operations reasons. Dynamically scans disk if `?week=latest` is supplied. | `curl "http://127.0.0.1:8000/rankings?week=2026-02-02"` <br> `curl "http://127.0.0.1:8000/rankings?week=latest"` |
| `GET /gateways/{id}` | `gateway_id` in path, `?week=YYYY-MM-DD`, `?ranker=composite\|baseline` | Diagnostic details for a single gateway. Normalizes both bare MAC (`0A2778A31BE3`) and colon MAC (`0a:27:78:a3:1b:e3`). Returns 404 if not found. | `curl "http://127.0.0.1:8000/gateways/0A2778A31BE3?week=2026-02-02"` |
| `GET /gateways/{id}/history` | `gateway_id` in path, `?ranker=composite\|baseline` | Chronological 8-week trend for a gateway showing weekly ranks, scores, offline hours, and whether a technician visit was recommended. | `curl "http://127.0.0.1:8000/gateways/0A2778A31BE3/history"` |
| `POST /run` | `?ranker=composite\|baseline`, `?out=predictions.csv` | Re-executes the prioritization pipeline dynamically over mounted disk data without server restart. Features a non-blocking mutex lock (409 Conflict on concurrent runs). | `curl -X POST "http://127.0.0.1:8000/run"` |

---

## 4. Key Engineering Decisions & Architectural Highlights

### 1. Strict Monday 00:00 UTC Temporal Cutoff
- **Implementation:** In `src/features.py`, all telemetry is strictly filtered to `[T - 28d, T)`, meter reads to `week_date < T`, field visits to `visited_on < T`, and engineer review to `T ≥ 2026-02-16`.
- **Why:** Eliminates future-to-past data leakage and protects the validity of out-of-sample evaluation.

### 2. In-Service Hardware Lifecycle Filtering
- **Implementation:** Filters `gateway_master.csv` (332 entries) to active commissioned hardware: `installed_on ≤ T AND (decommissioned_on ≥ T OR NULL)`.
- **Why:** 33 gateways in the master table have installation dates later in spring/summer 2026. Without filtering, uninstalled warehouse gateways have 0 telemetry hours and would falsely trigger maximum 168h silence penalties.

### 3. Multi-Week Episode Cooldown (0.10× → 0.25× → 0.50× → 1.00×)
- **Implementation:** In `src/ranker.py`, visited gateways receive a progressive decay based on weeks since last visit.
- **Why:** Under Round-2 FAQ §4.1, repeat visits to an ongoing fault yield €0 incremental benefit. This progressive schedule achieves 85 unique gateway visits across 120 slots.

### 4. Exponential Meter Read Staleness Decay (0.8^weeks_lag)
- **Implementation:** Multiplies meter read failure rate by `0.8^weeks_lag`.
- **Why:** `meter_read_success.csv` ends on `2026-01-26`. By week 8 (`2026-03-23`), the report is 8 weeks old. The decay ensures the system prioritizes fresh March telemetry over aging historical meter reports.

### 5. Robust Error Handling & Dynamic Disk Freshness (Track B)
- **Implementation:** Layered HTTP error codes (400 Bad Request with nearest-Monday suggestions, 404 Gateway Not Found, 409 Conflict mutex lock, 422 Unprocessable Entity for missing directories).
- **Why:** Avoids module-level static caching; any new Parquet files dropped into `data/telemetry/` are immediately picked up by `/rankings?week=latest` and `POST /run` without container restart.

---

## 5. Quick Verification & Demonstration Script (6–8 Min Video)

| Time | Topic | Action / Screen Display |
| :--- | :--- | :--- |
| 0:00 – 1:00 | Problem & Economics | Explain the €380 visit cost vs €600/week penalty and 15 visits/week constraint. |
| 1:00 – 2:30 | Architecture & Cutoffs | Highlight `src/features.py`, strict Monday 00:00 UTC cutoff, in-service filtering, and multi-week cooldown. |
| 2:30 – 3:30 | Pipeline Execution | Run `python run.py --data data --out predictions.csv` and `python validate_submission.py predictions.csv`. |
| 3:30 – 4:30 | Automated Tests | Run `pytest -v` to show all 29 automated unit and integration tests passing. |
| 4:30 – 6:00 | REST API Live Demo | Launch `python run.py --serve`, open `http://127.0.0.1:8000/docs`, execute `GET /fleet/summary`, `GET /rankings?week=latest`, `GET /gateways/{id}/history`, and `POST /run`. |
| 6:00 – 7:00 | Decisions & Roadmap | Review trade-offs in `DECISIONS.md`, limitations (carrier outages), and 2-week roadmap (geographic routing). |
