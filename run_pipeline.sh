#!/usr/bin/env bash
# Full refresh: collect -> compute -> monitor datasets -> dashboard datasets.
# Needs FRED_API_KEY in the environment (or a .env file in the repo root).
set -euo pipefail
cd "$(dirname "$0")"
python3 src/collect.py
python3 src/compute.py
(cd src && python3 monitor.py)
python3 src/export_dashboard.py
echo "Pipeline finished. Dashboard datasets are in data/outputs/dash/"
