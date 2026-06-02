#!/usr/bin/env python3
"""
journal.py — append picks from a report JSON into reports/_picks.jsonl.

Stdlib-only. One line per pick. Existing entries are not modified.
This is the input for score.py (retrospective return calculation).

Usage:
    python3 journal.py <path-to-report-json>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def reports_dir() -> Path:
    script_dir = Path(os.path.realpath(__file__)).parent
    return (script_dir / ".." / "reports").resolve()


def append_picks(report_json_path: Path) -> int:
    data = json.loads(report_json_path.read_text(encoding="utf-8"))
    skill = data.get("skill_type", "unknown")
    generated_at = data.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    date_only = generated_at.split("T")[0]
    picks = data.get("picks", [])

    journal = reports_dir() / "_picks.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with journal.open("a", encoding="utf-8") as f:
        for p in picks:
            entry = {
                "date": date_only,
                "generated_at": generated_at,
                "skill": skill,
                "ticker": p.get("ticker"),
                "type": p.get("type"),
                "price_at_pick": p.get("price"),
                "allocation_usd": p.get("allocation"),
                "scout_score": p.get("scout_score"),
                "confidence_scouts": p.get("confidence_scouts"),
                "scout_sources": p.get("scout_sources"),
                "report": str(report_json_path.name),
            }
            f.write(json.dumps(entry) + "\n")
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_json")
    args = ap.parse_args()
    p = Path(args.report_json)
    if not p.exists():
        print(f"Report JSON not found: {p}", file=sys.stderr)
        return 2
    n = append_picks(p)
    print(f"Appended {n} picks to {reports_dir() / '_picks.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
