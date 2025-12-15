"""
Whale Alert API客户端 - 大额转账监控

API文档: https://docs.whale-alert.io/
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta, WhaleTransfer, WhaleTransfersData
from src.data_sources.base import BaseDataSource


class WhaleAlertClient(BaseDataSource):
    """Whale Alert API客户端"""

    BASE_URL = "https://api.whale-alert.io/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Whale Alert客户端

        Args:
            api_key: API密钥（可选，会尝试从配置中获取）
        """
        super().__init__(
            name="whale_alert",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=True,
        )
        if api_key:
            self.api_key = api_key

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Accept": "application/json",
        }

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        # Whale Alert使用api_key作为查询参数
        if params is None:
            params = {}
        if self.api_key:
            params["api_key"] = self.api_key

        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据"""
        if data_type == "transactions":
            return self._transform_transactions(raw_data)
        return raw_data

    async def get_transactions(
        self,
        min_value: int = 500000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        currency: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[WhaleTransfersData, SourceMeta]:
        """
        获取大额转账记录

        Args:
            min_value: 最小金额（USD）
            start_time: 开始时间戳（Unix秒）
            end_time: 结束时间戳（Unix秒）
            currency: 货币符号过滤（如 btc, eth）
            limit: 返回数量限制

        Returns:
            (大额转账数据, SourceMeta)
        """
        endpoint = "/transactions"

        # 默认查询过去24小时
        if start_time is None:
            start_time = int((datetime.utcnow() - timedelta(hours=24)).timestamp())
        if end_time is None:
            end_time = int(datetime.utcnow().timestamp())

        params = {
            "min_value": min_value,
            "start": start_time,
            "end": end_time,
            "limit": limit,
        }
        if currency:
            params["currency"] = currency.lower()

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="transactions",
            ttl_seconds=60,  # 1分钟缓存
        )

        # 计算统计数据
        transfers = data.get("transfers", [])
        total_value = sum(t.get("value_usd", 0) for t in transfers)
        hours = (end_time - start_time) / 3600

        whale_data = WhaleTransfersData(
            token_symbol=currency.upper() if currency else None,
            chain=None,
            time_range_hours=int(hours),
            min_value_usd=float(min_value),
            total_transfers=len(transfers),
            total_value_usd=total_value,
            transfers=[
                WhaleTransfer(
                    tx_hash=t.get("hash", ""),
                    timestamp=datetime.fromtimestamp(t.get("timestamp", 0)).isoformat() + "Z",
                    from_address=t.get("from", {}).get("address", ""),
                    from_label=t.get("from", {}).get("owner", None),
                    to_address=t.get("to", {}).get("address", ""),
                    to_label=t.get("to", {}).get("owner", None),
                    token_symbol=t.get("symbol", "").upper(),
                    amount=t.get("amount", 0),
                    value_usd=t.get("amount_usd", 0),
                    chain=self._blockchain_to_chain(t.get("blockchain", "")),
                    blockchain=t.get("blockchain", ""),
                )
                for t in transfers
            ],
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        return whale_data, meta

    def _transform_transactions(self, raw_data: Any) -> Dict:
        """转换交易数据"""
        if not raw_data or raw_data.get("result") != "success":
            return {"transfers": [], "count": 0}

        transactions = raw_data.get("transactions", [])
        transfers = []

        for tx in transactions:
            transfers.append({
                "hash": tx.get("hash", ""),
                "timestamp": tx.get("timestamp", 0),
                "blockchain": tx.get("blockchain", ""),
                "symbol": tx.get("symbol", ""),
                "amount": tx.get("amount", 0),
                "amount_usd": tx.get("amount_usd", 0),
                "from": tx.get("from", {}),
                "to": tx.get("to", {}),
            })

        return {
            "transfers": transfers,
            "count": len(transfers),
        }

    def _blockchain_to_chain(self, blockchain: str) -> str:
        """将Whale Alert的blockchain名称转换为标准chain名称"""
        mapping = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum",
            "tron": "tron",
            "ripple": "ripple",
            "neo": "neo",
            "eos": "eos",
            "stellar": "stellar",
            "binancechain": "bsc",
        }
        return mapping.get(blockchain.lower(), blockchain.lower())

    async def get_status(self) -> tuple[Dict, SourceMeta]:
        """
        获取API状态

        Returns:
            (状态信息, SourceMeta)
        """
        endpoint = "/status"
        return await self.fetch(
            endpoint=endpoint,
            params={},
            data_type="status",
            ttl_seconds=60,
        )

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            data, _ = await self.get_status()
            return data.get("result") == "success"
        except Exception:
            return False
