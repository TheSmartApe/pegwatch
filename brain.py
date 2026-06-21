"""PegWatch — couche d'interprétation LLM (opt-in via --brain).

Sans clé OpenAI ou sans --brain : on retombe sur une interprétation heuristique
(pas d'appel réseau), pour que l'agent tourne toujours.
"""
import json
from urllib.request import Request, urlopen

from pegwatch import config


def _heuristic(snap):
    s = snap["summary"]
    bits = []
    if s["n_blue_chip"]:
        bits.append(f"{s['n_blue_chip']} blue chips tiennent un peg serré (liquidité profonde).")
    if s["n_breaks"]:
        bits.append(f"{s['n_breaks']} tokens cassent leur peg (>3%) — typiquement des noms peu liquides "
                    f"où un seul ordre déplace le prix.")
    if s["n_off_hours_drift"] and s["session"] != "open":
        bits.append("hors séance US, les tokens dérivent sur le sentiment plutôt que sur le sous-jacent.")
    bd, bp = s.get("biggest_discount"), s.get("biggest_premium")
    if bd:
        bits.append(f"plus gros discount: {bd['symbol']} ({bd['premium_pct']:+.2f}%) — fenêtre d'arbitrage potentielle, "
                    f"à confirmer avec le volume avant de conclure.")
    if bp:
        bits.append(f"plus gros premium: {bp['symbol']} ({bp['premium_pct']:+.2f}%).")
    return " ".join(bits)


def interpret(snap, use_llm=False):
    if not use_llm or not config.OPENAI_API_KEY:
        return _heuristic(snap)

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": (
                "Tu es un analyste onchain sobre et précis. On te donne un snapshot d'écarts de prix "
                "(premium/discount) entre des actions tokenisées sur Mantle et leur prix de référence. "
                "Écris 4-6 phrases d'interprétation: ce qui est notable, pourquoi (liquidité, séance, sentiment), "
                "et la fenêtre d'arbitrage la plus crédible. Pas de hype, pas de conseil financier, chiffres à l'appui."
            )},
            {"role": "user", "content": json.dumps({"summary": snap["summary"], "rows": snap["rows"]}, ensure_ascii=False)},
        ],
        "temperature": 0.4,
    }
    try:
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return _heuristic(snap) + f"\n\n(LLM indisponible: {e})"
