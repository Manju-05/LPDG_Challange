# LPDG Innovation Hub — Selection Challenge 2026 (Part 1)

An automated, economically-driven field visit prioritization system for LPDG's smart utility radio network (~320 gateways).

---

## 1. Project Overview & Operational Context

LPDG operates a utility radio network consisting of approximately **320 gateways** installed across rooftops, basements, and plant rooms. Each gateway relays telemetry and periodic meter readings for 40 to 900 connected utility meters.

When a gateway degrades or fails, the meters behind it stop transmitting readings. These failures are typically silent and difficult to diagnose immediately, leading to unread meters, inaccurate billing cycles, and manual read dispatch costs.

### The Operational Challenge:
- **Field Capacity Constraint**: Hard limit of **15 field visits per week** (120 total visits across the 8-week evaluation window).
- **Objective**: Identify and rank the 15 gateways most urgently requiring a technician visit for each of the 8 scored weeks from **2 February 2026 to 23 March 2026**.

### Economic Cost Model:
- **Dispatched Visit**: **€380** fixed cost per technician visit.
- **False Alarm** (Visit sent, but nothing wrong): **€380 wasted**.
- **Unattended Faulty Gateway**: **€600 per week** recurring penalty for every week a broken gateway remains unattended.
- **Episode Economics**: The first visit to an ongoing fault episode halts the recurring €600/week penalty. Re-visiting the same gateway in subsequent consecutive weeks during the same continuous problem yields **€0 incremental savings** and wastes a €380 visit slot. Early detection is strictly more valuable than late detection.

---

## 2. Repository Structure

```text
├── .gitignore                      # Protects raw data and environment artifacts
├── AI-USAGE.md                     # Statement of AI tool usage, review process, & fixes
├── DECISIONS.md                    # 5 architectural decisions, limitations, & roadmap
├── README.md                       # Main documentation & run instructions
├── baseline_3sigma.py              # Provided 3-sigma anomaly baseline script
├── predictions.csv                 # Generated submission (120 rows, 8 scored weeks)
├── run.py                          # One-command CLI entry point
├── validate_submission.py          # Official submission validator
├── src/
│   ├── __init__.py                 # Package initialization
│   ├── config.py                   # System constants, scored weeks, cost parameters
│   ├── data_loader.py              # Robust loaders for Parquet, CSVs, and Excel
│   ├── features.py                 # Multi-signal extraction with strict cutoff enforcement
│   ├── pipeline.py                 # End-to-end pipeline coordinator
│   ├── ranker.py                   # Scoring engine, episode cooldown, & deterministic sort
│   └── reason_generator.py         # Operations-centric reason builder (<= 300 chars)
└── tests/
    ├── test_components.py          # Unit tests for normalization, cooldown, & formatting
    ├── test_reproducibility.py     # Idempotency & determinism tests across runs
    ├── test_schema_and_validation.py # Synthetic fixture & output schema validation tests
    └── test_temporal_cutoff.py     # Strict temporal cutoff & leakage prevention tests
```

---

## 3. Quickstart & Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)
- Core dependencies: `pandas`, `numpy`, `pyarrow`, `pytest`

### Step 1: Clone Repository & Mount Data
Place the unzipped challenge `data/` directory at repository root:
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

### Step 2: Run Pipeline (One Command)
Generate the 120-row prediction file using your preferred execution method:

**Option A — Python**:
```bash
python run.py --data data --out predictions.csv
```

**Option B — Make**:
```bash
make run
```

**Option C — Shell Script (Unix / macOS / Linux)**:
```bash
./run.sh
```

**Option D — Docker Compose**:
```bash
docker compose up
```

### Step 3: Validate the Submission
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

## 4. Running the Automated Test Suite

Run the full pytest suite to verify temporal cutoff integrity, schema compliance, and reproducibility:
```bash
python -m pytest tests/ -v
```

### Test Coverage Highlights:
- **Temporal Leakage Prevention** ([`tests/test_temporal_cutoff.py`](file:///d:/Sigma/LPDG/tests/test_temporal_cutoff.py)):
  - Asserts all timestamps strictly on or after Monday 00:00 UTC are discarded.
  - Verifies `engineer_review_2026-02.xlsx` (dated 2026-02-15) is completely withheld for weeks starting `2026-02-02` and `2026-02-09`, only taking effect on `2026-02-16`.
- **Output Validation & Fixtures** ([`tests/test_schema_and_validation.py`](file:///d:/Sigma/LPDG/tests/test_schema_and_validation.py)):
  - Validates isolated synthetic fixtures and full `predictions.csv` against `validate_submission.py`.
- **Reproducibility** ([`tests/test_reproducibility.py`](file:///d:/Sigma/LPDG/tests/test_reproducibility.py)):
  - Executes the entire pipeline twice from scratch and verifies bit-for-bit identical output.
- **Components** ([`tests/test_components.py`](file:///d:/Sigma/LPDG/tests/test_components.py)):
  - Tests ID normalization, reason string length ($\le 300$ chars), and episode cooldown decay.

---

## 5. Technical Design & Ranking Methodology

### Strict Temporal Boundary Enforcement
For any target Monday $T$ (`2026-02-02` through `2026-03-23`):
- **Telemetry**: Evaluates a 28-day baseline window $[T - 28\text{d}, T)$ and recent 7-day observation window $[T - 7\text{d}, T)$. Any data timestamped $ts \ge T$ is strictly excluded.
- **Meter Reads**: Slices `meter_read_success.csv` strictly on $\text{week\_date} < T$ (the reporting week of $T$ is not yet available at dispatch time).
- **Field Visits**: Slices `field_visits.csv` on $\text{visited\_on} < T$.
- **Engineer Review**: Strictly restricted to $T \ge \text{2026-02-16}$.

### Multi-Source Signal Formulation
The ranking engine synthesizes four orthogonal evidence streams into an operational risk score:
1. **3-Sigma Telemetry Anomalies**: Hourly spikes exceeding $\mu + 3\sigma$ in `offline_duration_sec`, `disconnection_cnt`, or `reboot_cnt`.
2. **Telemetry Silence & Missing Hours**: Tracks unobserved hours ($\text{silent\_hours} = 168 - \text{reported\_hours}$) for active commissioned gateways.
3. **Meter Reading Failure Rate**: $\Delta = 1 - \frac{\text{meters\_read}}{\max(1, \text{meters\_expected})}$ from the most recent prior week.
4. **Engineer Ground Review**: High-risk flag for gateways reviewed as `Schlecht` (for weeks on or after 2026-02-16).

$$\text{Raw Score} = \text{flagged\_hours}_{3\sigma} + 0.5 \cdot \min(\text{offline\_hrs}, 48) + 10.0 \cdot \text{meter\_fail\_rate} + 0.05 \cdot \text{silent\_hrs} + 2.0 \cdot \text{expert\_schlecht}$$

### Episode Cooldown Discounting
To optimize within the 15-visit quota:
$$\text{Final Score} = \text{Raw Score} \times \begin{cases} 0.2 & \text{if visited in week } w-1 \\ 1.0 & \text{otherwise} \end{cases}$$
This prevents burning scarce visits on unchanged continuing faults and redirects technician capacity to newly degraded gateways.

### Deterministic Tie-Breaking
Rows are sorted by:
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

- **[`predictions.csv`](file:///d:/Sigma/LPDG/predictions.csv)**: Validated submission file.
- **[`DECISIONS.md`](file:///d:/Sigma/LPDG/DECISIONS.md)**: 5 core architectural decisions, trade-offs, risks, Part 2 Track Selection (Track B — Software Development), and limitations.
- **[`AI-USAGE.md`](file:///d:/Sigma/LPDG/AI-USAGE.md)**: Transparent declaration of AI tooling, manual review procedures, and concrete AI errors caught and resolved.
- **[`run.py`](file:///d:/Sigma/LPDG/run.py)** & **[`src/`](file:///d:/Sigma/LPDG/src/)**: Offline pipeline implementation.
- **[`tests/`](file:///d:/Sigma/LPDG/tests/)**: Automated verification suite.

---

## 8. Screen Recording Walkthrough Outline (6–8 Minutes)

1. **Problem & Economic Context (1 min)**: Fleet size (~320 gateways), 15 visits/week limit, €380 visit cost vs €600 recurring unattended fault penalty.
2. **Architecture & Cutoff Enforcement (2 mins)**: Walk through `src/` modules, showing strict Monday 00:00 UTC boundaries and date-checked engineer review integration.
3. **One-Command Execution (1 min)**: Execute `python run.py --data data --out predictions.csv` in terminal.
4. **Validation & Test Execution (1.5 mins)**: Run `python validate_submission.py predictions.csv` and `python -m pytest tests/ -v`.
5. **Decisions & Part 2 Focus (1.5 mins)**: Review episode cooldown strategy, explain Part 2 selection (Track B — Software Development), and address limitations documented in `DECISIONS.md`.
