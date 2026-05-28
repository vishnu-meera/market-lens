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

## Directory layout

```
market-lens/
  skills/
    invest-momentum/
      SKILL.md
      agents/
        scout-reddit.md
        scout-stocktwits.md
        scout-finviz.md
        scout-etfflows.md
        analyst.md
    invest-balanced/
      SKILL.md
      agents/
        scout-reddit.md
        scout-etfdb.md
        scout-macro.md
        analyst.md
    invest-contrarian/
      SKILL.md
      agents/
        scout-reddit.md
        scout-insider.md
        scout-finviz.md
        scout-sec.md
        analyst.md
  scripts/
    allocate.py
    generate_html.py
  reports/
```
