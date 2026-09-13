# LPDG Innovation Hub — Selection Challenge 2026 (Part 1)

An automated, economically-driven field visit prioritization system for LPDG's utility radio network (~320 gateways).

---

## 1. Executive Summary & Problem Context

LPDG operates a fleet of ~320 radio gateways relaying meter readings for utility customers. When a gateway begins to fail, the meters behind it stop transmitting readings, eventually resulting in billing inaccuracies, customer disputes, and costly manual reading trips.

- **Weekly Operational Constraint**: Hard limit of **15 field visits per week** (120 total visits across the 8-week evaluation window).
- **Economic Model**:
  - **Dispatched Visit**: €380 fixed cost.
  - **Wasted Visit** (False Alarm): €380 lost.
  - **Unattended Faulty Gateway**: **€600 per week** recurring penalty for each week the fault persists.
  - **Episode Economics**: The first visit to an ongoing fault episode terminates the €600 weekly accrual. Subsequent visits during the same episode yield zero incremental savings and waste a €380 visit slot.

Our solution replaces spreadsheet-and-gut-feel prioritization with an evidence-based ranking engine that maximizes economic utility under the 15-visit cap.

---

## 2. System Architecture

```
                       ┌─────────────────────────┐
                       │     data/ Directory     │
                       │   (Parquet, CSV, XLSX)  │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │   Data Ingestion Layer  │
                       │ (Encoding & ID normal.) │
                       └────────────┬────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Temporal Cutoff Boundary                          │
│     (Strictly filters data available before Monday 00:00 UTC)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │    Feature Extraction   │
                       │  - 3σ Telemetry Spikes  │
                       │  - Offline & Silence    │
                       │  - Meter Read Loss      │
                       │  - Expert Review (>=W3) │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │ Composite Scorer/Ranker │
                       │  - Multi-source score   │
                       │  - Episode cooldown     │
                       │  - Deterministic sort   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │ Operational Reason Gen  │
                       │   (Concise <= 300 ch)   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                       ┌─────────────────────────┐
                       │     predictions.csv     │
                       │   (120 rows, 8 weeks)   │
                       └─────────────────────────┘
```

---

## 3. Quickstart & One-Command Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.10 – 3.14)
- Standard dependencies: `pandas`, `numpy`, `pyarrow`, `pytest`

### Step 1: Clone Repository & Place Data
Ensure the challenge dataset is in `./data` at repository root:
```bash
# Data directory structure:
# data/telemetry/*.parquet
# data/gateway_master.csv
# data/meter_read_success.csv
# data/field_visits.csv
# data/engineer_review_2026-02.xlsx
```

### Step 2: Run Pipeline (One Command)
```bash
python run.py --data data --out predictions.csv
```
Options:
- `--data <path>`: Path to input data folder (default: `./data`).
- `--out <path>`: Destination path for prediction output (default: `./predictions.csv`).

### Step 3: Validate Output
```bash
python validate_submission.py predictions.csv
```

---

## 4. Running the Test Suite

Run all unit, integration, and leakage verification tests:
```bash
python -m pytest tests/ -v
```

The test suite validates:
- **Temporal integrity**: Asserts zero future leakage beyond Monday 00:00 UTC and verifies `engineer_review_2026-02.xlsx` is strictly excluded before 2026-02-16.
- **Output contract**: Asserts exactly 120 rows (15 per week for 8 weeks), ranks 1..15, valid gateway ID formats, numeric scores, and valid non-empty reasons $\le 300$ characters.
- **Reproducibility**: Asserts bit-for-bit identical output across consecutive runs.
- **Components**: Unit tests for ID normalization, episode cooldown logic, and reason string formatting.

---

## 5. Ranking Methodology & Scoring Logic

1. **Baseline Telemetry Statistics (28-day window $[T-28d, T)$)**:
   Computes mean and standard deviation per gateway for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
2. **Recent Telemetry Anomaly Detection (7-day window $[T-7d, T)$)**:
   Flags hours where metrics exceed $\mu + 3\sigma$. Detects silent hours where active gateways failed to report telemetry.
3. **Meter Read Deterioration**:
   Computes weekly meter reading drop rate $\Delta = 1 - \frac{\text{meters\_read}}{\text{meters\_expected}}$ from the latest reporting week strictly prior to $T$.
4. **Engineer Review Integration**:
   For weeks starting on or after `2026-02-16` (review date `2026-02-15`), gateways marked `Schlecht` receive a prioritized risk weight.
5. **Episode Cooldown**:
   Gateways visited in week $w-1$ receive a cooldown penalty unless a major new anomaly occurs, preventing wasted repeat visits during the same failure episode.
6. **Deterministic Tie-Breaking**:
   Primary key: `score DESC`; secondary key: `gateway_id ASC`.

---

## 6. Screen Recording Script (6–8 Minutes)

For the required candidate walkthrough recording:
1. **Introduction (1 min)**: Overview of the LPDG fleet problem, €380 vs €600 economics, and 15-visit cap.
2. **Architecture & Temporal Safety (2 mins)**: Walk through `src/` modules, explaining the strict Monday 00:00 UTC cutoff and zero-leakage guarantee.
3. **One-Command Execution (1 min)**: Execute `python run.py --data data --out predictions.csv` live in terminal.
4. **Validation & Output Inspection (1.5 mins)**: Run `python validate_submission.py predictions.csv` and inspect sample rows/reasons in `predictions.csv`.
5. **Key Engineering Decisions & Limitations (1.5 mins)**: Highlight episode cooldown rationale, Part 2 track selection, and limitations documented in `DECISIONS.md`.
