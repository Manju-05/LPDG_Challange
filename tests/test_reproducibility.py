"""Test for deterministic and reproducible execution across repeated pipeline runs."""

from __future__ import annotations

import pathlib
import pandas as pd

from src.pipeline import run_pipeline


def test_pipeline_reproducibility(tmp_path: pathlib.Path) -> None:
    """Running the pipeline twice with identical inputs must produce bit-for-bit identical predictions."""
    out1 = tmp_path / "predictions_run1.csv"
    out2 = tmp_path / "predictions_run2.csv"

    data_dir = pathlib.Path("data")

    df1 = run_pipeline(data_dir, out1)
    df2 = run_pipeline(data_dir, out2)

    pd.testing.assert_frame_equal(df1, df2)

    with open(out1, "r", encoding="utf-8") as f1, open(out2, "r", encoding="utf-8") as f2:
        assert f1.read() == f2.read(), "Predictions CSV text differs between consecutive runs"
