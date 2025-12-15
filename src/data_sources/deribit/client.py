"""
Deribit API客户端

提供加密货币期权和期货数据
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import SourceMeta
from src.data_sources.base import BaseDataSource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DeribitClient(BaseDataSource):
    """Deribit API客户端（期权和期货）"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        初始化Deribit客户端

        Args:
            api_key: API密钥（可选，公共端点不需要）
            api_secret: API密钥（可选，公共端点不需要）
        """
        base_url = "https://www.deribit.com/api/v2"
        super().__init__(
            name="deribit",
            base_url=base_url,
            timeout=10.0,
            requires_api_key=False,  # 公共数据不需要API key
        )
        self.api_key = api_key
        self.api_secret = api_secret

    def _get_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {"Content-Type": "application/json"}
        # 如果需要认证，添加授权头（Deribit使用OAuth2）
        # 暂时只实现公共端点
        return headers

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Dict[str, Any]:
        """
        转换原始数据为标准格式

        Args:
            raw_data: Deribit API原始响应
            data_type: 数据类型

        Returns:
            标准化数据字典
        """
        if data_type == "instrument":
            return self._transform_instrument(raw_data)
        elif data_type == "orderbook":
            return self._transform_orderbook(raw_data)
        elif data_type == "greeks":
            return self._transform_greeks(raw_data)
        else:
            return raw_data

    # ==================== 公共API方法 ====================

    async def get_instruments(
        self,
        currency: str = "BTC",
        kind: str = "option",
        expired: bool = False,
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取可用合约列表

        Args:
            currency: 货币（BTC, ETH）
            kind: 合约类型（option, future, option_combo, future_combo）
            expired: 是否包含已过期合约

        Returns:
            (合约列表, SourceMeta)
        """
        endpoint = "/public/get_instruments"
        params = {
            "currency": currency.upper(),
            "kind": kind,
            "expired": str(expired).lower(),
        }

        raw_data = await self.fetch_raw(endpoint, params)
        result = raw_data.get("result", [])

        meta = SourceMeta(
            provider="deribit",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=300,  # 5分钟缓存
        )

        # 转换每个合约
        instruments = [self._transform_instrument(inst) for inst in result]
        return instruments, meta

    async def get_orderbook(
        self,
        instrument_name: str,
        depth: int = 10,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取期权订单簿

        Args:
            instrument_name: 合约名称（如 BTC-30DEC24-100000-C）
            depth: 订单簿深度

        Returns:
            (订单簿数据, SourceMeta)
        """
        endpoint = "/public/get_order_book"
        params = {
            "instrument_name": instrument_name,
            "depth": depth,
        }

        raw_data = await self.fetch_raw(endpoint, params)
        result = raw_data.get("result", {})

        meta = SourceMeta(
            provider="deribit",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=10,  # 10秒缓存（订单簿变化快）
        )

        orderbook = self._transform_orderbook(result)
        return orderbook, meta

    async def get_volatility_index(
        self,
        currency: str = "BTC",
    ) -> tuple[Dict, SourceMeta]:
        """
        获取波动率指数（DVOL - Deribit Volatility Index）

        Args:
            currency: 货币（BTC, ETH）

        Returns:
            (波动率数据, SourceMeta)
        """
        import time

        # 使用 get_volatility_index_data 端点获取历史DVOL数据
        endpoint = "/public/get_volatility_index_data"

        # 获取最近1小时的数据
        end_timestamp = int(time.time() * 1000)
        start_timestamp = end_timestamp - 3600000  # 1小时前

        params = {
            "currency": currency.upper(),
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "resolution": "60",  # 1小时分辨率
        }

        raw_data = await self.fetch_raw(endpoint, params)
        result = raw_data.get("result", {})
        data_points = result.get("data", [])

        meta = SourceMeta(
            provider="deribit",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=60,  # 1分钟缓存
        )

        # 获取最新的DVOL值
        latest_dvol = None
        latest_timestamp = None
        if data_points:
            # 数据格式: [timestamp, open, high, low, close]
            latest_point = data_points[-1]
            latest_timestamp = latest_point[0] if len(latest_point) > 0 else None
            latest_dvol = latest_point[4] if len(latest_point) > 4 else None  # close value

        return {
            "currency": currency.upper(),
            "dvol": latest_dvol,
            "timestamp": latest_timestamp,
            "data_points": len(data_points),
        }, meta

    async def get_historical_volatility(
        self,
        currency: str = "BTC",
    ) -> tuple[Dict, SourceMeta]:
        """
        获取历史波动率

        Args:
            currency: 货币（BTC, ETH）

        Returns:
            (历史波动率数据, SourceMeta)
        """
        endpoint = "/public/get_historical_volatility"
        params = {"currency": currency.upper()}

        raw_data = await self.fetch_raw(endpoint, params)
        result = raw_data.get("result", [])

        meta = SourceMeta(
            provider="deribit",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=3600,  # 1小时缓存
        )

        return {"currency": currency.upper(), "data": result}, meta

    async def get_options_chain(
        self,
        currency: str = "BTC",
        expiry_date: Optional[str] = None,
    ) -> tuple[List[Dict], SourceMeta]:
        """
        获取期权链（所有strike的期权）

        Args:
            currency: 货币（BTC, ETH）
            expiry_date: 到期日（格式: 30DEC24）如果为None，返回所有未过期的

        Returns:
            (期权链列表, SourceMeta)
        """
        # 获取所有未过期的期权合约
        instruments, meta = await self.get_instruments(
            currency=currency,
            kind="option",
            expired=False,
        )

        # 如果指定了到期日，过滤
        if expiry_date:
            instruments = [
                inst
                for inst in instruments
                if expiry_date.upper() in inst.get("instrument_name", "")
            ]

        return instruments, meta

    async def get_ticker(
        self,
        instrument_name: str,
    ) -> tuple[Dict, SourceMeta]:
        """
        获取期权ticker（包含Greeks和IV）

        Args:
            instrument_name: 合约名称（如 BTC-30DEC24-100000-C）

        Returns:
            (ticker数据, SourceMeta)
        """
        endpoint = "/public/ticker"
        params = {"instrument_name": instrument_name}

        raw_data = await self.fetch_raw(endpoint, params)
        result = raw_data.get("result", {})

        meta = SourceMeta(
            provider="deribit",
            endpoint=endpoint,
            as_of_utc=datetime.utcnow().isoformat() + "Z",
            ttl_seconds=10,  # 10秒缓存
        )

        ticker = self._transform_ticker(result)
        return ticker, meta

    # ==================== 数据转换方法 ====================

    def _transform_instrument(self, data: Dict) -> Dict:
        """转换合约数据"""
        return {
            "instrument_name": data.get("instrument_name"),
            "kind": data.get("kind"),
            "currency": data.get("base_currency"),
            "quote_currency": data.get("quote_currency"),
            "creation_timestamp": data.get("creation_timestamp"),
            "expiration_timestamp": data.get("expiration_timestamp"),
            "is_active": data.get("is_active"),
            "strike": data.get("strike"),
            "option_type": data.get("option_type"),  # call or put
            "settlement_period": data.get("settlement_period"),
            "contract_size": data.get("contract_size"),
            "tick_size": data.get("tick_size"),
            "min_trade_amount": data.get("min_trade_amount"),
        }

    def _transform_orderbook(self, data: Dict) -> Dict:
        """转换订单簿数据"""
        return {
            "instrument_name": data.get("instrument_name"),
            "timestamp": data.get("timestamp"),
            "bids": [[bid[0], bid[1]] for bid in data.get("bids", [])],  # [price, amount]
            "asks": [[ask[0], ask[1]] for ask in data.get("asks", [])],
            "best_bid_price": data.get("best_bid_price"),
            "best_bid_amount": data.get("best_bid_amount"),
            "best_ask_price": data.get("best_ask_price"),
            "best_ask_amount": data.get("best_ask_amount"),
            "mark_price": data.get("mark_price"),
            "index_price": data.get("index_price"),
            "underlying_price": data.get("underlying_price"),
        }

    def _transform_ticker(self, data: Dict) -> Dict:
        """转换ticker数据（包含Greeks和IV）"""
        greeks = data.get("greeks", {})

        return {
            "instrument_name": data.get("instrument_name"),
            "timestamp": data.get("timestamp"),
            "state": data.get("state"),
            # 价格数据
            "mark_price": data.get("mark_price"),
            "index_price": data.get("index_price"),
            "underlying_price": data.get("underlying_price"),
            "last_price": data.get("last_price"),
            "best_bid_price": data.get("best_bid_price"),
            "best_ask_price": data.get("best_ask_price"),
            # 隐含波动率
            "mark_iv": data.get("mark_iv"),
            "bid_iv": data.get("bid_iv"),
            "ask_iv": data.get("ask_iv"),
            # Greeks
            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "theta": greeks.get("theta"),
            "vega": greeks.get("vega"),
            "rho": greeks.get("rho"),
            # 交易量
            "volume": data.get("stats", {}).get("volume"),
            "volume_usd": data.get("stats", {}).get("volume_usd"),
            "open_interest": data.get("open_interest"),
        }

    def _transform_greeks(self, data: Dict) -> Dict:
        """转换Greeks数据"""
        return {
            "delta": data.get("delta"),
            "gamma": data.get("gamma"),
            "theta": data.get("theta"),
            "vega": data.get("vega"),
            "rho": data.get("rho"),
        }
