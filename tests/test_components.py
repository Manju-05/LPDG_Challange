"""Unit tests for data loader normalization, ranker tie-breaking, and reason formatting."""

from __future__ import annotations

import pandas as pd

from src.data_loader import normalize_gateway_id
from src.ranker import compute_composite_score
from src.reason_generator import build_reason


def test_normalize_gateway_id() -> None:
    """Verify normalization of various gateway id formats."""
    assert normalize_gateway_id("06:39:EA:56:02:C1") == "0639EA5602C1"
    assert normalize_gateway_id("0639ea5602c1") == "0639EA5602C1"
    assert normalize_gateway_id("06-39-ea-56-02-c1") == "0639EA5602C1"
    assert normalize_gateway_id(None) == ""


def test_reason_generator_formatting() -> None:
    """Verify reason generator length and content."""
    row = pd.Series({
        "flagged_hours": 12,
        "worst_metric": "offline_duration_sec",
        "offline_hours": 34.5,
        "total_disconnects": 15,
        "total_reboots": 8,
        "silent_hours": 48,
        "meter_fail_rate": 0.35,
        "expert_schlecht": 1,
    })
    reason = build_reason(row)
    assert len(reason) <= 300
    assert len(reason) > 0
    assert "12h >3-sigma breach on offline_duration_sec" in reason
    assert "34.5h total offline" in reason
    assert "meter fail rate 35.0%" in reason
    assert "engineer review flagged Schlecht" in reason


def test_ranker_episode_cooldown() -> None:
    """Verify that gateways visited in immediately prior week are discounted."""
    features = pd.DataFrame({
        "gateway_id": ["GW_A", "GW_B"],
        "flagged_hours": [10, 10],
        "offline_hours": [0.0, 0.0],
        "meter_fail_rate": [0.0, 0.0],
        "silent_hours": [0, 0],
        "expert_schlecht": [0, 0],
    })

    recent_visits = {"GW_A": 0}  # Visited in week 0
    scored = compute_composite_score(features, recent_visits=recent_visits, current_week_idx=1)

    score_a = scored.loc[scored["gateway_id"] == "GW_A", "score"].values[0]
    score_b = scored.loc[scored["gateway_id"] == "GW_B", "score"].values[0]

    # GW_A should be penalized (0.2x) compared to GW_B (1.0x)
    assert score_a < score_b
    assert score_a == 2.0
    assert score_b == 10.0
