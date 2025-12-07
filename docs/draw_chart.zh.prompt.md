工具：draw_chart — 图表配置归一化

用途与场景
- 接收上游 Agent / 客户端已经根据行情、指标等生成的 Plotly 图表配置，做轻量校验与数据点统计。
- 适用于：已经拿到数据（如通过 `market_microstructure`、`derivatives_hub` 等），只需要一个统一的图表输出结构给前端或报告模版使用。

入参规划（Planner）
- 必填：
  - `chart_type`：支持 `line`、`candlestick`、`area`、`bar`、`heatmap`、`scatter` 等。
  - `symbol`：资产或交易对，例如 `BTC/USDT`、`ETH`。
  - `config`：完整 Plotly 配置（含 `data` 与 `layout`），由调用方构造。
- 选填：
  - `title`：图表标题，纯展示字段。
  - `timeframe`：时间框架标签（如 `1m/5m/15m/1h/4h/1d`），仅用于说明，不参与计算。
  - `indicators`：指标标签列表（如 `["MA20","MA50","RSI"]`），仅记录在输出中。

TTL 与新鲜度
- 工具本身不访问任何数据源，`as_of_utc` 表示生成图表的时间戳；
- 底层数据的新鲜度应由上游工具（如 `market_microstructure`）的 Evidence/TTL 说明，此处不再重复建模。

标准化与一致性
- 工具会尝试从 `config.data[0]` 中推断数据点数（优先看 `x`/`y`/`close`），写入 `chart.data_points`；
- `chart.chart_config` 原样返回调用方提供的 Plotly 配置，不做重写或补全。

冲突与异常
- 若 `config` 为空或无法解析出数据点（缺少 `data[0].x/y/close` 等），`data_points` 会为 `0`，并在 `warnings[]` 中给出提示；
- 不会自动生成 mock K 线或调用其他 MCP 工具。

输出与证据（EvidenceBundle）
- 返回字段：
  - `chart.chart_config`：完整 Plotly 配置；
  - `chart.data_points`：推断的数据点数量；
  - `chart.warnings[]`：关于配置问题的提示。
- 适合作为上游分析链路的最后一环，将已经确定的数据与图表配置打包交给前端渲染或报告系统。

示例入参
```json
{
  "chart_type": "candlestick",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "indicators": ["MA20", "RSI"],
  "config": {
    "layout": {
      "title": {"text": "BTC/USDT 价格走势 (1h)"}
    },
    "data": [
      {
        "type": "candlestick",
        "x": ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z"],
        "open": [42000.0, 42100.0],
        "high": [42200.0, 42300.0],
        "low": [41900.0, 42050.0],
        "close": [42150.0, 42250.0]
      }
    ]
  }
}
```

注意事项
- draw_chart 不负责拉取行情或指标数据，调用前必须先通过其他工具拿到时间序列并自行生成 Plotly 配置；
- 若需要多图联动或复杂布局，可以在 `config` 中自行组织多个 trace / subplot，draw_chart 会整体原样返回。
