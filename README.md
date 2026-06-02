# Investment Research Skills

Three autonomous investment research skills that crawl financial data sources and produce structured research briefs. Not financial advice.

---

## Skills

| Skill | What it does | Data sources |
|---|---|---|
| `invest-momentum` | Finds what retail and institutional money is chasing right now | Reddit RSS, StockTwits, Finviz movers, ETF inflows |
| `invest-balanced` | Builds a Boglehead-style core + satellite portfolio | r/Bogleheads, ETFDB category leaders, FRED rates, VIX |
| `invest-contrarian` | Surfaces undervalued names Wall Street is ignoring | Reddit value subs, OpenInsider cluster buys, Finviz 52w-low, SEC 13D filings |

---

## Install

**Via skillpm (recommended)**

```bash
npx skillpm install market-lens
```

**Manual symlink**

```bash
ln -s $(pwd)/skills/invest-momentum  ~/.claude/skills/invest-momentum
ln -s $(pwd)/skills/invest-balanced  ~/.claude/skills/invest-balanced
ln -s $(pwd)/skills/invest-contrarian ~/.claude/skills/invest-contrarian
```

Works with Claude Code, Gemini CLI, Cursor, VS Code Copilot, and any harness that supports `SKILL.md`.

---

## How it works

Each skill runs two parallel agent waves:

1. **Scout wave** — 3–4 sub-agents crawl distinct sources concurrently, return JSON pick arrays
2. **Analyst wave** — 5 sub-agents deep-dive each ticker in parallel
3. `scripts/allocate.py` splits a dollar amount across picks by weight
4. `scripts/generate_html.py` writes `reports/<timestamp>-<skill>.html` + `.json`

Contrarian picks are scored on a 4-ingredient checklist: TAM expansion, supply constraint, ignored by Wall St, upcoming catalyst.
Balanced weights: core slots 35/25/20%, satellite slots 12/8%.

---

## Output

Reports land in `reports/` as a styled HTML dashboard and a raw JSON file.

---

## Browse reports locally

```bash
python3 scripts/serve.py
```

Generates `reports/index.html` (a filterable dashboard of every report sorted newest-first with skill badges, dollar amount, top tickers), starts `http.server` on `127.0.0.1:8765`, and opens your browser. Reload to pick up new reports. `Ctrl+C` to stop. Flags: `--port <N>`, `--no-browser`.

---

## Publish to GitHub

Pass a repo URL when invoking any skill (e.g. `/invest-momentum $200 — save to vishnu-meera/market-lens-reports`) or run the helper directly:

```bash
python3 scripts/publish_github.py --repo owner/repo --report reports/<file>.html
```

Clones the repo (or reuses a local cache at `~/.cache/market-lens/publish/`), copies the `.html` + `.json` into `reports/`, updates `INDEX.md`, commits, and pushes. Accepts `owner/repo`, `https://github.com/owner/repo`, or `git@github.com:owner/repo`. Requires `git` on PATH with push credentials configured (`gh auth setup-git` or SSH key). Flags: `--branch <name>`, `--subdir <path>`, `--yes` (skip prompt).

---

## Reliability features

Five reasons these aren't just "LLM tells you a story over noisy mention counts":

1. **Structured fundamentals, not LLM hallucinations.** Analyst sub-agents call `scripts/fundamentals.py` (Yahoo Finance chart + quoteSummary; NASDAQ.com historical as fallback when Yahoo rate-limits) for price, 22-day history, 52w range, market cap, PE, EPS, margins, sector. The LLM fills `why_now` / `bear_case` / `watch_next` *over* the structured numbers — it never invents them. 5-minute disk cache. Returns `status: "ok"` (full Yahoo), `"partial"` (price+history only — Yahoo blocked or NASDAQ fallback), or `"error"` (both unavailable).
2. **Reddit sentiment, not raw mention counts.** `scripts/reddit_fetch.py` tags each post with a `sentiment_hint` (meta / loss / signal). The scout drops meta and loss-porn posts, classifies the rest as bullish / bearish / neutral, and uses `net_bullish = bullish − bearish` for scoring. A ticker the community is net-bearish on is excluded even if mention count is high.
3. **Pick journal + retrospective scoring.** Every report appends to `reports/_picks.jsonl`. Run `python scripts/score.py` weekly — it re-fetches prices via `fundamentals.py`, computes returns, and writes `reports/_scorecard.html` with win rate, avg return, best/worst, and per-skill breakdown.
4. **Price-context guard.** During aggregation, every candidate ticker is fetched through `fundamentals.py`. If trailing-1-month return > 20%, score is downranked by 5 and the pick is flagged in the HTML with a `⚠ late-entry risk` badge. Stops the "trending → top tick" trap.
5. **Confidence stars.** Each pick shows `★ N of M scouts` — visible calibration of whether this is a 4-of-4 cross-source signal or a 1-of-4 single-source guess. The dashboard mirrors this.

All stdlib-only. No new Python deps.

---

## Shared library

Every skill follows the same 9-step pipeline (parse $ → parallel scouts → aggregate + price guard → parallel analysts → allocate → HTML → journal → dashboard → publish). That recipe lives in `skills/_shared/orchestrate.md`, and the Reddit scout / per-ticker analyst prompts live in `skills/_shared/agents/`. Each `SKILL.md` is now a thin config layer (mode, subreddit list, scout files, allocation weights, output template) that delegates execution to the shared recipe. New features land in one place, not three.

---

## Directory layout

```
market-lens/
  skills/
    _shared/
      orchestrate.md             # the 9-step pipeline — source of truth
      agents/
        scout-reddit-base.md     # sentiment-aware Reddit scout (shared)
        analyst-base.md          # fundamentals.py-driven analyst (shared)
    invest-momentum/
      SKILL.md                   # thin config: mode, subs, scout list, template
      agents/
        scout-stocktwits.md
        scout-finviz.md
        scout-etfflows.md
    invest-balanced/
      SKILL.md
      agents/
        scout-etfdb.md
        scout-macro.md
    invest-contrarian/
      SKILL.md
      agents/
        scout-insider.md
        scout-finviz.md
        scout-sec.md
  scripts/
    allocate.py
    generate_html.py             # now renders ★ confidence + ⚠ top-tick warning + fund chips
    reddit_fetch.py              # Chrome UA, backoff, html fallback, 5-min cache, sentiment_hint
    fundamentals.py              # Yahoo Finance: price, 1mo history, 52w, PE, EPS, sector
    journal.py                   # appends picks to reports/_picks.jsonl
    score.py                     # retrospective return calc; writes _scorecard.html
    serve.py                     # localhost dashboard at :8765, links to _scorecard
    publish_github.py            # commit + push report to a GitHub repo
  reports/                       # .gitignored — local snapshots + index.html + _scorecard.html
```
