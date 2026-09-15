"""Feature extraction engine with strict temporal cutoff enforcement."""

from __future__ import annotations

import datetime as dt
import numpy as np
import pandas as pd

from src.config import (
    ANOMALY_METRICS,
    BASELINE_DAYS,
    ENGINEER_REVIEW_DATE,
    RECENT_DAYS,
    SIGMA_THRESHOLD,
)


def extract_features_for_week(
    monday: dt.date,
    telemetry: pd.DataFrame,
    gateway_master: pd.DataFrame,
    meter_reads: pd.DataFrame,
    engineer_review: pd.DataFrame,
) -> pd.DataFrame:
    """Extract operational risk features strictly using data available before Monday 00:00 UTC."""
    end_utc = pd.Timestamp(monday, tz="UTC")
    baseline_start = end_utc - dt.timedelta(days=BASELINE_DAYS)
    recent_start = end_utc - dt.timedelta(days=RECENT_DAYS)

    # 1. Telemetry slice strictly in [Monday - 28d, Monday)
    telemetry_window = telemetry[
        (telemetry["ts"] >= baseline_start) & (telemetry["ts"] < end_utc)
    ]

    # Get master list of all in-service gateways for this week
    m_ts = pd.Timestamp(monday)
    if not gateway_master.empty and "gateway_id" in gateway_master.columns:
        cols = [c for c in ["gateway_id", "n_meters_installed", "installed_on", "decommissioned_on"] if c in gateway_master.columns]
        all_gateways = gateway_master[cols].copy()
        if "n_meters_installed" not in all_gateways.columns:
            all_gateways["n_meters_installed"] = 100

        # Filter strictly for gateways in-service on this Monday:
        # 1. Commissioned/installed on or before this Monday
        # 2. Not decommissioned before this Monday
        in_service_mask = pd.Series(True, index=all_gateways.index)
        if "installed_on" in all_gateways.columns:
            inst_ts = pd.to_datetime(all_gateways["installed_on"], errors="coerce")
            in_service_mask = in_service_mask & (inst_ts.isna() | (inst_ts <= m_ts))
        if "decommissioned_on" in all_gateways.columns:
            decom_ts = pd.to_datetime(all_gateways["decommissioned_on"], errors="coerce")
            in_service_mask = in_service_mask & (decom_ts.isna() | (decom_ts >= m_ts))

        all_gateways = all_gateways[in_service_mask].copy()
    else:
        unique_gws = telemetry_window["gateway_id"].unique()
        all_gateways = pd.DataFrame({
            "gateway_id": unique_gws,
            "n_meters_installed": 100,
        })

    # Telemetry baseline stats per gateway
    stats = telemetry_window.groupby("gateway_id")[ANOMALY_METRICS].agg(["mean", "std"])

    # Recent 7-day window [Monday - 7d, Monday)
    recent = telemetry_window[telemetry_window["ts"] >= recent_start].copy()

    # Per-hour 3-sigma anomaly detection
    flags = pd.Series(0, index=recent.index, dtype=int)
    worst = pd.Series("", index=recent.index, dtype=object)

    for metric in ANOMALY_METRICS:
        if (metric, "mean") in stats.columns and (metric, "std") in stats.columns:
            mean = recent["gateway_id"].map(stats[(metric, "mean")])
            std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
            exceeded = (recent[metric] - mean) > SIGMA_THRESHOLD * std
            exceeded = exceeded.fillna(False)
            flags = flags + exceeded.astype(int)
            worst = worst.where(~exceeded | (worst != ""), metric)

    recent["flagged"] = flags
    recent["worst_metric"] = worst

    # Aggregations for recent 7 days
    tel_agg = recent.groupby("gateway_id").agg(
        reported_hours=("flagged", "count"),
        flagged_hours=("flagged", "sum"),
        worst_metric=("worst_metric", lambda s: next((v for v in s if v), "")),
        total_offline_sec=("offline_duration_sec", "sum"),
        total_disconnects=("disconnection_cnt", "sum"),
        total_reboots=("reboot_cnt", "sum"),
    ).reset_index()

    # Merge with master list of all active gateways
    features = all_gateways.merge(tel_agg, on="gateway_id", how="left")
    features["reported_hours"] = features["reported_hours"].fillna(0).astype(int)
    features["flagged_hours"] = features["flagged_hours"].fillna(0).astype(int)
    features["worst_metric"] = features["worst_metric"].fillna("")
    features["total_offline_sec"] = features["total_offline_sec"].fillna(0.0)
    features["total_disconnects"] = features["total_disconnects"].fillna(0.0)
    features["total_reboots"] = features["total_reboots"].fillna(0.0)
    features["offline_hours"] = features["total_offline_sec"] / 3600.0

    # Silence indicator: 168 hours in 7 days
    features["silent_hours"] = np.maximum(0, 168 - features["reported_hours"])

    # 2. Meter read success (strictly before Monday with staleness discount)
    if not meter_reads.empty:
        prior_reads = meter_reads[meter_reads["week_date"] < monday].copy()
        if not prior_reads.empty:
            # Sort by week_date descending to pick the most recent available week
            latest_reads = prior_reads.sort_values("week_date", ascending=False).groupby("gateway_id").first().reset_index()
            raw_fail_rate = 1.0 - (
                latest_reads["meters_read"] / latest_reads["meters_expected"].clip(lower=1)
            ).clip(lower=0.0, upper=1.0)

            # Exponential staleness decay: as weeks elapse since last meter read report (2026-01-26),
            # decay reliance on stale report so fresh telemetry carries higher weight
            days_diff = (monday - latest_reads["week_date"]).apply(lambda d: d.days if hasattr(d, "days") else int(d))
            weeks_lag = np.maximum(0, (days_diff // 7) - 1)
            staleness_factor = 0.8 ** weeks_lag
            latest_reads["meter_fail_rate"] = raw_fail_rate * staleness_factor

            features = features.merge(
                latest_reads[["gateway_id", "meter_fail_rate", "meters_expected", "meters_read"]],
                on="gateway_id",
                how="left",
            )
            features["meter_fail_rate"] = features["meter_fail_rate"].fillna(0.0)
            features["meters_expected"] = features["meters_expected"].fillna(features["n_meters_installed"])
            features["meters_read"] = features["meters_read"].fillna(features["meters_expected"])
        else:
            features["meter_fail_rate"] = 0.0
            features["meters_expected"] = features["n_meters_installed"]
            features["meters_read"] = features["n_meters_installed"]
    else:
        features["meter_fail_rate"] = 0.0
        features["meters_expected"] = features["n_meters_installed"]
        features["meters_read"] = features["n_meters_installed"]

    # 3. Engineer review (strictly available ONLY on/after 2026-02-16)
    if monday >= ENGINEER_REVIEW_DATE and not engineer_review.empty:
        review_slice = engineer_review[["gateway_id", "Kategorie"]].copy()
        review_slice["expert_schlecht"] = (review_slice["Kategorie"].str.strip() == "Schlecht").astype(int)
        features = features.merge(review_slice[["gateway_id", "expert_schlecht"]], on="gateway_id", how="left")
        features["expert_schlecht"] = features["expert_schlecht"].fillna(0).astype(int)
    else:
        features["expert_schlecht"] = 0

    return features
