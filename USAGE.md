# MCP Server 使用指南

## 快速开始

### 1. 环境准备

```bash
# 进入mcp_server目录
cd mcp_server

# 安装依赖
poetry install

# 启动Redis（Docker方式）
docker run -d -p 6379:6379 redis:7-alpine

# 或使用本地Redis
redis-server
```

### 2. 配置API密钥

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件，填入以下密钥（最低要求）：
# - COINMARKETCAP_API_KEY (免费注册)
# - ETHERSCAN_API_KEY (免费注册)
```

### 3. 运行服务器

```bash
# 方式1：使用Poetry运行
poetry run python -m src.server.app

# 方式2：使用开发脚本
poetry run python scripts/dev_server.py

# 方式3：使用Poetry脚本
poetry run mcp-server
```

### 4. 测试

```bash
# 运行所有测试
poetry run pytest

# 只运行单元测试（不需要API key）
poetry run pytest -m unit

# 运行集成测试（需要真实API key）
poetry run pytest -m integration

# 生成覆盖率报告
poetry run pytest --cov=src --cov-report=html
# 查看报告: open htmlcov/index.html
```

---

## crypto_overview工具使用

### 基本用法

通过MCP协议调用`crypto_overview`工具：

```json
{
  "tool": "crypto_overview",
  "arguments": {
    "symbol": "BTC"
  }
}
```

### 完整参数示例

```json
{
  "tool": "crypto_overview",
  "arguments": {
    "symbol": "ETH",
    "chain": "ethereum",
    "token_address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "vs_currency": "usd",
    "include_fields": ["basic", "market", "supply", "holders", "social", "sector", "dev_activity"]
  }
}
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `symbol` | string | ✅ | 代币符号，如 BTC, ETH, UNI |
| `chain` | string | ❌ | 链名称（消歧义用），如 ethereum, bsc, arbitrum |
| `token_address` | string | ❌ | 合约地址（消歧义用） |
| `vs_currency` | string | ❌ | 计价货币，默认 usd |
| `include_fields` | array | ❌ | 包含的字段，默认 ["all"] |

### include_fields选项

- `all` - 所有字段（默认）
- `basic` - 基础信息（名称、描述、官网等）
- `market` - 市场数据（价格、市值、成交量）
- `supply` - 供应信息（流通量、总量、最大供应）
- `holders` - 持有者分布（需要提供chain和token_address）
- `social` - 社交信息（Twitter、Reddit等）
- `sector` - 板块分类
- `dev_activity` - 开发活跃度（需要GitHub仓库）

### 返回数据结构

```json
{
  "symbol": "BTC",
  "data": {
    "basic": {
      "id": "bitcoin",
      "symbol": "BTC",
      "name": "Bitcoin",
      "description": "Bitcoin is a decentralized...",
      "homepage": ["https://bitcoin.org/"],
      "contract_address": null,
      "chain": null
    },
    "market": {
      "price": 95000.0,
      "market_cap": 1850000000000.0,
      "market_cap_rank": 1,
      "total_volume_24h": 45000000000.0,
      "price_change_percentage_24h": 1.06
    },
    "supply": {
      "circulating_supply": 19500000.0,
      "total_supply": 21000000.0,
      "max_supply": 21000000.0,
      "circulating_percent": 92.86
    }
  },
  "source_meta": [
    {
      "provider": "coingecko",
      "endpoint": "/coins/bitcoin",
      "as_of_utc": "2025-11-18T12:00:00Z",
      "ttl_seconds": 60,
      "degraded": false,
      "response_time_ms": 234.5
    }
  ],
  "conflicts": [
    {
      "field": "price",
      "values": {
        "coingecko": 95000,
        "coinmarketcap": 95100
      },
      "diff_percent": 0.105,
      "resolution": "average",
      "final_value": 95050
    }
  ],
  "warnings": [],
  "as_of_utc": "2025-11-18T12:00:00Z"
}
```

---

## 工作原理

### 数据源Fallback链

系统会自动按优先级尝试多个数据源：

1. **basic/market/supply/social/sector**
   - 主源：CoinGecko（免费）
   - 备源：CoinMarketCap（需API key）

2. **holders**
   - 主源：Etherscan/BSCScan等链浏览器（需API key）
   - 限制：最多返回10000持有者

3. **dev_activity**
   - 主源：GitHub API
   - 限制：无token时限流60次/小时，有token时5000次/小时

### 冲突检测与解决

当多个数据源返回不同值时：

- **价格差异 ≤ 0.5%** → 取平均值
- **价格差异 > 0.5%** → 主源优先（CoinGecko）+ 记录冲突
- 所有冲突都会在`conflicts`字段中详细记录

### 缓存策略

不同字段有不同的TTL：

| 字段 | TTL | 说明 |
|------|-----|------|
| basic | 24小时 | 基础信息变化慢 |
| market | 1分钟 | 价格实时性要求高 |
| supply | 1小时 | 供应量变化较慢 |
| holders | 6小时 | 持有者分布变化慢 |
| social | 24小时 | 社交数据更新频率低 |
| dev_activity | 6小时 | 开发活跃度中等更新频率 |

---

## 常见问题

### Q: 为什么holders字段为空？

**A**: holders字段需要同时提供`chain`和`token_address`参数。例如：

```json
{
  "symbol": "UNI",
  "chain": "ethereum",
  "token_address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
  "include_fields": ["holders"]
}
```

### Q: 为什么dev_activity字段为空？

**A**: dev_activity需要代币有GitHub仓库，且能从basic info的homepage中提取到GitHub URL。大部分主流币种都有。

### Q: 如何处理多链代币（如UNI）？

**A**: 提供`chain`参数明确指定链：

```json
{
  "symbol": "UNI",
  "chain": "ethereum"  // 或 "arbitrum", "polygon"
}
```

不指定时会默认使用主链（通常是Ethereum），并给出警告。

### Q: 如何提高GitHub API限流？

**A**: 在`.env`中配置GitHub Personal Access Token：

```bash
GITHUB_TOKEN=your-github-token
```

有token时限流从60次/小时提升到5000次/小时。

### Q: 为什么有些字段是null？

**A**: 可能原因：
1. 数据源不提供该字段（如CMC不提供24h高低价）
2. 该代币确实无此数据（如新币没有ATH）

---

## 其它工具一览

> 下列工具均通过 MCP `list_tools` 暴露，输入结构对应 `src/core/models.py` 中的 `*Input` 模型，这里只给出简要说明，详细 Prompt 见 `mcp_server/docs/*.zh.prompt.md`（如存在）。

### 市场与衍生品

- `market_microstructure` — 行情与微结构  
  - 功能：Binance/OKX 的 ticker、K 线、逐笔成交、订单簿、成交量分布、主动买卖流、滑点估算、交易规则、板块统计。  
  - 关键参数：`symbol`（必填，如 `BTC/USDT`）、`venues`（默认 `["binance"]`）、`include_fields`（如 `["ticker","orderbook"]`）、`kline_interval`、`kline_limit`、`orderbook_depth`、`trades_limit`、`slippage_size_usd`。

- `derivatives_hub` — 衍生品统一入口  
  - 功能：资金费率、未平仓量、多空比、清算概要（Coinglass）、基差曲线、期限结构、期权曲面与指标（Deribit）、借贷利率（DefiLlama）。  
  - 关键参数：`symbol`（必填，如 `BTC/USDT`）、`include_fields`（默认 `["funding_rate","open_interest"]`）、`lookback_hours`（清算回溯窗口）、`options_expiry`（期权到期日，YYMMDD）。

### 链上工具 onchain_*

- `onchain_tvl_fees` — 协议 TVL 与费用/收入  
  - 参数：`protocol`（必填，如 `uniswap`、`aave`）、`chain`（可选，用于标注链）。  
  - 返回：`tvl`（总锁仓与链分布）、`protocol_fees`（24h/7d/30d 费用与收入）。

- `onchain_stablecoins_cex` — 稳定币与 CEX 储备  
  - 参数：`exchange`（可选，如 `binance`，为空则返回聚合视图）。  
  - 返回：主要稳定币指标和 CEX 储备快照。

- `onchain_bridge_volumes` — 跨链桥交易量  
  - 参数：`bridge`（可选，如 `stargate`，为空则汇总）。  
  - 返回：24h/7d/30d 交易量及桥列表。

- `onchain_dex_liquidity` — DEX 流动性（Uniswap v3）  
  - 参数：`chain`（必填，如 `ethereum`）、`pool_address`（单池详情）、`token_address`（按代币列池）、`include_ticks`（是否返回 Tick 流动性分布）。  
  - 返回：`dex_liquidity`（池子列表、总 TVL、可选 ticks）。

- `onchain_governance` — 治理提案（Snapshot + Tally）  
  - 参数：`chain`（默认 `ethereum`）、`snapshot_space`（如 `uniswap.eth`）、`governor_address`（Tally governor 合约）。  
  - 返回：`governance`（提案列表、状态统计）。

- `onchain_whale_transfers` — 大额转账监控（Whale Alert）  
  - 参数：`token_symbol`（可选，如 `ETH`，为空则多币种）、`min_value_usd`（默认 500000）、`lookback_hours`（默认 24）。  
  - 返回：`whale_transfers`（转账明细与汇总）。

- `onchain_token_unlocks` — 代币解锁计划  
  - 参数：`token_symbol`（可选，不填时返回热门项目的解锁计划）。  
  - 返回：`token_unlocks`（未来解锁事件列表与聚合信息）。

- `onchain_activity` — 链上活跃度（Etherscan）  
  - 参数：`chain`（必填，如 `ethereum`、`arbitrum`）、`protocol`（可选标签）。  
  - 返回：活跃地址数、交易数、Gas 使用等。

- `onchain_contract_risk` — 合约风险评估（GoPlus / Slither）  
  - 参数：`contract_address`（必填）、`chain`（必填）。  
  - 返回：`contract_risk`（风险评分、风险级别、GoPlus/Slither 详细字段与 `warnings`）。

### 宏观与搜索

- `macro_hub` — 宏观/Fed/指数/日历  
  - 功能：恐惧贪婪指数、加密指数、传统指数、FRED/Fed 数据、宏观日历等，按 `mode` 控制。  
  - 参数：`mode`（`dashboard`/`fear_greed`/`crypto_indices`/`indices`/`fed`/`calendar`）、`country`（默认 `US`）、`calendar_days`、`calendar_min_importance`。

- `web_research_search` — Web/新闻/学术搜索  
  - 功能：统一调度 DuckDuckGo/Brave/Google/Bing/SerpAPI/Kaito + 新闻聚合（Telegram/Bing News/Kaito）+ 学术（Semantic Scholar/Arxiv）。  
  - 参数：`query`（必填）、`scope`（`web`/`news`/`academic`，默认 `web`）、`providers`（可选）、`time_range`（如 `past_24h`、`7d`）、`limit`（默认 10）。

### 图表

- `draw_chart` — 图表配置归一化  
  - 功能：接收调用方生成的 Plotly 配置，统计数据点并规范输出结构，不主动拉取行情数据。  
  - 参数：`chart_type`、`symbol`、`config`（必填），可选 `title`、`timeframe`、`indicators`。
3. API调用失败，降级到部分数据

### Q: 如何清除缓存？

**A**: 连接到Redis并执行：

```bash
# 清除所有crypto_overview缓存
redis-cli
> KEYS crypto_overview:*
> DEL crypto_overview:*

# 或清除特定symbol
> DEL crypto_overview:market:BTC:*
```

---

## 开发调试

### 启用详细日志

编辑`.env`：

```bash
LOG_LEVEL=DEBUG
```

### 禁用缓存（测试用）

编辑`.env`：

```bash
ENABLE_CACHE=false
```

### 查看API调用详情

日志中会记录：
- 数据源调用顺序
- 响应时间
- 降级事件
- 冲突检测结果

---

## 性能优化建议

1. **启用Redis缓存** - 避免重复API调用
2. **配置多数据源** - 提高可用性
3. **调整TTL策略** - 根据实际需求修改`config/ttl_policies.yaml`
4. **使用API key** - 提高限流额度

---

## 技术支持

遇到问题请查看：
- [项目文档](../docs/)
- [GitHub Issues](https://github.com/ethanzhrepo/hubrium_mcp/issues)
