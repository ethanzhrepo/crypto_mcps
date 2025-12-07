"""
web_research_search 工具完整实现

提供Web搜索和研究功能：
- DuckDuckGo Instant Answer API集成（无需API key）
- Brave Search API集成（可选，需要API key）
- 学术搜索（可扩展）
"""
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import structlog

from src.core.models import (
    SearchResult,
    SourceMeta,
    WebResearchInput,
    WebResearchOutput,
)
from src.data_sources.search import SearchClient

logger = structlog.get_logger()


class WebResearchTool:
    """web_research_search工具"""

    def __init__(self, search_client: Optional[SearchClient] = None):
        """
        初始化web_research工具

        Args:
            search_client: 搜索客户端（可选）
        """
        self.search_client = search_client or SearchClient()
        logger.info("web_research_tool_initialized")

    async def execute(
        self, params
    ) -> WebResearchOutput:
        """执行web_research查询"""
        # 如果传入字典，转换为Pydantic模型
        if isinstance(params, dict):
            params = WebResearchInput(**params)

        start_time = time.time()
        logger.info(
            "web_research_execute_start",
            query=params.query,
            scope=params.scope,
            providers=params.providers,
            time_range=params.time_range,
            limit=params.limit,
        )

        start_window = self._parse_time_range(params.time_range)

        warnings = []

        # 根据搜索范围执行搜索
        if params.scope == "web":
            results, meta = await self._search_web(params.query, params.limit, params.providers, params.time_range)
            source_metas = [meta]
        elif params.scope == "academic":
            results, meta = await self._search_academic(params.query, params.limit, params.time_range)
            source_metas = [meta]
        elif params.scope == "news":
            results, meta = await self._search_news(
                params.query,
                params.limit,
                params.providers,
                start_window,
                params.time_range,
            )
            source_metas = [meta]
        else:
            results = []
            source_metas = []
            warnings.append(f"Unknown search scope: {params.scope}")

        results = self._filter_by_time_range(results, start_window)

        elapsed = time.time() - start_time
        logger.info(
            "web_research_execute_complete",
            query=params.query,
            results_count=len(results),
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return WebResearchOutput(
            query=params.query,
            results=results,
            total_results=len(results),
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

    async def _search_web(
        self, query: str, limit: int, providers: Optional[List[str]] = None, time_range: Optional[str] = None
    ) -> Tuple[List[SearchResult], SourceMeta]:
        """执行Web搜索"""
        # 确定使用哪个搜索提供商
        provider = "auto"  # 默认自动选择

        if providers and len(providers) > 0:
            # 如果指定了providers，使用第一个可用的
            # 优先级：按用户指定顺序
            for p in providers:
                if p == "google" and self.search_client.google_api_key:
                    provider = "google"
                    break
                elif p == "brave" and self.search_client.brave_api_key:
                    provider = "brave"
                    break
                elif p == "bing" and self.search_client.bing_api_key:
                    provider = "bing"
                    break
                elif p == "serpapi" and self.search_client.serpapi_key:
                    provider = "serpapi"
                    break
                elif p == "kaito" and self.search_client.kaito_api_key:
                    provider = "kaito"
                    break
                elif p == "duckduckgo":
                    provider = "duckduckgo"
                    break

        data, meta = await self.search_client.search_web(
            query=query, limit=limit, provider=provider
        )

        # 转换为SearchResult
        results = []
        for item in data:
            results.append(SearchResult(**item))

        return results, meta

    async def _search_academic(
        self, query: str, limit: int, time_range: Optional[str] = None
    ) -> Tuple[List[SearchResult], SourceMeta]:
        """执行学术搜索（Semantic Scholar + Arxiv）"""
        from src.core.source_meta import SourceMetaBuilder

        results = []

        # 1. 尝试 Semantic Scholar API (免费，无需API key)
        try:
            ss_results = await self._search_semantic_scholar(query, limit // 2)
            results.extend(ss_results)
        except Exception as e:
            logger.warning(f"Semantic Scholar search failed: {e}")

        # 2. 尝试 Arxiv API (免费，无需API key)
        try:
            arxiv_results = await self._search_arxiv(query, limit - len(results))
            results.extend(arxiv_results)
        except Exception as e:
            logger.warning(f"Arxiv search failed: {e}")

        # 如果没有结果，fallback 到 Google Scholar 查询
        if not results:
            logger.info("Academic search failed, using web search with academic query")
            data, meta = await self.search_client.search_web(
                query=f"site:scholar.google.com OR site:arxiv.org {query}",
                limit=limit,
                provider="auto"
            )
            results = [SearchResult(**item) for item in data]
        else:
            meta = SourceMetaBuilder.build(
                provider="academic_aggregated",
                endpoint="semantic_scholar+arxiv",
                ttl_seconds=3600,
            )

        return results, meta

    async def _search_news(
        self,
        query: str,
        limit: int,
        providers: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        time_range: Optional[str] = None,
    ) -> Tuple[List[SearchResult], SourceMeta]:
        """执行新闻搜索（并行搜索所有配置的数据源）"""
        from src.core.source_meta import SourceMetaBuilder

        # 使用并行搜索
        data = await self.search_client.search_news_parallel(
            query=query,
            time_range=time_range,
            start_time=start_time,
        )

        # 应用 limit（如果指定）
        if limit and len(data) > limit:
            data = data[:limit]

        # 转换为 SearchResult
        results = [SearchResult(**item) for item in data]

        # 构建元信息
        meta = SourceMetaBuilder.build(
            provider="news_aggregated",
            endpoint="parallel_search",
            ttl_seconds=600,  # 新闻更新快，缓存10分钟
        )

        return results, meta

    def _parse_time_range(self, time_range: Optional[str]) -> Optional[datetime]:
        if not time_range:
            return None

        tr = time_range.lower().strip()

        if tr.startswith("past_"):
            tr = tr[len("past_") :]

        now = datetime.utcnow()

        if tr.endswith("h") and tr[:-1].isdigit():
            return now - timedelta(hours=int(tr[:-1]))
        if tr.endswith("d") and tr[:-1].isdigit():
            return now - timedelta(days=int(tr[:-1]))

        if "day" in tr:
            return now - timedelta(days=1)
        if "week" in tr or "7d" in tr:
            return now - timedelta(weeks=1)
        if "month" in tr or "30d" in tr:
            return now - timedelta(days=30)
        if "year" in tr or "365" in tr:
            return now - timedelta(days=365)

        return None

    async def _search_semantic_scholar(self, query: str, limit: int) -> List[Dict]:
        """搜索 Semantic Scholar"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": min(limit, 100),
                    "fields": "title,abstract,url,year,authors"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()

        results = []
        if "data" in data:
            for paper in data["data"]:
                authors = ", ".join([a.get("name", "") for a in paper.get("authors", [])[:3]])
                results.append({
                    "title": paper.get("title", ""),
                    "url": paper.get("url", f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}"),
                    "snippet": f"{paper.get('abstract', '')[:200]}... (Year: {paper.get('year', 'N/A')}, Authors: {authors})",
                    "source": "Semantic Scholar",
                    "relevance_score": None,
                })

        return results

    async def _search_arxiv(self, query: str, limit: int) -> List[Dict]:
        """搜索 Arxiv"""
        import httpx
        import xml.etree.ElementTree as ET

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": min(limit, 100),
                    "sortBy": "relevance",
                    "sortOrder": "descending"
                },
                timeout=10.0
            )
            response.raise_for_status()

        # 解析 Arxiv Atom XML
        root = ET.fromstring(response.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            link = entry.find("atom:id", ns)
            published = entry.find("atom:published", ns)

            authors = entry.findall("atom:author/atom:name", ns)
            author_names = ", ".join([a.text for a in authors[:3]]) if authors else "Unknown"

            results.append({
                "title": title.text.strip() if title is not None else "",
                "url": link.text if link is not None else "",
                "snippet": f"{summary.text[:200] if summary is not None else ''}... (Published: {published.text[:10] if published is not None else 'N/A'}, Authors: {author_names})",
                "source": "Arxiv",
                "relevance_score": None,
            })

        return results

    def _filter_by_time_range(
        self, results: List[Dict], start_time: Optional[datetime]
    ) -> List[Dict]:
        """根据起始时间过滤结果，仅保留有时间戳且在窗口内的项；无 timestamp 的结果也保留。"""
        if not start_time:
            return results

        filtered = []
        for entry in results:
            published = entry.get("published_at")
            if not published:
                filtered.append(entry)
                continue

            parsed = self._parse_timestamp(published)
            if parsed and parsed >= start_time:
                filtered.append(entry)

        return filtered

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None

        try:
            normalized = value
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
