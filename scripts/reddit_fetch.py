#!/usr/bin/env python3
"""
reddit_fetch.py — fetch hot posts from Reddit subreddits via RSS.

Stdlib-only. Sets a realistic browser User-Agent to bypass Reddit's bot-UA blocks.
Caches responses for 5 minutes at ~/.cache/market-lens/reddit/<sub>.json.
Falls back to old.reddit.com HTML scraping on persistent 403.
Exponential backoff on 429 (2s, 4s, 8s — max 3 tries).

Usage:
    python3 reddit_fetch.py <sub1> <sub2> [...]
    python3 reddit_fetch.py --no-cache wallstreetbets stocks

Emits JSON to stdout:
    {
      "fetched_at": "2026-06-02T14:30:00",
      "results": [
        {"subreddit": "wallstreetbets", "status": "ok", "source": "rss", "posts": [
          {"title": "...", "summary": "...", "link": "..."}
        ]},
        {"subreddit": "options", "status": "blocked", "reason": "403 after 3 retries"}
      ]
    }

Exit 0 if any subreddit returned posts; 1 if all failed.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}
CACHE_DIR = Path.home() / ".cache" / "market-lens" / "reddit"
CACHE_TTL = timedelta(minutes=5)
RSS_URL = "https://www.reddit.com/r/{sub}/hot.rss?limit=50"
HTML_URL = "https://old.reddit.com/r/{sub}/hot/"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def strip_html(s: str) -> str:
    """Crude HTML-to-text for Reddit content payloads."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


META_MARKERS = (
    "daily discussion", "weekly thread", "weekly earnings",
    "rate my portfolio", "megathread", "what are your moves",
    "what are you watching", "mod announcement", "monthly thread",
    "monday discussion", "tuesday discussion", "wednesday discussion",
    "thursday discussion", "friday discussion", "weekend discussion",
)
LOSS_MARKERS = (
    "rip my", "rip account", "lost everything", "wiped out",
    "loss porn", "yolo loss", "down 50", "down 60", "down 70",
    "down 80", "down 90", "down 95", "down 99",
)
SIGNAL_MARKERS = (
    " dd ", "(dd)", "[dd]", "due diligence", "deep dive",
    "analysis", "thesis", "valuation", "earnings beat", "earnings miss",
    "bullish on", "bearish on", "loading up", "added to my",
    "starting position", "trimming", "selling my", "bought more",
)


def classify_post(title: str, summary: str) -> str:
    """Crude rule-based sentiment hint. Returns 'meta', 'loss', or 'signal'.

    Conservative — only obviously off-topic posts (daily threads, mod posts,
    loss-porn vents) are tagged. Everything else stays 'signal' and is passed
    to the scout LLM for nuanced bullish/bearish classification.
    """
    text = (title + " " + summary).lower()
    if any(m in text for m in META_MARKERS):
        return "meta"
    if any(m in text for m in SIGNAL_MARKERS):
        return "signal"
    if any(m in text for m in LOSS_MARKERS):
        return "loss"
    return "signal"


def normalize_sub(s: str) -> str:
    s = s.strip().lstrip("/")
    if s.lower().startswith("r/"):
        s = s[2:]
    return s


def cache_path(sub: str) -> Path:
    return CACHE_DIR / f"{sub.lower()}.json"


def load_cache(sub: str):
    p = cache_path(sub)
    if not p.exists():
        return None
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if age > CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(sub: str, data: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path(sub).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # Cache is best-effort — don't fail the whole fetch on disk errors


def fetch_url(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        body = e.read() if e.fp else b""
        return e.code, body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, str(e).encode()


def parse_rss(xml_bytes: bytes) -> list:
    """Parse Reddit's Atom feed into posts with sentiment_hint."""
    root = ET.fromstring(xml_bytes)
    posts = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        title_el = entry.find(f"{ATOM_NS}title")
        content_el = entry.find(f"{ATOM_NS}content")
        link_el = entry.find(f"{ATOM_NS}link")
        title = (title_el.text or "").strip() if title_el is not None else ""
        summary = strip_html(content_el.text or "") if content_el is not None else ""
        link = link_el.get("href", "") if link_el is not None else ""
        if title:
            posts.append({
                "title": title,
                "summary": summary[:600],
                "link": link,
                "sentiment_hint": classify_post(title, summary),
            })
    return posts


def parse_old_reddit_html(html_bytes: bytes) -> list:
    """Best-effort: extract post titles from old.reddit.com HTML."""
    text = html_bytes.decode("utf-8", errors="ignore")
    pattern = re.compile(
        r'<a[^>]*class="title[^"]*"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]+)</a>',
        re.IGNORECASE,
    )
    posts = []
    for m in pattern.finditer(text):
        title = html.unescape(m.group("title")).strip()
        href = m.group("href")
        if title and len(title) > 3:
            posts.append({
                "title": title,
                "summary": "",
                "link": href,
                "sentiment_hint": classify_post(title, ""),
            })
    return posts


def fetch_subreddit(sub: str, use_cache: bool) -> dict:
    if use_cache:
        cached = load_cache(sub)
        if cached is not None:
            cached = dict(cached)
            cached["source"] = "cache"
            return cached

    last_status = None
    for attempt, backoff in enumerate([0, 2, 4, 8]):
        if backoff:
            time.sleep(backoff)
        status, body = fetch_url(RSS_URL.format(sub=sub))
        last_status = status
        if status == 200:
            try:
                posts = parse_rss(body)
            except ET.ParseError as e:
                return {"subreddit": sub, "status": "error", "reason": f"RSS parse error: {e}"}
            result = {"subreddit": sub, "status": "ok", "source": "rss", "posts": posts}
            save_cache(sub, result)
            return result
        if status == 429:
            continue
        if status == 403:
            break
        if status == 0 and attempt == 0:
            continue
        if status == 0:
            return {"subreddit": sub, "status": "error", "reason": f"network: {body.decode(errors='ignore')[:120]}"}

    status, body = fetch_url(HTML_URL.format(sub=sub))
    if status == 200:
        posts = parse_old_reddit_html(body)
        if posts:
            result = {"subreddit": sub, "status": "ok", "source": "html", "posts": posts}
            save_cache(sub, result)
            return result

    return {
        "subreddit": sub,
        "status": "blocked",
        "reason": f"RSS {last_status} after retries; HTML fallback {status}",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("subreddits", nargs="+")
    ap.add_argument("--no-cache", action="store_true", help="Skip the 5-minute disk cache.")
    args = ap.parse_args()

    subs = [normalize_sub(s) for s in args.subreddits]

    results = [fetch_subreddit(sub, use_cache=not args.no_cache) for sub in subs]

    output = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
    }
    print(json.dumps(output, indent=2))

    any_ok = any(r.get("status") == "ok" for r in results)
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
