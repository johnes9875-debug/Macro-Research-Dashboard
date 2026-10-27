"""Group-1 datasets: economic calendar, Fed dots vs market, term premium, liquidity, cross-asset,
FX vs rates, inflation expectations, and the facts file for the morning brief.

Writes data/outputs/dash/{econ_calendar,fed_dots,term_premium,liquidity,liquidity_hist,cross_asset,
fx_rates,fx_rates_hist,infl_expect,infl_expect_hist}.json and data/outputs/brief_facts.json.
Run after compute.py, monitor.py and export_dashboard.py.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import compute as C

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs" / "dash"
s, REG = C.s, C.REG
TODAY = pd.Timestamp(date.today())


def rnd(x, n):
    if x is None:
        return None
    try:
        if np.isnan(x):
            return None
    except TypeError:
        pass
    return round(float(x), n) + 0.0


def write(name, rows):
    (OUT / f"{name}.json").write_text(json.dumps(rows, separators=(",", ":"), default=str))
    print(f"{name:16} {len(rows):5} rows")


def at_or_before(x: pd.Series, when):
    y = x[x.index <= when].dropna()
    return None if y.empty else float(y.iloc[-1])


def chg(x: pd.Series, days: int, scale: float = 1.0):
    x = x.dropna()
    p = at_or_before(x, x.index[-1] - pd.Timedelta(days=days))
    return None if p is None else (float(x.iloc[-1]) - p) * scale


def pctile(x: pd.Series):
    x = x.dropna()
    yr = x[x.index > x.index[-1] - pd.Timedelta(days=365)]
    return rnd((yr < x.iloc[-1]).mean() * 100, 0)


def spark(x: pd.Series, days=92, n=3):
    x = x.dropna()
    return [rnd(v, n) for v in x[x.index > x.index[-1] - pd.Timedelta(days=days)].values]


def weekly(x: pd.Series, start: str, n=3):
    x = x[x.index >= start].dropna().resample("W-FRI").last().dropna()
    return [(d.strftime("%Y-%m-%d"), rnd(v, n)) for d, v in x.items()]


latest_macro = {r["key"]: r for r in json.loads((OUT / "macro_latest.json").read_text())}
latest_rel = {r["key"]: r for r in json.loads((OUT / "releases.json").read_text())}

# ------------------------------------------------------------------ 1. economic calendar
LAST = {  # release id -> (label, key in macro_latest/releases, decimals)
    "US10": [("CPI y/y", "USD CPI y/y"), ("core", "USD Core CPI y/y")],
    "US50": [("payrolls k", "USD Payrolls change (k)"), ("unemp.", "USD Unemployment rate")],
    "US54": [("core PCE y/y", "USD Core PCE y/y")],
    "US53": [("GDP q/q saar", "USD Real GDP q/q annualised")],
    "US192": [("openings m", "USD Job openings (m)")],
    "US180": [("claims k", "USD Initial claims (k)")],
    "US9": [], "US46": [], "US11": [], "US13": [],
    "EU:inflation": [("HICP y/y", "EUR HICP y/y"), ("core", "EUR Core HICP y/y")],
    "EU:unemployment": [("unemp.", "EUR Unemployment rate")],
    "EU:gdp": [("GDP y/y", "EUR Real GDP y/y")],
    "UK:CPI (incl. core, services)": [("CPI y/y", "GBP CPI y/y"), ("core", "GBP Core CPI y/y"), ("services", "GBP Services CPI y/y")],
    "UK:Labour market (LFS, pay)": [("unemp.", "GBP Unemployment rate (LFS)"), ("pay 3m y/y", "GBP Pay growth, 3m avg y/y")],
    "UK:Monthly GDP": [("GDP m/m", "GBP Monthly GDP m/m")],
}
TIER1 = {"US10", "US50", "US54", "US53", "EU:inflation", "UK:CPI (incl. core, services)", "UK:Labour market (LFS, pay)"}


def last_print(rid: str) -> str:
    key = rid
    if rid.startswith("EU:"):
        t = rid[3:]
        key = "EU:inflation" if ("inflation" in t or "hicp" in t) else "EU:unemployment" if "unemployment" in t else "EU:gdp" if "gdp" in t else rid
    parts, period = [], ""
    for label, k in LAST.get(key, []):
        r = latest_macro.get(k) or latest_rel.get(k)
        if r and r.get("value") is not None:
            v = float(r["value"])
            fmt = ".0f" if label.endswith(" k") else ".2f" if label.endswith(" m") else ".1f"
            parts.append(f"{label} {v:{fmt}}")
            pts = pd.Timestamp(r.get("period_iso") or r.get("period"))
            period = f"Q{(pts.month - 1) // 3 + 1} {pts.year}" if "GDP q/q" in label or "GDP y/y" in label else pts.strftime("%b %Y")
    return (", ".join(parts) + (f" ({period})" if period else "")) if parts else ""


def tier(rid: str) -> int:
    if rid in TIER1:
        return 1
    if rid.startswith("EU:") and ("inflation" in rid and "flash" in rid):
        return 1
    return 2


cal_rows = []
crp = ROOT / "data" / "calendar_releases.parquet"
if crp.exists():
    rc = pd.read_parquet(crp)
    for r in rc.itertuples():
        cal_rows.append({"date": r.date, "sgt": r.sgt, "economy": r.economy, "kind": "Data", "event": r.release,
                         "period": r.period or "", "last": last_print(r.release_id), "tier": tier(r.release_id),
                         "source": r.source})
CB_SGT_TIME = {}
for m in yaml.safe_load((ROOT / "config" / "calendar.yaml").read_text())["meetings"]:
    d = pd.Timestamp(m["date"])
    if TODAY <= d <= TODAY + pd.Timedelta(days=60):
        pol = C.ECON[m["economy"]]["policy"]() if m["economy"] in C.ECON else s("NZ_3M")
        # show the Singapore date and time: "29 Oct 02:00" -> 2026-10-29, 02:00
        sg_day = pd.to_datetime(f"{m['sgt'].split(',')[0].split(' ')[0]} {m['sgt'].split(',')[0].split(' ')[1]} {d.year}", format="%d %b %Y", errors="coerce")
        sg_day = d if pd.isna(sg_day) else sg_day
        cal_rows.append({"date": sg_day.strftime("%Y-%m-%d"), "sgt": m["sgt"].split(" ")[-1] if ":" in m["sgt"] else "midday", "economy": m["economy"], "kind": "Central bank",
                         "event": f"{m['cb']} policy decision", "period": "",
                         "last": (f"target {s('US_FF_LOWER').dropna().iloc[-1]:.2f}–{s('US_FF_UPPER').dropna().iloc[-1]:.2f}%" if m["economy"] == "USD"
                                  else ("NZ 3m bank bill " + f"{pol.dropna().iloc[-1]:.2f}% (monthly)" if m["economy"] == "NZD"
                                        else f"policy rate {pol.dropna().iloc[-1]:.2f}%")),
                         "tier": 1, "source": "config/calendar.yaml", "sgt_note": m["sgt"]})
cal = sorted(cal_rows, key=lambda r: (r["date"], r["sgt"] or "99"))
for r in cal:
    r["days"] = (pd.Timestamp(r["date"]) - TODAY).days
    r["key"] = f"{r['date']} {r['sgt']} {r['economy']} {r['event']}"
write("econ_calendar", cal)

# ------------------------------------------------------------------ 2. Fed dots vs market
curve_pts = [(1 / 12, "US_1M"), (0.25, "US_3M"), (0.5, "US_6M"), (1, "US_1Y"), (2, "US_2Y"), (5, "US_5Y")]


def market_rate_at(T: float, asof=None) -> float:
    ys = [(t, at_or_before(s(sid), asof) if asof is not None else float(s(sid).dropna().iloc[-1])) for t, sid in curve_pts]
    ts = np.array([0.0] + [t for t, _ in ys]); yv = np.array([ys[0][1]] + [y for _, y in ys])
    y = lambda t: float(np.interp(t, ts, yv))
    w = min(0.25, T)
    if T - w <= 1e-9:
        return y(T)
    return (y(T) * T - y(T - w) * (T - w)) / w


dots = s("US_DOTS").dropna()
prior = s("US_DOTS_PRIOR").dropna() if "US_DOTS_PRIOR" in set(C.D.series_id) else pd.Series(dtype=float)
vint = json.loads((ROOT / "data" / "dots_vintages.json").read_text()) if (ROOT / "data" / "dots_vintages.json").exists() else {}
asof = s("US_2Y").dropna().index[-1]
pol_now = float(C.us_policy().dropna().iloc[-1])
fed_rows = []
for d, v in dots.items():
    end = pd.Timestamp(f"{d.year}-12-31")
    T = (end - asof).days / 365.25
    mk = market_rate_at(T) if 0 < T <= 5 else None
    mk_w = market_rate_at(T + 7 / 365.25, asof - pd.Timedelta(days=7)) if 0 < T <= 5 else None
    pv = at_or_before(prior, d) if not prior.empty and d in prior.index else None
    fed_rows.append({"horizon": f"End-{d.year}", "dot_median": rnd(v, 2), "dot_prior": rnd(pv, 2),
                     "dot_change_bp": None if pv is None else rnd((v - pv) * 100, 0),
                     "market": rnd(mk, 2), "market_1w": rnd(mk_w, 2),
                     "market_minus_dot_bp": None if mk is None else rnd((mk - v) * 100, 0),
                     "dot_vs_policy_bp": rnd((v - pol_now) * 100, 0)})
lr = s("US_DOTS_LR").dropna()
fed_rows.append({"horizon": "Longer run", "dot_median": rnd(lr.iloc[-1], 2), "dot_prior": rnd(lr.iloc[-2], 2),
                 "dot_change_bp": rnd((lr.iloc[-1] - lr.iloc[-2]) * 100, 0), "market": None, "market_1w": None,
                 "market_minus_dot_bp": None, "dot_vs_policy_bp": rnd((lr.iloc[-1] - pol_now) * 100, 0)})
for r in fed_rows:
    r["sep"] = vint.get("latest", ""); r["sep_prior"] = vint.get("prior", ""); r["policy_mid"] = rnd(pol_now, 3)
    r["market_asof"] = asof.strftime("%Y-%m-%d")
write("fed_dots", fed_rows)

# ------------------------------------------------------------------ 3. term premium
tp, y10 = s("US_TP10").dropna(), s("US_10Y").dropna()
df = pd.concat([y10, tp], axis=1, sort=True).dropna(); df.columns = ["y10", "tp"]
df["exp"] = df.y10 - df.tp
tp_rows = []
for d, r in df[df.index >= "2021-01-01"].resample("W-FRI").last().dropna().iterrows():
    tp_rows.append({"date": d.strftime("%Y-%m-%d"), "y10": rnd(r.y10, 2), "term_premium": rnd(r.tp, 2), "expected_path": rnd(r.exp, 2)})
last = df.iloc[-1]
tp_summary = {"date": df.index[-1].strftime("%Y-%m-%d"), "y10": rnd(last.y10, 2), "term_premium": rnd(last.tp, 2),
              "expected_path": rnd(last.exp, 2), "tp_chg_1m_bp": rnd(chg(df.tp, 30, 100), 0), "tp_chg_1y_bp": rnd(chg(df.tp, 365, 100), 0),
              "exp_chg_1m_bp": rnd(chg(df.exp, 30, 100), 0), "tp_pctile_1y": pctile(df.tp)}
for r in tp_rows:
    r.update({"is_last": False})
tp_rows[-1]["is_last"] = True
write("term_premium", tp_rows)

# ------------------------------------------------------------------ 4. liquidity
sofr, effr, iorb = s("US_SOFR").dropna(), s("US_EFFR").dropna(), s("US_IORB").dropna()
sofr_iorb = (pd.concat([sofr, iorb], axis=1, sort=True).ffill().dropna().pipe(lambda d: d.iloc[:, 0] - d.iloc[:, 1]) * 100)
effr_iorb = (pd.concat([effr, iorb], axis=1, sort=True).ffill().dropna().pipe(lambda d: d.iloc[:, 0] - d.iloc[:, 1]) * 100)
LIQ = [  # key, label, series, scale to $bn (or bp), unit, decimals, good direction note
    ("fed_assets", "Fed balance sheet", s("US_FED_ASSETS") / 1000, "$bn", 0),
    ("reserves", "Bank reserves", s("US_RESERVES") / 1000, "$bn", 0),
    ("rrp", "Overnight reverse repo", s("US_RRP"), "$bn", 1),
    ("tga", "Treasury cash (TGA)", s("US_TGA") / 1000, "$bn", 0),
    ("sofr_iorb", "SOFR − IORB", sofr_iorb, "bp", 0),
    ("effr_iorb", "EFFR − IORB", effr_iorb, "bp", 0),
]
liq, liq_hist = [], []
for key, label, x, unit, n in LIQ:
    x = x.dropna()
    liq.append({"key": key, "measure": label, "unit": unit, "value": rnd(x.iloc[-1], n), "date": x.index[-1].strftime("%Y-%m-%d"),
                "chg_1w": rnd(chg(x, 7), n), "chg_1m": rnd(chg(x, 30), n), "chg_3m": rnd(chg(x, 91), n), "chg_1y": rnd(chg(x, 365), n),
                "pctile_1y": pctile(x), "spark": spark(x, 365, 2)})
    for d, v in weekly(x, "2022-01-01", 2):
        liq_hist.append({"date": d, "key": key, "measure": label, "value": v})
write("liquidity", liq)
write("liquidity_hist", liq_hist)

# ------------------------------------------------------------------ 5. cross-asset
XA = [("vix", "VIX", s("US_VIX"), "", 1, "Risk"), ("ig", "US IG credit spread", s("US_IG_OAS") * 100, "bp", 0, "Risk"),
      ("hy", "US high-yield spread", s("US_HY_OAS") * 100, "bp", 0, "Risk"),
      ("nfci", "Chicago Fed financial conditions", s("US_NFCI"), "index", 2, "Risk"),
      ("dxy", "Broad dollar index", s("US_DXY_BROAD"), "index", 1, "FX"),
      ("eurusd", "EURUSD", s("FX_EURUSD"), "", 4, "FX"), ("gbpusd", "GBPUSD", s("FX_GBPUSD"), "", 4, "FX"),
      ("usdjpy", "USDJPY", s("FX_USDJPY"), "", 2, "FX"), ("audusd", "AUDUSD", s("FX_AUDUSD"), "", 4, "FX"),
      ("usdcad", "USDCAD", s("FX_USDCAD"), "", 4, "FX"), ("usdchf", "USDCHF", s("FX_USDCHF"), "", 4, "FX"),
      ("nzdusd", "NZDUSD", s("FX_NZDUSD"), "", 4, "FX"), ("usdsek", "USDSEK", s("FX_USDSEK"), "", 3, "FX"),
      ("usdnok", "USDNOK", s("FX_USDNOK"), "", 3, "FX")]
xa = []
for key, label, x, unit, n, grp in XA:
    x = x.dropna()
    pct_like = grp == "FX"
    row = {"key": key, "group": grp, "measure": label, "unit": unit, "value": rnd(x.iloc[-1], n), "date": x.index[-1].strftime("%Y-%m-%d"),
           "pctile_1y": pctile(x), "spark": spark(x, 92, 4)}
    if pct_like:
        for k, dd in (("chg_1w", 7), ("chg_1m", 30), ("chg_3m", 91)):
            p = at_or_before(x, x.index[-1] - pd.Timedelta(days=dd))
            row[k] = None if p is None else rnd((x.iloc[-1] / p - 1) * 100, 2)
        row["chg_unit"] = "%"
    else:
        for k, dd in (("chg_1w", 7), ("chg_1m", 30), ("chg_3m", 91)):
            row[k] = rnd(chg(x, dd), n)
        row["chg_unit"] = unit or "pts"
    xa.append(row)
write("cross_asset", xa)

# ------------------------------------------------------------------ 6. FX vs 2y rate differential
PAIRS = [("EURUSD", "FX_EURUSD", "EA_2Y", "US_2Y", "EUR 2y − US 2y"), ("GBPUSD", "FX_GBPUSD", "UK_2Y", "US_2Y", "UK 2y − US 2y"),
         ("USDJPY", "FX_USDJPY", "US_2Y", "JP_2Y", "US 2y − JP 2y"), ("AUDUSD", "FX_AUDUSD", "AU_2Y", "US_2Y", "AU 2y − US 2y"),
         ("USDCAD", "FX_USDCAD", "US_2Y", "CA_2Y", "US 2y − CA 2y"), ("USDSEK", "FX_USDSEK", "US_2Y", "SE_2Y", "US 2y − SE 2y"),
         ("USDNOK", "FX_USDNOK", "US_2Y", "NO_3Y", "US 2y − NO 3y")]
fxr, fxh = [], []
for pair, fx_id, a, b, diff_label in PAIRS:
    df = pd.concat([s(fx_id), s(a), s(b)], axis=1, sort=True).dropna()
    df.columns = ["fx", "a", "b"]
    df["diff"] = (df.a - df.b) * 100
    yr = df[df.index > df.index[-1] - pd.Timedelta(days=365)]
    beta, alpha = np.polyfit(yr["diff"], np.log(yr.fx), 1)
    fair = np.exp(alpha + beta * yr["diff"])
    resid = (np.log(yr.fx) - np.log(fair)) * 100
    wk = yr.resample("W-FRI").last().dropna()
    corr = np.corrcoef(wk.fx.pct_change().dropna().tail(26), wk["diff"].diff().dropna().tail(26))[0, 1]
    fxr.append({"pair": pair, "spot": rnd(df.fx.iloc[-1], 2 if pair == "USDJPY" else 3 if pair in ("USDSEK", "USDNOK") else 4), "diff_label": diff_label,
                "diff_bp": rnd(df["diff"].iloc[-1], 0), "diff_chg_1m_bp": rnd(chg(df["diff"], 30), 0),
                "fair_value": rnd(fair.iloc[-1], 2 if pair == "USDJPY" else 3 if pair in ("USDSEK", "USDNOK") else 4), "misalignment_pct": rnd(resid.iloc[-1], 1),
                "misalignment_z": rnd(resid.iloc[-1] / resid.std(), 1), "beta_pct_per_10bp": rnd(beta * 1000, 2),
                "corr_26w": rnd(corr, 2), "date": df.index[-1].strftime("%Y-%m-%d")})
    for d, r in wk.iterrows():
        fv = float(np.exp(alpha + beta * r["diff"]))
        fxh.append({"date": d.strftime("%Y-%m-%d"), "pair": pair, "spot": rnd(r.fx, 4), "fair_value": rnd(fv, 4)})
write("fx_rates", fxr)
write("fx_rates_hist", fxh)

# ------------------------------------------------------------------ 7. inflation expectations
uk_i5, uk_i10 = s("UK_INFL_5Y").dropna(), s("UK_INFL_10Y").dropna()
uk_55 = (((1 + uk_i10 / 100) ** 10 / (1 + uk_i5 / 100) ** 5) ** (1 / 5) - 1) * 100
IE = [("USD", "5y breakeven", s("US_5Y_BEI")), ("USD", "10y breakeven", s("US_10Y_BEI")), ("USD", "5y5y forward", s("US_5Y5Y")),
      ("USD", "5y real yield (TIPS)", s("US_5Y_REAL")), ("USD", "10y real yield (TIPS)", s("US_10Y_REAL")),
      ("GBP", "5y implied inflation (RPI)", uk_i5), ("GBP", "10y implied inflation (RPI)", uk_i10), ("GBP", "5y5y forward (RPI)", uk_55.dropna()),
      ("GBP", "5y real yield (linkers)", s("UK_REAL_5Y")), ("GBP", "10y real yield (linkers)", s("UK_REAL_10Y"))]
ie, ieh = [], []
for eco, label, x in IE:
    x = x.dropna()
    ie.append({"key": f"{eco} {label}", "economy": eco, "measure": label, "value": rnd(x.iloc[-1], 2), "date": x.index[-1].strftime("%Y-%m-%d"),
               "chg_1w_bp": rnd(chg(x, 7, 100), 0), "chg_1m_bp": rnd(chg(x, 30, 100), 0), "chg_3m_bp": rnd(chg(x, 91, 100), 0),
               "pctile_1y": pctile(x), "low_1y": rnd(x[x.index > x.index[-1] - pd.Timedelta(days=365)].min(), 2),
               "high_1y": rnd(x[x.index > x.index[-1] - pd.Timedelta(days=365)].max(), 2)})
for name, x in (("US 5y5y", s("US_5Y5Y")), ("UK 5y5y (RPI)", uk_55), ("US 10y real", s("US_10Y_REAL")), ("UK 10y real", s("UK_REAL_10Y"))):
    for d, v in weekly(x, "2021-01-01", 2):
        ieh.append({"date": d, "series": name, "value": v})
write("infl_expect", ie)
write("infl_expect_hist", ieh)

# ------------------------------------------------------------------ 8. US Treasury supply (auctions)
auc_rows, upc_rows = [], []
ap = ROOT / "data" / "auctions.parquet"
if ap.exists():
    a = pd.read_parquet(ap)
    for c in ("offering_amt", "bid_to_cover_ratio", "high_yield", "primary_dealer_accepted", "indirect_bidder_accepted",
              "direct_bidder_accepted", "comp_accepted"):
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a = a[a.floating_rate != "Yes"].copy()
    a["kind"] = np.where(a.inflation_index_security == "Yes", "TIPS", a.security_type)
    a["tenor"] = a.original_security_term.fillna(a.security_term)
    a["dealer_pct"] = a.primary_dealer_accepted / a.comp_accepted * 100
    a["indirect_pct"] = a.indirect_bidder_accepted / a.comp_accepted * 100
    a["direct_pct"] = a.direct_bidder_accepted / a.comp_accepted * 100
    a = a.sort_values("auction_date")
    done = a[a.bid_to_cover_ratio.notna()]
    for (kind, tenor), g in done.groupby(["kind", "tenor"]):
        g = g.sort_values("auction_date")
        g["btc_avg6"] = g.bid_to_cover_ratio.shift(1).rolling(6, min_periods=3).mean()
        g["dealer_avg6"] = g.dealer_pct.shift(1).rolling(6, min_periods=3).mean()
        g["indirect_avg6"] = g.indirect_pct.shift(1).rolling(6, min_periods=3).mean()
        done.loc[g.index, ["btc_avg6", "dealer_avg6", "indirect_avg6"]] = g[["btc_avg6", "dealer_avg6", "indirect_avg6"]]
    recent = done.sort_values("auction_date", ascending=False).head(20)
    for r in recent.itertuples():
        auc_rows.append({"key": f"{r.auction_date} {r.kind} {r.tenor} {r.cusip}", "date": r.auction_date, "security": f"{r.tenor} {r.kind}" + (" (reopening)" if r.reopening == "Yes" else ""),
                         "size_bn": rnd(r.offering_amt / 1e9, 0), "high_yield": rnd(r.high_yield, 3), "btc": rnd(r.bid_to_cover_ratio, 2),
                         "btc_vs_avg": None if pd.isna(r.btc_avg6) else rnd(r.bid_to_cover_ratio - r.btc_avg6, 2),
                         "dealer_pct": rnd(r.dealer_pct, 1), "dealer_vs_avg": None if pd.isna(r.dealer_avg6) else rnd(r.dealer_pct - r.dealer_avg6, 1),
                         "indirect_pct": rnd(r.indirect_pct, 1), "indirect_vs_avg": None if pd.isna(r.indirect_avg6) else rnd(r.indirect_pct - r.indirect_avg6, 1),
                         "direct_pct": rnd(r.direct_pct, 1)})
    pending = a[a.bid_to_cover_ratio.isna() & (pd.to_datetime(a.auction_date) <= TODAY)]
    for r in pending.itertuples():
        upc_rows.append({"key": f"{r.auction_date} {r.kind} {r.tenor}", "date": r.auction_date, "security": f"{r.tenor} {r.kind}",
                         "size_bn": rnd(r.offering_amt / 1e9, 0), "status": "Results pending"})
up = ROOT / "data" / "auctions_upcoming.parquet"
if up.exists():
    u = pd.read_parquet(up)
    if not u.empty:
        u = u[u.security_type.isin(["Note", "Bond", "TIPS"]) & (pd.to_datetime(u.auction_date) >= TODAY)]
        for r in u.itertuples():
            amt = pd.to_numeric(r.offering_amt, errors="coerce")
            upc_rows.append({"key": f"{r.auction_date} {r.security_type} {r.security_term}", "date": r.auction_date,
                             "security": f"{r.security_term} {r.security_type}" + (" (reopening)" if r.reopening == "Yes" else ""),
                             "size_bn": None if pd.isna(amt) else rnd(amt / 1e9, 0), "status": "Announced" if not pd.isna(amt) else "Scheduled"})
upc_rows = sorted({r["key"]: r for r in upc_rows}.values(), key=lambda r: r["date"])
write("auctions", auc_rows)
write("auctions_upcoming", upc_rows)

# ------------------------------------------------------------------ 9. CFTC positioning (leveraged funds and asset managers)
pos_rows, pos_hist = [], []
cp = ROOT / "data" / "cftc.parquet"
if cp.exists():
    c = pd.read_parquet(cp)
    c["lev_net"] = c.lev_money_positions_long - c.lev_money_positions_short
    c["am_net"] = c.asset_mgr_positions_long - c.asset_mgr_positions_short
    c["lev_net_pct_oi"] = c.lev_net / c.open_interest_all * 100
    GROUP = {"UST 2y": "Rates", "UST 5y": "Rates", "UST 10y": "Rates", "UST Ultra 10y": "Rates", "UST Bond": "Rates",
             "UST Ultra Bond": "Rates", "SOFR 3m": "Rates"}
    order = list(dict.fromkeys(["UST 2y", "UST 5y", "UST 10y", "UST Ultra 10y", "UST Bond", "UST Ultra Bond", "SOFR 3m",
                                "EUR", "JPY", "GBP", "CAD", "AUD", "CHF", "NZD"]))
    for name in order:
        g = c[c.contract == name].sort_values("date")
        if g.empty:
            continue
        last = g.iloc[-1]
        prev = g.iloc[-2] if len(g) > 1 else None
        g3 = g[g.date > last.date - pd.Timedelta(days=365 * 3)]
        z = (last.lev_net - g3.lev_net.mean()) / g3.lev_net.std() if len(g3) > 20 else None
        pos_rows.append({"contract": name, "group": GROUP.get(name, "FX"), "date": last.date.strftime("%Y-%m-%d"),
                         "lev_net_k": rnd(last.lev_net / 1000, 1), "lev_chg_1w_k": None if prev is None else rnd((last.lev_net - prev.lev_net) / 1000, 1),
                         "lev_pct_oi": rnd(last.lev_net_pct_oi, 1), "lev_z_3y": rnd(z, 1),
                         "lev_pctile_3y": rnd((g3.lev_net < last.lev_net).mean() * 100, 0),
                         "am_net_k": rnd(last.am_net / 1000, 1), "am_chg_1w_k": None if prev is None else rnd((last.am_net - prev.am_net) / 1000, 1),
                         "oi_k": rnd(last.open_interest_all / 1000, 0)})
        for r in g[g.date >= TODAY - pd.Timedelta(days=730)].itertuples():
            pos_hist.append({"date": r.date.strftime("%Y-%m-%d"), "contract": name, "lev_net_k": rnd(r.lev_net / 1000, 1), "am_net_k": rnd(r.am_net / 1000, 1)})
write("positioning", pos_rows)
write("positioning_hist", pos_hist)

# ------------------------------------------------------------------ 10. brief facts (numbers the morning brief may use)
grid = json.loads((OUT / "rates_grid.json").read_text())
ov = json.loads((OUT / "overview.json").read_text())
boe = json.loads((OUT / "boe_meetings.json").read_text())
health = json.loads((OUT / "data_health.json").read_text())
rv = json.loads((OUT / "curve_rv.json").read_text())
biggest = sorted([g for g in grid if g["chg_1d"] is not None], key=lambda g: -abs(g["chg_1d"]))[:6]
facts = {
    "as_of_us_close": ov[0]["y10_date"],
    "policy": [{k: o[k] for k in ("economy", "cb", "policy", "priced_12m_bp", "priced_chg_1w_bp", "next_meeting", "next_meeting_sgt", "days_to_meeting")} for o in ov],
    "yields": [{k: g[k] for k in ("key", "level", "chg_1d", "chg_1w", "pct_1y")} for g in grid if any(t in g["instrument"] for t in ("2y", "10y"))],
    "biggest_1d_moves_bp": [{"key": g["key"], "chg_1d": g["chg_1d"], "level": g["level"]} for g in biggest],
    "boe_next_meeting": boe[0] if boe else None,
    "curve_rv_stretched": [r for r in rv if r["z_1y"] is not None and abs(r["z_1y"]) >= 1.5],
    "fed_dots": fed_rows,
    "term_premium": tp_summary,
    "liquidity": [{k: r[k] for k in ("measure", "unit", "value", "chg_1w", "chg_1m")} for r in liq],
    "cross_asset": [{k: r[k] for k in ("measure", "value", "chg_1w", "chg_unit")} for r in xa],
    "fx_vs_rates": fxr,
    "inflation_expectations": [{k: r[k] for k in ("key", "value", "chg_1w_bp", "chg_1m_bp")} for r in ie],
    "next_7_days": [r for r in cal if 0 <= r["days"] <= 7],
    "stale_series": [h["series"] for h in health if h["status"] == "Stale"],
    "auctions_recent": auc_rows[:6],
    "auctions_next": [r for r in upc_rows if r["status"] != "Results pending"][:6],
    "positioning": [{k: r[k] for k in ("contract", "lev_net_k", "lev_chg_1w_k", "lev_z_3y", "am_net_k")} for r in pos_rows],
}
(ROOT / "data" / "outputs" / "brief_facts.json").write_text(json.dumps(facts, indent=1, default=str))
print("brief_facts.json written")
