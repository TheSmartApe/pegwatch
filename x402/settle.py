"""PegWatch x402 — facilitator self-host : submit transferWithAuthorization sur Base.

C'est l'étape qui dépense du gas (payé par le wallet `submitter`, pas le payeur).
USDC bouge from -> to via l'autorisation signée hors-chaîne.
"""
import json
import time
from pathlib import Path

from eth_account import Account
from eth_utils import keccak
from eth_abi import encode as abi_encode

from pegwatch.x402 import common

# transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)
_SELECTOR = keccak(text="transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)")[:4]


def _calldata(auth, signature):
    sig = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
    r, s, v = sig[0:32], sig[32:64], sig[64]
    args = abi_encode(
        ["address", "address", "uint256", "uint256", "uint256", "bytes32", "uint8", "bytes32", "bytes32"],
        [auth["from"], auth["to"], int(auth["value"]), int(auth["validAfter"]), int(auth["validBefore"]),
         bytes.fromhex(auth["nonce"][2:]), v, r, s],
    )
    return "0x" + (_SELECTOR + args).hex()


def load_submitter_key():
    """Clé du wallet facilitator (paie le gas) : pegwatch/onchain/treasury.json."""
    p = Path(__file__).parent.parent / "onchain" / "treasury.json"
    if not p.exists():
        raise FileNotFoundError("treasury.json absent — génère le wallet facilitator d'abord.")
    return json.loads(p.read_text(encoding="utf-8"))["private_key"]


def settle(payload, submitter_priv=None, wait=True):
    """Submit l'autorisation EIP-3009 on-chain. -> dict façon SettleResponse x402."""
    submitter_priv = submitter_priv or load_submitter_key()
    auth = payload["payload"]["authorization"]
    data = _calldata(auth, payload["payload"]["signature"])
    acct = Account.from_key(submitter_priv)

    # estimate_gas simule la tx → échoue si la signature/état est invalide (pré-check gratuit)
    gas = int(common.rpc("eth_estimateGas", [{"from": acct.address, "to": common.USDC_BASE, "data": data}]), 16)
    gas_price = int(common.rpc("eth_gasPrice", []), 16)
    nonce = int(common.rpc("eth_getTransactionCount", [acct.address, "pending"]), 16)
    tx = {
        "to": common.USDC_BASE, "value": 0, "data": data,
        "gas": int(gas * 1.3), "gasPrice": gas_price, "nonce": nonce, "chainId": common.CHAIN_ID,
    }
    signed = Account.sign_transaction(tx, submitter_priv)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    raw_hex = "0x" + raw.hex() if isinstance(raw, (bytes, bytearray)) else raw
    txh = common.rpc("eth_sendRawTransaction", [raw_hex])

    receipt = None
    if wait:
        for _ in range(40):
            receipt = common.rpc("eth_getTransactionReceipt", [txh])
            if receipt:
                break
            time.sleep(2)

    status = int(receipt["status"], 16) if receipt else None
    return {
        "success": status == 1 if receipt else None,
        "transaction": txh,
        "network": common.NETWORK,
        "payer": auth["from"],
        "payTo": auth["to"],
        "value_usdc": common.fmt_usdc(auth["value"]),
        "explorer": f"https://basescan.org/tx/{txh}",
        "block": int(receipt["blockNumber"], 16) if receipt else None,
        "gas_submitter": acct.address,
    }
