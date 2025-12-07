"""
BinanceClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta
from src.data_sources.binance import BinanceClient


class TestBinanceClient:
    """BinanceClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return BinanceClient(api_key="test_api_key")

    @pytest.fixture
    def testnet_client(self):
        """创建测试网客户端"""
        return BinanceClient(use_testnet=True)

    def test_init(self, client):
        """测试初始化"""
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://api.binance.com"
        assert client.futures_base_url == "https://fapi.binance.com"

    def test_init_testnet(self, testnet_client):
        """测试测试网初始化"""
        assert testnet_client.base_url == "https://testnet.binance.vision"
        assert testnet_client.futures_base_url == "https://testnet.binancefuture.com"

    @pytest.mark.asyncio
    async def test_get_ticker(self, client):
        """测试获取24h行情"""
        mock_response = {
            "symbol": "BTCUSDT",
            "lastPrice": "45000.00",
            "bidPrice": "44999.00",
            "askPrice": "45001.00",
            "volume": "10000",
            "quoteVolume": "450000000",
            "priceChange": "1000",
            "priceChangePercent": "2.27",
            "highPrice": "46000",
            "lowPrice": "44000",
            "closeTime": 1700000000000,
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_ticker(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_ticker("BTCUSDT", market="spot")

            assert data["symbol"] == "BTCUSDT"
            assert data["exchange"] == "binance"
            assert data["last_price"] == 45000.0
            assert data["volume_24h"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_ticker_futures(self, client):
        """测试获取期货行情"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_ticker("BTCUSDT", market="futures")

            call_kwargs = mock_fetch.call_args[1]
            assert call_kwargs["base_url_override"] == client.futures_base_url

    @pytest.mark.asyncio
    async def test_get_klines(self, client):
        """测试获取K线数据"""
        mock_response = [
            [
                1700000000000, "45000", "46000", "44000", "45500", "100",
                1700003600000, "4500000", 500, "50", "2250000", "0"
            ]
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_klines(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_klines("BTCUSDT", interval="1h", limit=100)

            assert len(data) == 1
            assert data[0]["open"] == 45000.0
            assert data[0]["high"] == 46000.0
            assert data[0]["low"] == 44000.0
            assert data[0]["close"] == 45500.0

    @pytest.mark.asyncio
    async def test_get_klines_limit_cap(self, client):
        """测试K线数量限制"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ([], mock_meta)

            await client.get_klines("BTCUSDT", limit=2000)

            call_params = mock_fetch.call_args[1]["params"]
            assert call_params["limit"] == 1000  # 最大值

    @pytest.mark.asyncio
    async def test_get_orderbook(self, client):
        """测试获取订单簿"""
        mock_response = {
            "bids": [["45000", "1.0"], ["44999", "2.0"]],
            "asks": [["45001", "1.5"], ["45002", "2.5"]],
            "lastUpdateId": 123456,
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_orderbook(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_orderbook("BTCUSDT", limit=20)

            assert data["exchange"] == "binance"
            assert len(data["bids"]) == 2
            assert len(data["asks"]) == 2
            assert data["mid_price"] == 45000.5

    @pytest.mark.asyncio
    async def test_get_orderbook_valid_limit(self, client):
        """测试订单簿深度有效值"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"bids": [], "asks": []}, mock_meta)

            # 测试自动选择最近的有效值
            await client.get_orderbook("BTCUSDT", limit=15)

            call_params = mock_fetch.call_args[1]["params"]
            # 15最接近10或20
            assert call_params["limit"] in [5, 10, 20]

    @pytest.mark.asyncio
    async def test_get_recent_trades(self, client):
        """测试获取最近成交"""
        mock_response = [
            {
                "id": 12345,
                "price": "45000.00",
                "qty": "0.1",
                "quoteQty": "4500.00",
                "time": 1700000000000,
                "isBuyerMaker": False,
            }
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_trades(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_recent_trades("BTCUSDT", limit=100)

            assert len(data) == 1
            assert data[0]["price"] == 45000.0
            assert data[0]["side"] == "buy"

    @pytest.mark.asyncio
    async def test_get_exchange_info(self, client):
        """测试获取交易所规格"""
        mock_response = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "status": "TRADING",
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.00001"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
                    ]
                }
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_exchange_info(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_exchange_info()

            assert len(data["symbols"]) == 1
            assert data["symbols"][0]["symbol"] == "BTCUSDT"
            assert data["symbols"][0]["tick_size"] == 0.01

    @pytest.mark.asyncio
    async def test_get_funding_rate(self, client):
        """测试获取资金费率"""
        mock_response = {
            "symbol": "BTCUSDT",
            "lastFundingRate": "0.0001",
            "nextFundingTime": 1700000000000,
            "markPrice": "45000",
            "indexPrice": "44990",
            "time": 1699996400000,
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_funding_rate(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_funding_rate("BTCUSDT")

            assert data["symbol"] == "BTCUSDT"
            assert data["funding_rate"] == 0.0001
            assert data["mark_price"] == 45000.0

            # 验证使用期货URL
            call_kwargs = mock_fetch.call_args[1]
            assert call_kwargs["base_url_override"] == client.futures_base_url

    @pytest.mark.asyncio
    async def test_get_open_interest(self, client):
        """测试获取未平仓量"""
        mock_response = {
            "symbol": "BTCUSDT",
            "openInterest": "10000",
            "time": 1700000000000,
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_open_interest(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_open_interest("BTCUSDT")

            assert data["symbol"] == "BTCUSDT"
            assert data["open_interest"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_long_short_ratio(self, client):
        """测试获取多空比"""
        mock_response = [
            {
                "symbol": "BTCUSDT",
                "longAccount": "0.6",
                "shortAccount": "0.4",
                "timestamp": 1700000000000,
            }
        ]

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_long_short_ratio(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_long_short_ratio("BTCUSDT", period="1h")

            assert len(data) == 1
            assert data[0]["long_ratio"] == 0.6
            assert data[0]["short_ratio"] == 0.4
            assert data[0]["long_short_ratio"] == 1.5

    @pytest.mark.asyncio
    async def test_get_mark_price(self, client):
        """测试获取标记价格"""
        mock_response = {
            "symbol": "BTCUSDT",
            "lastFundingRate": "0.0001",
            "nextFundingTime": 1700000000000,
            "markPrice": "45000",
            "time": 1699996400000,
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            transformed = client._transform_funding_rate(mock_response)
            mock_fetch.return_value = (transformed, mock_meta)

            data, meta = await client.get_mark_price("BTCUSDT")

            assert data["mark_price"] == 45000.0

    def test_transform_ticker(self, client):
        """测试ticker数据转换"""
        raw = {
            "symbol": "BTCUSDT",
            "lastPrice": "45000",
            "bidPrice": "44999",
            "askPrice": "45001",
            "volume": "10000",
            "quoteVolume": "450000000",
            "priceChange": "1000",
            "priceChangePercent": "2.27",
            "highPrice": "46000",
            "lowPrice": "44000",
            "closeTime": 1700000000000,
        }

        result = client._transform_ticker(raw)

        assert result["symbol"] == "BTCUSDT"
        assert result["last_price"] == 45000.0
        assert "spread_bps" in result

    def test_transform_klines(self, client):
        """测试K线数据转换"""
        raw = [
            [1700000000000, "45000", "46000", "44000", "45500", "100",
             1700003600000, "4500000", 500, "50", "2250000", "0"]
        ]

        result = client._transform_klines(raw)

        assert len(result) == 1
        assert result[0]["open"] == 45000.0
        assert result[0]["trades_count"] == 500

    def test_transform_orderbook(self, client):
        """测试订单簿数据转换"""
        raw = {
            "bids": [["45000", "1.0"], ["44999", "2.0"]],
            "asks": [["45001", "1.5"], ["45002", "2.5"]],
        }

        result = client._transform_orderbook(raw)

        assert result["mid_price"] == 45000.5
        assert len(result["bids"]) == 2
        # 验证累计量计算
        assert result["bids"][0]["total"] == 1.0
        assert result["bids"][1]["total"] == 3.0

    def test_transform_trades(self, client):
        """测试成交记录转换"""
        raw = [
            {
                "id": 12345,
                "price": "45000",
                "qty": "0.1",
                "quoteQty": "4500",
                "time": 1700000000000,
                "isBuyerMaker": False,
            },
            {
                "id": 12346,
                "price": "45001",
                "qty": "0.2",
                "quoteQty": "9000",
                "time": 1700000001000,
                "isBuyerMaker": True,
            },
        ]

        result = client._transform_trades(raw)

        assert len(result) == 2
        assert result[0]["side"] == "buy"
        assert result[1]["side"] == "sell"

    def test_transform_long_short_ratio_empty(self, client):
        """测试空多空比数据转换"""
        result = client._transform_long_short_ratio([])
        assert result == []

    def test_transform_long_short_ratio_zero_short(self, client):
        """测试空头为0的多空比"""
        raw = [
            {
                "symbol": "BTCUSDT",
                "longAccount": "1.0",
                "shortAccount": "0",
                "timestamp": 1700000000000,
            }
        ]

        result = client._transform_long_short_ratio(raw)
        assert result[0]["long_short_ratio"] == 0

    def test_calculate_spread_bps(self, client):
        """测试价差计算"""
        # 正常情况
        spread = client._calculate_spread_bps(45000, 45001)
        assert spread > 0
        assert spread < 1  # 小于1个基点

        # 零值
        assert client._calculate_spread_bps(0, 45001) == 0.0
        assert client._calculate_spread_bps(45000, 0) == 0.0

    def test_transform_with_unknown_data_type(self, client):
        """测试未知数据类型转换"""
        raw_data = {"test": "data"}
        result = client.transform(raw_data, "unknown_type")
        assert result == raw_data

    def test_symbol_formatting(self, client):
        """测试交易对格式化"""
        # 测试自动大写和移除斜杠
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            import asyncio
            asyncio.get_event_loop().run_until_complete(
                client.get_ticker("btc/usdt")
            )

            call_params = mock_fetch.call_args[1]["params"]
            assert call_params["symbol"] == "BTCUSDT"
