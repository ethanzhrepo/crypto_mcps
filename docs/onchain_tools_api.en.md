# Onchain Analysis Tools API Documentation

## Overview

Onchain analysis tools provide deep blockchain-level data analysis, including protocol TVL, cross-chain bridge volumes, DEX liquidity, governance proposals, whale transfers, token unlocks, activity metrics, contract risk analysis, and CryptoQuant onchain analytics.

## General Information

- **Base URL**: `http://localhost:8001`
- **All Tool Endpoints**: `POST /tools/{tool_name}`
- **Request Format**: `Content-Type: application/json`
- **Response Format**: JSON

All responses include the following common fields:
- `source_meta`: Array of data source metadata
- `warnings`: Array of warning messages
- `as_of_utc`: Data timestamp (ISO 8601)

## Tools List

### 1. onchain_tvl_fees - Protocol TVL and Fees

**Description**: Query DeFi protocol TVL (Total Value Locked) and fee/revenue data from DefiLlama

**Endpoint**
```
POST /tools/onchain_tvl_fees
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| protocol | string | ✓ | - | Protocol name, e.g., uniswap, aave, compound |
| chain | string | ✗ | null | Optional chain label, e.g., ethereum, arbitrum |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_tvl_fees \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "uniswap"
  }'
```

**Response Format**
```json
{
  "protocol": "uniswap",
  "data": {
    "tvl": {
      "total_usd": 5200000000.0,
      "change_24h": 2.5,
      "chain_breakdown": {
        "ethereum": 3800000000.0,
        "arbitrum": 800000000.0,
        "optimism": 600000000.0
      }
    },
    "fees": {
      "fees_24h": 3500000.0,
      "revenue_24h": 1050000.0,
      "fees_7d": 25000000.0
    }
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/tvl/uniswap",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.tvl.total_usd`: Total value locked (USD)
- `data.tvl.change_24h`: 24-hour percentage change
- `data.tvl.chain_breakdown`: TVL distribution across chains
- `data.fees.fees_24h`: 24-hour protocol fees
- `data.fees.revenue_24h`: 24-hour protocol revenue

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Data from DefiLlama, no API key required
- Latency class: fast

---

### 2. onchain_stablecoins_cex - Stablecoins and CEX Reserves

**Description**: Query stablecoin metrics and centralized exchange reserve data from DefiLlama

**Endpoint**
```
POST /tools/onchain_stablecoins_cex
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| stablecoin | string | ✗ | null | Stablecoin symbol, e.g., USDT, USDC; omit for aggregate data |
| exchange | string | ✗ | null | CEX name, e.g., binance, coinbase; omit for all exchanges |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_stablecoins_cex \
  -H "Content-Type: application/json" \
  -d '{
    "stablecoin": "USDT"
  }'
```

**Response Format**
```json
{
  "data": {
    "stablecoin": {
      "symbol": "USDT",
      "total_supply": 95000000000.0,
      "market_cap": 95000000000.0,
      "chain_distribution": {
        "ethereum": 48000000000.0,
        "tron": 42000000000.0,
        "bsc": 3000000000.0
      }
    },
    "cex_reserves": {
      "total_usd": 65000000000.0,
      "exchanges": {
        "binance": 25000000000.0,
        "coinbase": 15000000000.0,
        "kraken": 8000000000.0
      }
    }
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/stablecoins/USDT",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.stablecoin.total_supply`: Total stablecoin supply
- `data.stablecoin.chain_distribution`: Distribution across chains
- `data.cex_reserves.total_usd`: Total CEX reserves (USD)
- `data.cex_reserves.exchanges`: Reserve distribution by exchange

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Data from DefiLlama, no API key required
- Latency class: fast

---

### 3. onchain_bridge_volumes - Cross-Chain Bridge Volumes

**Description**: Query cross-chain bridge volume data (24h/7d/30d) from DefiLlama

**Endpoint**
```
POST /tools/onchain_bridge_volumes
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✗ | null | Chain name, e.g., arbitrum, optimism |
| bridge | string | ✗ | null | Bridge name, e.g., stargate, hop; omit for aggregate data |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_bridge_volumes \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "arbitrum"
  }'
```

**Response Format**
```json
{
  "chain": "arbitrum",
  "data": {
    "volume_24h": 125000000.0,
    "volume_7d": 850000000.0,
    "volume_30d": 3200000000.0,
    "bridges": {
      "native": {
        "volume_24h": 80000000.0,
        "volume_7d": 550000000.0
      },
      "stargate": {
        "volume_24h": 25000000.0,
        "volume_7d": 180000000.0
      },
      "across": {
        "volume_24h": 20000000.0,
        "volume_7d": 120000000.0
      }
    }
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/bridges/arbitrum",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.volume_24h`: Total 24-hour bridge volume
- `data.volume_7d`: Total 7-day bridge volume
- `data.volume_30d`: Total 30-day bridge volume
- `data.bridges`: Volume breakdown by bridge

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Data from DefiLlama, no API key required
- Latency class: fast

---

### 4. onchain_dex_liquidity - DEX Liquidity

**Description**: Query Uniswap v3 DEX liquidity, pool information, and optional tick distribution from The Graph

**Endpoint**
```
POST /tools/onchain_dex_liquidity
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✓ | - | Chain name, e.g., ethereum, arbitrum, optimism, polygon |
| token_address | string | ✗ | null | Token address to list related pools |
| pool_address | string | ✗ | null | Uniswap v3 pool address for single pool details |
| include_ticks | boolean | ✗ | false | Include tick-level liquidity distribution (only when pool_address is specified) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_dex_liquidity \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum"
  }'
```

**Response Format**
```json
{
  "chain": "ethereum",
  "data": {
    "total_liquidity_usd": 4500000000.0,
    "pools": [
      {
        "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "token0": "USDC",
        "token1": "WETH",
        "fee_tier": "0.05%",
        "liquidity_usd": 320000000.0,
        "volume_24h": 185000000.0,
        "fee_revenue_24h": 92500.0
      }
    ]
  },
  "source_meta": [
    {
      "provider": "thegraph",
      "endpoint": "/subgraphs/uniswap-v3-ethereum",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.total_liquidity_usd`: Total liquidity (USD)
- `data.pools`: Pool list with address, token pair, fee tier, liquidity, volume
- `data.pools[].liquidity_usd`: Single pool liquidity
- `data.pools[].volume_24h`: Single pool 24-hour volume

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Supports querying Uniswap v3 pools via public subgraphs
- Latency class: medium

---

### 5. onchain_governance - Governance Proposals

**Description**: Query DAO governance proposals from Snapshot (off-chain) and Tally (on-chain)

**Endpoint**
```
POST /tools/onchain_governance
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✗ | ethereum | Chain name for deriving Tally chain_id |
| snapshot_space | string | ✗ | null | Snapshot space ID, e.g., aave.eth, uniswap.eth |
| governor_address | string | ✗ | null | On-chain governance contract address (for Tally) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_governance \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_space": "aave.eth"
  }'
```

**Response Format**
```json
{
  "data": {
    "snapshot_proposals": [
      {
        "id": "0x123abc...",
        "title": "AIP-42: Enable USDC as collateral",
        "state": "active",
        "start": "2025-01-05T00:00:00Z",
        "end": "2025-01-12T00:00:00Z",
        "scores": [850000, 320000],
        "choices": ["For", "Against"]
      }
    ],
    "tally_proposals": []
  },
  "source_meta": [
    {
      "provider": "snapshot",
      "endpoint": "/graphql",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 600,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.snapshot_proposals`: Snapshot off-chain proposal list
- `data.tally_proposals`: Tally on-chain proposal list
- `proposals[].state`: Proposal state (active, closed, pending, etc.)
- `proposals[].scores`: Vote counts per choice

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Some DAOs may require TALLY_API_KEY for Tally on-chain data
- Latency class: medium

---

### 6. onchain_whale_transfers - Whale Transfer Monitoring

**Description**: Monitor large on-chain transfers using Whale Alert API

**Endpoint**
```
POST /tools/onchain_whale_transfers
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✗ | null | Token symbol, e.g., BTC, ETH; omit for multi-asset view |
| min_value_usd | number | ✗ | 500000 | Minimum transfer value (USD) |
| lookback_hours | integer | ✗ | 24 | Lookback time window (hours) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_whale_transfers \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "min_value_usd": 1000000
  }'
```

**Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "transfers": [
      {
        "hash": "0xabc123...",
        "from": {
          "address": "binance",
          "owner_type": "exchange"
        },
        "to": {
          "address": "unknown",
          "owner_type": "unknown"
        },
        "amount": 1250.5,
        "amount_usd": 118797500.0,
        "timestamp": "2025-01-10T10:30:00Z"
      }
    ],
    "total_count": 15,
    "total_value_usd": 850000000.0
  },
  "source_meta": [
    {
      "provider": "whale_alert",
      "endpoint": "/transactions",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.transfers`: Transfer list
- `data.transfers[].from.owner_type`: Sender type (exchange, unknown, etc.)
- `data.transfers[].amount_usd`: Transfer amount (USD)
- `data.total_count`: Total transfer count
- `data.total_value_usd`: Total transfer value

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Recommend configuring WHALE_ALERT_API_KEY for full coverage
- Latency class: fast

---

### 7. onchain_token_unlocks - Token Unlock Schedule

**Description**: Query token vesting and unlock schedules from Token Unlocks

**Endpoint**
```
POST /tools/onchain_token_unlocks
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✗ | null | Token symbol; omit for popular projects unlock info |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_token_unlocks \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ARB"
  }'
```

**Response Format**
```json
{
  "symbol": "ARB",
  "data": {
    "next_unlock": {
      "date": "2025-02-15",
      "amount": 92500000.0,
      "amount_usd": 185000000.0,
      "percent_of_supply": 0.925
    },
    "upcoming_unlocks": [
      {
        "date": "2025-02-15",
        "amount": 92500000.0,
        "category": "team"
      },
      {
        "date": "2025-03-15",
        "amount": 75000000.0,
        "category": "investors"
      }
    ],
    "total_locked": 3800000000.0,
    "percent_locked": 38.0
  },
  "source_meta": [
    {
      "provider": "token_unlocks",
      "endpoint": "/unlocks/ARB",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 3600,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.next_unlock`: Next unlock information
- `data.next_unlock.amount`: Unlock amount
- `data.next_unlock.percent_of_supply`: Percentage of total supply
- `data.upcoming_unlocks`: Upcoming unlock list
- `data.total_locked`: Current total locked amount

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Some endpoints may require TOKEN_UNLOCKS_API_KEY
- Latency class: fast

---

### 8. onchain_activity - On-Chain Activity

**Description**: Query chain-level activity metrics (active addresses, transactions, gas usage) from Etherscan

**Endpoint**
```
POST /tools/onchain_activity
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✓ | - | Chain name, e.g., ethereum, arbitrum, optimism, polygon |
| window | string | ✗ | 7d | Time window, e.g., 1d, 7d, 30d |
| protocol | string | ✗ | null | Optional protocol tag for labeling only |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_activity \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum",
    "window": "7d"
  }'
```

**Response Format**
```json
{
  "chain": "ethereum",
  "window": "7d",
  "data": {
    "active_addresses": {
      "total": 850000,
      "daily_average": 121428,
      "change_7d": 5.2
    },
    "transactions": {
      "total": 8500000,
      "daily_average": 1214285,
      "change_7d": 3.8
    },
    "gas_usage": {
      "total_gwei": 125000000000,
      "average_gwei_per_tx": 14705882
    }
  },
  "source_meta": [
    {
      "provider": "etherscan",
      "endpoint": "/stats/ethereum",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 1800,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.active_addresses.total`: Total active addresses in time window
- `data.active_addresses.daily_average`: Daily average active addresses
- `data.transactions.total`: Total transactions in time window
- `data.gas_usage.total_gwei`: Total gas consumption

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- ETHERSCAN_API_KEY required for Ethereum mainnet queries
- Latency class: medium

---

### 9. onchain_contract_risk - Contract Risk Analysis

**Description**: Smart contract risk analysis via GoPlus or Slither

**Endpoint**
```
POST /tools/onchain_contract_risk
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| address | string | ✓ | - | Contract address to analyze |
| chain | string | ✓ | - | Chain name, e.g., ethereum, arbitrum, optimism, polygon |
| provider | string | ✗ | goplus | Analysis provider: goplus or slither |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_contract_risk \
  -H "Content-Type: application/json" \
  -d '{
    "address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "chain": "ethereum"
  }'
```

**Response Format**
```json
{
  "address": "0x6b175474e89094c44da98b954eedeac495271d0f",
  "chain": "ethereum",
  "data": {
    "risk_score": 15,
    "risk_level": "low",
    "findings": [
      {
        "severity": "low",
        "category": "centralization",
        "description": "Contract has owner privileges"
      }
    ],
    "checks": {
      "is_open_source": true,
      "is_proxy": false,
      "has_honeypot": false,
      "can_take_back_ownership": false,
      "owner_can_change_balance": false
    }
  },
  "source_meta": [
    {
      "provider": "goplus",
      "endpoint": "/token_security",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 3600,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.risk_score`: Risk score (0-100)
- `data.risk_level`: Risk level (low, medium, high)
- `data.findings`: Risk findings list
- `data.checks`: Security check items

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- GOPLUS_API_KEY and GOPLUS_API_SECRET required when using GoPlus
- Latency class: slow

---

### 10. onchain_analytics - CryptoQuant On-Chain Analytics

**Description**: On-chain analytics tool powered by CryptoQuant: MVRV ratio, SOPR, active addresses, exchange flows (reserves/netflow/inflow/outflow), miner data (BTC only), and derivatives funding rates

**Endpoint**
```
POST /tools/onchain_analytics
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✗ | BTC | Asset symbol (BTC, ETH) |
| include_fields | array[string] | ✗ | ["all"] | Fields to include: mvrv, sopr, active_addresses, exchange_reserve, exchange_netflow, exchange_inflow, exchange_outflow, miner (BTC only), funding_rate, all |
| window | string | ✗ | day | Time window: hour or day |
| limit | integer | ✗ | 30 | Number of data points (1-365) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_analytics \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "include_fields": ["mvrv", "sopr", "exchange_netflow"],
    "window": "day",
    "limit": 30
  }'
```

**Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "mvrv": {
      "current": 2.15,
      "signal": "neutral",
      "history": [
        {"date": "2025-01-10", "value": 2.15},
        {"date": "2025-01-09", "value": 2.12}
      ]
    },
    "sopr": {
      "current": 1.05,
      "signal": "slight_profit",
      "history": [
        {"date": "2025-01-10", "value": 1.05},
        {"date": "2025-01-09", "value": 1.03}
      ]
    },
    "exchange_netflow": {
      "current": -25000000.0,
      "signal": "bullish",
      "history": [
        {"date": "2025-01-10", "value": -25000000.0},
        {"date": "2025-01-09", "value": -18000000.0}
      ]
    }
  },
  "source_meta": [
    {
      "provider": "cryptoquant",
      "endpoint": "/v1/btc/market-data/mvrv",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 3600,
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `data.mvrv`: MVRV ratio (Market Value / Realized Value)
  - > 3.7: Overvalued
  - < 1.0: Undervalued
- `data.sopr`: SOPR (Spent Output Profit Ratio)
  - > 1.0: On-chain profits
  - < 1.0: On-chain losses
- `data.exchange_netflow`: Exchange net flow
  - Positive: Inflow (bearish signal)
  - Negative: Outflow (bullish signal)
- `data.miner`: Miner data (BTC only)
  - `reserve`: Miner reserves
  - `outflow`: Miner outflows
- `data.funding_rate`: Perpetual contract funding rate

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized (CRYPTOQUANT_API_KEY not configured)
- 500: Internal server error

**Notes**
- **Required**: CRYPTOQUANT_API_KEY
- Miner data only available for BTC
- Latency class: medium
- Data freshness: 1-hour cache

---

## Unified Error Handling

All tools follow a unified error response format:

### Parameter Validation Error (422)
```json
{
  "detail": [
    {
      "loc": ["body", "protocol"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Tool Not Initialized (503)
```json
{
  "detail": "Tool not initialized"
}
```

### Internal Server Error (500)
```json
{
  "detail": "Internal server error",
  "error": "Error message details"
}
```

## Data Source Metadata

The `source_meta` field in all responses provides data provenance:

```json
{
  "provider": "defillama",
  "endpoint": "/tvl/uniswap",
  "as_of_utc": "2025-01-10T12:00:00Z",
  "ttl_seconds": 300,
  "version": "v1",
  "degraded": false
}
```

- `provider`: Data provider
- `endpoint`: API endpoint
- `as_of_utc`: Data timestamp
- `ttl_seconds`: Cache TTL
- `degraded`: Whether in degraded mode

## Best Practices

1. **API Key Configuration**: Ensure required API keys are configured in `docker/.env`
2. **Error Handling**: Always check `warnings` field and HTTP status codes
3. **Data Freshness**: Refer to `source_meta[].ttl_seconds` for caching strategy
4. **Rate Limiting**: Be mindful of rate limits from various data sources
5. **Chain Parameters**: Use standardized chain names (ethereum, arbitrum, optimism, polygon)
