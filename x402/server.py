"""PegWatch x402 — serveur qui vend le rapport de l'agent derrière un mur HTTP 402.

  python -m pegwatch.x402.server      # sert sur http://localhost:8402/report

GET /report sans paiement   -> 402 + conditions (0.01 USDC sur Base, payTo, asset…)
GET /report avec X-PAYMENT  -> vérifie la signature, settle on-chain, renvoie le rapport.
"""
import os
import sys
import json
import base64
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

from pegwatch import config
from pegwatch.x402 import common, settle as settle_mod

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PORT = int(os.environ.get("X402_PORT", "8402"))
PRICE_USDC = float(os.environ.get("X402_PRICE", "0.01"))


def pay_to():
    return json.loads((Path(__file__).parent.parent / "onchain" / "treasury.json").read_text(encoding="utf-8"))["address"]


def latest_report():
    f = config.REPORT_DIR / "latest.md"
    return f.read_text(encoding="utf-8") if f.exists() else "(aucun rapport — lance d'abord `python -m pegwatch.agent`)"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, extra=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _402(self, reqs, error):
        self._send(402, {"x402Version": common.X402_VERSION, "accepts": [reqs], "error": error})

    def do_GET(self):
        if self.path.split("?")[0] != "/report":
            self._send(404, {"error": "not found — try /report"}); return

        reqs = common.build_requirements(
            pay_to(), PRICE_USDC, f"http://localhost:{PORT}/report",
            "PegWatch — tokenized-stock peg report (Mantle)")

        hdr = self.headers.get("X-PAYMENT")
        if not hdr:
            self._402(reqs, "X-PAYMENT header required"); return
        try:
            payload = common.decode_header(hdr)
        except Exception as e:
            self._402(reqs, f"X-PAYMENT illisible: {e}"); return

        ok, reason = common.verify_payment(payload, reqs)
        if not ok:
            self._402(reqs, f"paiement invalide: {reason}"); return

        print(f"[server] paiement vérifié de {payload['payload']['authorization']['from']} — settle…")
        try:
            res = settle_mod.settle(payload)
        except Exception as e:
            self._402(reqs, f"settle a échoué: {e}"); return
        if not res.get("success"):
            self._send(402, {"x402Version": common.X402_VERSION, "accepts": [reqs],
                             "error": "settlement non confirmé", "settlement": res}); return

        print(f"[server] payé ✅ tx {res['transaction']}")
        self._send(200, {"report": latest_report(), "settlement": res},
                   {"X-PAYMENT-RESPONSE": base64.b64encode(json.dumps(res).encode()).decode()})

    def log_message(self, *a):
        pass


def main():
    print(f"PegWatch x402 server → http://localhost:{PORT}/report")
    print(f"  payTo : {pay_to()}  | prix : {PRICE_USDC} USDC (Base mainnet)")
    print("  Ctrl+C pour arrêter.")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
