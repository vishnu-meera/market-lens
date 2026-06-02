# Shared orchestration recipe

The 9-step pipeline every invest-* skill follows. The calling `SKILL.md` provides
mode-specific config (mode, subreddits, scout set, allocation weights, extras),
then tells the LLM: "read this file and execute the steps using my config."

This is the single source of truth for the pipeline. Bug fixes, new features,
and shared helpers (`fundamentals.py`, `reddit_fetch.py`, `journal.py`, etc.)
all wire in here, not into per-skill files.

---

## Configuration the calling SKILL.md must define

Before referencing this file, the SKILL.md should have set (in plain text the
LLM can read):

- `<MODE>` — `momentum` | `balanced` | `contrarian`
- `<SKILL_NAME>` — e.g. `invest-momentum`
- `<SCRIPTS_DIR>` — typically `<SKILL_DIR>/../../scripts`
- `<REPORTS_DIR>` — typically `<SKILL_DIR>/../../reports`
- `<REDDIT_SUBS>` — list of subreddit names (no `r/` prefix)
- `<SCOUT_FILES>` — paths to mode-specific scout files (Reddit handled by `_shared/agents/scout-reddit-base.md`)
- `<NUM_PICKS>` — typically 5
- `<ALLOC>` — `equal` or explicit weights like `0.35,0.25,0.20,0.12,0.08`
- `<ANALYST_EXTRAS>` — `none` | `role` (balanced) | `checklist` (contrarian)

---

## Step 1 — Parse the dollar amount

Scan the user's message for: `$100`, `$1,000`, `1000`, `invest 500`, `with 250 dollars`.

- Found → use it.
- Not found → ask ONCE: "How much do you have to invest?" Use the answer.
- < $20 → warn about diversification but continue.

---

## Step 2 — Wave 1: spawn all scouts in parallel

Dispatch every scout in `<SCOUT_FILES>` plus the Reddit scout in **one parallel batch**.

On Claude Code: one message with N `Agent` tool calls (`subagent_type: "general-purpose"`). Other harnesses: equivalent parallel mechanism. **Never sequential.**

For Reddit, the agent prompt is:

> Read `<SKILL_DIR>/../_shared/agents/scout-reddit-base.md` and execute it for subreddits `<REDDIT_SUBS>` in mode `<MODE>`. Return only the JSON array specified in that file — no preamble.

For mode-specific scouts (finviz, stocktwits, insider, sec, etfdb, macro, etfflows):

> Read `<SKILL_DIR>/agents/<scout-file>.md` and execute its instructions exactly. Return only the JSON output specified.

Each scout returns either an array of picks or `[{"error": "..."}]`.

---

## Step 3 — Aggregate, score, apply price-context guard

3a. **Dedupe** tickers case-insensitively across scout outputs.

3b. **Score** each ticker. Base: `score = (num_distinct_scouts × 3) + total_mentions`. Apply mode-specific weights from the calling SKILL.md (e.g., contrarian's `insider +5`, `13D +6`). Set `confidence_scouts` = number of distinct scouts that surfaced this ticker (used later for the star rating in the HTML).

3c. **Price-context guard.** For the top N+3 candidates by score, call:

```
python3 <SCRIPTS_DIR>/fundamentals.py <T1> <T2> ... <TN+3>
```

For each ticker, check `context.trending_top_tick_risk`. If `"warning"` (trailing 1-month return > 20%):
  - Subtract 5 from its score (it's likely a momentum top-tick).
  - Set `top_tick_warning: true` for use later.
  - Note `trailing_return_pct` for the brief.

Re-sort descending. Take top `<NUM_PICKS>`. Keep 2–3 runners-up with reason dropped.

3d. **Cache the fundamentals JSON** in memory for Wave 2 — don't refetch.

---

## Step 4 — Wave 2: spawn analyst sub-agents in parallel

One agent per pick, all dispatched in a **single parallel batch**. Each prompt:

> Read `<SKILL_DIR>/../_shared/agents/analyst-base.md` and execute it for ticker `<TICKER>` in mode `<MODE>` with extras `<ANALYST_EXTRAS>`. The fundamentals.py output for this ticker is: `<paste the cached JSON entry>`. Return only the JSON object specified — no preamble.

Passing the cached fundamentals JSON in the prompt avoids a second Yahoo call per ticker.

If an analyst returns `{"error": ...}`, note "could not analyze TICKER — fundamentals fetch failed" in the brief and skip the slot. Don't substitute another ticker.

---

## Step 5 — Compute allocations

Run:

```
python3 <SCRIPTS_DIR>/allocate.py <amount> <T1>:<P1>[:<W1>] <T2>:<P2>[:<W2>] ...
```

- `<ALLOC>` is `equal` → omit weights, equal split.
- `<ALLOC>` is explicit (e.g. `0.35,0.25,0.20,0.12,0.08`) → pass `:<weight>` per ticker.

Prices come from analyst output. The script prints whole-share + fractional strategies.

---

## Step 6 — Write HTML report

6a. Compose the data JSON. Required fields per pick:

```
{
  "rank": 1, "ticker": "...", "type": "Stock|ETF", "price": N,
  "allocation": N, "whole_shares": N, "frac_shares": N,
  "scout_score": N, "scout_sources": "...",
  "confidence_scouts": N,         // for ★ rating
  "top_tick_warning": true|false, // from price guard
  "trailing_return_pct": N,       // from fundamentals
  "name": "...", "sector": "...",
  "market_cap": N, "pe_trailing": N, "dividend_yield": N,
  "fundamentals_note": "...",     // from analyst
  "why_now": "...", "freshness_days": N,
  "bear_case": "...", "watch_next": "..."
}
```

Plus mode extras (`role`/`expense_ratio`/`aum`/`top_holdings_summary` for balanced; `checklist` for contrarian).

Top-level: `skill_type`, `skill_name`, `amount`, `generated_at`, `scouts_ok`, `scouts_fail`, `picks`, `runners_up`, `how_picked`.

Write to `/tmp/etw-<MODE>-<YYYYMMDD-HHMMSS>.json`.

6b. Generate the HTML:

```
python3 <SCRIPTS_DIR>/generate_html.py /tmp/etw-<MODE>-<YYYYMMDD-HHMMSS>.json
```

The script prints the output path and writes both `.html` and `.json` under `<REPORTS_DIR>`. Show the user the path before rendering the markdown brief.

---

## Step 7 — Append picks to the journal

Right after Step 6b, run:

```
python3 <SCRIPTS_DIR>/journal.py <REPORTS_DIR>/<filename>.json
```

This appends each pick to `<REPORTS_DIR>/_picks.jsonl` for retrospective scoring by `scripts/score.py`. Silent on success.

---

## Step 8 — Synthesize the markdown brief

Use the mode-specific template defined in the calling SKILL.md. Render in the conversation. Include:

- The report path from Step 6b
- A ★ confidence rating per pick (mapping `confidence_scouts` → stars; max stars = max scouts in the wave)
- A ⚠️ "trailing 1mo +N%" tag if `top_tick_warning` is true
- A note for any pick where `fundamentals_note` reports a partial fetch (Yahoo quoteSummary missing) so the user knows the PE / margins are best-effort

---

## Step 9 — Offer dashboard + GitHub publish

9a. **Dashboard.** Ask:
> "Open the report dashboard in your browser? (y/n)"

If yes, run in the **background** (Claude Code: `Bash` with `run_in_background: true`):
```
python3 <SCRIPTS_DIR>/serve.py
```

Tell the user: "Dashboard at http://127.0.0.1:8765/ — Ctrl+C in that terminal to stop."

If port 8765 is already in use (a server is already running from a previous turn), skip the launch and just point them at the existing URL.

9b. **GitHub publish.** Scan the user's original message for a GitHub repo reference. Match:
- `https://github.com/owner/repo[.git]`
- `git@github.com:owner/repo[.git]`
- Bare `owner/repo` — only treat as GitHub if the surrounding text mentions "github", "repo", "save", or "publish"

If found, ask: "Publish this report to `<owner/repo>`? [y/N]" → if yes, run:
```
python3 <SCRIPTS_DIR>/publish_github.py --repo <owner/repo> --report <REPORTS_DIR>/<filename>.html --yes
```

Surface the GitHub URL the script prints.

If no repo URL was in the original message, ask once: "Want to save this report to GitHub? Reply with an `owner/repo` or repo URL, or skip."

---

## Generic don'ts (apply to every skill)

- Never run scouts sequentially — parallel only.
- Never fabricate fundamentals when `fundamentals.py` fails — say "data unavailable" instead.
- Never skip the disclaimer in the markdown brief.
- Never recommend buying — only "here's what surfaced, here's the math, here's why."
- Never substitute a pick when an analyst fails on one ticker — show the gap.
