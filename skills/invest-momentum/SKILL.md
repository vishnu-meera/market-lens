---
name: invest-momentum
description: Use when the user asks what stocks or ETFs are trending right now, where to put discretionary cash short-term, or wants to know what retail/institutional money is currently chasing. Triggers on phrases like "what's trending", "where should I invest $X today", "what's hot in ETFs", "find me momentum picks". Crawls Reddit (sentiment-classified), StockTwits, Finviz, and ETF fund flows; uses Yahoo Finance for structured fundamentals (no LLM hallucination of PE/EPS/etc.); flags trailing-1-month-up-20% tickers as late-entry risk. Produces a research brief, not financial advice.
version: 0.2.0
---

# invest-momentum

Discover what's trending across retail + institutional flows, explain *why*, output share allocations.

> ⚠️ **Research brief only. Not financial advice.** Markets move fast; this is a snapshot.

---

## Paths

- **SKILL_DIR** — this file's directory
- **SCRIPTS_DIR** — `<SKILL_DIR>/../../scripts`
- **REPORTS_DIR** — `<SKILL_DIR>/../../reports`
- **SHARED_DIR** — `<SKILL_DIR>/../_shared` (shared orchestration recipe + scout/analyst base prompts)

---

## Configuration for this mode

- `MODE` = `momentum`
- `SKILL_NAME` = `invest-momentum`
- `NUM_PICKS` = 5
- `ALLOC` = `equal`
- `ANALYST_EXTRAS` = `none`
- `REDDIT_SUBS` = `wallstreetbets, stocks, investing, options, ETFs`
- `SCOUT_FILES`:
  - `<SHARED_DIR>/agents/scout-reddit-base.md` (with `REDDIT_SUBS` above)
  - `<SKILL_DIR>/agents/scout-stocktwits.md`
  - `<SKILL_DIR>/agents/scout-finviz.md`
  - `<SKILL_DIR>/agents/scout-etfflows.md`

Per-scout scoring: default `(distinct_scouts × 3) + total_mentions`. Max scouts = 4 → max confidence stars = 4★.

---

## How to run

Read `<SHARED_DIR>/orchestrate.md` and execute its 9 steps using the configuration above. The shared file is the source of truth for the pipeline — Reddit fetch + sentiment classification, parallel scouts, price-context guard (downrank tickers up >20% trailing month), structured fundamentals via `fundamentals.py`, parallel analyst wave, allocation, HTML, journal append, dashboard offer, GitHub publish offer.

After Step 8 of the orchestrate recipe, render the markdown brief using the template below.

---

## Markdown brief template

```markdown
# Momentum picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice.

📁 Report: `[REPORTS_DIR/<filename>.html]`

## Top 5

### 1. [TICKER] ([Stock|ETF]) — $[ALLOC] · [N] whole shares @ $[PRICE] · $[LEFTOVER] cash · [★ rating: N of 4 scouts]
[⚠️ Trailing 1mo +N% — late-entry risk]   ← only if top_tick_warning
- **Why now:** [why_now]
- **Source signal:** [scout_sources]
- **Freshness:** ~[freshness_days] days
- **Fundamentals:** [pe_trailing or "N/A"] PE · [market_cap formatted] cap · [sector]
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]
[⚠️ Fundamentals fetch was partial: [fundamentals_note]]   ← only if note != "Full Yahoo quote+history"

[repeat for picks 2–5]

## Fractional-share alternative
[paste fractional row from allocate.py]

## How these were picked
[1–2 sentences on cross-scout overlap. Confidence stars: 4★ = all 4 scouts hit; 1★ = single source signal — calibrate trust accordingly.]

**Strong runners-up dropped:**
- [TICKER]: [reason — e.g., "PLTR — +35% this month, top-tick risk flagged"]

## Sources checked
- Reddit: r/wallstreetbets, r/stocks, r/investing, r/options, r/ETFs (sentiment-classified — bearish posts excluded) [or "(unavailable)" if scout failed]
- StockTwits trending [or "(unavailable)"]
- Finviz top gainers + unusual volume + new highs (mid-cap+) [or "(unavailable)"]
- ETF flows trailing week [or "(unavailable)"]
- Yahoo Finance via `fundamentals.py` (price + 1mo history + PE/EPS/margins where available)

---
*Not financial advice. Past trends don't predict future returns. Always do your own due diligence.*
```

---

## Mode-specific failure handling

- All scouts empty → "No clear momentum signal across any source. Markets may be quiet, or all sources unreachable. Try again in a few hours."
- All `fundamentals.py` calls fail → "Yahoo Finance is unreachable — cannot verify prices. Skipping today."
- Fewer than 5 unique tickers → proceed with however many; the template still works.
- Yahoo `quoteSummary` 401 across the board → proceed with price+history only; mark fundamentals fields as "verify on Yahoo Finance" in the brief.

## Don'ts

- Don't include crypto, leveraged ETFs (3× bull/bear), or penny stocks.
- Don't recommend buying — only "here's what's trending, here's the math."
- Don't run scouts sequentially. Parallel only.
- Don't fabricate fundamentals when `fundamentals.py` returns null fields.
- Don't skip the disclaimer.
