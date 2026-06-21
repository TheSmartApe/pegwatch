"""PegWatch — minter une identité d'agent ERC-8004 sur Mantle.

Le registre Identity d'ERC-8004 (ERC-721) est live sur Mantle mainnet :
  Identity Registry : 0x8004A169FB4a3325136EB29fA0ceB6D2e539a432  (vérifié sur mantlescan)
Interface (depuis l'EIP-8004) :
  register(string agentURI) returns (uint256 agentId)
  event Registered(uint256 indexed agentId, string agentURI, address indexed owner)

`agentURI` doit pointer vers ta carte d'agent (agent-card.json) hébergée en HTTPS/IPFS.

Transport : JSON-RPC brut via urllib (pas de `requests`/web3, plus robuste).
Signature/encodage : eth_account + eth_abi + eth_utils (inclus avec web3, aucun I/O réseau).

Sécurité : DRY-RUN par défaut (simule via eth_call, ne diffuse RIEN).
`--send` + une clé privée sont requis pour réellement minter.

Usage :
  python -m pegwatch.onchain.mint_identity            # dry-run (sûr)
  python -m pegwatch.onchain.mint_identity --send     # diffuse la tx (coûte un peu de MNT)
.env : MANTLE_PRIVATE_KEY=0x...   AGENT_URI=https://.../agent-card.json   [MANTLE_RPC=...]
"""
import os
import sys
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from pegwatch import config  # charge .env

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from eth_abi import encode as abi_encode, decode as abi_decode
from eth_utils import keccak
from eth_account import Account

IDENTITY_REGISTRY = "0x8004A169FB4a3325136EB29fA0ceB6D2e539a432"
CHAIN_ID = 5000
RPC = os.environ.get("MANTLE_RPC", "https://mantle.publicnode.com")
REGISTERED_SIG = "0x" + keccak(text="Registered(uint256,string,address)").hex()


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = Request(RPC, data=body, headers={"Content-Type": "application/json", "User-Agent": "PegWatch/0.1"})
    with urlopen(req, timeout=25) as r:
        d = json.loads(r.read())
    if d.get("error"):
        raise RuntimeError(d["error"])
    return d["result"]


def _hex_int(h):
    return int(h, 16)


def register_calldata(agent_uri):
    selector = keccak(text="register(string)")[:4]
    return "0x" + (selector + abi_encode(["string"], [agent_uri])).hex()


def main(send=False):
    agent_uri = os.environ.get("AGENT_URI", "")
    if not agent_uri:
        print("⚠️  AGENT_URI non défini. Héberge pegwatch/onchain/agent-card.json et mets son URL dans .env.")
        print("    (dry-run : on continue avec un URI placeholder)")
        agent_uri = "https://example.com/agent-card.json"

    try:
        cid = _hex_int(rpc("eth_chainId", []))
    except Exception as e:
        print(f"⛔ RPC injoignable ({RPC}) : {e}"); sys.exit(1)
    if cid != CHAIN_ID:
        print(f"⛔ mauvais réseau : chain id {cid} (attendu {CHAIN_ID} = Mantle)"); sys.exit(1)
    print(f"Mantle OK | chain {cid} | RPC {RPC}")
    print(f"registry : {IDENTITY_REGISTRY}")
    print(f"agentURI : {agent_uri}")

    data = register_calldata(agent_uri)
    pk = os.environ.get("MANTLE_PRIVATE_KEY")
    if not pk:
        print("\nℹ️  MANTLE_PRIVATE_KEY non défini → simulation depuis un wallet impossible.")
        print("   Le calldata register() est néanmoins valide :")
        print(f"   {data[:74]}…")
        return

    acct = Account.from_key(pk)
    addr = acct.address
    bal = _hex_int(rpc("eth_getBalance", [addr, "latest"]))
    print(f"wallet : {addr}")
    print(f"solde  : {bal/1e18:.6f} MNT")

    # simulation : eth_call register() → agentId qui serait attribué, sans rien diffuser
    try:
        ret = rpc("eth_call", [{"from": addr, "to": IDENTITY_REGISTRY, "data": data}, "latest"])
        if ret and ret != "0x":
            preview_id = abi_decode(["uint256"], bytes.fromhex(ret[2:]))[0]
            print(f"agentId (simulé) : {preview_id}")
    except Exception as e:
        print(f"⚠️  simulation eth_call impossible : {e}")

    try:
        gas = _hex_int(rpc("eth_estimateGas", [{"from": addr, "to": IDENTITY_REGISTRY, "data": data}]))
        gas_price = _hex_int(rpc("eth_gasPrice", []))
        print(f"gas estimé : {gas} @ {gas_price/1e9:.4f} gwei → ~{gas*gas_price/1e18:.6f} MNT")
    except Exception as e:
        print(f"⚠️  estimation gas impossible : {e}")
        gas, gas_price = 300000, _hex_int(rpc("eth_gasPrice", []))

    if not send:
        print("\n✅ DRY-RUN terminé (rien diffusé). Relance avec --send pour minter réellement.")
        return

    if bal == 0:
        print("⛔ solde MNT nul — alimente le wallet avant de minter."); sys.exit(1)

    nonce = _hex_int(rpc("eth_getTransactionCount", [addr, "pending"]))
    tx = {
        "to": IDENTITY_REGISTRY, "value": 0, "data": data,
        "gas": int(gas * 1.2), "gasPrice": gas_price,
        "nonce": nonce, "chainId": CHAIN_ID,
    }
    signed = Account.sign_transaction(tx, pk)
    raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
    h = rpc("eth_sendRawTransaction", ["0x" + raw.hex() if isinstance(raw, (bytes, bytearray)) else raw])
    print(f"tx envoyée : {h} — j'attends la confirmation…")

    rcpt = None
    for _ in range(60):
        rcpt = rpc("eth_getTransactionReceipt", [h])
        if rcpt:
            break
        time.sleep(3)
    if not rcpt:
        print("⚠️  pas de reçu après 3 min — vérifie sur mantlescan."); sys.exit(1)

    agent_id = None
    for log in rcpt.get("logs", []):
        if log.get("address", "").lower() == IDENTITY_REGISTRY.lower() and log["topics"][0].lower() == REGISTERED_SIG:
            agent_id = _hex_int(log["topics"][1])
    status = _hex_int(rcpt["status"])
    print(f"✅ minté ! agentId = {agent_id} | block {_hex_int(rcpt['blockNumber'])} | status {status}")

    out = Path(__file__).parent / "identity.json"
    out.write_text(json.dumps({
        "agentId": agent_id, "owner": addr, "agentURI": agent_uri,
        "registry": IDENTITY_REGISTRY, "tx": h, "chainId": CHAIN_ID,
    }, indent=2), encoding="utf-8")
    print(f"identité sauvegardée → {out}")
    print(f"explorer : https://mantlescan.xyz/tx/{h}")


if __name__ == "__main__":
    main(send="--send" in sys.argv)
