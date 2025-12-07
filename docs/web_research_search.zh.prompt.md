工具：web_research_search — Web/新闻/学术搜索

用途与场景
- 统一调度 Web（DuckDuckGo、Brave、Google、Bing、SerpAPI）、新闻（Telegram/新闻 API/Kaito）、学术（Semantic Scholar/Arxiv）搜索，支持多源并行。
- 适用于背景速查、新闻引用、学术/研报梳理、对照式检索，强调可追溯的 Evidence。

入参规划（Planner）
- 必填：`query`（搜索关键词）。
- 可选：
  - `scope`：`web`（默认，包括综合搜索）/`news`（并行 Telegram、Bing News、Kaito，带时间过滤）/`academic`（Semantic Scholar+Arxiv）。
  - `providers`：指定首选来源，支持 `google`、`brave`、`bing`、`serpapi`、`kaito`、`duckduckgo`，优先按列表顺序选择可用 API。
  - `time_range`：可选时间窗口，仅在 `scope=news` 生效（可传 `past_24h`、`past_day`、`past_week`、`past_month`、`past_year`、`7d`、`30d` 等），会让 Telegram（Elasticsearch range）和 Bing News（freshness）据此过滤。
  - `limit`：最多返回条数（默认 10）。

TTL 与新鲜度
- Web搜索：TTL 1–6h；新闻聚合：TTL 10–15min（Telegram/Bing/Kaito）；学术：TTL 6–24h。
- 实现 `time_range` 时会记录 `start_time`，若结果缺乏时间戳会原样返回但在 Evidence 里提示“时间过滤依赖于来源”。

源与回退（记录 source_meta）
- DuckDuckGo/Brave/Google/Bing/SerpAPI：按 `providers` 顺序（无 key 时自动回退到 DuckDuckGo）。
- 新闻：Telegram（ElasticSearch）、Bing News API、Kaito；优先并行取可用部分并去重。
- 学术：Semantic Scholar + Arxiv，若均失败 fallback 至 Google Scholar 关键词。

冲突处理
- 结果去重：基于 URL dedup；不同结果相互矛盾时在 Evidence 中附加 `warnings[]`。
- `time_range` 仅对携带 `published_at` 的来源生效（如 Telegram、Bing News）。

输出与证据（EvidenceBundle）
- EvidenceItem：`tool=web_research_search`、`scope/providers`、`time_range`、`params_hash`、`source_meta[]`。
- 仅在正文引用少量摘要，完整 URL 列于 “Evidence & Sources”。

失败与退化
- Telegram/Bing/Kaito 限额：自动跳过不可用源、降低 limit 并记录 `warnings[]`。
- `time_range` 对不含时间字段的结果无效，会在 Evidence 说明“source lacks timestamps, showing full window”。

示例入参
```json
{
  "query": "Solana Saga sales Q4 2025",
  "scope": "news",
  "providers": ["bing", "duckduckgo"],
  "time_range": "past_month",
  "limit": 15
}
```

注意事项
- 这个工具只是搜索接口，没有“研报优先”策略，结果按照 scope/提供商展示；若需要研报请在 query 中加入 site:messari.com 等限定。
- Telegram 搜索依赖 Elasticsearch，`time_range` 会真正转换为 `timestamp ≥ start_time` 的筛选。
