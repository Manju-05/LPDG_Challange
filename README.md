# LPDG Innovation Hub — Selection Challenge 2026 (Part 1 & Part 2: Track B — Software Development)

An automated, economically-driven field visit prioritization system and REST web service for LPDG's smart utility radio network (~320 gateways).

---

## 1. Project Overview & Operational Context

LPDG operates a utility radio network consisting of approximately **320 gateways** installed across rooftops, basements, and plant rooms. Each gateway relays telemetry and periodic meter readings for 40 to 900 connected utility meters.

When a gateway degrades or fails, the meters behind it stop transmitting readings. These failures are typically silent and difficult to diagnose immediately, leading to unread meters, inaccurate billing cycles, and manual read dispatch costs.

### The Operational Challenge
- **Field Capacity Constraint**: Hard limit of **15 field visits per week** (120 total visits across the 8-week evaluation window).
- **Objective**: Identify and rank the 15 gateways most urgently requiring a technician visit for each of the 8 scored weeks from **2 February 2026 to 23 March 2026**.

### Economic Cost Model
- **Dispatched Visit**: **€380** fixed cost per technician visit.
- **False Alarm** (Visit sent, but nothing wrong): **€380 wasted**.
- **Unattended Faulty Gateway**: **€600 per week** recurring penalty for every week a broken gateway remains unattended.
- **Episode Economics**: The first visit to an ongoing fault episode halts the recurring €600/week penalty. Re-visiting the same gateway in subsequent consecutive weeks during the same continuous problem yields **€0 incremental savings** and wastes a €380 visit slot. Early detection is strictly more valuable than late detection.

---

## 2. Repository Structure

```text
├── .gitignore                      # Protects raw data, prompt notes, and caches
├── AI-USAGE.md                     # Statement of AI tool usage, review process, & fixes
├── DECISIONS.md                    # 6 architectural decisions, limitations, & roadmap
├── README.md                       # Main documentation & run instructions
├── baseline_3sigma.py              # Provided 3-sigma anomaly baseline script
├── predictions.csv                 # Generated submission (120 rows, 8 scored weeks)
├── run.py                          # Dual-mode entry point (CLI pipeline & REST API server)
├── validate_submission.py          # Official submission validator
├── pytest.ini                      # Pytest runner configuration
├── requirements.txt                # Python dependencies (pandas, pyarrow, fastapi, uvicorn, pytest)
├── Makefile                        # Make targets for run, test, serve, validate
├── run.sh                          # Shell execution script
├── Dockerfile                      # Production container definition
├── docker-compose.yml              # One-command container runner
├── src/
│   ├── __init__.py                 # Package initialization
│   ├── api.py                      # FastAPI REST service & lifecycle coordinator (Track B)
│   ├── config.py                   # System constants, scored weeks, cost parameters
│   ├── data_loader.py              # Robust loaders for Parquet, CSVs, and Excel
│   ├── features.py                 # Multi-signal extraction with strict cutoff & staleness decay
│   ├── pipeline.py                 # End-to-end prioritization coordinator
│   ├── ranker.py                   # Polymorphic rankers, episode cooldown, & deterministic sort
│   ├── reason_generator.py         # Operations-centric reason builder (<= 300 chars)
│   └── schemas.py                  # Pydantic v2 request & response schemas
└── tests/
    ├── test_api.py                 # FastAPI REST API integration tests (18 tests)
    ├── test_components.py          # Unit tests for normalization, cooldown, & formatting (3 tests)
    ├── test_ranker_interface.py    # Interface conformance & ranker swapping tests (3 tests)
    ├── test_reproducibility.py     # Idempotency & determinism tests across runs (1 test)
    ├── test_schema_and_validation.py # Synthetic fixture & output schema validation tests (2 tests)
    └── test_temporal_cutoff.py     # Strict temporal cutoff & leakage prevention tests (2 tests)
```

---

## 3. Quickstart & Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)
- Core dependencies: `pandas`, `numpy`, `pyarrow`, `fastapi`, `uvicorn`, `pydantic`, `pytest`

### Step 1: Clone Repository & Mount Data
Place the unzipped challenge `data/` directory at the repository root:
```text
data/
├── engineer_review_2026-02.xlsx
├── field_visits.csv
├── gateway_master.csv
├── meter_read_success.csv
├── telemetry/
│   ├── month=2025-08/*.parquet
│   └── ...
└── telemetry_sample_2025-08.csv
```

### Step 2: Run Prioritization Pipeline (Part 1)
Generate the canonical 120-row prediction file using any supported execution method:

**Option A — Python CLI**:
```bash
python run.py --data data --out predictions.csv
```

**Option B — Make**:
```bash
make run
```

**Option C — Shell Script (Linux / macOS / Git Bash)**:
```bash
./run.sh
```

**Option D — Docker Compose**:
```bash
docker compose up
```

### Step 3: Start the REST Web API (Part 2 — Track B: Software Development)
Launch the interactive FastAPI service:
```bash
python run.py --serve --host 127.0.0.1 --port 8000
# or: make serve
```

Interactive Swagger Documentation is automatically available at:
👉 **`http://127.0.0.1:8000/docs`** (or Alternative ReDoc at `http://127.0.0.1:8000/redoc`)

#### REST API Endpoints Overview:
| Method & Route | Description | Key Parameters |
| :--- | :--- | :--- |
| `GET /health` | Service liveness probe & system metadata | None |
| `GET /fleet/summary` | High-level fleet health (3$\sigma$ spikes, silence, fail rate) | `?week=YYYY-MM-DD` |
| `GET /rankings` | Top 15 prioritized gateways for field dispatch | `?week=YYYY-MM-DD`, `?week=latest`, `?ranker=composite\|baseline` |
| `GET /gateways/{id}` | Detailed operational diagnostics for a gateway | `?week=YYYY-MM-DD`, `?ranker=composite\|baseline` |
| `GET /gateways/{id}/history` | Multi-week chronological trend across all 8 weeks | `?ranker=composite\|baseline` |
| `POST /run` | Re-executes pipeline over mounted data without restart | `?ranker=composite\|baseline`, `?out=predictions.csv` |

#### Example API Requests:
```bash
# 1. Inspect fleet-wide operational health
curl "http://127.0.0.1:8000/fleet/summary?week=2026-02-02"

# 2. Query top 15 ranked gateways for a specific week
curl "http://127.0.0.1:8000/rankings?week=2026-02-02"

# 3. Query the latest dynamically discovered evaluation week
curl "http://127.0.0.1:8000/rankings?week=latest"

# 4. Inspect specific gateway diagnostics (supports bare or colon MAC format)
curl "http://127.0.0.1:8000/gateways/0A2778A31BE3?week=2026-02-02"

# 5. Query 8-week historical diagnostic trajectory for a gateway
curl "http://127.0.0.1:8000/gateways/0A2778A31BE3/history"

# 6. Re-run pipeline dynamically over disk without service restart
curl -X POST "http://127.0.0.1:8000/run"
```

### Step 4: Validate the Submission
Verify output compliance against the official schema validator:
```bash
python validate_submission.py predictions.csv
# or: make validate
```
**Expected Output**:
```text
predictions.csv: OK
  15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
```

---

## 4. Automated Test Suite

Run the full automated test suite (29 tests passing):
```bash
pytest -v
# or: make test
```

### Test Coverage Highlights:
- **Core Pipeline & Integrity (11 tests)**:
  - [`tests/test_temporal_cutoff.py`](tests/test_temporal_cutoff.py): Strict Monday 00:00 UTC cutoff and future row exclusion.
  - [`tests/test_schema_and_validation.py`](tests/test_schema_and_validation.py): Synthetic fixture ranking and `validate_submission.py` compliance.
  - [`tests/test_reproducibility.py`](tests/test_reproducibility.py): Bit-for-bit deterministic reproducibility across repeated runs.
  - [`tests/test_components.py`](tests/test_components.py): ID normalization, reason formatting ($\le 300$ chars), and episode cooldown decay.
  - [`tests/test_ranker_interface.py`](tests/test_ranker_interface.py): Polymorphic ranker interface conformance and runtime swapping.
- **REST Web API Integration (18 tests)**:
  - [`tests/test_api.py`](tests/test_api.py): `/health`, `/fleet/summary`, `/rankings`, dynamic `latest` partition discovery, operator-centric date validation, out-of-bounds telemetry protection, case/colon ID normalization, 8-week history trends, concurrent run locking (`409 Conflict`), dynamic disk reload without restart, and default canonical `POST /run` generation.

---

## 5. Technical Design & Ranking Methodology

### Why This Architecture?
Standard 3-sigma anomaly counts fail when a gateway suffers total power loss (producing zero records and zero spikes) or when visits are redundantly sent to already-attended broken gateways. Our multi-signal architecture solves this.

### Strict Temporal Boundary Enforcement
For any target Monday $T$ (`2026-02-02` through `2026-03-23`):
- **Telemetry**: Evaluates a 28-day baseline window $[T - 28\text{d}, T)$ and recent 7-day observation window $[T - 7\text{d}, T)$. Any data timestamped $ts \ge T$ is strictly excluded.
- **Meter Reads**: Slices `meter_read_success.csv` strictly on $\text{week\_date} < T$.
- **Field Visits**: Slices `field_visits.csv` on $\text{visited\_on} < T$.
- **Engineer Review**: Strictly restricted to $T \ge \text{2026-02-16}$.

### In-Service Candidate Fleet Filtering (Hardware Lifecycle Boundaries)
Before feature extraction and scoring, candidate gateways are filtered from `gateway_master.csv` (332 total entries) down to active in-service units:
$$\text{installed\_on} \le T \quad \text{AND} \quad (\text{decommissioned\_on} \ge T \;\lor\; \text{decommissioned\_on is NULL})$$
- **Why this matters**: In `gateway_master.csv`, 33 gateways have `installed_on > 2026-02-02` (commissioned later in spring/summer 2026) and 12 decommissioned units. Without active in-service filtering, uninstalled warehouse gateways exhibit 0 telemetry hours, falsely triggering 168h silence penalties. Filtering reduces the candidate pool to operational hardware (~290 gateways depending on the week), ensuring complete telemetry silence accurately reflects live power or backhaul loss rather than uninstalled warehouse hardware.

### Multi-Source Signal Formulation
The ranking engine synthesizes orthogonal evidence streams into an operational risk score:
1. **3-Sigma Telemetry Anomalies**: Hourly spikes exceeding $\mu + 3\sigma$ in `offline_duration_sec`, `disconnection_cnt`, or `reboot_cnt`.
2. **Telemetry Silence & Missing Hours**: Tracks unobserved hours ($\text{silent\_hours} = 168 - \text{reported\_hours}$) for active commissioned gateways.
3. **Meter Reading Failure Rate**: $\Delta = 1 - \frac{\text{meters\_read}}{\max(1, \text{meters\_expected})}$ from the most recent prior week.
4. **Meter Staleness Decay**: Applies exponential discount $\text{decay} = 0.8^{\text{weeks\_lag}}$ to reflect diminishing relevance as meter snapshots age.
5. **Engineer Ground Review**: High-risk flag for gateways reviewed as `Schlecht` (for weeks on or after 2026-02-16).

$$\text{Raw Score} = \text{flagged\_hours}_{3\sigma} + 0.5 \cdot \min(\text{offline\_hrs}, 48) + 10.0 \cdot \text{meter\_fail\_rate} \cdot 0.8^{\text{weeks\_lag}} + 0.05 \cdot \text{silent\_hrs} + 2.0 \cdot \text{expert\_schlecht}$$

### Multi-Week Episode Cooldown Optimization
To maximize value within the 15-visit quota and prevent repeat-visit waste during continuous fault episodes (Round-2 FAQ 4.1):
$$\text{Final Score} = \text{Raw Score} \times \begin{cases} 0.10 & \text{if visited in week } w-1 \\ 0.25 & \text{if visited in week } w-2 \\ 0.50 & \text{if visited in week } w-3 \\ 1.00 & \text{otherwise} \end{cases}$$
This schedule achieves **85 unique gateway visits** across 120 slots without repeat-visit burn.

### Deterministic Tie-Breaking
Rows are sorted deterministically by:
1. `score` **Descending**
2. `gateway_id` **Ascending**

---

## 6. Sample Output (`predictions.csv`)

The generated submission contains exactly 120 rows (15 gateways $\times$ 8 weeks). Example rows:

| week_start | rank | gateway_id | score | reason |
| :--- | :---: | :---: | :---: | :--- |
| `2026-02-02` | 1 | `0A2778A31BE3` | 73.46 | 43h >3-sigma breach on disconnection_cnt; 141.2h total offline; 39 disconnects; 25h telemetry silence; meter fail rate 52.1% |
| `2026-02-02` | 2 | `06F49BD8F572` | 62.48 | 26h >3-sigma breach on disconnection_cnt; 283.6h total offline; 45 reboots; 272 disconnects; 106h telemetry silence; meter fail rate 71.8% |
| `2026-02-16` | 1 | `0AA296FF247D` | 66.33 | 32h >3-sigma breach on offline_duration_sec; 562.0h total offline; 17 reboots; 307 disconnects; 89h telemetry silence; meter fail rate 38.8%; engineer review flagged Schlecht |

---

## 7. Deliverables & Documentation Index

- **[`predictions.csv`](predictions.csv)**: Validated submission file (120 rows, 8 scored weeks).
- **[`DECISIONS.md`](DECISIONS.md)**: 6 core architectural decisions, trade-offs, risks, Part 2 Track Selection (Track B — Software Development), and limitations.
- **[`AI-USAGE.md`](AI-USAGE.md)**: Transparent declaration of AI tooling, manual review procedures, and concrete AI errors caught and resolved.
- **[`run.py`](run.py)** & **[`src/`](src/)**: Prioritization pipeline and FastAPI REST service.
- **[`tests/`](tests/)**: Automated 29-test verification suite.

---

## 8. Video Walkthrough & Presentation Outline

> **Note**: A 6–8 minute walkthrough video will be recorded and linked here prior to final submission.
> **Video Link**: `[Insert Walkthrough Link: YouTube / Loom / Drive]`

### Walkthrough Script / Slide Outline:
1. **Problem & Economic Context (1 min)**: Fleet scale (~320 gateways), 15 visits/week limit, €380 visit cost vs €600 recurring unattended fault penalty.
2. **Architecture & Cutoff Enforcement (2 mins)**: Walk through `src/` modules, showing strict Monday 00:00 UTC boundaries and date-checked engineer review integration.
3. **One-Command Execution (1 min)**: Execute `python run.py --data data --out predictions.csv` in terminal.
4. **Validation & Test Execution (1.5 mins)**: Run `python validate_submission.py predictions.csv` and `pytest -v`.
5. **REST API & Part 2 Focus (1.5 mins)**: Run `python run.py --serve`, showcase Swagger UI at `/docs`, demo `/fleet/summary`, `/gateways/{id}/history`, `/rankings?week=latest`, and `POST /run`.
6. **Decisions & Limitations (1 min)**: Review multi-week episode cooldown strategy, meter staleness decay, and limitations/roadmap in `DECISIONS.md`.
