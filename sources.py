"""PegWatch — sources de données (primaires, cœur sans clé)."""
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from datetime import datetime, timezone, timedelta

from pegwatch import config

# fuseau marché US : zoneinfo si dispo, sinon EDT fixe (UTC-4, valable l'été)
try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    _ET = timezone(timedelta(hours=-4))


def http_get(url, headers=None, retries=3, timeout=30):
    h = {"User-Agent": "PegWatch/0.1 (+research-agent)", "Accept": "application/json"}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            with urlopen(Request(url, headers=h), timeout=timeout) as r:
                return json.loads(r.read())
        except (HTTPError, OSError, ValueError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    return {"_error": str(last)}


# ---------- xStocks (univers + prix de référence/NAV) ----------

def list_mantle_xstocks():
    """Retourne {symbol: {address, name, underlying, halted}} pour tous les xStocks sur Mantle."""
    out = {}
    page = 0
    while page < 8:
        d = http_get(f"{config.XSTOCKS_API}/assets?page={page}")
        nodes = (d or {}).get("nodes") or []
        for a in nodes:
            sym = a.get("symbol")
            addr = None
            for dep in a.get("deployments") or []:
                if (dep.get("network") or "").lower() == "mantle":
                    cand = dep.get("address") or ""
                    if cand.startswith("0x"):
                        addr = cand.lower()
                    break
            if sym and addr:
                out[sym] = {
                    "address": addr,
                    "name": a.get("name"),
                    "underlying": a.get("underlyingSymbol"),
                    "halted": bool(a.get("isTradingHalted")),
                }
        if not (d or {}).get("page", {}).get("hasNextPage"):
            break
        page += 1
    return out


def nav_price(symbol):
    """Prix de référence (sous-jacent réel, source xStocks)."""
    d = http_get(f"{config.XSTOCKS_API}/assets/{symbol}/price-data")
    if not isinstance(d, dict):
        return None
    return d.get("quote") or d.get("price") or (d.get("data") or {}).get("quote")


# ---------- DefiLlama (prix on-chain DEX + liquidité) ----------

def onchain_prices(addresses):
    """Prix DEX on-chain Mantle via DefiLlama coins, par batch. -> {addr_lower: {price, confidence}}."""
    res = {}
    addresses = list(addresses)
    for i in range(0, len(addresses), 40):
        chunk = addresses[i:i + 40]
        ids = ",".join(f"{config.MANTLE_CHAIN}:{a}" for a in chunk)
        d = http_get(f"{config.DEFILLAMA_COINS}/prices/current/{ids}")
        coins = (d or {}).get("coins", {})
        for key, v in coins.items():
            addr = key.split(":", 1)[-1].lower()
            res[addr] = {"price": v.get("price"), "confidence": v.get("confidence")}
        time.sleep(0.2)
    return res


def mantle_chain_tvl():
    d = http_get(f"{config.DEFILLAMA_API}/v2/chains")
    if isinstance(d, list):
        for c in d:
            if c.get("name") == "Mantle":
                return c.get("tvl")
    return None


def protocol_tvls():
    """TVL Mantle des DEX qui hébergent les stocks tokenisés."""
    out = {}
    for slug in config.LIQUIDITY_PROTOCOLS:
        d = http_get(f"{config.DEFILLAMA_API}/protocol/{slug}")
        tvl = None
        if isinstance(d, dict):
            tvl = (d.get("currentChainTvls") or {}).get("Mantle") or d.get("tvl")
        out[slug] = tvl
    return out


# ---------- Finnhub (cross-check prix réel, optionnel) ----------

def real_stock_price(underlying):
    """Prix temps réel du sous-jacent via Finnhub (None si pas de clé / indispo)."""
    if not config.FINNHUB_API_KEY or not underlying:
        return None
    q = urlencode({"symbol": underlying, "token": config.FINNHUB_API_KEY})
    d = http_get(f"{config.FINNHUB_API}/quote?{q}")
    if isinstance(d, dict):
        c = d.get("c")
        if c:
            return c
    return None


# ---------- horloge marché US ----------

def us_market_session(now_utc=None):
    """'open' | 'closed' | 'weekend' — séance régulière NYSE 9h30-16h ET (hors jours fériés)."""
    now_utc = now_utc or datetime.now(timezone.utc)
    et = now_utc.astimezone(_ET)
    if et.weekday() >= 5:
        return "weekend"
    minutes = et.hour * 60 + et.minute
    return "open" if (9 * 60 + 30) <= minutes < (16 * 60) else "closed"
