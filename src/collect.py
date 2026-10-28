"""Collectors for v1 sources. Each returns a long DataFrame: series_id, date, value.

Run:  python src/collect.py            (pulls everything in config/series.yaml)
Needs FRED_API_KEY in the environment (or a .env file in the repo root).
"""
from __future__ import annotations

import io
import os
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
STORE = ROOT / "data" / "vintages.parquet"
LATEST = ROOT / "data" / "latest.parquet"
START = "2015-01-01"
UA = {"User-Agent": "Mozilla/5.0 (rates-monitor personal research script)"}

MON = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _get(url: str, headers: dict | None = None, **kw) -> requests.Response:
    """GET with 3 retries and backoff."""
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers={**UA, **(headers or {})}, timeout=90, **kw)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:150]}")
        except requests.RequestException as e:  # network error
            last = e
        time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def _post(url: str, **kw) -> requests.Response:
    """POST with 3 retries and backoff (PxWeb and StatCan APIs)."""
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=UA, timeout=90, **kw)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:150]}")
        except requests.RequestException as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def _frame(sid: str, dates, values) -> pd.DataFrame:
    df = pd.DataFrame({"series_id": sid, "date": pd.to_datetime(dates), "value": pd.to_numeric(values, errors="coerce")})
    return df.dropna(subset=["value"])


# ---------------------------------------------------------------- sources
def fred(sid: str, code: str) -> pd.DataFrame:
    r = _get("https://api.stlouisfed.org/fred/series/observations",
             params=dict(series_id=code, api_key=os.environ["FRED_API_KEY"], file_type="json",
                         observation_start=START))
    obs = r.json()["observations"]
    return _frame(sid, [o["date"] for o in obs], [o["value"] for o in obs])


def estat_cpi(items: list[tuple[str, str]]) -> pd.DataFrame:
    """Japan CPI year-on-year rates from e-Stat (Statistics Bureau, 2020-base table 0003427113).
    code = "<area>/<item>", e.g. "00000/0161" (all Japan, all items less fresh food). Needs ESTAT_APP_ID."""
    k = os.environ.get("ESTAT_APP_ID")
    if not k:
        raise RuntimeError("ESTAT_APP_ID not set; Japan CPI skipped")
    areas = sorted({c.split("/")[0] for _, c in items}); cats = sorted({c.split("/")[1] for _, c in items})
    j = _get("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData",
             params=dict(appId=k, statsDataId="0003427113", lang="E", cdTab="3", cdCat01=",".join(cats),
                         cdArea=",".join(areas), cdTimeFrom=START[:4] + "000101", limit=100000)).json()
    res = j["GET_STATS_DATA"]["RESULT"]
    if str(res.get("STATUS")) != "0":
        raise RuntimeError(f"e-Stat: {res.get('ERROR_MSG')}")
    rows = j["GET_STATS_DATA"]["STATISTICAL_DATA"]["DATA_INF"]["VALUE"]
    df = pd.DataFrame([{"area": v["@area"], "cat": v["@cat01"], "time": v["@time"], "val": v["$"]} for v in rows])
    df = df[(df.time.str[6:8] == df.time.str[8:10]) & (df.time.str[6:8] != "00")]  # monthly codes YYYY00MMMM
    df["date"] = pd.to_datetime(df.time.str[:4] + "-" + df.time.str[6:8] + "-01")
    out = []
    for sid, code in items:
        a, c = code.split("/")
        d = df[(df.area == a) & (df.cat == c)]
        out.append(_frame(sid, d["date"], d["val"]))
    return pd.concat(out)


def fred_dots_prior() -> pd.DataFrame:
    """FOMC median dots as published at the previous SEP (ALFRED vintage), series US_DOTS_PRIOR."""
    k = os.environ["FRED_API_KEY"]
    v = _get("https://api.stlouisfed.org/fred/series/vintagedates",
             params=dict(series_id="FEDTARMD", api_key=k, file_type="json", sort_order="desc", limit=2)).json()["vintage_dates"]
    prev = v[1]
    obs = _get("https://api.stlouisfed.org/fred/series/observations",
               params=dict(series_id="FEDTARMD", api_key=k, file_type="json", realtime_start=prev, realtime_end=prev)).json()["observations"]
    df = _frame("US_DOTS_PRIOR", [o["date"] for o in obs], [o["value"] for o in obs])
    (ROOT / "data" / "dots_vintages.json").write_text(f'{{"latest": "{v[0]}", "prior": "{prev}"}}')
    return df


def ecb(sid: str, code: str) -> pd.DataFrame:
    r = _get(f"https://data-api.ecb.europa.eu/service/data/{code}",
             params=dict(startPeriod=START[:7], format="csvdata"))
    d = pd.read_csv(io.StringIO(r.text))
    period = d["TIME_PERIOD"].astype(str)
    # quarterly "2026-Q1" -> quarter start date
    if period.str.contains("Q").any():
        period = pd.PeriodIndex(period.str.replace("-", ""), freq="Q").start_time
    return _frame(sid, period, d["OBS_VALUE"])


_EUROSTAT_CACHE: dict = {}


def eurostat_hicp(sid: str, code: str) -> pd.DataFrame:
    if "j" not in _EUROSTAT_CACHE:
        r = _get("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr",
                 params=dict(geo="EA", unit="RCH_A", sinceTimePeriod=START[:7]))
        _EUROSTAT_CACHE["j"] = r.json()
    j = _EUROSTAT_CACHE["j"]
    ids, size = j["id"], j["size"]
    cidx = j["dimension"]["coicop18"]["category"]["index"][code]
    times = j["dimension"]["time"]["category"]["index"]
    # flat index = ((((freq*U)+unit)*C + coicop)*G + geo)*T + time ; freq/unit/geo each size 1
    ntime = size[ids.index("time")]
    rows = []
    for t, ti in times.items():
        v = j["value"].get(str(cidx * ntime + ti))
        if v is not None:
            rows.append((t, v))
    return _frame(sid, [r[0] for r in rows], [r[1] for r in rows])


def ons(sid: str, uri: str) -> pd.DataFrame:
    r = _get("https://www.ons.gov.uk/generator", params=dict(format="csv", uri=uri))
    rows = []
    for line in r.text.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) != 2:
            continue
        per, val = parts[0].strip('"'), parts[1].strip('"')
        bits = per.split()
        if len(bits) == 2 and bits[1] in MON and bits[0].isdigit():
            rows.append((f"{bits[0]}-{MON[bits[1]]:02d}-01", val))
    return _frame(sid, [r[0] for r in rows], [r[1] for r in rows])


def boe_iadb(items: list[tuple[str, str]]) -> pd.DataFrame:
    codes = ",".join(c for _, c in items)
    if len(items) == 1:  # the IADB export errors on a single code
        codes += ",IUDBEDR"
    for attempt in range(4):  # the IADB sometimes answers 200 with an HTML error page
        r = _get("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp",
                 params={"csv.x": "yes", "Datefrom": "01/Jan/2015", "Dateto": "now", "SeriesCodes": codes,
                         "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N"})
        if "csv" in r.headers.get("content-type", "") and r.text.startswith("DATE"):
            break
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError("BoE IADB returned HTML instead of CSV after 4 tries")
    d = pd.read_csv(io.StringIO(r.text))
    d["DATE"] = pd.to_datetime(d["DATE"], format="%d %b %Y")
    return pd.concat([_frame(sid, d["DATE"], d[code]) for sid, code in items])


def _boe_curve_sheet(xlsx, sheet: str) -> pd.DataFrame:
    """Return wide frame: index=date, columns=tenor (months for short-end sheets, years otherwise)."""
    raw = pd.read_excel(xlsx, sheet_name=sheet, header=None)
    lab = raw.iloc[:, 0].astype(str)
    hdr_row = lab[lab.str.startswith("months")].index
    hdr_row = hdr_row[0] if len(hdr_row) else lab[lab.str.startswith("years")].index[0]
    tenors = [round(float(t), 4) if pd.notna(t) else None for t in raw.iloc[hdr_row, 1:].tolist()]
    body = raw.iloc[hdr_row + 1:].copy()
    dates = pd.to_datetime(body.iloc[:, 0], errors="coerce", format="mixed")
    body, dates = body[dates.notna()], dates[dates.notna()]
    wide = body.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    wide.columns = tenors
    wide = wide.loc[:, [c is not None for c in wide.columns]]
    wide.index = dates.values
    return wide


def boe_curves() -> pd.DataFrame:
    """2y gilt spot and GBP OIS short-end forwards from BoE archive + latest-month files."""
    dest = RAW / "boe_yc"
    dest.mkdir(parents=True, exist_ok=True)
    base = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
    files = {"glcnominalddata.zip": None, "oisddata.zip": None, "glcrealddata.zip": None,
             "glcinflationddata.zip": None, "latest-yield-curve-data.zip": None}
    for f in files:
        p = dest / f
        # archives change rarely: refresh weekly; latest month: every run
        if f.startswith("latest") or not p.exists() or (time.time() - p.stat().st_mtime) > 6 * 86400:
            p.write_bytes(_get(base + f).content)
        files[f] = zipfile.ZipFile(p)

    def members(prefix: str):
        out = []
        for zf in files.values():
            for n in zf.namelist():
                if n.startswith(prefix) and ("2016" in n or "2025" in n or "current month" in n):
                    out.append(zf.open(n).read())
        return out

    gilt = pd.concat([_boe_curve_sheet(io.BytesIO(b), "4. spot curve") for b in members("GLC Nominal")])
    gilt = gilt[~gilt.index.duplicated(keep="last")].sort_index()
    frames = [_frame("UK_2Y", gilt.index, gilt[2.0])]

    ois = pd.concat([_boe_curve_sheet(io.BytesIO(b), "1. fwds, short end") for b in members("OIS")])
    ois = ois[~ois.index.duplicated(keep="last")].sort_index()
    ois = ois[ois.index >= "2020-01-01"]
    for m in range(1, 25):
        if float(m) in ois.columns:
            frames.append(_frame(f"UK_OIS_FWD_{m:02d}M", ois.index, ois[float(m)]))
    spot = pd.concat([_boe_curve_sheet(io.BytesIO(b), "4. spot curve") for b in members("OIS")])
    spot = spot[~spot.index.duplicated(keep="last")].sort_index()
    for y in (1.0, 2.0):
        frames.append(_frame(f"UK_OIS_{int(y)}Y", spot.index, spot[y]))
    # UK real (index-linked) and implied inflation (RPI) spot curves, 5y and 10y
    for prefix, tag in (("GLC Real", "REAL"), ("GLC Inflation", "INFL")):
        c = pd.concat([_boe_curve_sheet(io.BytesIO(b), "4. spot curve") for b in members(prefix)])
        c = c[~c.index.duplicated(keep="last")].sort_index()
        c = c[c.index >= "2018-01-01"]
        for y in (5.0, 10.0):
            frames.append(_frame(f"UK_{tag}_{int(y)}Y", c.index, c[y]))
    return pd.concat(frames)


def release_calendar() -> pd.DataFrame:
    """Upcoming tier-1 release dates: US (FRED release dates), euro area (Eurostat euro-indicator
    calendar) and UK (ONS 'Next release' field). Written to data/calendar_releases.parquet."""
    today = pd.Timestamp.today().normalize()
    end = today + pd.Timedelta(days=35)
    rows = []
    us = {10: "CPI", 50: "Employment report (payrolls)", 54: "Personal income & PCE", 53: "GDP",
          192: "JOLTS job openings", 9: "Retail sales", 46: "PPI", 11: "Employment Cost Index",
          180: "Initial jobless claims", 13: "Industrial production"}
    from zoneinfo import ZoneInfo
    SGT = ZoneInfo("Asia/Singapore")

    def sgt(day: str, hhmm: str, tz: str) -> str:
        h, m = map(int, hhmm.split(":"))
        local = pd.Timestamp(day).to_pydatetime().replace(hour=h, minute=m, tzinfo=ZoneInfo(tz))
        return local.astimezone(SGT).strftime("%Y-%m-%d %H:%M")

    us_time = {192: "10:00", 13: "09:15"}  # everything else 08:30 New York time
    for rid, name in us.items():
        try:
            j = _get("https://api.stlouisfed.org/fred/release/dates",
                     params=dict(api_key=os.environ["FRED_API_KEY"], file_type="json", release_id=rid,
                                 realtime_start=today.strftime("%Y-%m-%d"), realtime_end="9999-12-31",
                                 include_release_dates_with_no_data="true", sort_order="asc", limit=10)).json()
            for d in j.get("release_dates", []):
                if pd.Timestamp(d["date"]) <= end:
                    when = sgt(d["date"], us_time.get(rid, "08:30"), "America/New_York")
                    rows.append({"date": when[:10], "economy": "USD", "release": name, "source": "FRED release calendar",
                                 "sgt": when[11:], "period": "", "release_id": f"US{rid}"})
        except Exception as e:
            print(f"calendar US {name}: {e}")
    try:
        q = (f"start={today:%Y-%m-%d}T00%3A00%3A00%2B01%3A00&end={end:%Y-%m-%d}T00%3A00%3A00%2B01%3A00"
             "&theme=0&category=0&keywords=&isEuroindicator=true&authorInclude=&authorExclude=")
        ev = _get("https://ec.europa.eu/eurostat/o/calendars/eventsJson?" + q).json()
        keep = ("inflation", "hicp", "gdp", "unemployment", "retail", "industrial production", "sentiment", "employment")
        for e in ev:
            t = e.get("title", "")
            if any(k in t.lower() for k in keep):
                # the feed marks times "Z" but they are Luxembourg local time (euro indicators publish at 11:00 CET)
                day, hhmm = e["start"][:10], e["start"][11:16]
                when = sgt(day, hhmm, "Europe/Luxembourg")
                rows.append({"date": when[:10], "economy": "EUR", "release": t, "source": "Eurostat release calendar",
                             "sgt": when[11:], "period": e.get("period", ""), "release_id": "EU:" + t.lower()})
    except Exception as e:
        print(f"calendar EUR: {e}")
    ons = {"CPI (incl. core, services)": "/economy/inflationandpriceindices/timeseries/d7g7/mm23",
           "Labour market (LFS, pay)": "/employmentandlabourmarket/peoplenotinwork/unemployment/timeseries/mgsx/lms",
           "Monthly GDP": "/economy/grossdomesticproductgdp/timeseries/ecy2/mgdp"}
    for name, uri in ons.items():
        try:
            txt = _get("https://www.ons.gov.uk/generator", params=dict(format="csv", uri=uri)).text
            for line in txt.splitlines()[:12]:
                if line.startswith('"Next release"'):
                    d = pd.to_datetime(line.split('","')[1].strip('"'), format="%d %B %Y", errors="coerce")
                    if pd.notna(d) and d <= end:
                        when = sgt(d.strftime("%Y-%m-%d"), "07:00", "Europe/London")
                        rows.append({"date": when[:10], "economy": "GBP", "release": name,
                                     "source": "ONS next-release date", "sgt": when[11:], "period": "", "release_id": "UK:" + name})
        except Exception as e:
            print(f"calendar GBP {name}: {e}")
    cal = pd.DataFrame(rows).drop_duplicates()
    cal.to_parquet(ROOT / "data" / "calendar_releases.parquet", index=False)
    print(f"release calendar: {len(cal)} upcoming releases")
    return cal


def boj(sid: str, code: str) -> pd.DataFrame:
    db, series = code.split("/")
    dates, vals, pos = [], [], None
    while True:
        params = dict(format="json", lang="en", db=db, code=series, startDate=START[:4] + "01")
        if pos:
            params["startPosition"] = pos
        j = _get("https://www.stat-search.boj.or.jp/api/v1/getDataCode", params=params).json()
        for rs in j.get("RESULTSET", []):
            v = rs["VALUES"]
            dates += [str(d) for d in v["SURVEY_DATES"]]
            vals += v["VALUES"]
        pos = j.get("NEXTPOSITION")
        if not pos:
            break
    return _frame(sid, pd.to_datetime(dates, format="%Y%m%d"), vals)


def mof(items: list[tuple[str, str]]) -> pd.DataFrame:
    base = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"
    parts = []
    for url in (base + "historical/jgbcme_all.csv", base + "jgbcme.csv"):
        txt = _get(url).content.decode("utf-8", "replace")
        d = pd.read_csv(io.StringIO(txt), skiprows=1, na_values=["-"])
        d = d[pd.to_datetime(d["Date"], format="%Y/%m/%d", errors="coerce").notna()]
        d["Date"] = pd.to_datetime(d["Date"], format="%Y/%m/%d")
        parts.append(d[d["Date"] >= START])
    d = pd.concat(parts).drop_duplicates("Date", keep="last")
    return pd.concat([_frame(sid, d["Date"], d[col]) for sid, col in items])


# ---------------------------------------------------------------- store
def save(new: pd.DataFrame) -> pd.DataFrame:
    """Append only new or changed observations, stamped with this run's vintage time."""
    ts = pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None)
    new = new.copy()
    new["vintage_ts"] = ts
    if STORE.exists():
        old = pd.read_parquet(STORE)
        latest = old.sort_values("vintage_ts").groupby(["series_id", "date"]).tail(1)
        m = new.merge(latest[["series_id", "date", "value"]], on=["series_id", "date"], how="left", suffixes=("", "_old"))
        changed = m[m["value_old"].isna() | ((m["value"] - m["value_old"]).abs() > 1e-9)]
        add = changed[["series_id", "date", "value", "vintage_ts"]]
        allv = pd.concat([old, add], ignore_index=True)
    else:
        add, allv = new, new
    allv.to_parquet(STORE, index=False)
    latest = allv.sort_values("vintage_ts").groupby(["series_id", "date"]).tail(1).sort_values(["series_id", "date"])
    latest.to_parquet(LATEST, index=False)
    return add


def main() -> int:
    _load_env()
    reg = yaml.safe_load((ROOT / "config" / "series.yaml").read_text())["series"]
    frames, errors = [], []
    iadb, mof_items, estat_items = [], [], []
    import collect_g10 as G
    g10_groups: dict[str, list] = {}
    G10_SOURCES = {"boc", "statcan", "rba", "abs", "snb", "riksbank", "scb", "norgesbank", "ssb", "bundesbank"}
    for s in reg:
        sid, src, code = s["id"], s["source"], s["code"]
        try:
            if src == "fred":
                frames.append(fred(sid, code))
            elif src == "ecb":
                frames.append(ecb(sid, code))
            elif src == "eurostat_hicp":
                frames.append(eurostat_hicp(sid, code))
            elif src == "ons":
                frames.append(ons(sid, code))
            elif src == "boj":
                frames.append(boj(sid, code))
            elif src == "boe_iadb":
                iadb.append((sid, code))
            elif src == "mof":
                mof_items.append((sid, code))
            elif src == "estat":
                estat_items.append((sid, code))
            elif src in G10_SOURCES:
                g10_groups.setdefault(src, []).append((sid, code))
        except Exception as e:  # keep going; report at the end
            errors.append(f"{sid}: {e}")
    for name, fn in (("boe_iadb", lambda: boe_iadb(iadb)), ("mof", lambda: mof(mof_items)), ("boe_curve", boe_curves),
                     ("fred_dots_prior", fred_dots_prior), ("estat_cpi", lambda: estat_cpi(estat_items))):
        try:
            frames.append(fn())
        except Exception as e:
            errors.append(f"{name}: {e}")
    g10_fns = {
        "boc": lambda it: G.boc(_get, it, START), "statcan": lambda it: G.statcan(_post, it, START),
        "rba": lambda it: G.rba(_get, it, START), "abs": lambda it: G.abs_cpi(_get, it, START),
        "snb": lambda it: G.snb(_get, it, START), "riksbank": lambda it: G.riksbank(_get, it, START),
        "scb": lambda it: G.pxweb(_post, "https://api.scb.se/OV0104/v1/doris/en/ssd", it, START),
        "norgesbank": lambda it: G.norgesbank(_get, it, START),
        "ssb": lambda it: G.pxweb(_post, "https://data.ssb.no/api/v0/en/table", it, START),
        "bundesbank": lambda it: G.bundesbank(_get, it, START),
    }
    for src, items in g10_groups.items():
        try:
            frames.append(g10_fns[src](items))
        except Exception as e:
            errors.append(f"{src}: {e}")
    import collect_cn as CN
    for src, fn in (("pbc_omo", CN.pbc_omo), ("chinamoney", CN.chinamoney), ("chinabond", CN.chinabond)):
        items = [(s["id"], str(s["code"])) for s in reg if s["source"] == src]
        if items:
            try:
                frames.append(fn(items))
            except Exception as e:
                errors.append(f"{src}: {e}")
    for name, fn in (("treasury_auctions", lambda: G.treasury_auctions(_get)), ("cftc", lambda: G.cftc(_get))):
        try:
            fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
    try:
        release_calendar()
    except Exception as e:
        errors.append(f"release_calendar: {e}")
    data = pd.concat(frames, ignore_index=True)
    added = save(data)
    summary = data.groupby("series_id").agg(first=("date", "min"), last=("date", "max"), n=("value", "size"))
    print(summary.to_string())
    print(f"\n{len(added)} new/changed observations stored; {data.series_id.nunique()} series.")
    if errors:
        print("\nERRORS:\n" + "\n".join(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
