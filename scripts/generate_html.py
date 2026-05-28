#!/usr/bin/env python3
"""
generate_html.py — render investment research brief as a styled HTML file.

Usage:
    python3 generate_html.py <path-to-data.json>

Writes to: <etw_finder>/reports/YYYY-MM-DD-HHMMSS-<skill_name>.html
Prints the output path to stdout.

JSON schema expected (all fields optional except picks):
{
  "skill_type": "momentum",         // "momentum" | "contrarian" | "balanced"
  "skill_name": "invest-momentum",
  "amount": 100.0,
  "generated_at": "2026-05-27T13:44:15",
  "scouts_ok": ["StockTwits", "Finviz"],
  "scouts_fail": ["Reddit", "ETF flows"],
  "picks": [{
    "rank": 1, "ticker": "ZS", "type": "Stock", "price": 126.49,
    "allocation": 20.0, "whole_shares": 0, "frac_shares": 0.1581,
    "scout_score": 8, "scout_sources": "StockTwits (5 mentions)",
    "why_now": "...", "freshness_days": 5, "fundamentals": "...",
    "bear_case": "...", "watch_next": "...",
    // contrarian only:
    "checklist": {"tam_expansion": "yes", "supply_constraint": "partial",
                  "ignored_wall_st": "yes", "upcoming_catalyst": "yes", "score": "3.5/4"},
    // balanced only:
    "expense_ratio": "0.03%", "aum": "$1.4T", "role": "core",
    "top_holdings_summary": "AAPL 7.2%, MSFT 6.8%"
  }],
  "runners_up": [{"ticker": "DY", "reason": "..."}],
  "how_picked": "..."
}
"""
import html
import json
import os
import sys
from datetime import datetime

SKILL_COLORS = {
    "momentum":   {"accent": "#58a6ff", "accent_dim": "#1c3045", "badge_bg": "#0d2137"},
    "contrarian": {"accent": "#d29922", "accent_dim": "#2d2008", "badge_bg": "#1a1300"},
    "balanced":   {"accent": "#3fb950", "accent_dim": "#0c2015", "badge_bg": "#061209"},
}

CHECKLIST_LABELS = {
    "tam_expansion":    "TAM Expansion",
    "supply_constraint":"Supply Constraint",
    "ignored_wall_st":  "Ignored by Wall St",
    "upcoming_catalyst":"Upcoming Catalyst",
}


def score_color(val):
    return {"yes": "#3fb950", "partial": "#d29922", "no": "#f85149"}.get(str(val).lower(), "#8b949e")


def pick_html(p, skill_type, accent):
    rank = p.get("rank", "?")
    ticker = p.get("ticker", "?")
    ptype = p.get("type", "")
    price = p.get("price")
    alloc = p.get("allocation")
    whole = p.get("whole_shares", 0)
    frac = p.get("frac_shares")
    score = p.get("scout_score", "")
    sources = html.escape(p.get("scout_sources", ""))
    why = html.escape(p.get("why_now", ""))
    fresh = p.get("freshness_days")
    fund = html.escape(p.get("fundamentals", ""))
    bear = html.escape(p.get("bear_case", ""))
    watch = html.escape(p.get("watch_next", ""))

    price_str = f"${price:,.2f}" if price else "N/A"
    alloc_str = f"${alloc:,.2f}" if alloc else ""
    shares_str = f"{whole} whole shares" if whole else (f"{frac} fractional shares" if frac else "")
    if shares_str and price:
        shares_str += f" @ {price_str}"

    extra = ""
    if skill_type == "contrarian" and "checklist" in p:
        cl = p["checklist"]
        rows = "".join(
            f'<div class="cl-row"><span class="cl-label">{CHECKLIST_LABELS.get(k, k)}</span>'
            f'<span class="cl-val" style="color:{score_color(v)}">{str(v).upper()}</span></div>'
            for k, v in cl.items() if k != "score"
        )
        extra = f'<div class="checklist"><div class="cl-score" style="color:{accent}">Score: {cl.get("score","")}</div>{rows}</div>'

    if skill_type == "balanced":
        role = p.get("role", "")
        er = html.escape(p.get("expense_ratio", ""))
        aum = html.escape(p.get("aum", ""))
        top_h = html.escape(p.get("top_holdings_summary", ""))
        role_color = accent if role == "core" else "#d29922"
        role_badge = f'<span class="role-badge" style="background:{role_color}20;color:{role_color};border:1px solid {role_color}40">{role.upper()}</span>' if role else ""
        extra = f'''
        <div class="balanced-meta">
          {role_badge}
          {"<span class='meta-item'><b>ER:</b> "+er+"</span>" if er else ""}
          {"<span class='meta-item'><b>AUM:</b> "+aum+"</span>" if aum else ""}
        </div>
        {"<div class='field'><div class='field-label'>Top Holdings</div><div class='field-value muted'>"+top_h+"</div></div>" if top_h else ""}
        '''

    return f'''
<div class="pick-card">
  <div class="pick-header">
    <div>
      <span class="rank-num" style="color:{accent}">#{rank}</span>
      <span class="ticker">{ticker}</span>
      <span class="pick-type">{ptype}</span>
    </div>
    <div class="pick-right">
      <div class="pick-alloc" style="color:{accent}">{alloc_str}</div>
      <div class="pick-shares">{shares_str}</div>
    </div>
  </div>
  {extra}
  <div class="field why-now">
    <div class="field-label">Why now</div>
    <div class="field-value">{why}</div>
  </div>
  <div class="field-row">
    <div class="field">
      <div class="field-label">Source signal</div>
      <div class="field-value muted">{sources}{"  ·  score "+str(score) if score else ""}</div>
    </div>
    {"<div class='field'><div class='field-label'>Catalyst freshness</div><div class='freshness-pill'>~"+str(fresh)+" days</div></div>" if fresh else ""}
  </div>
  {"<div class='field'><div class='field-label'>Fundamentals</div><div class='field-value muted'>"+fund+"</div></div>" if fund else ""}
  <div class="field bear-case">
    <div class="field-label">Bear case</div>
    <div class="field-value">{bear}</div>
  </div>
  <div class="field">
    <div class="field-label">Watch next</div>
    <div class="field-value muted">{watch}</div>
  </div>
</div>'''


def render(data):
    skill_type = data.get("skill_type", "momentum")
    skill_name = data.get("skill_name", "invest-momentum")
    amount = data.get("amount", 0)
    ts = data.get("generated_at", datetime.now().isoformat()[:19])
    scouts_ok = data.get("scouts_ok", [])
    scouts_fail = data.get("scouts_fail", [])
    picks = data.get("picks", [])
    runners = data.get("runners_up", [])
    how = html.escape(data.get("how_picked", ""))

    c = SKILL_COLORS.get(skill_type, SKILL_COLORS["momentum"])
    accent = c["accent"]
    accent_dim = c["accent_dim"]
    badge_bg = c["badge_bg"]

    skill_label = skill_name.replace("invest-", "").upper()
    title = f"{skill_label} PICKS — ${amount:,.0f}"

    picks_html = "\n".join(pick_html(p, skill_type, accent) for p in picks)

    runners_html = ""
    if runners:
        rows = "".join(f'<div class="runner-row"><span class="runner-ticker">{html.escape(r.get("ticker",""))}</span><span class="runner-reason">{html.escape(r.get("reason",""))}</span></div>' for r in runners)
        runners_html = f'<div class="runners-up"><h3>Strong runners-up dropped</h3>{rows}</div>'

    scouts_ok_html = "".join(f'<div class="source-row"><span class="dot ok">✓</span>{html.escape(s)}</div>' for s in scouts_ok)
    scouts_fail_html = "".join(f'<div class="source-row"><span class="dot fail">✗</span>{html.escape(s)} (unavailable)</div>' for s in scouts_fail)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  .container {{ max-width: 860px; margin: 0 auto; padding: 32px 20px 60px; }}
  header {{ margin-bottom: 28px; }}
  .skill-badge {{ display: inline-block; background: {badge_bg}; color: {accent}; border: 1px solid {accent}40; font-size: 11px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; padding: 3px 10px; border-radius: 12px; margin-bottom: 10px; }}
  h1 {{ font-size: 26px; color: #f0f6fc; font-weight: 700; margin-bottom: 4px; }}
  .meta {{ font-size: 12px; color: #6e7681; }}
  .disclaimer {{ background: #161b22; border: 1px solid #d2992260; color: #d29922; padding: 10px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 28px; }}
  .pick-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 14px; }}
  .pick-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; gap: 12px; }}
  .rank-num {{ font-size: 20px; font-weight: 700; margin-right: 6px; }}
  .ticker {{ font-size: 22px; font-weight: 700; color: #f0f6fc; }}
  .pick-type {{ font-size: 11px; color: #8b949e; background: #21262d; padding: 2px 8px; border-radius: 10px; margin-left: 8px; vertical-align: middle; }}
  .pick-right {{ text-align: right; flex-shrink: 0; }}
  .pick-alloc {{ font-size: 20px; font-weight: 700; }}
  .pick-shares {{ font-size: 12px; color: #8b949e; }}
  .field {{ margin-bottom: 10px; }}
  .field-row {{ display: flex; gap: 32px; margin-bottom: 10px; }}
  .field-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; font-weight: 600; margin-bottom: 3px; }}
  .field-value {{ font-size: 13px; color: #c9d1d9; }}
  .field-value.muted {{ color: #8b949e; }}
  .why-now .field-value {{ color: #3fb950; }}
  .bear-case .field-value {{ color: #f85149; }}
  .freshness-pill {{ display: inline-block; background: {accent_dim}; color: {accent}; border: 1px solid {accent}30; padding: 2px 10px; border-radius: 10px; font-size: 12px; }}
  .checklist {{ background: #0d1117; border: 1px solid #21262d; border-radius: 6px; padding: 10px 14px; margin-bottom: 12px; }}
  .cl-score {{ font-size: 15px; font-weight: 700; margin-bottom: 6px; }}
  .cl-row {{ display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; border-bottom: 1px solid #21262d; }}
  .cl-row:last-child {{ border-bottom: none; }}
  .cl-label {{ color: #8b949e; }}
  .cl-val {{ font-weight: 700; font-size: 11px; letter-spacing: 0.5px; }}
  .balanced-meta {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }}
  .role-badge {{ font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px; letter-spacing: 0.5px; text-transform: uppercase; }}
  .meta-item {{ font-size: 12px; color: #8b949e; }}
  .section-title {{ font-size: 16px; font-weight: 700; color: #f0f6fc; margin: 28px 0 12px; border-bottom: 1px solid #30363d; padding-bottom: 8px; }}
  .how-picked {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 14px; font-size: 13px; color: #8b949e; }}
  .runners-up {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 14px; }}
  .runners-up h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; margin-bottom: 10px; }}
  .runner-row {{ display: flex; gap: 12px; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #21262d; }}
  .runner-row:last-child {{ border-bottom: none; }}
  .runner-ticker {{ color: {accent}; font-weight: 700; min-width: 50px; }}
  .runner-reason {{ color: #8b949e; }}
  .sources {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
  .sources h3 {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; margin-bottom: 8px; }}
  .source-row {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #8b949e; padding: 2px 0; }}
  .dot {{ font-size: 12px; font-weight: 700; }}
  .dot.ok {{ color: #3fb950; }}
  .dot.fail {{ color: #f85149; }}
  footer {{ text-align: center; font-size: 11px; color: #484f58; margin-top: 40px; padding-top: 16px; border-top: 1px solid #21262d; }}
  @media (max-width: 600px) {{ .pick-header {{ flex-direction: column; }} .field-row {{ flex-direction: column; gap: 8px; }} }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="skill-badge">{skill_label}</div>
    <h1>{title}</h1>
    <div class="meta">Generated {ts}</div>
  </header>
  <div class="disclaimer">⚠ Research brief only. Not financial advice. Verify prices and news before acting. Markets move fast.</div>
  <div class="section-title">Top {len(picks)} picks</div>
  {picks_html}
  <div class="section-title">Context</div>
  <div class="how-picked">{how}</div>
  {runners_html}
  <div class="section-title">Sources checked</div>
  <div class="sources">
    <h3>Data sources</h3>
    {scouts_ok_html}
    {scouts_fail_html}
    <div class="source-row"><span class="dot ok">✓</span>Yahoo Finance, SEC EDGAR 8-K, OpenInsider (per-ticker analyst deep dive)</div>
  </div>
  <footer>
    This is not financial advice. Past trends do not guarantee future returns. Always do your own due diligence before investing.<br>
    Generated by {skill_name} · {ts}
  </footer>
</div>
</body>
</html>'''


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_html.py <data.json>", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1]) as f:
        data = json.load(f)

    skill_name = data.get("skill_name", "invest-momentum")
    ts_raw = data.get("generated_at", datetime.now().isoformat()[:19])
    ts_file = ts_raw.replace(":", "").replace("T", "-").replace(" ", "-")[:15]

    script_dir = os.path.dirname(os.path.realpath(__file__))
    reports_dir = os.path.realpath(os.path.join(script_dir, "..", "reports"))
    os.makedirs(reports_dir, exist_ok=True)

    out_name = f"{ts_file}-{skill_name}.html"
    out_path = os.path.join(reports_dir, out_name)
    json_path = os.path.join(reports_dir, f"{ts_file}-{skill_name}.json")

    with open(out_path, "w") as f:
        f.write(render(data))
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(out_path)


if __name__ == "__main__":
    main()
