"""PegWatch — un agent qui fact-check les actions tokenisées (xStocks) sur Mantle.

Compare le prix on-chain (DEX) de chaque stock tokenisé à son prix de référence (NAV),
repère les pegs cassés / fenêtres d'arbitrage / dérives 24-7, et écrit un rapport.
"""
__version__ = "0.1.0"
