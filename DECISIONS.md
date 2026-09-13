# Architectural & Engineering Decisions (DECISIONS.md)

This document details five fundamental decisions made during the design and implementation of the Part 1 field visit prioritization engine, followed by known system limitations and a prioritized engineering roadmap.

---

## 1. Five Core Decisions

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

### Decision 3: Episode Cooldown & Visit Deduplication Under the 15-Visit Cap
- **Decision**: Apply an episode cooldown penalty (0.2x score multiplier) to gateways that were already selected for a field visit in the immediately preceding week ($w-1$).
- **Alternative Considered**: Independent stateless weekly ranking (as done in `baseline_3sigma.py`).
- **Why Chosen**: The challenge economics dictate that the first visit to a broken gateway halts the recurring €600/week penalty for that episode. Re-visiting the same gateway in consecutive weeks during the same continuous problem wastes €380 and burns 1 of our 15 weekly slots without saving additional money.
- **Trade-off**: If a technician visit fails to fix the problem and the gateway remains broken in a brand-new episode, the system will temporarily de-prioritize it for 1 week.
- **Risk**: If the field team did not actually repair the gateway on their initial visit, the cooldown might delay a necessary follow-up.

---

### Decision 4: Handling Telemetry Silence as Ambiguous Risk Rather Than Zero-Filling
- **Decision**: Track unreported hours ($\text{silent\_hours} = 168 - \text{reported\_hours}$) as an additive risk factor for active gateways, rather than applying a global `fillna(0)` across missing rows.
- **Alternative Considered**: Imputing zeros for missing telemetry hours, or discarding gateways with missing hours.
- **Why Chosen**: In IoT radio networks, complete silence often indicates backhaul loss, antenna disconnection, or power outage. Imputing zero disconnects/offline seconds would make a completely dead gateway appear completely healthy.
- **Trade-off**: Minor network coverage drops or intermittent telco maintenance could slightly elevate silence risk.
- **Risk**: A newly installed gateway commissioned midway through the week might have fewer than 168 hours of historical data without being faulty.

---

### Decision 5: Part 2 Specialization Track Selection — Track B (Software Development)
- **Decision**: Implemented **Track B — Software Development**, delivering a production-grade FastAPI REST web service (`src/api.py`), decoupled ranking interface (`BaseRanker`), deliberate error handling (HTTP 400/404/409/422), interactive OpenAPI docs (`/docs`), and full automated test suite.
- **Alternative Considered**: Track A (Data Engineering), Track C (DevOps), or Track E (Machine Learning).
- **Why Chosen**: An anomaly ranking algorithm provides zero business value if field teams cannot easily query it, inspect reasoning, trigger re-runs when new data lands, and integrate it into field dispatch workflows. Track B provides a clean REST API, swappable ranking abstractions, robust error handling for corrupt inputs, comprehensive test suites, and self-documenting endpoints.
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
