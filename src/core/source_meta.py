"""
SourceMeta构建器
"""
from datetime import datetime, timezone
from typing import Optional

from src.core.models import SourceMeta


class SourceMetaBuilder:
    """SourceMeta构建器"""

    @staticmethod
    def build(
        provider: str,
        endpoint: str,
        ttl_seconds: int,
        degraded: bool = False,
        fallback_used: Optional[str] = None,
        response_time_ms: Optional[float] = None,
    ) -> SourceMeta:
        """
        构建SourceMeta

        Args:
            provider: 数据提供者名称
            endpoint: API端点
            ttl_seconds: 缓存TTL
            degraded: 是否降级模式
            fallback_used: 使用的备用源
            response_time_ms: 响应时间（毫秒）

        Returns:
            SourceMeta实例
        """
        return SourceMeta(
            provider=provider,
            endpoint=endpoint,
            as_of_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            ttl_seconds=ttl_seconds,
            degraded=degraded,
            fallback_used=fallback_used,
            response_time_ms=response_time_ms,
        )

    @staticmethod
    def build_degraded(
        provider: str,
        endpoint: str,
        ttl_seconds: int,
        fallback_from: str,
        response_time_ms: Optional[float] = None,
    ) -> SourceMeta:
        """
        构建降级模式的SourceMeta

        Args:
            provider: 当前使用的数据提供者
            endpoint: API端点
            ttl_seconds: 缓存TTL
            fallback_from: 从哪个源降级而来
            response_time_ms: 响应时间

        Returns:
            SourceMeta实例
        """
        return SourceMetaBuilder.build(
            provider=provider,
            endpoint=endpoint,
            ttl_seconds=ttl_seconds,
            degraded=True,
            fallback_used=fallback_from,
            response_time_ms=response_time_ms,
        )
