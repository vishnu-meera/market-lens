#!/usr/bin/env python3
"""
allocate.py — split a dollar amount across picks using whole-share and
fractional-share strategies.

Usage:
    python allocate.py <amount> <ticker:price[:weight]> ...

Equal-weight (no weights given):
    python allocate.py 200 NVDA:450 SPY:520 VTI:240 SCHD:78 QQQ:430

Explicit weights (must sum freely; will be normalized):
    python allocate.py 1000 NVDA:450:0.3 SPY:520:0.4 VTI:240:0.3

Stdlib only.
"""
import sys


def parse_amount(s: str) -> float:
    return float(s.lstrip("$").replace(",", ""))


def parse_tuple(s: str):
    parts = s.split(":")
    if len(parts) == 2:
        ticker, price = parts
        weight = None
    elif len(parts) == 3:
        ticker, price, weight_str = parts
        weight = float(weight_str)
    else:
        raise ValueError(f"Bad tuple {s!r}: expected ticker:price[:weight]")
    return ticker.upper(), float(price), weight


def allocate(amount: float, picks):
    weights = [w for _, _, w in picks]
    if all(w is None for w in weights):
        n = len(picks)
        weights = [1.0 / n] * n
    elif any(w is None for w in weights):
        raise ValueError("Mix of weighted and unweighted picks — provide weights for all or none.")
    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    rows, whole_total, frac_total = [], 0.0, 0.0
    for (ticker, price, _), w in zip(picks, weights):
        target = amount * w
        whole = int(target // price)
        whole_cost = whole * price
        leftover = target - whole_cost
        frac = round(target / price, 4)
        frac_cost = round(frac * price, 2)
        rows.append((ticker, price, w, target, whole, whole_cost, leftover, frac, frac_cost))
        whole_total += whole_cost
        frac_total += frac_cost
    return rows, whole_total, frac_total


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    amount = parse_amount(sys.argv[1])
    picks = [parse_tuple(s) for s in sys.argv[2:]]
    rows, whole_total, frac_total = allocate(amount, picks)

    print(f"Allocation for ${amount:,.2f} across {len(picks)} picks\n")
    header = f"{'Ticker':<8}{'Price':>10}{'Weight':>9}{'Target':>11}{'Whole':>7}{'Cost':>11}{'Cash':>11}{'Frac':>9}"
    print(header)
    print("-" * len(header))
    for t, p, w, target, whole, whole_cost, leftover, frac, _ in rows:
        print(f"{t:<8}${p:>8,.2f}{w*100:>8.1f}%${target:>9,.2f}{whole:>7d}${whole_cost:>9,.2f}${leftover:>9,.2f}{frac:>9.4f}")
    print("-" * len(header))
    print(f"Whole-share strategy:      ${whole_total:,.2f} invested, ${amount - whole_total:,.2f} cash leftover")
    print(f"Fractional-share strategy: ${frac_total:,.2f} invested (~${amount - frac_total:,.2f} rounding)")


if __name__ == "__main__":
    main()
