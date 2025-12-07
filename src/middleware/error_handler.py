"""
错误处理中间件

提供生产级别的错误处理：
- 指数退避重试
- 断路器模式
- 错误聚合和监控
"""
import asyncio
import time
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

import structlog

from src.utils.exceptions import (
    DataSourceAuthError,
    DataSourceError,
    DataSourceRateLimitError,
    DataSourceTimeoutError,
)

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """断路器状态"""

    CLOSED = "closed"  # 正常状态，请求通过
    OPEN = "open"  # 断开状态，请求直接失败
    HALF_OPEN = "half_open"  # 半开状态，允许少量请求测试


class CircuitBreaker:
    """
    断路器模式实现

    当错误率超过阈值时，暂时停止请求，避免雪崩效应
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,  # 失败次数阈值
        recovery_timeout: float = 60.0,  # 恢复超时（秒）
        expected_exception: Type[Exception] = Exception,
    ):
        """
        初始化断路器

        Args:
            name: 断路器名称（通常是数据源名称）
            failure_threshold: 连续失败次数阈值
            recovery_timeout: 断开后多久尝试恢复（秒）
            expected_exception: 需要捕获的异常类型
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None

        logger.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    @property
    def state(self) -> CircuitState:
        """获取当前状态（考虑自动恢复）"""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(
                    "circuit_breaker_half_open",
                    name=self.name,
                    reason="recovery_timeout_elapsed",
                )
                self._state = CircuitState.HALF_OPEN
        return self._state

    def _should_attempt_reset(self) -> bool:
        """是否应该尝试重置（从OPEN到HALF_OPEN）"""
        if not self._last_failure_time:
            return False
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过断路器调用函数

        Args:
            func: 要调用的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            函数返回值

        Raises:
            Exception: 断路器开启时抛出异常
        """
        if self.state == CircuitState.OPEN:
            logger.warning(
                "circuit_breaker_open",
                name=self.name,
                failure_count=self._failure_count,
            )
            raise DataSourceError(
                self.name,
                f"Circuit breaker is OPEN (failures: {self._failure_count})",
            )

        try:
            # 调用函数
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 成功：重置计数器
            self._on_success()
            return result

        except self.expected_exception as e:
            # 失败：增加计数器
            self._on_failure()
            raise

    def _on_success(self):
        """成功回调"""
        self._failure_count = 0
        self._last_success_time = datetime.now()

        if self._state == CircuitState.HALF_OPEN:
            logger.info(
                "circuit_breaker_closed",
                name=self.name,
                reason="successful_call_in_half_open",
            )
            self._state = CircuitState.CLOSED

    def _on_failure(self):
        """失败回调"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        logger.warning(
            "circuit_breaker_failure",
            name=self.name,
            failure_count=self._failure_count,
            threshold=self.failure_threshold,
        )

        if self._failure_count >= self.failure_threshold:
            logger.error(
                "circuit_breaker_opened",
                name=self.name,
                failure_count=self._failure_count,
            )
            self._state = CircuitState.OPEN

    def reset(self):
        """手动重置断路器"""
        logger.info("circuit_breaker_reset", name=self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time.isoformat()
            if self._last_failure_time
            else None,
            "last_success_time": self._last_success_time.isoformat()
            if self._last_success_time
            else None,
        }


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    max_backoff: float = 60.0,
    retry_exceptions: tuple = (
        DataSourceTimeoutError,
        DataSourceRateLimitError,
    ),
    no_retry_exceptions: tuple = (DataSourceAuthError,),
):
    """
    重试装饰器（支持指数退避）

    Args:
        max_attempts: 最大尝试次数
        backoff_base: 退避基数（每次重试延迟 = backoff_base ^ attempt）
        max_backoff: 最大退避时间（秒）
        retry_exceptions: 需要重试的异常类型
        no_retry_exceptions: 不重试的异常类型（直接抛出）

    Example:
        @with_retry(max_attempts=3, backoff_base=2.0)
        async def fetch_data():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    # 尝试调用函数
                    result = await func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(
                            "retry_success",
                            function=func.__name__,
                            attempt=attempt,
                        )
                    return result

                except no_retry_exceptions as e:
                    # 不重试的异常，直接抛出
                    logger.warning(
                        "no_retry_exception",
                        function=func.__name__,
                        exception=type(e).__name__,
                        message=str(e),
                    )
                    raise

                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        # 计算退避时间
                        backoff = min(
                            backoff_base ** (attempt - 1),
                            max_backoff,
                        )
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            exception=type(e).__name__,
                            backoff_seconds=backoff,
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            exception=type(e).__name__,
                        )

                except Exception as e:
                    # 未预期的异常
                    last_exception = e
                    logger.error(
                        "unexpected_exception",
                        function=func.__name__,
                        attempt=attempt,
                        exception=type(e).__name__,
                        message=str(e),
                    )
                    # 未预期的异常不重试
                    raise

            # 所有重试都失败
            if last_exception:
                raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            """同步函数包装器"""
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(
                            "retry_success",
                            function=func.__name__,
                            attempt=attempt,
                        )
                    return result

                except no_retry_exceptions as e:
                    logger.warning(
                        "no_retry_exception",
                        function=func.__name__,
                        exception=type(e).__name__,
                        message=str(e),
                    )
                    raise

                except retry_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        backoff = min(
                            backoff_base ** (attempt - 1),
                            max_backoff,
                        )
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            exception=type(e).__name__,
                            backoff_seconds=backoff,
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            exception=type(e).__name__,
                        )

                except Exception as e:
                    last_exception = e
                    logger.error(
                        "unexpected_exception",
                        function=func.__name__,
                        attempt=attempt,
                        exception=type(e).__name__,
                        message=str(e),
                    )
                    raise

            if last_exception:
                raise last_exception

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class ErrorAggregator:
    """
    错误聚合器

    收集和聚合错误信息，用于监控和告警
    """

    def __init__(self, window_seconds: int = 300):
        """
        初始化错误聚合器

        Args:
            window_seconds: 时间窗口（秒）
        """
        self.window_seconds = window_seconds
        self._errors: List[Dict[str, Any]] = []

    def record_error(
        self,
        source: str,
        exception: Exception,
        endpoint: Optional[str] = None,
    ):
        """
        记录错误

        Args:
            source: 数据源名称
            exception: 异常对象
            endpoint: API端点
        """
        error_record = {
            "timestamp": datetime.now(),
            "source": source,
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "endpoint": endpoint,
        }
        self._errors.append(error_record)

        # 清理过期记录
        self._cleanup_old_errors()

    def _cleanup_old_errors(self):
        """清理超出时间窗口的错误记录"""
        cutoff_time = datetime.now() - timedelta(seconds=self.window_seconds)
        self._errors = [e for e in self._errors if e["timestamp"] > cutoff_time]

    def get_error_rate(self, source: Optional[str] = None) -> float:
        """
        获取错误率（每分钟错误数）

        Args:
            source: 数据源名称（可选，不指定则返回全局错误率）

        Returns:
            每分钟错误数
        """
        self._cleanup_old_errors()

        if source:
            errors = [e for e in self._errors if e["source"] == source]
        else:
            errors = self._errors

        if not errors:
            return 0.0

        # 计算每分钟错误数
        window_minutes = self.window_seconds / 60
        return len(errors) / window_minutes

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        self._cleanup_old_errors()

        # 按数据源统计
        source_counts: Dict[str, int] = {}
        exception_counts: Dict[str, int] = {}

        for error in self._errors:
            source = error["source"]
            exception_type = error["exception_type"]

            source_counts[source] = source_counts.get(source, 0) + 1
            exception_counts[exception_type] = (
                exception_counts.get(exception_type, 0) + 1
            )

        return {
            "total_errors": len(self._errors),
            "error_rate_per_minute": self.get_error_rate(),
            "errors_by_source": source_counts,
            "errors_by_type": exception_counts,
            "window_seconds": self.window_seconds,
        }


# 全局错误聚合器实例
global_error_aggregator = ErrorAggregator(window_seconds=300)
