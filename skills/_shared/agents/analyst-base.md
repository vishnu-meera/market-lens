# Analyst: shared base

You analyze ONE ticker. The calling orchestrator told you:
- A ticker to analyze
- A mode: `momentum` | `balanced` | `contrarian`
- An extras flag: `none` | `role` (balanced) | `checklist` (contrarian)
- (Often) the cached `fundamentals.py` JSON entry for this ticker — use it if present

This file is shared across every invest-* skill.

---

## Step 1 — Get structured fundamentals (do NOT summarize web pages)

**If the orchestrator passed you cached fundamentals JSON, use it directly.** Otherwise:

```
python3 <SCRIPTS_DIR>/fundamentals.py <TICKER>
```

`<SCRIPTS_DIR>` is `<SKILL_DIR>/../../scripts`.

You get a structured JSON object with:

- `price.current` — current price (USD unless `currency` says otherwise)
- `quote.name`, `quote.exchange`, `quote.instrument_type` (`EQUITY` | `ETF`)
- `quote.52w_high`, `quote.52w_low`, `quote.market_cap`, `quote.sector`, `quote.industry`
- `history_1mo.trailing_return_pct` — trailing 1-month return %
- `context.trending_top_tick_risk` — `"warning"` if up >20% in trailing month (late-entry risk)
- `fundamentals.pe_trailing`, `pe_forward`, `eps_trailing`, `dividend_yield`, `beta`, `profit_margin`, `operating_margin`, `free_cash_flow`, `debt_to_equity`, `roe`, `analyst_recommendation`, `target_mean`
- (ETFs) `fundamentals.expense_ratio`, `fund_family`, `fund_category`

If `status` is `"error"`: return the error JSON in Step 4 — don't proceed.

If `status` is `"partial"`: chart endpoint succeeded but Yahoo's quoteSummary was blocked. You have price + history + 52w range + market cap, but PE/EPS/margins/etc. are missing. Be honest about this in `fundamentals_note`.

If `status` is `"ok"`: full data.

---

## Step 2 — Use the numbers DIRECTLY, do not invent

Read the fundamentals fields straight into your output. **Never** invent PE, EPS, margins, or any other number. If `fundamentals.pe_trailing` is null, your output's `pe_trailing` is null, and you mention "PE not in fetched data — verify on Yahoo Finance" in `fundamentals_note`.

Your real job is the **qualitative explanation**:

- **`why_now`** — what's actually happening with this ticker? Pull from recent news, scout snippets passed via the orchestrator, recent SEC 8-K filings, earnings dates. Tie it to actual price action (e.g., "Up 12% trailing month after Q1 beat + raised FY guidance"). Do NOT generate generic language — be specific to this ticker.
- **`freshness_days`** — your estimate of how many days until the current catalyst is priced in. Use the earnings calendar if relevant. If "no clear catalyst," say 30+ days (drift territory).
- **`bear_case`** — what would make this thesis wrong? Concrete and specific. Bad: "competition could be tough." Good: "AVGO's hyperscaler revenue is concentrated in 3 customers; any one renegotiating ASIC pricing could compress margins 200bps."
- **`watch_next`** — the single most informative upcoming data point: an earnings call, a Fed meeting, an FDA decision, a supplier shipment. One thing.

---

## Step 3 — Mode-specific extras

### momentum
Nothing extra. Base output below.

### balanced
Also fill:
- `role` — `"core"` (broad market: total US, total international, total bond) or `"satellite"` (sector, factor, single stock with thesis)
- `expense_ratio` — from `fundamentals.expense_ratio` (formatted as "0.03%"); null if not in data
- `aum` — formatted from `quote.market_cap` (e.g., "$1.4T"); null if not in data
- `top_holdings_summary` — best-effort one-liner (e.g., "AAPL 7.2%, MSFT 6.8%, NVDA 5.1%"). If you don't have this data, write: "Top holdings not in fundamentals fetch — see ETF issuer page."

### contrarian
Also fill `checklist`:
- `tam_expansion` — `yes` | `partial` | `no` — is the addressable market expanding?
- `supply_constraint` — `yes` | `partial` | `no` — limited supply giving pricing power?
- `ignored_wall_st` — `yes` | `partial` | `no` — thin/absent analyst coverage? (Use `fundamentals.analyst_recommendation` and the existence of `target_mean` as hints.)
- `upcoming_catalyst` — `yes` | `partial` | `no` — specific event in next 1-6 months that could re-rate?
- `score` — `"X.X/4"` (yes=1.0, partial=0.5, no=0)

Each ingredient gets a one-line justification — be specific, not generic. "TAM expansion: yes — moving from $50B addressable to $150B by 2028 per company guidance" beats "yes — market is growing."

---

## Step 4 — Output

Return ONE JSON object. No preamble, no markdown fence, no commentary.

```
{
  "ticker": "<T>",
  "type": "Stock" | "ETF",
  "price": <fundamentals.price.current>,
  "name": "<fundamentals.quote.name>",
  "sector": "<fundamentals.quote.sector or null>",
  "market_cap": <fundamentals.quote.market_cap or null>,
  "pe_trailing": <fundamentals.fundamentals.pe_trailing or null>,
  "pe_forward": <fundamentals.fundamentals.pe_forward or null>,
  "eps_trailing": <fundamentals.fundamentals.eps_trailing or null>,
  "dividend_yield": <fundamentals.fundamentals.dividend_yield or null>,
  "beta": <fundamentals.fundamentals.beta or null>,
  "trailing_return_pct": <fundamentals.history_1mo.trailing_return_pct>,
  "top_tick_warning": <true if context.trending_top_tick_risk == "warning" else false>,
  "fundamentals_note": "<'Full Yahoo quote+history' | 'Price+history only; quoteSummary blocked (PE/margins unavailable)' | other status>",
  "why_now": "<see Step 2>",
  "freshness_days": <int>,
  "bear_case": "<see Step 2>",
  "watch_next": "<see Step 2>"
}
```

Plus mode extras: `role`, `expense_ratio`, `aum`, `top_holdings_summary` (balanced) or `checklist` (contrarian) as defined in Step 3.

---

## Failure handling

If `fundamentals.py` returned `status: "error"` for this ticker:

```
{"ticker": "<T>", "error": "fundamentals fetch failed", "fundamentals_note": "<reason from fundamentals.py output>"}
```

The orchestrator will skip the slot and note "could not analyze TICKER" in the brief.

Never fabricate. If the data isn't there, say so.
