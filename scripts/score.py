#!/usr/bin/env python3
"""
score.py — re-fetch prices for journaled picks and compute returns.

Reads reports/_picks.jsonl. For picks aged >= --min-days (default 7), fetches
the current price via fundamentals.py and computes the return %.

Writes:
  - reports/_scorecard.json (raw data)
  - reports/_scorecard.html (dashboard view shown by serve.py)

Usage:
    python3 score.py
    python3 score.py --min-days 14
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def reports_dir() -> Path:
    script_dir = Path(os.path.realpath(__file__)).parent
    return (script_dir / ".." / "reports").resolve()


def scripts_dir() -> Path:
    return Path(os.path.realpath(__file__)).parent


def load_journal() -> list:
    j = reports_dir() / "_picks.jsonl"
    if not j.exists():
        return []
    out = []
    for line in j.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def fetch_current_prices(tickers: list) -> dict:
    if not tickers:
        return {}
    cmd = [sys.executable, str(scripts_dir() / "fundamentals.py")] + tickers
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"fundamentals.py failed: {e}", file=sys.stderr)
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    prices = {}
    for r in data.get("results", []):
        if r.get("status") in ("ok", "partial"):
            cur = (r.get("price") or {}).get("current")
            if cur is not None:
                prices[r.get("ticker", "").upper()] = cur
    return prices


def score_picks(picks: list, min_days: int) -> list:
    today = date.today()
    cutoff = today - timedelta(days=min_days)

    eligible = []
    for p in picks:
        pick_date_s = p.get("date") or (p.get("generated_at") or "")[:10]
        try:
            pick_date = datetime.strptime(pick_date_s, "%Y-%m-%d").date()
        except ValueError:
            continue
        if pick_date > cutoff:
            continue
        if not p.get("ticker") or not p.get("price_at_pick"):
            continue
        eligible.append((p, pick_date))

    tickers = sorted({p["ticker"].upper() for p, _ in eligible})
    prices = fetch_current_prices(tickers)

    scored = []
    for p, pick_date in eligible:
        ticker = p["ticker"].upper()
        entry_price = p["price_at_pick"]
        current = prices.get(ticker)
        if current is None or not entry_price:
            ret_pct = None
        else:
            ret_pct = round((current - entry_price) / entry_price * 100, 2)
        days_held = (today - pick_date).days
        scored.append({
            "ticker": ticker,
            "skill": p.get("skill"),
            "date": p["date"],
            "days_held": days_held,
            "entry_price": entry_price,
            "current_price": current,
            "return_pct": ret_pct,
        })
    return scored


def aggregate(scored: list) -> dict:
    rated = [s for s in scored if s["return_pct"] is not None]
    if not rated:
        return {
            "count": 0,
            "uncoverable_count": len(scored),
            "win_rate": None,
            "avg_return_pct": None,
            "best": None,
            "worst": None,
            "by_skill": {},
        }
    winners = [s for s in rated if s["return_pct"] > 0]
    avg = round(sum(s["return_pct"] for s in rated) / len(rated), 2)
    best = max(rated, key=lambda s: s["return_pct"])
    worst = min(rated, key=lambda s: s["return_pct"])
    by_skill = {}
    for s in rated:
        by_skill.setdefault(s["skill"], []).append(s["return_pct"])
    skill_stats = {
        k: {"count": len(v), "avg_return_pct": round(sum(v) / len(v), 2)}
        for k, v in by_skill.items()
    }
    return {
        "count": len(rated),
        "uncoverable_count": len(scored) - len(rated),
        "win_rate": round(len(winners) / len(rated) * 100, 1),
        "avg_return_pct": avg,
        "best": best,
        "worst": worst,
        "by_skill": skill_stats,
    }


def render_html(scored: list, agg: dict) -> str:
    rows = []
    for s in sorted(scored, key=lambda x: (x["return_pct"] is None, -(x["return_pct"] or 0))):
        ret = s["return_pct"]
        if ret is None:
            color, ret_str = "#8b949e", "—"
        elif ret > 0:
            color, ret_str = "#3fb950", f"+{ret:.1f}%"
        else:
            color, ret_str = "#f85149", f"{ret:.1f}%"
        entry = f"${s['entry_price']:,.2f}" if s["entry_price"] else "—"
        cur = f"${s['current_price']:,.2f}" if s["current_price"] else "—"
        rows.append(
            f'<tr><td class="ts">{html.escape(s["date"])}</td>'
            f'<td>{html.escape(s["skill"] or "")}</td>'
            f'<td class="tick">{html.escape(s["ticker"])}</td>'
            f'<td class="num">{entry}</td>'
            f'<td class="num">{cur}</td>'
            f'<td class="num" style="color:{color};font-weight:700">{ret_str}</td>'
            f'<td class="ts">{s["days_held"]}d</td></tr>'
        )
    rows_html = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="7" class="empty">No picks aged past the cutoff yet.</td></tr>'
    )

    summary_chip = ""
    if agg["count"]:
        win_color = "#3fb950" if agg["win_rate"] >= 50 else "#f85149"
        avg_color = "#3fb950" if agg["avg_return_pct"] >= 0 else "#f85149"
        summary_chip = f'''
        <div class="summary">
          <div class="card"><div class="label">Picks scored</div><div class="value">{agg["count"]}</div></div>
          <div class="card"><div class="label">Win rate</div><div class="value" style="color:{win_color}">{agg["win_rate"]}%</div></div>
          <div class="card"><div class="label">Avg return</div><div class="value" style="color:{avg_color}">{agg["avg_return_pct"]:+.2f}%</div></div>
          <div class="card"><div class="label">Best</div><div class="value">{html.escape(agg["best"]["ticker"])} {agg["best"]["return_pct"]:+.1f}%</div></div>
          <div class="card"><div class="label">Worst</div><div class="value">{html.escape(agg["worst"]["ticker"])} {agg["worst"]["return_pct"]:+.1f}%</div></div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>Market-Lens Scorecard</title>
<style>
  body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px; margin: 0; }}
  .container {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px; }}
  h1 {{ font-size: 24px; color: #f0f6fc; margin: 0 0 6px; }}
  .sub {{ font-size: 12px; color: #6e7681; margin-bottom: 18px; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin-bottom: 24px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; }}
  .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; margin-bottom: 4px; }}
  .value {{ font-size: 18px; color: #f0f6fc; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 10px 14px; border-bottom: 1px solid #21262d; text-align: left; font-size: 13px; }}
  tr:last-child td {{ border-bottom: none; }}
  th {{ background: #0d1117; font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; }}
  td.ts {{ font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: #8b949e; }}
  td.tick {{ font-weight: 700; color: #f0f6fc; }}
  td.num {{ font-family: ui-monospace, Consolas, monospace; text-align: right; }}
  td.empty {{ text-align: center; padding: 40px; color: #6e7681; font-style: italic; }}
  footer {{ text-align: center; color: #484f58; font-size: 11px; margin-top: 24px; }}
  a.back {{ display: inline-block; margin-bottom: 16px; color: #58a6ff; text-decoration: none; font-size: 12px; }}
  a.back:hover {{ text-decoration: underline; }}
</style></head><body><div class="container">
<a class="back" href="./index.html">← Dashboard</a>
<h1>Scorecard</h1>
<div class="sub">Computed {datetime.now().isoformat(timespec="seconds")} · best-effort retrospective on past picks · not financial advice</div>
{summary_chip}
<table>
  <thead><tr><th>Pick date</th><th>Skill</th><th>Ticker</th><th>Entry</th><th>Current</th><th>Return</th><th>Days</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
<footer>Generated by score.py · Run again with `python scripts/score.py` to refresh</footer>
</div></body></html>'''


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-days", type=int, default=7, help="Only score picks at least N days old (default 7)")
    args = ap.parse_args()

    picks = load_journal()
    if not picks:
        print("No picks journaled yet — run a skill to generate a report, then journal.py runs automatically.", file=sys.stderr)
        return 1

    scored = score_picks(picks, args.min_days)
    agg = aggregate(scored)

    out = {
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "min_days": args.min_days,
        "picks": scored,
        "aggregate": agg,
    }
    rdir = reports_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "_scorecard.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (rdir / "_scorecard.html").write_text(render_html(scored, agg), encoding="utf-8")

    if agg["count"]:
        print(
            f"Scored {len(scored)} picks ({agg['count']} with current prices). "
            f"Win rate: {agg['win_rate']}%, avg return: {agg['avg_return_pct']:+.2f}%."
        )
    else:
        print(f"Found {len(picks)} journaled picks but {agg['uncoverable_count']} were not scorable (need --min-days {args.min_days} or fundamentals fetch failed).")
    print(f"Wrote {rdir / '_scorecard.json'}")
    print(f"Wrote {rdir / '_scorecard.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
