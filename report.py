"""PegWatch — rendu du rapport (markdown lisible + draft X dans la voix du compte)."""


def _fmt_pct(p):
    if p is None:
        return "—"
    return f"{p:+.2f}%"


def _fmt_usd(n):
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n/1_000:.1f}k"
    return f"${n:,.0f}"


def render_markdown(snap):
    s = snap["summary"]
    liq = snap["liquidity"]
    rows = sorted(
        [r for r in snap["rows"] if r["premium_pct"] is not None],
        key=lambda r: abs(r["premium_pct"]), reverse=True,
    )
    L = []
    L.append(f"# PegWatch — {snap['timestamp']}")
    L.append("")
    L.append(f"**Séance US :** {s['session']}  |  **tokens chiffrés :** {s['n_priced']}/{s['n_total']}  "
             f"|  **écart médian :** {s['median_abs_premium']}%")
    L.append(f"**Blue chips (peg serré) :** {s['n_blue_chip']}  |  "
             f"**pegs cassés (>3%) :** {s['n_breaks']}  |  "
             f"**pricing peu liquide :** {s['n_thin_liquidity']}  |  "
             f"**dérive hors-séance :** {s['n_off_hours_drift']}")
    if s["biggest_premium"] and s["biggest_discount"]:
        bp, bd = s["biggest_premium"], s["biggest_discount"]
        L.append(f"**Plus gros premium :** {bp['symbol']} {_fmt_pct(bp['premium_pct'])}  |  "
                 f"**plus gros discount :** {bd['symbol']} {_fmt_pct(bd['premium_pct'])}")
    L.append("")
    L.append("## Premium / discount (on-chain DEX vs prix de référence)")
    L.append("")
    L.append("| token | sous-jacent | NAV | on-chain | écart | conf | tier | flags |")
    L.append("|---|---|---:|---:|---:|---:|---|---|")
    for r in rows:
        L.append(f"| {r['symbol']} | {r['underlying'] or '—'} | {r['nav']} | {r['onchain']} | "
                 f"{_fmt_pct(r['premium_pct'])} | {r['confidence']} | {r['tier']} | "
                 f"{', '.join(r['flags']) or '—'} |")
    L.append("")
    L.append("## Contexte liquidité (DefiLlama, live)")
    L.append("")
    L.append(f"- Mantle chain TVL : {_fmt_usd(liq.get('mantle_tvl'))}")
    for slug, tvl in (liq.get("protocols") or {}).items():
        L.append(f"- {slug} : {_fmt_usd(tvl)}")
    return "\n".join(L)


def render_x_draft(snap):
    """Draft de post X dans la voix du compte (lowercase, hook fort, contrarian)."""
    s = snap["summary"]
    rows = [r for r in snap["rows"] if r["premium_pct"] is not None]
    broken = [r for r in rows if "peg_break" in r["flags"] or "thin_liquidity" in r["flags"]]
    bd = s.get("biggest_discount") or {}
    bp = s.get("biggest_premium") or {}

    lines = []
    lines.append("mantle liste 157 actions tokenisées. j'ai build un agent pour vérifier si elles suivent vraiment leur prix réel.")
    lines.append("")
    lines.append(f"résultat: deux marchés sous le même label. {s['n_blue_chip']} blue chips collent au prix à ±0.5%. le reste dérape.")
    lines.append("")
    if bd:
        lines.append(f"exemple du jour: {bd['symbol']} se traite à {_fmt_pct(bd.get('premium_pct'))} de son prix réel on-chain.")
    if bp and bp.get("symbol") != bd.get("symbol"):
        lines.append(f"à l'inverse {bp['symbol']}: {_fmt_pct(bp.get('premium_pct'))}.")
    lines.append("")
    lines.append(f"{s['n_breaks']} pegs cassés (>3%), {s['n_thin_liquidity']} en pricing peu liquide. la 'distribution layer' marche — pour une poignée de noms.")
    lines.append("")
    lines.append("thread sur comment l'agent est build + ce qu'il révèle 👇")
    return "\n".join(lines)
