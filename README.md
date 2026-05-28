# ETW Finder: Investment Research Skills for Gemini CLI

A collection of autonomous investment research skills for the Gemini CLI. These skills crawl various financial data sources (Reddit, Finviz, SEC, OpenInsider, ETF flows, etc.) to produce structured research briefs and portfolio recommendations.

## 🚀 Skills Included

- **`invest-balanced`**: Builds diversified, Boglehead-style portfolios with core ETF holdings and tactical satellite positions.
- **`invest-momentum`**: Identifies what's trending across retail and institutional flows for short-term discretionary cash.
- **`invest-contrarian`**: Finds undervalued "hidden gems" ignored by Wall Street using a 4-ingredient quality checklist.

## 🛠️ Installation (Local Link)

To use these skills in your Gemini CLI session, symlink the skill directories to your Gemini skills folder:

```bash
# Example for macOS
ln -s $(pwd)/invest-balanced ~/.gemini/skills/invest-balanced
ln -s $(pwd)/invest-momentum ~/.gemini/skills/invest-momentum
ln -s $(pwd)/invest-contrarian ~/.gemini/skills/invest-contrarian
```

Alternatively, add this directory to your `include` paths in `~/.gemini/config.json`.

## 📊 Reports

All research briefs are output as:
1.  **JSON Data**: Raw analysis for further processing.
2.  **Styled HTML**: A beautiful, GitHub-themed dashboard for manual review.

Reports are saved in the `reports/` directory.

## ⚠️ Disclaimer

**Research brief only. Not financial advice.**
Investing involves risk. Always verify data and news before acting. The authors are not responsible for any financial losses.
