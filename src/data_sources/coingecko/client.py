"""
CoinGecko API客户端
"""
from typing import Any, Dict, Optional

from src.core.models import BasicInfo, MarketMetrics, SectorInfo, SocialInfo, SupplyInfo
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoinGeckoClient(BaseDataSource):
    """CoinGecko API客户端"""

    def __init__(self, api_key: Optional[str] = None, api_type: Optional[str] = None):
        from src.utils.config import config

        # 如果没有传入api_key，尝试从config获取
        if not api_key:
            api_key = config.get_api_key("coingecko")

        # 获取API类型（demo或pro）
        if not api_type:
            api_type = getattr(config.settings, "coingecko_api_type", "demo")

        # 根据API类型和key设置URL
        # Demo API: api.coingecko.com + x-cg-demo-api-key
        # Pro API: pro-api.coingecko.com + x-cg-pro-api-key
        self._api_type = api_type.lower() if api_type else "demo"

        if api_key:
            if self._api_type == "pro":
                base_url = "https://pro-api.coingecko.com/api/v3"
            else:
                # Demo API 仍然使用免费API的URL
                base_url = "https://api.coingecko.com/api/v3"
        else:
            base_url = "https://api.coingecko.com/api/v3"

        super().__init__(
            name="coingecko",
            base_url=base_url,
            timeout=10.0,
            requires_api_key=False,  # 免费版不需要API key
        )
        # 覆盖基类设置的api_key，确保与base_url一致
        self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "accept": "application/json",
        }

        # 根据API类型设置正确的header
        if self.api_key:
            if self._api_type == "pro":
                headers["x-cg-pro-api-key"] = self.api_key
            else:
                headers["x-cg-demo-api-key"] = self.api_key

        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: CoinGecko API原始响应
            data_type: 数据类型 (basic, market, supply, social, sector)

        Returns:
            标准化数据字典
        """
        if data_type == "basic":
            return self._transform_basic(raw_data)
        elif data_type == "market":
            return self._transform_market(raw_data)
        elif data_type == "supply":
            return self._transform_supply(raw_data)
        elif data_type == "social":
            return self._transform_social(raw_data)
        elif data_type == "sector":
            return self._transform_sector(raw_data)
        else:
            return raw_data

    def _transform_basic(self, data: Dict) -> Dict:
        """转换基础信息"""
        links = data.get("links", {})
        description = data.get("description", {})

        return {
            "id": data.get("id"),
            "symbol": data.get("symbol", "").upper(),
            "name": data.get("name"),
            "description": description.get("en", "")[:500] if description else None,  # 限制长度
            "homepage": links.get("homepage", [])[:1],  # 只取第一个
            "blockchain_site": links.get("blockchain_site", [])[:3],  # 取前3个
            "contract_address": data.get("contract_address"),
            "chain": data.get("asset_platform_id"),
        }

    def _transform_market(self, data: Dict) -> Dict:
        """转换市场数据"""
        market_data = data.get("market_data", {})
        current_price = market_data.get("current_price", {})
        market_cap = market_data.get("market_cap", {})
        fdv = market_data.get("fully_diluted_valuation", {})
        volume = market_data.get("total_volume", {})
        high_24h = market_data.get("high_24h", {})
        low_24h = market_data.get("low_24h", {})
        ath = market_data.get("ath", {})
        atl = market_data.get("atl", {})

        return {
            "price": current_price.get("usd"),
            "market_cap": market_cap.get("usd"),
            "market_cap_rank": market_data.get("market_cap_rank"),
            "fully_diluted_valuation": fdv.get("usd"),
            "total_volume_24h": volume.get("usd"),
            "high_24h": high_24h.get("usd"),
            "low_24h": low_24h.get("usd"),
            "price_change_24h": market_data.get("price_change_24h"),
            "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
            "ath": ath.get("usd"),
            "atl": atl.get("usd"),
        }

    def _transform_supply(self, data: Dict) -> Dict:
        """转换供应信息"""
        market_data = data.get("market_data", {})

        circulating = market_data.get("circulating_supply")
        total = market_data.get("total_supply")
        max_supply = market_data.get("max_supply")

        # 计算流通占比
        circulating_percent = None
        if circulating and max_supply and max_supply > 0:
            circulating_percent = (circulating / max_supply) * 100

        return {
            "circulating_supply": circulating,
            "total_supply": total,
            "max_supply": max_supply,
            "circulating_percent": circulating_percent,
        }

    def _transform_social(self, data: Dict) -> Dict:
        """转换社交信息"""
        community = data.get("community_data", {})

        return {
            "twitter_followers": community.get("twitter_followers"),
            "reddit_subscribers": community.get("reddit_subscribers"),
            "telegram_members": community.get("telegram_channel_user_count"),
            "discord_members": None,  # CoinGecko不提供Discord数据
        }

    def _transform_sector(self, data: Dict) -> Dict:
        """转换板块信息"""
        categories = data.get("categories", [])

        return {
            "categories": categories,
            "primary_category": categories[0] if categories else None,
        }

    async def get_coin_data(self, symbol: str) -> Dict:
        """
        获取代币完整数据

        Args:
            symbol: 代币符号 (如 BTC, ETH)

        Returns:
            完整的代币数据
        """
        # CoinGecko需要coin_id而不是symbol
        # 先通过search API获取coin_id
        coin_id = await self._symbol_to_id(symbol)

        endpoint = f"/coins/{coin_id}"
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false",
        }

        return await self.fetch_raw(endpoint, params)

    async def _symbol_to_id(self, symbol: str) -> str:
        """
        将symbol转换为CoinGecko的coin_id

        Args:
            symbol: 代币符号

        Returns:
            coin_id
        """
        # 常见币种映射（避免API调用）
        common_mappings = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "USDT": "tether",
            "BNB": "binancecoin",
            "SOL": "solana",
            "USDC": "usd-coin",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "TRX": "tron",
            "AVAX": "avalanche-2",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "ARB": "arbitrum",
            "OP": "optimism",
        }

        symbol_upper = symbol.upper()

        if symbol_upper in common_mappings:
            return common_mappings[symbol_upper]

        # 如果不在映射中，使用search API
        try:
            result = await self.fetch_raw("/search", {"query": symbol})
            coins = result.get("coins", [])

            if not coins:
                raise ValueError(f"Symbol '{symbol}' not found on CoinGecko")

            # 返回第一个匹配（通常是最准确的）
            return coins[0]["id"]

        except Exception as e:
            logger.error(f"Failed to resolve symbol {symbol}", error=str(e))
            # 降级：直接用小写symbol作为id（可能不准确）
            return symbol.lower()

    async def get_categories(
        self,
    ) -> tuple[Any, Any]:
        """
        获取所有分类（板块）

        Returns:
            (分类列表, SourceMeta)
        """
        endpoint = "/coins/categories"
        params = {"order": "market_cap_desc"}  # 按市值排序

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="categories",
            ttl_seconds=3600,  # 1小时缓存
        )

    async def get_category_detail(
        self, category_id: str
    ) -> tuple[Any, Any]:
        """
        获取特定分类详情

        Args:
            category_id: 分类ID，如 'decentralized-finance-defi'

        Returns:
            (分类详情, SourceMeta)
        """
        endpoint = f"/coins/categories/{category_id}"
        params = {}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="category_detail",
            ttl_seconds=1800,  # 30分钟缓存
        )
