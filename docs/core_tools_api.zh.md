# 核心工具 API 文档

## 概述

核心工具提供加密货币市场的基础数据查询能力，包括代币信息、市场数据、衍生品、宏观指标、社交媒体分析等。

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

### 1. crypto_overview - 代币概览

**描述**: 全面的代币概览，包括基础信息、市场指标、供应结构、持有者集中度、社交链接、板块分类和开发活动

**端点 / Endpoint**
```
POST /tools/crypto_overview
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 代币符号，如 BTC, ETH, ARB |
| token_address | string | ✗ | null | 合约地址（可选，用于消歧义） |
| chain | string | ✗ | null | 链名称，如 ethereum, bsc, arbitrum |
| vs_currency | string | ✗ | usd | 计价货币 |
| include_fields | array[string] | ✗ | ["all"] | 包含的字段: basic, market, supply, holders, social, sector, dev_activity, all |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/crypto_overview \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "include_fields": ["basic", "market", "supply"]
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC",
  "data": {
    "basic": {
      "id": "bitcoin",
      "symbol": "BTC",
      "name": "Bitcoin",
      "description": "Bitcoin is a decentralized cryptocurrency...",
      "homepage": ["https://bitcoin.org"],
      "blockchain_site": ["https://blockchain.info"],
      "contract_address": null,
      "chain": null
    },
    "market": {
      "price": 95000.0,
      "market_cap": 1850000000000.0,
      "market_cap_rank": 1,
      "total_volume_24h": 45000000000.0,
      "price_change_percentage_24h": 2.5
    },
    "supply": {
      "circulating_supply": 19500000.0,
      "total_supply": 19500000.0,
      "max_supply": 21000000.0,
      "circulating_percent": 92.86
    }
  },
  "source_meta": [
    {
      "provider": "coingecko",
      "endpoint": "/coins/bitcoin",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 60,
      "version": "v3",
      "degraded": false
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**主要字段说明 / Field Descriptions**
- `data.basic`: 基础信息，包括 ID、名称、描述、官网等
- `data.market`: 市场指标，包括价格、市值、交易量等
- `data.supply`: 供应信息，包括流通量、总供应量、最大供应量等
- `data.holders`: 持有者集中度信息（需要 ETHERSCAN_API_KEY）
- `data.social`: 社交媒体统计（Twitter、Reddit、Telegram 等）
- `data.sector`: 板块分类信息
- `data.dev_activity`: 开发活跃度（需要 GITHUB_TOKEN）
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 某些字段需要 API 密钥：COINMARKETCAP_API_KEY（市场排名）、ETHERSCAN_API_KEY（持有者）、GITHUB_TOKEN（开发活动）
- 延迟等级：中等 (medium)

---

### 2. market_microstructure - 市场微结构

**描述**: 实时市场微结构数据

**端点 / Endpoint**
```
POST /tools/market_microstructure
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 交易对符号，如 BTC/USDT, ETH/USDT |
| venues | array[string] | ✗ | ["binance"] | 交易所列表，如 ['binance', 'okx']，支持多场所聚合 |
| include_fields | array[string] | ✗ | ["ticker", "orderbook"] | 返回字段: ticker, klines, trades, orderbook, aggregated_orderbook, volume_profile, taker_flow, slippage, venue_specs, sector_stats, all |
| kline_interval | string | ✗ | 1h | K线周期: 1m, 5m, 15m, 1h, 4h, 1d |
| kline_limit | integer | ✗ | 100 | K线数量 |
| orderbook_depth | integer | ✗ | 100 | 订单簿深度（建议>=100；过小会导致深度/滑点等分析失真） |
| trades_limit | integer | ✗ | 100 | 成交记录数量 |
| slippage_size_usd | float | ✗ | 10000 | 滑点估算的订单大小(USD) |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/market_microstructure \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "venues": ["binance"],
    "include_fields": ["ticker"]
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC/USDT",
  "exchange": "binance",
  "data": {
    "ticker": {
      "symbol": "BTC/USDT",
      "exchange": "binance",
      "last_price": 95000.0,
      "bid": 94995.0,
      "ask": 95005.0,
      "spread_bps": 1.05,
      "volume_24h": 25000.0,
      "quote_volume_24h": 2375000000.0,
      "price_change_24h": 2000.0,
      "price_change_percent_24h": 2.15,
      "high_24h": 96000.0,
      "low_24h": 92000.0,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  },
  "source_meta": [
    {
      "provider": "binance",
      "endpoint": "/api/v3/ticker/24hr",
      "as_of_utc": "2025-01-10T12:00:00Z",
      "ttl_seconds": 10,
      "version": "v3"
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**主要字段说明 / Field Descriptions**
- `data.ticker`: 实时行情数据，包括价格、买卖价差、24h 交易量等
- `data.klines`: K线数据数组
- `data.trades`: 最近成交记录
- `data.orderbook`: 订单簿数据，包括买卖盘深度
- `data.aggregated_orderbook`: 多场所聚合订单簿
- `data.volume_profile`: 成交量价格分布
- `data.taker_flow`: 主动买卖流分析
- `data.slippage`: 滑点估算
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：快速 (fast)

---

### 3. derivatives_hub - 衍生品中心

**描述**: 衍生品数据中心：资金费率、未平仓量、清算、多空比、借贷利率、基差曲线、期限结构、期权曲面和期权指标

**端点 / Endpoint**
```
POST /tools/derivatives_hub
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 交易对符号，如 BTC/USDT, ETH/USDT |
| include_fields | array[string] | ✗ | ["funding_rate", "open_interest"] | 返回字段: funding_rate, open_interest, liquidations, long_short_ratio, basis_curve, term_structure, options_surface, options_metrics, borrow_rates, all |
| lookback_hours | integer | ✗ | 24 | 清算数据回溯小时数 |
| options_expiry | string | ✗ | null | 期权到期日，格式: YYMMDD |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/derivatives_hub \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "include_fields": ["funding_rate", "open_interest"]
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTCUSDT",
  "data": {
    "funding_rate": {
      "symbol": "BTCUSDT",
      "exchange": "binance",
      "funding_rate": 0.0001,
      "funding_rate_annual": 0.1095,
      "next_funding_time": "2025-01-10T16:00:00Z",
      "mark_price": 95000.0,
      "index_price": 94995.0,
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "open_interest": {
      "symbol": "BTCUSDT",
      "exchange": "binance",
      "open_interest": 125000.0,
      "open_interest_usd": 11875000000.0,
      "oi_change_24h": 5000.0,
      "oi_change_percent_24h": 4.17,
      "timestamp": "2025-01-10T12:00:00Z"
    }
  },
  "source_meta": [
    {
      "provider": "binance",
      "endpoint": "/fapi/v1/fundingRate",
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
- `data.funding_rate`: 资金费率数据，包括当前费率、年化费率、下次结算时间
- `data.open_interest`: 未平仓量数据，包括总量和 24h 变化
- `data.liquidations`: 清算统计，包括多空清算事件
- `data.long_short_ratio`: 多空比数据
- `data.basis_curve`: 基差曲线（现货与期货价差）
- `data.term_structure`: 期限结构
- `data.options_surface`: 期权波动率曲面
- `data.options_metrics`: 期权市场指标
- `data.borrow_rates`: 借贷利率
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 无特殊 API 密钥要求
- 延迟等级：中等 (medium)

---

### 4. crypto_news_search - 加密新闻搜索

**描述**: 搜索加密新闻

**端点 / Endpoint**
```
POST /tools/crypto_news_search
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| query | string | ✗ | null | 搜索关键词（可选） |
| symbol | string | ✗ | null | 币种符号（可选），如 BTC、ETH |
| limit | integer | ✗ | 20 | 结果数量 |
| sort_by | string | ✗ | timestamp | 排序字段：timestamp（最新优先）或 score（相关性优先） |
| time_range | string | ✗ | null | 时间范围过滤: past_24h/day, past_week/7d, past_month/30d, past_year 等 |
| start_time | string | ✗ | null | 起始时间（ISO格式，优先级高于 time_range），如 2025-01-01T00:00:00Z |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/crypto_news_search \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "limit": 20,
    "time_range": "24h"
  }'
```

**响应格式 / Response Format**
```json
{
  "query": null,
  "symbol": "BTC",
  "results": [
    {
      "title": "BTC 突破 95000",
      "url": "https://t.me/cryptonews/12345",
      "snippet": "比特币今日突破 95000 美元大关...",
      "source": "telegram",
      "relevance_score": 0.95,
      "published_at": "2025-01-10T10:30:00Z"
    }
  ],
  "total_results": 156,
  "source_meta": [
    {
      "provider": "telegram_scraper",
      "endpoint": "/search",
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
- `query`: 搜索关键词（如果提供）
- `symbol`: 币种符号（如果提供）
- `results`: 搜索结果数组
  - `title`: 结果标题
  - `url`: 结果链接
  - `snippet`: 结果摘要
  - `relevance_score`: 相关性评分
  - `published_at`: 发布时间
- `total_results`: 总结果数
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化或加密新闻后端不可达
- 500: 内部服务错误

**注意事项 / Notes**
- 需要配置 TELEGRAM_SCRAPER_URL
- 延迟等级：快速 (fast)

---

### 5. web_research_search - Web 研究搜索

**描述**: 多源 Web 和新闻搜索：Bing News、Brave Search、Kaito 加密新闻和 DuckDuckGo。支持可配置提供商的并行搜索

**端点 / Endpoint**
```
POST /tools/web_research_search
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| query | string | ✓ | - | 搜索关键词 |
| scope | string | ✗ | web | 搜索范围: web (综合搜索), academic (学术论文), news (新闻资讯) |
| providers | array[string] | ✗ | null | 搜索提供商列表：web 范围支持 brave, duckduckgo, google, bing, serpapi, kaito；news 范围支持 bing_news/bing, kaito。默认自动选择可用的提供商 |
| time_range | string | ✗ | null | 时间范围过滤: past_24h/day, past_week/7d, past_month/30d, past_year 等，仅在 scope=news 有效 |
| limit | integer | ✗ | 10 | 结果数量 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/web_research_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "BTC spot ETF approval",
    "top_k": 5
  }'
```

**响应格式 / Response Format**
```json
{
  "query": "BTC spot ETF approval",
  "results": [
    {
      "title": "SEC Approves Bitcoin Spot ETF",
      "url": "https://example.com/btc-etf-approval",
      "snippet": "The SEC has approved the first Bitcoin spot ETF...",
      "source": "bing_news",
      "relevance_score": 0.98,
      "published_at": "2025-01-09T15:00:00Z"
    }
  ],
  "total_results": 42,
  "source_meta": [
    {
      "provider": "bing_news",
      "endpoint": "/v7.0/news/search",
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
- `query`: 搜索关键词
- `results`: 搜索结果数组
  - `title`: 文章标题
  - `url`: 文章链接
  - `snippet`: 文章摘要
  - `source`: 数据源（bing_news, brave, kaito 等）
  - `relevance_score`: 相关性评分
  - `published_at`: 发布时间
- `total_results`: 总结果数
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 某些提供商可能需要 API 密钥（参见 docker/.env）
- 延迟等级：慢速 (slow)

---

### 6. grok_social_trace - Grok 社交追溯

**描述**: 使用 Grok 在 X/Twitter 上追溯流传消息的起源，评估是否可能为推广信息，并提供基于深度搜索的社交分析

**端点 / Endpoint**
```
POST /tools/grok_social_trace
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| keyword_prompt | string | ✓ | - | 来自 LLM 的关键提示词，用于在 X/Twitter 上进行溯源与 deepsearch 分析 |
| language | string | ✗ | auto | 优先使用的语言，例如 zh、en；auto 表示由 Grok 自动判断 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/grok_social_trace \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Some rumor text"
  }'
```

**响应格式 / Response Format**
```json
{
  "origin_account": {
    "handle": "@crypto_insider",
    "display_name": "Crypto Insider",
    "user_id": "123456789",
    "profile_url": "https://twitter.com/crypto_insider",
    "first_post_url": "https://twitter.com/crypto_insider/status/1234567890",
    "first_post_timestamp": "2025-01-09T08:00:00Z",
    "followers_count": 50000,
    "is_verified": true
  },
  "is_likely_promotion": false,
  "promotion_confidence": 0.15,
  "promotion_rationale": "账号有较高粉丝数和验证标识，内容为新闻分享而非推广",
  "deepsearch_insights": "该消息最早由 @crypto_insider 于 1月9日发布，随后被多个加密媒体账号转发。消息内容与 SEC 文件披露时间吻合，可信度较高。",
  "evidence_posts": [
    {
      "tweet_url": "https://twitter.com/crypto_insider/status/1234567890",
      "author_handle": "@crypto_insider",
      "summary": "首次发布该消息"
    }
  ],
  "raw_model_response": "根据 X 上的数据...",
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**主要字段说明 / Field Descriptions**
- `origin_account`: 消息最初来源账号信息
  - `handle`: 账号 @handle
  - `first_post_url`: 溯源到的最早帖子链接
  - `followers_count`: 粉丝数
  - `is_verified`: 是否为认证账号
- `is_likely_promotion`: 该消息是否可能为推广/营销信息
- `promotion_confidence`: 推广判断置信度（0-1）
- `promotion_rationale`: 判断理由
- `deepsearch_insights`: 基于 Grok deepsearch 的社交分析
- `evidence_posts`: 支持结论的代表性帖子列表
- `raw_model_response`: Grok 的原始文本响应

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化或 XAI API 不可用
- 500: 内部服务错误

**注意事项 / Notes**
- 需要 XAI_API_KEY，且工具必须在 config/tools.yaml 中启用
- 延迟等级：慢速 (slow)

---

### 7. macro_hub - 宏观中心

**描述**: 宏观经济和市场指标：恐惧与贪婪指数、FRED 数据、传统指数（S&P500、纳斯达克、VIX）、大宗商品、经济日历和 CME FedWatch 工具

**端点 / Endpoint**
```
POST /tools/macro_hub
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| mode | string | ✗ | dashboard | 查询模式: dashboard (全部数据), fed (联储数据), indices (市场指数), calendar (财经日历), fear_greed (恐惧贪婪指数), crypto_indices (加密货币指数) |
| country | string | ✗ | US | 国家代码 |
| calendar_days | integer | ✗ | 7 | 财经日历未来天数（用于calendar模式） |
| calendar_min_importance | integer | ✗ | 2 | 财经日历最低重要性 (1-3，用于calendar模式) |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/macro_hub \
  -H "Content-Type: application/json" \
  -d '{
    "include_fields": ["fear_greed", "dxy"]
  }'
```

**响应格式 / Response Format**
```json
{
  "data": {
    "fear_greed": {
      "value": 72,
      "classification": "greed",
      "timestamp": "2025-01-10T12:00:00Z"
    },
    "indices": [
      {
        "name": "S&P 500",
        "symbol": "^GSPC",
        "value": 4750.5,
        "change_24h": 45.2,
        "change_percent": 0.96,
        "timestamp": "2025-01-10T12:00:00Z"
      }
    ],
    "fed": [
      {
        "name": "Federal Funds Rate",
        "symbol": "FEDFUNDS",
        "value": 5.5,
        "date": "2025-01-01",
        "units": "Percent"
      }
    ]
  },
  "source_meta": [
    {
      "provider": "alternative.me",
      "endpoint": "/fng/",
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
- `data.fear_greed`: 恐惧与贪婪指数（0-100）
- `data.indices`: 市场指数数据（S&P500、纳斯达克、VIX 等）
- `data.fed`: 美联储数据（联邦基金利率、下次会议等）
- `data.crypto_indices`: 加密货币指数
- `data.calendar`: 财经日历事件
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- FRED 字段需要 FRED_API_KEY（如果启用）
- 延迟等级：快速 (fast)

---

### 8. sentiment_aggregator - 情绪聚合

**描述**: 来自 Telegram、Twitter/X（Grok）和新闻的多源情绪聚合。返回加权情绪评分、源分解和信号

**端点 / Endpoint**
```
POST /tools/sentiment_aggregator
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| symbol | string | ✓ | - | 代币符号，如 BTC, ETH |
| lookback_hours | integer | ✗ | 24 | 回溯小时数(最多7天，1-168) |
| sources | array[string] | ✗ | ["telegram", "twitter", "news"] | 数据源列表: telegram, twitter, news, reddit |
| include_raw_samples | boolean | ✗ | false | 是否返回原始消息样本 |
| sample_limit | integer | ✗ | 10 | 每个来源的样本数量 (1-50) |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/sentiment_aggregator \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "lookback_hours": 24
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC",
  "analysis_period": {
    "start": "2025-01-09T12:00:00Z",
    "end": "2025-01-10T12:00:00Z"
  },
  "overall_sentiment": {
    "score": 72,
    "label": "bullish",
    "confidence": 85,
    "trend_vs_24h_ago": "improving",
    "trend_vs_7d_ago": "stable"
  },
  "source_breakdown": {
    "telegram": {
      "score": 75,
      "message_count": 1250,
      "positive_count": 820,
      "negative_count": 180,
      "neutral_count": 250,
      "key_topics": ["ETF approval", "price rally", "institutional adoption"]
    },
    "twitter": {
      "score": 70,
      "tweet_count": 3500,
      "positive_count": 2100,
      "negative_count": 600,
      "neutral_count": 800
    },
    "news": {
      "score": 68,
      "article_count": 45,
      "positive_count": 28,
      "negative_count": 8,
      "neutral_count": 9
    }
  },
  "signals": [
    {
      "type": "bullish",
      "strength": 8,
      "source": "telegram",
      "reason": "ETF 批准消息在社区引发强烈看涨情绪"
    }
  ],
  "historical_sentiment": [
    {
      "timestamp": "2025-01-10T00:00:00Z",
      "score": 68
    },
    {
      "timestamp": "2025-01-10T12:00:00Z",
      "score": 72
    }
  ],
  "source_meta": [
    {
      "provider": "telegram_scraper",
      "endpoint": "/search",
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
- `overall_sentiment`: 综合情绪评分
  - `score`: 情绪评分 0-100（50=中性）
  - `label`: 情绪标签（very_bearish, bearish, neutral, bullish, very_bullish）
  - `confidence`: 置信度 0-100
  - `trend_vs_24h_ago`: 相对 24h 前的趋势
- `source_breakdown`: 各数据源的情绪分解
- `signals`: 情绪信号列表
- `historical_sentiment`: 历史情绪趋势
- `raw_samples`: 原始消息样本（如果请求）
- `source_meta`: 数据来源元信息
- `warnings`: 警告信息列表

**错误响应 / Error Responses**
- 422: 参数验证错误
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 需要 TELEGRAM_SCRAPER_URL 和 XAI_API_KEY 以获得完整覆盖
- 延迟等级：慢速 (slow)

---

### 9. draw_chart - 图表绘制

**描述**: 基于客户端提供的配置使用 Plotly 进行图表可视化：K线图、折线图、面积图、柱状图、散点图。不自行获取市场数据；调用者必须提供准备好的图表配置

**端点 / Endpoint**
```
POST /tools/draw_chart
```

**请求参数 / Request Parameters**

| 参数 / Parameter | 类型 / Type | 必选 / Required | 默认值 / Default | 说明 / Description |
|-----------------|------------|----------------|-----------------|-------------------|
| chart_type | string | ✓ | - | 图表类型: candlestick (K线图), line (折线图), bar (柱状图), area (面积图), scatter (散点图) 等 |
| symbol | string | ✓ | - | 资产或交易对符号，如 BTC/USDT、ETH 等 |
| title | string | ✗ | null | 图表标题（可选，用于前端展示） |
| timeframe | string | ✗ | null | 时间框架: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1y 等（可选，仅用于说明） |
| indicators | array[string] | ✗ | [] | 图表中包含的技术指标标识列表，如 MA20, MA50, MA200, RSI 等（仅用于记录） |
| config | object | ✓ | - | 完整的 Plotly 图表配置（包含 data 与 layout），由调用方根据 K 线或其他数据生成 |

**请求示例 / Request Example**
```bash
curl -X POST http://localhost:8001/tools/draw_chart \
  -H "Content-Type: application/json" \
  -d '{
    "chart_type": "line",
    "symbol": "BTC/USDT",
    "title": "BTC Price",
    "config": {
      "data": [
        {
          "x": ["2025-01-01", "2025-01-02", "2025-01-03"],
          "y": [93000, 94000, 95000],
          "type": "scatter",
          "mode": "lines",
          "name": "BTC Price"
        }
      ],
      "layout": {
        "title": "BTC Price Chart",
        "xaxis": {"title": "Date"},
        "yaxis": {"title": "Price (USD)"}
      }
    }
  }'
```

**响应格式 / Response Format**
```json
{
  "symbol": "BTC/USDT",
  "chart_type": "line",
  "chart": {
    "chart_config": {
      "data": [
        {
          "x": ["2025-01-01", "2025-01-02", "2025-01-03"],
          "y": [93000, 94000, 95000],
          "type": "scatter",
          "mode": "lines",
          "name": "BTC Price"
        }
      ],
      "layout": {
        "title": "BTC Price Chart",
        "xaxis": {"title": "Date"},
        "yaxis": {"title": "Price (USD)"}
      }
    },
    "data_points": 3,
    "warnings": []
  },
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**主要字段说明 / Field Descriptions**
- `chart.chart_config`: 完整的 Plotly 图表配置
- `chart.data_points`: 数据点数量
- `chart.warnings`: 警告信息列表
- `as_of_utc`: 数据时间戳

**错误响应 / Error Responses**
- 422: 参数验证错误（配置格式错误）
- 503: 工具未初始化
- 500: 内部服务错误

**注意事项 / Notes**
- 不会获取数据；输入配置必须包含系列数据
- 延迟等级：快速 (fast)

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
  "detail": "Tool 'crypto_news_search' is not initialized or disabled"
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
  "endpoint": "/api/v3/ticker/24hr",
  "as_of_utc": "2025-01-10T12:00:00Z",
  "ttl_seconds": 10,
  "version": "v3",
  "degraded": false,
  "fallback_used": null,
  "response_time_ms": 123.5
}
```

字段说明：
- `provider`: 数据提供者（如 binance, coingecko）
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
4. **并发请求**: 核心工具支持并发调用，但请注意 API 速率限制
5. **时间戳**: 所有时间戳均为 UTC ISO 8601 格式
6. **参数验证**: 利用 422 错误响应进行客户端验证
