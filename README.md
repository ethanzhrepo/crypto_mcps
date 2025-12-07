# MCP Server - Crypto + Macro Tools v3

加密金融与宏观经济MCP工具服务器，提供7个域中心工具 + 一组链上专用工具的统一数据接入层。

## 📋 功能概览

### ✅ 已实现
- `crypto_overview` - 代币一站式概览（基础资料、市场指标、供应、持有者、社交、板块、开发活跃度）
- `market_microstructure` - 行情与微结构
- `derivatives_hub` - 衍生品统一入口
- `web_research_search` - Web/研报检索（包含新闻搜索，支持并行多数据源）
- `macro_hub` - 宏观/Fed/指数/仪表盘
- `draw_chart` - 图表可视化（基于客户端提供的 Plotly 配置）
- 链上工具家族 `onchain_*`（拆分自原 `onchain_hub`）：
  - `onchain_tvl_fees` - 协议 TVL 与费用/收入（DefiLlama）
  - `onchain_stablecoins_cex` - 稳定币指标 + CEX 储备（DefiLlama）
  - `onchain_bridge_volumes` - 跨链桥 24h/7d/30d 交易量（DefiLlama）
  - `onchain_dex_liquidity` - Uniswap v3 流动性与池子/Tick 分布（The Graph）
  - `onchain_governance` - Snapshot + Tally 治理提案
  - `onchain_whale_transfers` - Whale Alert 大额转账监控
  - `onchain_token_unlocks` - Token Unlocks 解锁计划
  - `onchain_activity` - Etherscan 链上活跃度指标
  - `onchain_contract_risk` - GoPlus / Slither 合约风险分析

> 原 `onchain_hub`（链上+治理+协议）已正式废弃，由上述更细粒度的 `onchain_*` 工具替代。

## 🏗️ 架构特性

- **统一DataSourceRegistry**: 可配置的fallback链，自动降级
- **智能缓存**: Redis缓存 + 字段级TTL策略
- **冲突检测**: 多数据源交叉验证，阈值共识策略
- **可追溯**: 完整的SourceMeta记录（来源、端点、时间戳、TTL）
- **异步优先**: 全异步设计，高并发性能

## 🚀 快速开始

### 1. 环境要求

- Python 3.11+
- Redis 7.0+
- Poetry 1.7+

### 2. 安装

```bash
# 克隆项目
cd hubrium_mcp/mcp_server

# 安装依赖
poetry install

# 复制环境变量模板
cp .env.example .env

# 编辑.env，填入API密钥
vim .env
```

### 3. 配置API密钥

编辑 `.env` 文件，至少需要：

- `COINGECKO_API_KEY` (可选，免费版无需密钥)
- `COINMARKETCAP_API_KEY` (注册免费账号获取)
- `ETHERSCAN_API_KEY` (用于持有者数据)
- `GITHUB_TOKEN` (用于开发活跃度，可选)

### 4. 启动Redis

```bash
# Docker方式
docker run -d -p 6379:6379 redis:7-alpine

# 或使用本地Redis
redis-server
```

### 5. 运行服务器

```bash
# 开发模式
poetry run python -m src.server.app

# 或使用脚本（如果已实现）
poetry run mcp-server
```

## 🧪 开发

### 运行测试

```bash
# 所有测试
poetry run pytest

# 仅单元测试
poetry run pytest -m unit

# 仅集成测试
poetry run pytest -m integration

# 带覆盖率
poetry run pytest --cov=src --cov-report=html
```

### 代码格式化

```bash
# 格式化代码
poetry run black src/ tests/

# 检查代码质量
poetry run ruff check src/ tests/

# 类型检查
poetry run mypy src/
```

### 添加依赖

```bash
# 生产依赖
poetry add <package>

# 开发依赖
poetry add --group dev <package>
```

## 📁 项目结构

```
mcp_server/
├── src/
│   ├── server/              # MCP服务器主程序
│   ├── core/                # 核心抽象（基类、Registry、Models）
│   ├── tools/               # 8个MCP工具实现
│   ├── data_sources/        # 数据源适配器
│   ├── middleware/          # 缓存、限流、降级
│   └── utils/               # 工具函数
├── config/                  # 配置文件（TTL策略、数据源优先级）
├── tests/                   # 测试套件
└── scripts/                 # 辅助脚本
```

## 📚 配置文件说明

### config/ttl_policies.yaml
定义每个工具的字段级缓存TTL策略。

### config/data_sources.yaml
定义数据源优先级、fallback链和冲突阈值。

### .env
环境变量和API密钥配置。

## 🔧 工具使用示例

### crypto_overview

```python
# MCP调用示例
{
  "tool": "crypto_overview",
  "arguments": {
    "symbol": "BTC",
    "include_fields": ["basic", "market", "supply", "holders"]
  }
}
```

返回：
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
      "as_of_utc": "2025-11-18T12:00:00Z",
      "ttl_seconds": 60,
      "degraded": false
    }
  ],
  "conflicts": [],
  "warnings": []
}
```

## 🤝 贡献

详见根目录 [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)

## 📄 许可

详见根目录 LICENSE 文件

## 🔗 相关链接

- [工具规范v3](../docs/crypto-macro-mcp-tools-v3.md)
- [数据源计划v3](../docs/crypto-data-sources-plan-v3.md)
- [架构设计](../docs/ARCHITECTURE.md)
