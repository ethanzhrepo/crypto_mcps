"""
GoPlusClient 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import ContractRisk, SourceMeta
from src.data_sources.goplus import GoPlusClient


class TestGoPlusClient:
    """GoPlusClient测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return GoPlusClient(api_key="test_api_key")

    @pytest.fixture
    def client_without_key(self):
        """创建无API密钥的客户端"""
        return GoPlusClient()

    def test_init_with_api_key(self, client):
        """测试使用API密钥初始化"""
        assert client.api_key == "test_api_key"
        assert client.name == "goplus"
        assert client.base_url == "https://api.gopluslabs.io/api/v1"

    def test_init_without_api_key(self, client_without_key):
        """测试无API密钥初始化（免费版）"""
        assert client_without_key.requires_api_key is False

    def test_get_headers_with_key(self, client):
        """测试带API密钥的请求头"""
        headers = client._get_headers()
        assert headers["Authorization"] == "test_api_key"
        assert headers["Accept"] == "application/json"

    def test_get_headers_without_key(self, client_without_key):
        """测试无API密钥的请求头"""
        headers = client_without_key._get_headers()
        assert "Authorization" not in headers

    def test_chain_id_mapping(self, client):
        """测试链ID映射"""
        assert client.CHAIN_IDS["ethereum"] == "1"
        assert client.CHAIN_IDS["bsc"] == "56"
        assert client.CHAIN_IDS["polygon"] == "137"
        assert client.CHAIN_IDS["arbitrum"] == "42161"
        assert client.CHAIN_IDS["optimism"] == "10"
        assert client.CHAIN_IDS["base"] == "8453"

    @pytest.mark.asyncio
    async def test_get_token_security(self, client):
        """测试获取代币安全信息"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"
        mock_response = {
            contract_address.lower(): {
                "is_open_source": "1",
                "is_proxy": "0",
                "is_mintable": "0",
                "is_honeypot": "0",
                "buy_tax": "0.01",
                "sell_tax": "0.02",
                "holder_count": "1000",
            }
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_token_security(contract_address, "ethereum")

            assert isinstance(data, ContractRisk)
            assert data.contract_address == contract_address
            assert data.chain == "ethereum"
            assert data.provider == "goplus"
            assert data.is_open_source is True
            assert data.is_proxy is False
            assert data.is_mintable is False
            assert data.is_honeypot is False
            assert data.buy_tax == 0.01
            assert data.sell_tax == 0.02

            mock_fetch.assert_called_once_with(
                endpoint="/token_security/1",
                params={"contract_addresses": contract_address.lower()},
                data_type="token_security",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_get_token_security_different_chains(self, client):
        """测试不同链的代币安全检查"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            # 测试BSC
            await client.get_token_security(contract_address, "bsc")
            assert mock_fetch.call_args[1]["endpoint"] == "/token_security/56"

            # 测试Polygon
            await client.get_token_security(contract_address, "polygon")
            assert mock_fetch.call_args[1]["endpoint"] == "/token_security/137"

            # 测试Arbitrum
            await client.get_token_security(contract_address, "arbitrum")
            assert mock_fetch.call_args[1]["endpoint"] == "/token_security/42161"

    @pytest.mark.asyncio
    async def test_get_token_security_honeypot_detection(self, client):
        """测试蜜罐检测"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"
        mock_response = {
            contract_address.lower(): {
                "is_honeypot": "1",
                "hidden_owner": "1",
            }
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_token_security(contract_address, "ethereum")

            assert data.is_honeypot is True
            assert data.risk_score >= 50  # 高风险
            assert data.risk_level == "critical"
            assert "Honeypot detected" in data.warnings
            assert "Hidden owner detected" in data.warnings

    @pytest.mark.asyncio
    async def test_get_token_security_high_tax(self, client):
        """测试高税费检测"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"
        mock_response = {
            contract_address.lower(): {
                "buy_tax": "0.15",
                "sell_tax": "0.20",
            }
        }

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = (mock_response, mock_meta)

            data, meta = await client.get_token_security(contract_address, "ethereum")

            assert data.buy_tax == 0.15
            assert data.sell_tax == 0.20
            assert any("buy tax" in w.lower() for w in data.warnings)
            assert any("sell tax" in w.lower() for w in data.warnings)

    def test_transform_token_security(self, client):
        """测试代币安全数据转换"""
        raw_data = {
            "code": 1,
            "result": {
                "0x1234": {
                    "is_open_source": "1",
                    "is_proxy": "0",
                }
            }
        }

        result = client._transform_token_security(raw_data)
        assert "0x1234" in result
        assert result["0x1234"]["is_open_source"] == "1"

    def test_transform_token_security_error_code(self, client):
        """测试错误响应码"""
        raw_data = {"code": 0, "message": "error"}
        result = client._transform_token_security(raw_data)
        assert result == {}

    def test_transform_token_security_empty(self, client):
        """测试空数据转换"""
        assert client._transform_token_security(None) == {}
        assert client._transform_token_security({}) == {}

    def test_bool_from_str(self, client):
        """测试字符串转布尔值"""
        assert client._bool_from_str("1") is True
        assert client._bool_from_str("0") is False
        assert client._bool_from_str("true") is True
        assert client._bool_from_str("false") is False
        assert client._bool_from_str(True) is True
        assert client._bool_from_str(False) is False
        assert client._bool_from_str(None) is None
        assert client._bool_from_str(1) is True
        assert client._bool_from_str(0) is False

    def test_safe_float(self, client):
        """测试安全浮点数转换"""
        assert client._safe_float("0.01") == 0.01
        assert client._safe_float("1.5") == 1.5
        assert client._safe_float(0.5) == 0.5
        assert client._safe_float(None) is None
        assert client._safe_float("") is None
        assert client._safe_float("invalid") is None

    def test_safe_int(self, client):
        """测试安全整数转换"""
        assert client._safe_int("100") == 100
        assert client._safe_int(50) == 50
        assert client._safe_int(None) is None
        assert client._safe_int("") is None
        assert client._safe_int("invalid") is None

    def test_calculate_risk_score_low_risk(self, client):
        """测试低风险分数计算"""
        token_data = {
            "is_open_source": "1",
            "is_honeypot": "0",
            "hidden_owner": "0",
        }
        score = client._calculate_risk_score(token_data)
        assert score < 15

    def test_calculate_risk_score_high_risk(self, client):
        """测试高风险分数计算"""
        token_data = {
            "is_honeypot": "1",
            "hidden_owner": "1",
        }
        score = client._calculate_risk_score(token_data)
        assert score >= 50

    def test_calculate_risk_score_medium_risk(self, client):
        """测试中等风险分数计算"""
        token_data = {
            "is_mintable": "1",
            "owner_change_balance": "1",
            "buy_tax": "0.08",
        }
        score = client._calculate_risk_score(token_data)
        assert 15 <= score < 50

    def test_calculate_risk_score_max_100(self, client):
        """测试风险分数最大值为100"""
        token_data = {
            "is_honeypot": "1",
            "hidden_owner": "1",
            "selfdestruct": "1",
            "can_take_back_ownership": "1",
            "is_mintable": "1",
            "owner_change_balance": "1",
            "external_call": "1",
            "buy_tax": "0.50",
            "sell_tax": "0.50",
        }
        score = client._calculate_risk_score(token_data)
        assert score <= 100

    def test_calculate_risk_score_min_0(self, client):
        """测试风险分数最小值为0"""
        token_data = {
            "is_open_source": "1",
        }
        score = client._calculate_risk_score(token_data)
        assert score >= 0

    def test_get_risk_level(self, client):
        """测试风险等级判定"""
        assert client._get_risk_level(0) == "low"
        assert client._get_risk_level(10) == "low"
        assert client._get_risk_level(15) == "medium"
        assert client._get_risk_level(25) == "medium"
        assert client._get_risk_level(30) == "high"
        assert client._get_risk_level(45) == "high"
        assert client._get_risk_level(50) == "critical"
        assert client._get_risk_level(100) == "critical"

    def test_extract_warnings(self, client):
        """测试警告信息提取"""
        token_data = {
            "is_honeypot": "1",
            "hidden_owner": "1",
            "selfdestruct": "1",
            "can_take_back_ownership": "1",
            "is_mintable": "1",
            "buy_tax": "0.15",
            "sell_tax": "0.20",
        }

        warnings = client._extract_warnings(token_data)

        assert "Honeypot detected" in warnings
        assert "Hidden owner detected" in warnings
        assert "Contract can self-destruct" in warnings
        assert "Ownership can be taken back" in warnings
        assert "Token is mintable" in warnings
        assert any("buy tax" in w.lower() for w in warnings)
        assert any("sell tax" in w.lower() for w in warnings)

    def test_extract_warnings_no_issues(self, client):
        """测试无警告情况"""
        token_data = {
            "is_honeypot": "0",
            "is_open_source": "1",
            "buy_tax": "0.01",
            "sell_tax": "0.01",
        }

        warnings = client._extract_warnings(token_data)
        assert len(warnings) == 0

    @pytest.mark.asyncio
    async def test_get_address_security(self, client):
        """测试获取地址安全信息"""
        address = "0xabcdef1234567890abcdef1234567890abcdef12"

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_address_security(address, "ethereum")

            mock_fetch.assert_called_once_with(
                endpoint=f"/address_security/{address}",
                params={"chain_id": "1"},
                data_type="address_security",
                ttl_seconds=3600,
            )

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """测试健康检查成功"""
        with patch.object(client, "get_token_security") as mock_get:
            mock_get.return_value = (MagicMock(), MagicMock())

            result = await client.health_check()

            assert result is True
            # 验证使用WETH地址检查
            mock_get.assert_called_once_with(
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "ethereum"
            )

    @pytest.mark.asyncio
    async def test_health_check_failure(self, client):
        """测试健康检查失败"""
        with patch.object(client, "get_token_security") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result = await client.health_check()

            assert result is False

    @pytest.mark.asyncio
    async def test_get_token_security_empty_data(self, client):
        """测试空数据响应"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            data, meta = await client.get_token_security(contract_address, "ethereum")

            assert isinstance(data, ContractRisk)
            assert data.risk_score == 0
            assert data.risk_level == "low"

    @pytest.mark.asyncio
    async def test_contract_address_lowercase_conversion(self, client):
        """测试合约地址转换为小写"""
        contract_address = "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_token_security(contract_address, "ethereum")

            call_params = mock_fetch.call_args[1]["params"]
            assert call_params["contract_addresses"] == contract_address.lower()

    @pytest.mark.asyncio
    async def test_unknown_chain_defaults_to_ethereum(self, client):
        """测试未知链默认使用以太坊"""
        contract_address = "0x1234567890abcdef1234567890abcdef12345678"

        with patch.object(client, "fetch") as mock_fetch:
            mock_meta = MagicMock(spec=SourceMeta)
            mock_fetch.return_value = ({}, mock_meta)

            await client.get_token_security(contract_address, "unknown_chain")

            assert mock_fetch.call_args[1]["endpoint"] == "/token_security/1"
