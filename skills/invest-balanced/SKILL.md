---
name: invest-balanced
description: Use when the user wants a diversified, long-term portfolio recommendation, a Boglehead-style or core-satellite investment strategy, or asks what ETFs to hold for a balanced portfolio. Triggers on phrases like "balanced portfolio", "what ETFs should I buy", "set and forget investing", "index fund picks", "3-fund portfolio", "core ETF recommendations", "long-term holdings". Pulls signals from r/Bogleheads/ETFs, ETFDB category leaders, and macro conditions. Analyst evaluates each pick as core or satellite with expense ratio and AUM quality checks. Outputs 3–4 core positions and 1–2 satellite positions with share allocations.
version: 0.1.0
---

# invest-balanced

Build a balanced, long-term portfolio using ETFs as the backbone, with 1–2 satellite positions where the macro or tactical case is compelling. Aimed at the "set and forget with annual rebalancing" investor.

> ⚠️ **Research brief only. Not financial advice.** Balanced investing still carries market risk. Past performance doesn't guarantee future returns.

---

## Paths (resolve before running)

- **SKILL_DIR** — directory containing this SKILL.md file
- **SCRIPTS_DIR** — `<SKILL_DIR>/../../scripts` (shared Python helpers: `allocate.py`, `generate_html.py`)
- **REPORTS_DIR** — `<SKILL_DIR>/../../reports` (output folder)

---

## How to run

### 1. Parse the dollar amount

Look for `$X` or a bare number in the user's message. If absent, ask once: "How much are you investing?" Then proceed.

### 2. Wave 1 — spawn 3 scout sub-agents IN PARALLEL

Dispatch all 3 simultaneously — a single parallel batch, not sequential. Each agent prompt:

> Read the file at `<SKILL_DIR>/agents/<SCOUT_FILE>` and execute its instructions exactly. Return only the JSON output specified in that file.

*Harness note: on Claude Code use one message with 3 `Agent` tool calls (`subagent_type: "general-purpose"`); on Gemini CLI or other harnesses use the equivalent parallel mechanism.*

Paths (resolve <SKILL_DIR> to the current skill directory):
- `agents/scout-reddit.md`
- `agents/scout-etfdb.md`
- `agents/scout-macro.md`

Each scout returns picks in `[{"ticker", "name", "mentions", "source_url", "snippet"}]` format (macro scout returns special `_MACRO_` object — extract its `tilt_recommendation` and set it aside).

### 3. Aggregate with balanced weighting

- Dedupe tickers (excluding `_MACRO_`).
- Scoring: `(distinct scouts * 3) + mentions`
- **Portfolio construction rules:**
  - **Slots 1–3**: Must be CORE holdings (total market, bond, international). If scout data doesn't surface them, default to VTI + BND + VXUS as the evidence-based core.
  - **Slots 4–5**: SATELLITE — highest-scoring thematic/sector ETFs or one compelling stock from scouts.
  - Use `tilt_recommendation` from macro scout to decide: if rates are high → include a short-duration bond ETF (SHY, VGSH) over long-duration (TLT); if VIX > 25 → upweight bond slot.

### 4. Wave 2 — spawn 5 analyst sub-agents IN PARALLEL

Dispatch all 5 simultaneously. Each agent prompt:

> Read `<SKILL_DIR>/agents/analyst.md` and execute it against ticker `<TICKER>`. Return only the JSON object specified.

*Harness note: same parallel mechanism as Wave 1.*

Each returns: `{"ticker", "type", "price", "role", "expense_ratio", "aum", "top_holdings_summary", "why_now", "freshness_days", "fundamentals", "bear_case", "watch_next"}`

### 5. Compute allocations

Allocate differently from equal-weight: core slots get more weight.

Default allocation:
- Slot 1 (core): 35%
- Slot 2 (core): 25%
- Slot 3 (core): 20%
- Slot 4 (satellite): 12%
- Slot 5 (satellite): 8%

Run the allocation script (requires shell access):

```
python3 <SCRIPTS_DIR>/allocate.py <amount> <T1>:<P1>:0.35 <T2>:<P2>:0.25 <T3>:<P3>:0.20 <T4>:<P4>:0.12 <T5>:<P5>:0.08
```

If shell access is unavailable, compute inline using the weights above: alloc = `amount × weight`; whole shares = `floor(alloc / price)`; leftover = `alloc - (whole_shares × price)`.

### 6. Write HTML report

**Step 6a — write data JSON to a temp file using your harness's file-write tool:**

```
path: /tmp/etw-balanced-<YYYYMMDD-HHMMSS>.json
{
  "skill_type": "balanced",
  "skill_name": "invest-balanced",
  "amount": <amount>,
  "generated_at": "<ISO timestamp>",
  "scouts_ok": ["<scouts that returned data>"],
  "scouts_fail": ["<scouts that errored>"],
  "macro_context": "<tilt_recommendation from macro scout, or 'unavailable'>",
  "picks": [
    {
      "rank": 1, "ticker": "<T>", "type": "ETF|Stock", "price": <N>,
      "allocation": <N>, "whole_shares": <N>, "frac_shares": <N>,
      "scout_score": <N>, "scout_sources": "<which scouts>",
      "why_now": "<...>", "freshness_days": <N>,
      "fundamentals": "<...>", "bear_case": "<...>", "watch_next": "<...>",
      "expense_ratio": "<...>", "aum": "<...>", "role": "core|satellite",
      "top_holdings_summary": "<...>"
    }
    ... all 5 picks
  ],
  "runners_up": [{"ticker": "<T>", "reason": "<...>"}],
  "how_picked": "<...>"
}
```

**Step 6b — generate HTML:**
```
python3 <SCRIPTS_DIR>/generate_html.py /tmp/etw-balanced-<YYYYMMDD-HHMMSS>.json
```

The script prints the output path and saves both `.html` and `.json` to `<REPORTS_DIR>`. Report the path to the user.

### 7. Synthesize the text brief

Render this template:

```markdown
# Balanced picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice.

## Macro context
[macro_context from scout — e.g., "Fed funds 4.75%, 10Y yield 4.62%, VIX 18 — slight bond overweight favored"]

## Portfolio (3 core + 2 satellite)

### [C] 1. [TICKER] ([ETF|Stock]) — $[ALLOC] · [shares] · ER: [expense_ratio] · AUM: [aum]
**Role:** CORE
- **Why:** [why_now]
- **Holdings:** [top_holdings_summary]
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]

### [S] 4. [TICKER] — $[ALLOC] · [shares] *(satellite)*
- **Why:** [why_now]
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]

[repeat for all 5 picks — mark [C] for core, [S] for satellite]

## Rebalancing note
[1 sentence on when/how to rebalance — typically annually or when any position drifts > 5% from target weight]

## How these were picked
[overlap + macro tilt rationale]

## Sources checked
- Reddit: r/Bogleheads, r/ETFs, r/investing, r/personalfinance [(unavailable) if failed]
- ETFDB category leaders + StockAnalysis popular ETF screener [(unavailable) if failed]
- FRED (Fed rate, 10Y yield) + VIX + macro news [(unavailable) if failed]
- Yahoo Finance, ETF.com, StockAnalysis — per-ticker analyst deep dive

---
*Not financial advice. Balanced portfolios still lose value in broad market downturns. Rebalance annually or at >5% drift.*
```

---

## Fallback core defaults

If scouts fail entirely, default to the Boglehead 3-fund portfolio as the baseline:
- VTI (U.S. total market, 40%)
- VXUS (international total market, 25%)
- BND (U.S. total bond market, 20%)
Then add 2 satellite slots based on any partial scout data, or note "insufficient signal for satellite picks."

## Don'ts

- Don't include leveraged, inverse, or single-stock ETFs.
- Don't weight satellite positions > 20% combined.
- Don't skip the macro context section.
- Don't run scouts sequentially. Parallel only.
