# Architectural & Engineering Decisions (DECISIONS.md)

This document details the core architectural decisions made during the design and implementation of the field visit prioritization engine, followed by known system limitations and a prioritized engineering roadmap.

---

## 1. Core Engineering Decisions

### Decision 1: Temporal Cutoff Convention (Strict Monday 00:00 UTC)
- **Decision**: Enforce a strict cutoff at `Monday 00:00:00 UTC` for all datasets prior to target prediction week $T$. Telemetry is sliced strictly on $[T-28d, T)$, meter reads strictly on $\text{week\_date} < T$, and the engineer review spreadsheet (dated 2026-02-15) is only available for $T \ge \text{2026-02-16}$.
- **Alternative Considered**: Local Berlin midnight (`Europe/Berlin`), or using weekly aggregated summaries regardless of publication date.
- **Why Chosen**: Telemetry timestamps are recorded in UTC (`ts_utc`). Aligning all dataset boundaries strictly to Monday 00:00 UTC prevents timezone edge-case mismatches and eliminates any possibility of future-to-past data leakage.
- **Trade-off**: Slicing at Monday 00:00 UTC discards data that arrived during Monday morning before field dispatch, but ensures absolute temporal safety.
- **Risk**: If field engineers are dispatched late on Monday afternoon based on fresh Monday morning telemetry, our system will not reflect those extra few hours of data.

---

### Decision 2: Multi-Source Risk Scoring vs Pure 3-Sigma Anomaly Counts
- **Decision**: Augment the 3-sigma telemetry anomaly baseline with meter read failure rates, offline duration accumulation, silence counters, and expert review annotations.
- **Alternative Considered**: Relying purely on the supplied `baseline_3sigma.py` 3-sigma hourly count.
- **Why Chosen**: A gateway may suffer severe operational failure (e.g. power supply failure or radio silence) without triggering 3-sigma spikes if it stops reporting entirely. Integrating meter read success ($1 - \frac{\text{read}}{\text{expected}}$) provides direct business evidence of data loss.
- **Trade-off**: Adds additional data dependencies (`meter_read_success.csv`, `gateway_master.csv`) and minor processing overhead compared to single-table baseline.
- **Risk**: Meter read data is reported weekly with a lag, meaning sudden rapid drops occurring in the last 48 hours must be captured primarily by telemetry indicators.

---

### Decision 3: Multi-Week Episode Cooldown & Visit Deduplication Under the 15-Visit Cap
- **Decision**: Apply a progressive multi-week episode cooldown schedule ($0.10\times$ in week $w+1$, $0.25\times$ in week $w+2$, and $0.50\times$ in week $w+3$) to gateways selected for a field visit in prior weeks.
- **Alternative Considered**: Single-week stateless cooldown, or independent weekly ranking (as done in `baseline_3sigma.py`).
- **Why Chosen**: Round-2 FAQ 4.1 explicitly emphasizes that within an ongoing fault episode, only the earliest visit halts the €600/week penalty. Re-visiting the same gateway in subsequent consecutive weeks during the same continuous episode yields **€0 incremental savings** and wastes a scarce €380 visit slot. A multi-week cooldown prevents repeat-visit burn throughout the expected 3–4 week fault lifecycle.
- **Trade-off**: If a technician visit failed to resolve the issue on the first attempt, the gateway is temporarily de-prioritized for 1–2 weeks before full eligibility resumes in week 4.
- **Risk**: If on-site technician parts replacement fails, follow-up intervention is delayed until the cooldown decays.

---

### Decision 4: In-Service Gateway Boundary Filtering & Telemetry Silence Accounting
- **Decision**: Filter candidate gateways strictly by in-service dates ($\text{installed\_on} \le T$ AND $\text{decommissioned\_on} \ge T$). For verified in-service gateways, track missing reported hours ($\text{silent\_hours} = 168 - \text{reported\_hours}$) as an additive risk indicator rather than zero-filling.
- **Alternative Considered**: Unfiltered master registry with global `fillna(0)` across missing telemetry rows.
- **Why Chosen**: In `gateway_master.csv`, 33 gateways have `installed_on > 2026-02-02` (commissioned later in spring/summer 2026). Without active in-service filtering, uninstalled warehouse gateways exhibit 0 telemetry hours, falsely triggering 168h silence penalties. Filtering ensures only operational hardware is evaluated, and complete telemetry silence on active units correctly indicates backhaul/power loss.
- **Trade-off**: Requires joint filtering across installation and decommissioning timestamp columns.
- **Risk**: If installation date records in the master table have clerical lag, freshly deployed gateways might be omitted from the candidate pool for 1 week.

---

### Decision 5: Meter Read Staleness Exponential Decay
- **Decision**: Apply an exponential staleness discount factor ($\text{decay} = 0.8^{\text{weeks\_lag}}$) to meter read failure rates as prediction week $T$ drifts past the last published meter report (`2026-01-26`).
- **Alternative Considered**: Treating the static 2026-01-26 meter read snapshot as permanently fresh across all 8 evaluation weeks.
- **Why Chosen**: Per the Round-2 FAQ, `meter_read_success.csv` ends on 2026-01-26. In evaluation week 1 (2026-02-02), the report is 1 week old (fresh), but by week 8 (2026-03-23), it is 8 weeks old. Decaying the weight of stale historical reports ensures the system relies progressively more on fresh March telemetry rather than two-month-old historical meter data.
- **Trade-off**: Meter read signal influence smoothly diminishes in later evaluation weeks.
- **Risk**: If telemetry coverage drops on a gateway with historic meter failure, the decayed meter signal might not elevate it as aggressively in week 8.

---

### Decision 6: Part 2 Specialization Track Selection — Track B (Software Development)
- **Decision**: Implemented **Track B — Software Development**, delivering a production-grade FastAPI REST web service (`src/api.py`), decoupled ranking interface (`BaseRanker`), deliberate error handling (HTTP 400/404/409/422), interactive OpenAPI docs (`/docs`), fleet health summary (`GET /fleet/summary`), multi-week gateway history (`GET /gateways/{id}/history`), dynamic `/run` re-ranking without server restart, and a 22-test automated suite.
- **Alternative Considered**: Track A (Data Engineering), Track C (DevOps), or Track E (Machine Learning).
- **Why Chosen**: An anomaly ranking algorithm provides zero business value if field dispatchers and technicians cannot easily query it at 8:00 AM, inspect diagnostic reasons, evaluate fleet health, trigger re-runs when new data lands, and integrate it into field ticketing systems.
- **Trade-off**: Focuses engineering effort on software modularity, API design, and resilience rather than training black-box machine learning models.
- **Risk**: If the core ranking logic requires extensive nonlinear parameter tuning, an ML-focused track might yield marginally higher precision on specific holdout splits.

---

## 2. What the System Cannot Do (Known Limitations)

1. **Cannot Distinguish Carrier Outages from Hardware Faults**: If a regional cellular operator (e.g. TelekomDE or VodafoneDE) suffers a 24-hour tower blackout, all gateways in that area will exhibit simultaneous offline spikes. The system will flag them as high-priority visits even though on-site intervention cannot resolve a carrier-side outage.
2. **Cannot Verify On-Site Repair Success**: Because the challenge telemetry dataset is static and counterfactual, the pipeline cannot confirm whether a field engineer actually replaced a faulty part or if the work order was closed as "no access".
3. **Cannot Predict Pre-Failure Thermal Degradation**: Without sub-hourly sensor telemetry (e.g. capacitor temperature or battery voltage curves), gradual hardware degradation can only be detected once packet drops or disconnection events begin.

---

## 3. What Another Two Weeks Would Fix (Prioritized Roadmap)

1. **Spatial & Carrier Neighborhood Clustering (Estimated: 4 days)**:
   - *Action*: Group gateways by `region` and `site_type` to calculate fleet-wide correlation. If all gateways on `operator_TelekomDE` in `Baden-Württemberg` go down together, classify as an external carrier outage and suppress individual dispatch recommendations.
   - *Value*: Saves an estimated 2–3 false-alarm visits per month (€760–€1,140/mo).
2. **Technician Routing & Visit Batching (Estimated: 4 days)**:
   - *Action*: Cluster the top 15 weekly candidates geographically so that dispatched field engineers minimize travel time and maximize the chance of inspecting neighboring suspect gateways.
   - *Value*: Improves field technician efficiency and capacity utilization.
3. **Automated Feedback Loop from Closed Work Orders (Estimated: 6 days)**:
   - *Action*: Ingest structured work order outcomes (`field_visits.csv` `parts_replaced` and `outcome`) dynamically as technicians close tickets, adapting gateway risk priors based on component lifespan.
   - *Value*: Dynamically tunes the episode cooldown duration based on historical repeat-failure rates.
