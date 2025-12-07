"""
CacheManager单元测试
"""
import pytest

from src.middleware.cache import CacheManager


@pytest.mark.unit
class TestCacheManager:
    """CacheManager测试"""

    @pytest.fixture
    async def cache(self, mock_redis):
        """创建缓存管理器实例"""
        manager = CacheManager()
        manager._redis = mock_redis
        return manager

    def test_build_cache_key(self):
        """测试缓存键构建"""
        key = CacheManager.build_cache_key(
            "crypto_overview",
            "market",
            {"symbol": "BTC", "vs_currency": "usd"}
        )

        assert "crypto_overview" in key
        assert "market" in key
        assert "BTC" in key
        assert len(key.split(":")) == 4  # tool:capability:symbol:hash

    def test_build_cache_key_without_symbol(self):
        """测试无symbol的缓存键"""
        key = CacheManager.build_cache_key(
            "macro_hub",
            "series",
            {"series_ids": ["CPIAUCSL"]}
        )

        assert "macro_hub" in key
        assert "series" in key
        assert len(key.split(":")) == 3  # tool:capability:hash

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache):
        """测试缓存未命中"""
        result = await cache.get("non_existent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache, mock_redis):
        """测试缓存命中"""
        import json

        test_data = {"price": 95000}
        mock_redis.get.return_value = json.dumps(test_data)

        result = await cache.get("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_set_cache(self, cache, mock_redis):
        """测试设置缓存"""
        test_data = {"price": 95000}

        result = await cache.set("test_key", test_data, ttl=60)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_cache(self, cache, mock_redis):
        """测试删除缓存"""
        mock_redis.delete.return_value = 1

        result = await cache.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache, mock_redis):
        """测试模式匹配删除"""
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3

        count = await cache.invalidate_pattern("crypto_overview:*")

        assert count == 3
        mock_redis.keys.assert_called_once_with("crypto_overview:*")
        mock_redis.delete.assert_called_once_with("key1", "key2", "key3")
