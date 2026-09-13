"""Tests verifying the BaseRanker interface and swappable ranker implementations."""

from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.ranker import (
    BaseRanker,
    Baseline3SigmaRanker,
    CompositeRanker,
    get_ranker,
)


def _build_dummy_features() -> pd.DataFrame:
    gateways = [f"0A{i:010X}" for i in range(1, 20)]
    return pd.DataFrame({
        "gateway_id": gateways,
        "n_meters_installed": [100] * len(gateways),
        "flagged_hours": list(range(len(gateways), 0, -1)),
        "worst_metric": ["offline_duration_sec"] * len(gateways),
        "offline_hours": [float(i) for i in range(len(gateways))],
        "total_disconnects": [i * 2 for i in range(len(gateways))],
        "total_reboots": [i for i in range(len(gateways))],
        "silent_hours": [0] * len(gateways),
        "meter_fail_rate": [0.1] * len(gateways),
        "expert_schlecht": [0] * len(gateways),
    })


def test_ranker_interface_conformance() -> None:
    """Verify that CompositeRanker and Baseline3SigmaRanker adhere to BaseRanker interface."""
    composite = get_ranker("composite")
    baseline = get_ranker("baseline")

    assert isinstance(composite, BaseRanker)
    assert isinstance(baseline, BaseRanker)
    assert composite.name == "composite_multi_source"
    assert baseline.name == "baseline_3sigma"


def test_swapping_rankers_produces_valid_output() -> None:
    """Verify that both rankers produce 15 rows with ranks 1..15 and valid columns."""
    monday = dt.date(2026, 2, 2)
    features = _build_dummy_features()

    for ranker_name in ["composite", "baseline"]:
        ranker = get_ranker(ranker_name)
        ranked_df, selected_ids = ranker.rank_week(
            monday=monday,
            features=features,
            recent_visits={},
            week_idx=0,
        )

        assert len(ranked_df) == 15
        assert len(selected_ids) == 15
        assert ranked_df["rank"].tolist() == list(range(1, 16))
        assert list(ranked_df.columns) == ["week_start", "rank", "gateway_id", "score", "reason"]
        assert all(len(r) > 0 for r in ranked_df["reason"])


def test_unknown_ranker_raises_value_error() -> None:
    """Factory should raise ValueError for unregistered ranker names."""
    with pytest.raises(ValueError, match="Unknown ranker"):
        get_ranker("non_existent_ranker")
