工具：macro_hub — 宏观/Fed/指数/日历

用途与场景
- 聚合 Fear & Greed 指数、加密指数、传统金融指数、FRED 数据、财经日历，工作模式以 `mode` 控制。
- 适用于周报/策略会前的宏观背景、跨资产风险轮动观察、事件期（FOMC/CPI）数据准备。

入参规划（Planner）
- 必填：`mode`，可选：
  - `dashboard`（默认）：集中返回恐惧贪婪指数、加密指数、金融市场指数、财经日历。
  - `fear_greed`：只关注 Alternative.me Fear & Greed 指数。
  - `crypto_indices`：返回总市值/BTC 占比/ETH 占比等加密指数。
  - `indices`：返回传统市场指数（标普500、纳指、VIX、黄金、美元指数）与三个大类商品。
  - `fed`：聚合 FRED 通胀、就业、收益率曲线、联储工具（TGA/RRP）。
  - `calendar`：返回未来 `calendar_days` 内的重要财经事件。
- 其它参数：
  - `country`：财经日历所属国家，默认 `US`。
  - `calendar_days`：财经日历查询天数（默认 7）。
  - `calendar_min_importance`：财经日历最小重要性 1–3。

TTL 与新鲜度
- 恐惧贪婪与加密指数：TTL 1–6h；FRED/联储：TTL 30m–2h；财经日历：TTL 1h。
- `freshness_budget` 更严格时以其为准；不满足时在 `warnings[]` 及 `stale_fields` 说明影响。

源与回退（记录 source_meta）
- Fear & Greed：Alternative.me。
- 加密指数：MacroDataClient（可选 API）。
- FRED：inflation/employment/yield_curve/fed_tools，需配置 `FRED_API_KEY`。
- 传统指数：Yahoo Finance（仅闲置 API，无需 key）；财经日历：Investing.com。
- 尚未实现的 ETF 资金流（etf_flows）留在 TODO，工具会在 `warnings[]` 提示“ETF flows 未实现”。

冲突处理
- 以主源为准；FRED 与 传统指数间若口径不一致，在 Evidence 记录差异并提供 `warnings[]`。
- 若 API 限额或网络异常，使用缓存数据并标记 `cached=true`。

输出与证据（EvidenceBundle）
- EvidenceItem：`tool=macro_hub`、`mode`、`calendar_days`、`params_hash`、`source_meta[]`。
- 派生要点：FedTools 和收益率曲线的共同趋势、加密指数与传统金融之间的相关、财经日历重点事件。

失败与退化
- 未配置 FRED key：`mode` 为 `fed` 时会在 `warnings[]` 提示 “FRED API key required”。
- 网页抓取失败（Investing.com）：返回上次缓存并标记 `cached=true`。

示例入参
```json
{
  "mode": "indices",
  "calendar_days": 5,
  "calendar_min_importance": 2
}
```

注意事项
- `etf_flows` 功能暂未实现，会在 logs/`warnings[]` 明确提示。
- `mode` 设置决定返回字段，调用方应根据需求限定请求频率并侧重具体指标（如仅 `fed` 时不需 `calendar_days`）。
