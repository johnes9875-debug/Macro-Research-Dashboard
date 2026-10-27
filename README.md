# G10 rates monitor

A personal macro research pipeline for a G10 rates PM: it pulls official public data for nine G10 economies (USD, EUR, GBP, JPY, CAD, AUD, CHF, SEK, NOK, plus NZD macro), stores every release as a vintage, computes rates and macro metrics, and feeds a dashboard.

## What it covers

- **Rates:** policy and overnight rates; government curves (Treasuries, ECB AAA curve, Bunds, gilts, JGBs, GoC, ACGB, Confederations, SGBs, NGBs); GBP OIS curve; US real yields and breakevens.
- **Pricing:** BoE meeting-by-meeting pricing from the OIS forward curve; curve-based policy-path proxies for the other eight economies.
- **Relative value:** 2s10s, 5s30s, 2s5s10s butterflies and cross-market spreads with 1-year z-scores.
- **Macro:** inflation (headline, core, services), labour and growth for ten economies; Japan CPI from e-Stat.
- **Supply and positioning:** US Treasury coupon auction results (bid-to-cover, dealer/indirect/direct takedown vs recent average) and upcoming auctions; CFTC leveraged-fund positioning in UST, SOFR and G10 FX futures with 3-year z-scores.
- **Calendar:** next five weeks of US, euro area and UK data releases (FRED, Eurostat, ONS calendars) and central bank decisions, in Singapore time.
- **Fed and term premium:** FOMC dots vs Treasury forwards; US 10y split into expected path and Kim-Wright term premium.
- **Liquidity:** Fed balance sheet, reserves, reverse repo, TGA, SOFR/EFFR vs IORB.
- **Cross-asset:** VIX, credit spreads, financial conditions, dollar, FX vs 2y rate spreads with a rate-implied fair value.
- **Inflation expectations:** US breakevens, 5y5y and TIPS; UK implied RPI inflation and real yields from BoE curves.
- **Morning brief:** `data/outputs/brief_facts.json` feeds a daily email; `src/check_brief.py` rejects any number not in the facts.
- **Data health:** staleness of every series against its usual publication lag.

## Sources

FRED / ALFRED, ECB Data Portal, Eurostat (`prc_hicp_minr`, ECOICOP 2), ONS, Bank of England (IADB and yield-curve files), Bank of Japan Time-Series API, Japan Ministry of Finance JGB yields, e-Stat, Bank of Canada Valet, Statistics Canada, RBA tables, ABS Data API, SNB data portal, Riksbank SWEA/SWESTR, Statistics Sweden, Norges Bank, Statistics Norway, Deutsche Bundesbank, US Treasury Fiscal Data, CFTC TFF. Codes are in `config/series.yaml`.

## Run it

```bash
pip install -r requirements.txt
echo "FRED_API_KEY=your_key" > .env      # free key from fred.stlouisfed.org
echo "ESTAT_APP_ID=your_app_id" >> .env  # free app ID from api.e-stat.go.jp (Japan CPI)
./run_pipeline.sh
```

Outputs land in `data/outputs/dash/` (one JSON file per dashboard dataset). `data/vintages.parquet` keeps every value as first seen plus each revision, and is committed so history builds up across runs.

## Layout

```
config/    series registry, CB calendar, dashboard dataset list
src/       collect.py (sources, release calendars) · collect_g10.py (CAD, AUD, CHF, SEK, NOK, Bunds, auctions, CFTC) · compute.py (metrics) · monitor.py (grid, curves, RV, BoE strip, data health)
           extras.py (calendar, Fed dots, term premium, liquidity, cross-asset, FX vs rates, inflation expectations, auctions, positioning, brief facts)
           export_dashboard.py (dataset files) · publish_plan.py (dashboard update docs)
dashboard/ build_page.py (dashboard page)
data/      vintages.parquet (committed); raw/ and outputs/ are rebuilt each run
```

## Method notes

- US year-on-year rates are computed on the calendar, so a missing release (October 2025 CPI, US government shutdown) leaves a gap instead of shifting comparisons.
- BoE meeting pricing: expected Bank Rate after each MPC = average OIS instantaneous forward until the next meeting, less the SONIA–Bank Rate basis.
- Policy paths other than GBP are government-curve proxies (term premium and supply effects included). AUD uses bank bills (RBA OIS discontinued 2022); NOK uses the 3y (no 2y benchmark).
- CHF bond yields are daily but published monthly by the SNB. NZD is macro-only via FRED/OECD (RBNZ blocks automated access).
