"""
SnapshotClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.models import GovernanceData, SourceMeta
from src.data_sources.snapshot import SnapshotClient


class TestSnapshotClient:
    """SnapshotClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return SnapshotClient()

    def test_init(self, client):
        """测试初始化"""
        assert client.name == "snapshot"
        assert client.GRAPHQL_URL == "https://hub.snapshot.org/graphql"

    @pytest.mark.asyncio
    async def test_get_proposals(self, client):
        """测试获取治理提案"""
        mock_response = {
            "data": {
                "proposals": [
                    {
                        "id": "proposal-1",
                        "title": "Test Proposal",
                        "state": "active",
                        "start": 1700000000,
                        "end": 1700100000,
                        "choices": ["Yes", "No"],
                        "scores": [100.0, 50.0],
                        "author": "0xauthor",
                    },
                    {
                        "id": "proposal-2",
                        "title": "Closed Proposal",
                        "state": "closed",
                        "start": 1699900000,
                        "end": 1699950000,
                        "choices": ["For", "Against"],
                        "scores": [200.0, 100.0],
                        "author": "0xauthor2",
                    },
                ],
                "space": {
                    "id": "uniswap.eth",
                    "name": "Uniswap",
                    "proposalsCount": 100,
                },
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("uniswap.eth", limit=20)

            assert isinstance(data, GovernanceData)
            assert data.dao == "Uniswap"
            assert data.total_proposals == 100
            assert data.active_proposals == 1
            assert len(data.recent_proposals) == 2
            assert data.recent_proposals[0].id == "proposal-1"
            assert data.recent_proposals[0].title == "Test Proposal"
            assert data.recent_proposals[0].state == "active"
            assert data.recent_proposals[0].choices == ["Yes", "No"]
            assert data.recent_proposals[0].scores == [100.0, 50.0]

    @pytest.mark.asyncio
    async def test_get_proposals_with_state_filter(self, client):
        """测试按状态过滤提案"""
        mock_response = {
            "data": {
                "proposals": [],
                "space": {"name": "Test", "proposalsCount": 50},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            await client.get_proposals("test.eth", state="active", limit=10)

            # 验证请求包含状态过滤
            call_args = mock_http.post.call_args
            query = call_args[1]["json"]["query"]
            assert 'state: "active"' in query

    @pytest.mark.asyncio
    async def test_get_proposals_empty_response(self, client):
        """测试空响应"""
        mock_response = {
            "data": {
                "proposals": [],
                "space": {"name": "Empty DAO", "proposalsCount": 0},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("empty.eth")

            assert data.dao == "Empty DAO"
            assert data.total_proposals == 0
            assert data.active_proposals == 0
            assert len(data.recent_proposals) == 0

    @pytest.mark.asyncio
    async def test_get_proposals_api_error(self, client):
        """测试API错误处理"""
        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                await client.get_proposals("test.eth")

    @pytest.mark.asyncio
    async def test_get_space_info(self, client):
        """测试获取空间信息"""
        mock_response = {
            "data": {
                "space": {
                    "id": "uniswap.eth",
                    "name": "Uniswap",
                    "about": "Uniswap Governance",
                    "network": "1",
                    "symbol": "UNI",
                    "members": ["0x1", "0x2"],
                    "proposalsCount": 100,
                    "votesCount": 5000,
                    "followersCount": 10000,
                }
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_space_info("uniswap.eth")

            assert data["id"] == "uniswap.eth"
            assert data["name"] == "Uniswap"
            assert data["proposalsCount"] == 100
            assert data["votesCount"] == 5000

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """测试健康检查成功"""
        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(status_code=200)

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(status_code=500)

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, client):
        """测试健康检查异常"""
        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.side_effect = Exception("Connection error")

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_close(self, client):
        """测试关闭客户端"""
        # 创建客户端实例
        _ = client.client
        assert client._client is not None

        await client.close()
        assert client._client is None

    def test_client_property_creates_instance(self, client):
        """测试client属性创建实例"""
        assert client._client is None
        http_client = client.client
        assert http_client is not None
        assert client._client is http_client

    def test_client_property_reuses_instance(self, client):
        """测试client属性复用实例"""
        http_client1 = client.client
        http_client2 = client.client
        assert http_client1 is http_client2

    @pytest.mark.asyncio
    async def test_source_meta_generation(self, client):
        """测试SourceMeta生成"""
        mock_response = {
            "data": {
                "proposals": [],
                "space": {"name": "Test", "proposalsCount": 0},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("test.eth")

            assert meta.provider == "snapshot"
            assert "test.eth" in meta.endpoint
            assert meta.ttl_seconds == 300

    @pytest.mark.asyncio
    async def test_proposal_timestamp_conversion(self, client):
        """测试提案时间戳转换"""
        mock_response = {
            "data": {
                "proposals": [
                    {
                        "id": "1",
                        "title": "Test",
                        "state": "active",
                        "start": 1700000000,
                        "end": 1700100000,
                        "choices": [],
                        "scores": [],
                        "author": "0x",
                    },
                ],
                "space": {"name": "Test", "proposalsCount": 1},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("test.eth")

            proposal = data.recent_proposals[0]
            # 验证时间戳已转换为ISO格式
            assert "Z" in proposal.start_time
            assert "Z" in proposal.end_time

    @pytest.mark.asyncio
    async def test_active_proposals_count(self, client):
        """测试活跃提案计数"""
        mock_response = {
            "data": {
                "proposals": [
                    {"id": "1", "title": "A", "state": "active", "start": 0, "end": 0, "choices": [], "scores": [], "author": ""},
                    {"id": "2", "title": "B", "state": "active", "start": 0, "end": 0, "choices": [], "scores": [], "author": ""},
                    {"id": "3", "title": "C", "state": "closed", "start": 0, "end": 0, "choices": [], "scores": [], "author": ""},
                    {"id": "4", "title": "D", "state": "pending", "start": 0, "end": 0, "choices": [], "scores": [], "author": ""},
                ],
                "space": {"name": "Test", "proposalsCount": 4},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("test.eth")

            assert data.active_proposals == 2

    @pytest.mark.asyncio
    async def test_missing_space_data(self, client):
        """测试缺失空间数据时的默认值"""
        mock_response = {
            "data": {
                "proposals": [],
                "space": {},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("test.eth")

            # 使用空间ID作为默认名称
            assert data.dao == "test.eth"
            assert data.total_proposals == 0
