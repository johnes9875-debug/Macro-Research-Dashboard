"""China (CNY) collectors: PBoC open market operations, CFETS/ChinaMoney fixings, ChinaBond CGB curve.

All return long frames (series_id, date, value). Each collector fetches incrementally: from 10 days
before the last stored observation, or from BACKFILL on the first run, so the twice-daily runs stay
light. Codes used in config/series.yaml:

  pbc_omo       7D                          PBoC 7-day reverse repo rate (from each OMO announcement)
  chinamoney    LPR|1Y, LPR|5Y               loan prime rates
                FR|FR007, FR|FDR007          7-day repo fixing (all participants) and depository-institution fixing
                SHIBOR|3M (any Shibor tenor)
                CCPR|USD/CNY                 central parity fixing
  chinabond     2, 5, 10, 30 ...             CGB yield to maturity at that tenor (ChinaBond curve)
"""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BACKFILL = "2024-10-01"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
CM = "https://www.chinamoney.com.cn"
CB = "https://yield.chinabond.com.cn/cbweb-mn/yc/searchYc"
CGB_CURVE = "2c9081e50a2f9606010a3068cae70001"   # ChinaBond government bond yield curve (to maturity)
PBC = "https://www.pbc.gov.cn"
OMO_LIST = "/zhengcehuobisi/125207/125213/125431/125475"


def _frame(sid, dates, values):
    df = pd.DataFrame({"series_id": sid, "date": pd.to_datetime(dates), "value": pd.to_numeric(values, errors="coerce")})
    return df.dropna(subset=["value"])


def _since(sid: str) -> str:
    """Start date for an incremental pull: 10 days before the last stored point, else BACKFILL."""
    p = ROOT / "data" / "latest.parquet"
    if p.exists():
        d = pd.read_parquet(p, columns=["series_id", "date"])
        d = d[d.series_id == sid]
        if len(d):
            return (d.date.max() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    return BACKFILL


_S = threading.local()


def _session():
    if not hasattr(_S, "s"):
        _S.s = requests.Session()  # keep-alive: the TLS handshake to China is the slow part
    return _S.s


def _req(method, url, tries=4, **kw):
    """Chinese official sites throttle bursts and sometimes return an empty body; pause and retry."""
    last = None
    for i in range(tries):
        time.sleep(0.3 + i * 2)
        try:
            r = _session().request(method, url, headers={**UA, "Referer": kw.pop("referer", CM + "/english/")}, timeout=60, **kw)
            if r.status_code == 200 and r.text.strip():
                return r
            last = RuntimeError(f"HTTP {r.status_code} (empty={not r.text.strip()}) for {url[:120]}")
        except requests.RequestException as e:
            last = e
    raise last  # type: ignore[misc]


def _windows(start: str, days: int):
    a, end = pd.Timestamp(start), pd.Timestamp(date.today())
    while a <= end:
        b = min(a + pd.Timedelta(days=days - 1), end)
        yield a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")
        a = b + pd.Timedelta(days=1)


# ------------------------------------------------------------------ CFETS / ChinaMoney
def chinamoney(items):
    out = []
    for sid, code in items:
        kind, key = code.split("|", 1)
        rows = []
        if kind == "LPR":
            # The LPR endpoint ignores the date range and returns the last 12 fixings; history accumulates in the vintage store.
            j = _req("POST", f"{CM}/ags/ms/cm-u-bk-currency/LprHis", params={"lang": "EN"}).json()
            rows += [(r["showDateCN"], r.get(key)) for r in j.get("records", [])]
        elif kind == "SHIBOR":
            for a, b in _windows(_since(sid), 90):
                j = _req("POST", f"{CM}/ags/ms/cm-u-bk-shibor/ShiborHis", params={"lang": "EN", "startDate": a, "endDate": b}).json()
                rows += [(r["showDateCN"], r.get(key)) for r in j.get("records", [])]
        elif kind == "FR":
            for a, b in _windows(_since(sid), 30):
                j = _req("POST", f"{CM}/ags/ms/cm-u-bk-currency/FrrHis", params={"lang": "CN", "startDate": a, "endDate": b}).json()
                rows += [(r["lfiProducDate"], (r.get("frValueMap") or {}).get(key)) for r in j.get("records", [])]
        elif kind == "CCPR":
            for a, b in _windows(_since(sid), 30):
                j = _req("POST", f"{CM}/ags/ms/cm-u-bk-ccpr/CcprHisNew",
                         params={"startDate": a, "endDate": b, "currency": key, "pageNum": 1, "pageSize": 40}).json()
                rows += [(r["date"], (r.get("values") or [None])[0]) for r in j.get("records", [])]
        else:
            raise ValueError(f"unknown chinamoney code {code}")
        out.append(_frame(sid, [r[0] for r in rows], [r[1] for r in rows]).drop_duplicates(["series_id", "date"]))
    return pd.concat(out)


# ------------------------------------------------------------------ ChinaBond CGB curve (one request per business day)
def chinabond(items):
    tenors = {sid: float(code) for sid, code in items}
    start = min(_since(sid) for sid in tenors)
    days = pd.bdate_range(start, date.today())

    def one(d):
        ds = d.strftime("%Y-%m-%d")
        try:
            j = _req("POST", CB, tries=3, referer="https://yield.chinabond.com.cn/cbweb-mn/yield_main",
                     params={"xyzSelect": "txy", "workTimes": ds, "dxbj": "0", "qxll": "0,", "yqqxN": "N", "yqqxK": "K",
                             "ycDefIds": CGB_CURVE + ",", "wrjxCBFlag": "0", "locale": "zh_CN"}).json()
        except Exception:
            return []
        if not j or not j[0].get("seriesData"):
            return []  # holiday / no curve that day
        pts = dict((round(float(t), 4), float(y)) for t, y in j[0]["seriesData"])
        return [(sid, ds, pts[ten]) for sid, ten in tenors.items() if ten in pts]

    rows = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(one, days):
            rows += r
    d = pd.DataFrame(rows, columns=["series_id", "date", "value"])
    d["date"] = pd.to_datetime(d["date"])
    return d


# ------------------------------------------------------------------ PBoC 7-day reverse repo rate
_RATE = re.compile(r"7\s*天\s*(\d+\s*\.\s*\d+)\s*%")


def _omo_rate(path):
    t = _req("GET", PBC + path, referer=PBC + OMO_LIST + "/index.html").content.decode("utf-8", "replace")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    m = _RATE.search(t)
    return float(m.group(1).replace(" ", "")) if m else None


def pbc_omo(items):
    sid = items[0][0]
    since = pd.Timestamp(_since(sid))
    rows, page = [], 1
    while page <= 60:
        url = f"{OMO_LIST}/index.html" if page == 1 else f"{OMO_LIST}/17081-{page}.html"
        html = _req("GET", PBC + url, referer=PBC + OMO_LIST + "/index.html").content.decode("utf-8", "replace")
        # each list item: <a href=".../<id>/index.html" ...>title</a></font><span class="hui12">YYYY-MM-DD</span>
        links = [(p, y.replace("-", "")) for p, y in re.findall(
            rf'href="({OMO_LIST}/[^"/]+/index\.html)"[^>]*>[^<]*</a>\s*</font>\s*<span class="hui12">(\d{{4}}-\d{{2}}-\d{{2}})', html)]
        if not links:
            break
        todo = list(dict.fromkeys((p, y) for p, y in links if pd.Timestamp(y) >= since))

        def one(py):
            try:
                return pd.Timestamp(py[1]), _omo_rate(py[0])
            except Exception:
                return pd.Timestamp(py[1]), None
        with ThreadPoolExecutor(max_workers=4) as ex:
            rows += [x for x in ex.map(one, todo) if x[1] is not None]
        if min(pd.Timestamp(y) for _, y in links) < since:
            break
        page += 1
    d = _frame(sid, [r[0] for r in rows], [r[1] for r in rows]).drop_duplicates(["series_id", "date"])
    return d
