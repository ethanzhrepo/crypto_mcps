# Onchain Analysis Tools API Documentation

## Overview

Onchain analysis tools provide deep blockchain-level data analysis, including protocol TVL, cross-chain bridge volumes, DEX liquidity, governance proposals, token unlocks, activity metrics, contract risk analysis, and CryptoQuant onchain analytics.

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
  "chain": null,
  "tvl": {
    "protocol": "uniswap",
    "tvl_usd": 5200000000.0,
    "tvl_change_24h": 2.5,
    "tvl_change_7d": 6.8,
    "chain_breakdown": {
      "ethereum": 3800000000.0,
      "arbitrum": 800000000.0,
      "optimism": 600000000.0
    },
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "protocol_fees": {
    "protocol": "uniswap",
    "fees_24h": 3500000.0,
    "revenue_24h": 1050000.0,
    "fees_7d": 25000000.0,
    "revenue_7d": 7500000.0,
    "fees_30d": 98000000.0,
    "revenue_30d": 29500000.0,
    "timestamp": "2025-01-10T12:00:00Z"
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
- `tvl.tvl_usd`: Total value locked (USD)
- `tvl.tvl_change_24h`: 24-hour percentage change
- `tvl.tvl_change_7d`: 7-day percentage change
- `tvl.chain_breakdown`: TVL distribution across chains
- `protocol_fees.fees_24h`: 24-hour protocol fees
- `protocol_fees.revenue_24h`: 24-hour protocol revenue

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
| exchange | string | ✗ | null | CEX name, e.g., binance, coinbase; omit for all exchanges |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_stablecoins_cex \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "binance"
  }'
```

**Response Format**
```json
{
  "stablecoin_metrics": [
    {
      "stablecoin": "USDT",
      "total_supply": 95000000000.0,
      "market_cap": 95000000000.0,
      "chains": {
        "ethereum": 48000000000.0,
        "tron": 42000000000.0,
        "bsc": 3000000000.0
      },
      "dominance": 0.62,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  ],
  "cex_reserves": {
    "exchange": "binance",
    "total_reserves_usd": 65000000000.0,
    "token_breakdown": {},
    "chain_distribution": {},
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/stablecoins",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 300,
      "degraded": false
    },
    {
      "provider": "defillama",
      "endpoint": "/protocol/binance",
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
- `stablecoin_metrics`: Stablecoin metrics list (DefiLlama stablecoins)
- `cex_reserves`: CEX reserves summary (DefiLlama)

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
| bridge | string | ✗ | null | Bridge name, e.g., stargate, hop; omit for aggregate data |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_bridge_volumes \
  -H "Content-Type: application/json" \
  -d '{
    "bridge": "stargate"
  }'
```

**Response Format**
```json
{
  "bridge_volumes": {
    "bridge": "stargate",
    "volume_24h": 125000000.0,
    "volume_7d": 850000000.0,
    "volume_30d": 3200000000.0,
    "chains": ["ethereum", "arbitrum", "optimism"],
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "source_meta": [
    {
      "provider": "defillama",
      "endpoint": "/bridge/stargate",
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
- `bridge_volumes.bridge`: Bridge name (if queried)
- `bridge_volumes.volume_24h`: Total 24-hour bridge volume
- `bridge_volumes.volume_7d`: Total 7-day bridge volume
- `bridge_volumes.volume_30d`: Total 30-day bridge volume (may be null depending on provider)
- `bridge_volumes.chains`: Supported chains for the bridge (if available)
- `bridge_volumes.bridges`: Bridge list when querying aggregate view

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
  "dex_liquidity": {
    "protocol": "uniswap_v3",
    "chain": "ethereum",
    "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
    "total_liquidity_usd": 320000000.0,
    "pools": [
      {
        "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "token0": {"address": "0xa0b8...", "symbol": "USDC", "name": "USD Coin", "decimals": 6},
        "token1": {"address": "0xC02a...", "symbol": "WETH", "name": "Wrapped Ether", "decimals": 18},
        "fee_tier": 500,
        "liquidity": 123456789.0,
        "tvl_usd": 320000000.0,
        "volume_usd": 185000000.0,
        "tx_count": 120345
      }
    ],
    "ticks": [],
    "timestamp": "2025-01-10T12:00:00Z"
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
- `dex_liquidity.total_liquidity_usd`: Total liquidity (USD)
- `dex_liquidity.pools`: Pool list with addresses, token metadata, fees, liquidity, volume
- `dex_liquidity.ticks`: Tick distribution (only when `include_ticks` and `pool_address` are provided)

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
  "governance": {
    "dao": "aave",
    "total_proposals": 120,
    "active_proposals": 2,
    "recent_proposals": [
      {
        "id": "0x123abc...",
        "title": "AIP-42: Enable USDC as collateral",
        "state": "active",
        "start_time": "2025-01-05T00:00:00Z",
        "end_time": "2025-01-12T00:00:00Z",
        "choices": ["For", "Against"],
        "scores": [850000, 320000],
        "author": "0x9f...b2"
      }
    ],
    "timestamp": "2025-01-10T12:00:00Z"
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
- `governance.dao`: DAO identifier
- `governance.recent_proposals`: Proposal list with state, choices, and scores

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Some DAOs may require TALLY_API_KEY for Tally on-chain data
- Latency class: medium

---

### 6. onchain_token_unlocks - Token Unlock Schedule

**Description**: Query token vesting and unlock schedules from Token Unlocks

**Endpoint**
```
POST /tools/onchain_token_unlocks
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| token_symbol | string | ✗ | null | Token symbol; omit for popular projects unlock info |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_token_unlocks \
  -H "Content-Type: application/json" \
  -d '{
    "token_symbol": "ARB"
  }'
```

**Response Format**
```json
{
  "token_unlocks": {
    "token_symbol": "ARB",
    "upcoming_unlocks": [
      {
        "project": "Arbitrum",
        "token_symbol": "ARB",
        "unlock_date": "2025-02-15",
        "unlock_amount": 92500000.0,
        "unlock_value_usd": 185000000.0,
        "percentage_of_supply": 0.925,
        "cliff_type": "cliff",
        "description": "Team unlock",
        "source": "token_unlocks"
      }
    ],
    "total_locked_value_usd": 3800000000.0,
    "next_unlock_date": "2025-02-15",
    "timestamp": "2025-01-10T12:00:00Z"
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
- `token_unlocks.upcoming_unlocks`: Upcoming unlock list
- `token_unlocks.total_locked_value_usd`: Total locked value (USD)
- `token_unlocks.next_unlock_date`: Next unlock date

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Some endpoints may require TOKEN_UNLOCKS_API_KEY
- Latency class: fast

---

### 7. onchain_activity - On-Chain Activity

**Description**: Query chain-level activity metrics (active addresses, transactions, gas usage) from Etherscan

**Endpoint**
```
POST /tools/onchain_activity
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chain | string | ✓ | - | Chain name, e.g., ethereum, arbitrum, optimism, polygon |
| protocol | string | ✗ | null | Optional protocol tag for labeling only |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_activity \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum"
  }'
```

**Response Format**
```json
{
  "activity": {
    "protocol": null,
    "chain": "ethereum",
    "active_addresses_24h": 850000,
    "active_addresses_7d": 5200000,
    "transaction_count_24h": 1250000,
    "transaction_count_7d": 8500000,
    "gas_used_24h": 125000000000.0,
    "avg_gas_price_gwei": 22.5,
    "new_addresses_24h": 95000,
    "timestamp": "2025-01-10T12:00:00Z"
  },
  "source_meta": [
    {
      "provider": "etherscan_ethereum",
      "endpoint": "/stats",
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
- `activity.active_addresses_24h`: Active addresses in last 24h
- `activity.active_addresses_7d`: Active addresses in last 7d
- `activity.transaction_count_24h`: Transactions in last 24h
- `activity.gas_used_24h`: Gas used in last 24h

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- ETHERSCAN_API_KEY required for Ethereum mainnet queries
- Latency class: medium

---

### 8. onchain_contract_risk - Contract Risk Analysis

**Description**: Smart contract risk analysis via GoPlus or Slither

**Endpoint**
```
POST /tools/onchain_contract_risk
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| contract_address | string | ✓ | - | Contract address to analyze |
| chain | string | ✓ | - | Chain name, e.g., ethereum, arbitrum, optimism, polygon |
| provider | string | ✗ | null | Analysis provider override: goplus or slither |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_contract_risk \
  -H "Content-Type: application/json" \
  -d '{
    "contract_address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "chain": "ethereum",
    "provider": "goplus"
  }'
```

**Response Format**
```json
{
  "contract_risk": {
    "contract_address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "chain": "ethereum",
    "risk_score": 15,
    "risk_level": "low",
    "provider": "goplus",
    "is_open_source": true,
    "is_proxy": false,
    "is_mintable": false,
    "can_take_back_ownership": false,
    "owner_change_balance": false,
    "hidden_owner": false,
    "selfdestruct": false,
    "external_call": false,
    "buy_tax": 0.0,
    "sell_tax": 0.0,
    "is_honeypot": false,
    "holder_count": 85000,
    "audit_status": "audited",
    "auditors": ["OpenZeppelin"],
    "timestamp": "2025-01-10T12:00:00Z"
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
- `contract_risk.risk_score`: Risk score (0-100)
- `contract_risk.risk_level`: Risk level (low, medium, high, critical)
- `contract_risk.provider`: Data source (goplus or slither)
- `contract_risk.is_open_source/is_proxy/...`: Security check flags

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal server error

**Notes**
- Provider can be overridden per request via `provider` (goplus or slither)
- GOPLUS_API_KEY and GOPLUS_API_SECRET required when using GoPlus
- Latency class: slow

---

### 9. onchain_analytics - CryptoQuant On-Chain Analytics

**Description**: On-chain analytics tool powered by CryptoQuant: MVRV ratio, SOPR, active addresses, exchange flows (reserve/netflow/inflow/outflow), miner data (BTC only), and derivatives funding rates

**Endpoint**
```
POST /tools/onchain_analytics
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✗ | BTC | Asset symbol (BTC, ETH) |
| include_fields | array[string] | ✗ | ["all"] | Fields to include: active_addresses, mvrv, sopr, exchange_reserve, exchange_netflow, exchange_inflow, exchange_outflow, miner (BTC only), funding_rate, all |
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
      "mvrv_ratio": 2.15,
      "signal": "neutral",
      "timestamp": "2025-01-10T00:00:00Z",
      "history": [
        {"date": "2025-01-10", "value": 2.15},
        {"date": "2025-01-09", "value": 2.12}
      ]
    },
    "sopr": {
      "sopr": 1.05,
      "signal": "slight_profit",
      "timestamp": "2025-01-10T00:00:00Z",
      "history": [
        {"date": "2025-01-10", "value": 1.05},
        {"date": "2025-01-09", "value": 1.03}
      ]
    },
    "exchange_netflow": {
      "netflow": -25000000.0,
      "netflow_usd": -25000000.0,
      "signal": "bullish",
      "timestamp": "2025-01-10T00:00:00Z",
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
- `data.exchange_inflow`: Exchange inflow (USD and history when available)
- `data.exchange_outflow`: Exchange outflow (USD and history when available)
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
