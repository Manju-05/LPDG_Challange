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
    """Verify progressive multi-week episode cooldown schedule."""
    features = pd.DataFrame({
        "gateway_id": ["GW_A", "GW_B", "GW_C", "GW_D"],
        "flagged_hours": [10, 10, 10, 10],
        "offline_hours": [0.0, 0.0, 0.0, 0.0],
        "meter_fail_rate": [0.0, 0.0, 0.0, 0.0],
        "silent_hours": [0, 0, 0, 0],
        "expert_schlecht": [0, 0, 0, 0],
    })

    # GW_A visited week 3 (1 week ago in week 4), GW_B visited week 2 (2 weeks ago), GW_C visited week 1 (3 weeks ago)
    recent_visits = {"GW_A": 3, "GW_B": 2, "GW_C": 1}
    scored = compute_composite_score(features, recent_visits=recent_visits, current_week_idx=4)

    score_a = scored.loc[scored["gateway_id"] == "GW_A", "score"].values[0]
    score_b = scored.loc[scored["gateway_id"] == "GW_B", "score"].values[0]
    score_c = scored.loc[scored["gateway_id"] == "GW_C", "score"].values[0]
    score_d = scored.loc[scored["gateway_id"] == "GW_D", "score"].values[0]

    # Progressive discount: 1 week post (0.10x) < 2 weeks post (0.25x) < 3 weeks post (0.50x) < unvisited (1.0x)
    assert score_a == 1.0   # 10 * 0.10
    assert score_b == 2.5   # 10 * 0.25
    assert score_c == 5.0   # 10 * 0.50
    assert score_d == 10.0  # 10 * 1.00
    assert score_a < score_b < score_c < score_d
