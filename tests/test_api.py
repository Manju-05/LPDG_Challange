"""Integration and unit tests for FastAPI REST API endpoints (Track B)."""

from __future__ import annotations

import pathlib
from fastapi.testclient import TestClient
import pytest

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


def test_api_get_rankings_invalid_date_format() -> None:
    """Verify that invalid date formats trigger an HTTP 400 with a clear error message."""
    response = client.get("/rankings?week=invalid-date")
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


def test_api_get_rankings_out_of_window() -> None:
    """Verify that dates outside the scored evaluation window trigger HTTP 400."""
    response = client.get("/rankings?week=2025-05-01")
    assert response.status_code == 400
    assert "not in the scored evaluation window" in response.json()["detail"]


def test_api_gateway_detail_success() -> None:
    """Verify /gateways/{id} returns detailed diagnostics and ranking metrics."""
    # Gateway known to exist in telemetry
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
    # Test variation formats for the same gateway
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
