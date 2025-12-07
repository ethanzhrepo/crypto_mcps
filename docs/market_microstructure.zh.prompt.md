工具：market_microstructure — 行情与微结构

用途与场景
- 提供 Binance 行情：ticker、K线、逐笔、订单簿、成交量分布、主动买卖流、滑点估算、交易规则、板块统计和简要指标，适合追踪流动性与微观结构。
- 适用于：日评/流动性评估/容量与执行参数/波动与结构性变化复盘。

入参规划（Planner）
- 必填：`symbol`（如 BTCUSDT、ETHUSDT）。
- 可选：`venues`（建议只填 `["binance"]`，OKX 仅在 Binance 报错时做简单 fallback，尚未做全量聚合）、`include_fields`（支持 `ticker`、`klines`、`trades`、`orderbook`、`volume_profile`、`taker_flow`、`slippage`、`venue_specs`、`sector_stats`，默认 `["ticker","orderbook"]`）。
- 参数控制：`kline_interval`（1m/5m/15m/1h/4h/1d）、`kline_limit`（默认 100）、`orderbook_depth`（默认 20）、`trades_limit`（默认 100）、`slippage_size_usd`（默认 10000）。

TTL 与新鲜度
- ticker/trades/orderbook：TTL 3–5s；klines：TTL 等于一个 `interval`（至少 30–60s）。
- volume_profile/taker_flow/slippage：依赖 trades/orderbook 快照，TTL 10–30s；venue_specs：TTL 24h。
- 不满足模板 `freshness_budget` 时，标注 `freshness_sla_met=false` 与 `stale_fields`。

源与回退（记录 source_meta）
- 主源：Binance（统一 BinanceClient）。
- 备用：OKX 仅在 Binance 抓取失败时作为错误容错；Coinbase/Kraken 等未正式启用。
- 所有结果均以 USD 报价，若 `venues` 中含多个交易所，也会以 Binane 为主并记录 fallback。

冲突处理
- 目前仅有 Binance 主源；若 fetch 失败才会 fallback，合并时会在 warnings 中记录“使用 OKX”。
- `volume_profile`/`taker_flow`/`slippage` 不做跨所整合，仅在 Binance trades/orderbook 充足时生效。

输出与证据（EvidenceBundle）
- EvidenceItem：`tool=market_microstructure`、`include_fields`、入参与 `ttl_policy`、`source_meta[]`（大多来自 Binance）。
- 派生要点：
  - VP：基于 `trades` 自动分桶，突出高密度价格区与 VWAP 偏离。
  - 滑点估算：用 `orderbook` 快照加上 `slippage_size_usd` 推算冲击成本（仅买入侧）。
  - 板块统计：调用 CoinGecko 返回的大类数据，说明所属 category 和 top3 币的市值。

失败与退化
- 速率/配额：优先保留 Binance，必要时仅返回 ticker/orderbook，其他字段以 `warnings[]` 告知缺失。
- `venues` 建议仅填写 `["binance"]`，不同场所不会自动对齐 orderbook/klines。

示例入参
```json
{
  "symbol": "BTCUSDT",
  "include_fields": ["ticker", "orderbook", "klines", "volume_profile"],
  "kline_interval": "1h",
  "kline_limit": 100,
  "orderbook_depth": 20,
  "trades_limit": 100,
  "slippage_size_usd": 10000
}
```

注意事项
- `volume_profile`、`taker_flow`、`slippage` 等指标依赖于完整的 trades/orderbook，缺失则会返回 `warnings[]` 并跳过。
- 若跨交易所调用，只会在日志中记录 fallback（Binance → OKX），不会做汇总合并。
