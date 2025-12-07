工具：crypto_overview — 代币一站式概览

用途与场景
- 为单一代币建立“资产基线”：基础资料、市场指标、供应结构、持有者集中度、社交链接、板块分类与开发活跃度。
- 适用于：主题立项/初评、日评周报“资产卡片”、覆盖报告的背景与对照。

入参规划（Planner）
- 必填：`symbol`（如 BTC, ETH, SOL）。
- 选填：`token_address`（用于确认合约、获取 holders 等链上数据）、`chain`（如 ethereum、arbitrum，与 `token_address` 配合用于消歧义）、`include_fields=["all"|子集]`。
- `vs_currency` 参数目前仅支持 `usd`（服务端固定输出 USD 计价），如果提供其他值会自动回退到 USD。
- 若 `symbol` 对应多链或多合约，优先使用 `token_address+chain` 锁定唯一资产；否则内部会默认映射到主流 CEX 的主链（如 Ethereum）并在 warnings 中提示。

TTL 与新鲜度
- 市场指标：TTL 15–30s；基础资料/社交/分类：TTL 1–6h；开发活跃度：TTL 24h。
- 若模板 `freshness_budget` 更严，则以模板为准；不满足时标注 `freshness_sla_met=false` 并列出 `stale_fields`。

源与回退（记录 source_meta）
- 主源：CoinGecko（基础+价格+社交+分类）。
- 回退：CoinMarketCap；补充：Messari（解锁/质押）、多链浏览器（供应/持仓）、GitHub API（开发活跃）。
- 失败策略：主源失败→回退；记录 `degraded=true` 与原因。

冲突处理（多源不一致）
- 规则：主源优先；若差异>阈值（价格>10bps、流通供给>1%），执行“阈值共识”或“时间戳最新优先”。
- 必写 `conflicts[]`：字段/提供者/取值/差值/解决规则；在正文只给结论与影响说明。

输出与证据（EvidenceBundle）
- 每次调用产出 EvidenceItem：`tool=crypto_overview`、`params_hash`、`as_of_utc`、`ttl_policy`、`source_meta[]`、`snapshot_uri`（如存档）。
- 派生要点：FDV、流通占比、Top10/50/100持有者占比、开发活跃变化（近30/90天）。

失败与退化
- 命名歧义：回退到 `token_address+chain`；若仍不确定，输出“需人工确认”。
- 速率/配额：缩小字段集或拆分调用；重试指数退避；记录 `warnings[]`。

示例入参
```json
{
  "symbol": "ARB",
  "chain": "arbitrum",
  "include_fields": ["basic","market","supply","holders","sector","dev_activity"],
  "vs_currency": "usd"
}
```

注意事项
- 对初创/迁链资产，优先以合约地址与链确定唯一性。
- 若持有者集中度异常，标注对流动性与滑点评估的潜在影响。
- holders 数据必须带 `chain` + `token_address`，否则只返回基本范围或提示缺失；其它字段可只凭 `symbol`。
