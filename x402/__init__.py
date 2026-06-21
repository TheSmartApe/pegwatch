"""PegWatch x402 — vend le rapport de l'agent derrière un mur HTTP 402.

Le payeur signe une autorisation EIP-3009 (gasless) ; notre facilitator self-host
submit `transferWithAuthorization` sur Base mainnet et paie le gas. Vrai règlement USDC.
"""
