"""PegWatch x402 — primitives partagées (Base mainnet, schéma `exact`).

Tout est en urllib + eth_account/eth_abi/eth_utils (compatible sandbox, pas de requests).
Détails vérifiés on-chain : domaine EIP-712 USDC Base = name "USD Coin", version "2".
"""
import os
import json
import time
import base64
import secrets

from urllib.request import Request, urlopen
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak
from eth_abi import encode as abi_encode

from pegwatch import config  # charge .env

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CHAIN_ID = 8453
NETWORK = "base"
X402_VERSION = 1
USDC_DECIMALS = 6
DOMAIN = {"name": "USD Coin", "version": "2", "chainId": CHAIN_ID, "verifyingContract": USDC_BASE}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# endpoints Base (failover) — BASE_RPC en tête si défini
_RPCS = []
for _ep in [os.environ.get("BASE_RPC"), "https://base.publicnode.com", "https://mainnet.base.org",
            "https://1rpc.io/base", "https://base-rpc.publicnode.com", "https://base.drpc.org"]:
    if _ep and _ep not in _RPCS:
        _RPCS.append(_ep)
BASE_RPC = _RPCS[0]


def rpc(method, params, retries=2):
    """JSON-RPC Base avec retry + bascule d'endpoint sur erreur réseau.
    Une erreur RPC déterministe (revert, etc.) est propagée immédiatement (pas de failover)."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for ep in _RPCS:
        for _ in range(retries):
            try:
                req = Request(ep, data=body, headers={"Content-Type": "application/json", "User-Agent": UA})
                with urlopen(req, timeout=20) as r:
                    d = json.loads(r.read())
            except (OSError, ValueError) as e:   # réseau / SSL / JSON illisible → on bascule
                last = e
                time.sleep(1)
                continue
            if d.get("error"):                   # erreur RPC déterministe → on propage
                raise RuntimeError(d["error"])
            return d["result"]
    raise RuntimeError(f"tous les RPC Base ont échoué: {last}")


def usdc_atomic(amount_usdc):
    return int(round(amount_usdc * 10 ** USDC_DECIMALS))


def fmt_usdc(atomic):
    return int(atomic) / 10 ** USDC_DECIMALS


def build_requirements(pay_to, amount_usdc, resource, description, timeout_s=60):
    """Le `paymentRequirements` renvoyé dans la 402 (sous accepts[])."""
    return {
        "scheme": "exact",
        "network": NETWORK,
        "maxAmountRequired": str(usdc_atomic(amount_usdc)),
        "resource": resource,
        "description": description,
        "mimeType": "application/json",
        "payTo": pay_to,
        "maxTimeoutSeconds": timeout_s,
        "asset": USDC_BASE,
        "extra": {"name": DOMAIN["name"], "version": DOMAIN["version"]},
    }


def _typed_data(auth):
    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "domain": DOMAIN,
        "primaryType": "TransferWithAuthorization",
        "message": {
            "from": auth["from"], "to": auth["to"], "value": int(auth["value"]),
            "validAfter": int(auth["validAfter"]), "validBefore": int(auth["validBefore"]),
            "nonce": auth["nonce"],
        },
    }


def _sig_hex(signed):
    h = signed.signature.hex()
    return h if h.startswith("0x") else "0x" + h


def sign_payment(priv_key, requirements):
    """Côté payeur : signe l'autorisation EIP-3009 (gasless) et renvoie le payload x402."""
    acct = Account.from_key(priv_key)
    now = int(time.time())
    timeout = int(requirements.get("maxTimeoutSeconds", 60))
    auth = {
        "from": acct.address,
        "to": requirements["payTo"],
        "value": str(requirements["maxAmountRequired"]),
        "validAfter": "0",
        "validBefore": str(now + timeout + 60),
        "nonce": "0x" + secrets.token_bytes(32).hex(),
    }
    signed = Account.sign_message(encode_typed_data(full_message=_typed_data(auth)), priv_key)
    return {
        "x402Version": X402_VERSION, "scheme": "exact", "network": NETWORK,
        "payload": {"signature": _sig_hex(signed), "authorization": auth},
    }


def encode_header(payload):
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_header(header_value):
    return json.loads(base64.b64decode(header_value))


def verify_payment(payload, requirements):
    """Côté facilitator : vérifie la signature + la conformité aux exigences. -> (ok, raison)."""
    try:
        auth = payload["payload"]["authorization"]
        sig = payload["payload"]["signature"]
        signer = Account.recover_message(encode_typed_data(full_message=_typed_data(auth)), signature=sig)
    except Exception as e:
        return False, f"signature illisible: {e}"
    if signer.lower() != auth["from"].lower():
        return False, "signature ne correspond pas au payeur (from)"
    if auth["to"].lower() != requirements["payTo"].lower():
        return False, "payTo incorrect"
    if int(auth["value"]) < int(requirements["maxAmountRequired"]):
        return False, "montant insuffisant"
    now = int(time.time())
    if now < int(auth["validAfter"]):
        return False, "autorisation pas encore valide"
    if now > int(auth["validBefore"]):
        return False, "autorisation expirée"
    return True, "ok"
