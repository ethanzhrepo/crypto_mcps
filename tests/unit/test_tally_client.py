"""
TallyClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.models import GovernanceData, SourceMeta
from src.data_sources.tally import TallyClient


class TestTallyClient:
    """TallyClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TallyClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return TallyClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "tally"
        assert client.GRAPHQL_URL == "https://api.tally.xyz/query"

    def test_init_without_api_key(self, client_without_key):
        """测试无API密钥初始化"""
        assert client_without_key.api_key is None

    @pytest.mark.asyncio
    async def test_get_proposals(self, client):
        """测试获取链上治理提案"""
        mock_response = {
            "data": {
                "proposals": {
                    "nodes": [
                        {
                            "id": "proposal-1",
                            "title": "Upgrade Contract",
                            "description": "Upgrade to v2",
                            "eta": None,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "start": {"timestamp": "1704067200"},
                            "end": {"timestamp": "1704326400"},
                            "status": "ACTIVE",
                            "governor": {"name": "Compound Governor"},
                            "proposer": {"address": "0xproposer"},
                            "voteStats": [
                                {"votes": 100, "weight": "1000000", "support": "FOR"},
                                {"votes": 50, "weight": "500000", "support": "AGAINST"},
                                {"votes": 10, "weight": "100000", "support": "ABSTAIN"},
                            ],
                        },
                    ]
                },
                "governor": {
                    "name": "Compound Governor",
                    "proposalCount": 50,
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

            data, meta = await client.get_proposals(
                governor_address="0xgovernor",
                chain_id="eip155:1",
                limit=20,
            )

            assert isinstance(data, GovernanceData)
            assert data.dao == "Compound Governor"
            assert data.total_proposals == 50
            assert data.active_proposals == 1
            assert len(data.recent_proposals) == 1
            assert data.recent_proposals[0].id == "proposal-1"
            assert data.recent_proposals[0].state == "active"

    @pytest.mark.asyncio
    async def test_get_proposals_different_chains(self, client):
        """测试不同链的治理提案"""
        mock_response = {
            "data": {
                "proposals": {"nodes": []},
                "governor": {"name": "Test", "proposalCount": 0},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            # 测试以太坊
            await client.get_proposals("0xgov", chain_id="eip155:1")
            call_vars = mock_http.post.call_args[1]["json"]["variables"]
            assert call_vars["governorId"] == "eip155:1:0xgov"

            # 测试Polygon
            await client.get_proposals("0xgov", chain_id="eip155:137")
            call_vars = mock_http.post.call_args[1]["json"]["variables"]
            assert call_vars["governorId"] == "eip155:137:0xgov"

    @pytest.mark.asyncio
    async def test_get_proposals_api_error(self, client):
        """测试API错误处理"""
        mock_response = {
            "errors": [{"message": "Invalid governor ID"}]
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            with pytest.raises(Exception, match="Tally API error"):
                await client.get_proposals("0xgov")

    def test_map_tally_status(self, client):
        """测试状态映射"""
        assert client._map_tally_status("PENDING") == "pending"
        assert client._map_tally_status("ACTIVE") == "active"
        assert client._map_tally_status("CANCELED") == "closed"
        assert client._map_tally_status("DEFEATED") == "closed"
        assert client._map_tally_status("SUCCEEDED") == "closed"
        assert client._map_tally_status("QUEUED") == "closed"
        assert client._map_tally_status("EXPIRED") == "closed"
        assert client._map_tally_status("EXECUTED") == "closed"
        assert client._map_tally_status("UNKNOWN") == "unknown"
        # 测试大小写不敏感
        assert client._map_tally_status("active") == "active"
        assert client._map_tally_status("Active") == "active"

    @pytest.mark.asyncio
    async def test_get_governor_info(self, client):
        """测试获取Governor信息"""
        mock_response = {
            "data": {
                "governor": {
                    "id": "eip155:1:0xgov",
                    "name": "Uniswap Governor",
                    "type": "OPENZEPPELIN",
                    "proposalCount": 100,
                    "votersCount": 5000,
                    "tokenOwnersCount": 100000,
                    "delegatesCount": 1000,
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

            data, meta = await client.get_governor_info("0xgov", "eip155:1")

            assert data["name"] == "Uniswap Governor"
            assert data["proposalCount"] == 100
            assert data["votersCount"] == 5000

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
        _ = client.client
        assert client._client is not None

        await client.close()
        assert client._client is None

    def test_client_property_with_api_key(self, client):
        """测试带API密钥的客户端属性"""
        http_client = client.client
        assert http_client is not None
        assert "Api-Key" in http_client.headers

    def test_client_property_without_api_key(self, client_without_key):
        """测试无API密钥的客户端属性"""
        http_client = client_without_key.client
        assert http_client is not None
        assert "Api-Key" not in http_client.headers

    @pytest.mark.asyncio
    async def test_vote_stats_parsing(self, client):
        """测试投票统计解析"""
        mock_response = {
            "data": {
                "proposals": {
                    "nodes": [
                        {
                            "id": "1",
                            "title": "Test",
                            "description": "",
                            "eta": None,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "start": {"timestamp": "1704067200"},
                            "end": {"timestamp": "1704326400"},
                            "status": "ACTIVE",
                            "governor": {"name": "Test"},
                            "proposer": {"address": "0x"},
                            "voteStats": [
                                {"votes": 100, "weight": "1000000000000000000", "support": "FOR"},
                                {"votes": 50, "weight": "500000000000000000", "support": "AGAINST"},
                            ],
                        },
                    ]
                },
                "governor": {"name": "Test", "proposalCount": 1},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("0xgov")

            proposal = data.recent_proposals[0]
            assert proposal.choices == ["FOR", "AGAINST"]
            assert len(proposal.scores) == 2
            assert proposal.scores[0] == 1000000000000000000.0

    @pytest.mark.asyncio
    async def test_empty_vote_stats(self, client):
        """测试空投票统计"""
        mock_response = {
            "data": {
                "proposals": {
                    "nodes": [
                        {
                            "id": "1",
                            "title": "Test",
                            "description": "",
                            "eta": None,
                            "createdAt": "2024-01-01T00:00:00Z",
                            "start": {"timestamp": "1704067200"},
                            "end": {"timestamp": "1704326400"},
                            "status": "ACTIVE",
                            "governor": {"name": "Test"},
                            "proposer": {"address": "0x"},
                            "voteStats": [],
                        },
                    ]
                },
                "governor": {"name": "Test", "proposalCount": 1},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("0xgov")

            proposal = data.recent_proposals[0]
            # 默认选项
            assert proposal.choices == ["For", "Against", "Abstain"]

    @pytest.mark.asyncio
    async def test_source_meta_generation(self, client):
        """测试SourceMeta生成"""
        mock_response = {
            "data": {
                "proposals": {"nodes": []},
                "governor": {"name": "Test", "proposalCount": 0},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("0xgov")

            assert meta.provider == "tally"
            assert "0xgov" in meta.endpoint
            assert meta.ttl_seconds == 300

    @pytest.mark.asyncio
    async def test_multiple_proposal_states_count(self, client):
        """测试多种状态提案计数"""
        mock_response = {
            "data": {
                "proposals": {
                    "nodes": [
                        self._create_mock_proposal("1", "ACTIVE"),
                        self._create_mock_proposal("2", "ACTIVE"),
                        self._create_mock_proposal("3", "SUCCEEDED"),
                        self._create_mock_proposal("4", "DEFEATED"),
                        self._create_mock_proposal("5", "PENDING"),
                    ]
                },
                "governor": {"name": "Test", "proposalCount": 5},
            }
        }

        with patch.object(client, "client") as mock_http:
            mock_http.post = AsyncMock()
            mock_http.post.return_value = MagicMock(
                status_code=200,
                json=MagicMock(return_value=mock_response),
                raise_for_status=MagicMock(),
            )

            data, meta = await client.get_proposals("0xgov")

            assert data.active_proposals == 2

    def _create_mock_proposal(self, id: str, status: str):
        """创建模拟提案数据"""
        return {
            "id": id,
            "title": f"Proposal {id}",
            "description": "",
            "eta": None,
            "createdAt": "2024-01-01T00:00:00Z",
            "start": {"timestamp": "1704067200"},
            "end": {"timestamp": "1704326400"},
            "status": status,
            "governor": {"name": "Test"},
            "proposer": {"address": "0x"},
            "voteStats": [],
        }
