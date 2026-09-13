"""Unit and regression tests for temporal cutoff rules and leakage prevention."""

from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.config import ENGINEER_REVIEW_DATE
from src.features import extract_features_for_week


def test_engineer_review_cutoff_enforced() -> None:
    """Engineer review (dated 2026-02-15) must not influence predictions before 2026-02-16."""
    gateway_id = "0A0000000001"
    monday_early = dt.date(2026, 2, 2)
    monday_valid = dt.date(2026, 2, 16)

    # Telemetry dummy
    ts_range = pd.date_range("2026-01-01", "2026-03-01", freq="h", tz="UTC")
    telemetry = pd.DataFrame({
        "gateway_id": [gateway_id] * len(ts_range),
        "ts": ts_range,
        "offline_duration_sec": [100.0] * len(ts_range),
        "disconnection_cnt": [1] * len(ts_range),
        "reboot_cnt": [0] * len(ts_range),
    })

    master = pd.DataFrame({
        "gateway_id": [gateway_id],
        "n_meters_installed": [100],
        "decommissioned_on": [None],
    })

    meter_reads = pd.DataFrame(columns=["week_start", "gateway_id", "meters_expected", "meters_read", "week_date"])

    engineer_review = pd.DataFrame({
        "gateway_id": [gateway_id],
        "Kategorie": ["Schlecht"],
        "reviewed_on": ["2026-02-15"],
    })

    # Week 1: 2026-02-02 (before 2026-02-16) -> expert_schlecht must be 0
    feat_early = extract_features_for_week(
        monday=monday_early,
        telemetry=telemetry,
        gateway_master=master,
        meter_reads=meter_reads,
        engineer_review=engineer_review,
    )
    assert feat_early.loc[feat_early["gateway_id"] == gateway_id, "expert_schlecht"].values[0] == 0

    # Week 3: 2026-02-16 (on/after 2026-02-16) -> expert_schlecht must be 1
    feat_valid = extract_features_for_week(
        monday=monday_valid,
        telemetry=telemetry,
        gateway_master=master,
        meter_reads=meter_reads,
        engineer_review=engineer_review,
    )
    assert feat_valid.loc[feat_valid["gateway_id"] == gateway_id, "expert_schlecht"].values[0] == 1


def test_telemetry_future_rows_strictly_excluded() -> None:
    """Telemetry timestamps on or after Monday 00:00 UTC must not be processed."""
    monday = dt.date(2026, 2, 9)
    cutoff_ts = pd.Timestamp(monday, tz="UTC")

    # Construct telemetry with an anomalous spike strictly in the future (on Monday 02:00)
    future_ts = cutoff_ts + pd.Timedelta(hours=2)
    past_ts = cutoff_ts - pd.Timedelta(days=2)

    telemetry = pd.DataFrame({
        "gateway_id": ["0A0000000001", "0A0000000001"],
        "ts": [past_ts, future_ts],
        "offline_duration_sec": [10.0, 99999.0],
        "disconnection_cnt": [0, 50],
        "reboot_cnt": [0, 20],
    })

    master = pd.DataFrame({
        "gateway_id": ["0A0000000001"],
        "n_meters_installed": [100],
    })

    feat = extract_features_for_week(
        monday=monday,
        telemetry=telemetry,
        gateway_master=master,
        meter_reads=pd.DataFrame(),
        engineer_review=pd.DataFrame(),
    )

    # The future anomaly row must have been excluded, total offline should only reflect past_ts
    assert feat["total_offline_sec"].values[0] == pytest.approx(10.0)
