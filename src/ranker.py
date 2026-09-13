"""Deterministic ranking engine with swappable ranker interfaces."""

from __future__ import annotations

import abc
import datetime as dt
import pandas as pd

from src.config import VISITS_PER_WEEK
from src.reason_generator import build_reason


class BaseRanker(abc.ABC):
    """Abstract base class defining the ranking interface."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the ranking strategy."""
        raise NotImplementedError

    @abc.abstractmethod
    def rank_week(
        self,
        monday: dt.date,
        features: pd.DataFrame,
        recent_visits: dict[str, int],
        week_idx: int,
    ) -> tuple[pd.DataFrame, list[str]]:
        """Rank gateways for the given week and return (ranked_dataframe, selected_gateway_ids)."""
        raise NotImplementedError


class CompositeRanker(BaseRanker):
    """Multi-source operational risk ranker with episode cooldown discount."""

    @property
    def name(self) -> str:
        return "composite_multi_source"

    def rank_week(
        self,
        monday: dt.date,
        features: pd.DataFrame,
        recent_visits: dict[str, int],
        week_idx: int,
    ) -> tuple[pd.DataFrame, list[str]]:
        scored = compute_composite_score(features, recent_visits, week_idx)

        # Deterministic sorting: score DESC, then gateway_id ASC
        sorted_df = scored.sort_values(
            by=["score", "gateway_id"], ascending=[False, True]
        ).reset_index(drop=True)

        top_15 = sorted_df.head(VISITS_PER_WEEK).copy()
        if len(top_15) < VISITS_PER_WEEK:
            raise ValueError(f"Fewer than {VISITS_PER_WEEK} gateways available for week {monday}")

        top_15["rank"] = range(1, VISITS_PER_WEEK + 1)
        top_15["week_start"] = monday.isoformat()
        top_15["reason"] = top_15.apply(build_reason, axis=1)

        result_cols = ["week_start", "rank", "gateway_id", "score", "reason"]
        return top_15[result_cols], top_15["gateway_id"].tolist()


class Baseline3SigmaRanker(BaseRanker):
    """Reference ranker replicating standard 3-sigma anomaly ranking."""

    @property
    def name(self) -> str:
        return "baseline_3sigma"

    def rank_week(
        self,
        monday: dt.date,
        features: pd.DataFrame,
        recent_visits: dict[str, int],
        week_idx: int,
    ) -> tuple[pd.DataFrame, list[str]]:
        df = features.copy()
        df["score"] = df["flagged_hours"].astype(float)

        sorted_df = df.sort_values(
            by=["score", "gateway_id"], ascending=[False, True]
        ).reset_index(drop=True)

        top_15 = sorted_df.head(VISITS_PER_WEEK).copy()
        if len(top_15) < VISITS_PER_WEEK:
            raise ValueError(f"Fewer than {VISITS_PER_WEEK} gateways available for week {monday}")

        top_15["rank"] = range(1, VISITS_PER_WEEK + 1)
        top_15["week_start"] = monday.isoformat()

        # Build baseline-style reasons
        def _baseline_reason(r: pd.Series) -> str:
            worst = r.get("worst_metric", "") or "telemetry"
            fl = int(r.get("flagged_hours", 0))
            return f"{fl} hour(s) beyond 3 sigma of 28-day baseline; breach on {worst}"

        top_15["reason"] = top_15.apply(_baseline_reason, axis=1)
        result_cols = ["week_start", "rank", "gateway_id", "score", "reason"]
        return top_15[result_cols], top_15["gateway_id"].tolist()


# Registry for swappable rankers
RANKER_REGISTRY: dict[str, type[BaseRanker]] = {
    "composite": CompositeRanker,
    "baseline": Baseline3SigmaRanker,
}


def get_ranker(ranker_type: str = "composite") -> BaseRanker:
    """Factory function to retrieve a ranker instance by name."""
    cls = RANKER_REGISTRY.get(ranker_type.lower())
    if cls is None:
        raise ValueError(
            f"Unknown ranker '{ranker_type}'. Available: {list(RANKER_REGISTRY.keys())}"
        )
    return cls()


def compute_composite_score(
    features: pd.DataFrame,
    recent_visits: dict[str, int],
    current_week_idx: int,
) -> pd.DataFrame:
    """Calculate operational risk score for each gateway incorporating multi-source signals and episode cooldown."""
    df = features.copy()

    base_score = df["flagged_hours"].astype(float)
    offline_component = 0.5 * df["offline_hours"].clip(upper=48.0)
    meter_loss_component = 10.0 * df["meter_fail_rate"]
    silence_component = 0.05 * df["silent_hours"]
    expert_component = 2.0 * df["expert_schlecht"]

    raw_score = base_score + offline_component + meter_loss_component + silence_component + expert_component

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
    """Legacy helper forwarding to the default CompositeRanker."""
    return CompositeRanker().rank_week(monday, features, recent_visits, week_idx)
