# LPDG Challenge 2026 — Master Project Explanation & Interview Defense Guide

**Candidate Registration ID**: `24095A3305`  
**Track Selected**: **Part 2 — Track B: Software Development**  
**Repository**: [Manju-05/LPDG_Challange](https://github.com/Manju-05/LPDG_Challange)

---

## Table of Contents
1. [What is the Problem Statement?](#1-what-is-the-problem-statement)
2. [What are the Core Operational & Technical Challenges?](#2-what-are-the-core-operational--technical-challenges)
3. [Part 1: The Deterministic Prioritization Pipeline](#3-part-1-the-deterministic-prioritization-pipeline)
   - What is Part 1?
   - How is Part 1 Solved? (Mathematical Formulation & Algorithm)
   - What is Solved in Part 1?
   - How to Run & Validate Part 1
4. [Part 2: Track B — Software Development REST Web Service](#4-part-2-track-b--software-development-rest-web-service)
   - What is Part 2 and How Does it Solve the Problem?
   - Key Features & Architectural Highlights
   - Step-by-Step Guide to Running & Testing the API
5. [Deep-Dive into AI-USAGE.md & DECISIONS.md](#5-deep-dive-into-ai-usagemd--decisionsmd)
   - Why `AI-USAGE.md` Exists & Real AI Mistakes Caught
   - The 6 Core Architectural Decisions in `DECISIONS.md`
   - Known Limitations & 2-Week Engineering Roadmap
6. [Docker & Containerization: How to Run & Why It Is Useful](#6-docker--containerization-how-to-run--why-it-is-useful)
7. [Live Interview & Defense Scenarios (The 3 Critical Questions)](#7-live-interview--defense-scenarios-the-3-critical-questions)
   - Scenario 1: Running on Unseen Month of Data Live
   - Scenario 2: Making One Live Code Change in the Room
   - Scenario 3: What Another Week Would Buy You

---

## 1. What is the Problem Statement?

### The Context
LPDG operates a smart utility radio network across Germany consisting of approximately **320 radio gateways**. Each gateway is mounted in rooftops, basements, and plant rooms, serving as a communications bridge that collects and relays telemetry and periodic meter readings from **40 to 900 connected utility meters** (water, gas, electricity, heat).

### The Problem
When a gateway degrades or fails (due to power loss, firmware crashes, radio interference, or backhaul disconnection), all meters connected behind it stop transmitting readings. 
- These failures are often **silent** (the gateway stops communicating entirely, leaving no error logs).
- Left unattended, unread meters cause inaccurate billing cycles, customer complaints, and expensive emergency manual meter-reading dispatches.

### The Objective
Given historical telemetry, meter success rates, past field visits, and engineer reviews:
> **Identify and rank exactly 15 gateways most urgently requiring a technician field visit for each of the 8 evaluation weeks from 2 February 2026 to 23 March 2026 (120 total visits).**

---

## 2. What are the Core Operational & Technical Challenges?

| Challenge | Real-World Operational Reality | Technical Dilemma |
| :--- | :--- | :--- |
| **1. Strict Quota Constraint** | Hard capacity cap of **15 visits per week** (120 total across 8 weeks). | You cannot visit every suspicious gateway; precision ranking is mandatory. |
| **2. Asymmetric Economic Penalty** | - Dispatched Visit: **€380 fixed**.<br>- False Alarm: **€380 wasted**.<br>- Unattended Broken Gateway: **€600/week penalty** recurring until visited. | Missing a faulty gateway is 1.58× more expensive than a false visit (€600 vs €380). |
| **3. Episode Economics (Repeat Visit Burn)** | The **first visit** to an ongoing fault halts the €600/week penalty. Re-visiting the same broken gateway in consecutive weeks yields **€0 incremental savings** and burns €380. | Stateless 3-sigma anomaly counters keep re-flagging the same broken gateway every week. Multi-week cooldown is essential. |
| **4. Silent Power Outages** | When power cuts completely, telemetry generation drops to zero. | A 3-sigma spike counter looks for anomalous high numbers, so a totally dead gateway with 0 telemetry hours generates **zero spikes** and gets ignored! |
| **5. Warehouse vs Field Gateways** | `gateway_master.csv` contains 332 entries, including 33 future-commissioned units and 12 decommissioned units. | Uninstalled warehouse hardware generates 0 telemetry hours; without active in-service filtering, warehouse hardware falsely triggers maximum silence alarms. |
| **6. Meter Read Staleness Drift** | `meter_read_success.csv` ends on `2026-01-26`. | In February it is fresh, but by late March it is 8 weeks old. The system must decay old meter signals to avoid prioritizing stale data over fresh March telemetry. |
| **7. Strict Temporal Leakage Protection** | Out-of-sample evaluation requires that decisions for Monday $T$ use only data collected before Monday 00:00 UTC. | Zero future data leakage is permissible (including mid-February engineer sheets before Feb 16). |

---

## 3. Part 1: The Deterministic Prioritization Pipeline

### What is Part 1?
Part 1 is the core algorithmic pipeline that ingests raw telemetry (Parquet), meter reading records (CSV), field dispatch history (CSV), gateway metadata (CSV), and engineer reviews (Excel), and generates a deterministic, fully validated `predictions.csv` containing exactly 15 ranked gateways for each of the 8 scored weeks (120 rows total).

### How is Part 1 Solved? (Algorithmic & Mathematical Formulation)

Our solution replaces naive single-metric counters with a **multi-signal operational risk engine**:

#### Step 1: In-Service Hardware Lifecycle Filtering
Candidate gateways are filtered strictly to active operational units at target Monday $T$:
$$\text{installed\_on} \le T \quad \text{AND} \quad (\text{decommissioned\_on} \ge T \;\lor\; \text{decommissioned\_on is NULL})$$

#### Step 2: Multi-Source Signal Synthesis
For each candidate gateway over the observation window $[T-7\text{d}, T)$:
1. **3-Sigma Telemetry Spikes** ($\text{flagged\_hours}_{3\sigma}$): Hours where `offline_duration_sec`, `disconnection_cnt`, or `reboot_cnt` exceed $\mu + 3\sigma$ calculated over the prior 28-day baseline $[T-28\text{d}, T)$.
2. **Telemetry Silence Penalty** ($\text{silent\_hours} = 168 - \text{reported\_hours}$): Identifies dead or disconnected gateways that stopped transmitting.
3. **Capped Offline Duration**: $\min(\text{offline\_hrs}, 48) \times 0.5$ captures severe continuous downtime.
4. **Decayed Meter Failure Rate**: $10.0 \times \left(1 - \frac{\text{meters\_read}}{\max(1, \text{meters\_expected})}\right) \times 0.8^{\text{weeks\_lag}}$.
5. **Expert Review Flag**: $+2.0$ boost if engineer review labeled `Schlecht` (strictly for $T \ge \text{2026-02-16}$).

$$\text{Raw Score} = \text{flagged\_hours}_{3\sigma} + 0.5 \cdot \min(\text{offline\_hrs}, 48) + 10.0 \cdot \text{meter\_fail\_rate} \cdot 0.8^{\text{weeks\_lag}} + 0.05 \cdot \text{silent\_hrs} + 2.0 \cdot \text{expert\_schlecht}$$

#### Step 3: Multi-Week Episode Cooldown Optimization
To prevent repeat-visit waste within ongoing fault episodes:
$$\text{Final Score} = \text{Raw Score} \times \begin{cases} 
0.10 & \text{if visited in week } w-1 \\ 
0.25 & \text{if visited in week } w-2 \\ 
0.50 & \text{if visited in week } w-3 \\ 
1.00 & \text{otherwise} 
\end{cases}$$
*Result*: Visited gateways are suppressed during the 3-week repair/stabilization cycle, yielding **85 unique gateways visited across 120 slots** without burning slots.

#### Step 4: Deterministic Tie-Breaking
Sorted deterministically by:
1. `score` **Descending**
2. `gateway_id` **Ascending** (lexicographical)

#### Step 5: Operations-Centric Reason Generation
Generates concise, informative reason strings ($\le 300$ characters) explaining the root operational cause (e.g. `43h >3-sigma breach on disconnection_cnt; 141.2h total offline; 39 disconnects; 25h telemetry silence; meter fail rate 52.1%`).

---

### What is Solved in Part 1?
- ✅ 100% adherence to the 15-visit/week constraint.
- ✅ Zero temporal leakage across all datasets.
- ✅ Resolves silent gateway blindness through silence counters.
- ✅ Eliminates repeat-visit waste through episode cooldown decay.
- ✅ Filters warehouse hardware from false alarms.
- ✅ Passes `validate_submission.py` with exit code 0.

---

### How to Run & Validate Part 1

```bash
# 1. Run pipeline CLI
python run.py --data data --out predictions.csv

# 2. Validate output schema, rows, ranks, and reason length
python validate_submission.py predictions.csv

# 3. Run automated core tests
pytest tests/test_temporal_cutoff.py tests/test_schema_and_validation.py tests/test_reproducibility.py tests/test_components.py -v
```

---

## 4. Part 2: Track B — Software Development REST Web Service

### What is Part 2 and How Does it Solve the Problem?
An anomaly algorithm is useless if field dispatchers, operations managers, and technicians cannot access it seamlessly. 

**Part 2 (Track B)** wraps the prioritization pipeline in a **production-grade FastAPI REST Web Service** (`src/api.py`), providing real-time HTTP endpoints, polymorphic ranker swapping, dynamic on-disk data freshness, and interactive Swagger documentation.

---

### Key Features & Endpoints in Part 2

| Endpoint | Method | Key Parameters | Purpose & Value |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | None | Liveness probe reporting active data directory, available weeks, and registered rankers. |
| `/fleet/summary` | `GET` | `?week=YYYY-MM-DD` | Fleet-wide macro health (active count, 3$\sigma$ spikes, silent gateways, average meter fail rate). |
| `/rankings` | `GET` | `?week=YYYY-MM-DD`, `?week=latest`, `?ranker=composite\|baseline` | Returns top 15 prioritized gateways for field dispatch with scores and detailed reasons. |
| `/gateways/{id}` | `GET` | Path `gateway_id`, `?week=YYYY-MM-DD`, `?ranker=...` | Single-gateway operational diagnostics (supports bare MAC `0A2778A31BE3` or colon MAC `0a:27:78:a3:1b:e3`). |
| `/gateways/{id}/history` | `GET` | Path `gateway_id`, `?ranker=...` | Full 8-week chronological trend showing weekly ranks, scores, offline hours, and dispatch flags. |
| `/run` | `POST` | `?ranker=...`, `?out=predictions.csv` | Re-executes the pipeline dynamically over disk without server restart (protected by non-blocking mutex lock `409 Conflict`). |

#### Important Architectural Highlights:
1. **Dynamic Partition Discovery (`week=latest`)**: Automatically discovers the newest telemetry partition on disk without hardcoded dates.
2. **Polymorphic Ranker Interface (`BaseRanker`)**: Allows instant runtime switching between `composite` and `baseline` rankers via query parameters without redeploying.
3. **Defensive Error Handling**:
   - `400 Bad Request`: Friendly date errors with nearest-Monday recommendations.
   - `404 Not Found`: Gateway ID not found in fleet.
   - `409 Conflict`: Non-blocking mutex prevents concurrent pipeline write collisions.
   - `422 Unprocessable Entity`: Missing or invalid data directories.

---

### Step-by-Step Guide to Running & Testing the API

```bash
# Step 1: Start the REST API server
python run.py --serve --host 127.0.0.1 --port 8000

# Step 2: Open Interactive API Documentation in Browser
# Swagger UI: http://127.0.0.1:8000/docs
# ReDoc:      http://127.0.0.1:8000/redoc

# Step 3: Example curl requests in terminal
# 1. Health check
curl "http://127.0.0.1:8000/health"

# 2. Fleet-wide summary
curl "http://127.0.0.1:8000/fleet/summary?week=2026-02-02"

# 3. Top 15 ranked gateways for dispatch
curl "http://127.0.0.1:8000/rankings?week=2026-02-02"

# 4. Top 15 ranked gateways for latest dynamically discovered week
curl "http://127.0.0.1:8000/rankings?week=latest"

# 5. Gateway operational diagnostics (supports bare or colon MAC)
curl "http://127.0.0.1:8000/gateways/0A2778A31BE3?week=2026-02-02"

# 6. Gateway 8-week history trajectory
curl "http://127.0.0.1:8000/gateways/0A2778A31BE3/history"

# 7. Dynamically trigger pipeline execution over disk
curl -X POST "http://127.0.0.1:8000/run"

# Step 4: Run full 29-test automated test suite
pytest -v
```

---

## 5. Deep-Dive into AI-USAGE.md & DECISIONS.md

### `AI-USAGE.md`
This file provides a transparent declaration of AI usage, verification procedures, and 3 concrete AI mistakes caught and resolved:
1. **Unicode Greek $\sigma$ Crash on Windows CP1252 Consoles**:
   - *Issue*: AI generated reason strings with unicode `σ` (`>3σ breach`).
   - *Fix*: Caught via terminal testing; replaced with ASCII `>3-sigma` for 100% OS portability.
2. **Pandas 3.0 Datetime vs Date Comparison TypeError**:
   - *Issue*: AI wrote `decom_dates >= monday`, comparing `datetime64[s]` Series with standard library `date`.
   - *Fix*: Caught via `pytest`; converted operands to `pd.Timestamp(monday)` with explicit `isna()` masks.
3. **Assumed UTF-8 Encoding for German Dataset CSVs**:
   - *Issue*: Standard `pd.read_csv()` threw `UnicodeDecodeError` on German umlauts (`ß` = 0xDF in `gateway_master.csv`).
   - *Fix*: Set `encoding='latin1'` across all CSV loaders for robust German text ingestion.

---

### `DECISIONS.md`
Documents the 6 architectural choices, trade-offs, and future roadmap:

1. **Decision 1: Strict Monday 00:00 UTC Cutoff** — Aligns with `ts_utc` timestamps, eliminating any future-to-past data leakage.
2. **Decision 2: Multi-Source Risk Scoring vs Pure 3-Sigma** — Ingests meter read failure rates, offline duration, silence counters, and engineer reviews to capture silent hardware failures.
3. **Decision 3: Multi-Week Episode Cooldown ($0.10 \to 0.25 \to 0.50 \to 1.00$)** — Prevents repeat-visit slot burn during continuous multi-week fault episodes (€0 incremental savings under Round-2 FAQ 4.1).
4. **Decision 4: In-Service Gateway Boundary Filtering** — Eliminates false silence alarms from uninstalled warehouse hardware (33 future-commissioned units).
5. **Decision 5: Exponential Meter Staleness Decay ($0.8^{\text{weeks\_lag}}$)** — Automatically de-weights aging January meter snapshots as evaluation progresses into March.
6. **Decision 6: Track B (Software Development) Selection** — Delivers modular REST API, OpenAPI docs, swappable rankers, and 29 automated tests.

#### Known Limitations:
- *Limitation 1*: Cannot distinguish carrier-wide cellular tower blackouts from individual gateway hardware faults.
- *Limitation 2*: Cannot verify on-site physical technician repair success from static data.
- *Limitation 3*: Cannot predict pre-failure thermal degradation without sub-hourly sensor curves.

---

## 6. Docker & Containerization: How to Run & Why It Is Useful

### Why Docker is Useful:
1. **Zero-Dependency Reproducibility**: Guarantees bit-for-bit identical execution across Windows, macOS, Linux, and CI/CD pipelines regardless of host Python versions.
2. **Isolated Environment**: Encapsulates dependencies (`pandas`, `pyarrow`, `fastapi`, `uvicorn`, `pytest`) in an isolated container without polluting system packages.
3. **One-Command Evaluation**: Evaluators can run the entire pipeline and validation suite with a single command without configuring local virtual environments.

### How to Run Docker:

```bash
# Option A — Docker Compose (Recommended: mounts data and outputs predictions.csv to host)
docker compose up

# Option B — Native Docker CLI
# Build image
docker build -t lpdg-prioritizer .

# Run pipeline container with mounted host data directory
docker run --rm -v $(pwd)/data:/app/data -v $(pwd):/app/output lpdg-prioritizer
```

---

## 7. Live Interview & Defense Scenarios (The 3 Critical Questions)

### Question 1: *"We hand you a month of data nobody has seen and ask your thing to run on it while we watch."*

#### Defense & Demonstration Plan:
1. **No Hardcoded Dates**: Our system dynamically scans the `data/telemetry/` directory. If you drop a new month (e.g. `month=2026-04/` or `month=2026-05/`), the pipeline automatically:
   - Discovers all Parquet partitions on disk.
   - Computes baseline statistics from the 28 days preceding the target Monday.
   - Slices telemetry strictly to $[T-28\text{d}, T)$.
2. **Live CLI Execution**:
   ```bash
   python run.py --data new_unseen_data/ --out new_predictions.csv
   python validate_submission.py new_predictions.csv
   ```
3. **Live REST API Dynamic Freshness**:
   - Without restarting the server, query:
     ```bash
     curl "http://127.0.0.1:8000/rankings?week=latest"
     ```
   - The API will dynamically inspect disk, identify the latest partition, score the active fleet, and return the top 15 ranked gateways instantly.

---

### Question 2: *"We ask you to make one change, live, in the area you picked. Not a rewrite — one change, with us in the room."*

#### Prepared Live Change Options for Track B:

- **Option A: Add a new filter or custom parameter to the REST API**
  - *Example*: Add a query parameter `?min_score=50.0` or `?exclude_silent=true` to `GET /rankings` in `src/api.py` and `src/schemas.py`.
  - *Time to execute*: < 2 minutes (add parameter to FastAPI route, filter the dataframe, return response).

- **Option B: Adjust Signal Weights or Cooldown Penalty**
  - *Example*: Adjust the meter failure weight from $10.0$ to $15.0$ or change the week-1 cooldown multiplier from $0.10$ to $0.05$ in `src/config.py` / `src/ranker.py`.
  - *Time to execute*: < 1 minute, re-run `pytest tests/test_components.py` to confirm.

- **Option C: Add a new Fleet Health metric endpoint**
  - *Example*: Add `decommissioned_count` or `average_offline_hours` to `GET /fleet/summary` in `src/api.py`.
  - *Time to execute*: < 3 minutes.

---

### Question 3: *"We ask what another week would buy you"*

#### Structured 3-Point Answer:

1. **Spatial & Carrier Neighborhood Clustering (4 Engineering Days)**:
   - *Goal*: Correlate gateway offline spikes by `region` and cellular operator (`site_type` / `operator_TelekomDE`).
   - *Impact*: If 15 gateways in the same postal code go offline simultaneously, classify as an external carrier tower outage and suppress technician dispatches, **saving €760–€1,140/month in false-alarm dispatches**.

2. **Geographic Field Technician Route Optimization (4 Engineering Days)**:
   - *Goal*: Cluster the top 15 weekly candidates geographically (travel-distance TSP heuristic).
   - *Impact*: Reduces technician windshield travel time and allows 1 technician to inspect multiple neighboring flagged gateways in a single day.

3. **Closed Work-Order Feedback Loop (6 Engineering Days)**:
   - *Goal*: Dynamically ingest technician closure codes from `field_visits.csv` (`parts_replaced`, `outcome`).
   - *Impact*: Automatically adjusts gateway risk priors based on component lifespan and dynamically tunes episode cooldown duration.
