"""PegWatch — config & chargement .env."""
import os
from pathlib import Path

ROOT = Path(__file__).parent
PROJECT_ROOT = ROOT.parent
DATA_DIR = ROOT / "data"
SNAP_DIR = DATA_DIR / "snapshots"
REPORT_DIR = ROOT / "reports"
for d in (DATA_DIR, SNAP_DIR, REPORT_DIR):
    d.mkdir(exist_ok=True)

# charge .env depuis la racine du projet puis le dossier local (sans écraser l'env existant)
for env_path in (PROJECT_ROOT / ".env", ROOT / ".env"):
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")           # optionnel (cross-check + heures marché)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")             # optionnel (interprétation LLM)
LLM_MODEL = os.environ.get("PEGWATCH_LLM_MODEL", "gpt-4o-mini")

# endpoints (tous vérifiés en live, cœur sans clé)
XSTOCKS_API = "https://api.xstocks.fi/api/v2/public"
DEFILLAMA_COINS = "https://coins.llama.fi"
DEFILLAMA_API = "https://api.llama.fi"
FINNHUB_API = "https://finnhub.io/api/v1"
MANTLE_CHAIN = "mantle"          # préfixe DefiLlama coins
MANTLE_CHAIN_ID = 5000

# protocoles Mantle à suivre pour le contexte liquidité (slugs DefiLlama)
LIQUIDITY_PROTOCOLS = ["fluxion-network", "merchant-moe"]

# seuils (en %)
BREAK_THRESHOLD = 3.0     # |premium| au-dessus = peg cassé / arb potentiel
DRIFT_THRESHOLD = 1.0     # |premium| au-dessus hors-séance = dérive 24-7
MIN_CONFIDENCE = 0.95     # en-dessous = pricing peu liquide, à prendre avec des pincettes
DEEP_CONFIDENCE = 0.98    # au-dessus + peg serré = blue chip

# liste focus : les noms US liquides qu'on met en avant dans le rapport
FOCUS = [
    "TSLAx", "NVDAx", "AAPLx", "GOOGLx", "METAx", "MSFTx", "AMZNx",
    "MSTRx", "SPYx", "QQQx", "SPCXx", "COINx", "HOODx", "CRCLx",
]
