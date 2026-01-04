"""
DefiLlama API客户端

提供DeFi协议数据：
- TVL (Total Value Locked)
- 协议费用和收入
- 稳定币统计
- CEX储备（交易所资产）
- 桥接资产
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource
from src.middleware.cache import cache_manager
from src.utils.config import config


class DefiLlamaClient(BaseDataSource):
    """DefiLlama API客户端"""

    BASE_URL = "https://api.llama.fi"
    COINS_URL = "https://coins.llama.fi"  # Coins/Prices endpoints
    STABLECOINS_URL = "https://stablecoins.llama.fi"
    BRIDGES_URL = "https://bridges.llama.fi"
    YIELDS_URL = "https://yields.llama.fi"

    def __init__(self):
        """初始化DefiLlama客户端（无需API key）"""
        super().__init__(
            name="defillama",
            base_url=self.BASE_URL,
            timeout=60.0,  # 增加超时时间以应对慢速API响应
            requires_api_key=False,
        )

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "accept": "application/json",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    # ==================== Coins/Prices API (Contract Address Support) ====================

    async def get_current_prices(
        self, coins: str, search_width: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取代币当前价格（支持合约地址查询）

        Args:
            coins: 逗号分隔的代币列表，格式为 "chain:address"
                  例如: "ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
                  支持多个: "ethereum:0x...,bsc:0x..."
            search_width: 价格查找时间范围 ("4h", "24h")

        Returns:
            (价格数据, 元信息)

        Example Response:
            {
                "coins": {
                    "ethereum:0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": {
                        "decimals": 6,
                        "symbol": "USDC",
                        "price": 0.999,
                        "timestamp": 1640995200,
                        "confidence": 0.99
                    }
                }
            }
        """
        endpoint = f"/prices/current/{coins}"
        params = {}
        if search_width:
            params["searchWidth"] = search_width

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="current_prices",
            ttl_seconds=60,  # 1分钟缓存（实时价格）
            base_url_override=self.COINS_URL,
        )

    async def get_historical_prices(
        self, timestamp: int, coins: str, search_width: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取代币历史价格

        Args:
            timestamp: Unix时间戳
            coins: 逗号分隔的代币列表 "chain:address"
            search_width: 搜索范围（秒）

        Returns:
            (历史价格数据, 元信息)
        """
        endpoint = f"/prices/historical/{timestamp}/{coins}"
        params = {}
        if search_width:
            params["searchWidth"] = search_width

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="historical_prices",
            ttl_seconds=86400,  # 24小时缓存（历史数据不变）
            base_url_override=self.COINS_URL,
        )

    async def get_price_chart(
        self,
        coins: str,
        period: Optional[str] = None,
        span: Optional[int] = None,
        search_width: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取价格图表数据

        Args:
            coins: 逗号分隔的代币列表 "chain:address"
            period: 时间周期 ("1d", "7d", "30d", "90d", "180d", "365d")
            span: 数据点间隔（小时）
            search_width: 搜索宽度

        Returns:
            (价格图表数据, 元信息)
        """
        endpoint = f"/chart/{coins}"
        params = {}
        if period:
            params["period"] = period
        if span:
            params["span"] = span
        if search_width:
            params["searchWidth"] = search_width

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="price_chart",
            ttl_seconds=3600,  # 1小时缓存
            base_url_override=self.COINS_URL,
        )

    async def get_batch_historical_prices(
        self, coins_dict: Dict[str, List[int]]
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        批量获取历史价格

        Args:
            coins_dict: 代币和时间戳映射
                       例如: {
                           "ethereum:0x...": [1640995200, 1641081600],
                           "bsc:0x...": [1640995200]
                       }

        Returns:
            (批量历史价格数据, 元信息)
        """
        endpoint = "/batchHistorical"

        # 使用POST请求
        raw_data = await self._make_request(
            "POST",
            endpoint,
            data={"coins": coins_dict},
            base_url_override=self.COINS_URL
        )

        meta = SourceMeta(
            provider="defillama",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=86400,  # 24小时缓存
        )

        return raw_data, meta

    async def get_price_percentage(
        self,
        coins: str,
        timestamp: Optional[int] = None,
        look_forward: Optional[bool] = None,
        period: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取价格变化百分比

        Args:
            coins: 逗号分隔的代币列表 "chain:address"
            timestamp: 参考时间戳
            look_forward: 是否向前查找
            period: 时间周期

        Returns:
            (价格变化数据, 元信息)
        """
        endpoint = f"/percentage/{coins}"
        params = {}
        if timestamp:
            params["timestamp"] = timestamp
        if look_forward is not None:
            params["lookForward"] = str(look_forward).lower()
        if period:
            params["period"] = period

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="price_percentage",
            ttl_seconds=300,  # 5分钟缓存
            base_url_override=self.COINS_URL,
        )

    async def get_first_price(
        self, coins: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取首次记录的价格

        Args:
            coins: 逗号分隔的代币列表 "chain:address"

        Returns:
            (首次价格数据, 元信息)
        """
        endpoint = f"/prices/first/{coins}"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="first_price",
            ttl_seconds=604800,  # 7天缓存（历史数据不变）
            base_url_override=self.COINS_URL,
        )

    async def get_block_at_timestamp(
        self, chain: str, timestamp: int
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取指定时间戳对应的区块高度

        Args:
            chain: 区块链标识符
            timestamp: Unix时间戳

        Returns:
            (区块信息, 元信息)
        """
        endpoint = f"/block/{chain}/{timestamp}"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="block_info",
            ttl_seconds=86400,  # 24小时缓存（区块数据不变）
            base_url_override=self.COINS_URL,
        )

    # ==================== 公共方法 ====================

    async def get_protocol_tvl(
        self, protocol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取协议TVL（优先使用轻量级summary端点，避免超大历史数据响应）

        Args:
            protocol: 协议slug，如 uniswap, aave

        Returns:
            (TVL数据, 元信息)
        """
        protocol_slug = protocol.lower()

        # 从配置读取summary缓存TTL（默认1小时，可在ttl_policies.yaml中调整）
        summary_ttl = config.get_ttl("defillama_protocols", "protocols_summary")

        # 1) 首选 /protocols summary 列表（约几 MB，包含当前 TVL 和链上分布），并通过Redis缓存
        cache_key = cache_manager.build_cache_key(
            "defillama_protocols", "protocols_summary", {}
        )
        summary_data: Optional[Any] = None
        meta: Optional[SourceMeta] = None

        cached = await cache_manager.get(cache_key)
        if cached:
            # 统一采用新格式缓存: {"data": [...], "meta": {...}}
            if isinstance(cached, dict) and "data" in cached:
                summary_data = cached["data"]
                meta_dict = cached.get("meta")
                if meta_dict:
                    try:
                        meta = SourceMeta(**meta_dict)
                    except Exception:
                        meta = None

        if summary_data is None:
            summary_data, meta = await self.fetch(
                endpoint="/protocols",
                params={},
                data_type="protocols_summary",
                ttl_seconds=summary_ttl,
            )

            # 写入缓存（忽略失败）
            if meta is not None:
                cache_payload = {
                    "data": summary_data,
                    "meta": meta.model_dump()
                    if hasattr(meta, "model_dump")
                    else meta.__dict__,
                }
            else:
                cache_payload = {"data": summary_data}
            await cache_manager.set(cache_key, cache_payload, ttl=summary_ttl)

        if isinstance(summary_data, list):
            # 尝试三种匹配方式：
            #   - 直接 slug == protocol_slug (如 aave-v3)
            #   - parentProtocolSlug == protocol_slug (如 uniswap, aave)
            #   - 名称精确匹配（兜底）
            exact_slug = [
                p
                for p in summary_data
                if (p.get("slug") or "").lower() == protocol_slug
            ]
            parent_children = [
                p
                for p in summary_data
                if (p.get("parentProtocolSlug") or "").lower() == protocol_slug
            ]
            exact_name = [
                p
                for p in summary_data
                if (p.get("name") or "").lower() == protocol_slug
            ]

            if parent_children:
                target_protocols = parent_children
                protocol_name = protocol
            elif exact_slug:
                target_protocols = exact_slug
                protocol_name = exact_slug[0].get("name", protocol)
            elif exact_name:
                target_protocols = exact_name
                protocol_name = exact_name[0].get("name", protocol)
            else:
                target_protocols = []
                protocol_name = protocol

            if target_protocols:
                # 聚合当前TVL
                total_tvl = float(
                    sum(float(p.get("tvl") or 0) for p in target_protocols)
                )

                # 聚合链上分布（跳过 *-borrowed / borrowed / staking 等非纯TVL维度）
                chain_breakdown: Dict[str, float] = {}
                skip_keys = {"borrowed", "staking", "pool2"}
                for p in target_protocols:
                    for chain, value in (p.get("chainTvls") or {}).items():
                        if (
                            not isinstance(value, (int, float))
                            or chain in skip_keys
                            or chain.endswith("-borrowed")
                        ):
                            continue
                        chain_breakdown[chain] = chain_breakdown.get(chain, 0.0) + float(
                            value
                        )

                # 使用TVL加权方式近似聚合24h/7d变化（原数据为百分比）
                def _weighted_change(key: str) -> float:
                    if total_tvl <= 0:
                        return 0.0
                    numerator = 0.0
                    for p in target_protocols:
                        tvl = float(p.get("tvl") or 0)
                        change = float(p.get(key) or 0.0)
                        numerator += tvl * change
                    return numerator / total_tvl

                change_24h = _weighted_change("change_1d")
                change_7d = _weighted_change("change_7d")

                result = {
                    "protocol": protocol_name,
                    "tvl_usd": total_tvl,
                    "tvl_change_24h": change_24h,
                    "tvl_change_7d": change_7d,
                    "chain_breakdown": chain_breakdown or None,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }

                # 如果meta为空（缓存命中但未能还原），构造一个轻量SourceMeta
                if meta is None:
                    meta = SourceMeta(
                        provider="defillama",
                        endpoint="/protocols",
                        as_of_utc=datetime.utcnow().isoformat() + "Z",
                        ttl_seconds=summary_ttl,
                        response_time_ms=None,
                    )

                return result, meta

        # 2) 回退到历史TVL端点（数据量巨大，仅在summary无法匹配时使用）
        endpoint = f"/protocol/{protocol}"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="protocol_tvl",
            ttl_seconds=config.get_ttl("defillama_protocols", "protocol_tvl"),
        )

    async def get_protocol_fees(
        self, protocol: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取协议费用和收入

        Args:
            protocol: 协议名称

        Returns:
            (费用数据, 元信息)
        """
        endpoint = f"/summary/fees/{protocol}"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="protocol_fees",
            ttl_seconds=3600,  # 1小时缓存
        )

    async def get_stablecoins(self) -> tuple[List[Dict], SourceMeta]:
        """
        获取所有稳定币统计

        Returns:
            (稳定币列表, 元信息)
        """
        endpoint = "/stablecoins"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="stablecoins",
            ttl_seconds=1800,  # 30分钟缓存
            base_url_override=self.STABLECOINS_URL,
        )

    async def get_cex_all(self) -> tuple[List[Dict], SourceMeta]:
        """
        获取所有CEX储备数据

        Returns:
            (CEX列表, 元信息)
        """
        endpoint = "/protocols"
        params = {"category": "CEX"}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="cex_list",
            ttl_seconds=600,  # 10分钟缓存
        )

        return data, meta

    async def get_cex_reserves(
        self, exchange: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取CEX储备数据（交易所钱包余额）

        Args:
            exchange: 交易所名称（如 'binance', 'coinbase'）
                     如果为None，返回所有交易所汇总

        Returns:
            (储备数据, 元信息)

        Note:
            DefiLlama通过追踪已知交易所钱包地址来估算储备
        """
        if exchange:
            # 获取特定交易所
            endpoint = f"/protocol/{exchange}"
            data_type = "cex_single"
        else:
            # 获取所有CEX（按类别）
            endpoint = "/protocols"
            data_type = "cex_all"

        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type=data_type,
            ttl_seconds=600,  # 10分钟缓存
        )

    async def get_bridge_volumes(
        self, bridge: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取跨链桥交易量

        Args:
            bridge: 桥名称（可选）

        Returns:
            (桥接数据, 元信息)
        """
        if bridge:
            endpoint = f"/bridge/{bridge}"
        else:
            endpoint = "/bridges"

        return await self.fetch(
            endpoint=endpoint,
            params={},
            data_type="bridge",
            ttl_seconds=1800,  # 30分钟
            base_url_override=self.BRIDGES_URL,
        )

    async def get_yields(
        self, symbol: Optional[str] = None, protocol: Optional[str] = None
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取借贷收益率数据

        Note: 此端点可能需要 Pro API key

        Args:
            symbol: 资产符号过滤（如 ETH, USDC）
            protocol: 协议名称过滤（如 aave, compound）

        Returns:
            (收益率数据列表, 元信息)
        """
        endpoint = "/pools"

        data, meta = await self.fetch(
            endpoint=endpoint,
            params={},
            data_type="yields",
            ttl_seconds=300,  # 5分钟缓存
            base_url_override=self.YIELDS_URL,
        )

        # 过滤数据
        if isinstance(data, list):
            filtered = data
            if symbol:
                symbol_upper = symbol.upper()
                filtered = [
                    p for p in filtered
                    if symbol_upper in p.get("symbol", "").upper()
                ]
            if protocol:
                protocol_lower = protocol.lower()
                filtered = [
                    p for p in filtered
                    if protocol_lower in p.get("project", "").lower()
                ]
            return filtered[:50], meta  # 限制返回数量

        return data, meta

    async def get_borrow_rates(
        self, symbol: str
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取特定资产的借贷利率

        Args:
            symbol: 资产符号（如 ETH, USDC, BTC）

        Returns:
            (借贷利率数据列表, 元信息)
        """
        data, meta = await self.get_yields(symbol=symbol)

        # 转换为标准借贷利率格式
        borrow_rates = []
        for pool in data:
            # 只选择lending类型的池子
            if pool.get("category") in ["lending", "Lending"]:
                borrow_rates.append({
                    "asset": pool.get("symbol", symbol),
                    "exchange": pool.get("project", "unknown"),
                    "chain": pool.get("chain", "unknown"),
                    "apy_base": pool.get("apyBase", 0),  # 基础APY
                    "apy_reward": pool.get("apyReward", 0),  # 奖励APY
                    "apy_total": pool.get("apy", 0),  # 总APY
                    "tvl_usd": pool.get("tvlUsd", 0),
                    "pool_id": pool.get("pool", ""),
                    # 转换为借贷利率格式
                    "hourly_rate": (pool.get("apy", 0) / 100) / 8760,
                    "daily_rate": (pool.get("apy", 0) / 100) / 365,
                    "annual_rate": pool.get("apy", 0) / 100,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })

        return borrow_rates, meta

    # ==================== 数据转换方法 ====================

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """
        转换原始数据为标准格式

        Args:
            raw_data: DefiLlama API原始响应
            data_type: 数据类型

        Returns:
            标准化数据
        """
        # Price-related data types - return as-is (already in good format)
        if data_type in ["current_prices", "historical_prices", "price_chart",
                         "price_percentage", "first_price", "block_info"]:
            return raw_data

        # Existing transformations
        if data_type == "protocol_tvl":
            return self._transform_protocol_tvl(raw_data)
        elif data_type == "protocol_fees":
            return self._transform_protocol_fees(raw_data)
        elif data_type == "stablecoins":
            return self._transform_stablecoins(raw_data)
        elif data_type == "cex_list":
            return self._transform_cex_list(raw_data)
        elif data_type == "cex_single":
            return self._transform_cex_single(raw_data)
        elif data_type == "cex_all":
            return self._transform_cex_all(raw_data)
        elif data_type == "bridge":
            return self._transform_bridge(raw_data)
        elif data_type == "yields":
            return self._transform_yields(raw_data)
        else:
            return raw_data

    def _transform_protocol_tvl(self, data: Dict) -> Dict:
        """转换协议TVL数据"""
        tvl_field = data.get("tvl")

        # 支持两种格式：
        #  - 历史序列: [{"date": ..., "totalLiquidityUSD": ...}, ...]
        #  - 直接数值: 123456.0
        if isinstance(tvl_field, list):
            current_tvl = tvl_field[-1] if tvl_field else {}
            current_value = current_tvl.get("totalLiquidityUSD", 0)

            tvl_series = tvl_field
            tvl_24h_ago = tvl_series[-2] if len(tvl_series) >= 2 else {}
            tvl_7d_ago = tvl_series[-8] if len(tvl_series) >= 8 else {}

            tvl_24h = tvl_24h_ago.get("totalLiquidityUSD", current_value)
            tvl_7d = tvl_7d_ago.get("totalLiquidityUSD", current_value)
        elif isinstance(tvl_field, (int, float)):
            current_value = float(tvl_field)
            tvl_24h = current_value
            tvl_7d = current_value
        else:
            current_value = 0.0
            tvl_24h = 0.0
            tvl_7d = 0.0

        change_24h = ((current_value - tvl_24h) / tvl_24h * 100) if tvl_24h > 0 else 0.0
        change_7d = ((current_value - tvl_7d) / tvl_7d * 100) if tvl_7d > 0 else 0.0

        # 链上分布
        chain_tvls = data.get("chainTvls", {})
        chain_breakdown = {}
        for chain, value in chain_tvls.items():
            if isinstance(value, dict):
                chain_breakdown[chain] = value.get("tvl", 0)
            else:
                chain_breakdown[chain] = value

        return {
            "protocol": data.get("name", data.get("slug", "unknown")),
            "tvl_usd": current_value,
            "tvl_change_24h": change_24h,
            "tvl_change_7d": change_7d,
            "chain_breakdown": chain_breakdown,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _transform_protocol_fees(self, data: Dict) -> Dict:
        """转换协议费用数据"""
        total_data = data.get("total", {})

        return {
            "protocol": data.get("name", "unknown"),
            "fees_24h": total_data.get("fees_24h", 0),
            "revenue_24h": total_data.get("revenue_24h", 0),
            "fees_7d": total_data.get("fees_7d", 0),
            "revenue_7d": total_data.get("revenue_7d", 0),
            "fees_30d": total_data.get("fees_30d", 0),
            "revenue_30d": total_data.get("revenue_30d", 0),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _transform_stablecoins(self, data: Dict) -> List[Dict]:
        """转换稳定币数据"""
        pegged_assets = data.get("peggedAssets", [])
        result = []

        for asset in pegged_assets[:10]:  # 只返回前10个
            chains = {}
            for chain_data in asset.get("chainCirculating", {}).values():
                if isinstance(chain_data, dict):
                    for chain_name, value in chain_data.items():
                        if isinstance(value, (int, float)):
                            chains[chain_name] = value

            result.append(
                {
                    "stablecoin": asset.get("name", "unknown"),
                    "total_supply": asset.get("circulating", {}).get("peggedUSD", 0),
                    "market_cap": asset.get("circulating", {}).get("peggedUSD", 0),
                    "chains": chains,
                    "dominance": None,  # 需要额外计算
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )

        return result

    def _transform_cex_list(self, data: List[Dict]) -> List[Dict]:
        """转换CEX列表数据"""
        result = []
        for cex in data:
            if cex.get("category") == "CEX":
                result.append({
                    "name": cex.get("name"),
                    "slug": cex.get("slug"),
                    "tvl_usd": cex.get("tvl", 0),
                    "change_1h": cex.get("change_1h", 0),
                    "change_24h": cex.get("change_1d", 0),
                    "change_7d": cex.get("change_7d", 0),
                })
        return result

    def _transform_cex_single(self, data: Dict) -> Dict:
        """转换单个CEX储备数据"""
        # 类似protocol_tvl的转换
        current_tvl_data = data.get("tvl", [{}])[-1] if data.get("tvl") else {}
        current_tvl = current_tvl_data.get("totalLiquidityUSD", 0)

        # 获取链上分布
        chain_tvls = data.get("chainTvls", {})
        token_breakdown = {}

        # DefiLlama的tokens字段包含各资产持仓
        if "tokens" in data:
            for token_data in data["tokens"]:
                symbol = token_data.get("symbol", "unknown")
                balance = token_data.get("balance", 0)
                price = token_data.get("price", 0)
                token_breakdown[symbol] = {
                    "balance": balance,
                    "value_usd": balance * price,
                }

        return {
            "exchange": data.get("name", data.get("slug", "unknown")),
            "total_reserves_usd": current_tvl,
            "token_breakdown": token_breakdown,
            "chain_distribution": chain_tvls,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _transform_cex_all(self, data: List[Dict]) -> Dict:
        """转换所有CEX汇总数据"""
        cex_data = [p for p in data if p.get("category") == "CEX"]

        total_tvl = sum(cex.get("tvl", 0) for cex in cex_data)

        exchanges = []
        for cex in sorted(cex_data, key=lambda x: x.get("tvl", 0), reverse=True)[:10]:
            exchanges.append({
                "name": cex.get("name"),
                "tvl_usd": cex.get("tvl", 0),
                "change_24h": cex.get("change_1d", 0),
                "market_share": (cex.get("tvl", 0) / total_tvl * 100) if total_tvl > 0 else 0,
            })

        return {
            "total_cex_reserves_usd": total_tvl,
            "exchange_count": len(cex_data),
            "top_exchanges": exchanges,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def _transform_bridge(self, data: Any) -> Dict:
        """转换桥接数据"""
        if isinstance(data, list):
            # 所有桥列表
            bridges = []
            for bridge in data[:10]:
                bridges.append({
                    "name": bridge.get("displayName", bridge.get("name", "unknown")),
                    "volume_24h": bridge.get("volume24h", 0),
                    "volume_7d": bridge.get("volume7d", 0),
                    "volume_30d": bridge.get("volume30d", 0),
                })
            return {"bridges": bridges, "count": len(bridges)}
        else:
            # 单个桥
            return {
                "bridge": data.get("displayName", data.get("name", "unknown")),
                "volume_24h": data.get("volume24h", 0),
                "volume_7d": data.get("volume7d", 0),
                "chains": list(data.get("chainBreakdown", {}).keys()),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

    def _transform_yields(self, data: Any) -> List[Dict]:
        """转换yields数据"""
        if not isinstance(data, dict) or "data" not in data:
            # 如果直接返回列表
            if isinstance(data, list):
                return data
            return []

        # yields.llama.fi返回 {"status": "success", "data": [...]}
        return data.get("data", [])

    # ==================== 新增方法 ====================

    async def get_chain_tvl(
        self, chain: str
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取特定链的历史TVL数据

        Args:
            chain: 链名称（如 Ethereum, BSC, Arbitrum）

        Returns:
            (链TVL数据, 元信息)
        """
        endpoint = f"/v2/historicalChainTvl/{chain}"
        params = {}

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="chain_tvl",
            ttl_seconds=300,  # 5分钟缓存
        )

        # 转换数据
        if isinstance(data, list) and len(data) > 0:
            # 获取最新的TVL值
            latest = data[-1]
            tvl_24h_ago = data[-2] if len(data) >= 2 else data[-1]

            current_tvl = latest.get("tvl", 0)
            tvl_24h = tvl_24h_ago.get("tvl", current_tvl)
            change_24h = ((current_tvl - tvl_24h) / tvl_24h * 100) if tvl_24h > 0 else 0

            result = {
                "chain": chain,
                "tvl_usd": current_tvl,
                "tvl_change_24h": change_24h,
                "data_points": len(data),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        else:
            result = {
                "chain": chain,
                "tvl_usd": 0,
                "tvl_change_24h": 0,
                "data_points": 0,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

        return result, meta

    async def get_dex_volumes(
        self, chain: Optional[str] = None
    ) -> tuple[Dict[str, Any], SourceMeta]:
        """
        获取DEX交易量数据

        Args:
            chain: 链名称（可选，如果不指定则返回所有链的汇总）

        Returns:
            (DEX交易量数据, 元信息)
        """
        if chain:
            endpoint = f"/overview/dexs/{chain}"
        else:
            endpoint = "/overview/dexs"

        params = {
            "excludeTotalDataChart": "true",
            "excludeTotalDataChartBreakdown": "true",
        }

        raw_data = await self.fetch_raw(endpoint, params)

        meta = SourceMeta(
            provider="defillama",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,  # 5分钟缓存
        )

        # 转换数据
        protocols = raw_data.get("protocols", [])
        total_volume_24h = raw_data.get("total24h", 0)
        total_volume_7d = raw_data.get("total7d", 0)

        # 获取前10个DEX
        top_dexs = []
        for proto in sorted(protocols, key=lambda x: x.get("total24h") or 0, reverse=True)[:10]:
            top_dexs.append({
                "name": proto.get("name", "unknown"),
                "volume_24h": proto.get("total24h") or 0,
                "volume_7d": proto.get("total7d") or 0,
                "change_24h": proto.get("change_1d") or 0,
                "chains": proto.get("chains", []),
            })

        result = {
            "total_volume_24h": total_volume_24h,
            "total_volume_7d": total_volume_7d,
            "change_24h": raw_data.get("change_1d", 0),
            "change_7d": raw_data.get("change_7d", 0),
            "dex_count": len(protocols),
            "top_dexs": top_dexs,
            "chain": chain,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        return result, meta
