"""PegWatch — cross-check Dune : volume DEX décodé des xStocks sur Mantle.

Confirme si un peg cassé est un vrai arbitrage (volume réel) ou un pool fin / non-décodé.

Découverte clé (2026-06-21) : sur `dex.trades` Mantle, les DEX décodés sont
merchant_moe / agni / fusionx / uniswap. **Fluxion N'EST PAS décodé** → le volume
xStock natif (Fluxion Atomic RFQ) est invisible à Dune. Le seul xStock avec du volume
décodé notable est SPCXx (sur Merchant Moe, incentivé) — et son amount_usd est NULL
(token absent du price feed Dune). Conclusion : un écart de peg sur Mantle ne peut PAS
être présenté comme un arbitrage exécutable tant que la liquidité du venue n'est pas
confirmée hors-Dune.

Usage :
  DUNE_API_KEY=...  python -m pegwatch.dune_volume      # exécute la query sauvegardée
  (sans clé : imprime le SQL à coller sur dune.com)
"""
import os
import sys
import json
import time
from urllib.request import Request, urlopen

from pegwatch import config

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DUNE_API = "https://api.dune.com/api/v1"
QUERY_ID = os.environ.get("DUNE_QUERY_ID", "7771652")   # PegWatch — xStock 7d volume on Mantle
SQL_PATH = config.ROOT / "sql" / "xstock_volume_7d.sql"


def _req(path, method="GET", body=None):
    headers = {"X-Dune-API-Key": os.environ.get("DUNE_API_KEY", ""), "Content-Type": "application/json"}
    req = Request(f"{DUNE_API}{path}", data=json.dumps(body).encode() if body else None,
                  headers=headers, method=method)
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    if not os.environ.get("DUNE_API_KEY"):
        print("ℹ️  DUNE_API_KEY non défini. SQL à exécuter sur dune.com :\n")
        print(SQL_PATH.read_text(encoding="utf-8"))
        return

    ex = _req(f"/query/{QUERY_ID}/execute", "POST", {"performance": "small"})
    eid = ex.get("execution_id")
    print(f"execution : {eid}")
    for _ in range(40):
        res = _req(f"/execution/{eid}/results")
        state = res.get("state")
        if state == "QUERY_STATE_COMPLETED":
            rows = res.get("result", {}).get("rows", [])
            print(f"\n{len(rows)} ligne(s) :\n")
            print(f"{'sym':8} {'trades_7d':>10} {'volume_usd':>14} {'last_trade':>22}")
            for r in rows:
                vol = r.get("volume_usd_7d")
                print(f"{r.get('sym',''):8} {r.get('trades_7d',0):>10} "
                      f"{('null' if vol is None else f'{vol:,.0f}'):>14} {str(r.get('last_trade',''))[:22]:>22}")
            return
        if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED", "QUERY_STATE_EXPIRED"):
            print(f"échec : {state}"); return
        time.sleep(3)
    print("timeout — vérifie sur dune.com/queries/" + QUERY_ID)


if __name__ == "__main__":
    main()
