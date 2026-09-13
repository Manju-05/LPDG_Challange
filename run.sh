#!/usr/bin/env bash
# One-command execution script for LPDG Part 1 Pipeline
set -e

DATA_DIR="${1:-data}"
OUT_FILE="${2:-predictions.csv}"

echo "Executing LPDG Field Visit Prioritization Pipeline..."
python3 run.py --data "$DATA_DIR" --out "$OUT_FILE"
python3 validate_submission.py "$OUT_FILE"
