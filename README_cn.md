# MCP Server - 加密货币 + 宏观工具 v3

一个统一的 MCP Server，用于加密金融与宏观经济数据，提供 8 个核心工具以及完整的链上分析工具套件。

## 📋 功能特性

### ✅ 已实现工具

**核心工具：**
- `crypto_overview` - 代币全景概览（基本面、市场指标、供应、持币地址、社媒、赛道、开发活跃度）
- `market_microstructure` - 市场数据与微观结构分析
- `derivatives_hub` - 统一的衍生品数据访问入口
- `crypto_news_search` - 加密新闻搜索
- `web_research_search` - Web 与研究搜索（新闻、研报、多来源并行查询）
- `grok_social_trace` - 通过 Grok 对 X/Twitter 的社交传播溯源（源头账号、推广可能性、基于 deepsearch 的解释）
- `macro_hub` - 宏观指标、Fed 数据、指数与看板
- `sentiment_aggregator` - 多源情绪聚合（Telegram、Twitter/X、新闻综合分析）
- `draw_chart` - 图表可视化（基于 Plotly）

**市场扩展工具：**
- `price_history` - 历史K线与技术指标（SMA、EMA、RSI、MACD、布林带、ATR）及统计分析
- `sector_peers` - 赛道对比分析（同类代币市场指标、TVL、费用、估值对比）
- `etf_flows_holdings` - ETF 资金流与持仓快照（免费优先来源）
- `cex_netflow_reserves` - CEX 储备与大额转账监控
- `lending_liquidation_risk` - 借贷收益与清算风险
- `stablecoin_health` - 稳定币供应与链分布
- `options_vol_skew` - 期权波动率/偏度快照（Deribit/OKX/Binance）
- `blockspace_mev` - MEV-Boost 与 gas oracle 统计
- `hyperliquid_market` - Hyperliquid 市场数据（资金费率/OI/盘口/成交）

**链上分析工具套件：**
- `onchain_tvl_fees` - 协议 TVL 与费用/收入（DefiLlama）
- `onchain_stablecoins_cex` - 稳定币指标 + CEX 储备（DefiLlama）
- `onchain_bridge_volumes` - 跨链桥成交量（24h/7d/30d，DefiLlama）
- `onchain_dex_liquidity` - Uniswap v3 流动性与池子/Tick 分布（The Graph）
- `onchain_governance` - 治理提案（Snapshot + Tally）
- `onchain_whale_transfers` - 大额转账监控（Whale Alert）
- `onchain_token_unlocks` - 代币解锁时间表
- `onchain_activity` - 链上活跃度指标（Etherscan）
- `onchain_contract_risk` - 合约风险分析（GoPlus / Slither）
- `onchain_analytics` - CryptoQuant 链上分析（MVRV、SOPR、活跃地址、交易所流量、矿工数据、资金费率）

> 原 `onchain_hub` 已弃用，并由以上更细粒度的 `onchain_*` 工具替代。

## 📚 API 文档

详细的 HTTP API 文档按工具类别组织：

- [核心工具 API](docs/core_tools_api.zh.md) - 9 个核心工具的详细 API 参考
- [市场扩展工具 API](docs/market_tools_api.zh.md) - 9 个市场分析工具的详细 API 参考
- [链上分析工具 API](docs/onchain_tools_api.zh.md) - 10 个链上工具的详细 API 参考

每个文档包含：
- API 端点定义
- 请求参数详细说明
- 响应格式与示例
- 字段说明与数据解释
- 错误处理
- 使用注意事项

## 🏗️ 架构

- **统一的 DataSourceRegistry**：可配置的回退链（fallback chain），并支持自动降级
- **智能缓存**：基于 Redis 的缓存，支持字段级 TTL 策略
- **冲突检测**：跨数据源校验，支持基于阈值的共识策略
- **全链路可追溯**：完整的 SourceMeta 记录（provider、endpoint、timestamp、TTL）
- **Async 优先**：全异步设计，适配高并发场景

## 🚀 快速开始

### 先决条件

- Docker 与 Docker Compose
- API Keys（见下方「配置」）

### 安装

1. **克隆仓库**
```bash
git clone <repository-url>
cd crypto_mcps
```

2. **配置环境变量**
```bash
# 复制环境变量模板
cp docker/.env.example docker/.env

# 编辑 .env 并填入你的 API keys
vim docker/.env
```

3. **配置 API Keys**

编辑 `docker/.env`，至少添加：

- `COINGECKO_API_KEY`（免费档可选）
- `COINMARKETCAP_API_KEY`（提供免费档）
- `ETHERSCAN_API_KEY`（用于持币地址/holder 数据）
- `GITHUB_TOKEN`（用于开发活跃度，可选）
- `TELEGRAM_SCRAPER_URL`（用于 `crypto_news_search`，可选）
- 链上工具按需添加更多 keys

### 运行服务

```bash
cd docker

# 启动生产环境 MCP HTTP 服务
make start

# 服务地址：
# - MCP HTTP: http://localhost:8001
# - Health: http://localhost:8001/health
# - Tools: http://localhost:8001/tools
```

**其他命令：**
```bash
make stop      # 停止服务
make restart   # 重启服务
make logs      # 查看服务日志
```

### 验证

```bash
# 健康检查
curl http://localhost:8001/health

# 列出可用工具（轻量）
curl http://localhost:8001/tools

# 获取可执行的工具注册表（schemas、examples、capabilities、freshness）
curl http://localhost:8001/tools/registry

# 获取单个工具定义（GET）。对同一路径使用 POST 可执行该工具。
curl http://localhost:8001/tools/crypto_overview
```

## 🔌 HTTP 工具注册表 APIs

HTTP Server 提供动态的工具元数据，用于 LLM/Agent 编排。
所有 registry 端点只会返回 **由 `config/tools.yaml` 启用** 的工具。

### `GET /tools/registry`

返回所有已启用工具的可执行注册表，包括：
- `input_schema`：来自 Pydantic 输入模型的 JSON Schema
- `output_schema`：来自 Pydantic 输出模型的 JSON Schema
- `examples`：规范的调用样例与参数模式
- `capabilities`：用于规划的语义标签
- `freshness`：TTL 提示与 `as_of_utc` 语义
- `limitations` / `cost_hints`：provider/key/延迟等说明

### `GET /tools/{name}`

返回单个工具的 registry 条目。  
示例：
```bash
curl http://localhost:8001/tools/derivatives_hub
```

### `GET /tools`

用于发现的轻量列表（仅 `name/description/endpoint`）。

## 🧪 测试

### 运行测试

```bash
cd docker

# 构建测试容器
make build

# 运行全部测试（单元 + 集成）
make test

# 运行指定测试集
make test-unit         # 仅单元测试
make test-integration  # 仅集成测试
make test-live-free    # 使用免费 API 的在线测试（无需 keys）
make test-live         # 使用真实 API keys 的在线测试

# 带覆盖率运行测试
make test-cov

# 重新运行失败用例
make test-failed

# 按模式匹配运行测试
make test-pattern PATTERN=crypto
```

### 测试辅助工具

```bash
# 查看测试日志
make logs

# 进入测试容器 Shell
make shell

# 连接测试 Redis
make redis-cli

# 清理测试容器
make clean
```

## 📁 项目结构

```
crypto_mcps/
├── src/
│   ├── server/              # MCP server 实现
│   ├── core/                # 核心抽象（基类、Registry、Models）
│   ├── tools/               # MCP 工具实现
│   ├── data_sources/        # 数据源适配器
│   ├── middleware/          # 缓存、限流、熔断
│   └── utils/               # 工具函数
├── config/                  # 配置文件（TTL 策略、数据源）
├── tests/                   # 测试套件
├── docker/                  # Docker 配置与 Makefile
│   ├── Dockerfile
│   ├── docker-compose.yml       # 生产环境
│   ├── docker-compose.test.yml  # 测试环境
│   ├── Makefile
│   └── .env                 # 环境变量（由 .env.example 生成）
└── scripts/                 # 辅助脚本
```

## 📚 配置

### `config/ttl_policies.yaml`
为每个工具定义字段级缓存 TTL 策略。

### `config/data_sources.yaml`
定义数据源优先级、回退链与冲突阈值。

### `config/tools.yaml`
定义 MCP Server 的工具开关（启用/禁用）。

- 格式：
  ```yaml
  crypto_overview:
    enabled: true
  market_microstructure:
    enabled: true
  # ...
  grok_social_trace:
    enabled: false
  ```
- 如果 `config/tools.yaml` 缺失或某工具未列出，则该工具默认视为 **启用**。
- 新增的 `grok_social_trace` 工具默认 **禁用**，需要显式启用：
  ```yaml
  grok_social_trace:
    enabled: true
  ```

### `docker/.env`
环境变量与 API Key 配置。

- 对于 `grok_social_trace`，需要配置 XAI API Key：
  - 在环境变量或 `docker/.env` 中设置 `XAI_API_KEY=...`
  - stdio 与 HTTP server 都使用该环境变量
- 对于 `crypto_news_search`，需要配置 Telegram Scraper URL：
  - 在环境变量或 `docker/.env` 中设置 `TELEGRAM_SCRAPER_URL=...`
  - 指向可访问的加密新闻搜索后端

## 🔧 工具使用示例

### `crypto_overview`

**请求：**
```json
{
  "tool": "crypto_overview",
  "arguments": {
    "symbol": "BTC",
    "include_fields": ["basic", "market", "supply", "holders"]
  }
}
```

**响应：**
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

详见 `LICENSE`。

## 🐳 Docker 服务

**生产环境：**
- MCP HTTP Server: `http://localhost:8001`
- Redis: `localhost:6380`

**测试环境：**
- 为测试提供独立隔离的容器
- 通过 `make clean` 自动清理
