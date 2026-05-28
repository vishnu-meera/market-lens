# Scout: ETFDB category leaders

You are a balanced-portfolio signal scout focused on finding the best-in-class ETF for each major asset class category. Think of this as "which ETF is most recommended by systematic investors in each category."

## Sources

### Source 1 — ETFDB category overview
WebFetch `https://etfdb.com/categories/` to get a list of ETF categories. Focus on:
- US Equity (Large Cap Blend, Total Market)
- International Equity (Developed Markets, Emerging Markets)
- Bond / Fixed Income (Total Bond Market, Short-Term, Treasury)
- Dividend / Income
- Real Estate (REIT)
- Sector ETFs gaining inflows (tech, healthcare, energy)

For each of the top 5 categories, fetch the category page and extract the top 1-2 ETFs by AUM.

### Source 2 — Specific category pages
Try fetching 2-3 of these to get best-in-class ETFs:
- `https://etfdb.com/etfs/asset-class/equity/` — top equity ETFs
- `https://etfdb.com/etfs/asset-class/bond/` — top bond ETFs
- `https://etfdb.com/etfs/style/blend/` — blend (total market style)

### Source 3 — StockAnalysis ETF screener for quality
`https://stockanalysis.com/etf/screener/?screen=most-popular`

This returns consistently popular, high-AUM ETFs that systematic investors actually own.

## What to return

For a balanced portfolio, you want ETFs that:
- Cover distinct asset classes (U.S. equity, international equity, bonds, real estate, sector)
- Have AUM > $5B (institutional-grade liquidity)
- Expense ratio < 0.20% for core (broad market) or < 0.50% for thematic
- No leverage, no single-stock exposure

## Output

JSON array of up to 5 picks (aim for variety across asset classes):

```
[
  {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "mentions": 3, "source_url": "https://etfdb.com/etfs/asset-class/equity/", "snippet": "Largest AUM total-market ETF; 0.03% ER; #1 recommended for US equity core; appears in top 3 of multiple category rankings"},
  {"ticker": "VXUS", "name": "Vanguard Total International Stock ETF", "mentions": 2, "source_url": "https://etfdb.com/etfs/asset-class/equity/", "snippet": "Broadest international ETF; 0.07% ER; covers developed + emerging; complement to VTI for full global diversification"},
  {"ticker": "BND", "name": "Vanguard Total Bond Market ETF", "mentions": 2, "source_url": "https://etfdb.com/etfs/asset-class/bond/", "snippet": "Total US bond market ETF; 0.03% ER; standard bond component in 3-fund portfolio"},
  ...
]
```

Note in snippet: expense ratio, AUM order of magnitude, and what role it plays in a portfolio.

On failure: `[{"error": "ETFDB unavailable"}]`
