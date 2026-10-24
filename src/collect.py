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


def _get(url: str, **kw) -> requests.Response:
    """GET with 3 retries and backoff."""
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=90, **kw)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} for {url}: {r.text[:150]}")
        except requests.RequestException as e:  # network error
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
    files = {"glcnominalddata.zip": None, "oisddata.zip": None, "latest-yield-curve-data.zip": None}
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
    return pd.concat(frames)


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
    iadb, mof_items = [], []
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
        except Exception as e:  # keep going; report at the end
            errors.append(f"{sid}: {e}")
    for name, fn in (("boe_iadb", lambda: boe_iadb(iadb)), ("mof", lambda: mof(mof_items)), ("boe_curve", boe_curves)):
        try:
            frames.append(fn())
        except Exception as e:
            errors.append(f"{name}: {e}")
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
