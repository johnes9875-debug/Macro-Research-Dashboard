"""Turn data/latest.parquet into data/outputs/dashboard.json for the dashboard.

All arithmetic happens here; the dashboard only displays these numbers.
Run: python src/compute.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

D = pd.read_parquet(ROOT / "data" / "latest.parquet")
REG = {s["id"]: s for s in yaml.safe_load((ROOT / "config" / "series.yaml").read_text())["series"]}
CAL = yaml.safe_load((ROOT / "config" / "calendar.yaml").read_text())["meetings"]


def s(sid: str) -> pd.Series:
    x = D[D.series_id == sid].set_index("date")["value"].sort_index()
    if x.empty:
        raise KeyError(sid)
    # Put monthly/quarterly series on a regular calendar so a missing release
    # (e.g. US CPI for Oct 2025, never published after the shutdown) leaves a gap
    # instead of shifting every y/y comparison by one period.
    freq = REG.get(sid, {}).get("freq")
    if freq in ("M", "Q"):
        # some sources date periods at month end (RBA): normalise to period start first
        x.index = x.index.to_period(freq).to_timestamp()
        x = x[~x.index.duplicated(keep="last")]
        x = x.asfreq("MS" if freq == "M" else "QS")
    return x


def r2(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def change_bp(x: pd.Series, days: int) -> float | None:
    """Change in bp vs the last observation on or before (last date - days)."""
    last_d = x.index[-1]
    prev = x[x.index <= last_d - pd.Timedelta(days=days)]
    return None if prev.empty else r2((x.iloc[-1] - prev.iloc[-1]) * 100, 1)


def yoy(x: pd.Series) -> pd.Series:
    return (x / x.shift(12) - 1) * 100


def ann3m(x: pd.Series) -> pd.Series:
    return ((x / x.shift(3)) ** 4 - 1) * 100


def point(x: pd.Series, n=2) -> dict:
    x = x.dropna()
    return {"value": r2(x.iloc[-1], n), "prior": r2(x.iloc[-2], n), "period": iso(x.index[-1])}


def rate_block(sid: str) -> dict:
    x = s(sid)
    return {"value": r2(x.iloc[-1], 3), "date": iso(x.index[-1]),
            "chg_1d": change_bp(x, 1), "chg_1w": change_bp(x, 7), "chg_1m": change_bp(x, 30)}


def history(x: pd.Series, start: str, freq: str | None = None, n=3) -> list:
    x = x[x.index >= start].dropna()
    if freq:
        x = x.resample(freq).last().dropna()
    return [[iso(d), r2(v, n)] for d, v in x.items()]


# ------------------------------------------------------------------ economies
def us_policy() -> pd.Series:
    return (s("US_FF_UPPER") + s("US_FF_LOWER")) / 2


def jp_policy() -> pd.Series:
    """BoJ policy rate (uncollateralised overnight call rate target). The BoJ sets the basic loan rate at
    target + 25bp (since the July 2024 hike), so target = basic loan rate - 0.25. Before August 2024 the
    actual call rate is used (the target was a 0-0.1% range or -0.1%)."""
    blr, call = s("JP_BLR"), s("JP_CALL")
    if blr.dropna().empty:
        return call
    tgt = (blr - 0.25)[blr.index >= "2024-08-01"]
    return pd.concat([call[call.index < "2024-08-01"], tgt]).sort_index()


def policy_display(code: str, value) -> str:
    """How a desk quotes the policy rate: the Fed as a range, others as a level with 2 decimals."""
    if code == "USD":
        return f"{s('US_FF_LOWER').dropna().iloc[-1]:.2f}–{s('US_FF_UPPER').dropna().iloc[-1]:.2f}"
    return f"{value:.2f}"


ECON = {
    "USD": dict(cb="Fed", policy=us_policy, policy_label="Fed funds target range (midpoint used in calculations)",
                y2="US_2Y", y10="US_10Y", y30="US_30Y", long_label="30y",
                path=[("1m", 1, "US_1M"), ("3m", 3, "US_3M"), ("6m", 6, "US_6M"), ("1y", 12, "US_1Y"), ("2y", 24, "US_2Y")],
                path_quality="Proxy: Treasury bill and note yields vs the policy midpoint. Bills also carry supply and term premium, so read the shape, not the exact bp."),
    "EUR": dict(cb="ECB", policy=lambda: s("EA_DFR"), policy_label="ECB deposit facility rate",
                y2="EA_2Y", y10="EA_10Y", y30="EA_30Y", long_label="30y",
                path=[("3m", 3, "EA_3M"), ("1y", 12, "EA_1Y"), ("2y", 24, "EA_2Y")],
                path_quality="Proxy: ECB AAA government curve (spot) vs the deposit rate. Rough guide only."),
    "GBP": dict(cb="BoE", policy=lambda: s("UK_BANKRATE"), policy_label="Bank Rate",
                y2="UK_2Y", y10="UK_10Y", y30="UK_20Y", long_label="20y",
                path=[(f"{m}m", m, f"UK_OIS_FWD_{m:02d}M") for m in (1, 3, 6, 9, 12, 18, 24)],
                path_quality="Market pricing: Bank of England OIS instantaneous forward curve. Closest to a true priced path."),
    "JPY": dict(cb="BoJ", policy=jp_policy, policy_label="BoJ policy rate (call rate target; basic loan rate − 25bp)",
                y2="JP_2Y", y10="JP_10Y", y30="JP_30Y", long_label="30y",
                path=[("1y", 12, "JP_1Y"), ("2y", 24, "JP_2Y")],
                path_quality="Proxy: JGB 1y and 2y yields vs the overnight call rate. Rough guide only."),
    "CAD": dict(cb="BoC", policy=lambda: s("CA_POLICY"), policy_label="BoC target overnight rate",
                y2="CA_2Y", y10="CA_10Y", y30="CA_LONG", long_label="30y",
                path=[("3m", 3, "CA_3M"), ("6m", 6, "CA_6M"), ("1y", 12, "CA_1Y"), ("2y", 24, "CA_2Y")],
                path_quality="Proxy: Government of Canada T-bills and 2y benchmark vs the overnight target."),
    "AUD": dict(cb="RBA", policy=lambda: s("AU_CASH"), policy_label="RBA cash rate target",
                y2="AU_2Y", y10="AU_10Y", y30="AU_10Y", long_label="10y",
                path=[("3m", 3, "AU_BAB_3M"), ("6m", 6, "AU_BAB_6M"), ("2y", 24, "AU_2Y"), ("3y", 36, "AU_3Y")],
                path_quality="Proxy: bank bills (carry a credit spread over OIS, which the RBA stopped publishing in 2022) and ACGB yields vs the cash rate."),
    "CHF": dict(cb="SNB", policy=lambda: s("CH_POLICY"), policy_label="SNB policy rate",
                y2="CH_2Y", y10="CH_10Y", y30="CH_30Y", long_label="30y",
                path=[("2y", 24, "CH_2Y")],
                path_quality="Proxy: Confederation 2y vs the SNB rate. SNB publishes bond yields monthly, so this lags by up to a month."),
    "SEK": dict(cb="Riksbank", policy=lambda: s("SE_POLICY"), policy_label="Riksbank policy rate",
                y2="SE_2Y", y10="SE_10Y", y30="SE_10Y", long_label="10y",
                path=[("3m", 3, "SE_3M"), ("2y", 24, "SE_2Y")],
                path_quality="Proxy: Swedish T-bill 3m and SGB 2y vs the policy rate."),
    "NOK": dict(cb="Norges Bank", policy=lambda: s("NO_POLICY"), policy_label="Norges Bank policy rate",
                y2="NO_3Y", y10="NO_10Y", y30="NO_10Y", long_label="10y", y2_label="3y",
                path=[("3y", 36, "NO_3Y")],
                path_quality="Proxy: Norwegian government 3y vs the policy rate (no 2y benchmark published)."),
    "CNY": dict(cb="PBoC", policy=lambda: s("CN_POLICY"), policy_label="PBoC 7-day reverse repo rate",
                y2="CN_2Y", y10="CN_10Y", y30="CN_30Y", long_label="30y",
                path=[("3m", 3, "CN_SHIBOR3M"), ("1y", 12, "CN_1Y"), ("2y", 24, "CN_2Y")],
                path_quality="Proxy: Shibor 3m and CGB 1y/2y vs the 7-day reverse repo rate. Shibor carries a bank credit spread and CGBs trade below policy on safe-haven demand, so read direction only."),
}
ORDER = list(ECON)


def sgt_time(m) -> str:
    """ISO timestamp (+08:00) of a decision from its 'sgt' label, e.g. '28 Oct 21:45'; 'midday' = 12:00."""
    d = pd.Timestamp(m["date"])
    lab = str(m["sgt"]).split(",")[0].strip()
    hm = re.search(r"(\d{1,2}):(\d{2})", str(m["sgt"]))
    t = pd.Timestamp(f"{lab.split()[0]} {lab.split()[1]} {d.year}")
    if t.month < d.month:  # decision late on 31 Dec local, early 1 Jan SGT
        t = t.replace(year=d.year + 1)
    t = t.replace(hour=int(hm.group(1)) if hm else 12, minute=int(hm.group(2)) if hm else 0)
    return t.strftime("%Y-%m-%dT%H:%M:00+08:00")


def cb_calendar() -> list:
    """Upcoming decisions sorted by Singapore time (not local date), so tonight's BoC precedes tomorrow's Fed."""
    now = pd.Timestamp.now(tz="Asia/Singapore").tz_localize(None) - pd.Timedelta(hours=3)
    rows = [m | {"date": str(m["date"]), "sgt_iso": sgt_time(m)} for m in CAL]
    rows = [r for r in rows if pd.Timestamp(r["sgt_iso"][:16]) >= now]
    return sorted(rows, key=lambda r: r["sgt_iso"])


def implied_path(cfg: dict, policy_now: float, asof_shift_days: int = 0) -> list:
    out = []
    for label, months, sid in cfg["path"]:
        x = s(sid)
        if asof_shift_days:
            x = x[x.index <= x.index[-1] - pd.Timedelta(days=asof_shift_days)]
        if x.empty:
            continue
        out.append({"label": label, "months": months, "rate": r2(x.iloc[-1], 3),
                    "vs_policy_bp": r2((x.iloc[-1] - policy_now) * 100, 0)})
    return out


def economy_block(code: str) -> dict:
    cfg = ECON[code]
    pol = cfg["policy"]().dropna()
    pol_now = float(pol.iloc[-1])
    y2, y10, y30 = s(cfg["y2"]), s(cfg["y10"]), s(cfg["y30"])
    curve = (y10 - y2).dropna() * 100
    path_now = implied_path(cfg, pol_now)
    path_1w = implied_path(cfg, pol_now, 7)
    # headline proxy: 12m-ahead point (or nearest) vs policy
    p12 = min(path_now, key=lambda p: abs(p["months"] - 12))
    p12_1w = next((p for p in path_1w if p["label"] == p12["label"]), None)
    nxt = next((m for m in CAL if m["economy"] == code and pd.Timestamp(m["date"]) >= pd.Timestamp.today().normalize()), None)
    return {
        "cb": cfg["cb"], "y2_label": cfg.get("y2_label", "2y"),
        "policy": {"label": cfg["policy_label"], "value": r2(pol_now, 3), "date": iso(pol.index[-1]),
                   "display": policy_display(code, pol_now)},
        "next_meeting": nxt,
        "y2": rate_block(cfg["y2"]), "y10": rate_block(cfg["y10"]),
        "ylong": {**rate_block(cfg["y30"]), "label": cfg["long_label"]},
        "s2s10s": {"value": r2(curve.iloc[-1], 1), "chg_1w": r2(curve.iloc[-1] - curve[curve.index <= curve.index[-1] - pd.Timedelta(days=7)].iloc[-1], 1),
                   "chg_1m": r2(curve.iloc[-1] - curve[curve.index <= curve.index[-1] - pd.Timedelta(days=30)].iloc[-1], 1)},
        "priced_12m": {"label": p12["label"], "vs_policy_bp": p12["vs_policy_bp"],
                       "chg_1w_bp": None if p12_1w is None else r2(p12["vs_policy_bp"] - p12_1w["vs_policy_bp"], 0)},
        "path": path_now, "path_1w": path_1w, "path_quality": cfg["path_quality"],
        "hist": {"y2": history(y2, "2024-10-01"), "y10": history(y10, "2024-10-01"),
                 "policy": history(pol, "2024-10-01")},
    }


# ------------------------------------------------------------------ macro
def macro() -> dict:
    us_cpi, us_core, us_pce, us_pcec = s("US_CPI"), s("US_CPI_CORE"), s("US_PCE"), s("US_PCE_CORE")
    us_shel = s("US_CPI_SHELTER")
    pay = s("US_PAYROLLS").diff()
    infl = {
        "USD": {"headline": point(yoy(us_cpi).dropna(), 1), "core": point(yoy(us_core).dropna(), 1),
                "extra": [{"name": "Core CPI, 3m annualised", **point(ann3m(us_core).dropna(), 1)},
                          {"name": "Core PCE y/y", **point(yoy(us_pcec).dropna(), 1)},
                          {"name": "Shelter CPI y/y", **point(yoy(us_shel).dropna(), 1)},
                          {"name": "10y breakeven", **point(s("US_10Y_BEI"), 2)}],
                "headline_name": "CPI y/y", "core_name": "Core CPI y/y"},
        "EUR": {"headline": point(s("EA_HICP"), 1), "core": point(s("EA_HICP_CORE"), 1),
                "extra": [{"name": "Services y/y", **point(s("EA_HICP_SERV"), 1)},
                          {"name": "Energy y/y", **point(s("EA_HICP_NRG"), 1)},
                          {"name": "Non-energy goods y/y", **point(s("EA_HICP_NEIG"), 1)}],
                "headline_name": "HICP y/y", "core_name": "Core HICP y/y"},
        "GBP": {"headline": point(s("UK_CPI"), 1), "core": point(s("UK_CPI_CORE"), 1),
                "extra": [{"name": "Services CPI y/y", **point(s("UK_CPI_SERV"), 1)}],
                "headline_name": "CPI y/y", "core_name": "Core CPI y/y"},
        "CAD": {"headline": point(s("CA_CPI"), 1), "core": point(s("CA_CPI_TRIM"), 1),
                "extra": [{"name": "CPI-median y/y", **point(s("CA_CPI_MED"), 1)}],
                "headline_name": "CPI y/y", "core_name": "CPI-trim y/y"},
        "AUD": {"headline": point(s("AU_CPI"), 1), "core": point(s("AU_CPI_TRIM"), 1), "extra": [],
                "headline_name": "Monthly CPI y/y", "core_name": "Trimmed mean y/y"},
        "CHF": {"headline": point(s("CH_CPI"), 1), "core": None, "extra": [],
                "headline_name": "CPI y/y", "core_name": "Core CPI y/y"},
        "SEK": {"headline": point(s("SE_CPIF"), 1), "core": None, "extra": [],
                "headline_name": "CPIF y/y (Riksbank target)", "core_name": "CPIF ex energy y/y"},
        "NZD": {"headline": point(s("NZ_CPI"), 1), "core": point(s("NZ_CPI_CORE"), 1),
                "extra": [{"name": "Services CPI y/y", **point(s("NZ_CPI_SERV"), 1)}],
                "headline_name": "CPI y/y (quarterly)", "core_name": "CPI ex food & energy y/y"},
        "CNY": {"headline": point(s("CN_CPI"), 1), "core": None, "extra": [{"name": "Food CPI y/y", **point(s("CN_CPI_FOOD"), 1)}],
                "headline_name": "CPI y/y (via OECD)", "core_name": "Core CPI y/y"},
        "NOK": {"headline": point(s("NO_CPI"), 1), "core": point(s("NO_CPI_ATE"), 1), "extra": [],
                "headline_name": "CPI y/y", "core_name": "CPI-ATE y/y"},
        "JPY": {"headline": point(s("JP_CPI"), 1), "core": point(s("JP_CPI_CORE"), 1),
                "extra": [{"name": "Core-core (ex fresh food & energy) y/y", **point(s("JP_CPI_CORECORE"), 1)},
                          {"name": "Services CPI y/y", **point(s("JP_CPI_SERV"), 1)},
                          {"name": "Tokyo core CPI y/y", **point(s("JP_TOKYO_CORE"), 1)}],
                "headline_name": "CPI y/y", "core_name": "Core CPI (ex fresh food) y/y"},
    }
    labour = {
        "USD": [{"name": "Unemployment rate", **point(s("US_UNEMP"), 1)},
                {"name": "Payrolls, 3m avg (k)", **point(pay.rolling(3).mean().dropna(), 0)},
                {"name": "Hourly earnings y/y", **point(yoy(s("US_AHE")).dropna(), 1)},
                {"name": "Job openings (m)", **point(s("US_JOLTS") / 1000, 2)},
                {"name": "Initial claims (k)", **point(s("US_CLAIMS") / 1000, 0)}],
        "EUR": [{"name": "Unemployment rate", **point(s("EA_UNEMP"), 1)}],
        "GBP": [{"name": "Unemployment rate (LFS)", **point(s("UK_UNEMP"), 1)},
                {"name": "Pay growth, 3m avg y/y", **point(s("UK_PAY"), 1)}],
        "JPY": [{"name": "Unemployment rate", **point(s("JP_UNEMP"), 1)}],
        "CAD": [{"name": "Unemployment rate (LFS)", **point(s("CA_UNEMP"), 1)}],
        "AUD": [{"name": "Unemployment rate", **point(s("AU_UNEMP"), 1)}],
        "NZD": [{"name": "Unemployment rate (quarterly)", **point(s("NZ_UNEMP"), 1)}],
        "CHF": [{"name": "Registered jobless rate (SA)", **point(s("CH_UNEMP"), 1)}],
        "SEK": [{"name": "Unemployment rate (LFS, SA)", **point(s("SE_UNEMP"), 1)}],
        "NOK": [{"name": "Unemployment rate (LFS, SA)", **point(s("NO_UNEMP"), 1)}],
    }
    gdp_us = ((s("US_GDP") / s("US_GDP").shift(1)) ** 4 - 1) * 100
    uk_gdp = s("UK_GDP_M").pct_change() * 100
    growth = {
        "USD": {"name": "Real GDP q/q annualised", **point(gdp_us.dropna(), 1)},
        "EUR": {"name": "Real GDP y/y", **point(s("EA_GDP"), 1)},
        "GBP": {"name": "Monthly GDP m/m", **point(uk_gdp.dropna(), 1)},
        "JPY": None, "CAD": None, "AUD": None, "NZD": {"name": "Real GDP y/y", **point(s("NZ_GDP"), 1)}, "CHF": None, "SEK": None, "NOK": None,
        "CNY": {"name": "Exports y/y (USD)", **point(s("CN_EXPORTS"), 1)},
    }
    charts = {
        "inflation": {
            "USD": {"headline": history(yoy(us_cpi).dropna(), "2021-01-01", n=2), "core": history(yoy(us_core).dropna(), "2021-01-01", n=2)},
            "EUR": {"headline": history(s("EA_HICP"), "2021-01-01", n=2), "core": history(s("EA_HICP_CORE"), "2021-01-01", n=2)},
            "GBP": {"headline": history(s("UK_CPI"), "2021-01-01", n=2), "core": history(s("UK_CPI_CORE"), "2021-01-01", n=2)},
            "JPY": {"headline": history(s("JP_CPI"), "2021-01-01", n=2), "core": history(s("JP_CPI_CORE"), "2021-01-01", n=2)},
            "CAD": {"headline": history(s("CA_CPI"), "2021-01-01", n=2), "core": history(s("CA_CPI_TRIM"), "2021-01-01", n=2)},
            "AUD": {"headline": history(s("AU_CPI"), "2021-01-01", n=2), "core": history(s("AU_CPI_TRIM"), "2021-01-01", n=2)},
            "CHF": {"headline": history(s("CH_CPI"), "2021-01-01", n=2), "core": []},
            "SEK": {"headline": history(s("SE_CPIF"), "2021-01-01", n=2), "core": []},
            "NOK": {"headline": history(s("NO_CPI"), "2021-01-01", n=2), "core": history(s("NO_CPI_ATE"), "2021-01-01", n=2)},
            "NZD": {"headline": history(s("NZ_CPI"), "2021-01-01", n=2), "core": history(s("NZ_CPI_CORE"), "2021-01-01", n=2)},
            "CNY": {"headline": history(s("CN_CPI"), "2021-01-01", n=2), "core": []},
        },
        "unemployment": {
            "USD": history(s("US_UNEMP"), "2021-01-01", n=2), "EUR": history(s("EA_UNEMP"), "2021-01-01", n=2),
            "GBP": history(s("UK_UNEMP"), "2021-01-01", n=2), "JPY": history(s("JP_UNEMP"), "2021-01-01", n=2),
            "CAD": history(s("CA_UNEMP"), "2021-01-01", n=2), "AUD": history(s("AU_UNEMP"), "2021-01-01", n=2),
            "NZD": history(s("NZ_UNEMP"), "2021-01-01", n=2), "CHF": history(s("CH_UNEMP"), "2021-01-01", n=2),
            "SEK": history(s("SE_UNEMP"), "2021-01-01", n=2), "NOK": history(s("NO_UNEMP"), "2021-01-01", n=2),
        },
    }
    return {"inflation": infl, "labour": labour, "growth": growth, "charts": charts}


# ------------------------------------------------------------------ releases (latest monthly prints)
def releases() -> list:
    rows = []
    specs = [("USD", "CPI y/y", yoy(s("US_CPI")), 1), ("USD", "Core CPI y/y", yoy(s("US_CPI_CORE")), 1),
             ("USD", "Core PCE y/y", yoy(s("US_PCE_CORE")), 1), ("USD", "Unemployment rate", s("US_UNEMP"), 1),
             ("USD", "Payrolls change (k)", s("US_PAYROLLS").diff(), 0), ("USD", "Hourly earnings y/y", yoy(s("US_AHE")), 1),
             ("USD", "Job openings (m)", s("US_JOLTS") / 1000, 2),
             ("EUR", "HICP y/y", s("EA_HICP"), 1), ("EUR", "Core HICP y/y", s("EA_HICP_CORE"), 1),
             ("EUR", "Services HICP y/y", s("EA_HICP_SERV"), 1), ("EUR", "Unemployment rate", s("EA_UNEMP"), 1),
             ("GBP", "CPI y/y", s("UK_CPI"), 1), ("GBP", "Core CPI y/y", s("UK_CPI_CORE"), 1),
             ("GBP", "Services CPI y/y", s("UK_CPI_SERV"), 1), ("GBP", "Unemployment rate", s("UK_UNEMP"), 1),
             ("GBP", "Pay growth 3m y/y", s("UK_PAY"), 1), ("GBP", "Monthly GDP m/m", s("UK_GDP_M").pct_change() * 100, 1),
             ("JPY", "CPI y/y", s("JP_CPI"), 1), ("JPY", "Core CPI (ex fresh food) y/y", s("JP_CPI_CORE"), 1),
             ("JPY", "Tokyo core CPI y/y", s("JP_TOKYO_CORE"), 1), ("JPY", "Unemployment rate", s("JP_UNEMP"), 1),
             ("CAD", "CPI y/y", s("CA_CPI"), 1), ("CAD", "CPI-trim y/y", s("CA_CPI_TRIM"), 1), ("CAD", "Unemployment rate", s("CA_UNEMP"), 1),
             ("AUD", "Monthly CPI y/y", s("AU_CPI"), 1), ("AUD", "Trimmed mean y/y", s("AU_CPI_TRIM"), 1), ("AUD", "Unemployment rate", s("AU_UNEMP"), 1),
             ("CHF", "CPI y/y", s("CH_CPI"), 1), ("SEK", "CPIF y/y", s("SE_CPIF"), 1), ("SEK", "Unemployment rate", s("SE_UNEMP"), 1),
             ("NOK", "CPI-ATE y/y", s("NO_CPI_ATE"), 1), ("NOK", "Unemployment rate", s("NO_UNEMP"), 1),
             ("NZD", "CPI y/y (quarterly)", s("NZ_CPI"), 1), ("NZD", "Unemployment rate", s("NZ_UNEMP"), 1),
             ("CNY", "CPI y/y", s("CN_CPI"), 1), ("CNY", "Exports y/y", s("CN_EXPORTS"), 1)]
    for eco, name, x, n in specs:
        x = x.dropna()
        rows.append({"economy": eco, "name": name, "period": x.index[-1].strftime("%b %Y"), "period_iso": iso(x.index[-1]),
                     "value": r2(x.iloc[-1], n), "prior": r2(x.iloc[-2], n), "change": r2(x.iloc[-1] - x.iloc[-2], n)})
    return sorted(rows, key=lambda r: r["period_iso"], reverse=True)


# ------------------------------------------------------------------ cross-market
def spreads() -> list:
    pairs = [("UST – Bund 10y", "US_10Y", "DE_10Y"), ("Gilt – Bund 10y", "UK_10Y", "DE_10Y"),
             ("UST – Bund 2y", "US_2Y", "DE_2Y"), ("UST – JGB 10y", "US_10Y", "JP_10Y"),
             ("Gilt – UST 10y", "UK_10Y", "US_10Y"), ("ACGB – UST 10y", "AU_10Y", "US_10Y"),
             ("GoC – UST 10y", "CA_10Y", "US_10Y"), ("Euro AAA – Bund 10y", "EA_10Y", "DE_10Y"),
             ("UST – CGB 10y", "US_10Y", "CN_10Y"), ("CGB – JGB 10y", "CN_10Y", "JP_10Y")]
    out = []
    for name, a, b in pairs:
        x = (pd.concat([s(a), s(b)], axis=1).dropna().pipe(lambda d: d.iloc[:, 0] - d.iloc[:, 1]) * 100)
        yr = x[x.index >= x.index[-1] - pd.Timedelta(days=365)]
        out.append({"name": name, "value_bp": r2(x.iloc[-1], 0), "date": iso(x.index[-1]),
                    "chg_1w_bp": change_bp(x / 100, 7), "chg_1m_bp": change_bp(x / 100, 30),
                    "z_1y": r2((x.iloc[-1] - yr.mean()) / yr.std(), 2),
                    "range_1y": [r2(yr.min(), 0), r2(yr.max(), 0)],
                    "hist": history(x, "2024-10-01", "W-FRI", n=1)})
    return out


def main() -> None:
    econ = {c: economy_block(c) for c in ECON}
    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "economies": econ,
        "macro": macro(),
        "releases": releases(),
        "spreads": spreads(),
        "calendar": cb_calendar(),
        "freshness": {sid: iso(g["date"].max()) for sid, g in D.groupby("series_id") if "OIS_FWD" not in sid},
        "sources": ["FRED (St. Louis Fed)", "ECB Data Portal", "Eurostat (prc_hicp_minr)", "ONS", "Bank of England (IADB, yield curves)",
                    "Bank of Japan Time-Series API", "Japan Ministry of Finance (JGB yields)"],
    }
    (OUT / "dashboard.json").write_text(json.dumps(out, default=str))
    print("wrote", OUT / "dashboard.json", f"{(OUT / 'dashboard.json').stat().st_size/1024:.0f} KB")
    for c, e in econ.items():
        print(c, "policy", e["policy"]["value"], "| 2y", e["y2"]["value"], e["y2"]["chg_1w"], "| 10y", e["y10"]["value"],
              "| 2s10s", e["s2s10s"]["value"], "| priced", e["priced_12m"], "| next", (e["next_meeting"] or {}).get("date"))


if __name__ == "__main__":
    main()
