"""PegWatch x402 — client qui paie le rapport (le payeur = wallet de l'agent).

  python -m pegwatch.x402.client      # paie http://localhost:8402/report

Démontre le flux x402 complet : 402 → signe l'autorisation EIP-3009 (gasless) → repaie.
"""
import os
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from pegwatch import config
from pegwatch.x402 import common

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SERVER = os.environ.get("X402_SERVER", "http://localhost:8402/report")


def get(url, headers=None):
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except HTTPError as e:
        return e.code, json.loads(e.read()), dict(e.headers)


def main():
    pk = os.environ.get("MANTLE_PRIVATE_KEY")  # le wallet payeur (l'agent)
    if not pk:
        print("⛔ MANTLE_PRIVATE_KEY absent du .env (c'est le wallet payeur)."); sys.exit(1)

    code, body, _ = get(SERVER)
    print(f"1) GET /report (sans paiement) → {code}")
    if code != 402:
        print(json.dumps(body, indent=2, ensure_ascii=False)); return
    reqs = body["accepts"][0]
    print(f"   conditions : {common.fmt_usdc(reqs['maxAmountRequired'])} USDC ({reqs['network']}) → payTo {reqs['payTo']}")

    payload = common.sign_payment(pk, reqs)
    payer = payload["payload"]["authorization"]["from"]
    print(f"2) autorisation EIP-3009 signée (gasless) par {payer}")

    code, body, headers = get(SERVER, {"X-PAYMENT": common.encode_header(payload)})
    print(f"3) GET /report (avec X-PAYMENT) → {code}")
    if code == 200:
        s = body["settlement"]
        print(f"   ✅ payé {s['value_usdc']} USDC | block {s['block']}")
        print(f"   tx : {s['transaction']}")
        print(f"   explorer : {s['explorer']}")
        print("\n--- rapport reçu (extrait) ---\n")
        print((body.get("report") or "")[:700])
    else:
        print(json.dumps(body, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
