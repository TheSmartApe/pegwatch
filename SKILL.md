---
name: pegwatch
description: Fact-check tokenized stocks (xStocks) on Mantle. Use when asked whether a tokenized equity on Mantle tracks its real price, to find peg breaks or arbitrage windows between on-chain and real-world prices, or to map which of Mantle's tokenized stocks are actually liquid vs ghost listings.
homepage: https://github.com/TheSmartApe/pegwatch
metadata:
  openclaw: {"requires":{"bins":["python"],"env":[],"config":[]},"install":[{"run":"python -m pip install -q -r requirements.txt"}]}
---

# PegWatch — tokenized-stock reality check on Mantle

PegWatch compares every xStocks tokenized equity deployed on **Mantle** (chain id 5000) to its
real-world reference price, and reports premium/discount, broken pegs, arbitrage windows, and
off-hours drift. The core uses **no API key**.

## When to use this skill
- "Does TSLAx / NVDAx / SPCXx on Mantle track the real stock right now?"
- "Find me mispriced tokenized stocks on Mantle / any arbitrage windows."
- "How many of Mantle's tokenized stocks are actually liquid?"
- "Is the SpaceX (SPCXx) token holding its peg?"

## How it works
1. Pulls the universe of xStocks on Mantle (xStocks public API).
2. Gets each token's on-chain DEX price (DefiLlama coins) and reference NAV (xStocks).
3. Computes `premium = (onchain - nav) / nav`, classifies each token
   (`blue_chip` / `mid` / `broken`), and flags `peg_break` (>3%), `thin_liquidity`,
   and `off_hours_drift` (deviation while US market is closed).
4. Writes a JSON snapshot, a markdown report, and an X-post draft.

## How to run
From the repository root (the directory containing the `pegwatch/` package):

```bash
python -m pegwatch.agent            # focus list (14 liquid names), ~40s
python -m pegwatch.agent --full     # all ~157 Mantle xStocks, ~3min
python -m pegwatch.agent --brain    # + LLM interpretation (needs OPENAI_API_KEY)
```

Outputs land in `pegwatch/reports/latest.md` (human report) and
`pegwatch/data/snapshots/<timestamp>.json` (raw data; accumulates a 24/7 drift dataset).

## How to read the output
- **tier `blue_chip`** — pegs within ±0.5% at deep liquidity: behaves like the real stock.
- **tier `broken`** — |premium| ≥ 3% or thin pricing: do not treat as a clean arb until volume
  is confirmed (an extreme premium, e.g. >10%, usually means a near-dead pool with a stale price).
- **flag `off_hours_drift`** — the deviation appeared while US markets were closed; compare during
  the regular session (9:30–16:00 ET) for an apples-to-apples read.
- Pair any "arbitrage" claim with on-chain volume (Dune `dex.trades` on Mantle) before acting.

## Identity
This skill's agent can carry an on-chain **ERC-8004** identity on Mantle (Identity Registry
`0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`) so its research calls leave an auditable
reputation trail. See `pegwatch/onchain/mint_identity.py`.
