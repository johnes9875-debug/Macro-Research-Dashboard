"""Institutional monitor datasets: change grid, curve snapshots, curve RV, BoE meeting strip, data health.

Writes data/outputs/dash/{rates_grid,curves,curve_rv,boe_meetings,data_health}.json
Run after collect.py (uses data/latest.parquet).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import compute as C  # reuse loaders (s, REG, D)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs" / "dash"
OUT.mkdir(parents=True, exist_ok=True)
s, REG, D = C.s, C.REG, C.D


def rnd(x, n):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n) + 0.0


def write(name, rows):
    (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":")))
    print(f"{name:14} {len(rows):5} rows")


def at_or_before(x: pd.Series, when) -> float | None:
    y = x[x.index <= when].dropna()
    return None if y.empty else float(y.iloc[-1])


def changes(x: pd.Series) -> dict:
    x = x.dropna()
    last_d, last = x.index[-1], float(x.iloc[-1])
    out = {}
    for k, days in (("chg_1d", 1), ("chg_1w", 7), ("chg_1m", 30), ("chg_3m", 91)):
        p = at_or_before(x, last_d - pd.Timedelta(days=days))
        out[k] = None if p is None else rnd((last - p) * 100, 0)
    p = at_or_before(x, pd.Timestamp(f"{last_d.year - 1}-12-31"))
    out["chg_ytd"] = None if p is None else rnd((last - p) * 100, 0)
    yr = x[x.index > last_d - pd.Timedelta(days=365)]
    out["pct_1y"] = rnd((yr < last).mean() * 100, 0)
    out["low_1y"], out["high_1y"] = rnd(yr.min(), 2), rnd(yr.max(), 2)
    out["level"], out["date"] = rnd(last, 2), last_d.strftime("%Y-%m-%d")
    return out


# ------------------------------------------------------------------ 1. rates grid
GRID = [
    ("USD", "Overnight (EFFR)", 0, "US_EFFR"), ("USD", "2y", 2, "US_2Y"), ("USD", "5y", 5, "US_5Y"),
    ("USD", "10y", 10, "US_10Y"), ("USD", "30y", 30, "US_30Y"), ("USD", "10y real (TIPS)", 10.1, "US_10Y_REAL"),
    ("USD", "10y breakeven", 10.2, "US_10Y_BEI"),
    ("EUR", "Overnight (€STR)", 0, "EA_ESTR"), ("EUR", "2y AAA", 2, "EA_2Y"), ("EUR", "5y AAA", 5, "EA_5Y"),
    ("EUR", "10y AAA", 10, "EA_10Y"), ("EUR", "30y AAA", 30, "EA_30Y"),
    ("GBP", "Overnight (SONIA)", 0, "UK_SONIA"), ("GBP", "1y OIS", 1, "UK_OIS_1Y"), ("GBP", "2y OIS", 1.9, "UK_OIS_2Y"),
    ("GBP", "2y gilt", 2, "UK_2Y"), ("GBP", "5y gilt", 5, "UK_5Y"), ("GBP", "10y gilt", 10, "UK_10Y"), ("GBP", "20y gilt", 20, "UK_20Y"),
    ("JPY", "Overnight (call)", 0, "JP_CALL"), ("JPY", "2y JGB", 2, "JP_2Y"), ("JPY", "5y JGB", 5, "JP_5Y"),
    ("JPY", "10y JGB", 10, "JP_10Y"), ("JPY", "30y JGB", 30, "JP_30Y"),
]
grid = []
for eco, label, order, sid in GRID:
    grid.append({"key": f"{eco} {label}", "economy": eco, "instrument": label, "order": order, **changes(s(sid))})
write("rates_grid", grid)

# ------------------------------------------------------------------ 2. curve snapshots
CURVES = {
    "USD": [("1m", 1 / 12, "US_1M"), ("3m", .25, "US_3M"), ("6m", .5, "US_6M"), ("1y", 1, "US_1Y"), ("2y", 2, "US_2Y"),
            ("5y", 5, "US_5Y"), ("10y", 10, "US_10Y"), ("30y", 30, "US_30Y")],
    "EUR": [("3m", .25, "EA_3M"), ("1y", 1, "EA_1Y"), ("2y", 2, "EA_2Y"), ("5y", 5, "EA_5Y"), ("10y", 10, "EA_10Y"), ("30y", 30, "EA_30Y")],
    "GBP": [("2y", 2, "UK_2Y"), ("5y", 5, "UK_5Y"), ("10y", 10, "UK_10Y"), ("20y", 20, "UK_20Y")],
    "JPY": [("1y", 1, "JP_1Y"), ("2y", 2, "JP_2Y"), ("5y", 5, "JP_5Y"), ("10y", 10, "JP_10Y"), ("30y", 30, "JP_30Y")],
}
curves = []
for eco, pts in CURVES.items():
    for label, yrs, sid in pts:
        x = s(sid).dropna()
        d = x.index[-1]
        now, w, m = float(x.iloc[-1]), at_or_before(x, d - pd.Timedelta(days=7)), at_or_before(x, d - pd.Timedelta(days=30))
        curves.append({"key": f"{eco} {label}", "economy": eco, "tenor": label, "years": round(yrs, 4),
                       "now": rnd(now, 2), "wk": rnd(w, 2), "mo": rnd(m, 2),
                       "chg_1w": rnd((now - w) * 100, 0), "chg_1m": rnd((now - m) * 100, 0)})
write("curves", curves)

# ------------------------------------------------------------------ 3. curve RV
RV = {
    "USD": ("US_2Y", "US_5Y", "US_10Y", "US_30Y", "5s30s"),
    "EUR": ("EA_2Y", "EA_5Y", "EA_10Y", "EA_30Y", "5s30s"),
    "GBP": ("UK_2Y", "UK_5Y", "UK_10Y", "UK_20Y", "5s20s"),
    "JPY": ("JP_2Y", "JP_5Y", "JP_10Y", "JP_30Y", "5s30s"),
}
rv = []
for eco, (a2, a5, a10, along, long_label) in RV.items():
    df = pd.concat([s(a2), s(a5), s(a10), s(along)], axis=1, sort=True).dropna()
    df.columns = ["y2", "y5", "y10", "yl"]
    measures = {"2s10s": (df.y10 - df.y2) * 100, long_label: (df.yl - df.y5) * 100,
                "2s5s10s fly": (2 * df.y5 - df.y2 - df.y10) * 100}
    for name, x in measures.items():
        d = x.index[-1]
        yr = x[x.index > d - pd.Timedelta(days=365)]
        rv.append({"key": f"{eco} {name}", "economy": eco, "measure": name, "value_bp": rnd(x.iloc[-1], 0),
                   "chg_1w": rnd(x.iloc[-1] - at_or_before(x, d - pd.Timedelta(days=7)), 0),
                   "chg_1m": rnd(x.iloc[-1] - at_or_before(x, d - pd.Timedelta(days=30)), 0),
                   "z_1y": rnd((x.iloc[-1] - yr.mean()) / yr.std(), 1),
                   "low_1y": rnd(yr.min(), 0), "high_1y": rnd(yr.max(), 0)})
write("curve_rv", rv)

# ------------------------------------------------------------------ 4. BoE meeting strip from OIS forwards
MPC = ["2026-11-05", "2026-12-17", "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-17", "2027-07-29",
       "2027-09-16", "2027-11-04", "2027-12-16"]


def meeting_strip(asof: pd.Timestamp) -> list:
    """Expected Bank Rate after each MPC meeting = average OIS instantaneous forward over the
    period until the next meeting, less the current SONIA–Bank Rate basis."""
    fw = {m: at_or_before(s(f"UK_OIS_FWD_{m:02d}M"), asof) for m in range(1, 25)}
    curve_date = max(s(f"UK_OIS_FWD_01M")[lambda x: x.index <= asof].index)
    months = np.array([0.0] + list(fw.keys()))
    bank = at_or_before(s("UK_BANKRATE"), asof)
    sonia = at_or_before(s("UK_SONIA"), asof)
    basis = sonia - bank  # SONIA prints a little below Bank Rate
    vals = np.array([sonia] + list(fw.values()))
    def fwd(day: pd.Timestamp) -> float:
        mo = (day - curve_date).days / 30.4375
        return float(np.interp(mo, months, vals))
    out, prev = [], bank
    dates = [pd.Timestamp(d) for d in MPC if pd.Timestamp(d) > curve_date]
    for i, d in enumerate(dates):
        end = dates[i + 1] if i + 1 < len(dates) else d + pd.Timedelta(days=45)
        days = pd.date_range(d + pd.Timedelta(days=1), end, freq="D")
        if (days[-1] - curve_date).days / 30.4375 > 24:
            break
        rate = float(np.mean([fwd(x) for x in days])) - basis
        out.append({"date": d.strftime("%Y-%m-%d"), "rate": rate, "chg": (rate - prev) * 100, "cum": (rate - bank) * 100})
        prev = rate
    return out, curve_date


now_strip, cd = meeting_strip(s("UK_OIS_FWD_01M").index[-1])
wk_strip, _ = meeting_strip(cd - pd.Timedelta(days=7))
wk = {r["date"]: r for r in wk_strip}
boe = []
for r in now_strip:
    w = wk.get(r["date"])
    boe.append({"date": r["date"], "implied_rate": rnd(r["rate"], 2), "change_bp": rnd(r["chg"], 1), "cumulative_bp": rnd(r["cum"], 0),
                "hike_odds_pct": rnd(r["chg"] / 25 * 100, 0), "cumulative_bp_1w": None if not w else rnd(w["cum"], 0),
                "curve_date": cd.strftime("%Y-%m-%d")})
write("boe_meetings", boe)

# ------------------------------------------------------------------ 5. data health
MAX_AGE = {"D": 5, "W": 12, "M": 75, "Q": 200}
today = pd.Timestamp.today().normalize()
health = []
for sid, g in D.groupby("series_id"):
    base = "UK_OIS_FWD_01M" if sid.startswith("UK_OIS_FWD") else sid
    if sid.startswith("UK_OIS_FWD") and sid != "UK_OIS_FWD_01M":
        continue
    meta = REG.get(base, {"economy": "GBP", "name": "OIS forward curve (24 points)", "source": "boe_curve", "freq": "D"})
    if sid == "UK_OIS_FWD_01M":
        meta = {"economy": "GBP", "name": "OIS forward curve, 1–24m", "source": "boe_curve", "freq": "D"}
    if sid in ("UK_OIS_1Y", "UK_OIS_2Y"):
        meta = {"economy": "GBP", "name": f"OIS spot {sid[-2:].lower()}", "source": "boe_curve", "freq": "D"}
    last = g["date"].max()
    freq = meta.get("freq", "D")
    # monthly/quarterly are dated at period start: measure age from period end
    ref = last + (pd.offsets.MonthEnd(0) if freq == "M" else pd.offsets.QuarterEnd(0) if freq == "Q" else pd.Timedelta(0))
    age = (today - ref).days
    health.append({"series": sid, "economy": meta["economy"], "name": meta["name"], "source": meta["source"],
                   "frequency": freq, "last_obs": last.strftime("%Y-%m-%d"), "age_days": int(age),
                   "status": "Stale" if age > MAX_AGE[freq] else "OK"})
health.sort(key=lambda r: (r["status"] != "Stale", r["economy"], r["series"]))
write("data_health", health)
