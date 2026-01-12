# Market Extension Tools API Documentation

## Overview

Market extension tools provide in-depth market data analysis capabilities, including historical prices, technical indicators, ETF flows, exchange reserves, lending markets, stablecoin monitoring, options data, MEV statistics, and Hyperliquid data.

## General Information

- **Base URL**: `http://localhost:8001`
- **All Tool Endpoints**: `POST /tools/{tool_name}`
- **Request Format**: `Content-Type: application/json`
- **Response Format**: JSON

All responses include the following common fields:
- `source_meta`: Data source metadata array
- `warnings`: Warning messages array
- `as_of_utc`: Data timestamp (ISO 8601)

## Tool List

### 1. price_history - Historical Price & Technical Indicators

**Description**: Historical K-line data with technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands, ATR), statistics (volatility, max drawdown, Sharpe ratio), and support/resistance levels

**Endpoint**
```
POST /tools/price_history
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Trading pair symbol, e.g., BTC/USDT, ETH/USDT |
| interval | string | ✗ | 1d | K-line period: 1h=hourly, 4h=4-hour, 1d=daily, 1w=weekly, 1M=monthly |
| lookback_days | integer | ✗ | 365 | Lookback days, default 365 days, max 5 years (1825 days) |
| include_indicators | array[string] | ✗ | ["sma", "rsi", "macd", "bollinger"] | Technical indicators to calculate: sma, ema, rsi, macd, bollinger, atr, all |
| indicator_params | object | ✗ | null | Indicator parameter overrides, e.g., {'sma_periods': [20, 50, 200], 'rsi_period': 14} |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/price_history \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "interval": "1d",
    "lookback_days": 30,
    "include_indicators": ["sma", "rsi"]
  }'
```

**Response Format**
```json
{
  "symbol": "BTC/USDT",
  "interval": "1d",
  "data_points": 30,
  "date_range": {
    "start": "2024-12-11T00:00:00Z",
    "end": "2025-01-10T00:00:00Z"
  },
  "ohlcv": [
    {
      "timestamp": 1702252800000,
      "open": 93000.0,
      "high": 95000.0,
      "low": 92000.0,
      "close": 94500.0,
      "volume": 25000.5
    }
  ],
  "indicators": {
    "sma": {
      "sma_20": [93500.0, 94000.0, 94500.0],
      "sma_50": [92000.0, 92500.0, 93000.0],
      "sma_200": [85000.0, 85500.0, 86000.0]
    },
    "rsi": {
      "rsi_14": [65.5, 68.2, 70.1],
      "current": 70.1
    },
    "macd": {
      "macd_line": [1200.0, 1300.0, 1400.0],
      "signal_line": [1100.0, 1200.0, 1300.0],
      "histogram": [100.0, 100.0, 100.0],
      "current_signal": "bullish"
    },
    "bollinger": {
      "upper": [96000.0, 96500.0, 97000.0],
      "middle": [94000.0, 94500.0, 95000.0],
      "lower": [92000.0, 92500.0, 93000.0],
      "bandwidth": 0.15
    }
  },
  "statistics": {
    "volatility_30d": 0.45,
    "volatility_90d": 0.52,
    "max_drawdown_30d": -0.12,
    "max_drawdown_90d": -0.18,
    "sharpe_ratio_90d": 1.85,
    "current_vs_ath_pct": -5.2,
    "current_vs_atl_pct": 320.5,
    "price_change_7d_pct": 3.5,
    "price_change_30d_pct": 8.2,
    "price_change_90d_pct": 25.6
  },
  "support_resistance": {
    "support_levels": [92000.0, 90000.0, 88000.0],
    "resistance_levels": [96000.0, 98000.0, 100000.0]
  },
  "source_meta": [
    {
      "provider": "binance",
      "endpoint": "/api/v3/klines",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `ohlcv`: K-line data array containing timestamp, open/high/low/close prices, and volume
- `indicators.sma`: Simple Moving Average (20, 50, 200 periods)
- `indicators.ema`: Exponential Moving Average (12, 26 periods)
- `indicators.rsi`: Relative Strength Index (14 periods), current value and historical data
- `indicators.macd`: MACD indicator with MACD line, signal line, histogram, and current signal
- `indicators.bollinger`: Bollinger Bands with upper, middle, lower bands and bandwidth
- `indicators.atr`: Average True Range (14 periods)
- `statistics`: Statistical data including volatility, max drawdown, Sharpe ratio, etc.
- `support_resistance`: Support and resistance levels
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- No special API keys required
- Latency class: medium
- Supported K-line periods: 1h (hourly), 4h (4-hour), 1d (daily), 1w (weekly), 1M (monthly)
- Lookback days range: 7-1825 days

---

### 2. sector_peers - Sector Comparison Analysis

**Description**: Sector/peer comparison analysis: get tokens in the same category with market metrics, TVL, fees, and comparative valuation

**Endpoint**
```
POST /tools/sector_peers
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Target token symbol, e.g., AAVE, UNI |
| limit | integer | ✗ | 10 | Number of peers to return (3-20) |
| sort_by | string | ✗ | market_cap | Sort field: market_cap, tvl, volume_24h, price_change_7d |
| include_metrics | array[string] | ✗ | ["market", "tvl", "fees", "social"] | Comparison metrics to include: market, tvl, fees, social |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/sector_peers \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAVE",
    "limit": 10
  }'
```

**Response Format**
```json
{
  "target_symbol": "AAVE",
  "sector": "DeFi - Lending",
  "sector_description": "Decentralized lending protocols",
  "peers": [
    {
      "rank": 1,
      "symbol": "AAVE",
      "name": "Aave",
      "is_target": true,
      "market_cap": 2500000000.0,
      "market_cap_rank": 45,
      "tvl": 8500000000.0,
      "tvl_rank_in_sector": 1,
      "fees_24h": 850000.0,
      "fees_7d": 6200000.0,
      "price": 165.5,
      "price_change_24h_pct": 3.2,
      "price_change_7d_pct": 8.5,
      "volume_24h": 450000000.0,
      "holders": 125000,
      "twitter_followers": 385000,
      "github_commits_30d": 145
    },
    {
      "rank": 2,
      "symbol": "COMP",
      "name": "Compound",
      "is_target": false,
      "market_cap": 850000000.0,
      "market_cap_rank": 98,
      "tvl": 2200000000.0,
      "tvl_rank_in_sector": 2,
      "fees_24h": 120000.0,
      "fees_7d": 890000.0,
      "price": 52.3,
      "price_change_24h_pct": -1.5,
      "price_change_7d_pct": 2.1,
      "volume_24h": 85000000.0,
      "holders": 45000,
      "twitter_followers": 168000,
      "github_commits_30d": 78
    }
  ],
  "comparison": {
    "valuation_ratios": {
      "avg_mcap_tvl_ratio": 0.35,
      "target_mcap_tvl_ratio": 0.29,
      "target_vs_avg": "undervalued"
    },
    "fee_multiples": {
      "avg_pe_ratio": 420.5,
      "target_pe_ratio": 405.2,
      "target_vs_avg": "fair"
    },
    "market_share": {
      "target_tvl_share": 0.42,
      "target_volume_share": 0.38
    }
  },
  "sector_stats": {
    "total_tvl": 20500000000.0,
    "total_market_cap": 7200000000.0,
    "avg_price_change_7d_pct": 5.2,
    "top_performer_7d": {
      "symbol": "AAVE",
      "price_change_7d_pct": 8.5
    },
    "worst_performer_7d": {
      "symbol": "MKR",
      "price_change_7d_pct": -2.1
    }
  },
  "source_meta": [
    {
      "provider": "coingecko",
      "endpoint": "/coins/markets",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `sector`: Sector name (e.g., "DeFi - Lending")
- `peers`: Peer list including target token and sector projects
  - `is_target`: Indicates if this is the target token
  - `market_cap`: Market capitalization
  - `tvl`: Total Value Locked
  - `fees_24h/7d`: 24-hour/7-day fee income
  - `price_change_*_pct`: Price change percentage
- `comparison`: Comparative analysis
  - `valuation_ratios`: Valuation ratios (Market Cap/TVL, etc.)
  - `fee_multiples`: Fee income multiples (P/E ratio)
  - `market_share`: Market share analysis
- `sector_stats`: Sector statistics
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- No special API keys required
- Latency class: medium
- Number of peers is configurable (3-20)
- Automatically identifies token sector

---

### 3. etf_flows_holdings - ETF Flows & Holdings

**Description**: ETF flows and holdings snapshots (free-first sources like Farside)

**Endpoint**
```
POST /tools/etf_flows_holdings
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| dataset | string | ✗ | bitcoin | Dataset: bitcoin / ethereum |
| url_override | string | ✗ | null | Optional Farside URL override |
| include_fields | array[string] | ✗ | ["flows"] | Return fields: flows, holdings, all |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/etf_flows_holdings \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "bitcoin"
  }'
```

**Response Format**
```json
{
  "dataset": "bitcoin",
  "flows": [
    {
      "data": {
        "date": "2025-01-10",
        "total_net_flow": 325000000.0,
        "etf_flows": {
          "IBIT": 145000000.0,
          "FBTC": 95000000.0,
          "GBTC": -25000000.0,
          "ARKB": 65000000.0,
          "BITB": 45000000.0
        },
        "cumulative_flow": 18500000000.0
      }
    }
  ],
  "holdings": [
    {
      "data": {
        "date": "2025-01-10",
        "total_btc": 875000.5,
        "total_value_usd": 83125000000.0,
        "etf_holdings": {
          "GBTC": 285000.2,
          "IBIT": 215000.8,
          "FBTC": 145000.3,
          "ARKB": 95000.1,
          "BITB": 75000.0
        }
      }
    }
  ],
  "source_meta": [
    {
      "provider": "farside",
      "endpoint": "/btc-etf-flow-all-data",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 3600,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `dataset`: Dataset type (bitcoin or ethereum)
- `flows`: Flow data
  - `total_net_flow`: Total net inflow (USD)
  - `etf_flows`: Individual ETF flows
  - `cumulative_flow`: Cumulative flow
- `holdings`: Holdings data
  - `total_btc/eth`: Total holdings
  - `total_value_usd`: Total holdings value
  - `etf_holdings`: Individual ETF holdings
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Holdings data requires a configured source; flows are best-effort parsing
- Latency class: medium
- Data source: Farside and other public sources

---

### 4. cex_netflow_reserves - CEX Reserves & Netflow

**Description**: CEX reserves from DefiLlama with optional Whale Alert transfers

**Endpoint**
```
POST /tools/cex_netflow_reserves
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| exchange | string | ✗ | null | Exchange name (e.g., binance), returns all exchanges aggregate if empty |
| include_whale_transfers | boolean | ✗ | false | Include Whale Alert large transfers |
| min_transfer_usd | integer | ✗ | 500000 | Minimum transfer amount in USD |
| lookback_hours | integer | ✗ | 24 | Lookback hours for large transfers |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/cex_netflow_reserves \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "binance"
  }'
```

**Response Format**
```json
{
  "exchange": "binance",
  "reserves": {
    "total_reserves_usd": 65000000000.0,
    "token_breakdown": {
      "BTC": {
        "amount": 580000.5,
        "value_usd": 55100000000.0
      },
      "ETH": {
        "amount": 3200000.2,
        "value_usd": 7680000000.0
      },
      "USDT": {
        "amount": 2100000000.0,
        "value_usd": 2100000000.0
      }
    },
    "chain_distribution": {
      "ethereum": 35000000000.0,
      "bitcoin": 55100000000.0,
      "bsc": 2500000000.0
    },
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "whale_transfers": {
    "token_symbol": null,
    "chain": null,
    "time_range_hours": 24,
    "min_value_usd": 500000.0,
    "total_transfers": 156,
    "total_value_usd": 2850000000.0,
    "transfers": [
      {
        "tx_hash": "0xabc123...",
        "timestamp": "2025-01-10T10:30:00Z",
        "from_address": "0x123...",
        "from_label": "Binance",
        "to_address": "0x456...",
        "to_label": "Unknown Wallet",
        "token_symbol": "BTC",
        "amount": 850.5,
        "value_usd": 80750000.0,
        "chain": "bitcoin"
      }
    ],
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/protocols",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 600,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `reserves`: CEX reserve data
  - `total_reserves_usd`: Total reserve value (USD)
  - `token_breakdown`: Token reserve details
  - `chain_distribution`: Chain reserve distribution
- `whale_transfers`: Large transfer data (if requested)
  - `total_transfers`: Total number of transfers
  - `total_value_usd`: Total transfer value
  - `transfers`: Transfer record list
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Whale Alert requires WHALE_ALERT_API_KEY for transfer data
- Latency class: fast
- Supports single exchange query or all exchanges aggregate

---

### 5. lending_liquidation_risk - Lending & Liquidation Risk

**Description**: Lending yield snapshots with optional liquidation data

**Endpoint**
```
POST /tools/lending_liquidation_risk
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| asset | string | ✗ | null | Asset symbol filter (e.g., ETH, USDC) |
| protocols | array[string] | ✗ | null | Protocol filter (e.g., aave) |
| include_liquidations | boolean | ✗ | false | Include liquidation data |
| lookback_hours | integer | ✗ | 24 | Liquidation data lookback hours |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/lending_liquidation_risk \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "ETH"
  }'
```

**Response Format**
```json
{
  "asset": "ETH",
  "yields": [
    {
      "protocol": "aave_v3",
      "chain": "ethereum",
      "asset": "ETH",
      "supply_apy": 0.0285,
      "borrow_apy": 0.0425,
      "utilization_rate": 0.68,
      "total_supply": 2500000.5,
      "total_borrow": 1700000.3,
      "available_liquidity": 800000.2,
      "timestamp": "2025-01-10T12:00:00Z"
    },
    {
      "protocol": "compound_v3",
      "chain": "ethereum",
      "asset": "ETH",
      "supply_apy": 0.0265,
      "borrow_apy": 0.0445,
      "utilization_rate": 0.72,
      "total_supply": 1800000.2,
      "total_borrow": 1296000.1,
      "available_liquidity": 503999.9,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  ],
  "liquidations": {
    "symbol": "ETH",
    "exchange": "coinglass_aggregate",
    "time_range_hours": 24,
    "total_liquidations": 456,
    "total_value_usd": 125000000.0,
    "long_liquidations": 285,
    "long_value_usd": 78000000.0,
    "short_liquidations": 171,
    "short_value_usd": 47000000.0,
    "events": [
      {
        "symbol": "ETH",
        "exchange": "binance",
        "side": "LONG",
        "price": 2350.5,
        "quantity": 850.2,
        "value_usd": 1998220.0,
        "timestamp": 1704888000000
      }
    ]
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/yields",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `yields`: Lending yield data array
  - `supply_apy`: Supply APY
  - `borrow_apy`: Borrow APY
  - `utilization_rate`: Utilization rate
  - `total_supply/borrow`: Total supply/borrow amount
  - `available_liquidity`: Available liquidity
- `liquidations`: Liquidation data (if requested)
  - `total_liquidations`: Total liquidation count
  - `total_value_usd`: Total liquidation value
  - `long/short_*`: Long/short liquidation statistics
  - `events`: Liquidation event list
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Coinglass liquidation data requires COINGLASS_API_KEY
- Latency class: fast
- Supports multi-protocol comparison queries

---

### 6. stablecoin_health - Stablecoin Health

**Description**: Stablecoin supply and chain distribution snapshots

**Endpoint**
```
POST /tools/stablecoin_health
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✗ | null | Stablecoin symbol filter, e.g., USDT |
| chains | array[string] | ✗ | null | Chain filter |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/stablecoin_health \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "USDC"
  }'
```

**Response Format**
```json
{
  "symbol": "USDC",
  "stablecoins": [
    {
      "symbol": "USDC",
      "name": "USD Coin",
      "total_supply": 25000000000.0,
      "market_cap": 25000000000.0,
      "chains": {
        "ethereum": 15000000000.0,
        "arbitrum": 3500000000.0,
        "optimism": 2000000000.0,
        "polygon": 1500000000.0,
        "base": 1200000000.0,
        "avalanche": 800000000.0,
        "solana": 1000000000.0
      },
      "dominance": 0.285,
      "price": 1.0002,
      "price_deviation_pct": 0.02,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  ],
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/stablecoins",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 600,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `stablecoins`: Stablecoin data array
  - `total_supply`: Total supply
  - `market_cap`: Market capitalization
  - `chains`: Chain distribution details
  - `dominance`: Market share (relative to all stablecoins)
  - `price`: Current price
  - `price_deviation_pct`: Deviation from peg (percentage)
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- No special API keys required
- Latency class: fast
- Supports single stablecoin query or all stablecoins aggregate

---

### 7. options_vol_skew - Options Volatility & Skew

**Description**: Options volatility/skew snapshots from Deribit/OKX/Binance

**Endpoint**
```
POST /tools/options_vol_skew
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Underlying symbol, e.g., BTC or ETH |
| expiry | string | ✗ | null | Expiry date or contract ID (optional) |
| providers | array[string] | ✗ | ["deribit", "okx", "binance"] | Data source list: deribit, okx, binance |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/options_vol_skew \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC"
  }'
```

**Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "deribit": {
      "dvol_index": 68.5,
      "atm_iv_30d": 65.2,
      "atm_iv_60d": 62.8,
      "atm_iv_90d": 60.5,
      "skew_25delta": 5.8,
      "put_call_ratio": 1.35,
      "total_oi_usd": 8500000000.0,
      "total_volume_24h_usd": 1200000000.0,
      "iv_rank": 58.5,
      "expiries": [
        {
          "expiry_date": "2025-01-31",
          "atm_iv": 65.2,
          "skew_25delta": 5.8,
          "put_call_ratio": 1.32,
          "total_oi": 2500000000.0
        }
      ],
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "okx": {
      "atm_iv_30d": 66.5,
      "skew_25delta": 6.2,
      "put_call_ratio": 1.28,
      "total_oi_usd": 3200000000.0,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  },
  "source_meta": [
    {
      "provider": "deribit",
      "endpoint": "/get_volatility_index_data",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.<provider>`: Options data from each provider
  - `dvol_index`: Deribit Volatility Index (Deribit only)
  - `atm_iv_*`: ATM implied volatility (30/60/90 days)
  - `skew_25delta`: 25 delta skew
  - `put_call_ratio`: Put/call ratio
  - `total_oi_usd`: Total open interest (USD)
  - `total_volume_24h_usd`: 24-hour trading volume (USD)
  - `iv_rank`: IV percentile
  - `expiries`: Details for each expiry
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Binance options requires a specific option symbol for mark data
- Latency class: medium
- Supports multi-provider comparison

---

### 8. blockspace_mev - Blockspace & MEV

**Description**: Blockspace + MEV-Boost stats with gas oracle data

**Endpoint**
```
POST /tools/blockspace_mev
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✗ | ethereum | Chain name (currently supports ethereum only) |
| limit | integer | ✗ | 100 | MEV-Boost record count |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/blockspace_mev \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum"
  }'
```

**Response Format**
```json
{
  "chain": "ethereum",
  "mev_boost": {
    "total_blocks": 15680,
    "mev_boost_blocks": 14850,
    "mev_boost_rate": 0.947,
    "total_value_eth": 8520.5,
    "total_value_usd": 20450000.0,
    "avg_value_per_block_eth": 0.574,
    "top_builders": [
      {
        "builder": "beaverbuild",
        "blocks": 5200,
        "value_eth": 3150.2,
        "share": 0.35
      },
      {
        "builder": "flashbots",
        "blocks": 4800,
        "value_eth": 2850.1,
        "share": 0.323
      }
    ],
    "top_relays": [
      {
        "relay": "ultra_sound_relay",
        "blocks": 6500,
        "value_eth": 3850.5,
        "share": 0.438
      }
    ],
    "recent_blocks": [
      {
        "block_number": 18950000,
        "value_eth": 0.85,
        "builder": "beaverbuild",
        "relay": "ultra_sound_relay",
        "timestamp": "2025-01-10T11:58:00Z"
      }
    ],
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "gas_oracle": {
    "safe_gas_price": 25,
    "propose_gas_price": 30,
    "fast_gas_price": 35,
    "base_fee": 22,
    "priority_fee_suggestions": {
      "low": 1.5,
      "medium": 2.0,
      "high": 3.0
    },
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "source_meta": [
    {
      "provider": "mevboost.pics",
      "endpoint": "/",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `mev_boost`: MEV-Boost statistics
  - `total_blocks`: Total block count
  - `mev_boost_blocks`: MEV-Boost block count
  - `mev_boost_rate`: MEV-Boost usage rate
  - `total_value_eth/usd`: Total MEV value
  - `top_builders`: Top builder list
  - `top_relays`: Top relay list
  - `recent_blocks`: Recent block list
- `gas_oracle`: Gas price oracle data
  - `safe/propose/fast_gas_price`: Safe/standard/fast gas prices (Gwei)
  - `base_fee`: Base fee
  - `priority_fee_suggestions`: Priority fee suggestions
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Gas oracle requires ETHERSCAN_API_KEY for ethereum
- Latency class: fast
- Currently supports Ethereum mainnet only

---

### 9. hyperliquid_market - Hyperliquid Market Data

**Description**: Hyperliquid market data (funding, OI, orderbook, trades)

**Endpoint**
```
POST /tools/hyperliquid_market
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Underlying symbol, e.g., BTC |
| include_fields | array[string] | ✗ | ["all"] | Return fields: funding, open_interest, orderbook, trades, asset_contexts, all |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/hyperliquid_market \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC"
  }'
```

**Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "funding": {
      "funding_rate": 0.00015,
      "funding_rate_annual": 0.1314,
      "next_funding_time": "2025-01-10T16:00:00Z",
      "mark_price": 95000.0,
      "index_price": 94995.0,
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "open_interest": {
      "open_interest": 2500000000.0,
      "oi_change_24h": 125000000.0,
      "oi_change_percent_24h": 5.26,
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "orderbook": {
      "bids": [
        {"price": 94995.0, "size": 5.25},
        {"price": 94990.0, "size": 8.50}
      ],
      "asks": [
        {"price": 95005.0, "size": 4.75},
        {"price": 95010.0, "size": 7.25}
      ],
      "mid_price": 95000.0,
      "spread_bps": 1.05,
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "trades": [
      {
        "price": 95000.0,
        "size": 2.5,
        "side": "buy",
        "timestamp": 1704888000000
      }
    ],
    "asset_contexts": {
      "mark_price": 95000.0,
      "oracle_price": 94995.0,
      "funding_rate": 0.00015,
      "open_interest": 2500000000.0,
      "volume_24h": 8500000000.0,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  },
  "source_meta": [
    {
      "provider": "hyperliquid",
      "endpoint": "/info",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 60,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.funding`: Funding rate data
  - `funding_rate`: Current rate
  - `funding_rate_annual`: Annualized rate
  - `next_funding_time`: Next settlement time
- `data.open_interest`: Open interest data
  - `open_interest`: Open interest (USD)
  - `oi_change_24h`: 24-hour change
- `data.orderbook`: Orderbook data
  - `bids/asks`: Bid/ask sides
  - `mid_price`: Mid price
  - `spread_bps`: Bid-ask spread (bps)
- `data.trades`: Recent trade records
- `data.asset_contexts`: Asset context information
- `source_meta`: Data source metadata

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- No special API keys required
- Latency class: fast
- Focused on Hyperliquid DEX data

---

## Error Handling

All tools follow a unified error response format:

### 422 Unprocessable Entity
Parameter validation error with detailed validation error messages.

```json
{
  "detail": [
    {
      "loc": ["body", "symbol"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 503 Service Unavailable
Tool not initialized or dependent service unavailable.

```json
{
  "detail": "Tool 'price_history' is not initialized or disabled"
}
```

### 500 Internal Server Error
Internal service error with error message.

```json
{
  "detail": "Internal error: connection timeout"
}
```

## Data Source Metadata

All successful responses include a `source_meta` array providing complete data source traceability:

```json
{
  "provider": "binance",
  "endpoint": "/api/v3/klines",
  "as_of_utc": "2025-01-10T12:00:00Z",
  "ttl_seconds": 300,
  "version": "v3",
  "degraded": false,
  "fallback_used": null,
  "response_time_ms": 156.5
}
```

Field descriptions:
- `provider`: Data provider (e.g., binance, defillama)
- `endpoint`: API endpoint path
- `as_of_utc`: Data retrieval timestamp
- `ttl_seconds`: Cache TTL (seconds)
- `version`: Data contract version
- `degraded`: Whether in degraded mode
- `fallback_used`: Fallback source used (if any)
- `response_time_ms`: Response time (milliseconds)

## Best Practices

1. **Error Handling**: Always check the `warnings` array, even if the request succeeds
2. **Caching Strategy**: Cache data appropriately based on `ttl_seconds` in `source_meta`
3. **Degradation Handling**: Check the `degraded` field; data may be incomplete in degraded mode
4. **Concurrent Requests**: Market tools support concurrent calls, but be mindful of API rate limits
5. **Timestamps**: All timestamps are in UTC ISO 8601 format
6. **Parameter Validation**: Use 422 error responses for client-side validation
7. **API Key Management**: Some tools require third-party API keys, configure them in `docker/.env`
