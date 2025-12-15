"""
CoinMarketCap API客户端
"""
from typing import Any, Dict, Optional

from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CoinMarketCapClient(BaseDataSource):
    """CoinMarketCap API客户端"""

    def __init__(self, api_key: Optional[str] = None):
        base_url = "https://pro-api.coinmarketcap.com/v1"
        super().__init__(
            name="coinmarketcap",
            base_url=base_url,
            timeout=10.0,
            requires_api_key=True,
        )
        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Accept": "application/json",
        }

        if self.api_key:
            headers["X-CMC_PRO_API_KEY"] = self.api_key

        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: CMC API原始响应
            data_type: 数据类型 (basic, market, quotes)

        Returns:
            标准化数据字典
        """
        if data_type == "basic":
            return self._transform_basic(raw_data)
        elif data_type == "market":
            return self._transform_market(raw_data)
        elif data_type == "quotes":
            # 提取data部分，返回币种数据
            return raw_data.get("data", {})
        else:
            return raw_data

    def _transform_basic(self, data: Dict) -> Dict:
        """转换基础信息"""
        # CMC metadata API响应
        if "data" in data:
            # 获取第一个币种数据
            coin_data = list(data["data"].values())[0] if data["data"] else {}

            urls = coin_data.get("urls", {})

            return {
                "id": str(coin_data.get("id")),
                "symbol": coin_data.get("symbol", "").upper(),
                "name": coin_data.get("name"),
                "description": coin_data.get("description", "")[:500],
                "homepage": urls.get("website", [])[:1],
                "blockchain_site": urls.get("explorer", [])[:3],
                "contract_address": coin_data.get("contract_address"),
                "chain": coin_data.get("platform", {}).get("name") if coin_data.get("platform") else None,
            }

        return {}

    def _transform_market(self, data: Dict) -> Dict:
        """转换市场数据"""
        # CMC quotes API响应
        if "data" in data:
            # 取第一个币种的数据（通常按symbol查询只返回一个）
            coin_data = list(data["data"].values())[0] if data["data"] else {}
            quote = coin_data.get("quote", {}).get("USD", {})

            return {
                "price": quote.get("price"),
                "market_cap": quote.get("market_cap"),
                "market_cap_rank": coin_data.get("cmc_rank"),
                "fully_diluted_valuation": quote.get("fully_diluted_market_cap"),
                "total_volume_24h": quote.get("volume_24h"),
                "high_24h": None,  # CMC不提供24h高低价
                "low_24h": None,
                "price_change_24h": quote.get("price_change_24h"),
                "price_change_percentage_24h": quote.get("percent_change_24h"),
                "ath": None,  # CMC免费版不提供ATH/ATL
                "atl": None,
            }

        return {}

    async def get_coin_quotes(self, symbol: str) -> Dict:
        """
        获取代币行情数据

        Args:
            symbol: 代币符号 (如 BTC, ETH)

        Returns:
            行情数据
        """
        endpoint = "/cryptocurrency/quotes/latest"
        params = {
            "symbol": symbol.upper(),
            "convert": "USD",
        }

        return await self.fetch_raw(endpoint, params)

    async def get_quotes(self, symbol: str) -> tuple[Dict, Any]:
        """
        获取代币报价数据（兼容方法）

        Args:
            symbol: 代币符号 (如 BTC, ETH)

        Returns:
            (报价数据, SourceMeta)
        """
        endpoint = "/cryptocurrency/quotes/latest"
        params = {
            "symbol": symbol.upper(),
            "convert": "USD",
        }

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="quotes",
            ttl_seconds=60,
        )

    async def get_coin_metadata(self, symbol: str) -> Dict:
        """
        获取代币元数据

        Args:
            symbol: 代币符号

        Returns:
            元数据
        """
        endpoint = "/cryptocurrency/info"
        params = {
            "symbol": symbol.upper(),
        }

        return await self.fetch_raw(endpoint, params)
