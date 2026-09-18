# 5-Slide Interview Presentation: LPDG Selection Challenge 2026

**Candidate Registration ID**: `24095A3305`  
**Track**: **Part 2 — Track B: Software Development**  
**Repository**: [Manju-05/LPDG_Challange](https://github.com/Manju-05/LPDG_Challange)

---

## 🖥️ Slide 1: Operational Context & The Business Problem

### Slide Content (What is on the Screen):
* **Fleet Scale**: ~320 smart utility radio gateways deployed across Germany (rooftops, basements, plant rooms).
* **Cascading Impact**: Each gateway aggregates telemetry and meter readings for **40 to 900 utility meters** (water, gas, electricity, heating). Gateway failures silently cut off customer billing data.
* **The Operational Constraint**:
  * **15 field technician visits per week** (hard capacity quota: 120 visits across 8 evaluation weeks).
* **The Asymmetric Economic Model**:
  * **€380 fixed cost** per dispatched field visit.
  * **€380 wasted** on false alarms (visiting healthy gateways).
  * **€600/week penalty** recurring for every week a faulty gateway remains unvisited.
* **Objective**: Accurately predict and rank the **Top 15 gateways** most urgently requiring physical intervention for each Monday from **2 Feb 2026 to 23 Mar 2026**.

---

### 🎙️ Speaker Notes (What You Say):
> *"Good morning/afternoon. Today I’m presenting our field visit prioritization system and REST web service for LPDG's utility radio network.  
> LPDG manages approximately 320 gateways across Germany, each connecting 40 to 900 meters. When a gateway silently drops offline, hundreds of meters stop transmitting, risking inaccurate billing and heavy dispatch costs.  
> We have a strict operational quota of 15 technician visits per week, and missing a broken gateway costs €600 every single week compared to a €380 visit cost. Our goal is to maximize economic savings by dispatching technicians to the highest-risk units without wasting slots on false alarms."*

---

## 🖥️ Slide 2: Technical Dilemmas & Core Challenges

### Slide Content (What is on the Screen):
* **1. Silent Power Outage Blindness**:
  * Standard 3-sigma anomaly spike counters only flag high values. When power cuts completely, telemetry drops to 0—producing **zero spikes** and getting ignored.
* **2. Episode Economics & Repeat Visit Burn**:
  * Under Round-2 FAQ §4.1, the first visit halts the €600/week penalty. Re-visiting the same ongoing fault in subsequent weeks yields **€0 incremental savings** and wastes €380.
* **3. Warehouse vs. Live Field Gateways**:
  * Master registry contains 33 future-commissioned warehouse units with 0 telemetry. Without lifecycle filtering, they falsely trigger maximum silence penalties.
* **4. Aging Meter Snapshot Drift**:
  * Meter success reports end on `2026-01-26`. As we progress toward March, meter data becomes stale and must be decayed relative to fresh telemetry.
* **5. Strict Temporal Isolation**:
  * Absolute zero lookahead bias: strict Monday 00:00 UTC boundary enforcement across all data sources.

---

### 🎙️ Speaker Notes (What You Say):
> *"When designing the prioritization engine, we uncovered critical edge cases that naive anomaly detection misses.  
> First, dead gateways don't produce error logs; a 3-sigma spike counter ignores complete power loss because zero records equal zero spikes.  
> Second, repeat visits to an ongoing problem produce zero extra savings—re-visiting a broken gateway in consecutive weeks wastes a €380 slot.  
> Third, warehouse hardware awaiting spring installation exhibits zero telemetry, which could falsely trigger emergency alarms without active in-service lifecycle filtering. Our architecture directly solves each of these challenges."*

---

## 🖥️ Slide 3: Part 1 — Multi-Source Scoring & Episode Cooldown

### Slide Content (What is on the Screen):
* **Step 1: Active In-Service Filtering**:
  * Filter candidate gateways: $\text{installed\_on} \le T \;\text{AND}\; (\text{decommissioned\_on} \ge T \;\lor\; \text{NULL})$.
* **Step 2: Multi-Source Risk Formula**:
  $$\text{Raw Score} = \text{flagged\_hours}_{3\sigma} + 0.5 \cdot \min(\text{offline\_hrs}, 48) + 10.0 \cdot \text{meter\_fail\_rate} \cdot 0.8^{\text{weeks\_lag}} + 0.05 \cdot \text{silent\_hrs} + 2.0 \cdot \text{expert\_schlecht}$$
  * **Telemetry Spikes**: Captures erratic reboot/disconnect spikes.
  * **Silence Counter**: Identifies completely dead gateways ($168 - \text{reported\_hours}$).
  * **Meter Failure Decay**: $0.8^{\text{weeks\_lag}}$ shifts weight to fresh telemetry as meter reports age.
  * **Engineer Review**: Mid-February expert inspection boost (restricted strictly to $T \ge \text{2026-02-16}$).
* **Step 3: Multi-Week Cooldown Optimization**:
  $$\text{Final Score} = \text{Raw Score} \times \begin{cases} 0.10 & (w-1) \\ 0.25 & (w-2) \\ 0.50 & (w-3) \\ 1.00 & (\text{default}) \end{cases}$$
  * *Result*: Visits **85 unique gateways across 120 slots**, preventing repeat-visit waste.
* **Output**: Fully validated 120-row `predictions.csv` with detailed operational reasons ($\le 300$ chars).

---

### 🎙️ Speaker Notes (What You Say):
> *"For Part 1, we built an integrated multi-signal scoring engine.  
> We filter the fleet down to active in-service hardware, calculate rolling 28-day baseline statistics, and combine 3-sigma spikes, unobserved silence hours, offline duration, exponential meter staleness decay, and ground engineer reviews.  
> To protect the 15-visit quota, we developed a progressive multi-week cooldown schedule that suppresses visited units over a 3-week repair window. This ensures we maximize unique problem resolution—reaching 85 unique gateways across 120 slots while staying 100% deterministic."*

---

## 🖥️ Slide 4: Part 2 — Track B: Production FastAPI REST Web Service

### Slide Content (What is on the Screen):
* **Why Track B (Software Development)?**:
  * An algorithm is only theoretical unless operations dispatchers and field technicians can interact with it in real-time.
* **Core REST API Architecture (`src/api.py`)**:
  * **`GET /health`**: Liveness probe & system metadata.
  * **`GET /fleet/summary`**: Macro fleet health (3$\sigma$ breach count, silent units, average fail rate).
  * **`GET /rankings`**: Top 15 ranked gateways with reasons (`?week=YYYY-MM-DD`, `?week=latest`, `?ranker=composite|baseline`).
  * **`GET /gateways/{id}` & `/history`**: Single-gateway diagnostics & 8-week chronological trend.
  * **`POST /run`**: Dynamically re-executes pipeline over disk without server restart (protected by non-blocking mutex lock `409 Conflict`).
* **Interactive OpenAPI/Swagger Documentation**: Live at `http://127.0.0.1:8000/docs`.
* **Polymorphic Ranker Interface**: Object-oriented `BaseRanker` enabling instant runtime swapping.

---

### 🎙️ Speaker Notes (What You Say):
> *"For Part 2, we specialized in Track B — Software Development.  
> We wrapped the entire pipeline in a production-ready FastAPI service. Operations managers can view fleet-wide summaries, dispatchers can query the top 15 gateways for any target week or dynamically inspect the latest on-disk partition using `week=latest`, and technicians can inspect 8-week historical trajectories for any specific gateway ID.  
> We also implemented polymorphic ranker swapping, structured Pydantic schemas, and a non-blocking mutex lock on `POST /run` to prevent write collisions during live disk reloads."*

---

## 🖥️ Slide 5: Quality Assurance, Verification, & 2-Week Roadmap

### Slide Content (What is on the Screen):
* **Testing & Quality Assurance**:
  * **29/29 Automated Tests Passing** (`pytest -v`): Temporal cutoff integrity, bit-for-bit reproducibility, ID normalization (bare/colon MAC), schema validation, and complete REST API test suite.
  * **Official Validator Compliance**: `validate_submission.py predictions.csv` $\rightarrow$ `OK` (exit code 0).
* **Zero-Setup Deployment**:
  * Docker & Docker Compose (`docker compose up`) for instant cross-platform execution.
* **Transparent Engineering Practices**:
  * `AI-USAGE.md`: Full disclosure of AI tooling + 3 real bugs caught (Windows unicode sigma crash, Pandas date comparisons, German Latin-1 CSV encodings).
  * `DECISIONS.md`: 6 architectural decisions, trade-offs, and risk analysis.
* **What Another Two Weeks Would Deliver**:
  1. **Spatial & Carrier Outage Clustering**: Suppress false alarms caused by regional cellular tower blackouts (saving €760–€1,140/mo).
  2. **Geographic Route Optimization**: TSP travel clustering for field technicians.
  3. **Closed Work-Order Feedback Loop**: Dynamic cooldown tuning based on technician repair codes.

---

### 🎙️ Speaker Notes (What You Say):
> *"To ensure enterprise readiness, we backed the system with 29 automated unit and integration tests, verified reproducibility across platforms with Docker, and documented our engineering choices in `DECISIONS.md` and `AI-USAGE.md`.  
> If given another two weeks, our immediate priority would be spatial clustering to distinguish carrier tower blackouts from individual gateway hardware faults, followed by geographic route batching to cut technician travel time.  
> Thank you, and I am now ready for your questions and the live demonstration!"*
