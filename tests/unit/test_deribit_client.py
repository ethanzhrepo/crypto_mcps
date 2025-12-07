"""
DeribitClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.deribit import DeribitClient


class TestDeribitClient:
    """DeribitClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return DeribitClient(api_key="test_key", api_secret="test_secret")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return DeribitClient()

    def test_init(self, client):
        """测试初始化"""
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.name == "deribit"
        assert client.base_url == "https://www.deribit.com/api/v2"
        assert client.requires_api_key is False

    def test_get_headers(self, client):
        """测试请求头"""
        headers = client._get_headers()
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_get_instruments(self, client):
        """测试获取合约列表"""
        mock_response = {
            "result": [
                {
                    "instrument_name": "BTC-30DEC24-100000-C",
                    "kind": "option",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "expiration_timestamp": 1735603200000,
                    "strike": 100000,
                    "option_type": "call",
                    "is_active": True,
                    "min_trade_amount": 0.1,
                    "tick_size": 0.0001,
                    "settlement_period": "month",
                },
            ]
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            instruments, meta = await client.get_instruments(
                currency="BTC",
                kind="option",
                expired=False,
            )

            assert len(instruments) == 1
            assert instruments[0]["instrument_name"] == "BTC-30DEC24-100000-C"
            assert meta.provider == "deribit"
            assert meta.ttl_seconds == 300

    @pytest.mark.asyncio
    async def test_get_instruments_futures(self, client):
        """测试获取期货合约"""
        mock_response = {
            "result": [
                {
                    "instrument_name": "BTC-PERPETUAL",
                    "kind": "future",
                    "base_currency": "BTC",
                    "quote_currency": "USD",
                    "is_active": True,
                },
            ]
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            instruments, meta = await client.get_instruments(
                currency="BTC",
                kind="future",
            )

            assert len(instruments) == 1
            assert instruments[0]["kind"] == "future"

    @pytest.mark.asyncio
    async def test_get_orderbook(self, client):
        """测试获取期权订单簿"""
        mock_response = {
            "result": {
                "instrument_name": "BTC-30DEC24-100000-C",
                "bids": [[0.05, 10], [0.045, 20]],
                "asks": [[0.055, 15], [0.06, 25]],
                "mark_price": 0.0525,
                "underlying_price": 45000,
                "underlying_index": "btc_usd",
                "timestamp": 1700000000000,
            }
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            orderbook, meta = await client.get_orderbook(
                instrument_name="BTC-30DEC24-100000-C",
                depth=10,
            )

            assert orderbook["instrument_name"] == "BTC-30DEC24-100000-C"
            assert len(orderbook["bids"]) == 2
            assert len(orderbook["asks"]) == 2
            assert meta.ttl_seconds == 10

    @pytest.mark.asyncio
    async def test_get_volatility_index(self, client):
        """测试获取波动率指数"""
        mock_response = {
            "result": {
                "instrument_name": "BTC_DVOL",
                "index_price": 45000,
                "underlying_price": 55.5,  # DVOL value
                "timestamp": 1700000000000,
            }
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            data, meta = await client.get_volatility_index(currency="BTC")

            assert data["currency"] == "BTC"
            assert data["index_price"] == 45000
            assert data["dvol"] == 55.5

    @pytest.mark.asyncio
    async def test_get_volatility_index_eth(self, client):
        """测试获取ETH波动率指数"""
        mock_response = {
            "result": {
                "instrument_name": "ETH_DVOL",
                "index_price": 2500,
                "underlying_price": 65.0,
                "timestamp": 1700000000000,
            }
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            data, meta = await client.get_volatility_index(currency="eth")

            assert data["currency"] == "ETH"

    @pytest.mark.asyncio
    async def test_get_historical_volatility(self, client):
        """测试获取历史波动率"""
        mock_response = {
            "result": [
                [1700000000000, 50.5],
                [1699913600000, 48.2],
            ]
        }

        with patch.object(client, "fetch_raw", return_value=mock_response):
            data, meta = await client.get_historical_volatility(currency="BTC")

            assert len(data["data"]) == 2

    def test_transform_instrument(self, client):
        """测试合约数据转换"""
        raw_data = {
            "instrument_name": "BTC-30DEC24-100000-C",
            "kind": "option",
            "base_currency": "BTC",
            "quote_currency": "USD",
            "expiration_timestamp": 1735603200000,
            "strike": 100000,
            "option_type": "call",
            "is_active": True,
            "min_trade_amount": 0.1,
            "tick_size": 0.0001,
        }

        result = client._transform_instrument(raw_data)

        assert result["instrument_name"] == "BTC-30DEC24-100000-C"
        assert result["strike"] == 100000
        assert result["option_type"] == "call"

    def test_transform_orderbook(self, client):
        """测试订单簿数据转换"""
        raw_data = {
            "instrument_name": "BTC-30DEC24-100000-C",
            "bids": [[0.05, 10], [0.045, 20]],
            "asks": [[0.055, 15], [0.06, 25]],
            "mark_price": 0.0525,
            "underlying_price": 45000,
            "timestamp": 1700000000000,
        }

        result = client._transform_orderbook(raw_data)

        assert result["instrument_name"] == "BTC-30DEC24-100000-C"
        assert result["mark_price"] == 0.0525
        assert result["underlying_price"] == 45000

    def test_transform_greeks(self, client):
        """测试Greeks数据转换"""
        raw_data = {
            "delta": 0.55,
            "gamma": 0.001,
            "theta": -50,
            "vega": 200,
            "rho": 100,
        }

        result = client._transform_greeks(raw_data)

        assert result["delta"] == 0.55
        assert result["gamma"] == 0.001
        assert result["theta"] == -50
        assert result["vega"] == 200

    def test_transform_unknown_type(self, client):
        """测试未知数据类型"""
        raw_data = {"test": "data"}
        result = client.transform(raw_data, "unknown")
        assert result == raw_data

    @pytest.mark.asyncio
    async def test_get_instruments_empty(self, client):
        """测试空合约列表"""
        mock_response = {"result": []}

        with patch.object(client, "fetch_raw", return_value=mock_response):
            instruments, meta = await client.get_instruments()

            assert instruments == []

    @pytest.mark.asyncio
    async def test_currency_uppercase(self, client):
        """测试货币自动转大写"""
        mock_response = {"result": []}

        with patch.object(client, "fetch_raw", return_value=mock_response) as mock:
            await client.get_instruments(currency="btc")

            call_params = mock.call_args[0][1]
            assert call_params["currency"] == "BTC"

    @pytest.mark.asyncio
    async def test_expired_bool_conversion(self, client):
        """测试expired布尔值转换"""
        mock_response = {"result": []}

        with patch.object(client, "fetch_raw", return_value=mock_response) as mock:
            await client.get_instruments(expired=True)

            call_params = mock.call_args[0][1]
            assert call_params["expired"] == "true"

    @pytest.mark.asyncio
    async def test_orderbook_depth_param(self, client):
        """测试订单簿深度参数"""
        mock_response = {"result": {}}

        with patch.object(client, "fetch_raw", return_value=mock_response) as mock:
            await client.get_orderbook("BTC-30DEC24-100000-C", depth=20)

            call_params = mock.call_args[0][1]
            assert call_params["depth"] == 20

    def test_transform_instrument_minimal(self, client):
        """测试最小合约数据转换"""
        raw_data = {
            "instrument_name": "BTC-PERPETUAL",
            "kind": "future",
        }

        result = client._transform_instrument(raw_data)

        assert result["instrument_name"] == "BTC-PERPETUAL"
        assert result["kind"] == "future"

    def test_transform_orderbook_empty_books(self, client):
        """测试空订单簿转换"""
        raw_data = {
            "instrument_name": "TEST",
            "bids": [],
            "asks": [],
            "mark_price": 0,
            "timestamp": 0,
        }

        result = client._transform_orderbook(raw_data)

        assert result["bids"] == []
        assert result["asks"] == []
