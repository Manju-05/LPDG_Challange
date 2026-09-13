"""Data loading and normalization utilities for LPDG challenge datasets."""

from __future__ import annotations

import datetime as dt
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from src.config import ANOMALY_METRICS

_BARE = re.compile(r"^[0-9A-Fa-f]{12}$")
_COLON = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def normalize_gateway_id(value: str | int | float | None) -> str:
    """Normalize gateway identifier to 12 uppercase hex characters."""
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if _BARE.match(text):
        return text.upper()
    if _COLON.match(text):
        return text.replace(":", "").upper()
    # Fallback strip of colon/hyphen/spaces
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", text)
    if len(cleaned) == 12:
        return cleaned.upper()
    return text.upper()


def load_telemetry(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load hourly telemetry parquet files and parse timestamps as UTC."""
    telemetry_path = data_dir / "telemetry"
    columns = ["gateway_id", "ts_utc", *ANOMALY_METRICS]
    frame = pd.read_parquet(telemetry_path, columns=columns)
    frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    return frame.drop(columns=["ts_utc"])


def load_gateway_master(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load gateway master registry with latin1 encoding support."""
    path = data_dir / "gateway_master.csv"
    if not path.exists():
        return pd.DataFrame(columns=["gateway_id", "tenant", "site_type", "region", "n_meters_installed"])
    frame = pd.read_csv(path, encoding="latin1")
    frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
    return frame


def load_meter_reads(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load weekly meter read success records."""
    path = data_dir / "meter_read_success.csv"
    if not path.exists():
        return pd.DataFrame(columns=["week_start", "gateway_id", "meters_expected", "meters_read"])
    frame = pd.read_csv(path, encoding="latin1")
    frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
    frame["week_date"] = pd.to_datetime(frame["week_start"]).dt.date
    return frame


def load_field_visits(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load historic work orders and field visit records."""
    path = data_dir / "field_visits.csv"
    if not path.exists():
        return pd.DataFrame(columns=["visit_id", "gateway_id", "requested_on", "visited_on", "outcome"])
    frame = pd.read_csv(path, encoding="latin1")
    frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
    frame["visited_date"] = pd.to_datetime(frame["visited_on"], errors="coerce").dt.date
    return frame


def load_engineer_review(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load engineer review spreadsheet with zero-dependency fallback."""
    path = data_dir / "engineer_review_2026-02.xlsx"
    if not path.exists():
        return pd.DataFrame(columns=["gateway_id", "Kategorie", "reviewed_on", "Bemerkung"])

    # Try standard openpyxl first if installed
    try:
        frame = pd.read_excel(path)
        frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
        return frame
    except Exception:
        pass

    # Zero-dependency XML parser for .xlsx
    try:
        with zipfile.ZipFile(path) as z:
            sheet_tree = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            rows_data: list[list[str]] = []
            for r in sheet_tree.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                row_vals: list[str] = []
                for c in r.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                    is_elem = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
                    v_elem = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    val = ""
                    if is_elem is not None:
                        val = "".join(is_elem.itertext())
                    elif v_elem is not None:
                        val = v_elem.text or ""
                    row_vals.append(val)
                if row_vals:
                    rows_data.append(row_vals)

            if len(rows_data) > 1:
                cols = rows_data[0]
                frame = pd.DataFrame(rows_data[1:], columns=cols)
                if "gateway_id" in frame.columns:
                    frame["gateway_id"] = frame["gateway_id"].apply(normalize_gateway_id)
                return frame
    except Exception:
        pass

    return pd.DataFrame(columns=["gateway_id", "Kategorie", "reviewed_on", "Bemerkung"])
