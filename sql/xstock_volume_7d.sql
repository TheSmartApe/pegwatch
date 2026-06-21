-- PegWatch — volume DEX décodé (7j) des xStocks sur Mantle
-- Sert à confirmer si un peg cassé = vrai arbitrage (volume réel) ou pool fin.
-- NB: amount_usd peut être NULL si le token n'est pas dans le price feed de Dune
--     (cas de SPCXx au lancement). Étendre la liste VALUES aux 157 adresses
--     depuis pegwatch/data/universe.json pour la couverture complète.
WITH xstocks (sym, addr) AS (
  VALUES
   ('TSLAx',  0x8ad3c73f833d3f9a523ab01476625f269aeb7cf0),
   ('NVDAx',  0xc845b2894dbddd03858fd2d643b4ef725fe0849d),
   ('AAPLx',  0x9d275685dc284c8eb1c79f6aba7a63dc75ec890a),
   ('METAx',  0x96702be57cd9777f835117a809c7124fe4ec989a),
   ('GOOGLx', 0xe92f673ca36c5e2efd2de7628f815f84807e803f),
   ('SPYx',   0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48),
   ('QQQx',   0xa753a7395cae905cd615da0b82a53e0560f250af),
   ('SPCXx',  0x68fa48b1c2fe52b3d776e1953e0e782b5044ce28),
   ('MSTRx',  0xae2f842ef90c0d5213259ab82639d5bbf649b08e),
   ('COINx',  0x364f210f430ec2448fc68a49203040f6124096f0),
   ('HOODx',  0xe1385fdd5ffb10081cd52c56584f25efa9084015),
   ('CRCLx',  0xfebded1b0986a8ee107f5ab1a1c5a813491deceb)
)
SELECT
  x.sym,
  count(*)                    AS trades_7d,
  sum(t.amount_usd)           AS volume_usd_7d,
  max(t.block_time)           AS last_trade,
  approx_distinct(t.tx_hash)  AS txs
FROM dex.trades t
JOIN xstocks x
  ON x.addr IN (t.token_bought_address, t.token_sold_address)
WHERE t.blockchain = 'mantle'
  AND t.block_date >= CURRENT_DATE - INTERVAL '7' DAY
GROUP BY 1
ORDER BY volume_usd_7d DESC;
