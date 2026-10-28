"""Flatten data/outputs/dashboard.json into row-object JSON datasets for the dashboard page.

Writes data/outputs/dash/<dataset>.json. Values are rounded to the precision the page shows,
so every number on the page matches its dataset exactly.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = json.loads((ROOT / "data" / "outputs" / "dashboard.json").read_text())
OUT = ROOT / "data" / "outputs" / "dash"
OUT.mkdir(parents=True, exist_ok=True)
ORDER = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "SEK", "NOK", "CNY"]


def rnd(x, n):
    return None if x is None else round(float(x), n)


def write(name: str, rows: list) -> None:
    (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":")))
    print(f"{name:14} {len(rows):6} rows  {(OUT / f'{name}.json').stat().st_size / 1024:7.1f} KB")


E = SRC["economies"]

# 1. overview: one row per economy
overview = []
for c in ORDER:
    e = E[c]
    nm = e["next_meeting"] or {}
    overview.append({
        "economy": c, "cb": e["cb"], "y2_label": e.get("y2_label", "2y"), "policy_label": e["policy"]["label"], "policy": rnd(e["policy"]["value"], 3),
        "policy_date": e["policy"]["date"],
        "y2": rnd(e["y2"]["value"], 2), "y2_chg_1d": rnd(e["y2"]["chg_1d"], 0), "y2_chg_1w": rnd(e["y2"]["chg_1w"], 0),
        "y2_chg_1m": rnd(e["y2"]["chg_1m"], 0), "y2_date": e["y2"]["date"],
        "y10": rnd(e["y10"]["value"], 2), "y10_chg_1d": rnd(e["y10"]["chg_1d"], 0), "y10_chg_1w": rnd(e["y10"]["chg_1w"], 0),
        "y10_chg_1m": rnd(e["y10"]["chg_1m"], 0), "y10_date": e["y10"]["date"],
        "ylong_label": e["ylong"]["label"], "ylong": rnd(e["ylong"]["value"], 2),
        "s2s10s": rnd(e["s2s10s"]["value"], 0), "s2s10s_chg_1w": rnd(e["s2s10s"]["chg_1w"], 0), "s2s10s_chg_1m": rnd(e["s2s10s"]["chg_1m"], 0),
        "priced_label": e["priced_12m"]["label"], "priced_12m_bp": rnd(e["priced_12m"]["vs_policy_bp"], 0),
        "priced_chg_1w_bp": rnd(e["priced_12m"]["chg_1w_bp"], 0),
        "next_meeting": nm.get("date"), "next_meeting_sgt": nm.get("sgt"),
        "days_to_meeting": None if not nm.get("date") else
            (__import__("datetime").date.fromisoformat(str(nm["date"])) - __import__("datetime").date.today()).days,
        "path_quality": e["path_quality"],
    })
write("overview", overview)

# 2. implied path: now and one week earlier
path = []
for c in ORDER:
    e = E[c]
    wk = {p["label"]: p for p in e["path_1w"]}
    for p in e["path"]:
        w = wk.get(p["label"], {})
        path.append({"key": f"{c} {p['label']}", "economy": c, "horizon": p["label"], "months": p["months"],
                     "rate": rnd(p["rate"], 2), "vs_policy_bp": rnd(p["vs_policy_bp"], 0),
                     "vs_policy_bp_1w": rnd(w.get("vs_policy_bp"), 0)})
write("implied_path", path)

# 3. yields history: 2y, 10y, policy (daily, last 2 years)
yh = []
for c in ORDER:
    for series, label in (("policy", "Policy rate"), ("y2", "2y"), ("y10", "10y")):
        for d, v in E[c]["hist"][series]:
            yh.append({"date": d, "economy": c, "series": label, "value": rnd(v, 2)})
write("yields_hist", yh)

# 4. spreads (latest) and 5. spreads history
sp, sph = [], []
for x in SRC["spreads"]:
    sp.append({"name": x["name"], "value_bp": rnd(x["value_bp"], 0), "chg_1w_bp": rnd(x["chg_1w_bp"], 0),
               "chg_1m_bp": rnd(x["chg_1m_bp"], 0), "z_1y": rnd(x["z_1y"], 1),
               "low_1y": rnd(x["range_1y"][0], 0), "high_1y": rnd(x["range_1y"][1], 0), "date": x["date"]})
    for d, v in x["hist"]:
        sph.append({"date": d, "name": x["name"], "value_bp": rnd(v, 0)})
write("spreads", sp)
write("spreads_hist", sph)

# 6. macro latest (inflation, labour, growth)
M = SRC["macro"]
ml = []
for c in ORDER + ["NZD"]:
    inf = M["inflation"].get(c, {"extra": []})
    for nm_key, blk in (("headline_name", "headline"), ("core_name", "core")):
        if inf.get(blk):
            ml.append({"key": f"{c} {inf[nm_key]}", "economy": c, "group": "Inflation", "metric": inf[nm_key],
                       "value": inf[blk]["value"], "prior": inf[blk]["prior"], "period": inf[blk]["period"]})
    for x in inf["extra"]:
        ml.append({"key": f"{c} {x['name']}", "economy": c, "group": "Inflation", "metric": x["name"],
                   "value": x["value"], "prior": x["prior"], "period": x["period"]})
    for x in M["labour"].get(c, []):
        ml.append({"key": f"{c} {x['name']}", "economy": c, "group": "Labour", "metric": x["name"],
                   "value": x["value"], "prior": x["prior"], "period": x["period"]})
    g = M["growth"].get(c)
    if g:
        ml.append({"key": f"{c} {g['name']}", "economy": c, "group": "Growth", "metric": g["name"],
                   "value": g["value"], "prior": g["prior"], "period": g["period"]})
for r in ml:
    r["change"] = None if r["value"] is None or r["prior"] is None else round(r["value"] - r["prior"], 2)
write("macro_latest", ml)

# 7. macro history (monthly, since 2021)
mh = []
for c, v in M["charts"]["inflation"].items():
    for metric in ("headline", "core"):
        for d, val in v[metric]:
            mh.append({"date": d, "economy": c, "metric": "Headline inflation" if metric == "headline" else "Core inflation", "value": rnd(val, 2)})
for c, v in M["charts"]["unemployment"].items():
    for d, val in v:
        mh.append({"date": d, "economy": c, "metric": "Unemployment rate", "value": rnd(val, 2)})
write("macro_hist", mh)

# 8. releases
rel = [{"key": f"{r['economy']} {r['name']}", **{k: r[k] for k in ("economy", "name", "period", "period_iso", "value", "prior", "change")}}
       for r in SRC["releases"]]
write("releases", rel)

# 9. calendar
cal = [{"key": f"{m['cb']} {m['date']}", "date": m["date"], "cb": m["cb"], "economy": m["economy"], "sgt": m["sgt"], "sgt_iso": m.get("sgt_iso")} for m in SRC["calendar"]]
write("calendar", cal)
