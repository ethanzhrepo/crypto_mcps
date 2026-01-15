# MCP Server - Crypto + Macro Tools v3

A unified MCP server for crypto finance and macroeconomic data, providing 8 core tools plus a comprehensive onchain analytics suite.

## 📋 Features

### ✅ Implemented Tools

**Core Tools:**
- `crypto_overview` - Comprehensive token overview (fundamentals, market metrics, supply, holders, social, sectors, dev activity)
- `market_microstructure` - Market data & microstructure analysis
- `derivatives_hub` - Unified derivatives data access
- `crypto_news_search` - Crypto news search
- `web_research_search` - Web & research search (news, reports, parallel multi-source queries)
- `grok_social_trace` - X/Twitter social media origin tracing via Grok (origin account, promotion likelihood, deepsearch-based interpretation)
- `macro_hub` - Macro indicators, Fed data, indices & dashboards
- `sentiment_aggregator` - Multi-source sentiment aggregation (Telegram, Twitter/Grok, News)
- `draw_chart` - Chart visualization (Plotly-based)

**Market Extensions:**
- `etf_flows_holdings` - ETF flows and holdings snapshots (free-first sources)
- `cex_netflow_reserves` - CEX reserves with optional whale transfer monitoring
- `lending_liquidation_risk` - Lending yields with optional liquidation data
- `stablecoin_health` - Stablecoin supply and chain distribution
- `options_vol_skew` - Options volatility/skew snapshots (Deribit/OKX/Binance)
- `blockspace_mev` - MEV-Boost and gas oracle stats
- `hyperliquid_market` - Hyperliquid market data (funding, OI, orderbook, trades)
- `price_history` - Historical K-line data with indicators and support/resistance
- `sector_peers` - Sector comparison with market metrics and TVL

**Onchain Analytics Suite:**
- `onchain_tvl_fees` - Protocol TVL & fees/revenue (DefiLlama)
- `onchain_stablecoins_cex` - Stablecoin metrics + CEX reserves (DefiLlama)
- `onchain_bridge_volumes` - Cross-chain bridge volumes (24h/7d/30d, DefiLlama)
- `onchain_dex_liquidity` - Uniswap v3 liquidity & pool/tick distribution (The Graph)
- `onchain_governance` - Governance proposals (Snapshot + Tally)
- `onchain_whale_transfers` - Large transfer monitoring (Whale Alert)
- `onchain_token_unlocks` - Token unlock schedules
- `onchain_activity` - Onchain activity metrics (Etherscan)
- `onchain_contract_risk` - Contract risk analysis (GoPlus / Slither)
- `onchain_analytics` - **NEW** On-chain analytics (CryptoQuant): MVRV, SOPR, active addresses, exchange flows, miner data, funding rates

> The original `onchain_hub` has been deprecated and replaced by the granular `onchain_*` tools above.

## 🏗️ Architecture

- **Unified DataSourceRegistry**: Configurable fallback chains with automatic degradation
- **Smart Caching**: Redis-backed caching with field-level TTL policies
- **Conflict Detection**: Cross-source validation with threshold-based consensus
- **Full Traceability**: Complete SourceMeta records (provider, endpoint, timestamp, TTL)
- **Async-First**: Fully async design for high-concurrency performance

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- API keys (see Configuration below)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd crypto_mcps
```

2. **Configure environment**
```bash
# Copy environment template
cp docker/.env.example docker/.env

# Edit .env and add your API keys
vim docker/.env
```

3. **Configure API Keys**

Edit `docker/.env` and add at least:

- `COINGECKO_API_KEY` (optional for free tier)
- `COINMARKETCAP_API_KEY` (free tier available)
- `ETHERSCAN_API_KEY` (for holder data)
- `GITHUB_TOKEN` (for dev activity, optional)
- `TELEGRAM_SCRAPER_URL` (for crypto_news_search tool, optional)
- Additional keys for onchain tools as needed

### Running the Server

```bash
cd docker

# Start production MCP HTTP server
make start

# Server will be available at:
# - MCP HTTP: http://localhost:8001
# - Health: http://localhost:8001/health
# - Tools: http://localhost:8001/tools
```

**Other Commands:**
```bash
make stop      # Stop the server
make restart   # Restart the server
make logs      # View server logs
```

### Verification

```bash
# Check health
curl http://localhost:8001/health

# List available tools (lightweight)
curl http://localhost:8001/tools

# Get executable tool registry (schemas, examples, capabilities, freshness)
curl http://localhost:8001/tools/registry

# Get a single tool definition (GET). Use POST on the same path to execute the tool.
curl http://localhost:8001/tools/crypto_overview
```

## 🔌 HTTP Tool Registry APIs

The HTTP server exposes dynamic tool metadata for LLM/agent orchestration.
All registry endpoints only return tools that are **enabled by `config/tools.yaml`**.

### `GET /tools/registry`

Returns an executable registry for all enabled tools, including:
- `input_schema`: JSON Schema from Pydantic input model.
- `output_schema`: JSON Schema from Pydantic output model.
- `examples`: canonical calls and argument patterns.
- `capabilities`: semantic tags for planning.
- `freshness`: TTL hints and `as_of_utc` semantics.
- `limitations` / `cost_hints`: provider/key/latency notes.

### `GET /tools/{name}`

Returns a single tool registry entry.  
Example:
```bash
curl http://localhost:8001/tools/derivatives_hub
```

### `GET /tools`

Lightweight list for discovery (`name/description/endpoint` only).

## 🧪 Testing

### Run Tests

```bash
cd docker

# Build test containers
make build

# Run all tests (unit + integration)
make test

# Run specific test suites
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-live-free    # Live tests with free APIs (no keys required)
make test-live         # Live tests with real API keys

# Run tests with coverage
make test-cov

# Re-run failed tests
make test-failed

# Run tests matching a pattern
make test-pattern PATTERN=crypto
```

### Test Utilities

```bash
# View test logs
make logs

# Open shell in test container
make shell

# Connect to test Redis
make redis-cli

# Clean up test containers
make clean
```

## 📁 Project Structure

```
crypto_mcps/
├── src/
│   ├── server/              # MCP server implementation
│   ├── core/                # Core abstractions (base classes, Registry, Models)
│   ├── tools/               # MCP tool implementations
│   ├── data_sources/        # Data source adapters
│   ├── middleware/          # Caching, rate limiting, circuit breakers
│   └── utils/               # Utility functions
├── config/                  # Configuration files (TTL policies, data sources)
├── tests/                   # Test suite
├── docker/                  # Docker configuration & Makefile
│   ├── Dockerfile
│   ├── docker-compose.yml       # Production
│   ├── docker-compose.test.yml  # Testing
│   ├── Makefile
│   └── .env                 # Environment variables (create from .env.example)
└── scripts/                 # Helper scripts
```

## 📚 Configuration

### config/ttl_policies.yaml
Defines field-level cache TTL policies for each tool.

### config/data_sources.yaml
Defines data source priorities, fallback chains, and conflict thresholds.

### config/tools.yaml
Defines per-tool enable/disable switches for the MCP server.

- Format:
  ```yaml
  crypto_overview:
    enabled: true
  market_microstructure:
    enabled: true
  # ...
  grok_social_trace:
    enabled: false
  ```
- If `config/tools.yaml` is missing or a tool is not listed, that tool is treated as **enabled by default**.
- The new `grok_social_trace` tool is **disabled by default** and must be explicitly enabled by setting:
  ```yaml
  grok_social_trace:
    enabled: true
  ```

### docker/.env
Environment variables and API key configuration.

- For the `grok_social_trace` tool, you must configure the XAI API key:
  - Set `XAI_API_KEY=...` in your environment or `docker/.env` file
  - Both stdio and HTTP servers use this environment variable
- For the `crypto_news_search` tool, you must configure the Telegram Scraper URL:
  - Set `TELEGRAM_SCRAPER_URL=...` in your environment or `docker/.env` file
  - Points to a reachable crypto news search backend

## 🔧 Tool Usage Example

### crypto_overview

**Request:**
```json
{
  "tool": "crypto_overview",
  "arguments": {
    "symbol": "BTC",
    "include_fields": ["basic", "market", "supply", "holders"]
  }
}
```

**Response:**
```json
{
  "symbol": "BTC",
  "data": {
    "basic": {...},
    "market": {...},
    "supply": {...},
    "holders": {...}
  },
  "source_meta": [
    {
      "provider": "coingecko",
      "endpoint": "/coins/bitcoin",
      "as_of_utc": "2025-12-06T12:00:00Z",
      "ttl_seconds": 60,
      "degraded": false
    }
  ],
  "conflicts": [],
  "warnings": []
}
```

## 📄 License

See LICENSE file for details.

## 🐳 Docker Services

**Production Environment:**
- MCP HTTP Server: `http://localhost:8001`
- Redis: `localhost:6380`

**Test Environment:**
- Separate isolated containers for testing
- Automatic cleanup with `make clean`
