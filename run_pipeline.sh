#!/usr/bin/env bash
# Full refresh: collect -> compute -> monitor datasets -> dashboard datasets.
# Needs FRED_API_KEY in the environment (or a .env file in the repo root).
set -euo pipefail
cd "$(dirname "$0")"
# A failing source is reported but does not stop the run: the last good values stay in the store.
python3 src/collect.py || echo "WARNING: some sources failed (see ERRORS above); continuing with stored data"
python3 src/compute.py
(cd src && python3 monitor.py)
python3 src/export_dashboard.py
(cd src && python3 extras.py)
echo "Pipeline finished. Dashboard datasets are in data/outputs/dash/"
