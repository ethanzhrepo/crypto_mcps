"""
通用搜索API客户端

支持多个搜索引擎：
- DuckDuckGo Instant Answer API (无需API key)
- Brave Search API (需要API key)
- Google Custom Search API (需要API key + Search Engine ID)
- Bing Search API (需要API key)
- SerpAPI (聚合搜索API，需要API key)
- Kaito (加密货币搜索，需要API key)
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

import structlog

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource

logger = structlog.get_logger()


class SearchClient(BaseDataSource):
    """通用搜索客户端"""

    DDG_API_URL = "https://api.duckduckgo.com/"
    BRAVE_API_URL = "https://api.search.brave.com/res/v1"
    GOOGLE_API_URL = "https://www.googleapis.com/customsearch/v1"
    BING_API_URL = "https://api.bing.microsoft.com/v7.0/search"
    SERPAPI_URL = "https://serpapi.com/search"
    KAITO_API_URL = "https://api.kaito.ai/v1"

    def __init__(
        self,
        brave_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        google_cse_id: Optional[str] = None,
        bing_api_key: Optional[str] = None,
        serpapi_key: Optional[str] = None,
        kaito_api_key: Optional[str] = None,
        news_source_config: Optional[Dict[str, Dict]] = None,
    ):
        """
        初始化搜索客户端

        Args:
            brave_api_key: Brave Search API密钥（可选）
            google_api_key: Google Custom Search API密钥（可选）
            google_cse_id: Google Custom Search Engine ID（可选）
            bing_api_key: Bing Search API密钥（可选）
            serpapi_key: SerpAPI密钥（可选）
            kaito_api_key: Kaito API密钥（可选）
            news_source_config: 新闻源配置字典（可选）
        """
        super().__init__(
            name="search",
            base_url=self.DDG_API_URL,  # 默认使用DuckDuckGo
            timeout=15.0,
            requires_api_key=False,
        )
        self.brave_api_key = brave_api_key
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id
        self.bing_api_key = bing_api_key
        self.serpapi_key = serpapi_key
        self.kaito_api_key = kaito_api_key

        # 新闻源默认配置
        self.news_source_config = news_source_config or {
            "bing_news": {"enabled": True, "top_n": 20},
            "kaito": {"enabled": False, "top_n": 30},
        }

    def _get_headers(self) -> Dict[str, str]:
        """构建默认请求头"""
        return {
            "accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; HubriumMCP/1.0)",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    async def search_web(
        self, query: str, limit: int = 10, provider: str = "auto"
    ) -> tuple[List[Dict], SourceMeta]:
        """
        Web搜索

        Args:
            query: 搜索查询
            limit: 结果数量
            provider: 搜索提供商 (auto/duckduckgo/brave/google/bing/serpapi/kaito)
                     auto: 自动选择第一个可用的提供商

        Returns:
            (搜索结果列表, 元信息)
        """
        # 自动选择提供商（按优先级）
        if provider == "auto":
            if self.google_api_key and self.google_cse_id:
                provider = "google"
            elif self.brave_api_key:
                provider = "brave"
            elif self.bing_api_key:
                provider = "bing"
            elif self.serpapi_key:
                provider = "serpapi"
            elif self.kaito_api_key:
                provider = "kaito"
            else:
                provider = "duckduckgo"  # 默认使用免费的DDG

        # 调用对应的搜索方法
        if provider == "google":
            return await self._search_google(query, limit)
        elif provider == "brave":
            return await self._search_brave(query, limit)
        elif provider == "bing":
            return await self._search_bing(query, limit)
        elif provider == "serpapi":
            return await self._search_serpapi(query, limit)
        elif provider == "kaito":
            return await self._search_kaito(query, limit)
        else:  # duckduckgo
            return await self._search_duckduckgo(query, limit)

    async def _search_duckduckgo(
        self, query: str, limit: int
    ) -> tuple[List[Dict], SourceMeta]:
        """使用DuckDuckGo Instant Answer API"""
        endpoint = ""
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="duckduckgo",
            ttl_seconds=3600,  # 1小时缓存
            base_url_override=self.DDG_API_URL,
        )

        return data, meta

    async def _search_brave(
        self, query: str, limit: int
    ) -> tuple[Dict, SourceMeta]:
        """使用Brave Search API"""
        endpoint = "/web/search"
        params = {
            "q": query,
            "count": limit,
        }

        headers = {"X-Subscription-Token": self.brave_api_key}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="brave",
            ttl_seconds=3600,
            base_url_override=self.BRAVE_API_URL,
            headers=headers,
        )

        return data, meta

    async def _search_google(
        self, query: str, limit: int
    ) -> tuple[List[Dict], SourceMeta]:
        """使用Google Custom Search API"""
        if not self.google_api_key or not self.google_cse_id:
            raise ValueError("Google Search requires API key and Custom Search Engine ID")

        endpoint = ""
        params = {
            "key": self.google_api_key,
            "cx": self.google_cse_id,
            "q": query,
            "num": min(limit, 10),  # Google限制最多10个结果
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="google",
            ttl_seconds=3600,
            base_url_override=self.GOOGLE_API_URL,
        )

        return data, meta

    async def _search_bing(
        self, query: str, limit: int
    ) -> tuple[List[Dict], SourceMeta]:
        """使用Bing Search API"""
        if not self.bing_api_key:
            raise ValueError("Bing Search requires API key")

        endpoint = ""
        params = {
            "q": query,
            "count": min(limit, 50),  # Bing限制最多50个结果
            "mkt": "en-US",
        }

        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="bing",
            ttl_seconds=3600,
            base_url_override=self.BING_API_URL,
            headers=headers,
        )

        return data, meta

    async def _search_serpapi(
        self, query: str, limit: int
    ) -> tuple[List[Dict], SourceMeta]:
        """使用SerpAPI（聚合搜索API）"""
        if not self.serpapi_key:
            raise ValueError("SerpAPI requires API key")

        endpoint = ""
        params = {
            "api_key": self.serpapi_key,
            "q": query,
            "num": min(limit, 100),
            "engine": "google",  # 默认使用Google引擎
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="serpapi",
            ttl_seconds=3600,
            base_url_override=self.SERPAPI_URL,
        )

        return data, meta

    async def _search_kaito(
        self, query: str, limit: int
    ) -> tuple[List[Dict], SourceMeta]:
        """使用Kaito加密货币搜索API"""
        if not self.kaito_api_key:
            raise ValueError("Kaito requires API key")

        endpoint = "/search"
        params = {
            "q": query,
            "limit": limit,
        }

        headers = {"Authorization": f"Bearer {self.kaito_api_key}"}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="kaito",
            ttl_seconds=3600,
            base_url_override=self.KAITO_API_URL,
            headers=headers,
        )

        return data, meta

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据为标准格式"""
        if data_type == "duckduckgo":
            return self._transform_duckduckgo(raw_data)
        elif data_type == "brave":
            return self._transform_brave(raw_data)
        elif data_type == "google":
            return self._transform_google(raw_data)
        elif data_type == "bing":
            return self._transform_bing(raw_data)
        elif data_type == "serpapi":
            return self._transform_serpapi(raw_data)
        elif data_type == "kaito":
            return self._transform_kaito(raw_data)
        return raw_data

    def _transform_duckduckgo(self, data: Dict) -> List[Dict]:
        """转换DuckDuckGo结果（改进版，更健壮的处理）"""
        results = []

        # DuckDuckGo Instant Answer主要返回单个答案，不是搜索结果列表
        # 1. 优先处理 Abstract（最相关的答案）
        if data.get("Abstract"):
            results.append(
                {
                    "title": data.get("Heading", "DuckDuckGo Answer"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("Abstract", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                    "relevance_score": 1.0,
                }
            )

        # 2. 提取RelatedTopics作为相关结果
        if "RelatedTopics" in data and isinstance(data["RelatedTopics"], list):
            for topic in data["RelatedTopics"][:10]:
                # RelatedTopics 可能包含分组（有 "Topics" 键）或直接的主题
                if isinstance(topic, dict):
                    if "Topics" in topic and isinstance(topic["Topics"], list):
                        # 处理分组的主题
                        for subtopic in topic["Topics"][:5]:
                            if isinstance(subtopic, dict) and subtopic.get("Text"):
                                results.append(
                                    {
                                        "title": subtopic.get("Text", "")[:100],
                                        "url": subtopic.get("FirstURL", ""),
                                        "snippet": subtopic.get("Text", ""),
                                        "source": "DuckDuckGo",
                                        "relevance_score": 0.8,
                                    }
                                )
                    elif topic.get("Text"):
                        # 直接的主题
                        results.append(
                            {
                                "title": topic.get("Text", "")[:100],
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", ""),
                                "source": "DuckDuckGo",
                                "relevance_score": 0.9,
                            }
                        )

        # 3. 如果还没有结果，检查 Definition
        if not results and data.get("Definition"):
            results.append(
                {
                    "title": data.get("Heading", "Definition"),
                    "url": data.get("DefinitionURL", ""),
                    "snippet": data.get("Definition", ""),
                    "source": data.get("DefinitionSource", "DuckDuckGo"),
                    "relevance_score": 0.9,
                }
            )

        # 4. 如果还没有结果，检查 Answer
        if not results and data.get("Answer"):
            results.append(
                {
                    "title": "Quick Answer",
                    "url": "",
                    "snippet": data.get("Answer", ""),
                    "source": "DuckDuckGo",
                    "relevance_score": 0.8,
                }
            )

        # 5. 记录空结果情况（用于调试）
        if not results:
            logger.warning(
                "DuckDuckGo returned no usable results",
                available_fields=list(data.keys()),
                has_redirect=bool(data.get("Redirect")),
            )
            # 检查是否是重定向
            if data.get("Redirect"):
                logger.info(f"DuckDuckGo suggests redirect to: {data.get('Redirect')}")

        return results

    def _transform_brave(self, data: Dict) -> List[Dict]:
        """转换Brave Search结果"""
        results = []

        if "web" in data and "results" in data["web"]:
            for item in data["web"]["results"]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "source": "Brave Search",
                        "relevance_score": item.get("page_age_rank", None),
                    }
                )

        return results

    def _transform_google(self, data: Dict) -> List[Dict]:
        """转换Google Custom Search结果"""
        results = []

        if "items" in data:
            for item in data["items"]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "Google",
                        "relevance_score": None,
                    }
                )

        return results

    def _transform_bing(self, data: Dict) -> List[Dict]:
        """转换Bing Search结果"""
        results = []

        if "webPages" in data and "value" in data["webPages"]:
            for item in data["webPages"]["value"]:
                results.append(
                    {
                        "title": item.get("name", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", ""),
                        "source": "Bing",
                        "relevance_score": None,
                    }
                )

        return results

    def _transform_serpapi(self, data: Dict) -> List[Dict]:
        """转换SerpAPI结果"""
        results = []

        # SerpAPI返回的organic_results包含搜索结果
        if "organic_results" in data:
            for item in data["organic_results"]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                        "source": f"SerpAPI ({item.get('source', 'Google')})",
                        "relevance_score": item.get("position", None),
                    }
                )

        return results

    def _transform_kaito(self, data: Dict) -> List[Dict]:
        """转换Kaito加密货币搜索结果"""
        results = []

        # Kaito API返回结构（假设）
        if "results" in data:
            for item in data["results"]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                        "source": f"Kaito - {item.get('category', 'Crypto')}",
                        "relevance_score": item.get("score", None),
                    }
                )
        elif "data" in data:  # 备用结构
            for item in data["data"]:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("summary", ""),
                        "source": "Kaito",
                        "relevance_score": None,
                    }
                )

        return results

    async def search_news_parallel(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        time_range: Optional[str] = None,
        start_time: Optional[datetime] = None,
    ) -> Tuple[List[Dict], List[str]]:
        """
        并行搜索所有配置的新闻数据源，合并结果

        Args:
            query: 搜索查询
            providers: 新闻提供商（可选），支持：bing_news/bing, kaito
            time_range: 时间范围（可选）

        Returns:
            合并后的搜索结果列表和警告信息
        """
        tasks = []
        warnings = []
        source_names = []

        provider_set = None
        if providers:
            provider_set = {p.lower().strip() for p in providers if isinstance(p, str)}

        def _provider_enabled(provider_name: str) -> bool:
            if not provider_set:
                return True
            if provider_name == "bing_news":
                return "bing_news" in provider_set or "bing" in provider_set
            return provider_name in provider_set

        # Bing News
        if _provider_enabled("bing_news") and self.news_source_config.get("bing_news", {}).get("enabled", False):
            if self.bing_api_key:
                top_n = self.news_source_config["bing_news"].get("top_n", 20)
                tasks.append(self._search_bing_news_safe(query, top_n, time_range))
                source_names.append("Bing")
            else:
                warnings.append("Bing News需要BING_SEARCH_API_KEY")

        # Kaito
        if _provider_enabled("kaito") and self.news_source_config.get("kaito", {}).get("enabled", False):
            if self.kaito_api_key:
                top_n = self.news_source_config["kaito"].get("top_n", 30)
                tasks.append(self._search_kaito_safe(query, top_n))
                source_names.append("Kaito")
            else:
                warnings.append("Kaito需要KAITO_API_KEY")

        # 并行执行所有搜索
        if not tasks:
            logger.warning("no_news_sources_enabled", query=query)
            warnings.append("没有可用的新闻数据源（Bing News/Kaito均未配置）")
            return [], warnings

        logger.info(
            "parallel_news_search_start",
            query=query,
            num_sources=len(tasks),
        )

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        all_results = []
        for i, results in enumerate(results_list):
            source_name = source_names[i] if i < len(source_names) else f"Source{i}"
            if isinstance(results, Exception):
                logger.warning("news_search_source_failed", source=source_name, error=str(results))
                warnings.append(f"{source_name}搜索失败: {str(results)}")
                continue
            if isinstance(results, list):
                all_results.extend(results)

        logger.info(
            "parallel_news_search_complete",
            query=query,
            total_results=len(all_results),
        )

        return all_results, warnings

    async def _search_bing_news_safe(self, query: str, limit: int, time_range: Optional[str] = None) -> List[Dict]:
        """安全的 Bing News 搜索（捕获异常）"""
        try:
            import httpx

            freshness = "Day"
            if time_range:
                tr = time_range.lower()
                if "year" in tr or "365" in tr:
                    freshness = "Month"
                elif "month" in tr or "30d" in tr:
                    freshness = "Month"
                elif "week" in tr or "7d" in tr:
                    freshness = "Week"
                elif "24h" in tr or "day" in tr or "past_24h" in tr:
                    freshness = "Day"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.bing.microsoft.com/v7.0/news/search",
                    params={
                        "q": query,
                        "count": min(limit, 100),
                        "mkt": "en-US",
                        "freshness": freshness,
                    },
                    headers={"Ocp-Apim-Subscription-Key": self.bing_api_key},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()

            results = []
            if "value" in data:
                for item in data["value"]:
                    provider_name = "Unknown"
                    if item.get("provider"):
                        provider_name = item["provider"][0].get("name", "Unknown")

                    results.append(
                        {
                            "title": item.get("name", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("description", ""),
                            "source": f"Bing News - {provider_name}",
                            "relevance_score": None,
                            "published_at": item.get("datePublished"),
                        }
                    )

            logger.info("bing_news_search_success", count=len(results))
            return results
        except Exception as e:
            logger.warning(f"bing_news_search_failed: {e}")
            return []

    async def _search_kaito_safe(self, query: str, limit: int) -> List[Dict]:
        """安全的 Kaito 搜索（捕获异常）"""
        try:
            data, _ = await self._search_kaito(query, limit)
            logger.info("kaito_search_success", count=len(data))
            return data
        except Exception as e:
            logger.warning(f"kaito_search_failed: {e}")
            return []
