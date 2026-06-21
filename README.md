# PegWatch

An autonomous research agent that fact-checks **tokenized stocks (xStocks) on Mantle**: it
compares each token's **on-chain DEX price** to its **real-world reference price (NAV)**, flags
broken pegs / arbitrage windows / off-hours drift, and writes a report — twice a day.

Built for the **Mantle Research Challenge — Track 2 (Research Agent)**.

## Why it exists

Mantle markets itself as *"the distribution layer connecting TradFi & onchain liquidity"* and
lists **157 tokenized US equities** via xStocks. PegWatch asks the obvious question nobody had
measured: **do these tokens actually track reality — and where does it break?**

The first run already surfaced the headline finding: there are **two markets** under one label.
A handful of blue chips (TSLA, NVDA, META, GOOGL, AAPL…) peg within ±0.3% of their real price;
the long tail (HOOD, COIN, MSTR…) drifts 3–9%. Peg fidelity ≈ a function of on-chain liquidity.

## How it works

```
xStocks API ───► reference price (NAV, real-world)  ┐
                                                     ├─► premium/discount ─► flags ─► report
DefiLlama  ───► on-chain DEX price + confidence     ┘                                  │
DefiLlama  ───► chain / protocol TVL (liquidity context)                              │
Finnhub*   ───► real stock price cross-check (optional)                               │
clock      ───► US market session (open/closed/weekend) ─► off-hours drift            │
                                                                                       ▼
                                              snapshot JSON  +  markdown report  +  X draft
```

`*` optional, needs `FINNHUB_API_KEY`. The **core needs no API key.**

### Modules
- `config.py` — endpoints, thresholds, env loading
- `sources.py` — data fetchers (xStocks, DefiLlama, Finnhub, market clock)
- `analyze.py` — premium/discount, classification (blue_chip / mid / broken), anomaly flags
- `brain.py` — interpretation layer (heuristic by default, OpenAI with `--brain`)
- `report.py` — markdown report + X-post draft
- `agent.py` — orchestrator

## Run

```bash
python -m pegwatch.agent            # focus list (14 liquid names), fast
python -m pegwatch.agent --full     # all ~157 Mantle xStocks
python -m pegwatch.agent --brain    # + LLM interpretation (needs OPENAI_API_KEY)
```

Outputs:
- `data/snapshots/<ts>.json` — raw snapshot (accumulates the 24/7 drift dataset)
- `reports/<ts>.md` + `reports/latest.md` — readable report
- an X-post draft printed to console

## The Mantle agent stack (Track 2 "depth of integration")

PegWatch is designed to plug into Mantle's agent primitives (next build steps):
- **ERC-8004 identity** — mint the agent an on-chain identity on Mantle
  (`0x8004A169FB4a3325136EB29fA0ceB6D2e539a432`, live, verified on mantlescan) so its
  research calls carry an auditable reputation trail.
- **Mantle AI Agent Skill** — package the research capability as a `SKILL.md`
  (OpenClaw / `npx skills` format) so any agent can install it.
- **x402** — (optional) put the daily report behind an HTTP-402 paywall via the
  Questflow facilitator on Mantle, so other agents pay USDC to consume it.

## Data sources (all primary)
- xStocks public API — `https://api.xstocks.fi/api/v2/public`
- DefiLlama coins — `https://coins.llama.fi/prices/current/mantle:{address}`
- DefiLlama TVL — `https://api.llama.fi`
- Finnhub (optional) — `https://finnhub.io/api/v1`

## Caveats
- DefiLlama's `confidence` is a liquidity proxy, not ground truth — pair with real TVL/volume
  (Dune `dex.trades` on Mantle) before calling any spread a tradable arbitrage.
- **Dune cross-check (2026-06-21):** on Mantle `dex.trades`, only `merchant_moe`, `agni`,
  `fusionx` and `uniswap` are decoded — **Fluxion (the xStocks-native venue) is NOT**, so
  xStock volume routed through Fluxion is invisible to Dune. The only xStock with notable
  decoded volume is **SPCXx** (218 trades / 7d on Merchant Moe, incentivized), and even its
  `amount_usd` is NULL (not in Dune's price feed). Net: a peg gap on Mantle can NOT be
  presented as an executable arbitrage until the venue's liquidity is confirmed off-Dune.
  Queries: `sql/xstock_volume_7d.sql`, `sql/mantle_dex_coverage_7d.sql`; runner: `dune_volume.py`.
- Reference price (NAV) is the xStocks-published quote; cross-check with Finnhub for the
  liquid names.
- SpaceX (SPCX) only began trading on 2026-06-12 — early price history is thin.
