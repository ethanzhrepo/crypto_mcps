"""
数据源抽象基类
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

from src.core.models import SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.middleware import (
    CircuitBreaker,
    RateLimiter,
    global_error_aggregator,
    global_rate_limiter_registry,
    with_retry,
)
from src.utils.config import config
from src.utils.exceptions import (
    DataSourceAuthError,
    DataSourceNotFoundError,
    DataSourceRateLimitError,
    DataSourceTimeoutError,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseDataSource(ABC):
    """数据源抽象基类"""

    def __init__(
        self,
        name: str,
        base_url: str,
        timeout: float = 10.0,
        requires_api_key: bool = False,
        enable_circuit_breaker: bool = True,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 60.0,
    ):
        """
        初始化数据源

        Args:
            name: 数据源名称（如 coingecko, binance）
            base_url: API基础URL
            timeout: 请求超时时间（秒）
            requires_api_key: 是否需要API密钥
            enable_circuit_breaker: 是否启用断路器
            circuit_failure_threshold: 断路器失败阈值
            circuit_recovery_timeout: 断路器恢复超时（秒）
        """
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.requires_api_key = requires_api_key
        self.api_key = config.get_api_key(name)

        # 检查API密钥
        if requires_api_key and not self.api_key:
            logger.warning(
                f"{name} requires API key but none configured",
                provider=name,
            )

        self._client: Optional[httpx.AsyncClient] = None

        # 初始化断路器
        self.circuit_breaker: Optional[CircuitBreaker] = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                name=name,
                failure_threshold=circuit_failure_threshold,
                recovery_timeout=circuit_recovery_timeout,
            )

        # 获取速率限制器（从全局注册表）
        self.rate_limiter: Optional[RateLimiter] = (
            global_rate_limiter_registry.get(name)
        )
        if not self.rate_limiter:
            # 如果没有预注册，尝试自动注册
            self.rate_limiter = global_rate_limiter_registry.register(name)

    @property
    def client(self) -> httpx.AsyncClient:
        """获取HTTP客户端（懒加载）"""
        if self._client is None:
            headers = self._get_headers()
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头（子类实现）

        Returns:
            请求头字典
        """
        pass

    @abstractmethod
    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """
        获取原始数据（子类实现）

        Args:
            endpoint: API端点路径
            params: 查询参数
            base_url_override: 可选的基础URL覆盖
            headers: 可选的自定义请求头

        Returns:
            原始响应数据

        Raises:
            DataSourceError: 数据源错误
        """
        pass

    @abstractmethod
    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        将原始数据转换为标准格式（子类实现）

        Args:
            raw_data: 原始API响应
            data_type: 数据类型（如 basic, market）

        Returns:
            标准化后的数据字典
        """
        pass

    async def fetch(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        data_type: str = "default",
        ttl_seconds: int = 300,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取并转换数据的完整流程

        Args:
            endpoint: API端点
            params: 查询参数
            data_type: 数据类型
            ttl_seconds: TTL秒数
            base_url_override: 可选的基础URL覆盖
            headers: 可选的自定义请求头

        Returns:
            (转换后的数据, SourceMeta)
        """
        start_time = time.time()

        try:
            # 使用断路器保护
            if self.circuit_breaker:
                raw_data = await self.circuit_breaker.call(
                    self._fetch_with_retry, endpoint, params, base_url_override, headers
                )
            else:
                raw_data = await self._fetch_with_retry(endpoint, params, base_url_override, headers)

            # 转换数据
            transformed_data = self.transform(raw_data, data_type)

            # 计算响应时间
            response_time_ms = (time.time() - start_time) * 1000

            # 构建SourceMeta
            source_meta = SourceMetaBuilder.build(
                provider=self.name,
                endpoint=endpoint,
                ttl_seconds=ttl_seconds,
                response_time_ms=response_time_ms,
            )

            logger.info(
                f"Successfully fetched from {self.name}",
                provider=self.name,
                endpoint=endpoint,
                response_time_ms=response_time_ms,
            )

            return transformed_data, source_meta

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000

            # 记录错误到聚合器
            global_error_aggregator.record_error(
                source=self.name,
                exception=e,
                endpoint=endpoint,
            )

            logger.error(
                f"Failed to fetch from {self.name}",
                provider=self.name,
                endpoint=endpoint,
                error=str(e),
                response_time_ms=response_time_ms,
            )
            raise

    @with_retry(
        max_attempts=3,
        backoff_base=2.0,
        max_backoff=60.0,
    )
    async def _fetch_with_retry(
        self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None
    ) -> Any:
        """
        带重试的数据获取（内部方法）

        Args:
            endpoint: API端点
            params: 查询参数
            base_url_override: 可选的基础URL覆盖
            headers: 可选的自定义请求头

        Returns:
            原始数据
        """
        # 速率限制检查
        if self.rate_limiter:
            # 等待获取速率限制许可（最多等待30秒）
            allowed = await self.rate_limiter.acquire(wait=True, timeout=30.0)
            if not allowed:
                raise DataSourceRateLimitError(
                    self.name,
                    "Rate limit exceeded and could not acquire permit",
                )

        return await self.fetch_raw(endpoint, params, base_url_override, headers)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        base_url_override: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict] = None,
    ) -> Any:
        """
        发起HTTP请求（通用方法）

        Args:
            method: HTTP方法（GET, POST等）
            endpoint: 端点路径
            params: 查询参数（Query String）
            base_url_override: 可选的基础URL覆盖
            headers: 可选的自定义请求头（会与默认请求头合并）
            json_body: JSON 请求体（主要用于 POST/PUT）

        Returns:
            响应数据

        Raises:
            DataSourceError: 各种数据源错误
        """
        try:
            # 如果提供了base_url_override，构建完整URL
            if base_url_override:
                url = f"{base_url_override.rstrip('/')}{endpoint}"
            else:
                url = endpoint

            # 合并自定义headers（如果提供）
            request_headers = None
            if headers:
                request_headers = headers

            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                headers=request_headers,
                json=json_body,
            )

            # 处理HTTP错误状态码
            if response.status_code == 401:
                raise DataSourceAuthError(
                    self.name, "Authentication failed. Check API key."
                )
            elif response.status_code == 404:
                raise DataSourceNotFoundError(self.name, f"Resource not found: {endpoint}")
            elif response.status_code == 429:
                raise DataSourceRateLimitError(self.name, "Rate limit exceeded")
            elif response.status_code >= 400:
                raise Exception(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )

            return response.json()

        except httpx.TimeoutException:
            raise DataSourceTimeoutError(
                self.name, f"Request timeout after {self.timeout}s"
            )
        except httpx.HTTPError as e:
            raise Exception(f"HTTP error: {str(e)}")

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True表示健康
        """
        try:
            # 子类可以覆盖此方法实现特定的健康检查
            # 默认尝试发起一个简单请求
            await self.client.get("/")
            return True
        except Exception as e:
            logger.warning(f"{self.name} health check failed", error=str(e))
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取数据源统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "name": self.name,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "requires_api_key": self.requires_api_key,
            "has_api_key": bool(self.api_key),
        }

        # 添加断路器统计
        if self.circuit_breaker:
            stats["circuit_breaker"] = self.circuit_breaker.get_stats()

        # 添加速率限制统计
        if self.rate_limiter:
            stats["rate_limiter"] = self.rate_limiter.get_stats()

        # 添加错误率
        error_rate = global_error_aggregator.get_error_rate(source=self.name)
        stats["error_rate_per_minute"] = error_rate

        return stats

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} base_url={self.base_url}>"
