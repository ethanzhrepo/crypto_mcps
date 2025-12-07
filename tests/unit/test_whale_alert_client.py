"""
WhaleAlertClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.core.models import SourceMeta, WhaleTransfersData
from src.data_sources.whale_alert import WhaleAlertClient


class TestWhaleAlertClient:
    """WhaleAlertClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return WhaleAlertClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return WhaleAlertClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "whale_alert"
        assert client.base_url == "https://api.whale-alert.io/v1"

    def test_get_headers(self, client):
        """测试请求头"""
        headers = client._get_headers()
        assert headers["Accept"] == "application/json"
        # API key作为查询参数而非header
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_get_transactions(self, client):
        """测试获取大额转账记录"""
        mock_response = {
            "transfers": [
                {
                    "hash": "0x123abc",
                    "timestamp": 1700000000,
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 1000,
                    "amount_usd": 2000000,
                    "from": {"address": "0xfrom", "owner": "Binance"},
                    "to": {"address": "0xto", "owner": "Unknown"},
                }
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_transactions(
                min_value=500000,
                currency="eth",
                limit=100,
            )

            assert isinstance(data, WhaleTransfersData)
            assert data.total_transfers == 1
            assert data.total_value_usd == 2000000
            assert data.token_symbol == "ETH"
            assert len(data.transfers) == 1
            assert data.transfers[0].tx_hash == "0x123abc"
            assert data.transfers[0].from_label == "Binance"

    @pytest.mark.asyncio
    async def test_get_transactions_default_time_range(self, client):
        """测试默认时间范围（过去24小时）"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"transfers": []}, mock_meta)

            await client.get_transactions(min_value=500000)

            call_params = mock_fetch.call_args[1]["params"]
            assert "start" in call_params
            assert "end" in call_params
            # 验证时间范围约为24小时
            time_diff = call_params["end"] - call_params["start"]
            assert 23 * 3600 < time_diff <= 24 * 3600

    @pytest.mark.asyncio
    async def test_get_transactions_with_custom_time_range(self, client):
        """测试自定义时间范围"""
        start_time = 1700000000
        end_time = 1700003600

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"transfers": []}, mock_meta)

            data, meta = await client.get_transactions(
                min_value=500000,
                start_time=start_time,
                end_time=end_time,
            )

            call_params = mock_fetch.call_args[1]["params"]
            assert call_params["start"] == start_time
            assert call_params["end"] == end_time
            assert data.time_range_hours == 1

    @pytest.mark.asyncio
    async def test_get_transactions_with_currency_filter(self, client):
        """测试货币过滤"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"transfers": []}, mock_meta)

            await client.get_transactions(min_value=500000, currency="BTC")

            call_params = mock_fetch.call_args[1]["params"]
            assert call_params["currency"] == "btc"  # 转换为小写

    @pytest.mark.asyncio
    async def test_fetch_raw_adds_api_key(self, client):
        """测试fetch_raw自动添加API密钥"""
        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {}

            await client.fetch_raw("/test", {"param": "value"})

            call_params = mock_request.call_args[0][2]
            assert call_params["api_key"] == "test_api_key"
            assert call_params["param"] == "value"

    def test_transform_transactions(self, client):
        """测试交易数据转换"""
        raw_data = {
            "result": "success",
            "transactions": [
                {
                    "hash": "0x123",
                    "timestamp": 1700000000,
                    "blockchain": "ethereum",
                    "symbol": "ETH",
                    "amount": 100,
                    "amount_usd": 200000,
                    "from": {"address": "0xfrom", "owner": "Exchange"},
                    "to": {"address": "0xto", "owner": "Whale"},
                },
                {
                    "hash": "0x456",
                    "timestamp": 1700000001,
                    "blockchain": "bitcoin",
                    "symbol": "BTC",
                    "amount": 50,
                    "amount_usd": 2000000,
                    "from": {"address": "bc1from"},
                    "to": {"address": "bc1to"},
                },
            ]
        }

        result = client._transform_transactions(raw_data)

        assert len(result["transfers"]) == 2
        assert result["count"] == 2
        assert result["transfers"][0]["hash"] == "0x123"
        assert result["transfers"][0]["from"]["owner"] == "Exchange"

    def test_transform_transactions_failure(self, client):
        """测试失败响应转换"""
        raw_data = {"result": "error", "message": "Invalid API key"}

        result = client._transform_transactions(raw_data)

        assert result["transfers"] == []
        assert result["count"] == 0

    def test_transform_transactions_empty(self, client):
        """测试空数据转换"""
        assert client._transform_transactions(None) == {"transfers": [], "count": 0}
        assert client._transform_transactions({}) == {"transfers": [], "count": 0}

    def test_blockchain_to_chain_mapping(self, client):
        """测试区块链名称映射"""
        assert client._blockchain_to_chain("bitcoin") == "bitcoin"
        assert client._blockchain_to_chain("ethereum") == "ethereum"
        assert client._blockchain_to_chain("tron") == "tron"
        assert client._blockchain_to_chain("binancechain") == "bsc"
        assert client._blockchain_to_chain("unknown") == "unknown"
        assert client._blockchain_to_chain("ETHEREUM") == "ethereum"

    @pytest.mark.asyncio
    async def test_get_status(self, client):
        """测试获取API状态"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({"result": "success"}, mock_meta)

            data, meta = await client.get_status()

            mock_fetch.assert_called_once_with(
                endpoint="/status",
                params={},
                data_type="status",
                ttl_seconds=60,
            )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """测试健康检查成功"""
        with patch.object(client, "get_status") as mock_get:
            mock_get.return_value = ({"result": "success"}, MagicMock())

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, "get_status") as mock_get:
            mock_get.return_value = ({"result": "error"}, MagicMock())

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, client):
        """测试健康检查异常"""
        with patch.object(client, "get_status") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_multiple_transfers_aggregation(self, client):
        """测试多笔转账聚合"""
        mock_response = {
            "transfers": [
                {
                    "hash": "0x1",
                    "timestamp": 1700000000,
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 1000,
                    "amount_usd": 2000000,
                    "from": {"address": "0xfrom1"},
                    "to": {"address": "0xto1"},
                },
                {
                    "hash": "0x2",
                    "timestamp": 1700000001,
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 500,
                    "amount_usd": 1000000,
                    "from": {"address": "0xfrom2"},
                    "to": {"address": "0xto2"},
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_transactions(min_value=500000)

            assert data.total_transfers == 2
            assert data.total_value_usd == 3000000

    @pytest.mark.asyncio
    async def test_transfer_labels_extraction(self, client):
        """测试转账标签提取"""
        mock_response = {
            "transfers": [
                {
                    "hash": "0x1",
                    "timestamp": 1700000000,
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 1000,
                    "amount_usd": 2000000,
                    "from": {"address": "0xfrom", "owner": "Binance"},
                    "to": {"address": "0xto", "owner": "Coinbase"},
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_transactions(min_value=500000)

            transfer = data.transfers[0]
            assert transfer.from_label == "Binance"
            assert transfer.to_label == "Coinbase"

    @pytest.mark.asyncio
    async def test_transfer_without_labels(self, client):
        """测试无标签的转账"""
        mock_response = {
            "transfers": [
                {
                    "hash": "0x1",
                    "timestamp": 1700000000,
                    "blockchain": "ethereum",
                    "symbol": "eth",
                    "amount": 1000,
                    "amount_usd": 2000000,
                    "from": {"address": "0xfrom"},
                    "to": {"address": "0xto"},
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_transactions(min_value=500000)

            transfer = data.transfers[0]
            assert transfer.from_label is None
            assert transfer.to_label is None
