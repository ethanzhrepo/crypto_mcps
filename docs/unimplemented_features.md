# Unimplemented Features

This file tracks parameters or response fields that are not implemented in code,
but were previously documented or requested.

## Core Tools
- `macro_hub`: `include_fields` filter is not supported; use `mode` only.
- `crypto_overview`: `vs_currency` is accepted but currently ignored (always USD).

## Market Tools
- `stablecoin_health`: no `price` or `price_deviation_pct` fields are returned.
- `options_vol_skew`: normalized fields (`atm_iv_*`, `skew_25delta`,
  `put_call_ratio`, `iv_rank`, `expiries`) are not produced; only DVOL summary is derived.
- `hyperliquid_market`: normalized funding/open interest/orderbook fields are not provided;
  raw provider payloads only.
- `etf_flows_holdings`: holdings source is not configured; `holdings` remains empty.

## Onchain Tools
- `onchain_stablecoins_cex`: no `stablecoin` filter parameter.
- `onchain_bridge_volumes`: no `chain` filter parameter.
- `onchain_token_unlocks`: no `next_unlock`/`percent_locked` summary block in response.
- `onchain_activity`: no `window` parameter; metrics are fixed to 24h/7d from Etherscan.
