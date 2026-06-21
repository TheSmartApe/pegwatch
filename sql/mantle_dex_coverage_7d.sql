-- PegWatch — couverture des DEX décodés sur Mantle (7j)
-- Permet de savoir quels venues sont visibles dans dex.trades.
-- Résultat 2026-06-21 : merchant_moe, agni, fusionx, uniswap sont décodés.
--   → Fluxion (venue natif xStocks via Atomic RFQ) N'EST PAS décodé : son volume
--     est invisible à Dune. À garder en tête avant toute conclusion sur la liquidité.
SELECT
  project,
  count(*)                               AS trades_7d,
  approx_distinct(token_bought_address)  AS distinct_tokens_bought,
  count(amount_usd)                      AS trades_with_usd
FROM dex.trades
WHERE blockchain = 'mantle'
  AND block_date >= CURRENT_DATE - INTERVAL '7' DAY
GROUP BY 1
ORDER BY trades_7d DESC;
