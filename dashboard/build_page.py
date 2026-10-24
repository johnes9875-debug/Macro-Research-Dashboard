"""Generate the dashboard page (index.html) for the G10 Rates Monitor artifact — v2, tabbed monitor."""
from pathlib import Path

ECON = [("USD", "Fed"), ("EUR", "ECB"), ("GBP", "BoE"), ("JPY", "BoJ")]


def m(src, field, eco=None):
    where = f' data-where="economy={eco}"' if eco else ""
    return f'data-source="{src}" data-field="{field}"{where}'


def card(eco, cb):
    o = lambda f: m("overview", f, eco)
    return f"""
  <article class="g10-card" id="card-{eco}">
    <header class="g10-card-head"><span class="g10-eco">{eco}</span><span class="g10-cb" {o('cb')}>{cb}</span></header>
    <div class="g10-big-wrap">
      <div class="g10-big dash-skeleton" {o('priced_12m_bp')}></div>
      <div class="g10-big-note">bp priced vs policy, <span {o('priced_label')}></span> ahead
        <span class="g10-muted">· 1w <span {o('priced_chg_1w_bp')}></span></span></div>
    </div>
    <dl class="g10-rows">
      <div><dt>Policy rate</dt><dd><span {o('policy')}></span></dd></div>
      <div><dt>Next decision</dt><dd><span {o('next_meeting')}></span><span class="g10-sub" {o('next_meeting_sgt')}></span></dd></div>
      <div><dt>2y</dt><dd><span {o('y2')}></span><span class="g10-sub">1d <span {o('y2_chg_1d')}></span> · 1w <span {o('y2_chg_1w')}></span></span></dd></div>
      <div><dt>10y</dt><dd><span {o('y10')}></span><span class="g10-sub">1d <span {o('y10_chg_1d')}></span> · 1w <span {o('y10_chg_1w')}></span></span></dd></div>
      <div><dt>2s10s</dt><dd><span {o('s2s10s')}></span><span class="g10-sub">1w <span {o('s2s10s_chg_1w')}></span> · 1m <span {o('s2s10s_chg_1m')}></span></span></dd></div>
    </dl>
  </article>"""


def small(eco, kind, src, note=""):
    return f"""
    <div class="g10-small">
      <h3 class="g10-small-title">{eco}</h3>
      <div class="g10-chart" id="{kind}-{eco}" data-source="{src}"></div>{note}
    </div>"""


TABS = [("overview", "Overview"), ("curves", "Curves & RV"), ("pricing", "Policy pricing"), ("macro", "Macro"), ("health", "Data health")]
tabbar = "".join(f'<button class="g10-tab" role="tab" data-tab="{t}" id="tab-{t}">{n}</button>' for t, n in TABS)

HTML = f"""<style>
.g10 {{ font-family: var(--font-anthropic-sans); color: var(--color-fg); display: flex; flex-direction: column; gap: var(--cds-gap-lg); }}
.g10-title {{ font-family: var(--font-anthropic-serif); font-weight: 400; font-size: var(--cds-font-size-title); margin: 0; }}
.g10-lede {{ margin: var(--cds-gap-xs) 0 0; color: var(--color-fg-muted); font-size: var(--cds-font-size-body); max-width: 64rem; }}
.g10-lede b {{ color: var(--color-fg); font-weight: 600; font-variant-numeric: tabular-nums; }}
.g10-asof {{ margin: var(--cds-gap-xs) 0 0; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }}
.g10-tabs {{ display: flex; gap: 2px; border-bottom: 1px solid var(--color-border-line); overflow-x: auto; position: sticky; top: 0; background: var(--color-bg); z-index: 3; }}
.g10-tab {{ font: inherit; font-size: var(--cds-font-size-body); background: none; border: 0; border-bottom: 2px solid transparent; color: var(--color-fg-muted); padding: var(--cds-pad-sm) var(--cds-pad-md); cursor: pointer; white-space: nowrap; }}
.g10-tab[aria-selected="true"] {{ color: var(--color-fg); border-bottom-color: var(--color-fg); font-weight: var(--cds-font-weight-medium); }}
.g10-pane {{ display: flex; flex-direction: column; gap: var(--cds-gap-lg); }}
.g10-pane[hidden] {{ display: none; }}
.g10-section > h2 {{ font-size: var(--cds-font-size-heading); font-weight: var(--cds-font-weight-medium); margin: 0 0 var(--cds-gap-xs); }}
.g10-sec-note {{ margin: 0 0 var(--cds-gap-sm); color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); max-width: 64rem; }}
.g10-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: var(--cds-gap-md); }}
.g10-grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 26rem), 1fr)); gap: var(--cds-gap-md); }}
.g10-card, .g10-panel {{ background: var(--color-panel); border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: var(--cds-pad-md); }}
.g10-card-head {{ display: flex; justify-content: space-between; align-items: baseline; }}
.g10-eco {{ font-weight: var(--cds-font-weight-medium); font-size: var(--cds-font-size-heading); }}
.g10-cb {{ color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }}
.g10-big-wrap {{ margin: var(--cds-gap-xs) 0 var(--cds-gap-sm); }}
.g10-big {{ font-family: var(--font-anthropic-serif); font-weight: 400; font-size: calc(var(--cds-font-size-title) * 1.5); line-height: 1.1; font-variant-numeric: tabular-nums; min-height: 2.4rem; }}
.g10-big-note {{ color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }}
.g10-rows {{ margin: 0; display: grid; gap: 4px; font-size: var(--cds-font-size-caption); }}
.g10-rows > div {{ display: flex; justify-content: space-between; gap: var(--cds-gap-sm); border-top: 1px solid var(--color-border-line); padding-top: 4px; }}
.g10-rows dt {{ color: var(--color-fg-muted); }}
.g10-rows dd {{ margin: 0; text-align: right; font-variant-numeric: tabular-nums; display: flex; flex-direction: column; align-items: flex-end; font-size: var(--cds-font-size-body); }}
.g10-sub {{ font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); }}
.g10-muted {{ color: var(--color-fg-muted); }}
.g10-small {{ background: var(--color-panel); border: 1px solid var(--color-border-line); border-radius: var(--cds-radius); padding: var(--cds-pad-md); display: flex; flex-direction: column; }}
.g10-small-title {{ margin: 0 0 var(--cds-gap-xs); font-size: var(--cds-font-size-body); font-weight: var(--cds-font-weight-medium); }}
.g10-chart {{ position: relative; min-height: 190px; }}
.g10-note {{ margin: var(--cds-gap-xs) 0 0; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }}
.g10-legend {{ display: flex; flex-wrap: wrap; gap: var(--cds-gap-md); font-size: var(--cds-font-size-caption); color: var(--color-fg-muted); margin-bottom: var(--cds-gap-xs); }}
.g10-legend i {{ display: inline-block; width: 14px; height: 2px; margin-right: 6px; vertical-align: middle; }}
.g10-tip {{ position: absolute; pointer-events: none; background: var(--cds-surface-popover); border: 1px solid var(--cds-border); border-radius: var(--cds-radius); box-shadow: var(--cds-shadow-popover); padding: var(--cds-pad-xs) var(--cds-pad-sm); font-size: var(--cds-font-size-caption); white-space: nowrap; z-index: 2; display: none; }}
.g10-tip .d {{ color: var(--cds-text-secondary); margin-bottom: 2px; }}
.g10-tip .sw {{ display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; }}
.g10-table-wrap {{ overflow-x: auto; }}
.g10-table {{ width: 100%; border-collapse: collapse; font-size: var(--cds-font-size-caption); font-variant-numeric: tabular-nums; }}
.g10-table th {{ text-align: right; font-weight: var(--cds-font-weight-medium); color: var(--color-fg-muted); padding: 4px 8px; border-bottom: 1px solid var(--color-border-line); white-space: nowrap; position: sticky; top: 0; background: var(--color-panel); }}
.g10-table td {{ text-align: right; padding: 3px 8px; border-bottom: 1px solid var(--color-border-line); white-space: nowrap; }}
.g10-table .l {{ text-align: left; }}
.g10-table tr.g10-grp td {{ border-top: 1px solid var(--cds-chart-axis); }}
.g10-table td.g10-eco-cell {{ font-weight: var(--cds-font-weight-medium); }}
.g10-heat {{ border-radius: 3px; }}
.g10-rng {{ display: inline-flex; align-items: center; gap: 6px; }}
.g10-rng-track {{ position: relative; width: 64px; height: 4px; border-radius: 2px; background: var(--cds-chart-grid); }}
.g10-rng-dot {{ position: absolute; top: -3px; width: 2px; height: 10px; background: var(--color-fg); }}
.g10-warn {{ color: var(--color-warn); }}
.g10-bad {{ color: var(--color-bad); font-weight: var(--cds-font-weight-medium); }}
.g10-ok {{ color: var(--color-ok); }}
.g10-scroll {{ max-height: 32rem; overflow: auto; }}
.g10-footer {{ color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); border-top: 1px solid var(--color-border-line); padding-top: var(--cds-gap-md); }}
.g10-footer p {{ margin: 0 0 var(--cds-gap-xs); }}
[data-dash-source-state=empty] {{ color: transparent; }}
[data-dash-source-state=refreshing] {{ opacity: .5; transition: opacity var(--cds-dur-slow); }}
.g10-fail {{ display: flex; align-items: center; justify-content: center; gap: 8px; min-height: inherit; height: 100%; color: var(--color-fg-muted); font-size: var(--cds-font-size-caption); }}
.g10-fail::before {{ content: ""; width: .375rem; height: .375rem; border-radius: 50%; background: var(--color-bad); }}
.g10 svg text {{ font-family: var(--font-anthropic-sans); }}
</style>

<div class="g10">
  <header>
    <h1 class="g10-title" id="top">G10 rates monitor</h1>
    <p class="g10-lede" id="takeaway">Priced vs today's policy rate, 12 months out:
      USD <b {m('overview','priced_12m_bp','USD')}></b>bp ·
      EUR <b {m('overview','priced_12m_bp','EUR')}></b>bp ·
      GBP <b {m('overview','priced_12m_bp','GBP')}></b>bp ·
      JPY <b {m('overview','priced_12m_bp','JPY')}></b>bp.
      BoE OIS prices <b data-source="boe_meetings" data-field="change_bp" data-row="0"></b>bp at the
      <span data-source="boe_meetings" data-field="date" data-row="0"></span> MPC.
      Next decision: <b data-source="calendar" data-field="cb" data-row="0"></b>,
      <span data-source="calendar" data-field="sgt" data-row="0"></span> SGT.</p>
    <p class="g10-asof">Official public data (FRED, ECB, Eurostat, ONS, Bank of England, Bank of Japan, Japan MoF). US closes as of
      <span {m('overview','y10_date','USD')}></span>. Changes in basis points.</p>
  </header>

  <nav class="g10-tabs" role="tablist">{tabbar}</nav>

  <!-- ===================== OVERVIEW ===================== -->
  <div class="g10-pane" id="pane-overview" role="tabpanel">
    <div class="g10-grid">{''.join(card(e, cb) for e, cb in ECON)}
    </div>

    <section class="g10-section" id="grid">
      <h2>Rates monitor</h2>
      <p class="g10-sec-note">Level and change in bp. Shading: <span id="heat-key"></span>. The 1y bar shows where today's level sits in its one-year range.</p>
      <div class="g10-panel g10-table-wrap">
        <table class="g10-table" id="grid-table" data-source="rates_grid" data-row-key="key">
          <thead><tr><th data-field="economy" class="l"></th><th data-field="instrument" class="l">Instrument</th><th data-field="level">Level %</th><th data-field="chg_1d">1d</th><th data-field="chg_1w">1w</th><th data-field="chg_1m">1m</th><th data-field="chg_3m">3m</th><th data-field="chg_ytd">YTD</th><th data-field="pct_1y">1y percentile</th><th data-field="date">As of</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <section class="g10-section" id="cal">
      <h2>Central bank calendar</h2>
      <div class="g10-panel g10-table-wrap">
        <table class="g10-table" id="cal-table" data-source="calendar" data-row-key="key">
          <thead><tr><th data-field="date" class="l">Decision</th><th data-field="cb" class="l">Central bank</th><th data-field="economy" class="l">Currency</th><th data-field="sgt" class="l">Singapore time</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>
  </div>

  <!-- ===================== CURVES & RV ===================== -->
  <div class="g10-pane" id="pane-curves" role="tabpanel" hidden>
    <section class="g10-section" id="snapshots">
      <h2>Curve snapshots</h2>
      <p class="g10-sec-note">Government curves today vs one week and one month ago (tenor on a log scale). GBP mixes the BoE 2y spot with 5y–20y par yields; EUR is the ECB AAA curve.</p>
      <div class="g10-legend" id="snap-legend"></div>
      <div class="g10-grid">{''.join(small(e, 'snap', 'curves') for e, _ in ECON)}
      </div>
    </section>

    <section class="g10-section" id="rv">
      <h2>Curve relative value</h2>
      <p class="g10-sec-note">Slopes and the 2s5s10s butterfly (2×5y − 2y − 10y; negative = 5y rich vs the wings). z-score vs the past year; |z| ≥ 1.5 highlighted.</p>
      <div class="g10-grid-2">
        <div class="g10-panel g10-table-wrap">
          <table class="g10-table" id="rv-table" data-source="curve_rv" data-row-key="key">
            <thead><tr><th data-field="economy" class="l"></th><th data-field="measure" class="l">Measure</th><th data-field="value_bp">bp</th><th data-field="chg_1w">1w</th><th data-field="chg_1m">1m</th><th data-field="z_1y">z (1y)</th><th data-field="low_1y">1y low</th><th data-field="high_1y">1y high</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="g10-panel g10-table-wrap">
          <table class="g10-table" id="spreads-table" data-source="spreads" data-row-key="name">
            <thead><tr><th data-field="name" class="l">Cross-market spread</th><th data-field="value_bp">bp</th><th data-field="chg_1w_bp">1w</th><th data-field="chg_1m_bp">1m</th><th data-field="z_1y">z (1y)</th><th data-field="low_1y">1y low</th><th data-field="high_1y">1y high</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="g10-section" id="spread-hist">
      <h2>Cross-market spreads, weekly</h2>
      <div class="g10-panel">
        <div class="g10-legend" id="spreads-legend"></div>
        <div class="g10-chart" id="spreads-chart" data-source="spreads_hist" style="min-height:260px"></div>
      </div>
    </section>

    <section class="g10-section" id="yields">
      <h2>2y and 10y yields with policy rate, two years</h2>
      <div class="g10-legend" id="yields-legend"></div>
      <div class="g10-grid">{''.join(small(e, 'yld', 'yields_hist') for e, _ in ECON)}
      </div>
    </section>
  </div>

  <!-- ===================== POLICY PRICING ===================== -->
  <div class="g10-pane" id="pane-pricing" role="tabpanel" hidden>
    <section class="g10-section" id="boe">
      <h2>Bank of England: meeting-by-meeting pricing</h2>
      <p class="g10-sec-note">Expected Bank Rate after each MPC meeting, from the BoE OIS instantaneous forward curve (average forward until the next meeting, adjusted for the SONIA–Bank Rate basis). Curve date <span data-source="boe_meetings" data-field="curve_date" data-row="0"></span>.
        Bars: cumulative bp vs today's Bank Rate; tick: one week earlier.</p>
      <div class="g10-grid-2">
        <div class="g10-panel"><div class="g10-chart" id="boe-chart" data-source="boe_meetings" style="min-height:240px"></div></div>
        <div class="g10-panel g10-table-wrap">
          <table class="g10-table" id="boe-table" data-source="boe_meetings" data-row-key="date">
            <thead><tr><th data-field="date" class="l">MPC</th><th data-field="implied_rate">Implied rate %</th><th data-field="change_bp">At meeting</th><th data-field="hike_odds_pct">25bp odds %</th><th data-field="cumulative_bp">Cumulative</th><th data-field="cumulative_bp_1w">1w ago</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="g10-section" id="paths">
      <h2>Market-implied path, all four</h2>
      <p class="g10-sec-note">bp above (+) or below (−) today's policy rate, by months ahead. Solid: latest; dashed: one week earlier. Shared scale.</p>
      <div class="g10-grid">{''.join(small(e, 'path', 'implied_path overview', f'<p class="g10-note" {m("overview", "path_quality", e)}></p>') for e, _ in ECON)}
      </div>
    </section>
  </div>

  <!-- ===================== MACRO ===================== -->
  <div class="g10-pane" id="pane-macro" role="tabpanel" hidden>
    <section class="g10-section" id="macro">
      <h2>Inflation, labour and growth</h2>
      <p class="g10-sec-note">Latest print vs prior. Japan CPI not yet collected (needs a free e-Stat app ID).</p>
      <div class="g10-grid-2">
        <div class="g10-panel g10-table-wrap">
          <table class="g10-table" id="macro-table" data-source="macro_latest" data-row-key="key">
            <thead><tr><th data-field="economy" class="l"></th><th data-field="metric" class="l">Measure</th><th data-field="value">Latest</th><th data-field="prior">Prior</th><th data-field="change">Change</th><th data-field="period">Period</th></tr></thead>
            <tbody></tbody>
          </table>
        </div>
        <div class="g10-panel">
          <h3 class="g10-small-title">Headline and core inflation, y/y %</h3>
          <div class="g10-legend" id="infl-legend"></div>
          <div class="g10-chart" id="infl-USD" data-source="macro_hist" style="min-height:150px"></div>
          <div class="g10-chart" id="infl-EUR" data-source="macro_hist" style="min-height:150px"></div>
          <div class="g10-chart" id="infl-GBP" data-source="macro_hist" style="min-height:150px"></div>
          <h3 class="g10-small-title" style="margin-top: var(--cds-gap-md)">Unemployment rate, %</h3>
          <div class="g10-chart" id="unemp-chart" data-source="macro_hist" style="min-height:180px"></div>
        </div>
      </div>
    </section>
  </div>

  <!-- ===================== DATA HEALTH ===================== -->
  <div class="g10-pane" id="pane-health" role="tabpanel" hidden>
    <section class="g10-section" id="health">
      <h2>Data health</h2>
      <p class="g10-sec-note">Every series the monitor uses, with its latest observation. A series is stale when it is older than its usual publication lag (daily 5 days, weekly 12, monthly 75, quarterly 200, measured from the end of the period). Stale series are listed first.</p>
      <div class="g10-panel g10-table-wrap g10-scroll">
        <table class="g10-table" id="health-table" data-source="data_health" data-row-key="series">
          <thead><tr><th data-field="status" class="l">Status</th><th data-field="series" class="l">Series</th><th data-field="economy" class="l">Currency</th><th data-field="name" class="l">Description</th><th data-field="source" class="l">Source</th><th data-field="frequency" class="l">Freq</th><th data-field="last_obs">Last observation</th><th data-field="age_days">Age (days)</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </section>
  </div>

  <footer class="g10-footer">
    <p>Pricing: GBP uses the Bank of England OIS forward curve. USD (Treasury bills/notes vs the fed funds midpoint), EUR (ECB AAA curve vs the deposit rate) and JPY (JGB 1y/2y vs the call rate) are government-curve proxies that carry term premium and supply effects: read direction and shape, not exact bp.</p>
    <p>Euro area HICP comes from Eurostat's 2026 ECOICOP 2 dataset. US year-on-year rates are computed on the calendar, so the missing October 2025 CPI (US government shutdown) does not distort them.</p>
  </footer>
</div>

<script>
(() => {{
  const ECO = ['USD', 'EUR', 'GBP', 'JPY'];
  const C = dash.colors;
  const sgn = (v, d = 0) => (v == null || isNaN(v)) ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
  const pct = (v, d = 2) => (v == null || isNaN(v)) ? '—' : v.toFixed(d) + '%';
  const num = (v, d = 1) => (v == null || isNaN(v)) ? '—' : (v < 0 ? '−' : '') + Math.abs(v).toFixed(d);
  const fmtDate = d3.utcFormat('%-d %b %Y');
  const parse = s => new Date(s + 'T00:00:00Z');
  const N = v => v == null ? null : Number(v);

  // ---------- tabs
  const renders = [];
  const runAll = () => renders.forEach(fn => fn());
  const show = (name, push) => {{
    document.querySelectorAll('.g10-tab').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    document.querySelectorAll('.g10-pane').forEach(p => p.hidden = p.id !== 'pane-' + name);
    if (push) dash.setLink('tab-' + name);
    runAll();
  }};
  document.querySelectorAll('.g10-tab').forEach(b => b.addEventListener('click', () => show(b.dataset.tab, true)));
  const h = location.hash.slice(1);
  const startTab = h.startsWith('tab-') ? h.slice(4) : 'overview';
  document.querySelectorAll('.g10-tab').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === startTab)));
  document.querySelectorAll('.g10-pane').forEach(p => p.hidden = p.id !== 'pane-' + startTab);

  // ---------- helpers
  const failBox = el => {{ el.innerHTML = ''; const d = document.createElement('div'); d.className = 'g10-fail'; d.textContent = 'Failed to load'; el.appendChild(d); }};
  const bad = st => st === 'error' || st === 'missing' || st === 'declined';
  const td = (tr, text, cls) => {{ const c = document.createElement('td'); c.textContent = text; if (cls) c.className = cls; tr.appendChild(c); return c; }};
  const legend = (id, items) => {{
    const el = document.getElementById(id); if (!el) return; el.innerHTML = '';
    items.forEach(([name, color, dash]) => {{ const s = document.createElement('span'); const i = document.createElement('i'); i.style.background = dash ? 'none' : color; if (dash) i.style.borderTop = `2px dashed ${{color}}`; s.appendChild(i); s.appendChild(document.createTextNode(name)); el.appendChild(s); }});
  }};
  const visible = el => el && el.offsetParent !== null;

  function lineChart(el, series, opt) {{
    el.innerHTML = '';
    const W = Math.max(260, el.clientWidth || 300), H = opt.height || 190;
    const all = series.flatMap(s => s.points).filter(p => p.y != null);
    if (!all.length) return;
    const x = (opt.xType === 'linear' ? d3.scaleLinear() : opt.xType === 'log' ? d3.scaleLog() : d3.scaleUtc()).domain(opt.xDomain || d3.extent(all, p => p.x));
    const y = d3.scaleLinear().domain(opt.yDomain || d3.extent(all, p => p.y)).nice();
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${{W}} ${{H}}`).attr('role', 'img').attr('aria-label', opt.label || 'chart');
    const yTicks = y.ticks(4);
    const tmp = svg.append('text').attr('font-size', 11).text(yTicks.map(opt.yFmt).reduce((a, b) => a.length > b.length ? a : b, ''));
    const yw = tmp.node().getComputedTextLength(); tmp.remove();
    const mg = {{ t: 8, r: opt.endLabels ? 72 : 12, b: 22, l: yw + 10 }};
    x.range([mg.l, W - mg.r]); y.range([H - mg.b, mg.t]);
    const g = svg.append('g');
    g.append('g').selectAll('line').data(yTicks).join('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y).attr('y2', y).attr('stroke', 'var(--cds-chart-grid)');
    g.append('g').selectAll('text').data(yTicks).join('text').attr('x', mg.l - 6).attr('y', d => y(d) + 4).attr('text-anchor', 'end').attr('font-size', 11).attr('fill', 'var(--color-fg-muted)').text(opt.yFmt);
    const xTicks = opt.xTicks || x.ticks(Math.max(2, Math.floor((W - mg.l - mg.r) / 90)));
    g.append('g').selectAll('text').data(xTicks).join('text').attr('x', x).attr('y', H - 6).attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--color-fg-muted)').text(opt.xFmt);
    if (opt.zero && y.domain()[0] < 0 && y.domain()[1] > 0)
      g.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--cds-chart-axis)');
    series.forEach(s => {{
      const line = (s.step ? d3.line().curve(d3.curveStepAfter) : d3.line()).x(p => x(p.x)).y(p => y(p.y)).defined(p => p.y != null);
      g.append('path').datum(s.points).attr('fill', 'none').attr('stroke', s.color).attr('stroke-width', s.width || 2)
        .attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round').attr('stroke-dasharray', s.dash || null).attr('d', line);
      if (s.dots) g.append('g').selectAll('circle').data(s.points.filter(p => p.y != null)).join('circle').attr('cx', p => x(p.x)).attr('cy', p => y(p.y)).attr('r', 2.5).attr('fill', s.color);
    }});
    if (opt.endLabels) {{
      const ends = series.map(s => ({{ s, p: s.points.filter(p => p.y != null).slice(-1)[0] }})).filter(e => e.p).map(e => ({{ ...e, ty: y(e.p.y) }})).sort((a, b) => a.ty - b.ty);
      for (let i = 1; i < ends.length; i++) if (ends[i].ty - ends[i - 1].ty < 13) ends[i].ty = ends[i - 1].ty + 13;
      ends.forEach(e => g.append('text').attr('x', W - mg.r + 6).attr('y', e.ty + 4).attr('font-size', 11).attr('fill', e.s.color).text(e.s.short + ' ' + opt.yFmt(e.p.y)));
    }}
    const tip = document.createElement('div'); tip.className = 'g10-tip'; el.appendChild(tip);
    const rule = g.append('line').attr('y1', mg.t).attr('y2', H - mg.b).attr('stroke', 'var(--cds-chart-axis)').style('display', 'none');
    const dots = series.map(s => g.append('circle').attr('r', 4).attr('fill', s.color).style('display', 'none'));
    svg.append('rect').attr('x', mg.l).attr('y', mg.t).attr('width', W - mg.l - mg.r).attr('height', H - mg.t - mg.b).attr('fill', 'transparent')
      .on('mousemove', ev => {{
        const [mx] = d3.pointer(ev);
        const xv = x.invert(mx);
        const rows = series.map(s => {{ const pts = s.points.filter(p => p.y != null); const i = d3.bisector(p => p.x).center(pts, xv); return {{ s, p: pts[i] }}; }}).filter(r => r.p);
        if (!rows.length) return;
        const px = x(rows[rows.length - 1].p.x);
        rule.attr('x1', px).attr('x2', px).style('display', null);
        rows.forEach(r => dots[series.indexOf(r.s)].attr('cx', x(r.p.x)).attr('cy', y(r.p.y)).style('display', null));
        tip.innerHTML = '';
        const dd = document.createElement('div'); dd.className = 'd'; dd.textContent = opt.tipX(rows[rows.length - 1].p.x, rows[rows.length - 1].p); tip.appendChild(dd);
        rows.forEach(r => {{ const line = document.createElement('div'); const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = r.s.color; line.appendChild(sw); line.appendChild(document.createTextNode(r.s.name + '  ' + opt.yFmt(r.p.y))); tip.appendChild(line); }});
        tip.style.display = 'block';
        const sc = el.clientWidth / W;
        let left = px * sc + 12; if (left + tip.offsetWidth > el.clientWidth) left = px * sc - tip.offsetWidth - 12;
        tip.style.left = Math.max(0, left) + 'px'; tip.style.top = '4px';
      }})
      .on('mouseleave', () => {{ tip.style.display = 'none'; rule.style('display', 'none'); dots.forEach(d => d.style('display', 'none')); }});
  }}

  // ---------- header + cards
  renders.push(() => {{
    const ov = dash.data('overview'), cal = dash.data('calendar'), bm = dash.data('boe_meetings');
    if (ov.status === 'ok') {{
      const by = Object.fromEntries(ov.data.map(r => [r.economy, r]));
      document.querySelectorAll('[data-source="overview"][data-field]').forEach(el => {{
        const r = by[(el.dataset.where || '').split('=')[1]]; if (!r) return;
        const f = el.dataset.field, v = r[f];
        el.classList.remove('dash-skeleton');
        if (/_chg_|priced_12m_bp|priced_chg/.test(f)) el.textContent = sgn(N(v));
        else if (f === 'policy') el.textContent = pct(N(v), Math.round(N(v) * 1000) % 10 ? 3 : 2);
        else if (['y2', 'y10', 'ylong'].includes(f)) el.textContent = pct(N(v));
        else if (f === 's2s10s') el.textContent = sgn(N(v)) + 'bp';
        else if (f === 'next_meeting' || f.endsWith('_date')) el.textContent = v ? fmtDate(parse(v)) : '—';
        else el.textContent = v ?? '—';
      }});
    }} else if (ov.status !== 'loading') document.querySelectorAll('.g10-big').forEach(el => {{ el.classList.remove('dash-skeleton'); el.textContent = '—'; }});
    if (cal.status === 'ok' && cal.data.length) {{
      const r0 = cal.data[0];
      document.querySelectorAll('[data-source="calendar"][data-row="0"]').forEach(el => el.textContent = r0[el.dataset.field]);
    }}
    if (bm.status === 'ok' && bm.data.length) {{
      const r0 = bm.data[0];
      document.querySelectorAll('[data-source="boe_meetings"][data-row="0"]').forEach(el => {{
        const f = el.dataset.field;
        el.textContent = f === 'change_bp' ? sgn(N(r0[f]), 1) : fmtDate(parse(r0[f]));
      }});
    }}
  }});

  // ---------- rates grid heatmap
  const CAP = {{ chg_1d: 15, chg_1w: 25, chg_1m: 40, chg_3m: 60, chg_ytd: 100 }};
  const heat = (v, cap) => {{
    if (v == null || v === 0) return '';
    const a = Math.round(Math.min(1, Math.abs(v) / cap) * 45);
    return `color-mix(in srgb, ${{v > 0 ? C[1] : C[0]}} ${{a}}%, transparent)`;
  }};
  renders.push(() => {{
    const key = document.getElementById('heat-key'); key.innerHTML = '';
    [['yields up', C[1]], ['yields down', C[0]]].forEach(([t, c], i) => {{ const s = document.createElement('span'); s.textContent = t; s.style.background = `color-mix(in srgb, ${{c}} 35%, transparent)`; s.style.padding = '0 4px'; s.style.borderRadius = '3px'; if (i) key.appendChild(document.createTextNode(' / ')); key.appendChild(s); }});
    const gd = dash.data('rates_grid');
    const tb = document.querySelector('#grid-table tbody');
    if (gd.status !== 'ok') return;
    tb.innerHTML = '';
    let last = null;
    gd.data.forEach(r => {{
      const tr = document.createElement('tr'); tr.dataset.key = r.key;
      if (last && r.economy !== last) tr.className = 'g10-grp';
      td(tr, r.economy !== last ? r.economy : '', 'l g10-eco-cell');
      td(tr, r.instrument, 'l');
      td(tr, N(r.level).toFixed(2));
      ['chg_1d', 'chg_1w', 'chg_1m', 'chg_3m', 'chg_ytd'].forEach(f => {{ const c = td(tr, sgn(N(r[f]))); c.style.background = heat(N(r[f]), CAP[f]); c.classList.add('g10-heat'); }});
      const pc = td(tr, ''); const wrap = document.createElement('span'); wrap.className = 'g10-rng';
      const track = document.createElement('span'); track.className = 'g10-rng-track'; const dot = document.createElement('span'); dot.className = 'g10-rng-dot'; dot.style.left = `calc(${{N(r.pct_1y)}}% - 1px)`; track.appendChild(dot);
      wrap.appendChild(track); wrap.appendChild(document.createTextNode(String(N(r.pct_1y)))); pc.appendChild(wrap);
      if (N(r.pct_1y) >= 90 || N(r.pct_1y) <= 10) pc.classList.add('g10-warn');
      td(tr, d3.utcFormat('%-d %b')(parse(r.date)));
      last = r.economy;
      tb.appendChild(tr);
    }});
  }});

  // ---------- calendar
  renders.push(() => {{
    const cal = dash.data('calendar'); if (cal.status !== 'ok') return;
    const tb = document.querySelector('#cal-table tbody'); tb.innerHTML = '';
    cal.data.forEach(r => {{ const tr = document.createElement('tr'); tr.dataset.key = r.key; td(tr, fmtDate(parse(r.date)), 'l'); td(tr, r.cb, 'l'); td(tr, r.economy, 'l'); td(tr, r.sgt, 'l'); tb.appendChild(tr); }});
  }});

  // ---------- curve snapshots
  renders.push(() => {{
    legend('snap-legend', [['Today', C[0]], ['1 week ago', 'var(--cds-chart-muted)', true], ['1 month ago', 'var(--cds-chart-muted)']]);
    const cv = dash.data('curves');
    ECO.forEach(e => {{
      const el = document.getElementById('snap-' + e);
      if (bad(cv.status)) return failBox(el);
      if (cv.status !== 'ok' || !visible(el)) return;
      const rows = cv.data.filter(r => r.economy === e).map(r => ({{ ...r, years: N(r.years) }}));
      const all = cv.data.flatMap(r => [N(r.now), N(r.wk), N(r.mo)]).filter(v => v != null);
      const mk = f => rows.map(r => ({{ x: r.years, y: N(r[f]), label: r.tenor }}));
      lineChart(el, [
        {{ name: '1 month ago', color: 'var(--cds-chart-muted)', width: 1.5, points: mk('mo') }},
        {{ name: '1 week ago', color: 'var(--cds-chart-muted)', dash: '4 3', width: 1.5, points: mk('wk') }},
        {{ name: 'Today', color: C[0], dots: true, points: mk('now') }},
      ], {{ xType: 'log', xDomain: [d3.min(cv.data, r => N(r.years)), 30], xTicks: rows.map(r => r.years), xFmt: v => (rows.find(r => r.years === v) || {{}}).tenor || '',
            yDomain: [Math.min(0, d3.min(all)), d3.max(all)], yFmt: v => v.toFixed(1) + '%', tipX: (v, p) => p.label, label: e + ' curve snapshot' }});
    }});
  }});

  // ---------- RV + spreads tables
  const zCls = z => Math.abs(z) >= 1.5 ? 'g10-warn' : '';
  renders.push(() => {{
    const rv = dash.data('curve_rv');
    if (rv.status === 'ok') {{
      const tb = document.querySelector('#rv-table tbody'); tb.innerHTML = ''; let last = null;
      rv.data.forEach(r => {{
        const tr = document.createElement('tr'); tr.dataset.key = r.key; if (last && r.economy !== last) tr.className = 'g10-grp';
        td(tr, r.economy !== last ? r.economy : '', 'l g10-eco-cell'); td(tr, r.measure, 'l');
        td(tr, sgn(N(r.value_bp))); td(tr, sgn(N(r.chg_1w))); td(tr, sgn(N(r.chg_1m))); td(tr, num(N(r.z_1y), 1), zCls(N(r.z_1y))); td(tr, sgn(N(r.low_1y))); td(tr, sgn(N(r.high_1y)));
        last = r.economy; tb.appendChild(tr);
      }});
    }}
    const sp = dash.data('spreads');
    if (sp.status === 'ok') {{
      const tb = document.querySelector('#spreads-table tbody'); tb.innerHTML = '';
      sp.data.forEach(r => {{ const tr = document.createElement('tr'); td(tr, r.name, 'l'); td(tr, sgn(N(r.value_bp))); td(tr, sgn(N(r.chg_1w_bp))); td(tr, sgn(N(r.chg_1m_bp))); td(tr, num(N(r.z_1y), 1), zCls(N(r.z_1y))); td(tr, sgn(N(r.low_1y))); td(tr, sgn(N(r.high_1y))); tb.appendChild(tr); }});
    }}
  }});

  // ---------- spreads history
  renders.push(() => {{
    const sh = dash.data('spreads_hist'), el = document.getElementById('spreads-chart');
    if (bad(sh.status)) return failBox(el);
    if (sh.status !== 'ok' || !visible(el)) return;
    const names = [...new Set(sh.data.map(r => r.name))];
    legend('spreads-legend', names.map((n, i) => [n, C[i]]));
    lineChart(el, names.map((n, i) => ({{ name: n, color: C[i], points: sh.data.filter(r => r.name === n).map(r => ({{ x: parse(r.date), y: N(r.value_bp) }})) }})),
      {{ height: 260, yFmt: v => sgn(v), xFmt: d3.utcFormat("%b '%y"), tipX: v => 'Week to ' + fmtDate(v), zero: true, label: 'Cross-market spreads' }});
  }});

  // ---------- yields history
  renders.push(() => {{
    legend('yields-legend', [['2y', C[0]], ['10y', C[1]], ['Policy rate', 'var(--cds-chart-muted)']]);
    const yh = dash.data('yields_hist');
    if (bad(yh.status)) return ECO.forEach(e => failBox(document.getElementById('yld-' + e)));
    if (yh.status !== 'ok' || !visible(document.getElementById('yld-USD'))) return;
    const vals = yh.data.map(r => N(r.value));
    const yDomain = [Math.min(0, d3.min(vals)), d3.max(vals)];
    ECO.forEach(e => {{
      const pts = name => yh.data.filter(r => r.economy === e && r.series === name).map(r => ({{ x: parse(r.date), y: N(r.value) }}));
      lineChart(document.getElementById('yld-' + e), [
        {{ name: 'Policy rate', color: 'var(--cds-chart-muted)', step: true, width: 1.5, points: pts('Policy rate') }},
        {{ name: '10y', color: C[1], width: 1.5, points: pts('10y') }},
        {{ name: '2y', color: C[0], width: 1.5, points: pts('2y') }},
      ], {{ yDomain, yFmt: v => v.toFixed(1) + '%', xFmt: d3.utcFormat("%b '%y"), tipX: fmtDate, label: e + ' yields' }});
    }});
  }});

  // ---------- BoE meeting strip
  renders.push(() => {{
    const bm = dash.data('boe_meetings'), el = document.getElementById('boe-chart');
    if (bad(bm.status)) return failBox(el);
    if (bm.status !== 'ok') return;
    const tb = document.querySelector('#boe-table tbody'); tb.innerHTML = '';
    bm.data.forEach(r => {{
      const tr = document.createElement('tr'); tr.dataset.key = r.date;
      td(tr, d3.utcFormat('%-d %b %y')(parse(r.date)), 'l'); td(tr, N(r.implied_rate).toFixed(2)); td(tr, sgn(N(r.change_bp), 1));
      td(tr, String(N(r.hike_odds_pct))); td(tr, sgn(N(r.cumulative_bp))); td(tr, r.cumulative_bp_1w == null ? '—' : sgn(N(r.cumulative_bp_1w)));
      tb.appendChild(tr);
    }});
    if (!visible(el)) return;
    el.innerHTML = '';
    const W = Math.max(280, el.clientWidth), H = 240, mg = {{ t: 18, r: 8, b: 26, l: 36 }};
    const x = d3.scaleBand().domain(bm.data.map(r => r.date)).range([mg.l, W - mg.r]).padding(0.3);
    const vals = bm.data.flatMap(r => [N(r.cumulative_bp), N(r.cumulative_bp_1w)]).filter(v => v != null);
    const y = d3.scaleLinear().domain([Math.min(0, d3.min(vals)), Math.max(0, d3.max(vals))]).nice().range([H - mg.b, mg.t]);
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${{W}} ${{H}}`).attr('role', 'img').attr('aria-label', 'BoE cumulative pricing by meeting');
    svg.append('g').selectAll('line').data(y.ticks(4)).join('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y).attr('y2', y).attr('stroke', 'var(--cds-chart-grid)');
    svg.append('g').selectAll('text').data(y.ticks(4)).join('text').attr('x', mg.l - 6).attr('y', d => y(d) + 4).attr('text-anchor', 'end').attr('font-size', 11).attr('fill', 'var(--color-fg-muted)').text(d => sgn(d));
    svg.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--cds-chart-axis)');
    const bw = Math.min(32, x.bandwidth());
    const off = (x.bandwidth() - bw) / 2;
    svg.append('g').selectAll('rect').data(bm.data).join('rect').attr('x', r => x(r.date) + off).attr('width', bw)
      .attr('y', r => y(Math.max(0, N(r.cumulative_bp)))).attr('height', r => Math.abs(y(N(r.cumulative_bp)) - y(0))).attr('rx', 4).attr('fill', C[0]);
    svg.append('g').selectAll('line.wk').data(bm.data.filter(r => r.cumulative_bp_1w != null)).join('line').attr('x1', r => x(r.date) + off - 3).attr('x2', r => x(r.date) + off + bw + 3)
      .attr('y1', r => y(N(r.cumulative_bp_1w))).attr('y2', r => y(N(r.cumulative_bp_1w))).attr('stroke', 'var(--color-fg)').attr('stroke-width', 2);
    if (bw >= 22) svg.append('g').selectAll('text.v').data(bm.data).join('text').attr('x', r => x(r.date) + x.bandwidth() / 2).attr('y', r => y(Math.max(0, N(r.cumulative_bp))) - 5)
      .attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--color-fg)').text(r => sgn(N(r.cumulative_bp)));
    const every = Math.ceil(bm.data.length / Math.max(1, Math.floor((W - mg.l) / 56)));
    svg.append('g').selectAll('text.x').data(bm.data.filter((r, i) => i % every === 0)).join('text').attr('x', r => x(r.date) + x.bandwidth() / 2).attr('y', H - 8)
      .attr('text-anchor', 'middle').attr('font-size', 11).attr('fill', 'var(--color-fg-muted)').text(r => d3.utcFormat("%b '%y")(parse(r.date)));
  }});

  // ---------- implied path small multiples
  renders.push(() => {{
    const ip = dash.data('implied_path');
    ECO.forEach(e => {{
      const el = document.getElementById('path-' + e);
      if (bad(ip.status)) return failBox(el);
      if (ip.status !== 'ok' || !visible(el)) return;
      const rows = ip.data.filter(r => r.economy === e).map(r => ({{ m: N(r.months), now: N(r.vs_policy_bp), wk: N(r.vs_policy_bp_1w) }}));
      const allv = ip.data.flatMap(r => [N(r.vs_policy_bp), N(r.vs_policy_bp_1w)]).filter(v => v != null);
      const start = {{ x: 0, y: 0 }};
      lineChart(el, [
        {{ name: '1 week earlier', color: 'var(--cds-chart-muted)', dash: '4 4', points: [start, ...rows.filter(r => r.wk != null).map(r => ({{ x: r.m, y: r.wk }}))] }},
        {{ name: 'Latest', color: C[0], dots: true, points: [start, ...rows.map(r => ({{ x: r.m, y: r.now }}))] }},
      ], {{ xType: 'linear', xDomain: [0, 24], xTicks: [0, 6, 12, 18, 24], xFmt: d => d + 'm', yDomain: [Math.min(0, d3.min(allv)) - 10, Math.max(0, d3.max(allv)) + 10], yFmt: v => sgn(v), zero: true,
            tipX: v => v + ' months ahead', label: e + ' market-implied path' }});
    }});
  }});

  // ---------- macro
  renders.push(() => {{
    const ml = dash.data('macro_latest'), mh = dash.data('macro_hist');
    if (ml.status === 'ok') {{
      const tb = document.querySelector('#macro-table tbody'); tb.innerHTML = ''; let last = null;
      ml.data.forEach(r => {{
        const tr = document.createElement('tr'); tr.dataset.key = r.key; if (last && r.economy !== last) tr.className = 'g10-grp';
        const dec = v => String(v ?? '').includes('.') ? String(v).split('.')[1].length : 0;
        const d = Math.min(2, Math.max(dec(r.value), dec(r.prior)));
        td(tr, r.economy !== last ? r.economy : '', 'l g10-eco-cell'); td(tr, r.metric, 'l'); td(tr, num(N(r.value), d)); td(tr, r.prior == null ? '—' : num(N(r.prior), d));
        td(tr, r.change == null ? '—' : sgn(N(r.change), d)); td(tr, d3.utcFormat('%b %Y')(parse(r.period)));
        last = r.economy; tb.appendChild(tr);
      }});
    }}
    legend('infl-legend', [['Headline', C[0]], ['Core', C[2]]]);
    if (bad(mh.status)) return ['infl-USD', 'infl-EUR', 'infl-GBP', 'unemp-chart'].forEach(id => failBox(document.getElementById(id)));
    if (mh.status !== 'ok' || !visible(document.getElementById('infl-USD'))) return;
    const pts = (e, mtr) => mh.data.filter(r => r.economy === e && r.metric === mtr).map(r => ({{ x: parse(r.date), y: N(r.value) }}));
    const infl = mh.data.filter(r => r.metric !== 'Unemployment rate').map(r => N(r.value));
    const yDomain = [Math.min(0, d3.min(infl)), d3.max(infl)];
    ['USD', 'EUR', 'GBP'].forEach(e => lineChart(document.getElementById('infl-' + e), [
      {{ name: e + ' headline', short: e, color: C[0], points: pts(e, 'Headline inflation') }},
      {{ name: e + ' core', short: 'core', color: C[2], points: pts(e, 'Core inflation') }},
    ], {{ height: 150, yDomain, endLabels: true, yFmt: v => v.toFixed(1) + '%', xFmt: d3.utcFormat('%Y'), tipX: d3.utcFormat('%b %Y'), label: e + ' inflation' }}));
    lineChart(document.getElementById('unemp-chart'), ECO.map((e, i) => ({{ name: e, short: e, color: C[i], points: pts(e, 'Unemployment rate') }})),
      {{ height: 180, endLabels: true, yFmt: v => v.toFixed(1) + '%', xFmt: d3.utcFormat('%Y'), tipX: d3.utcFormat('%b %Y'), label: 'Unemployment rates' }});
  }});

  // ---------- data health
  renders.push(() => {{
    const dh = dash.data('data_health'); if (dh.status !== 'ok') return;
    const tb = document.querySelector('#health-table tbody'); tb.innerHTML = '';
    dh.data.forEach(r => {{
      const tr = document.createElement('tr'); tr.dataset.key = r.series;
      td(tr, r.status, 'l ' + (r.status === 'Stale' ? 'g10-bad' : 'g10-ok')); td(tr, r.series, 'l'); td(tr, r.economy, 'l'); td(tr, r.name, 'l'); td(tr, r.source, 'l'); td(tr, r.frequency, 'l');
      td(tr, fmtDate(parse(r.last_obs))); td(tr, String(N(r.age_days)));
      tb.appendChild(tr);
    }});
  }});

  dash.onData(runAll);
}})();
</script>
"""

out = Path(__file__).with_name("index.html")
out.write_text(HTML)
print(out, f"{len(HTML.encode()) / 1024:.1f} KB")
