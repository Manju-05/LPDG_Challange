#!/usr/bin/env python3
"""One-command runner for LPDG Selection Challenge 2026 — Part 1.

Usage:
    python run.py --data data --out predictions.csv
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from src.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LPDG Part 1: Field Visit Prioritization Pipeline"
    )
    here = pathlib.Path(__file__).resolve().parent
    default_data = here / "data"

    parser.add_argument(
        "--data",
        type=pathlib.Path,
        default=default_data,
        help="Path to directory containing input datasets (default: ./data)",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=here / "predictions.csv",
        help="Path for destination predictions CSV (default: ./predictions.csv)",
    )

    args = parser.parse_args(argv)

    if not args.data.exists():
        print(f"Error: Data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    try:
        run_pipeline(data_dir=args.data, output_path=args.out)
        return 0
    except Exception as exc:
        print(f"Pipeline execution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
