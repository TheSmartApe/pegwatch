"""PegWatch — orchestrateur de l'agent.

Usage:
  python -m pegwatch.agent              # focus (14 noms liquides), rapide
  python -m pegwatch.agent --full       # scan complet (~157 tokens Mantle)
  python -m pegwatch.agent --brain      # + interprétation LLM (OpenAI)

Sorties:
  pegwatch/data/snapshots/<ts>.json     # snapshot brut (pour le dataset 24-7)
  pegwatch/reports/<ts>.md              # rapport lisible
  pegwatch/reports/latest.md            # dernier rapport
  + draft de post X imprimé en console
"""
import os
import sys
import json
import time
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pegwatch import config, sources, analyze, report, brain


def run(full=False, use_llm=False, ref="nav"):
    t0 = time.time()
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    session = sources.us_market_session(now)
    print(f"[pegwatch] {ts} | séance US: {session} | mode: {'full' if full else 'focus'} | ref: {ref}")

    print("[1/5] univers xStocks sur Mantle…")
    uni_file = config.DATA_DIR / "universe.json"
    # mode cloud (ref=finnhub) : on lit la liste versionnée pour éviter l'endpoint xStocks
    # (joignable mais lent depuis une IP datacenter) ; sinon on rafraîchit depuis l'API.
    if ref == "finnhub" and uni_file.exists():
        universe = json.loads(uni_file.read_text(encoding="utf-8"))
        print(f"       {len(universe)} tokens (depuis universe.json — pas d'appel xStocks)")
    else:
        universe = sources.list_mantle_xstocks()
        print(f"       {len(universe)} tokens trouvés sur Mantle")
        uni_file.write_text(json.dumps(universe, indent=2, ensure_ascii=False), encoding="utf-8")

    symbols = list(universe) if full else [s for s in config.FOCUS if s in universe]
    print(f"       analyse de {len(symbols)} tokens")

    print("[2/5] prix on-chain (DefiLlama)…")
    addr_by_sym = {s: universe[s]["address"] for s in symbols}
    oc = sources.onchain_prices(addr_by_sym.values())

    ref_label = "prix réel (Finnhub)" if ref == "finnhub" else "NAV xStocks"
    print(f"[3/5] prix de référence ({ref_label})…")
    rows = []
    for i, s in enumerate(symbols, 1):
        meta = universe[s]
        if ref == "finnhub":
            reference = sources.real_stock_price(meta.get("underlying"))
        else:
            reference = sources.nav_price(s)
        row = analyze.build_row(s, meta, reference, oc.get(addr_by_sym[s]), session)
        rows.append(row)
        if i % 25 == 0:
            print(f"       {i}/{len(symbols)}")
        time.sleep(0.25)

    print("[4/5] contexte liquidité…")
    liquidity = {
        "mantle_tvl": sources.mantle_chain_tvl(),
        "protocols": sources.protocol_tvls(),
    }

    summary = analyze.summarize(rows, session)

    snap = {
        "timestamp": ts,
        "session": session,
        "mode": "full" if full else "focus",
        "ref_source": ref,
        "summary": summary,
        "liquidity": liquidity,
        "rows": rows,
    }

    print("[5/5] interprétation…")
    snap["interpretation"] = brain.interpret(snap, use_llm=use_llm)

    # sauvegardes
    (config.SNAP_DIR / f"{ts}.json").write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
    md = report.render_markdown(snap)
    (config.REPORT_DIR / f"{ts}.md").write_text(md, encoding="utf-8")
    (config.REPORT_DIR / "latest.md").write_text(md, encoding="utf-8")

    # console
    print("\n" + "=" * 72)
    print(md)
    print("\n## Interprétation\n")
    print(snap["interpretation"])
    print("\n" + "=" * 72)
    print("## Draft post X\n")
    print(report.render_x_draft(snap))
    print("=" * 72)
    print(f"\n[ok] snapshot: data/snapshots/{ts}.json | rapport: reports/{ts}.md | {time.time()-t0:.1f}s")
    return snap


if __name__ == "__main__":
    ref = "finnhub" if ("--ref-finnhub" in sys.argv or os.environ.get("PEGWATCH_REF") == "finnhub") else "nav"
    run(full="--full" in sys.argv, use_llm="--brain" in sys.argv, ref=ref)
