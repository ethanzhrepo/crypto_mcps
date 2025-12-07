"""
数据源注册表与Fallback链管理
"""
import time
from typing import Any, Dict, List, Optional, Tuple

from src.core.models import DataSourcePriority, SourceMeta
from src.data_sources.base import BaseDataSource
from src.middleware.cache import cache_manager
from src.utils.config import config
from src.utils.exceptions import AllSourcesFailedError, DataSourceError
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataSourceRegistry:
    """数据源注册表"""

    def __init__(self):
        self._sources: Dict[str, BaseDataSource] = {}

    def register(self, name: str, source: BaseDataSource):
        """
        注册数据源

        Args:
            name: 数据源名称
            source: 数据源实例
        """
        self._sources[name] = source
        logger.info(f"Data source registered: {name}")

    def get_source(self, name: str) -> Optional[BaseDataSource]:
        """
        获取数据源实例

        Args:
            name: 数据源名称

        Returns:
            数据源实例，不存在返回None
        """
        return self._sources.get(name)

    def get_fallback_chain(
        self,
        tool_name: str,
        capability: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """
        获取fallback链配置

        Args:
            tool_name: 工具名称（如 crypto_overview）
            capability: 能力类型（如 basic, market）

        Returns:
            [(source_name, config), ...] 按优先级排序
        """
        sources_config = config.get_data_source_config(tool_name, capability)

        # 过滤出已注册的数据源
        chain = []
        for source_cfg in sources_config:
            source_name = source_cfg.get("name")
            if source_name in self._sources:
                chain.append((source_name, source_cfg))
            else:
                logger.warning(
                    f"Data source '{source_name}' configured but not registered",
                    tool=tool_name,
                    capability=capability,
                )

        return chain

    async def fetch_with_fallback(
        self,
        tool_name: str,
        capability: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data_type: str = "default",
    ) -> Tuple[Dict[str, Any], SourceMeta]:
        """
        使用fallback链获取数据

        流程：
        1. 检查缓存
        2. 按优先级尝试每个数据源
        3. 第一个成功的数据源返回
        4. 所有失败则抛出异常

        Args:
            tool_name: 工具名称
            capability: 能力类型
            endpoint: API端点
            params: 查询参数
            data_type: 数据类型

        Returns:
            (数据, SourceMeta)

        Raises:
            AllSourcesFailedError: 所有数据源都失败
        """
        params = params or {}

        # 1. 检查缓存
        cache_key = cache_manager.build_cache_key(tool_name, capability, params)
        cached_data = await cache_manager.get(cache_key)

        if cached_data:
            logger.info(
                "Returning cached data",
                tool=tool_name,
                capability=capability,
                cache_key=cache_key,
            )
            # 从缓存返回时，SourceMeta可能也在缓存中
            if isinstance(cached_data, dict) and "data" in cached_data and "source_meta" in cached_data:
                return cached_data["data"], SourceMeta(**cached_data["source_meta"])
            else:
                # 旧格式缓存，无SourceMeta
                return cached_data, None

        # 2. 获取fallback链
        chain = self.get_fallback_chain(tool_name, capability)

        if not chain:
            raise AllSourcesFailedError(
                capability,
                {"error": f"No data sources configured for {tool_name}:{capability}"}
            )

        # 3. 依次尝试每个数据源
        errors = {}

        for idx, (source_name, source_config) in enumerate(chain):
            source = self._sources.get(source_name)
            if not source:
                continue

            is_primary = idx == 0
            ttl_seconds = config.get_ttl(tool_name, capability)

            try:
                logger.info(
                    f"Fetching from {source_name}",
                    tool=tool_name,
                    capability=capability,
                    priority=source_config.get("priority"),
                    is_primary=is_primary,
                )

                start_time = time.time()

                # 调用数据源
                data, source_meta = await source.fetch(
                    endpoint=endpoint,
                    params=params,
                    data_type=data_type,
                    ttl_seconds=ttl_seconds,
                )

                response_time = (time.time() - start_time) * 1000

                # 如果使用了fallback，标记为降级
                if not is_primary:
                    source_meta.degraded = True
                    source_meta.fallback_used = chain[0][0]  # 记录原本应该用的主源

                logger.info(
                    f"Successfully fetched from {source_name}",
                    tool=tool_name,
                    capability=capability,
                    response_time_ms=response_time,
                    degraded=source_meta.degraded,
                )

                # 缓存结果
                cache_data = {
                    "data": data,
                    "source_meta": source_meta.model_dump(),
                }
                await cache_manager.set(cache_key, cache_data, ttl=ttl_seconds)

                return data, source_meta

            except DataSourceError as e:
                errors[source_name] = str(e)
                logger.warning(
                    f"Data source {source_name} failed",
                    tool=tool_name,
                    capability=capability,
                    error=str(e),
                )
                continue

            except Exception as e:
                errors[source_name] = f"Unexpected error: {str(e)}"
                logger.error(
                    f"Unexpected error from {source_name}",
                    tool=tool_name,
                    capability=capability,
                    error=str(e),
                )
                continue

        # 4. 所有数据源都失败
        raise AllSourcesFailedError(capability, errors)

    async def close_all(self):
        """关闭所有数据源连接"""
        for name, source in self._sources.items():
            try:
                await source.close()
                logger.info(f"Data source closed: {name}")
            except Exception as e:
                logger.error(f"Failed to close {name}", error=str(e))


# 全局注册表实例
registry = DataSourceRegistry()
