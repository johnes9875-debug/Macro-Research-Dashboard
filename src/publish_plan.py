"""Build the dashboard dataset updates after a refresh.

Usage: python src/publish_plan.py uploads.json out_dir
  uploads.json = {"<dataset id>": "<32-hex asset id>", ...}  (from the asset uploads)
Writes out_dir/<dataset id>.json with the fields to merge into datasets/<id>:
a new file source, updated time, schedule and staleness window.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load((ROOT / "config" / "dashboard.yaml").read_text())
uploads = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for ds in cfg["datasets"]:
    aid = uploads.get(ds)
    if not aid or not re.fullmatch(r"[0-9a-f]{32}", aid):
        print(f"skip {ds}: no valid upload")
        continue
    doc = {
        "source": {"kind": "file", "url": f"/_blob/{aid}", "name": f"{ds}.json"},
        "updated": {"at": now, "by": "Scheduled refresh (rates-monitor)"},
        "schedule": "Refreshed twice daily by a scheduled task: 06:00 SGT Tue–Sat and 23:00 SGT Mon–Fri, from official public sources.",
        "staleAfterHours": 60,
    }
    (out / f"{ds}.json").write_text(json.dumps(doc))
    print(f"ok   {ds}")
