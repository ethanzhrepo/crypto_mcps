"""
速率限制中间件

提供API配额管理和速率限制：
- Token Bucket算法
- Sliding Window算法
- 按数据源的配额管理
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class RateLimitConfig:
    """速率限制配置"""

    requests_per_second: Optional[float] = None  # 每秒请求数
    requests_per_minute: Optional[int] = None  # 每分钟请求数
    requests_per_hour: Optional[int] = None  # 每小时请求数
    requests_per_day: Optional[int] = None  # 每天请求数
    requests_per_month: Optional[int] = None  # 每月请求数
    burst_size: Optional[int] = None  # 突发请求大小


class TokenBucket:
    """
    令牌桶算法实现

    允许突发流量，同时限制平均速率
    """

    def __init__(
        self,
        rate: float,  # 令牌生成速率（每秒）
        capacity: int,  # 桶容量
    ):
        """
        初始化令牌桶

        Args:
            rate: 令牌生成速率（每秒）
            capacity: 桶容量（最大令牌数）
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌

        Args:
            tokens: 需要的令牌数

        Returns:
            是否成功获取
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def wait_for_token(self, tokens: int = 1, timeout: Optional[float] = None):
        """
        等待令牌（阻塞）

        Args:
            tokens: 需要的令牌数
            timeout: 超时时间（秒）

        Raises:
            asyncio.TimeoutError: 超时
        """
        start_time = time.time()

        while True:
            if await self.acquire(tokens):
                return

            # 检查超时
            if timeout and (time.time() - start_time) >= timeout:
                raise asyncio.TimeoutError("Rate limit acquisition timeout")

            # 计算需要等待的时间
            wait_time = tokens / self.rate
            await asyncio.sleep(min(wait_time, 0.1))  # 最多等待0.1秒再检查

    def _refill(self):
        """补充令牌"""
        now = time.time()
        elapsed = now - self._last_update

        # 计算新增令牌数
        new_tokens = elapsed * self.rate
        self._tokens = min(self._tokens + new_tokens, self.capacity)
        self._last_update = now

    def get_available_tokens(self) -> float:
        """获取当前可用令牌数"""
        return self._tokens

    def get_wait_time(self, tokens: int = 1) -> float:
        """
        获取需要等待的时间（秒）

        Args:
            tokens: 需要的令牌数

        Returns:
            等待时间（秒），0表示无需等待
        """
        if self._tokens >= tokens:
            return 0.0

        needed_tokens = tokens - self._tokens
        return needed_tokens / self.rate


class SlidingWindowCounter:
    """
    滑动窗口计数器

    用于精确的时间窗口限制（如每分钟、每小时）
    """

    def __init__(self, window_seconds: int, max_requests: int):
        """
        初始化滑动窗口计数器

        Args:
            window_seconds: 时间窗口（秒）
            max_requests: 最大请求数
        """
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._requests: list[float] = []  # 请求时间戳列表
        self._lock = asyncio.Lock()

    async def check_and_add(self) -> bool:
        """
        检查并添加请求

        Returns:
            是否允许请求
        """
        async with self._lock:
            now = time.time()
            cutoff_time = now - self.window_seconds

            # 清理过期记录
            self._requests = [t for t in self._requests if t > cutoff_time]

            # 检查是否超限
            if len(self._requests) >= self.max_requests:
                return False

            # 记录新请求
            self._requests.append(now)
            return True

    def get_current_count(self) -> int:
        """获取当前窗口内的请求数"""
        now = time.time()
        cutoff_time = now - self.window_seconds
        self._requests = [t for t in self._requests if t > cutoff_time]
        return len(self._requests)

    def get_remaining(self) -> int:
        """获取剩余配额"""
        return max(0, self.max_requests - self.get_current_count())

    def get_reset_time(self) -> Optional[datetime]:
        """获取重置时间"""
        if not self._requests:
            return None
        oldest_request = min(self._requests)
        reset_timestamp = oldest_request + self.window_seconds
        return datetime.fromtimestamp(reset_timestamp)


class RateLimiter:
    """
    多层速率限制器

    支持同时配置多个时间窗口的限制
    """

    def __init__(self, name: str, config: RateLimitConfig):
        """
        初始化速率限制器

        Args:
            name: 限制器名称（通常是数据源名称）
            config: 速率限制配置
        """
        self.name = name
        self.config = config

        # Token Bucket（用于每秒限制和突发控制）
        self.token_bucket: Optional[TokenBucket] = None
        if config.requests_per_second:
            burst_size = config.burst_size or int(config.requests_per_second * 2)
            self.token_bucket = TokenBucket(
                rate=config.requests_per_second,
                capacity=burst_size,
            )

        # Sliding Windows（用于分钟、小时、天级别限制）
        self.minute_window: Optional[SlidingWindowCounter] = None
        if config.requests_per_minute:
            self.minute_window = SlidingWindowCounter(
                window_seconds=60,
                max_requests=config.requests_per_minute,
            )

        self.hour_window: Optional[SlidingWindowCounter] = None
        if config.requests_per_hour:
            self.hour_window = SlidingWindowCounter(
                window_seconds=3600,
                max_requests=config.requests_per_hour,
            )

        self.day_window: Optional[SlidingWindowCounter] = None
        if config.requests_per_day:
            self.day_window = SlidingWindowCounter(
                window_seconds=86400,
                max_requests=config.requests_per_day,
            )

        logger.info(
            "rate_limiter_initialized",
            name=name,
            config=config,
        )

    async def acquire(self, wait: bool = False, timeout: Optional[float] = None) -> bool:
        """
        获取速率限制许可

        Args:
            wait: 是否等待（阻塞直到获得许可）
            timeout: 等待超时时间（秒）

        Returns:
            是否获得许可

        Raises:
            asyncio.TimeoutError: 等待超时
        """
        # 检查所有限制
        if self.token_bucket:
            if wait:
                await self.token_bucket.wait_for_token(1, timeout)
            else:
                if not await self.token_bucket.acquire(1):
                    logger.warning(
                        "rate_limit_exceeded",
                        name=self.name,
                        limit_type="per_second",
                    )
                    return False

        # 检查分钟限制
        if self.minute_window:
            if not await self.minute_window.check_and_add():
                logger.warning(
                    "rate_limit_exceeded",
                    name=self.name,
                    limit_type="per_minute",
                    current=self.minute_window.get_current_count(),
                    max=self.config.requests_per_minute,
                )
                return False

        # 检查小时限制
        if self.hour_window:
            if not await self.hour_window.check_and_add():
                logger.warning(
                    "rate_limit_exceeded",
                    name=self.name,
                    limit_type="per_hour",
                    current=self.hour_window.get_current_count(),
                    max=self.config.requests_per_hour,
                )
                return False

        # 检查天限制
        if self.day_window:
            if not await self.day_window.check_and_add():
                logger.warning(
                    "rate_limit_exceeded",
                    name=self.name,
                    limit_type="per_day",
                    current=self.day_window.get_current_count(),
                    max=self.config.requests_per_day,
                )
                return False

        return True

    def get_stats(self) -> Dict[str, any]:
        """获取统计信息"""
        stats = {
            "name": self.name,
            "limits": {
                "per_second": self.config.requests_per_second,
                "per_minute": self.config.requests_per_minute,
                "per_hour": self.config.requests_per_hour,
                "per_day": self.config.requests_per_day,
                "burst_size": self.config.burst_size,
            },
            "current": {},
        }

        if self.token_bucket:
            stats["current"]["available_tokens"] = self.token_bucket.get_available_tokens()

        if self.minute_window:
            stats["current"]["minute_used"] = self.minute_window.get_current_count()
            stats["current"]["minute_remaining"] = self.minute_window.get_remaining()

        if self.hour_window:
            stats["current"]["hour_used"] = self.hour_window.get_current_count()
            stats["current"]["hour_remaining"] = self.hour_window.get_remaining()

        if self.day_window:
            stats["current"]["day_used"] = self.day_window.get_current_count()
            stats["current"]["day_remaining"] = self.day_window.get_remaining()

        return stats


class RateLimiterRegistry:
    """
    速率限制器注册表

    管理所有数据源的速率限制器
    """

    # 预定义的数据源速率限制
    DEFAULT_CONFIGS: Dict[str, RateLimitConfig] = {
        "binance": RateLimitConfig(
            requests_per_second=10,  # 保守估计
            requests_per_minute=1200,  # Binance: 1200/min
            burst_size=20,
        ),
        "coingecko": RateLimitConfig(
            requests_per_second=10,  # 免费版限制
            requests_per_minute=50,  # CoinGecko免费版：50/min
        ),
        "defillama": RateLimitConfig(
            requests_per_second=5,  # DefiLlama没有明确限制，保守配置
            requests_per_minute=150,
        ),
        "cryptopanic": RateLimitConfig(
            requests_per_minute=60,  # 免费版限制
            requests_per_day=3000,  # 免费版每天3000次
        ),
        "brave_search": RateLimitConfig(
            requests_per_month=2000,  # 免费版每月2000次
        ),
    }

    def __init__(self):
        """初始化速率限制器注册表"""
        self._limiters: Dict[str, RateLimiter] = {}

    def register(
        self,
        name: str,
        config: Optional[RateLimitConfig] = None,
    ) -> RateLimiter:
        """
        注册速率限制器

        Args:
            name: 数据源名称
            config: 速率限制配置（如果不提供，使用默认配置）

        Returns:
            RateLimiter实例
        """
        if config is None:
            config = self.DEFAULT_CONFIGS.get(name, RateLimitConfig())

        limiter = RateLimiter(name, config)
        self._limiters[name] = limiter

        logger.info(
            "rate_limiter_registered",
            name=name,
        )

        return limiter

    def get(self, name: str) -> Optional[RateLimiter]:
        """获取速率限制器"""
        return self._limiters.get(name)

    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有限制器的统计信息"""
        return {name: limiter.get_stats() for name, limiter in self._limiters.items()}


# 全局速率限制器注册表
global_rate_limiter_registry = RateLimiterRegistry()
