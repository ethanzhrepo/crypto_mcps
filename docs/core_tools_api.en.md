# Core Tools API Documentation

## Overview

Core tools provide fundamental data query capabilities for cryptocurrency markets, including token information, market data, derivatives, macro indicators, social media analysis, and more.

## General Information

- **Base URL**: `http://localhost:8001`
- **All Tool Endpoints**: `POST /tools/{tool_name}`
- **Request Format**: `Content-Type: application/json`
- **Response Format**: JSON

All responses include the following common fields:
- `source_meta`: Array of data source metadata
- `warnings`: Array of warning messages
- `as_of_utc`: Data timestamp (ISO 8601)

## Tool List

### 1. crypto_overview - Token Overview

**Description**: Comprehensive token overview including basic profile, market metrics, supply structure, holder concentration, social links, sector classification, and developer activity

**Endpoint**
```
POST /tools/crypto_overview
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Token symbol, e.g., BTC, ETH, ARB |
| token_address | string | ✗ | null | Contract address (optional, for disambiguation) |
| chain | string | ✗ | null | Chain name, e.g., ethereum, bsc, arbitrum |
| vs_currency | string | ✗ | usd | Quote currency |
| include_fields | array[string] | ✗ | ["all"] | Fields to include: basic, market, supply, holders, social, sector, dev_activity, all |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/crypto_overview \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "include_fields": ["basic", "market", "supply"]
  }'
```

**Response Format**
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

**Field Descriptions**
- `data.basic`: Basic information including ID, name, description, homepage, etc.
- `data.market`: Market metrics including price, market cap, volume, etc.
- `data.supply`: Supply information including circulating, total, and max supply
- `data.holders`: Holder concentration info (requires ETHERSCAN_API_KEY)
- `data.social`: Social media statistics (Twitter, Reddit, Telegram, etc.)
- `data.sector`: Sector classification information
- `data.dev_activity`: Developer activity (requires GITHUB_TOKEN)
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- Some fields require API keys: COINMARKETCAP_API_KEY (market ranking), ETHERSCAN_API_KEY (holders), GITHUB_TOKEN (dev activity)
- Latency class: medium

---

### 2. market_microstructure - Market Microstructure

**Description**: Real-time market microstructure data

**Endpoint**
```
POST /tools/market_microstructure
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Trading pair symbol, e.g., BTC/USDT, ETH/USDT |
| venues | array[string] | ✗ | ["binance"] | Exchange list, e.g., ['binance', 'okx'], supports multi-venue aggregation |
| include_fields | array[string] | ✗ | ["ticker", "orderbook"] | Fields to return: ticker, klines, trades, orderbook, aggregated_orderbook, volume_profile, taker_flow, slippage, venue_specs, sector_stats, all |
| kline_interval | string | ✗ | 1h | Kline period: 1m, 5m, 15m, 1h, 4h, 1d |
| kline_limit | integer | ✗ | 100 | Number of klines |
| orderbook_depth | integer | ✗ | 100 | Orderbook depth (recommend >=100; too small will distort depth/slippage analysis) |
| trades_limit | integer | ✗ | 100 | Number of trade records |
| slippage_size_usd | float | ✗ | 10000 | Order size in USD for slippage estimation |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/market_microstructure \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "venues": ["binance"],
    "include_fields": ["ticker"]
  }'
```

**Response Format**
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

**Field Descriptions**
- `data.ticker`: Real-time market data including price, spread, 24h volume, etc.
- `data.klines`: Array of kline data
- `data.trades`: Recent trade records
- `data.orderbook`: Orderbook data including bid/ask depth
- `data.aggregated_orderbook`: Multi-venue aggregated orderbook
- `data.volume_profile`: Volume-price distribution
- `data.taker_flow`: Taker buy/sell flow analysis
- `data.slippage`: Slippage estimation
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- No special API keys required
- Latency class: fast

---

### 3. derivatives_hub - Derivatives Hub

**Description**: Derivatives data hub: funding rate, open interest, liquidations, long/short ratio, borrow rates, basis curve, term structure, options surface, and options metrics

**Endpoint**
```
POST /tools/derivatives_hub
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Trading pair symbol, e.g., BTC/USDT, ETH/USDT |
| include_fields | array[string] | ✗ | ["funding_rate", "open_interest"] | Fields to return: funding_rate, open_interest, liquidations, long_short_ratio, basis_curve, term_structure, options_surface, options_metrics, borrow_rates, all |
| lookback_hours | integer | ✗ | 24 | Lookback hours for liquidation data |
| options_expiry | string | ✗ | null | Options expiry date, format: YYMMDD |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/derivatives_hub \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "include_fields": ["funding_rate", "open_interest"]
  }'
```

**Response Format**
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

**Field Descriptions**
- `data.funding_rate`: Funding rate data including current rate, annualized rate, next funding time
- `data.open_interest`: Open interest data including total amount and 24h change
- `data.liquidations`: Liquidation statistics including long/short liquidation events
- `data.long_short_ratio`: Long/short ratio data
- `data.basis_curve`: Basis curve (spot vs futures price difference)
- `data.term_structure`: Term structure
- `data.options_surface`: Options volatility surface
- `data.options_metrics`: Options market metrics
- `data.borrow_rates`: Lending rates
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- No special API keys required
- Latency class: medium

---

### 4. telegram_search - Telegram Search

**Description**: Search Telegram messages (Elasticsearch-backed) via Telegram Scraper

**Endpoint**
```
POST /tools/telegram_search
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | ✗ | null | Search keyword (optional) |
| symbol | string | ✗ | null | Token symbol (optional), e.g., BTC, ETH |
| limit | integer | ✗ | 20 | Number of results |
| sort_by | string | ✗ | timestamp | Sort field: timestamp (newest first) or score (relevance first) |
| time_range | string | ✗ | null | Time range filter: past_24h/day, past_week/7d, past_month/30d, past_year, etc. |
| start_time | string | ✗ | null | Start time (ISO format, takes precedence over time_range), e.g., 2025-01-01T00:00:00Z |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/telegram_search \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "limit": 20,
    "time_range": "24h"
  }'
```

**Response Format**
```json
{
  "query": null,
  "symbol": "BTC",
  "results": [
    {
      "title": "BTC breaks 95000",
      "url": "https://t.me/cryptonews/12345",
      "snippet": "Bitcoin breaks $95,000 milestone today...",
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

**Field Descriptions**
- `query`: Search keyword (if provided)
- `symbol`: Token symbol (if provided)
- `results`: Array of search results
  - `title`: Message title
  - `url`: Message link
  - `snippet`: Message snippet
  - `relevance_score`: Relevance score
  - `published_at`: Publication time
- `total_results`: Total number of results
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized or Telegram Scraper unreachable
- 500: Internal service error

**Notes**
- Requires TELEGRAM_SCRAPER_URL pointing to a reachable Telegram Scraper/Elasticsearch proxy
- Latency class: fast

---

### 5. web_research_search - Web Research Search

**Description**: Multi-source web and news search: Bing News, Brave Search, Kaito crypto news, and DuckDuckGo. Supports parallel search with configurable providers

**Endpoint**
```
POST /tools/web_research_search
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | ✓ | - | Search query |
| scope | string | ✗ | web | Search scope: web (general search), academic (academic papers), news (news articles) |
| providers | array[string] | ✗ | null | Provider list: web scope supports brave, duckduckgo, google, bing, serpapi, kaito; news scope supports bing_news/bing, kaito. Defaults to auto-select available providers |
| time_range | string | ✗ | null | Time range filter: past_24h/day, past_week/7d, past_month/30d, past_year, etc., only valid for scope=news |
| limit | integer | ✗ | 10 | Number of results |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/web_research_search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "BTC spot ETF approval",
    "top_k": 5
  }'
```

**Response Format**
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

**Field Descriptions**
- `query`: Search query
- `results`: Array of search results
  - `title`: Article title
  - `url`: Article link
  - `snippet`: Article snippet
  - `source`: Data source (bing_news, brave, kaito, etc.)
  - `relevance_score`: Relevance score
  - `published_at`: Publication time
- `total_results`: Total number of results
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- Providers may require API keys (see docker/.env)
- Latency class: slow

---

### 6. grok_social_trace - Grok Social Trace

**Description**: Trace the origin of a circulating message on X/Twitter using Grok, assess whether it is likely promotional, and provide deepsearch-based social analysis

**Endpoint**
```
POST /tools/grok_social_trace
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| keyword_prompt | string | ✓ | - | Keyword prompt from LLM for tracing and deepsearch analysis on X/Twitter |
| language | string | ✗ | auto | Preferred language, e.g., zh, en; auto means Grok auto-detects |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/grok_social_trace \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Some rumor text"
  }'
```

**Response Format**
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
  "promotion_rationale": "Account has high follower count and verification badge, content is news sharing rather than promotion",
  "deepsearch_insights": "The message was first posted by @crypto_insider on Jan 9, then retweeted by multiple crypto media accounts. The content timing aligns with SEC filing disclosure, credibility is high.",
  "evidence_posts": [
    {
      "tweet_url": "https://twitter.com/crypto_insider/status/1234567890",
      "author_handle": "@crypto_insider",
      "summary": "First post of this message"
    }
  ],
  "raw_model_response": "According to X data...",
  "as_of_utc": "2025-01-10T12:00:00Z"
}
```

**Field Descriptions**
- `origin_account`: Origin account information
  - `handle`: Account @handle
  - `first_post_url`: Earliest traced post link
  - `followers_count`: Follower count
  - `is_verified`: Whether verified account
- `is_likely_promotion`: Whether message is likely promotional/marketing
- `promotion_confidence`: Promotion confidence (0-1)
- `promotion_rationale`: Reasoning for the judgment
- `deepsearch_insights`: Social analysis based on Grok deepsearch
- `evidence_posts`: Representative posts supporting the conclusion
- `raw_model_response`: Grok's raw text response

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized or XAI API unavailable
- 500: Internal service error

**Notes**
- Requires XAI_API_KEY and tool must be enabled in config/tools.yaml
- Latency class: slow

---

### 7. macro_hub - Macro Hub

**Description**: Macro economic and market indicators: Fear & Greed Index, FRED data, traditional indices (S&P500, NASDAQ, VIX), commodities, economic calendar, and CME FedWatch tool

**Endpoint**
```
POST /tools/macro_hub
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| mode | string | ✗ | dashboard | Query mode: dashboard (all data), fed (Fed data), indices (market indices), calendar (economic calendar), fear_greed (Fear & Greed Index), crypto_indices (crypto indices) |
| country | string | ✗ | US | Country code |
| calendar_days | integer | ✗ | 7 | Economic calendar future days (for calendar mode) |
| calendar_min_importance | integer | ✗ | 2 | Economic calendar minimum importance (1-3, for calendar mode) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/macro_hub \
  -H "Content-Type: application/json" \
  -d '{
    "include_fields": ["fear_greed", "dxy"]
  }'
```

**Response Format**
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

**Field Descriptions**
- `data.fear_greed`: Fear & Greed Index (0-100)
- `data.indices`: Market indices data (S&P500, NASDAQ, VIX, etc.)
- `data.fed`: Federal Reserve data (federal funds rate, next meeting, etc.)
- `data.crypto_indices`: Crypto indices
- `data.calendar`: Economic calendar events
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- FRED fields require FRED_API_KEY when enabled
- Latency class: fast

---

### 8. sentiment_aggregator - Sentiment Aggregator

**Description**: Multi-source sentiment aggregation from Telegram, Twitter/X (Grok), and news. Returns weighted sentiment score, source breakdown, and signals

**Endpoint**
```
POST /tools/sentiment_aggregator
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| symbol | string | ✓ | - | Token symbol, e.g., BTC, ETH |
| lookback_hours | integer | ✗ | 24 | Lookback hours (max 7 days, 1-168) |
| sources | array[string] | ✗ | ["telegram", "twitter", "news"] | Source list: telegram, twitter, news, reddit |
| include_raw_samples | boolean | ✗ | false | Whether to return raw message samples |
| sample_limit | integer | ✗ | 10 | Sample count per source (1-50) |

**Request Example**
```bash
curl -X POST http://localhost:8001/tools/sentiment_aggregator \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "lookback_hours": 24
  }'
```

**Response Format**
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
      "reason": "ETF approval news triggered strong bullish sentiment in community"
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

**Field Descriptions**
- `overall_sentiment`: Overall sentiment score
  - `score`: Sentiment score 0-100 (50=neutral)
  - `label`: Sentiment label (very_bearish, bearish, neutral, bullish, very_bullish)
  - `confidence`: Confidence 0-100
  - `trend_vs_24h_ago`: Trend compared to 24h ago
- `source_breakdown`: Sentiment breakdown by source
- `signals`: Sentiment signals list
- `historical_sentiment`: Historical sentiment trend
- `raw_samples`: Raw message samples (if requested)
- `source_meta`: Data source metadata
- `warnings`: Warning messages list

**Error Responses**
- 422: Parameter validation error
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- Requires TELEGRAM_SCRAPER_URL and XAI_API_KEY for full coverage
- Latency class: slow

---

### 9. draw_chart - Draw Chart

**Description**: Chart visualization with Plotly based on client-provided configs: candlestick, line, area, bar, scatter. Does not fetch market data itself; callers must supply ready-to-render chart config

**Endpoint**
```
POST /tools/draw_chart
```

**Request Parameters**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| chart_type | string | ✓ | - | Chart type: candlestick, line, bar, area, scatter, etc. |
| symbol | string | ✓ | - | Asset or trading pair symbol, e.g., BTC/USDT, ETH |
| title | string | ✗ | null | Chart title (optional, for frontend display) |
| timeframe | string | ✗ | null | Timeframe: 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1y, etc. (optional, for documentation only) |
| indicators | array[string] | ✗ | [] | Technical indicator labels included in chart, e.g., MA20, MA50, MA200, RSI, etc. (for documentation only) |
| config | object | ✓ | - | Complete Plotly chart config (containing data and layout), generated by caller based on kline or other data |

**Request Example**
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

**Response Format**
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

**Field Descriptions**
- `chart.chart_config`: Complete Plotly chart configuration
- `chart.data_points`: Number of data points
- `chart.warnings`: Warning messages list
- `as_of_utc`: Data timestamp

**Error Responses**
- 422: Parameter validation error (config format error)
- 503: Tool not initialized
- 500: Internal service error

**Notes**
- Does not fetch data; input config must contain series
- Latency class: fast

---

## Error Handling

All tools follow a unified error response format:

### 422 Unprocessable Entity
Parameter validation error, returns detailed validation error information.

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
  "detail": "Tool 'telegram_search' is not initialized or disabled"
}
```

### 500 Internal Server Error
Internal service error, returns error message.

```json
{
  "detail": "Internal error: connection timeout"
}
```

## Data Source Metadata

All successful responses include a `source_meta` array providing complete traceability information for data sources:

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

Field descriptions:
- `provider`: Data provider (e.g., binance, coingecko)
- `endpoint`: API endpoint path
- `as_of_utc`: Data acquisition timestamp
- `ttl_seconds`: Cache TTL (seconds)
- `version`: Data contract version
- `degraded`: Whether in degraded mode
- `fallback_used`: Fallback source used (if any)
- `response_time_ms`: Response time (milliseconds)

## Best Practices

1. **Error Handling**: Always check the `warnings` array even if the request succeeds
2. **Caching Strategy**: Cache data reasonably based on `ttl_seconds` in `source_meta`
3. **Degraded Handling**: Check the `degraded` field; data may be incomplete in degraded mode
4. **Concurrent Requests**: Core tools support concurrent calls, but mind API rate limits
5. **Timestamps**: All timestamps are in UTC ISO 8601 format
6. **Parameter Validation**: Leverage 422 error responses for client-side validation
