---
name: invest-momentum
description: Use when the user asks what stocks or ETFs are trending right now, where to put discretionary cash short-term, or wants to know what retail/institutional money is currently chasing. Triggers on phrases like "what's trending", "where should I invest $X today", "what's hot in ETFs", "find me momentum picks". Crawls Reddit, StockTwits, Finviz, and ETF fund flows; explains why each pick is trending and outputs share allocations for a given dollar amount. Produces a research brief, not financial advice.
version: 0.1.0
---

# invest-momentum

Discover what's trending across retail + institutional flows, explain *why* each pick is trending, and output share allocations for a given dollar amount.

> ⚠️ **This skill produces a research brief, not financial advice.** Every output must include a disclaimer. Markets move fast; data fetched here is a snapshot, not real-time.

---

## Paths (resolve before running)

- **SKILL_DIR** — directory containing this SKILL.md file
- **SCRIPTS_DIR** — `<SKILL_DIR>/../../scripts` (shared Python helpers: `allocate.py`, `generate_html.py`)
- **REPORTS_DIR** — `<SKILL_DIR>/../../reports` (output folder)

---

## How to run

### 1. Parse the dollar amount

Look in the user's message for a number that represents available cash. Patterns: `$100`, `$1,000`, `1000`, `invest 500`, `with 250 dollars`.

- If found, use it.
- If not found, **ask once**: "How much do you have to invest?" Then proceed with the answer.
- If amount < $20, warn that meaningful 5-way diversification will be tough (most stocks/ETFs cost more than $4 per share), but continue.

### 2. Wave 1 — spawn 4 scout sub-agents IN PARALLEL

Dispatch all 4 simultaneously — a single parallel batch, not sequential. Each agent prompt:

> Read the file at `<SKILL_DIR>/agents/<SCOUT_FILE>` and execute its instructions exactly. Return only the JSON output specified in that file — no preamble, no markdown, no commentary.

*Harness note: on Claude Code use one message with 4 `Agent` tool calls (`subagent_type: "general-purpose"`); on Gemini CLI or other harnesses use the equivalent parallel mechanism.*

Paths (resolve <SKILL_DIR> to the current skill directory):
- `agents/scout-reddit.md`
- `agents/scout-stocktwits.md`
- `agents/scout-finviz.md`
- `agents/scout-etfflows.md`

Each returns up to 5 picks in this shape:

```
[{"ticker": "...", "name": "...", "mentions": N, "source_url": "...", "snippet": "..."}, ...]
```

If a scout returns `{"error": "..."}` or empty, note the source as unavailable and continue. Do not retry.

### 3. Aggregate

- Dedupe tickers case-insensitively across all 4 scout outputs.
- Score each ticker: `score = (num_distinct_scouts * 3) + total_mentions`
- Sort descending; take the top 5.
- Keep a list of 2–3 strong runners-up (rank 6–8) and why you dropped them — you'll mention these in the brief.

### 4. Wave 2 — spawn 5 analyst sub-agents IN PARALLEL

Dispatch all 5 simultaneously. Each agent prompt:

> Read `<SKILL_DIR>/agents/analyst.md` and execute it against ticker `<TICKER>`. Return only the JSON object specified — no preamble, no markdown.

*Harness note: same parallel mechanism as Wave 1.*

Each returns:

```
{"ticker": "...", "type": "Stock|ETF", "price": N.NN, "why_now": "...", "freshness_days": N, "fundamentals": "...", "bear_case": "...", "watch_next": "..."}
```

If an analyst fails on one ticker, note it in the final brief ("could not analyze TICKER — Yahoo unreachable") and skip that slot. Don't substitute another ticker.

### 5. Compute share allocations

Run the allocation script (requires shell access):

```
python3 <SCRIPTS_DIR>/allocate.py <amount> <T1>:<P1> <T2>:<P2> <T3>:<P3> <T4>:<P4> <T5>:<P5>
```

Use prices from the analyst output. The script prints whole-share and fractional-share strategies.

If shell access is unavailable, compute inline: each ticker gets `amount / N` dollars; whole shares = `floor(alloc / price)`; leftover = `alloc - (whole_shares × price)`.

### 6. Write HTML report

After allocation, compose a JSON object with all pick data and write it to a temp file, then generate the HTML report.

**Step 6a — compose the data JSON.** Build this object, then write it to a temp file using your harness's file-write tool:

```
path: /tmp/etw-momentum-<YYYYMMDD-HHMMSS>.json
contents: {
  "skill_type": "momentum",
  "skill_name": "invest-momentum",
  "amount": <dollar amount>,
  "generated_at": "<ISO timestamp>",
  "scouts_ok": ["<names of scouts that returned data>"],
  "scouts_fail": ["<names of scouts that returned errors>"],
  "picks": [
    {
      "rank": 1, "ticker": "<T>", "type": "Stock|ETF", "price": <N>,
      "allocation": <alloc>, "whole_shares": <N>, "frac_shares": <N>,
      "scout_score": <N>, "scout_sources": "<which scouts + counts>",
      "why_now": "<analyst.why_now>",
      "freshness_days": <N>,
      "fundamentals": "<analyst.fundamentals>",
      "bear_case": "<analyst.bear_case>",
      "watch_next": "<analyst.watch_next>"
    }
    ... repeat for all 5 picks
  ],
  "runners_up": [{"ticker": "<T>", "reason": "<why dropped>"}],
  "how_picked": "<1-2 sentence overlap summary>"
}
```

**Step 6b — generate the HTML:**
```
python3 <SCRIPTS_DIR>/generate_html.py /tmp/etw-momentum-<YYYYMMDD-HHMMSS>.json
```

The script prints the output path and saves both `.html` and `.json` to `<REPORTS_DIR>`. Report the path to the user before showing the text brief.

### 7. Synthesize using the template below

Fill the template with:

- Amount from step 1
- Current ISO timestamp
- Per-pick rows from analyst output + allocate.py output
- "How these were picked" using overlap + runners-up from step 3
- Sources footer listing what was checked

---

## Output template

Render exactly this structure (markdown), substituting the bracketed values:

```markdown
# Momentum picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice. Markets move fast; verify prices and news before acting.

## Top 5

### 1. [TICKER] ([Stock|ETF]) — $[ALLOC] · [N] whole shares @ $[PRICE] · $[LEFTOVER] cash
- **Why now:** [analyst.why_now]
- **Source signal:** [list scouts that hit this ticker, e.g. "Reddit (28 mentions, 3 subs) + Finviz (gainers + unusual vol)"]
- **Freshness:** ~[analyst.freshness_days] days until catalyst likely priced in
- **Bear case:** [analyst.bear_case]
- **Watch next:** [analyst.watch_next]

### 2. [TICKER] ...
[repeat for picks 2–5]

## Fractional-share alternative
If your brokerage supports fractional shares: [paste fractional row from allocate.py]

## How these were picked
[1–2 sentences on overlap: e.g., "NVDA and AVGO hit 3 of 4 scouts — strongest signals. SMH appeared only in ETF flows but the semi-rotation theme reinforced both stock picks."]

**Strong runners-up dropped:**
- [TICKER]: [one-line reason, e.g., "PLTR — already +40% this week, late to enter"]
- [TICKER]: [...]

## Sources checked
- Reddit: r/wallstreetbets, r/stocks, r/investing, r/options, r/ETFs (hot, last 24–72h) [or "(unavailable)" if scout failed]
- StockTwits trending [or "(unavailable)"]
- Finviz top gainers + unusual volume + new highs (mid-cap+) [or "(unavailable)"]
- ETF.com / VettaFi / ETFDB fund flows (trailing week) [or "(unavailable)"]
- Yahoo Finance, SEC EDGAR 8-K, OpenInsider (per-ticker analyst deep dive)

---
*This is not financial advice. Past trends do not guarantee future returns. Always do your own due diligence before investing.*
```

---

## Failure modes to handle gracefully

- **All scouts return empty** — tell the user: "No clear momentum signal across any of the 4 sources right now. Markets may be quiet, or all sources may be unreachable. Try again in a few hours."
- **Fewer than 5 unique tickers aggregated** — proceed with however many you have; the template still works.
- **Analyst returns stale price** (Yahoo returns data from > 1 trading day ago) — use it, but note "Last close $X (market closed)" in the row.
- **Bash `python3` not available** — try `python`. If neither works, compute the allocation arithmetically yourself (equal-weight, integer division by price) and proceed.

## Don'ts

- Don't output anything before parsing the dollar amount and confirming the user wants you to proceed.
- Don't skip the disclaimer.
- Don't recommend buying — only "here's what's trending, here's why, here's the math."
- Don't include crypto, leveraged ETFs (3× bull/bear), or penny stocks.
- Don't run scouts sequentially. Parallel only.
