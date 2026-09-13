"""Deterministic ranking engine and operational score calculation."""

from __future__ import annotations

import datetime as dt
import pandas as pd

from src.config import VISITS_PER_WEEK
from src.reason_generator import build_reason


def compute_composite_score(
    features: pd.DataFrame,
    recent_visits: dict[str, int],
    current_week_idx: int,
) -> pd.DataFrame:
    """Calculate operational risk score for each gateway incorporating multi-source signals and episode cooldown."""
    df = features.copy()

    # 1. Base 3-sigma telemetry anomaly hours
    base_score = df["flagged_hours"].astype(float)

    # 2. Additive operational risk factors
    offline_component = 0.5 * df["offline_hours"].clip(upper=48.0)
    meter_loss_component = 10.0 * df["meter_fail_rate"]
    silence_component = 0.05 * df["silent_hours"]
    expert_component = 2.0 * df["expert_schlecht"]

    raw_score = base_score + offline_component + meter_loss_component + silence_component + expert_component

    # 3. Episode cooldown: if visited in the immediately preceding week, penalize to avoid wasting 15-visit quota
    cooldown_multiplier = df["gateway_id"].map(
        lambda gid: 0.2 if (gid in recent_visits and (current_week_idx - recent_visits[gid]) <= 1) else 1.0
    )

    df["score"] = raw_score * cooldown_multiplier
    return df


def rank_gateways_for_week(
    monday: dt.date,
    features: pd.DataFrame,
    recent_visits: dict[str, int],
    week_idx: int,
) -> tuple[pd.DataFrame, list[str]]:
    """Rank gateways deterministically and return top 15 rows with reasons and visited IDs."""
    scored = compute_composite_score(features, recent_visits, week_idx)

    # Deterministic sorting: score DESC, then gateway_id ASC
    sorted_df = scored.sort_values(by=["score", "gateway_id"], ascending=[False, True]).reset_index(drop=True)

    top_15 = sorted_df.head(VISITS_PER_WEEK).copy()

    # If fewer than 15, ensure 15 rows
    if len(top_15) < VISITS_PER_WEEK:
        raise ValueError(f"Fewer than {VISITS_PER_WEEK} gateways available for week {monday}")

    # Assign ranks 1 to 15
    top_15["rank"] = range(1, VISITS_PER_WEEK + 1)
    top_15["week_start"] = monday.isoformat()
    top_15["reason"] = top_15.apply(build_reason, axis=1)

    result_cols = ["week_start", "rank", "gateway_id", "score", "reason"]
    selected_ids = top_15["gateway_id"].tolist()

    return top_15[result_cols], selected_ids
