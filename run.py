#!/usr/bin/env python3
"""One-command runner & API server for LPDG Selection Challenge 2026.

Usage:
    Batch Mode:
        python run.py --data data --out predictions.csv

    Server Mode (REST API):
        python run.py --serve --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from src.pipeline import run_pipeline
from src.ranker import get_ranker


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LPDG Part 1 & Part 2 (Track B): Field Visit Prioritization & REST API"
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
    parser.add_argument(
        "--ranker",
        type=str,
        default="composite",
        choices=["composite", "baseline"],
        help="Ranking algorithm to use ('composite' or 'baseline', default: composite)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the FastAPI REST web service instead of running batch mode",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address for the REST API server (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for the REST API server (default: 8000)",
    )

    args = parser.parse_args(argv)

    if args.serve:
        try:
            import uvicorn
            from src.api import app

            print(f"Starting LPDG REST API server on http://{args.host}:{args.port}...")
            print(f"Interactive Swagger documentation available at: http://{args.host}:{args.port}/docs")
            uvicorn.run(app, host=args.host, port=args.port, log_level="info")
            return 0
        except ImportError:
            print("Error: 'uvicorn' is required to run the API server. Install with: pip install uvicorn", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Server execution failed: {exc}", file=sys.stderr)
            return 1

    if not args.data.exists():
        print(f"Error: Data directory does not exist: {args.data}", file=sys.stderr)
        return 1

    try:
        ranker_instance = get_ranker(args.ranker)
        run_pipeline(
            data_dir=args.data,
            output_path=args.out,
            ranker=ranker_instance,
        )
        return 0
    except Exception as exc:
        print(f"Pipeline execution failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
