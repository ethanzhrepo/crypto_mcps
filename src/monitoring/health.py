"""
健康检查模块

提供系统健康状态检查：
- 数据源健康检查
- 系统资源检查
- 依赖服务检查
"""
import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

from src.core.data_source_registry import DataSourceRegistry
from src.middleware import global_error_aggregator, global_rate_limiter_registry

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""

    HEALTHY = "healthy"  # 完全健康
    DEGRADED = "degraded"  # 部分降级
    UNHEALTHY = "unhealthy"  # 不健康


class HealthChecker:
    """
    系统健康检查器

    执行全面的系统健康检查
    """

    def __init__(
        self,
        data_source_registry: Optional[DataSourceRegistry] = None,
        check_interval_seconds: int = 60,
    ):
        """
        初始化健康检查器

        Args:
            data_source_registry: 数据源注册表
            check_interval_seconds: 检查间隔（秒）
        """
        self.registry = data_source_registry
        self.check_interval = check_interval_seconds
        self._last_check_time: Optional[datetime] = None
        self._cached_result: Optional[Dict[str, Any]] = None

    async def check_all(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        执行完整的健康检查

        Args:
            use_cache: 是否使用缓存结果

        Returns:
            健康检查结果字典
        """
        # 检查缓存
        if use_cache and self._cached_result and self._last_check_time:
            elapsed = (datetime.now() - self._last_check_time).total_seconds()
            if elapsed < self.check_interval:
                return self._cached_result

        start_time = time.time()

        # 执行各项检查
        data_sources_health = await self._check_data_sources()
        error_health = self._check_error_rates()
        rate_limiter_health = self._check_rate_limiters()

        # 汇总状态
        overall_status = self._determine_overall_status(
            data_sources_health, error_health, rate_limiter_health
        )

        result = {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {
                "data_sources": data_sources_health,
                "error_rates": error_health,
                "rate_limiters": rate_limiter_health,
            },
            "check_duration_ms": round((time.time() - start_time) * 1000, 2),
        }

        # 更新缓存
        self._last_check_time = datetime.now()
        self._cached_result = result

        logger.info(
            "health_check_completed",
            status=overall_status.value,
            duration_ms=result["check_duration_ms"],
        )

        return result

    async def _check_data_sources(self) -> Dict[str, Any]:
        """检查所有数据源的健康状态"""
        if not self.registry:
            return {
                "status": HealthStatus.HEALTHY.value,
                "message": "No registry configured",
                "sources": {},
            }

        sources_status = {}
        healthy_count = 0
        total_count = 0

        # 并发检查所有数据源
        tasks = []
        source_names = []

        for source_name in self.registry.list_providers():
            source = self.registry.get_source(source_name)
            if source and hasattr(source, "health_check"):
                tasks.append(source.health_check())
                source_names.append(source_name)
                total_count += 1

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(source_names, results):
                if isinstance(result, Exception):
                    sources_status[name] = {
                        "healthy": False,
                        "error": str(result),
                    }
                else:
                    is_healthy = bool(result)
                    sources_status[name] = {"healthy": is_healthy}
                    if is_healthy:
                        healthy_count += 1

        # 确定状态
        if total_count == 0:
            status = HealthStatus.HEALTHY
        elif healthy_count == total_count:
            status = HealthStatus.HEALTHY
        elif healthy_count >= total_count / 2:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        return {
            "status": status.value,
            "healthy_count": healthy_count,
            "total_count": total_count,
            "sources": sources_status,
        }

    def _check_error_rates(self) -> Dict[str, Any]:
        """检查错误率"""
        error_summary = global_error_aggregator.get_error_summary()
        error_rate = error_summary["error_rate_per_minute"]

        # 错误率阈值
        if error_rate == 0:
            status = HealthStatus.HEALTHY
        elif error_rate < 10:  # 每分钟少于10个错误
            status = HealthStatus.HEALTHY
        elif error_rate < 50:  # 每分钟少于50个错误
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        return {
            "status": status.value,
            "error_rate_per_minute": error_rate,
            "total_errors": error_summary["total_errors"],
            "errors_by_source": error_summary["errors_by_source"],
            "errors_by_type": error_summary["errors_by_type"],
        }

    def _check_rate_limiters(self) -> Dict[str, Any]:
        """检查速率限制器状态"""
        all_stats = global_rate_limiter_registry.get_all_stats()

        # 检查是否有耗尽的限制器
        exhausted_limiters = []
        for name, stats in all_stats.items():
            current = stats.get("current", {})

            # 检查各种限制
            if "minute_remaining" in current and current["minute_remaining"] == 0:
                exhausted_limiters.append(f"{name}(minute)")
            if "hour_remaining" in current and current["hour_remaining"] == 0:
                exhausted_limiters.append(f"{name}(hour)")
            if "day_remaining" in current and current["day_remaining"] == 0:
                exhausted_limiters.append(f"{name}(day)")

        # 确定状态
        if not exhausted_limiters:
            status = HealthStatus.HEALTHY
        elif len(exhausted_limiters) <= 2:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        return {
            "status": status.value,
            "exhausted_limiters": exhausted_limiters,
            "limiters": all_stats,
        }

    def _determine_overall_status(
        self,
        data_sources: Dict,
        errors: Dict,
        rate_limiters: Dict,
    ) -> HealthStatus:
        """确定总体健康状态"""
        statuses = [
            HealthStatus(data_sources["status"]),
            HealthStatus(errors["status"]),
            HealthStatus(rate_limiters["status"]),
        ]

        # 如果有任何UNHEALTHY，整体为UNHEALTHY
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY

        # 如果有任何DEGRADED，整体为DEGRADED
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED

        # 否则为HEALTHY
        return HealthStatus.HEALTHY

    async def check_single_source(self, source_name: str) -> Dict[str, Any]:
        """
        检查单个数据源

        Args:
            source_name: 数据源名称

        Returns:
            健康检查结果
        """
        if not self.registry:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "message": "No registry configured",
            }

        source = self.registry.get_source(source_name)
        if not source:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "message": f"Source '{source_name}' not found",
            }

        start_time = time.time()

        try:
            is_healthy = await source.health_check()
            duration_ms = (time.time() - start_time) * 1000

            # 获取统计信息
            stats = {}
            if hasattr(source, "get_stats"):
                stats = source.get_stats()

            return {
                "status": (
                    HealthStatus.HEALTHY.value
                    if is_healthy
                    else HealthStatus.UNHEALTHY.value
                ),
                "source_name": source_name,
                "check_duration_ms": round(duration_ms, 2),
                "stats": stats,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "health_check_failed",
                source=source_name,
                error=str(e),
            )

            return {
                "status": HealthStatus.UNHEALTHY.value,
                "source_name": source_name,
                "check_duration_ms": round(duration_ms, 2),
                "error": str(e),
            }

    def get_readiness(self) -> Dict[str, Any]:
        """
        获取就绪状态（用于K8s readiness probe）

        返回简化的就绪检查结果
        """
        if not self._cached_result:
            return {
                "ready": False,
                "message": "Health check not yet performed",
            }

        status = HealthStatus(self._cached_result["status"])

        return {
            "ready": status != HealthStatus.UNHEALTHY,
            "status": status.value,
            "last_check": self._cached_result["timestamp"],
        }

    def get_liveness(self) -> Dict[str, Any]:
        """
        获取存活状态（用于K8s liveness probe）

        返回简单的存活检查结果
        """
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
