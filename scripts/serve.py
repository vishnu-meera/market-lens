#!/usr/bin/env python3
"""
serve.py — generate a dashboard index of all reports and serve them on localhost.

Stdlib-only. Generates reports/index.html listing every .html report (sorted
newest-first) with skill badge, dollar amount, top tickers, and a link. Starts
http.server on 127.0.0.1:<port> rooted at reports/, opens browser to the
dashboard, and blocks until Ctrl+C.

Usage:
    python3 serve.py
    python3 serve.py --port 9000 --no-browser
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SKILL_COLORS = {
    "momentum":   {"accent": "#58a6ff", "badge_bg": "#0d2137"},
    "contrarian": {"accent": "#d29922", "badge_bg": "#1a1300"},
    "balanced":   {"accent": "#3fb950", "badge_bg": "#061209"},
}


def reports_dir() -> Path:
    script_dir = Path(os.path.realpath(__file__)).parent
    return (script_dir / ".." / "reports").resolve()


def load_report_meta(html_path: Path) -> dict:
    json_path = html_path.with_suffix(".json")
    meta = {
        "filename": html_path.name,
        "mtime": html_path.stat().st_mtime,
        "skill_type": "unknown",
        "skill_name": html_path.stem,
        "amount": None,
        "generated_at": "",
        "tickers": [],
    }
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            meta["skill_type"] = data.get("skill_type", "unknown")
            meta["skill_name"] = data.get("skill_name", meta["skill_name"])
            meta["amount"] = data.get("amount")
            meta["generated_at"] = data.get("generated_at", "")
            meta["tickers"] = [p.get("ticker", "") for p in data.get("picks", [])][:3]
        except (json.JSONDecodeError, OSError):
            pass
    return meta


def render_dashboard(reports: list, scorecard_exists: bool) -> str:
    rows = []
    for r in reports:
        c = SKILL_COLORS.get(r["skill_type"], {"accent": "#8b949e", "badge_bg": "#21262d"})
        ts = html.escape(r["generated_at"] or datetime.fromtimestamp(r["mtime"]).isoformat(timespec="seconds"))
        amount = f"${r['amount']:,.0f}" if isinstance(r["amount"], (int, float)) else "—"
        tickers = " · ".join(html.escape(t) for t in r["tickers"] if t) or "—"
        badge = (
            f'<span class="badge" style="color:{c["accent"]};'
            f'background:{c["badge_bg"]};border-color:{c["accent"]}40">'
            f'{html.escape(r["skill_type"]).upper()}</span>'
        )
        rows.append(
            f'<tr data-skill="{html.escape(r["skill_type"])}">'
            f'<td class="ts">{ts}</td>'
            f'<td>{badge}</td>'
            f'<td class="amount">{amount}</td>'
            f'<td class="tickers">{tickers}</td>'
            f'<td class="open"><a href="./{html.escape(r["filename"])}">Open →</a></td>'
            f'</tr>'
        )

    body = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="5" class="empty">No reports yet. Run /invest-momentum, '
             '/invest-balanced, or /invest-contrarian to generate one.</td></tr>'
    )
    count = len(reports)
    plural = "s" if count != 1 else ""

    scorecard_link = (
        '<a class="scorecard-link" href="./_scorecard.html">📊 Scorecard →</a>'
        if scorecard_exists
        else '<span class="scorecard-link disabled">Scorecard not yet generated — run <code>python scripts/score.py</code></span>'
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Market-Lens Dashboard</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  .container {{ max-width: 1080px; margin: 0 auto; padding: 32px 20px 60px; }}
  header {{ margin-bottom: 24px; }}
  h1 {{ font-size: 26px; color: #f0f6fc; font-weight: 700; margin-bottom: 4px; }}
  .sub {{ font-size: 12px; color: #6e7681; }}
  .chips {{ margin: 18px 0; display: flex; gap: 8px; flex-wrap: wrap; }}
  .chip {{ background: #161b22; border: 1px solid #30363d; color: #8b949e; padding: 4px 12px; border-radius: 12px; cursor: pointer; font-size: 12px; font-weight: 600; letter-spacing: 0.4px; user-select: none; }}
  .chip.active {{ color: #f0f6fc; border-color: #58a6ff; background: #0d2137; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 10px 14px; text-align: left; font-size: 13px; border-bottom: 1px solid #21262d; }}
  th {{ background: #0d1117; font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: #6e7681; font-weight: 600; }}
  tr:last-child td {{ border-bottom: none; }}
  tbody tr:hover {{ background: #1c2028; }}
  td.ts {{ color: #8b949e; font-family: ui-monospace, Consolas, monospace; font-size: 12px; white-space: nowrap; }}
  td.amount {{ color: #f0f6fc; font-weight: 700; white-space: nowrap; }}
  td.tickers {{ color: #c9d1d9; font-family: ui-monospace, Consolas, monospace; font-size: 12px; }}
  td.open a {{ color: #58a6ff; text-decoration: none; font-weight: 600; white-space: nowrap; }}
  td.open a:hover {{ text-decoration: underline; }}
  td.empty {{ text-align: center; color: #6e7681; padding: 40px; font-style: italic; }}
  .badge {{ display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 2px 8px; border-radius: 10px; border: 1px solid; white-space: nowrap; }}
  footer {{ text-align: center; font-size: 11px; color: #484f58; margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; }}
  .scorecard-link {{ display: inline-block; margin-left: 12px; font-size: 12px; color: #58a6ff; text-decoration: none; font-weight: 600; }}
  .scorecard-link.disabled {{ color: #6e7681; font-weight: 400; }}
  .scorecard-link.disabled code {{ background: #161b22; padding: 1px 6px; border-radius: 4px; font-size: 11px; color: #c9d1d9; }}
  .scorecard-link:hover:not(.disabled) {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Market-Lens Reports</h1>
    <div class="sub">{count} report{plural} · newest first · refresh to pick up new ones {scorecard_link}</div>
  </header>
  <div class="chips">
    <span class="chip active" data-filter="all">All</span>
    <span class="chip" data-filter="momentum">Momentum</span>
    <span class="chip" data-filter="contrarian">Contrarian</span>
    <span class="chip" data-filter="balanced">Balanced</span>
  </div>
  <table>
    <thead><tr><th>Generated</th><th>Skill</th><th>Amount</th><th>Top picks</th><th></th></tr></thead>
    <tbody>{body}</tbody>
  </table>
  <footer>Generated by serve.py · Reload to refresh · Reports live under reports/ in the repo</footer>
</div>
<script>
  const chips = document.querySelectorAll('.chip');
  const rows = document.querySelectorAll('tbody tr');
  chips.forEach(chip => chip.addEventListener('click', () => {{
    chips.forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    const f = chip.dataset.filter;
    rows.forEach(r => {{
      r.style.display = (f === 'all' || r.dataset.skill === f) ? '' : 'none';
    }});
  }}));
</script>
</body>
</html>'''


def build_index() -> Path:
    rdir = reports_dir()
    rdir.mkdir(parents=True, exist_ok=True)
    skip = {"index.html", "_scorecard.html"}
    htmls = [p for p in rdir.glob("*.html") if p.name not in skip]
    reports = sorted((load_report_meta(p) for p in htmls), key=lambda r: r["mtime"], reverse=True)
    scorecard_exists = (rdir / "_scorecard.html").exists()
    index_path = rdir / "index.html"
    index_path.write_text(render_dashboard(reports, scorecard_exists), encoding="utf-8")
    return index_path


_REPORTS_DIR = reports_dir()


class DashboardHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler rooted at reports/, regenerates index.html on each landing-page hit."""

    def __init__(self, *args, **kwargs):
        kwargs.pop("directory", None)
        super().__init__(*args, directory=str(_REPORTS_DIR), **kwargs)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                build_index()
            except Exception as e:
                sys.stderr.write(f"  index regen failed: {e}\n")
        super().do_GET()

    def log_message(self, fmt, *args):
        # Keep console quiet — only print errors (4xx/5xx).
        if args and isinstance(args[0], str) and args[0][:1] in ("4", "5"):
            sys.stderr.write(f"  {self.address_string()} - {fmt % args}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    build_index()
    rdir = reports_dir()

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    except OSError as e:
        print(f"Could not bind to 127.0.0.1:{args.port} — {e}", file=sys.stderr)
        print("Try --port <other-port>.", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving {rdir} at {url}  (Ctrl+C to stop)")

    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
