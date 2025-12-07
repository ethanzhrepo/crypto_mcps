# MCP Server - Crypto + Macro Tools v3

A unified MCP server for crypto finance and macroeconomic data, providing 7 core tools plus a comprehensive onchain analytics suite.

## 📋 Features

### ✅ Implemented Tools

**Core Tools:**
- `crypto_overview` - Comprehensive token overview (fundamentals, market metrics, supply, holders, social, sectors, dev activity)
- `market_microstructure` - Market data & microstructure analysis
- `derivatives_hub` - Unified derivatives data access
- `web_research_search` - Web & research search (news, reports, parallel multi-source queries)
- `macro_hub` - Macro indicators, Fed data, indices & dashboards
- `draw_chart` - Chart visualization (Plotly-based)

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
- Additional keys for onchain tools as needed

### Running the Server

```bash
cd docker

# Start production MCP HTTP server
make start

# Server will be available at:
# - MCP HTTP: http://localhost:8000
# - Health: http://localhost:8000/health
# - Tools: http://localhost:8000/tools
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
curl http://localhost:8000/health

# List available tools
curl http://localhost:8000/tools
```

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

### docker/.env
Environment variables and API key configuration.

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

## 🤝 Contributing

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architectural details.

## 📄 License

See LICENSE file for details.

## 🔗 Documentation

- [Tool Specifications v3](docs/crypto-macro-mcp-tools-v3.md)
- [Data Sources Plan v3](docs/crypto-data-sources-plan-v3.md)
- [Architecture Design](docs/ARCHITECTURE.md)

## 🐳 Docker Services

**Production Environment:**
- MCP HTTP Server: `http://localhost:8000`
- Redis: `localhost:6379`

**Test Environment:**
- Separate isolated containers for testing
- Automatic cleanup with `make clean`
