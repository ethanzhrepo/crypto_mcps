"""
Redis缓存管理器
"""
import hashlib
import json
from typing import Any, Optional

from redis.asyncio import Redis

from src.utils.config import config
from src.utils.exceptions import CacheError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Redis缓存管理器"""

    def __init__(self, redis_url: Optional[str] = None):
        """
        初始化缓存管理器

        Args:
            redis_url: Redis连接URL，默认从配置读取
        """
        self.redis_url = redis_url or config.settings.redis_url
        self._redis: Optional[Redis] = None

    async def _get_redis(self) -> Redis:
        """获取Redis连接（懒加载）"""
        if self._redis is None:
            try:
                self._redis = Redis.from_url(
                    self.redis_url,
                    max_connections=config.settings.redis_max_connections,
                    decode_responses=True,
                )
                # 测试连接
                await self._redis.ping()
                logger.info("Redis connection established", url=self.redis_url)
            except Exception as e:
                logger.error("Failed to connect to Redis", error=str(e))
                raise CacheError(f"Redis connection failed: {e}")
        return self._redis

    async def close(self):
        """关闭Redis连接"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis connection closed")

    @staticmethod
    def build_cache_key(tool_name: str, capability: str, params: dict) -> str:
        """
        构建缓存键

        格式: tool_name:capability:symbol:params_hash
        例如: crypto_overview:market:BTC:a1b2c3d4

        Args:
            tool_name: 工具名称
            capability: 能力类型
            params: 参数字典

        Returns:
            缓存键字符串
        """
        # 提取symbol（如果有）
        symbol = params.get("symbol", "")

        # 生成参数hash
        params_str = json.dumps(params, sort_keys=True, default=str)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]

        if symbol:
            return f"{tool_name}:{capability}:{symbol.upper()}:{params_hash}"
        else:
            return f"{tool_name}:{capability}:{params_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存的数据，不存在返回None
        """
        if not config.settings.enable_cache:
            return None

        try:
            redis = await self._get_redis()
            data = await redis.get(key)

            if data:
                logger.debug("Cache hit", key=key)
                return json.loads(data)
            else:
                logger.debug("Cache miss", key=key)
                return None

        except Exception as e:
            logger.warning("Cache get failed", key=key, error=str(e))
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 要缓存的数据
            ttl: 过期时间（秒），None表示永不过期

        Returns:
            是否成功
        """
        if not config.settings.enable_cache:
            return False

        try:
            redis = await self._get_redis()
            serialized = json.dumps(value, default=str)

            if ttl:
                await redis.setex(key, ttl, serialized)
            else:
                await redis.set(key, serialized)

            logger.debug("Cache set", key=key, ttl=ttl)
            return True

        except Exception as e:
            logger.warning("Cache set failed", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        try:
            redis = await self._get_redis()
            result = await redis.delete(key)
            logger.debug("Cache deleted", key=key, deleted=result > 0)
            return result > 0

        except Exception as e:
            logger.warning("Cache delete failed", key=key, error=str(e))
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        批量删除匹配模式的缓存

        Args:
            pattern: Redis键模式，如 "crypto_overview:*"

        Returns:
            删除的键数量
        """
        try:
            redis = await self._get_redis()
            keys = await redis.keys(pattern)

            if keys:
                deleted = await redis.delete(*keys)
                logger.info("Cache invalidated", pattern=pattern, count=deleted)
                return deleted

            return 0

        except Exception as e:
            logger.warning("Cache invalidation failed", pattern=pattern, error=str(e))
            return 0

    async def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        try:
            redis = await self._get_redis()
            return await redis.exists(key) > 0
        except Exception as e:
            logger.warning("Cache exists check failed", key=key, error=str(e))
            return False

    async def get_ttl(self, key: str) -> Optional[int]:
        """
        获取缓存剩余TTL

        Args:
            key: 缓存键

        Returns:
            剩余秒数，-1表示永不过期，None表示不存在
        """
        try:
            redis = await self._get_redis()
            ttl = await redis.ttl(key)

            if ttl == -2:  # 键不存在
                return None
            elif ttl == -1:  # 永不过期
                return -1
            else:
                return ttl

        except Exception as e:
            logger.warning("Get TTL failed", key=key, error=str(e))
            return None

    async def clear_all(self) -> bool:
        """
        清空所有缓存（危险操作，仅用于测试）

        Returns:
            是否成功
        """
        try:
            redis = await self._get_redis()
            await redis.flushdb()
            logger.warning("All cache cleared (FLUSHDB)")
            return True
        except Exception as e:
            logger.error("Clear all cache failed", error=str(e))
            return False


# 全局缓存管理器实例
cache_manager = CacheManager()
