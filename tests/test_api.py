"""Integration and unit tests for FastAPI REST API endpoints (Track B)."""

from __future__ import annotations

import datetime as dt
import pathlib
from fastapi.testclient import TestClient
import pandas as pd
import pytest

import src.api
from src.api import app

client = TestClient(app)


def test_api_health_endpoint() -> None:
    """Verify that /health reports liveness, version, and supported algorithms."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "composite" in data["available_rankers"]
    assert "baseline" in data["available_rankers"]
    assert len(data["available_weeks"]) == 8


def test_api_fleet_summary_endpoint() -> None:
    """Verify that /fleet/summary returns fleet-wide operational health statistics."""
    response = client.get("/fleet/summary?week=2026-02-02")
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-02-02"
    assert data["total_gateways_monitored"] > 0
    assert data["recommended_visits_count"] == 15
    assert "gateways_with_3sigma_breaches" in data
    assert "silent_gateways_count" in data


def test_api_get_rankings_default() -> None:
    """Verify that /rankings returns top 15 gateways for the default week."""
    response = client.get("/rankings")
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-02-02"
    assert data["total_ranked"] == 15
    assert len(data["rankings"]) == 15
    ranks = [item["rank"] for item in data["rankings"]]
    assert ranks == list(range(1, 16))


def test_api_get_rankings_with_latest_keyword() -> None:
    """Verify that /rankings accepts ?week=latest and returns the latest evaluation week."""
    response = client.get("/rankings?week=latest")
    assert response.status_code == 200
    data = response.json()
    assert data["week_start"] == "2026-03-23"
    assert data["total_ranked"] == 15


def test_api_get_rankings_latest_dynamic_with_unseen_partition(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live Session Test: ?week=latest dynamically discovers new April 2026 partitions on disk."""
    mock_data = tmp_path / "mock_live_data"
    mock_data.mkdir()
    tel_dir = mock_data / "telemetry"
    tel_dir.mkdir()

    gateways = [f"0A{i:010X}" for i in range(1, 21)]
    master_df = pd.DataFrame({
        "gateway_id": gateways,
        "n_meters_installed": [100] * 20,
        "installed_on": ["2024-01-01"] * 20,
        "decommissioned_on": [None] * 20,
    })
    master_df.to_csv(mock_data / "gateway_master.csv", index=False)

    # Telemetry spanning into Monday April 13, 2026
    april_timestamps = [
        (pd.Timestamp("2026-04-13 12:00:00", tz="UTC") - dt.timedelta(hours=h)).isoformat()
        for h in range(168)
    ]
    records = []
    for gw in gateways:
        for ts in april_timestamps:
            records.append({
                "gateway_id": gw,
                "ts_utc": ts,
                "offline_duration_sec": 0,
                "disconnection_cnt": 0,
                "reboot_cnt": 0,
            })
    pd.DataFrame(records).to_parquet(tel_dir / "month=2026-04.parquet")

    monkeypatch.setattr(src.api, "DEFAULT_DATA_DIR", mock_data)

    response = client.get("/rankings?week=latest")
    assert response.status_code == 200
    data = response.json()
    # Confirms latest resolved dynamically to 2026-04-13 on disk!
    assert data["week_start"] == "2026-04-13"


def test_api_get_rankings_with_specific_week() -> None:
    """Verify that /rankings accepts any valid ?week= parameter from the 8 scored weeks."""
    for week_str in ["2026-02-02", "2026-02-16", "2026-03-23"]:
        response = client.get(f"/rankings?week={week_str}")
        assert response.status_code == 200
        data = response.json()
        assert data["week_start"] == week_str
        assert data["total_ranked"] == 15


def test_api_get_rankings_with_swappable_ranker() -> None:
    """Verify that /rankings allows seamlessly swapping to the baseline ranker."""
    res_composite = client.get("/rankings?week=2026-02-02&ranker=composite")
    res_baseline = client.get("/rankings?week=2026-02-02&ranker=baseline")

    assert res_composite.status_code == 200
    assert res_baseline.status_code == 200

    data_comp = res_composite.json()
    data_base = res_baseline.json()

    assert data_comp["ranker_type"] == "composite_multi_source"
    assert data_base["ranker_type"] == "baseline_3sigma"
    assert len(data_comp["rankings"]) == 15
    assert len(data_base["rankings"]) == 15


def test_api_get_rankings_invalid_ranker_name() -> None:
    """Verify that passing an unregistered ranker name returns HTTP 400 Bad Request."""
    response = client.get("/rankings?ranker=invalid_algorithm")
    assert response.status_code == 400
    assert "Unknown ranker" in response.json()["detail"]


def test_api_get_rankings_invalid_date_format() -> None:
    """Verify that invalid date formats trigger an HTTP 400 with a clear error message."""
    response = client.get("/rankings?week=invalid-date")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


def test_api_get_rankings_non_monday_date() -> None:
    """Verify that non-Monday dates trigger HTTP 400 explaining Monday dispatch convention."""
    response = client.get("/rankings?week=2026-02-04")  # Wednesday
    assert response.status_code == 400
    assert "is a Wednesday" in response.json()["detail"]
    assert "strictly operates on Mondays" in response.json()["detail"]


def test_api_get_rankings_preceding_telemetry_history() -> None:
    """Verify that dates far in the past before telemetry observations return HTTP 400."""
    response = client.get("/rankings?week=2020-01-06")
    assert response.status_code == 400
    assert "precedes available telemetry history" in response.json()["detail"]


def test_api_gateway_detail_success() -> None:
    """Verify /gateways/{id} returns detailed diagnostics and ranking metrics."""
    known_id = "0A2778A31BE3"
    response = client.get(f"/gateways/{known_id}?week=2026-02-02")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == known_id
    assert data["week_start"] == "2026-02-02"
    assert "metrics" in data
    assert "flagged_hours_3sigma" in data["metrics"]
    assert "total_offline_hours" in data["metrics"]


def test_api_gateway_history_endpoint() -> None:
    """Verify /gateways/{id}/history returns multi-week chronological snapshots."""
    known_id = "0A2778A31BE3"
    response = client.get(f"/gateways/{known_id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["gateway_id"] == known_id
    assert data["weeks_evaluated"] == 8
    assert len(data["history"]) == 8
    assert data["history"][0]["week_start"] == "2026-02-02"


def test_api_gateway_detail_not_found() -> None:
    """Verify /gateways/{id} returns HTTP 404 for non-existent gateways."""
    response = client.get("/gateways/FFFFFFFFFFFF?week=2026-02-02")
    assert response.status_code == 404
    assert "not found in network registry" in response.json()["detail"]


def test_api_bug_driven_case_and_colon_normalization() -> None:
    """Bug-driven regression test: Ensure colon-formatted and lowercase IDs resolve identically."""
    bare_upper = "0A2778A31BE3"
    colon_lower = "0a:27:78:a3:1b:e3"

    res1 = client.get(f"/gateways/{bare_upper}?week=2026-02-02")
    res2 = client.get(f"/gateways/{colon_lower}?week=2026-02-02")

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["gateway_id"] == res2.json()["gateway_id"] == bare_upper
    assert res1.json()["metrics"] == res2.json()["metrics"]


def test_api_trigger_run_pipeline(tmp_path: pathlib.Path) -> None:
    """Verify /run triggers the pipeline and generates output without service restart."""
    out_file = tmp_path / "api_predictions.csv"
    response = client.post(f"/run?out={out_file}&ranker=composite")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["rows_generated"] == 120
    assert data["weeks_processed"] == 8
    assert out_file.exists()


def test_api_run_freshness_picks_up_new_data_on_disk(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FAQ 6.5 Live Session Test: Dropping fresh data on disk is picked up by /run without restarting service."""
    mock_data = tmp_path / "mock_data"
    mock_data.mkdir()
    tel_dir = mock_data / "telemetry"
    tel_dir.mkdir()

    gateways = [f"0A{i:010X}" for i in range(1, 21)]
    master_df = pd.DataFrame({
        "gateway_id": gateways,
        "n_meters_installed": [100] * 20,
        "installed_on": ["2024-01-01"] * 20,
        "decommissioned_on": [None] * 20,
    })
    master_df.to_csv(mock_data / "gateway_master.csv", index=False)

    timestamps = [
        (pd.Timestamp("2026-02-02", tz="UTC") - dt.timedelta(hours=h)).isoformat()
        for h in range(1, 169)
    ]
    base_records = []
    for gw in gateways:
        for ts in timestamps:
            base_records.append({
                "gateway_id": gw,
                "ts_utc": ts,
                "offline_duration_sec": 0,
                "disconnection_cnt": 0,
                "reboot_cnt": 0,
            })
    pd.DataFrame(base_records).to_parquet(tel_dir / "batch_1.parquet")

    monkeypatch.setattr(src.api, "DEFAULT_DATA_DIR", mock_data)

    out_1 = tmp_path / "preds_1.csv"
    res1 = client.post(f"/run?out={out_1}")
    assert res1.status_code == 200
    df1 = pd.read_csv(out_1)
    top_gw_1 = df1.iloc[0]["gateway_id"]

    # Drop new month data while service is running
    spike_records = [
        {
            "gateway_id": "0A0000000014",
            "ts_utc": ts,
            "offline_duration_sec": 3600,
            "disconnection_cnt": 50,
            "reboot_cnt": 5,
        }
        for ts in timestamps[:150]
    ]
    pd.DataFrame(spike_records).to_parquet(tel_dir / "fresh_drop_batch_2.parquet")

    out_2 = tmp_path / "preds_2.csv"
    res2 = client.post(f"/run?out={out_2}")
    assert res2.status_code == 200
    df2 = pd.read_csv(out_2)
    top_gw_2 = df2.iloc[0]["gateway_id"]

    assert top_gw_2 == "0A0000000014"
    assert top_gw_2 != top_gw_1


def test_api_trigger_run_pipeline_default_path() -> None:
    """Verify POST /run with no parameters writes to canonical predictions.csv and passes validation."""
    from validate_submission import validate

    response = client.post("/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["rows_generated"] == 120
    assert data["weeks_processed"] == 8
    assert data["output_path"] == "predictions.csv"

    default_out = pathlib.Path("predictions.csv")
    assert default_out.exists()
    problems = validate(default_out)
    assert problems == [], f"Validation errors found in generated predictions.csv: {problems}"

