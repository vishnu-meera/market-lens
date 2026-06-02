---
name: invest-balanced
description: Use when the user wants a diversified, long-term portfolio recommendation, a Boglehead-style or core-satellite investment strategy, or asks what ETFs to hold for a balanced portfolio. Triggers on phrases like "balanced portfolio", "what ETFs should I buy", "set and forget investing", "index fund picks", "3-fund portfolio", "core ETF recommendations", "long-term holdings". Pulls signals from r/Bogleheads/ETFs (sentiment-classified), ETFDB category leaders, and macro conditions; uses Yahoo Finance for structured ETF data (expense ratio, AUM, holdings). Outputs 3 core + 2 satellite positions with share allocations.
version: 0.2.0
---

# invest-balanced

Build a balanced long-term portfolio: ETF core + 1–2 tactical satellites. Aimed at the "set-and-forget with annual rebalancing" investor.

> ⚠️ **Research brief only. Not financial advice.** Balanced still loses value in broad downturns. Past performance ≠ future returns.

---

## Paths

- **SKILL_DIR** — this file's directory
- **SCRIPTS_DIR** — `<SKILL_DIR>/../../scripts`
- **REPORTS_DIR** — `<SKILL_DIR>/../../reports`
- **SHARED_DIR** — `<SKILL_DIR>/../_shared`

---

## Configuration for this mode

- `MODE` = `balanced`
- `SKILL_NAME` = `invest-balanced`
- `NUM_PICKS` = 5 (3 core + 2 satellite)
- `ALLOC` = `0.35, 0.25, 0.20, 0.12, 0.08`
- `ANALYST_EXTRAS` = `role`
- `REDDIT_SUBS` = `Bogleheads, ETFs, investing, personalfinance`
- `SCOUT_FILES`:
  - `<SHARED_DIR>/agents/scout-reddit-base.md` (with `REDDIT_SUBS` above; mode-specific filtering inside the base scout focuses on ETFs)
  - `<SKILL_DIR>/agents/scout-etfdb.md`
  - `<SKILL_DIR>/agents/scout-macro.md` — returns a special `_MACRO_` object with `tilt_recommendation`; extract and use in aggregation
- Max scouts = 3 → max confidence stars = 3★

**Portfolio construction rules (apply during Step 3 aggregation):**
- Slots 1–3 must be CORE (total US market, total bond, total international). If scouts don't surface them, default to **VTI + BND + VXUS**.
- Slots 4–5 are SATELLITE (sector ETF, factor ETF, or a single stock with a fundamental thesis).
- Use the macro scout's `tilt_recommendation`: high rates → short-duration bonds (SHY/VGSH) over long-duration (TLT); VIX > 25 → upweight bond slot.

---

## How to run

Read `<SHARED_DIR>/orchestrate.md` and execute its 9 steps using the configuration above.

In Step 3, apply the portfolio construction rules and the macro tilt before finalizing the top 5. In Step 4 (analyst wave), pass `ANALYST_EXTRAS=role` so each analyst tags `role` ("core"|"satellite"), `expense_ratio`, `aum`, `top_holdings_summary`. Pull ER from `fundamentals.expense_ratio` if populated; otherwise mark as "verify on issuer page."

After Step 8, render the markdown brief using the template below.

---

## Markdown brief template

```markdown
# Balanced picks — $[AMOUNT] total
*Generated [ISO TIMESTAMP]*

> ⚠️ Research brief only. Not financial advice.

📁 Report: `[REPORTS_DIR/<filename>.html]`

## Macro context
[macro_context — e.g., "Fed funds 4.75%, 10Y yield 4.62%, VIX 18 — slight bond overweight favored"]

## Portfolio (3 core + 2 satellite)

### [C] 1. [TICKER] ([ETF|Stock]) — $[ALLOC] · [shares] · ER: [expense_ratio] · AUM: [aum] · [★ rating: N of 3]
**Role:** CORE
[⚠️ Trailing 1mo +N% — late-entry risk]   ← only if top_tick_warning
- **Why:** [why_now]
- **Holdings:** [top_holdings_summary]
- **Fundamentals:** [PE or N/A] PE · [market_cap formatted]
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]
[⚠️ Fundamentals fetch was partial: [fundamentals_note]]   ← only if applicable

### [S] 4. [TICKER] — $[ALLOC] · [shares] *(satellite)* · [★ rating]
- **Why:** [why_now]
- **Bear case:** [bear_case]
- **Watch next:** [watch_next]

[repeat for all 5 picks — mark [C] for core, [S] for satellite]

## Rebalancing note
Rebalance annually or when any position drifts > 5% from target weight.

## How these were picked
[overlap + macro tilt rationale + confidence rating interpretation]

## Sources checked
- Reddit: r/Bogleheads, r/ETFs, r/investing, r/personalfinance (sentiment-classified) [or "(unavailable)"]
- ETFDB category leaders + StockAnalysis popular ETF screener [or "(unavailable)"]
- FRED (Fed rate, 10Y yield) + VIX + macro news [or "(unavailable)"]
- Yahoo Finance via `fundamentals.py` (ER, AUM, holdings where available)

---
*Not financial advice. Rebalance annually or at >5% drift.*
```

---

## Fallback core defaults

If scouts fail entirely, default to the Boglehead 3-fund baseline:
- VTI (U.S. total market, 40%)
- VXUS (international total market, 25%)
- BND (U.S. total bond market, 20%)

Add 2 satellites based on partial scout data, or note "insufficient signal for satellite picks."

## Don'ts

- Don't include leveraged, inverse, or single-stock leveraged ETFs.
- Don't weight satellite positions > 20% combined.
- Don't skip the macro context section.
- Don't run scouts sequentially.
- Don't fabricate ER/AUM if `fundamentals.py` doesn't surface them.
