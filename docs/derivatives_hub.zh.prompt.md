工具：derivatives_hub — 衍生品统一入口

用途与场景
- 统一返回资金费率、未平仓量、多空比、基差/期限结构、期权曲面/指标、借贷利率和清算摘要（有适配的数据源时）。
- 适用于：资金面与杠杆程度监控、期货贴水/升水与期限结构分析、期权偏斜与 IV 风险点估、资金利率与借贷成本对比。

入参规划（Planner）
- 必填：`symbol`（如 BTCUSDT、ETHUSDT）。
- 可选：
  - `include_fields`（默认 `["funding_rate","open_interest"]`，可选项：`funding_rate`、`open_interest`、`long_short_ratio`、`basis_curve`、`term_structure`、`options_surface`、`options_metrics`、`borrow_rates`、`liquidations`）。  
  - `lookback_hours`（用于 `liquidations`，默认 24，小于 48）。
  - `options_expiry`（用于 `options_surface`，若未提供，将取最近可用到期日）。

TTL 与新鲜度
- 资金费率/开盘利率/OI：TTL 15–60s；多空比/基差：TTL 30s–2min；期权/借贷：TTL 5–10min；清算（Coinglass）：TTL 1–5min。
- 仅当数据源配置齐全（如 Deribit/DefiLlama/Coinglass）时才返回对应字段，缺失时记录 `warnings[]`。

源与回退（记录 source_meta）
- 资金费率、OI、多空比来自 Binance（OKX 表现为 fallback）。
- `liquidations` 依赖 Coinglass；`options_surface`/`options_metrics` 依赖 Deribit；`borrow_rates` 依赖 DefiLlama；`basis_curve` 和 `term_structure` 是基于 Binance 永续/交割合约的推算。

冲突处理
- 数据以主源为准，若 fallback 到 OKX，仅记录 `warnings[]` 和 `source_meta.fallback_used`。
- 期权数据仅在 Deribit 可用时返回，口径固定为 25δ RR/BF、ATM-IV，未做复杂滚动或 25d 以上曲面合成。

输出与证据（EvidenceBundle）
- EvidenceItem：`tool=derivatives_hub`、`include_fields`、入参与 `ttl_policy`、`source_meta[]`。
- 派生要点：
  - 基差/期限结构：以永续/交割合约 mark price + funding rate 推估。
  - 期权：若 Deribit 可用，返回 options_surface（ATM-IV + skew）与 options_metrics（Put/Call、IV index）。
  - 借贷利率：DefiLlama 借贷市场快照。

失败与退化
- Deribit/DefiLlama/Coinglass 未配置：对应字段返回 `warnings[]`（如 `options_surface` 需明确提示“未配置 Deribit”）。
- 资金费率/OI 获取失败：降级到 OKX 并在 `warnings[]` 说明。

示例入参
```json
{
  "symbol": "ETHUSDT",
  "include_fields": ["funding_rate", "open_interest", "basis_curve", "term_structure"],
  "lookback_hours": 24
}
```

注意事项
- `liquidations` 仅在 Coinglass API key 配置完毕且字段包含在 `include_fields` 时才返回。
- `options_surface`/`options_metrics` 需要 Deribit 客户端，默认不启用时会在 `warnings[]` 说明“Deribit 未配置”。
