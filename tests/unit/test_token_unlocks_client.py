"""
TokenUnlocksClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import SourceMeta, TokenUnlocksData
from src.data_sources.token_unlocks import TokenUnlocksClient


class TestTokenUnlocksClient:
    """TokenUnlocksClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TokenUnlocksClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return TokenUnlocksClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "token_unlocks"
        assert client.base_url == "https://api.token.unlocks.app/v1"

    def test_get_headers_with_key(self, client):
        """测试带API密钥的请求头"""
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test_api_key"
        assert headers["Accept"] == "application/json"

    def test_get_headers_without_key(self, client_without_key):
        """测试无API密钥的请求头"""
        headers = client_without_key._get_headers()
        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_get_upcoming_unlocks(self, client):
        """测试获取即将到来的代币解锁"""
        mock_response = {
            "events": [
                {
                    "project": "Arbitrum",
                    "token_symbol": "ARB",
                    "unlock_date": "2025-03-16",
                    "unlock_amount": 1000000,
                    "unlock_value_usd": 2000000,
                    "percentage_of_supply": 0.5,
                    "cliff_type": "cliff",
                    "description": "Team unlock",
                },
                {
                    "project": "Optimism",
                    "token_symbol": "OP",
                    "unlock_date": "2025-03-20",
                    "unlock_amount": 500000,
                    "unlock_value_usd": 1500000,
                    "percentage_of_supply": 0.3,
                    "cliff_type": "linear",
                    "description": "Investor unlock",
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_upcoming_unlocks(
                token_symbol="ARB",
                days_ahead=30,
                limit=50,
            )

            assert isinstance(data, TokenUnlocksData)
            assert data.token_symbol == "ARB"
            assert len(data.upcoming_unlocks) == 2
            assert data.total_locked_value_usd == 3500000
            assert data.next_unlock_date == "2025-03-16"

            # 验证第一个事件
            event = data.upcoming_unlocks[0]
            assert event.project == "Arbitrum"
            assert event.unlock_amount == 1000000
            assert event.cliff_type == "cliff"
            assert event.source == "token_unlocks"

    @pytest.mark.asyncio
    async def test_get_upcoming_unlocks_without_token_filter(self, client):
        """测试无代币过滤的解锁查询"""
        mock_response = {"events": []}

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_upcoming_unlocks(days_ahead=30)

            assert data.token_symbol is None
            call_params = mock_fetch.call_args[1]["params"]
            assert "symbol" not in call_params

    @pytest.mark.asyncio
    async def test_get_upcoming_unlocks_empty(self, client):
        """测试空解锁数据"""
        mock_response = {"events": []}

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_upcoming_unlocks("XYZ")

            assert data.total_locked_value_usd == 0
            assert data.next_unlock_date is None
            assert len(data.upcoming_unlocks) == 0

    @pytest.mark.asyncio
    async def test_get_token_vesting(self, client):
        """测试获取代币vesting计划"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_token_vesting("ARB")

            mock_fetch.assert_called_once_with(
                endpoint="/token/ARB/vesting",
                params={},
                data_type="vesting",
                ttl_seconds=86400,
            )

    @pytest.mark.asyncio
    async def test_get_token_vesting_lowercase(self, client):
        """测试代币符号转换为大写"""
        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_token_vesting("arb")

            call_endpoint = mock_fetch.call_args[1]["endpoint"]
            assert call_endpoint == "/token/ARB/vesting"

    def test_transform_unlocks(self, client):
        """测试解锁数据转换"""
        raw_data = {
            "status": "success",
            "data": [
                {
                    "project": "Test",
                    "token_symbol": "TEST",
                    "unlock_date": "2025-01-01",
                    "unlock_amount": 1000,
                    "unlock_value_usd": 10000,
                    "percentage_of_supply": 0.1,
                    "cliff_type": "cliff",
                },
            ]
        }

        result = client._transform_unlocks(raw_data)

        assert len(result["events"]) == 1
        assert result["events"][0]["project"] == "Test"

    def test_transform_unlocks_list_format(self, client):
        """测试列表格式的解锁数据转换"""
        raw_data = [
            {
                "name": "Test",
                "symbol": "TEST",
                "date": "2025-01-01",
                "amount": 1000,
                "value_usd": 10000,
                "percent": 0.1,
                "type": "linear",
            },
        ]

        result = client._transform_unlocks(raw_data)

        assert len(result["events"]) == 1
        # 验证备用字段名映射
        assert result["events"][0]["project"] == "Test"
        assert result["events"][0]["token_symbol"] == "TEST"
        assert result["events"][0]["cliff_type"] == "linear"

    def test_transform_unlocks_empty(self, client):
        """测试空数据转换"""
        assert client._transform_unlocks(None) == {"events": []}
        assert client._transform_unlocks({}) == {"events": []}

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """测试健康检查成功"""
        with patch.object(client, "get_upcoming_unlocks") as mock_get:
            mock_data = MagicMock(spec=TokenUnlocksData)
            mock_get.return_value = (mock_data, MagicMock())

            result = await client.health_check()

            assert result is True
            mock_get.assert_called_once_with(days_ahead=7, limit=1)

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, "get_upcoming_unlocks") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_fetch_parameters(self, client):
        """测试fetch调用参数"""
        mock_response = {"events": []}

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            await client.get_upcoming_unlocks(
                token_symbol="ETH",
                days_ahead=60,
                limit=100,
            )

            mock_fetch.assert_called_once_with(
                endpoint="/unlocks",
                params={
                    "days": 60,
                    "limit": 100,
                    "symbol": "ETH",
                },
                data_type="unlocks",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_next_unlock_date_sorting(self, client):
        """测试最近解锁日期排序"""
        mock_response = {
            "events": [
                {
                    "project": "Later",
                    "token_symbol": "LATER",
                    "unlock_date": "2025-04-01",
                    "unlock_amount": 100,
                },
                {
                    "project": "Earlier",
                    "token_symbol": "EARLY",
                    "unlock_date": "2025-02-01",
                    "unlock_amount": 100,
                },
                {
                    "project": "Middle",
                    "token_symbol": "MID",
                    "unlock_date": "2025-03-01",
                    "unlock_amount": 100,
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_upcoming_unlocks()

            # 验证最近解锁日期是最早的
            assert data.next_unlock_date == "2025-02-01"

    @pytest.mark.asyncio
    async def test_value_calculation_with_none(self, client):
        """测试包含None值的金额计算"""
        mock_response = {
            "events": [
                {
                    "project": "A",
                    "token_symbol": "A",
                    "unlock_date": "2025-01-01",
                    "unlock_amount": 100,
                    "unlock_value_usd": 1000,
                },
                {
                    "project": "B",
                    "token_symbol": "B",
                    "unlock_date": "2025-01-02",
                    "unlock_amount": 100,
                    "unlock_value_usd": None,  # 无USD价值
                },
            ]
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_upcoming_unlocks()

            # None值应被视为0
            assert data.total_locked_value_usd == 1000
