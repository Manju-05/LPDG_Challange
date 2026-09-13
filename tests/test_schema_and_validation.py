"""Tests for output schema compliance, synthetic fixtures, and submission validation."""

from __future__ import annotations

import datetime as dt
import pathlib
import pandas as pd

from src.config import SCORED_WEEKS, VISITS_PER_WEEK
from src.features import extract_features_for_week
from src.ranker import rank_gateways_for_week
from validate_submission import validate


def test_synthetic_fixture_ranking() -> None:
    """Validate ranking logic on an isolated synthetic fixture."""
    monday = SCORED_WEEKS[0]
    cutoff_ts = pd.Timestamp(monday, tz="UTC")

    # Build 20 synthetic gateways
    gateways = [f"0A{i:010X}" for i in range(1, 21)]
    telemetry_rows = []

    for i, gid in enumerate(gateways):
        # 168 hours of baseline & recent
        for h in range(1, 24 * 28 + 1):
            ts = cutoff_ts - pd.Timedelta(hours=h)
            # Make first 5 gateways highly anomalous
            is_anom = (i < 5) and (h <= 24 * 7)
            telemetry_rows.append({
                "gateway_id": gid,
                "ts": ts,
                "offline_duration_sec": 3000.0 if is_anom else 10.0,
                "disconnection_cnt": 20 if is_anom else 0,
                "reboot_cnt": 5 if is_anom else 0,
            })

    telemetry = pd.DataFrame(telemetry_rows)
    master = pd.DataFrame({
        "gateway_id": gateways,
        "n_meters_installed": [100] * 20,
    })

    feat = extract_features_for_week(
        monday=monday,
        telemetry=telemetry,
        gateway_master=master,
        meter_reads=pd.DataFrame(),
        engineer_review=pd.DataFrame(),
    )

    ranked_df, selected_ids = rank_gateways_for_week(
        monday=monday,
        features=feat,
        recent_visits={},
        week_idx=0,
    )

    assert len(ranked_df) == VISITS_PER_WEEK
    assert ranked_df["rank"].tolist() == list(range(1, VISITS_PER_WEEK + 1))
    assert all(gid in selected_ids for gid in gateways[:5])
    assert all(len(r) <= 300 for r in ranked_df["reason"])
    assert all(len(r) > 0 for r in ranked_df["reason"])


def test_full_predictions_csv_passes_validator(tmp_path: pathlib.Path) -> None:
    """Ensure the generated predictions.csv passes official validation checks."""
    csv_path = pathlib.Path("predictions.csv")
    if not csv_path.exists():
        from src.pipeline import run_pipeline
        run_pipeline(data_dir=pathlib.Path("data"), output_path=csv_path)

    problems = validate(csv_path)
    assert problems == [], f"Validation problems encountered: {problems}"
