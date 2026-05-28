---
name: invest-contrarian
description: Use when the user wants contrarian, value-oriented, or against-the-grain investment ideas. Triggers on phrases like "what's undervalued", "what is Wall Street ignoring", "contrarian picks", "deep value stocks", "what has insider buying", "find me hidden gems". Screens Reddit value communities, OpenInsider cluster buys, Finviz 52-week-low screener, and SEC activist filings. Scores each pick against a 4-ingredient checklist (TAM expansion, supply constraint, ignored by Wall St, upcoming catalyst). Outputs share allocations for a given dollar amount as a research brief.
version: 0.1.0
---

# invest-contrarian

Find under-followed, fundamentally interesting ideas that retail and institutional momentum have missed. Score each against the 4-ingredient checklist. Output a thesis per pick with a bear case and catalyst to watch.

> ⚠️ **Research brief only. Not financial advice.** Contrarian ideas carry higher individual risk than broad index investing — verify everything before acting.

---

## How to run

### 1. Parse the dollar amount

Look for a number or `$X` in the user's message. If absent, ask once: "How much are you looking to put to work?" Then proceed.

### 2. Wave 1 — spawn 4 scout sub-agents IN PARALLEL

Single message, four Agent tool calls, `subagent_type: "general-purpose"`. Each prompt:

> Read the file at `<SKILL_DIR>/agents/<SCOUT_FILE>` and execute its instructions exactly. Return only the JSON output specified in that file.

Paths (resolve <SKILL_DIR> to the current skill directory):
- `agents/scout-reddit.md`
- `agents/scout-insider.md`
- `agents/scout-finviz.md`
- `agents/scout-sec.md`

Each returns up to 5 picks: `[{"ticker", "name", "mentions", "source_url", "snippet"}]`

On error or empty: note the source as unavailable and continue.

### 3. Aggregate

- Dedupe tickers across all 4 scouts.
- Scoring (contrarian-weighted):
  - `insider scout` hit: +5 per insider listed
  - `sec scout` 13D hit: +6
  - `finviz scout` both screens hit: +4, one screen hit: +2
  - `reddit scout` hit: +3 + mention count
- Sort descending. Take top 5.
- Insider + SEC hits are quality signals — boost them above pure Reddit mention counts.

### 4. Wave 2 — spawn 5 analyst sub-agents IN PARALLEL

Single message, five Agent tool calls. Each prompt:

> Read `<SKILL_DIR>/agents/analyst.md` and execute it against ticker `<TICKER>`. Return only the JSON object specified.

Each returns: `{"ticker", "type", "price", "checklist": {"tam_expansion", "supply_constraint", "ignored_wall_st", "upcoming_catalyst", "score"}, "why_now", "freshness_days", "fundamentals", "bear_case", "watch_next"}`

### 5. Compute allocations

```
python3 <SKILL_DIR>/scripts/allocate.py <amount> <T1>:<P1> <T2>:<P2> ...
```

Equal-weight by default.

### 6. Write HTML report

**Step 6a — compose data JSON and write using Write tool:**

```
path: <REPORTS_DIR>/invest-contrarian-<YYYYMMDD-HHMMSS>.json
{
  "skill_type": "contrarian",
  "skill_name": "invest-contrarian",
  "amount": <amount>,
  "generated_at": "<ISO timestamp>",
  "scouts_ok": ["<scouts that returned data>"],
  "scouts_fail": ["<scouts that errored>"],
  "picks": [
    {
      "rank": 1, "ticker": "<T>", "type": "Stock|ETF", "price": <N>,
      "allocation": <N>, "whole_shares": <N>, "frac_shares": <N>,
      "scout_score": <N>, "scout_sources": "<which scouts>",
      "why_now": "<...>", "freshness_days": <N>,
      "fundamentals": "<...>", "bear_case": "<...>", "watch_next": "<...>",
      "checklist": {
        "tam_expansion": "<yes|partial|no>",
        "supply_constraint": "<yes|partial|no>",
        "ignored_wall_st": "<yes|partial|no>",
        "upcoming_catalyst": "<yes|partial|no>",
        "score": "<X.X/4>"
      }
    }
    ... all 5 picks
  ],
  "runners_up": [{"ticker": "<T>", "reason": "<...>"}],
  "how_picked": "<...>"
}
```

**Step 6b — generate HTML:**
```
python3 <SKILL_DIR>/scripts/generate_html.py <PATH_TO_JSON>
```

Tell the user: `📊 Report saved to: <output path>`

### 7. Synthesize the text brief

Render this template in markdown:

```markdown
# Contrarian picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice. Contrarian investing means holding through short-term pain — size positions accordingly.

## Top [N] picks

### 1. [TICKER] ([Stock|ETF]) · Score [X.X/4] — $[ALLOC] · [shares info]

| Ingredient | Score |
|---|---|
| TAM Expansion | [YES / PARTIAL / NO] |
| Supply Constraint | [YES / PARTIAL / NO] |
| Ignored by Wall St | [YES / PARTIAL / NO] |
| Upcoming Catalyst | [YES / PARTIAL / NO] |

- **Why now:** [why_now]
- **Source signal:** [which scouts]
- **Freshness:** ~[freshness_days] days until catalyst likely resolves
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]

[... repeat for picks 2–5]

## How these were picked
[overlap summary + scoring rationale]

**Strong runners-up dropped:**
- [TICKER]: [reason]

## Sources checked
- Reddit: r/ValueInvesting, r/SecurityAnalysis, r/stocks, r/investing [(unavailable) if failed]
- OpenInsider cluster buys (last 30 days) [(unavailable) if failed]
- Finviz 52-week-low + value screener [(unavailable) if failed]
- SEC 13D/13G activist filings (last 30 days) [(unavailable) if failed]
- Yahoo Finance, SEC EDGAR 8-K, OpenInsider — per-ticker analyst deep dive

---
*Not financial advice. Contrarian ideas can stay cheap for a long time. Position size small until a catalyst confirms the thesis.*
```

---

## Failure modes

- **All scouts empty** — tell user: "No contrarian signals found across all sources today. Markets may be in a phase where everything is trending up (few 52-week lows) or sources are unreachable."
- **Analyst can't score an ingredient** (data missing) — score "partial" and note "(data unavailable)" — do not skip the ingredient.
- **Fewer than 5 tickers** — proceed with however many you have.

## Don'ts

- Don't inflate checklist scores. A genuine 2/4 with a clear catalyst is more actionable than a inflated 4/4.
- Don't include stocks in SEC enforcement actions (vs. activists seeking change — those are fine).
- Don't run scouts sequentially. Parallel only.
- Don't skip the disclaimer.
