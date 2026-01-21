# 市场扩展工具 API 文档

## 概述

市场扩展工具提供深度市场数据分析能力，包括历史价格、技术指标、ETF 流向、交易所储备、借贷市场、稳定币监控、期权数据、MEV 统计和 Hyperliquid 数据。

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

### 1. price_history - 历史价格与技术指标

**描述**: 历史 K 线数据，包含技术指标（SMA、EMA、RSI、MACD、布林带、ATR）、统计数据（波动率、最大回撤、夏普比率）和支撑/阻力位

**端点 / Endpoint**
```
POST /tools/price_history
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 交易对符号，如 BTC/USDT, ETH/USDT |
| interval | string | ✗ | 1d | K线周期: 1h=小时, 4h=4小时, 1d=日线, 1w=周线, 1M=月线 |
| lookback_days | integer | ✗ | 365 | 回溯天数，默认365天，最多5年(1825天) |
| include_indicators | array[string] | ✗ | ["sma", "rsi", "macd", "bollinger"] | 需要计算的技术指标: sma, ema, rsi, macd, bollinger, atr, all |
| indicator_params | object | ✗ | null | 指标参数覆盖，如 {'sma_periods': [20, 50, 200], 'rsi_period': 14} |

**请求示例 / Request Example**
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

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `ohlcv`: K线数据数组，包含时间戳、开高低收价和交易量
- `indicators.sma`: 简单移动平均线（20、50、200期）
- `indicators.ema`: 指数移动平均线（12、26期）
- `indicators.rsi`: 相对强弱指数（14期），当前值和历史数据
- `indicators.macd`: MACD指标，包含MACD线、信号线、柱状图和当前信号
- `indicators.bollinger`: 布林带，包含上轨、中轨、下轨和带宽
- `indicators.atr`: 平均真实波幅（14期）
- `statistics`: 统计数据，包括波动率、最大回撤、夏普比率等
- `support_resistance`: 支撑和阻力位
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：中等 (medium)
- 支持的 K 线周期：1h（小时）、4h（4小时）、1d（日线）、1w（周线）、1M（月线）
- 回溯天数范围：7-1825 天

---

### 2. sector_peers - 赛道对比分析

**描述**: 赛道/同类项目对比分析：获取同类别代币的市场指标、TVL、费用和估值对比

**端点 / Endpoint**
```
POST /tools/sector_peers
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 目标代币符号，如 AAVE, UNI |
| limit | integer | ✗ | 10 | 返回竞品数量 (3-20) |
| sort_by | string | ✗ | market_cap | 排序字段: market_cap, tvl, volume_24h, price_change_7d |
| include_metrics | array[string] | ✗ | ["market", "tvl", "fees", "social"] | 包含的对比指标: market, tvl, fees, social |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/sector_peers \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAVE",
    "limit": 10
  }'
```

**响应格式 / Response Format**
```json
{
  "target_symbol": "AAVE",
  "sector": "DeFi - Lending",
  "sector_description": "去中心化借贷协议",
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

**主要字段说明 / Field Descriptions**
- `sector`: 板块名称（如 "DeFi - Lending"）
- `peers`: 竞品列表，包含目标代币和同赛道项目
  - `is_target`: 标识是否为目标代币
  - `market_cap`: 市值
  - `tvl`: 总锁仓量
  - `fees_24h/7d`: 24小时/7日费用收入
  - `price_change_*_pct`: 价格变化百分比
- `comparison`: 对比分析
  - `valuation_ratios`: 估值比率（市值/TVL等）
  - `fee_multiples`: 费用收入倍数（P/E比率）
  - `market_share`: 市场份额分析
- `sector_stats`: 板块统计数据
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：中等 (medium)
- 返回的竞品数量可配置（3-20个）
- 自动识别代币所属赛道

---

### 3. etf_flows_holdings - ETF 资金流与持仓

**描述**: ETF 资金流向和持仓快照（基于 Farside 等免费数据源）

**端点 / Endpoint**
```
POST /tools/etf_flows_holdings
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| dataset | string | ✗ | bitcoin | 数据集：bitcoin / ethereum |
| url_override | string | ✗ | null | 可选的Farside URL覆盖 |
| include_fields | array[string] | ✗ | ["flows"] | 返回字段：flows, holdings, all |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/etf_flows_holdings \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "bitcoin"
  }'
```

**响应格式 / Response Format**
```json
{
  "dataset": "bitcoin",
  "flows": [
    {
      "data": {}
    }
  ],
  "holdings": [],
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

**主要字段说明 / Field Descriptions**
- `dataset`: 数据集类型（bitcoin 或 ethereum）
- `flows`: Farside 解析后的资金流向行（字段随数据集变化）
- `holdings`: 持仓行数据（未配置数据源时可能为空）
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 默认未配置持仓数据源；请求 `holdings`/`all` 时将返回空持仓并给出 warning
- 延迟等级：中等 (medium)
- 数据来源：Farside 等公开数据

---

### 4. cex_netflow_reserves - CEX 储备与大额转账

**描述**: 来自 DefiLlama 的 CEX 储备数据，可选包含 Whale Alert 大额转账

**端点 / Endpoint**
```
POST /tools/cex_netflow_reserves
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| exchange | string | ✗ | null | 交易所名称（如 binance），为空时返回所有交易所汇总 |
| include_whale_transfers | boolean | ✗ | false | 是否附带 Whale Alert 大额转账 |
| min_transfer_usd | integer | ✗ | 500000 | 大额转账最小USD |
| lookback_hours | integer | ✗ | 24 | 大额转账回溯小时数 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/cex_netflow_reserves \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "binance"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `reserves`: CEX 储备数据
  - `total_reserves_usd`: 总储备价值（USD）
  - `token_breakdown`: 各币种储备详情
  - `chain_distribution`: 各链储备分布
- `whale_transfers`: 大额转账数据（如果请求）
  - `total_transfers`: 转账总数
  - `total_value_usd`: 转账总价值
  - `transfers`: 转账记录列表
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- Whale Alert 需要 WHALE_ALERT_API_KEY 才能获取转账数据
- 延迟等级：快速 (fast)
- 支持单个交易所查询或全部交易所汇总

---

### 5. lending_liquidation_risk - 借贷与清算风险

**描述**: 借贷收益率快照，可选包含清算数据

**端点 / Endpoint**
```
POST /tools/lending_liquidation_risk
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| asset | string | ✗ | null | 资产符号过滤（如 ETH, USDC） |
| protocols | array[string] | ✗ | null | 协议过滤（如 aave） |
| include_liquidations | boolean | ✗ | false | 是否包含清算数据 |
| lookback_hours | integer | ✗ | 24 | 清算数据回溯小时数 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/lending_liquidation_risk \
  -H "Content-Type: application/json" \
  -d '{
    "asset": "ETH"
  }'
```

**响应格式 / Response Format**
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

**主要字段说明 / Field Descriptions**
- `yields`: 借贷收益率数据数组
  - `supply_apy`: 存款年化收益率
  - `borrow_apy`: 借款年化利率
  - `utilization_rate`: 资金利用率
  - `total_supply/borrow`: 总存款/借款量
  - `available_liquidity`: 可用流动性
- `liquidations`: 清算数据（如果请求）
  - `total_liquidations`: 清算总数
  - `total_value_usd`: 清算总价值
  - `long/short_*`: 多头/空头清算统计
  - `events`: 清算事件列表
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- Coinglass 清算数据需要 COINGLASS_API_KEY
- 延迟等级：快速 (fast)
- 支持多协议对比查询

---

### 6. stablecoin_health - 稳定币健康度

**描述**: 稳定币供应量和链分布快照

**端点 / Endpoint**
```
POST /tools/stablecoin_health
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✗ | null | 稳定币符号过滤，如 USDT |
| chains | array[string] | ✗ | null | 链过滤 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/stablecoin_health \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "USDC"
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "USDC",
  "stablecoins": [
    {
      "stablecoin": "USDC",
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

**主要字段说明 / Field Descriptions**
- `stablecoins`: 稳定币数据数组
  - `total_supply`: 总供应量
  - `market_cap`: 市值
  - `chains`: 各链分布详情
  - `dominance`: 市场份额（相对所有稳定币）
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：快速 (fast)
- 支持单个稳定币查询或全部稳定币汇总

---

### 7. options_vol_skew - 期权波动率与偏度

**描述**: 来自 Deribit/OKX/Binance 的期权波动率/偏度快照

**端点 / Endpoint**
```
POST /tools/options_vol_skew
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 标的符号，如 BTC 或 ETH |
| expiry | string | ✗ | null | 到期日或合约ID（可选） |
| providers | array[string] | ✗ | ["deribit", "okx", "binance"] | 数据源列表：deribit, okx, binance |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/options_vol_skew \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC"
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "summary": {
      "dvol_index": 68.5,
      "dvol_timestamp": "2025-01-10T12:00:00Z"
    },
    "deribit": {
      "volatility_index": {}
    },
    "okx": {},
    "binance": {}
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

**主要字段说明 / Field Descriptions**
- `data.summary`: 派生指标（尽力而为）
  - `dvol_index`: Deribit DVOL 值
  - `dvol_timestamp`: DVOL 时间戳
- `data.<provider>`: 各数据源的原始响应（结构因数据源/到期日而异）
  - `deribit.volatility_index`: 波动率指数响应
  - `deribit.instruments`: 提供 `expiry` 时返回筛选后的合约列表
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- Binance 期权需要特定期权符号才能获取标记数据
- 延迟等级：中等 (medium)
- 支持多数据源对比

---

### 8. blockspace_mev - 区块空间与 MEV

**描述**: 区块空间 + MEV-Boost 统计数据，包含 Gas Oracle 数据

**端点 / Endpoint**
```
POST /tools/blockspace_mev
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chain | string | ✗ | ethereum | 链名称（目前仅支持ethereum） |
| limit | integer | ✗ | 100 | MEV-Boost记录数量 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/blockspace_mev \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "ethereum"
  }'
```

**响应格式 / Response Format**
```json
{
  "chain": "ethereum",
  "mev_boost": {
    "builder_blocks_received": [],
    "proposer_payload_delivered": [],
    "summary": {
      "builder_blocks_count": 0,
      "proposer_blocks_count": 0,
      "total_builder_value_wei": 0,
      "total_proposer_value_wei": 0,
      "total_proposer_value_eth": 0.0,
      "total_proposer_value_usd": 0.0,
      "avg_proposer_value_eth": 0.0,
      "avg_proposer_value_usd": 0.0
    },
    "top_builders": [
      {
        "builder": "0xabc...",
        "blocks": 120,
        "value_wei": 4500000000000000000,
        "share": 0.25
      }
    ],
    "top_relays": [
      {
        "relay": "flashbots",
        "blocks": 480,
        "share": 1.0
      }
    ],
    "recent_blocks": [
      {
        "block_number": 18950000,
        "value_wei": 850000000000000000,
        "value_eth": 0.85,
        "value_usd": 2040.0,
        "builder": "0xabc...",
        "relay": "flashbots",
        "timestamp": "2025-01-10T11:58:00Z"
      }
    ]
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
      "provider": "flashbots",
      "endpoint": "/relay/v1/data/bidtraces/builder_blocks_received",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 30,
      "version": "v3"
    },
    {
      "provider": "flashbots",
      "endpoint": "/relay/v1/data/bidtraces/proposer_payload_delivered",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 30,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**主要字段说明 / Field Descriptions**
- `mev_boost`: MEV-Boost 原始数据与派生指标
  - `builder_blocks_received`: Flashbots builder blocks 列表
  - `proposer_payload_delivered`: Flashbots proposer payload 列表
  - `summary`: 汇总统计与总价值（wei/eth/usd）
  - `top_builders`: 按交付 payload 统计的 builders
  - `top_relays`: 按交付 payload 统计的 relays
  - `recent_blocks`: 最近交付的 payload 列表
- `gas_oracle`: Gas 价格预言机数据
  - `safe/propose/fast_gas_price`: 安全/标准/快速 Gas 价格（Gwei）
  - `base_fee`: 基础费用
  - `priority_fee_suggestions`: 优先费用建议
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- Gas oracle 需要 ETHERSCAN_API_KEY（以太坊主网）
- USD 价值字段会在可用时使用 Etherscan ETH 价格计算
- 延迟等级：快速 (fast)
- 当前仅支持以太坊主网

---

### 9. hyperliquid_market - Hyperliquid 市场数据

**描述**: Hyperliquid 市场数据（资金费率、未平仓量、订单簿、成交记录）

**端点 / Endpoint**
```
POST /tools/hyperliquid_market
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 标的符号，如 BTC |
| start_time | integer | ✗ | null | 资金费率起始时间（Unix 毫秒时间戳，仅 funding 生效）。若请求 funding 且未提供，默认 now - 7d。 |
| end_time | integer | ✗ | null | 资金费率结束时间（Unix 毫秒时间戳，仅 funding 生效）。默认当前时间。 |
| include_fields | array[string] | ✗ | ["all"] | 返回字段：funding, open_interest, orderbook, trades, asset_contexts, all |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/hyperliquid_market \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "include_fields": ["funding", "open_interest"],
    "start_time": 1735689600000
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "funding": {},
    "open_interest": {},
    "orderbook": {},
    "trades": [],
    "asset_contexts": {}
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

**主要字段说明 / Field Descriptions**
- `data.<field>`: Hyperliquid 各字段的原始响应
- `source_meta`: 数据来源元信息

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：快速 (fast)
- 专注于 Hyperliquid DEX 数据
- 资金费率需要 `start_time`；未提供时工具会自动补默认值。
- open_interest 从 `metaAndAssetCtxs` 解析并返回对应资产的上下文数据。

---

## 错误处理

所有工具都遵循统一的错误响应格式：

### 422 Unprocessable Entity
参数验证错误，返回详细的验证错误信息。

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
工具未初始化或依赖服务不可用。

```json
{
  "detail": "Tool 'price_history' is not initialized or disabled"
}
```

### 500 Internal Server Error
内部服务错误，返回错误消息。

```json
{
  "detail": "Internal error: connection timeout"
}
```

## 数据源元信息

所有成功响应都包含 `source_meta` 数组，提供数据来源的完整追溯信息：

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

字段说明：
- `provider`: 数据提供者（如 binance, defillama）
- `endpoint`: API 端点路径
- `as_of_utc`: 数据获取时间戳
- `ttl_seconds`: 缓存 TTL（秒）
- `version`: 数据契约版本
- `degraded`: 是否处于降级模式
- `fallback_used`: 使用的备用源（如果有）
- `response_time_ms`: 响应时间（毫秒）

## 最佳实践

1. **错误处理**: 始终检查 `warnings` 数组，即使请求成功
2. **缓存策略**: 根据 `source_meta` 中的 `ttl_seconds` 合理缓存数据
3. **降级处理**: 检查 `degraded` 字段，降级模式下数据可能不完整
4. **并发请求**: 市场工具支持并发调用，但请注意 API 速率限制
5. **时间戳**: 所有时间戳均为 UTC ISO 8601 格式
6. **参数验证**: 利用 422 错误响应进行客户端验证
7. **API 密钥管理**: 部分工具需要第三方 API 密钥，请在 `docker/.env` 中配置
