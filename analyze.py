"""PegWatch — calcul premium/discount, classification, détection d'anomalies."""
from statistics import median

from pegwatch import config


def _tier(premium, confidence):
    """Classe un token : blue_chip (peg serré + liquide) / broken / mid / unknown."""
    if premium is None:
        return "unknown"
    ap = abs(premium)
    if confidence is not None and confidence >= config.DEEP_CONFIDENCE and ap < 0.5:
        return "blue_chip"
    if ap >= config.BREAK_THRESHOLD or (confidence is not None and confidence < config.MIN_CONFIDENCE):
        return "broken"
    return "mid"


def build_row(symbol, meta, nav, oc, session):
    """Construit une ligne d'analyse pour un token."""
    price = (oc or {}).get("price")
    conf = (oc or {}).get("confidence")
    premium = None
    if nav and price:
        premium = (price - nav) / nav * 100.0

    flags = []
    if meta.get("halted"):
        flags.append("trading_halted")
    if conf is not None and conf < config.MIN_CONFIDENCE:
        flags.append("thin_liquidity")
    if premium is not None and abs(premium) >= config.BREAK_THRESHOLD:
        flags.append("peg_break")
    if premium is not None and session != "open" and abs(premium) >= config.DRIFT_THRESHOLD:
        flags.append("off_hours_drift")

    return {
        "symbol": symbol,
        "underlying": meta.get("underlying"),
        "address": meta.get("address"),
        "nav": round(nav, 4) if nav else None,
        "onchain": round(price, 4) if price else None,
        "premium_pct": round(premium, 3) if premium is not None else None,
        "confidence": conf,
        "tier": _tier(premium, conf),
        "flags": flags,
    }


def summarize(rows, session):
    priced = [r for r in rows if r["premium_pct"] is not None]
    abs_prem = [abs(r["premium_pct"]) for r in priced]
    breaks = [r for r in priced if "peg_break" in r["flags"]]
    thin = [r for r in priced if "thin_liquidity" in r["flags"]]
    drift = [r for r in priced if "off_hours_drift" in r["flags"]]
    blue = [r for r in priced if r["tier"] == "blue_chip"]

    top_prem = max(priced, key=lambda r: r["premium_pct"], default=None)
    top_disc = min(priced, key=lambda r: r["premium_pct"], default=None)

    return {
        "session": session,
        "n_total": len(rows),
        "n_priced": len(priced),
        "median_abs_premium": round(median(abs_prem), 3) if abs_prem else None,
        "n_blue_chip": len(blue),
        "n_breaks": len(breaks),
        "n_thin_liquidity": len(thin),
        "n_off_hours_drift": len(drift),
        "biggest_premium": {"symbol": top_prem["symbol"], "premium_pct": top_prem["premium_pct"]} if top_prem else None,
        "biggest_discount": {"symbol": top_disc["symbol"], "premium_pct": top_disc["premium_pct"]} if top_disc else None,
    }
