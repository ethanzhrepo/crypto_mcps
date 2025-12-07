"""
Etherscan API客户端（支持多链）
"""
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.models import OnchainActivity, SourceMeta
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EtherscanClient(BaseDataSource):
    """Etherscan API客户端（支持Ethereum及兼容链）"""

    # 链到API基础URL的映射
    CHAIN_URLS = {
        "ethereum": "https://api.etherscan.io/api",
        "bsc": "https://api.bscscan.com/api",
        "polygon": "https://api.polygonscan.com/api",
        "arbitrum": "https://api.arbiscan.io/api",
        "optimism": "https://api-optimistic.etherscan.io/api",
        "avalanche": "https://api.snowtrace.io/api",
    }

    def __init__(self, chain: str = "ethereum", api_key: Optional[str] = None):
        """
        初始化Etherscan客户端

        Args:
            chain: 链名称 (ethereum, bsc, polygon, arbitrum)
            api_key: API密钥
        """
        self.chain = chain.lower()
        base_url = self.CHAIN_URLS.get(self.chain, self.CHAIN_URLS["ethereum"])

        super().__init__(
            name=f"etherscan_{chain}",
            base_url=base_url,
            timeout=15.0,
            requires_api_key=True,
        )

        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "User-Agent": "Mozilla/5.0",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None) -> Any:
        """
        获取原始数据

        Note: Etherscan的endpoint实际上是query参数，统一用baseurl
        """
        params = params or {}

        # 添加API key
        if self.api_key:
            params["apikey"] = self.api_key

        # Etherscan不使用endpoint路径，所有参数都在query中
        return await self._make_request("GET", "", params)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: Etherscan API原始响应
            data_type: 数据类型 (holders)

        Returns:
            标准化数据字典
        """
        if data_type == "holders":
            return self._transform_holders(raw_data)
        elif data_type == "supply":
            return self._transform_supply(raw_data)
        else:
            return raw_data

    def _transform_holders(self, data: Dict) -> Dict:
        """
        转换持有者数据

        注意：Etherscan tokenholderlist API限制返回10000条
        """
        if data.get("status") != "1":
            return {
                "total_holders": None,
                "top10_percent": None,
                "top50_percent": None,
                "top100_percent": None,
                "data_coverage": "unavailable",
            }

        # result是持有者列表
        holders = data.get("result", [])

        if not holders:
            return {
                "total_holders": 0,
                "top10_percent": None,
                "top50_percent": None,
                "top100_percent": None,
                "data_coverage": "empty",
            }

        # 计算总供应量（假设已经从token info获取）
        # 这里简化处理，实际应该从另一个API获取total_supply
        total_balance = sum(float(h.get("TokenHolderQuantity", 0)) for h in holders)

        if total_balance == 0:
            return {
                "total_holders": len(holders),
                "top10_percent": None,
                "top50_percent": None,
                "top100_percent": None,
                "data_coverage": "zero_balance",
            }

        # 计算Top N占比（按Q3设计：只计算可获取范围）
        def calc_top_n_percent(n: int) -> Optional[float]:
            if len(holders) < n:
                return None
            top_n_balance = sum(float(holders[i].get("TokenHolderQuantity", 0)) for i in range(n))
            return (top_n_balance / total_balance) * 100

        return {
            "total_holders": len(holders),  # 注意：可能不是真实总数
            "top10_percent": calc_top_n_percent(10),
            "top50_percent": calc_top_n_percent(50),
            "top100_percent": calc_top_n_percent(100),
            "data_coverage": f"first_{len(holders)}_holders",
        }

    def _transform_supply(self, data: Dict) -> Dict:
        """转换供应信息"""
        if data.get("status") != "1":
            return {}

        result = data.get("result", [])
        if isinstance(result, list) and result:
            token_info = result[0]
            total_supply = token_info.get("totalSupply", "0")
            divisor = int(token_info.get("divisor", "0"))

            # 转换为实际数量（考虑decimals）
            if divisor > 0:
                total_supply = float(total_supply) / (10 ** divisor)

            return {
                "total_supply": total_supply,
                "circulating_supply": None,  # Etherscan不直接提供
                "max_supply": None,
            }

        return {}

    async def get_token_holders(
        self,
        contract_address: str,
        page: int = 1,
        offset: int = 10000
    ) -> Dict:
        """
        获取代币持有者列表

        Args:
            contract_address: 合约地址
            page: 页码
            offset: 每页数量（最大10000）

        Returns:
            持有者数据
        """
        params = {
            "module": "token",
            "action": "tokenholderlist",
            "contractaddress": contract_address,
            "page": str(page),
            "offset": str(min(offset, 10000)),
        }

        return await self.fetch_raw("", params)

    async def get_token_info(self, contract_address: str) -> Dict:
        """
        获取代币基本信息

        Args:
            contract_address: 合约地址

        Returns:
            代币信息
        """
        params = {
            "module": "token",
            "action": "tokeninfo",
            "contractaddress": contract_address,
        }

        return await self.fetch_raw("", params)

    async def get_chain_stats(self) -> tuple[OnchainActivity, SourceMeta]:
        """
        获取链上活动统计

        Returns:
            (链上活动数据, SourceMeta)
        """
        # 获取每日交易数
        tx_params = {
            "module": "stats",
            "action": "dailytx",
            "startdate": (datetime.utcnow().date()).isoformat(),
            "enddate": (datetime.utcnow().date()).isoformat(),
            "sort": "desc",
        }

        # 获取平均Gas价格
        gas_params = {
            "module": "gastracker",
            "action": "gasoracle",
        }

        # 获取交易数
        tx_data = await self.fetch_raw("", tx_params)
        gas_data = await self.fetch_raw("", gas_params)

        # 解析交易数据
        tx_count_24h = 0
        if tx_data.get("status") == "1":
            result = tx_data.get("result", [])
            if result:
                tx_count_24h = int(result[0].get("transactioncount", 0)) if isinstance(result, list) else 0

        # 解析Gas数据
        avg_gas_price = None
        if gas_data.get("status") == "1":
            result = gas_data.get("result", {})
            if isinstance(result, dict):
                avg_gas_price = float(result.get("ProposeGasPrice", 0))

        activity = OnchainActivity(
            chain=self.chain,
            transaction_count_24h=tx_count_24h,
            avg_gas_price_gwei=avg_gas_price,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        # 构建SourceMeta
        from src.core.source_meta import SourceMetaBuilder
        meta = SourceMetaBuilder.build(
            provider=self.name,
            endpoint="/stats",
            ttl_seconds=300,
            response_time_ms=0,
        )

        return activity, meta

    async def get_eth_supply(self) -> Dict:
        """
        获取ETH供应量

        Returns:
            供应量数据
        """
        params = {
            "module": "stats",
            "action": "ethsupply",
        }

        return await self.fetch_raw("", params)

    async def get_eth_price(self) -> Dict:
        """
        获取ETH价格

        Returns:
            价格数据
        """
        params = {
            "module": "stats",
            "action": "ethprice",
        }

        return await self.fetch_raw("", params)
