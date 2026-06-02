---
name: invest-contrarian
description: Use when the user wants contrarian, value-oriented, or against-the-grain investment ideas. Triggers on phrases like "what's undervalued", "what is Wall Street ignoring", "contrarian picks", "deep value stocks", "what has insider buying", "find me hidden gems". Screens Reddit value communities (sentiment-classified, momentum tickers penalized), OpenInsider cluster buys, Finviz 52-week-low screener, and SEC activist filings. Uses Yahoo Finance for structured fundamentals (no LLM hallucination of PE/EPS). Scores each pick against a 4-ingredient checklist (TAM expansion, supply constraint, ignored by Wall St, upcoming catalyst).
version: 0.2.0
---

# invest-contrarian

Find under-followed, fundamentally interesting ideas momentum has missed. Score against the 4-ingredient checklist.

> ⚠️ **Research brief only. Not financial advice.** Contrarian ideas carry higher individual risk than broad indexing — verify everything.

---

## Paths

- **SKILL_DIR** — this file's directory
- **SCRIPTS_DIR** — `<SKILL_DIR>/../../scripts`
- **REPORTS_DIR** — `<SKILL_DIR>/../../reports`
- **SHARED_DIR** — `<SKILL_DIR>/../_shared`

---

## Configuration for this mode

- `MODE` = `contrarian`
- `SKILL_NAME` = `invest-contrarian`
- `NUM_PICKS` = 5
- `ALLOC` = `equal`
- `ANALYST_EXTRAS` = `checklist`
- `REDDIT_SUBS` = `ValueInvesting, SecurityAnalysis, stocks, investing`
- `SCOUT_FILES`:
  - `<SHARED_DIR>/agents/scout-reddit-base.md` (with `REDDIT_SUBS` above; mode-specific filtering inside the base scout penalizes ATH/high-volume tickers)
  - `<SKILL_DIR>/agents/scout-insider.md`
  - `<SKILL_DIR>/agents/scout-finviz.md`
  - `<SKILL_DIR>/agents/scout-sec.md`
- Max scouts = 4 → max confidence stars = 4★

**Per-scout scoring weights** (override default in Step 3):
- `insider` scout hit: +5 per cluster buy
- `sec` scout 13D hit: +6
- `finviz` scout: +4 (both screens) or +2 (one screen)
- `reddit` scout: +3 + `net_bullish` value

Insider + SEC are quality signals — boost above pure Reddit chatter.

---

## How to run

Read `<SHARED_DIR>/orchestrate.md` and execute its 9 steps using the configuration above.

In Step 3, apply the contrarian scoring weights above instead of the default. The price-context guard (downrank tickers up >20% trailing month) is especially load-bearing here — contrarian means catching falling knives, not chasing tops.

In Step 4, pass `ANALYST_EXTRAS=checklist` so each analyst fills the 4-ingredient checklist with specific justifications (not generic language).

After Step 8, render the markdown brief using the template below.

---

## Markdown brief template

```markdown
# Contrarian picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice. Contrarian ideas can stay cheap for a long time — size positions accordingly.

📁 Report: `[REPORTS_DIR/<filename>.html]`

## Top [N] picks

### 1. [TICKER] ([Stock|ETF]) · Score [X.X/4] — $[ALLOC] · [shares] · [★ rating: N of 4]
[⚠️ Trailing 1mo +N% — momentum risk; not a contrarian setup right now]   ← only if top_tick_warning

| Ingredient | Score | Why |
|---|---|---|
| TAM Expansion | [YES / PARTIAL / NO] | [specific one-liner] |
| Supply Constraint | [YES / PARTIAL / NO] | [specific one-liner] |
| Ignored by Wall St | [YES / PARTIAL / NO] | [specific one-liner — e.g., "2 analyst coverage vs 25 for peers"] |
| Upcoming Catalyst | [YES / PARTIAL / NO] | [specific one-liner with date if known] |

- **Why now:** [why_now]
- **Source signal:** [scout_sources]
- **Fundamentals:** [PE or N/A] PE · [market_cap formatted] · [sector]
- **Freshness:** ~[freshness_days] days until catalyst resolves
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]
[⚠️ Fundamentals fetch was partial: [fundamentals_note]]   ← only if applicable

[repeat for picks 2–5]

## How these were picked
[overlap + scoring rationale + confidence interpretation]

**Strong runners-up dropped:**
- [TICKER]: [reason — e.g., "too far through the catalyst already; +15% on the activist news"]

## Sources checked
- Reddit: r/ValueInvesting, r/SecurityAnalysis, r/stocks, r/investing (sentiment-classified) [or "(unavailable)"]
- OpenInsider cluster buys (last 30 days) [or "(unavailable)"]
- Finviz 52-week-low + value screener [or "(unavailable)"]
- SEC 13D/13G activist filings (last 30 days) [or "(unavailable)"]
- Yahoo Finance via `fundamentals.py` (per-ticker)

---
*Not financial advice. Contrarian ideas can stay cheap a long time. Position size small until a catalyst confirms.*
```

---

## Failure modes

- All scouts empty → "No contrarian signals found across all sources today. Markets may be in an everything-trending-up phase (few 52-week lows) or sources are unreachable."
- Analyst can't score a checklist ingredient → mark "partial" with "(data unavailable)" — don't skip the ingredient.
- Fewer than 5 tickers → proceed with however many.

## Don'ts

- Don't inflate checklist scores. A genuine 2/4 with a clear catalyst is more actionable than an inflated 4/4.
- Don't include stocks in SEC enforcement actions (vs. activists seeking change — those are fine).
- Don't run scouts sequentially.
- Don't fabricate fundamentals when `fundamentals.py` returns null.
- Don't skip the disclaimer.
