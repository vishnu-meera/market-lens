#!/usr/bin/env python3
"""
fundamentals.py — fetch structured price + key metrics from Yahoo Finance.

Stdlib-only. Two free public endpoints, no auth needed:
  - v8/chart        — price + 1-month history + 52w range + market cap (reliable)
  - v10/quoteSummary — PE, EPS, dividend, beta, margins (may 401; best-effort)

Usage:
    python3 fundamentals.py <TICKER> [<TICKER> ...]

Output: JSON with `results[]`. Each entry has `status`:
  - "ok"      — chart + quoteSummary both succeeded
  - "partial" — chart succeeded, quoteSummary 401/blocked
  - "error"   — chart failed; ticker likely invalid or network down

Also computes `context.trending_top_tick_risk` ("warning" if trailing 1-month
return > 20%) so the analyst can flag late-entry risk in the brief.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
}

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=1mo&interval=1d"
SUMMARY_URL = (
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{t}"
    "?modules=summaryDetail,defaultKeyStatistics,financialData,assetProfile,fundProfile"
)
NASDAQ_HIST_URL = (
    "https://api.nasdaq.com/api/quote/{t}/historical"
    "?assetclass={ac}&fromdate={start}&todate={end}&limit=30"
)

CACHE_DIR = Path.home() / ".cache" / "market-lens" / "fundamentals"
CACHE_TTL = timedelta(minutes=5)

TOP_TICK_THRESHOLD_PCT = 20.0


def fetch_bytes(url: str, timeout: int = 15, retries_429: int = 2):
    """Fetch raw bytes with exponential backoff on 429. Returns (status, bytes_or_None)."""
    backoffs = [0, 2, 4, 8][: retries_429 + 1]
    last_status = 0
    for delay in backoffs:
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            last_status = e.code
            if e.code == 429:
                continue
            return e.code, None
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, None
    return last_status, None


def fetch_json(url: str, timeout: int = 15, retries_429: int = 2):
    status, body = fetch_bytes(url, timeout, retries_429)
    if status == 200 and body:
        try:
            return status, json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return status, None
    return status, None


def cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker.upper()}.json"


def load_cache(ticker: str):
    p = cache_path(ticker)
    if not p.exists():
        return None
    age = datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)
    if age > CACHE_TTL:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(ticker: str, data: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path(ticker).write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _round(x, digits=2):
    if isinstance(x, (int, float)):
        return round(float(x), digits)
    return None


def parse_chart(payload):
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return None
    r = result[0]
    meta = r.get("meta") or {}
    indicators = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [c for c in (indicators.get("close") or []) if c is not None]
    highs = [h for h in (indicators.get("high") or []) if h is not None]
    lows = [low for low in (indicators.get("low") or []) if low is not None]

    current = meta.get("regularMarketPrice")
    first_close = closes[0] if closes else None
    trailing_return = None
    if first_close and current and first_close > 0:
        trailing_return = round((current - first_close) / first_close * 100, 2)

    top_tick = (
        "warning"
        if (trailing_return is not None and trailing_return > TOP_TICK_THRESHOLD_PCT)
        else "none"
    )

    as_of = None
    rmt = meta.get("regularMarketTime")
    if rmt:
        try:
            as_of = datetime.fromtimestamp(rmt, tz=timezone.utc).isoformat()
        except (OSError, ValueError):
            pass

    return {
        "price": {
            "current": _round(current),
            "previous_close": _round(meta.get("chartPreviousClose")),
            "market_state": meta.get("marketState"),
            "currency": meta.get("currency", "USD"),
            "as_of": as_of,
        },
        "history_1mo": {
            "first_close": _round(first_close),
            "high": _round(max(highs)) if highs else None,
            "low": _round(min(lows)) if lows else None,
            "trailing_return_pct": trailing_return,
            "data_points": len(closes),
        },
        "context": {
            "trending_top_tick_risk": top_tick,
            "trailing_return_pct": trailing_return,
        },
        "quote": {
            "name": meta.get("longName") or meta.get("shortName"),
            "exchange": meta.get("exchangeName"),
            "instrument_type": meta.get("instrumentType"),
            "52w_high": _round(meta.get("fiftyTwoWeekHigh")),
            "52w_low": _round(meta.get("fiftyTwoWeekLow")),
            "market_cap": None,
            "sector": None,
            "industry": None,
        },
    }


def _g(d, *path):
    """Drill into nested dict; unwrap Yahoo's {raw, fmt} containers."""
    x = d
    for p in path:
        if not isinstance(x, dict):
            return None
        x = x.get(p)
    if isinstance(x, dict) and "raw" in x:
        return x["raw"]
    return x


def parse_summary(payload):
    qs = payload.get("quoteSummary") or {}
    if qs.get("error"):
        return None
    result = qs.get("result") or []
    if not result:
        return None
    r = result[0]

    return {
        "market_cap": _g(r, "summaryDetail", "marketCap"),
        "pe_trailing": _g(r, "summaryDetail", "trailingPE"),
        "pe_forward": _g(r, "summaryDetail", "forwardPE"),
        "eps_trailing": _g(r, "defaultKeyStatistics", "trailingEps"),
        "dividend_yield": _g(r, "summaryDetail", "dividendYield"),
        "beta": _g(r, "summaryDetail", "beta"),
        "profit_margin": _g(r, "defaultKeyStatistics", "profitMargins"),
        "operating_margin": _g(r, "financialData", "operatingMargins"),
        "free_cash_flow": _g(r, "financialData", "freeCashflow"),
        "debt_to_equity": _g(r, "financialData", "debtToEquity"),
        "roe": _g(r, "financialData", "returnOnEquity"),
        "analyst_recommendation": _g(r, "financialData", "recommendationKey"),
        "target_mean": _g(r, "financialData", "targetMeanPrice"),
        "sector": _g(r, "assetProfile", "sector"),
        "industry": _g(r, "assetProfile", "industry"),
        # ETF-specific (fundProfile module)
        "expense_ratio": _g(r, "fundProfile", "feesExpensesInvestment", "annualReportExpenseRatio"),
        "fund_family": _g(r, "fundProfile", "family"),
        "fund_category": _g(r, "fundProfile", "categoryName"),
    }


def _money(s):
    """Parse '$306.31' or '306.31' to float; None on failure."""
    if not s:
        return None
    try:
        return float(str(s).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def fetch_nasdaq_historical(ticker: str):
    """Fetch ~30 days of OHLC from NASDAQ.com. Tries assetclass=stocks then etf.

    Returns (assetclass_used, rows) or (None, None).
    """
    today = date.today()
    start = today - timedelta(days=45)
    for ac in ("stocks", "etf"):
        url = NASDAQ_HIST_URL.format(t=ticker, ac=ac, start=start.isoformat(), end=today.isoformat())
        status, data = fetch_json(url)
        if status != 200 or not data:
            continue
        rows = ((data.get("data") or {}).get("tradesTable") or {}).get("rows") or []
        if rows:
            return ac, rows
    return None, None


def parse_nasdaq_rows(rows, assetclass):
    """Parse NASDAQ historical rows into a chart-equivalent dict (price + 1mo history)."""
    parsed = []
    for r in rows:
        d = r.get("date")
        c = _money(r.get("close"))
        h = _money(r.get("high"))
        low = _money(r.get("low"))
        if d and c:
            parsed.append({"date": d, "close": c, "high": h, "low": low})
    if not parsed:
        return None

    # NASDAQ returns descending order — sort ascending by date (MM/DD/YYYY).
    def _key(r):
        try:
            m, d, y = r["date"].split("/")
            return (int(y), int(m), int(d))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    parsed.sort(key=_key)
    parsed = parsed[-22:]
    closes = [r["close"] for r in parsed]
    highs = [r["high"] for r in parsed if r["high"]]
    lows = [r["low"] for r in parsed if r["low"]]

    current = closes[-1]
    first_close = closes[0]
    trailing_return = None
    if first_close > 0:
        trailing_return = round((current - first_close) / first_close * 100, 2)
    top_tick = (
        "warning"
        if (trailing_return is not None and trailing_return > TOP_TICK_THRESHOLD_PCT)
        else "none"
    )

    return {
        "price": {
            "current": _round(current),
            "previous_close": _round(closes[-2]) if len(closes) >= 2 else None,
            "market_state": None,
            "currency": "USD",
            "as_of": parsed[-1]["date"],
        },
        "history_1mo": {
            "first_close": _round(first_close),
            "high": _round(max(highs)) if highs else None,
            "low": _round(min(lows)) if lows else None,
            "trailing_return_pct": trailing_return,
            "data_points": len(closes),
        },
        "context": {
            "trending_top_tick_risk": top_tick,
            "trailing_return_pct": trailing_return,
        },
        "quote": {
            "name": None,
            "exchange": "NASDAQ",
            "instrument_type": "EQUITY" if assetclass == "stocks" else "ETF",
            "52w_high": None,
            "52w_low": None,
            "market_cap": None,
            "sector": None,
            "industry": None,
        },
    }


def fetch_ticker(ticker: str, use_cache: bool = True):
    ticker = ticker.upper().strip()

    if use_cache:
        cached = load_cache(ticker)
        if cached is not None:
            cached["_source"] = cached.get("_source", "yahoo") + " (cached)"
            return cached

    out = {
        "ticker": ticker,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "status": "error",
    }

    # 1. Try Yahoo chart
    chart_status, chart_data = fetch_json(CHART_URL.format(t=ticker))
    chart_parsed = None
    if chart_status == 200 and chart_data:
        chart_parsed = parse_chart(chart_data)

    if chart_parsed:
        out.update(chart_parsed)
        out["status"] = "partial"
        out["_source"] = "yahoo"
    else:
        # 2. Yahoo failed — try NASDAQ.com historical API for price + history
        ac, rows = fetch_nasdaq_historical(ticker)
        if rows:
            nasdaq_parsed = parse_nasdaq_rows(rows, ac)
            if nasdaq_parsed:
                out.update(nasdaq_parsed)
                out["status"] = "partial"
                out["_source"] = "nasdaq"
        if out["status"] == "error":
            out["reason"] = f"Yahoo chart {chart_status}; NASDAQ also unavailable"
            return out

    # 3. Try Yahoo quoteSummary opportunistically (may succeed even if chart 429'd)
    summary_status, summary_data = fetch_json(SUMMARY_URL.format(t=ticker))
    if summary_status == 200 and summary_data:
        summary_parsed = parse_summary(summary_data)
        if summary_parsed:
            if summary_parsed.get("market_cap") is not None:
                out["quote"]["market_cap"] = summary_parsed["market_cap"]
            if summary_parsed.get("sector"):
                out["quote"]["sector"] = summary_parsed["sector"]
            if summary_parsed.get("industry"):
                out["quote"]["industry"] = summary_parsed["industry"]
            out["fundamentals"] = {
                k: v
                for k, v in summary_parsed.items()
                if k not in ("market_cap", "sector", "industry")
            }
            if out["_source"] == "yahoo":
                out["status"] = "ok"

    if "fundamentals" not in out:
        out["fundamentals"] = {
            "_note": f"quoteSummary unavailable ({summary_status}); price/history from {out.get('_source', 'unknown')}"
        }

    save_cache(ticker, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--no-cache", action="store_true", help="Skip the 5-minute disk cache")
    args = ap.parse_args()

    results = []
    for i, t in enumerate(args.tickers):
        if i > 0:
            time.sleep(0.5)  # gentle pacing
        results.append(fetch_ticker(t, use_cache=not args.no_cache))
    output = {"fetched_at": datetime.now().isoformat(timespec="seconds"), "results": results}
    print(json.dumps(output, indent=2))

    any_ok = any(r.get("status") in ("ok", "partial") for r in results)
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
