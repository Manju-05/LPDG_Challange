"""Configuration and constants for LPDG selection challenge Part 1."""

from __future__ import annotations

import datetime as dt

# Scored weeks specified by the challenge brief
SCORED_WEEKS: list[dt.date] = [
    dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)
]

# Field operations constraints & costs
VISITS_PER_WEEK: int = 15
COST_VISIT: float = 380.0
COST_FAULTY_WEEK: float = 600.0

# Temporal windows
BASELINE_DAYS: int = 28
RECENT_DAYS: int = 7
SIGMA_THRESHOLD: float = 3.0

# Primary telemetry metrics monitored for 3-sigma anomalies
ANOMALY_METRICS: list[str] = [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]

# Engineer review availability cutoff
ENGINEER_REVIEW_DATE: dt.date = dt.date(2026, 2, 15)

# Reason length limit
MAX_REASON_CHARS: int = 300
