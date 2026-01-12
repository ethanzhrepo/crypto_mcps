# 链上分析工具 API 文档

## 概述

链上分析工具提供区块链层面的深度数据分析，包括协议 TVL、跨链桥流量、DEX 流动性、治理提案、大额转账、代币解锁、活跃度指标、合约风险和 CryptoQuant 链上分析。

## 通用说明

- **Base URL**: `http://localhost:8001`
- **所有工具端点**: `POST /tools/{tool_name}`
- **请求格式**: `Content-Type: application/json`
- **响应格式**: JSON

所有响应都包含以下通用字段：
- `source_meta`: 数据来源元信息数组
- `warnings`: 警告信息数组
- `as_of_utc`: 数据时间戳（ISO 8601）

## 工具列表

### 1. onchain_tvl_fees - 协议 TVL 与费用

**描述**: 查询 DeFi 协议的 TVL（总锁仓价值）和费用/收入数据，数据来自 DefiLlama

**端点 / Endpoint**
```
POST /tools/onchain_tvl_fees
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| protocol | string | ✓ | - | 协议名称，如 uniswap, aave, compound |
| chain | string | ✗ | null | 可选的链标签，如 ethereum, arbitrum |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_tvl_fees \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "uniswap"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.tvl.total_usd`: 总锁仓价值（美元）
- `data.tvl.change_24h`: 24小时变化百分比
- `data.tvl.chain_breakdown`: 各链的 TVL 分布
- `data.fees.fees_24h`: 24小时协议费用
- `data.fees.revenue_24h`: 24小时协议收入

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 数据来自 DefiLlama，无需 API key
- 延迟等级：fast

---

### 2. onchain_stablecoins_cex - 稳定币与 CEX 储备

**描述**: 查询稳定币指标和中心化交易所储备数据，数据来自 DefiLlama

**端点 / Endpoint**
```
POST /tools/onchain_stablecoins_cex
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| stablecoin | string | ✗ | null | 稳定币符号，如 USDT, USDC；省略则返回汇总数据 |
| exchange | string | ✗ | null | CEX 名称，如 binance, coinbase；省略则返回所有交易所 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_stablecoins_cex \
  -H "Content-Type: application/json" \
  -d '{
    "stablecoin": "USDT"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.stablecoin.total_supply`: 稳定币总供应量
- `data.stablecoin.chain_distribution`: 各链的分布情况
- `data.cex_reserves.total_usd`: CEX 总储备（美元）
- `data.cex_reserves.exchanges`: 各交易所的储备分布

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 数据来自 DefiLlama，无需 API key
- 延迟等级：fast

---

### 3. onchain_bridge_volumes - 跨链桥成交量

**描述**: 查询跨链桥的成交量数据（24h/7d/30d），数据来自 DefiLlama

**端点 / Endpoint**
```
POST /tools/onchain_bridge_volumes
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chain | string | ✗ | null | 链名称，如 arbitrum, optimism |
| bridge | string | ✗ | null | 桥名称，如 stargate, hop；省略则返回汇总数据 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_bridge_volumes \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "arbitrum"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.volume_24h`: 24小时跨链桥总成交量
- `data.volume_7d`: 7天跨链桥总成交量
- `data.volume_30d`: 30天跨链桥总成交量
- `data.bridges`: 各个桥的成交量明细

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 数据来自 DefiLlama，无需 API key
- 延迟等级：fast

---

### 4. onchain_dex_liquidity - DEX 流动性

**描述**: 查询 Uniswap v3 的 DEX 流动性、池子信息和可选的 tick 分布，数据来自 The Graph

**端点 / Endpoint**
```
POST /tools/onchain_dex_liquidity
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chain | string | ✓ | - | 链名称，如 ethereum, arbitrum, optimism, polygon |
| token_address | string | ✗ | null | 代币地址，用于列出相关池子 |
| pool_address | string | ✗ | null | Uniswap v3 池子地址，用于单个池子详情 |
| include_ticks | boolean | ✗ | false | 是否包含 tick 级别的流动性分布（仅当指定 pool_address 时有效） |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_dex_liquidity \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.total_liquidity_usd`: 总流动性（美元）
- `data.pools`: 池子列表，包含地址、代币对、费率等级、流动性、交易量
- `data.pools[].liquidity_usd`: 单个池子的流动性
- `data.pools[].volume_24h`: 单个池子的24小时交易量

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 支持通过公共子图查询 Uniswap v3 池子
- 延迟等级：medium

---

### 5. onchain_governance - 治理提案

**描述**: 查询 DAO 治理提案，包括 Snapshot（链下）和 Tally（链上）的提案数据

**端点 / Endpoint**
```
POST /tools/onchain_governance
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chain | string | ✗ | ethereum | 链名称，用于派生 Tally chain_id |
| snapshot_space | string | ✗ | null | Snapshot 空间 ID，如 aave.eth, uniswap.eth |
| governor_address | string | ✗ | null | 链上治理合约地址（用于 Tally） |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_governance \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_space": "aave.eth"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.snapshot_proposals`: Snapshot 链下提案列表
- `data.tally_proposals`: Tally 链上提案列表
- `proposals[].state`: 提案状态（active, closed, pending 等）
- `proposals[].scores`: 各选项的投票数

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 对于某些 DAO，Tally 链上数据可能需要 TALLY_API_KEY
- 延迟等级：medium

---

### 6. onchain_whale_transfers - 鲸鱼转账监控

**描述**: 使用 Whale Alert API 监控大额链上转账

**端点 / Endpoint**
```
POST /tools/onchain_whale_transfers
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✗ | null | 代币符号，如 BTC, ETH；省略则返回多资产视图 |
| min_value_usd | number | ✗ | 500000 | 最小转账金额（美元） |
| lookback_hours | integer | ✗ | 24 | 回溯时间窗口（小时） |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_whale_transfers \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "min_value_usd": 1000000
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.transfers`: 转账列表
- `data.transfers[].from.owner_type`: 发送方类型（exchange, unknown 等）
- `data.transfers[].amount_usd`: 转账金额（美元）
- `data.total_count`: 转账总数
- `data.total_value_usd`: 转账总价值

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 建议配置 WHALE_ALERT_API_KEY 以获得完整覆盖
- 延迟等级：fast

---

### 7. onchain_token_unlocks - 代币解锁时间表

**描述**: 查询代币的归属和解锁时间表，数据来自 Token Unlocks

**端点 / Endpoint**
```
POST /tools/onchain_token_unlocks
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✗ | null | 代币符号；省略则返回热门项目的解锁信息 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_token_unlocks \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ARB"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.next_unlock`: 下次解锁信息
- `data.next_unlock.amount`: 解锁数量
- `data.next_unlock.percent_of_supply`: 占总供应量的百分比
- `data.upcoming_unlocks`: 即将到来的解锁列表
- `data.total_locked`: 当前锁定总量

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 某些端点可能需要 TOKEN_UNLOCKS_API_KEY
- 延迟等级：fast

---

### 8. onchain_activity - 链上活跃度

**描述**: 查询链级别的活跃度指标（活跃地址数、交易数、Gas 使用量），数据来自 Etherscan

**端点 / Endpoint**
```
POST /tools/onchain_activity
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chain | string | ✓ | - | 链名称，如 ethereum, arbitrum, optimism, polygon |
| window | string | ✗ | 7d | 时间窗口，如 1d, 7d, 30d |
| protocol | string | ✗ | null | 可选的协议标签，仅用于标记 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_activity \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum",
    "window": "7d"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.active_addresses.total`: 时间窗口内的活跃地址总数
- `data.active_addresses.daily_average`: 日均活跃地址数
- `data.transactions.total`: 时间窗口内的交易总数
- `data.gas_usage.total_gwei`: Gas 总消耗量

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 查询以太坊主网时需要 ETHERSCAN_API_KEY
- 延迟等级：medium

---

### 9. onchain_contract_risk - 合约风险分析

**描述**: 通过 GoPlus 或 Slither 进行智能合约风险分析

**端点 / Endpoint**
```
POST /tools/onchain_contract_risk
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| address | string | ✓ | - | 要分析的合约地址 |
| chain | string | ✓ | - | 链名称，如 ethereum, arbitrum, optimism, polygon |
| provider | string | ✗ | goplus | 分析提供商：goplus 或 slither |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/onchain_contract_risk \
  -H "Content-Type: application/json" \
  -d '{
    "address": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "chain": "ethereum"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.risk_score`: 风险评分（0-100）
- `data.risk_level`: 风险等级（low, medium, high）
- `data.findings`: 风险发现列表
- `data.checks`: 安全检查项

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 使用 GoPlus 时需要 GOPLUS_API_KEY 和 GOPLUS_API_SECRET
- 延迟等级：slow

---

### 10. onchain_analytics - CryptoQuant 链上分析

**描述**: 由 CryptoQuant 提供支持的链上分析工具：MVRV 比率、SOPR、活跃地址、交易所流量（储备/净流量/流入/流出）、矿工数据（仅 BTC）和衍生品资金费率

**端点 / Endpoint**
```
POST /tools/onchain_analytics
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✗ | BTC | 资产符号（BTC, ETH） |
| include_fields | array[string] | ✗ | ["all"] | 包含的字段：mvrv, sopr, active_addresses, exchange_reserve, exchange_netflow, exchange_inflow, exchange_outflow, miner (仅BTC), funding_rate, all |
| window | string | ✗ | day | 时间窗口：hour 或 day |
| limit | integer | ✗ | 30 | 数据点数量（1-365） |

**请求示例 / Request Example**
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

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `data.mvrv`: MVRV 比率（市值/实现价值）
  - > 3.7: 超买（overvalued）
  - < 1.0: 超卖（undervalued）
- `data.sopr`: SOPR（花费产出利润率）
  - > 1.0: 链上获利
  - < 1.0: 链上亏损
- `data.exchange_netflow`: 交易所净流量
  - 正值: 流入（看跌信号）
  - 负值: 流出（看涨信号）
- `data.miner`: 矿工数据（仅 BTC）
  - `reserve`: 矿工储备
  - `outflow`: 矿工流出
- `data.funding_rate`: 永续合约资金费率

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化（未配置 CRYPTOQUANT_API_KEY）
- 500: 内部服务错误

**注意事项 / Notes**
- **必需**: CRYPTOQUANT_API_KEY
- 矿工数据仅适用于 BTC
- 延迟等级：medium
- 数据新鲜度：1小时缓存

---

## 统一错误处理

所有工具都遵循统一的错误响应格式：

### 参数验证错误（422）
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

### 工具未初始化（503）
```json
{
  "detail": "Tool not initialized"
}
```

### 内部服务错误（500）
```json
{
  "detail": "Internal server error",
  "error": "Error message details"
}
```

## 数据源元信息

所有响应中的 `source_meta` 字段提供数据溯源：

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

- `provider`: 数据提供商
- `endpoint`: API 端点
- `as_of_utc`: 数据时间戳
- `ttl_seconds`: 缓存有效期
- `degraded`: 是否处于降级模式

## 最佳实践

1. **API Key 配置**: 确保在 `docker/.env` 中配置必需的 API keys
2. **错误处理**: 始终检查 `warnings` 字段和 HTTP 状态码
3. **数据新鲜度**: 参考 `source_meta[].ttl_seconds` 了解数据缓存策略
4. **速率限制**: 注意各数据源的速率限制，避免过度请求
5. **链参数**: 使用标准化的链名称（ethereum, arbitrum, optimism, polygon）
