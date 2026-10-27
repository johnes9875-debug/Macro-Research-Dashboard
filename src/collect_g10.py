"""Collectors for the rest of the G10 (CAD, AUD, NZD via FRED, CHF, SEK, NOK), German Bunds,
US Treasury auctions and CFTC positioning. Called from collect.py.

Each series collector returns a long DataFrame (series_id, date, value). Auctions and CFTC
positioning are tables, written to data/auctions.parquet and data/cftc.parquet.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _frame(sid, dates, values):
    df = pd.DataFrame({"series_id": sid, "date": pd.to_datetime(dates), "value": pd.to_numeric(values, errors="coerce")})
    return df.dropna(subset=["value"])


# ------------------------------------------------------------------ Canada
def boc(get, items, start):
    out = []
    for sid, code in items:
        j = get(f"https://www.bankofcanada.ca/valet/observations/{code}/json", params={"start_date": start}).json()
        obs = j.get("observations", [])
        out.append(_frame(sid, [o["d"] for o in obs], [o.get(code, {}).get("v") for o in obs]))
    return pd.concat(out)


def statcan(get_post, items, start):
    body = [{"vectorId": int(code.lstrip("v")), "latestN": 160} for _, code in items]
    j = get_post("https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods", json=body).json()
    by = {int(x["object"]["vectorId"]): x["object"]["vectorDataPoint"] for x in j if x.get("status") == "SUCCESS"}
    out = []
    for sid, code in items:
        pts = by.get(int(code.lstrip("v")), [])
        out.append(_frame(sid, [p["refPer"] for p in pts], [p["value"] for p in pts]))
    return pd.concat(out)


# ------------------------------------------------------------------ Australia
def rba(get, items, start):
    """code = '<table>/<series id>', e.g. 'f2/FCMYGBAG10D'."""
    tables = {}
    out = []
    for sid, code in items:
        t, s = code.split("/")
        if t not in tables:
            txt = get(f"https://www.rba.gov.au/statistics/tables/csv/{t}-data.csv").content.decode("utf-8", "replace")
            rows = list(csv.reader(io.StringIO(txt)))
            ids = next(r for r in rows if r and r[0] == "Series ID")
            data = [r for r in rows if r and r[0][:1].isdigit()]
            tables[t] = (ids, data)
        ids, data = tables[t]
        i = ids.index(s)
        dates = pd.to_datetime([r[0] for r in data], format="mixed", dayfirst=True, errors="coerce")
        vals = [r[i] if i < len(r) else None for r in data]
        df = _frame(sid, dates, vals)
        out.append(df[df.date >= start])
    return pd.concat(out)


def abs_cpi(get, items, start):
    """code = '<measure>.<index>.<tsest>.<region>.M' on the ABS CPI dataflow (monthly)."""
    out = []
    for sid, code in items:
        r = get(f"https://data.api.abs.gov.au/rest/data/ABS,CPI/{code}", params={"startPeriod": start[:7], "format": "csvfilewithlabels"})
        d = pd.read_csv(io.StringIO(r.text))
        out.append(_frame(sid, pd.to_datetime(d["TIME_PERIOD"].astype(str) + "-01"), d["OBS_VALUE"]))
    return pd.concat(out)


# ------------------------------------------------------------------ Switzerland
def snb(get, items, start):
    """code = '<cube>/<item>' or '<cube>/<d0>|<d1>' (e.g. 'rendeiduebd/CHF|10J0')."""
    cubes, out = {}, []
    for sid, code in items:
        cube, item = code.split("/", 1)
        if cube not in cubes:
            txt = get(f"https://data.snb.ch/api/cube/{cube}/data/csv/en", params={"fromDate": start[:7]}).text.lstrip("﻿")
            lines = txt.splitlines()
            hdr = next(i for i, l in enumerate(lines) if l.startswith('"Date"'))
            cubes[cube] = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), sep=";", dtype=str)
        d = cubes[cube]
        if "|" in item:
            a, b = item.split("|")
            d = d[(d["D0"] == a) & (d["D1"] == b)]
        else:
            d = d[d["D0"] == item]
        dates = pd.to_datetime(d["Date"].where(d["Date"].str.len() > 7, d["Date"] + "-01"))
        out.append(_frame(sid, dates, d["Value"]))
    return pd.concat(out)


# ------------------------------------------------------------------ Sweden
def riksbank(get, items, start):
    out = []
    for sid, code in items:
        if code == "SWESTR":
            j = get(f"https://api.riksbank.se/swestr/v1/all/SWESTR", params={"fromDate": start}).json()
            out.append(_frame(sid, [x["date"] for x in j], [x["rate"] for x in j]))
        else:
            j = get(f"https://api.riksbank.se/swea/v1/Observations/{code}/{start}").json()
            out.append(_frame(sid, [x["date"] for x in j], [x["value"] for x in j]))
    return pd.concat(out)


def pxweb(post, base, items, start):
    """code = '<table path>|<json selection: code=value;code=value>'. Time is always the last variable."""
    out = []
    for sid, code in items:
        path, sel = code.split("|", 1)
        query = [{"code": k, "selection": {"filter": "item", "values": [v]}} for k, v in (p.split("=") for p in sel.split(";"))]
        j = post(f"{base}/{path}", json={"query": query, "response": {"format": "json-stat2" if "ssb" in base else "json"}}).json()
        if "ssb" in base:
            times = list(j["dimension"]["Tid"]["category"]["index"].keys())
            vals = j["value"]
        else:
            times = [d["key"][-1] for d in j["data"]]
            vals = [d["values"][0] for d in j["data"]]
        dates = pd.to_datetime([t.replace("M", "-") + "-01" for t in times])
        df = _frame(sid, dates, [None if v in ("..", ".") else v for v in vals])
        out.append(df[df.date >= start])
    return pd.concat(out)


# ------------------------------------------------------------------ Norway
def norgesbank(get, items, start):
    out = []
    for sid, code in items:
        r = get(f"https://data.norges-bank.no/api/data/{code}", params={"format": "csv", "startPeriod": start, "locale": "en"})
        d = pd.read_csv(io.StringIO(r.text), sep=";")
        out.append(_frame(sid, d["TIME_PERIOD"], d["OBS_VALUE"]))
    return pd.concat(out)


# ------------------------------------------------------------------ Germany
def bundesbank(get, items, start):
    out = []
    for sid, code in items:
        r = get(f"https://api.statistiken.bundesbank.de/rest/data/{code}", params={"startPeriod": start},
                headers={"Accept": "text/csv", "User-Agent": "Mozilla/5.0 (rates-monitor personal research script)"})
        d = pd.read_csv(io.StringIO(r.content.decode("utf-8-sig")), sep=";", dtype=str)
        out.append(_frame(sid, d["TIME_PERIOD"], d["OBS_VALUE"].replace(".", None)))
    return pd.concat(out)


# ------------------------------------------------------------------ US Treasury auctions
def treasury_auctions(get):
    base = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
    since = (pd.Timestamp.today() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    rows, page = [], 1
    while True:
        j = get(base + "auctions_query", params={"sort": "-auction_date", "page[size]": 500, "page[number]": page,
                                                 "filter": f"security_type:in:(Note,Bond),auction_date:gte:{since}"}).json()
        rows += j["data"]
        if page >= j.get("meta", {}).get("total-pages", 1):
            break
        page += 1
    d = pd.DataFrame(rows)
    keep = ["auction_date", "issue_date", "security_type", "security_term", "original_security_term", "inflation_index_security",
            "floating_rate", "reopening", "cusip", "offering_amt", "bid_to_cover_ratio", "high_yield", "high_discnt_margin",
            "primary_dealer_accepted", "indirect_bidder_accepted", "direct_bidder_accepted", "comp_accepted", "total_accepted"]
    d = d[[c for c in keep if c in d]].replace("null", None)
    d.to_parquet(ROOT / "data" / "auctions.parquet", index=False)
    up = get(base + "upcoming_auctions", params={"sort": "-record_date,auction_date", "page[size]": 100}).json()["data"]
    u = pd.DataFrame(up).replace("null", None)
    if not u.empty:
        u = u[u["record_date"] == u["record_date"].max()]
    u.to_parquet(ROOT / "data" / "auctions_upcoming.parquet", index=False)
    print(f"auctions: {len(d)} coupon auctions, {len(u)} upcoming")
    return len(d)


# ------------------------------------------------------------------ CFTC positioning (Traders in Financial Futures)
CFTC = {"042601": "UST 2y", "044601": "UST 5y", "043602": "UST 10y", "043607": "UST Ultra 10y", "020601": "UST Bond",
        "020604": "UST Ultra Bond", "134741": "SOFR 3m",
        "099741": "EUR", "097741": "JPY", "096742": "GBP", "090741": "CAD", "232741": "AUD", "092741": "CHF", "112741": "NZD"}


def cftc(get):
    since = (pd.Timestamp.today() - pd.Timedelta(days=365 * 3 + 30)).strftime("%Y-%m-%d")
    codes = ",".join(f"'{c}'" for c in CFTC)
    j = get("https://publicreporting.cftc.gov/resource/gpe5-46if.json",
            params={"$where": f"cftc_contract_market_code in({codes}) AND report_date_as_yyyy_mm_dd >= '{since}'",
                    "$select": "report_date_as_yyyy_mm_dd,cftc_contract_market_code,open_interest_all,lev_money_positions_long,"
                               "lev_money_positions_short,asset_mgr_positions_long,asset_mgr_positions_short,dealer_positions_long_all,dealer_positions_short_all",
                    "$limit": 50000}).json()
    d = pd.DataFrame(j)
    d["date"] = pd.to_datetime(d["report_date_as_yyyy_mm_dd"]).dt.tz_localize(None).dt.normalize()
    d["contract"] = d["cftc_contract_market_code"].map(CFTC)
    for c in d.columns:
        if c.endswith(("_long", "_short", "_all")) and c != "cftc_contract_market_code":
            d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.drop(columns=["report_date_as_yyyy_mm_dd"]).sort_values(["contract", "date"])
    d.to_parquet(ROOT / "data" / "cftc.parquet", index=False)
    print(f"cftc: {len(d)} rows, {d.contract.nunique()} contracts, latest {d.date.max().date()}")
    return len(d)
