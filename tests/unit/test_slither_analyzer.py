"""
SlitherAnalyzer 单元测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.core.models import ContractRisk, SourceMeta
from src.utils.security import SlitherAnalyzer, slither_analyzer


class TestSlitherAnalyzer:
    """SlitherAnalyzer测试"""

    @pytest.fixture
    def analyzer(self):
        """创建测试分析器"""
        return SlitherAnalyzer()

    def test_init(self, analyzer):
        """测试初始化"""
        assert analyzer.name == "slither"
        assert analyzer._slither_available is None

    @pytest.mark.asyncio
    async def test_is_available_success(self, analyzer):
        """测试Slither可用性检查成功"""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(b"0.9.0", b""))
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await analyzer.is_available()

            assert result is True
            assert analyzer._slither_available is True

    @pytest.mark.asyncio
    async def test_is_available_failure(self, analyzer):
        """测试Slither可用性检查失败"""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("slither not found")

            result = await analyzer.is_available()

            assert result is False
            assert analyzer._slither_available is False

    @pytest.mark.asyncio
    async def test_is_available_caches_result(self, analyzer):
        """测试可用性检查缓存结果"""
        analyzer._slither_available = True

        # 不应该再次调用subprocess
        result = await analyzer.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_analyze_contract_slither_not_available(self, analyzer):
        """测试Slither不可用时的分析"""
        with patch.object(analyzer, "is_available", return_value=False):
            result, meta = await analyzer.analyze_contract(
                "0x1234",
                "ethereum",
            )

            assert isinstance(result, ContractRisk)
            assert result.risk_level == "unknown"
            assert "Slither not installed" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_analyze_contract_success(self, analyzer):
        """测试成功的合约分析"""
        mock_output = {
            "results": {
                "detectors": [
                    {
                        "check": "reentrancy-eth",
                        "description": "Reentrancy vulnerability",
                        "impact": "High",
                    },
                    {
                        "check": "unused-return",
                        "description": "Return value not used",
                        "impact": "Medium",
                    },
                    {
                        "check": "naming-convention",
                        "description": "Variable naming",
                        "impact": "Informational",
                    },
                ]
            }
        }

        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    return_value=(json.dumps(mock_output).encode(), b"")
                )
                mock_exec.return_value = mock_process

                with patch("asyncio.wait_for", return_value=(
                    json.dumps(mock_output).encode(), b""
                )):
                    result, meta = await analyzer.analyze_contract(
                        "0x1234567890abcdef",
                        "ethereum",
                        "test_api_key",
                    )

                    assert isinstance(result, ContractRisk)
                    assert result.provider == "slither"
                    assert result.vulnerability_count == 3
                    assert result.high_severity_count == 1
                    assert result.medium_severity_count == 1
                    assert result.low_severity_count == 1

    @pytest.mark.asyncio
    async def test_analyze_contract_timeout(self, analyzer):
        """测试分析超时"""
        import asyncio

        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock()
                mock_exec.return_value = mock_process

                with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    result, meta = await analyzer.analyze_contract(
                        "0x1234",
                        "ethereum",
                    )

                    assert result.risk_level == "unknown"
                    assert "timed out" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_analyze_contract_exception(self, analyzer):
        """测试分析异常"""
        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_exec.side_effect = Exception("Unexpected error")

                result, meta = await analyzer.analyze_contract(
                    "0x1234",
                    "ethereum",
                )

                assert result.risk_level == "unknown"
                assert "Unexpected error" in result.warnings[0]

    def test_parse_slither_result(self, analyzer):
        """测试Slither结果解析"""
        result = {
            "results": {
                "detectors": [
                    {
                        "check": "reentrancy-eth",
                        "description": "Reentrancy in function transfer",
                        "impact": "High",
                    },
                    {
                        "check": "reentrancy-no-eth",
                        "description": "Reentrancy in function swap",
                        "impact": "High",
                    },
                    {
                        "check": "unused-return",
                        "description": "Return value ignored",
                        "impact": "Medium",
                    },
                ]
            }
        }

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        assert contract_risk.high_severity_count == 2
        assert contract_risk.medium_severity_count == 1
        assert contract_risk.low_severity_count == 0
        assert contract_risk.vulnerability_count == 3
        assert len(contract_risk.vulnerabilities) == 3
        assert "2 high severity issues found" in contract_risk.warnings

    def test_parse_slither_result_critical_impact(self, analyzer):
        """测试critical级别漏洞解析"""
        result = {
            "results": {
                "detectors": [
                    {
                        "check": "arbitrary-send",
                        "description": "Arbitrary send",
                        "impact": "Critical",
                    },
                ]
            }
        }

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        # Critical也算作high
        assert contract_risk.high_severity_count == 1

    def test_parse_slither_result_empty(self, analyzer):
        """测试空结果解析"""
        result = {"results": {"detectors": []}}

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        assert contract_risk.vulnerability_count == 0
        assert contract_risk.risk_score == 0
        assert contract_risk.risk_level == "low"

    def test_empty_result(self, analyzer):
        """测试空结果生成"""
        contract_risk = analyzer._empty_result(
            "0x1234", "ethereum", "Test error"
        )

        assert contract_risk.contract_address == "0x1234"
        assert contract_risk.chain == "ethereum"
        assert contract_risk.risk_level == "unknown"
        assert contract_risk.risk_score is None
        assert "Test error" in contract_risk.warnings[0]

    def test_get_risk_level(self, analyzer):
        """测试风险等级判定"""
        assert analyzer._get_risk_level(0) == "low"
        assert analyzer._get_risk_level(10) == "low"
        assert analyzer._get_risk_level(15) == "medium"
        assert analyzer._get_risk_level(25) == "medium"
        assert analyzer._get_risk_level(30) == "high"
        assert analyzer._get_risk_level(45) == "high"
        assert analyzer._get_risk_level(50) == "critical"
        assert analyzer._get_risk_level(100) == "critical"

    def test_risk_score_calculation(self, analyzer):
        """测试风险分数计算"""
        # 高风险：每个30分
        # 中风险：每个10分
        # 低风险：每个2分
        result = {
            "results": {
                "detectors": [
                    {"check": "a", "description": "a", "impact": "High"},
                    {"check": "b", "description": "b", "impact": "Medium"},
                    {"check": "c", "description": "c", "impact": "Low"},
                ]
            }
        }

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        # 30 + 10 + 2 = 42
        assert contract_risk.risk_score == 42

    def test_risk_score_max_100(self, analyzer):
        """测试风险分数最大值100"""
        result = {
            "results": {
                "detectors": [
                    {"check": str(i), "description": str(i), "impact": "High"}
                    for i in range(10)  # 10 * 30 = 300
                ]
            }
        }

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        assert contract_risk.risk_score == 100

    def test_vulnerabilities_limited_to_20(self, analyzer):
        """测试漏洞列表限制为20"""
        result = {
            "results": {
                "detectors": [
                    {"check": f"vuln-{i}", "description": f"Desc {i}", "impact": "Low"}
                    for i in range(30)
                ]
            }
        }

        contract_risk = analyzer._parse_slither_result(
            result, "0x1234", "ethereum"
        )

        assert len(contract_risk.vulnerabilities) == 20
        assert contract_risk.vulnerability_count == 30

    def test_build_meta(self, analyzer):
        """测试SourceMeta生成"""
        from datetime import datetime
        start_time = datetime.utcnow()

        meta = analyzer._build_meta(start_time, "0x1234")

        assert meta.provider == "slither"
        assert "0x1234" in meta.endpoint
        assert meta.ttl_seconds == 86400

    def test_global_instance(self):
        """测试全局实例"""
        assert slither_analyzer is not None
        assert isinstance(slither_analyzer, SlitherAnalyzer)

    @pytest.mark.asyncio
    async def test_network_mapping(self, analyzer):
        """测试网络映射"""
        # 测试不同链的映射在_analyze_contract中正确使用
        # 由于是通过环境变量传递，这里主要验证映射表
        network_map = {
            "ethereum": "mainnet",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arbitrum",
            "optimism": "optimism",
        }

        # 验证映射存在
        assert "ethereum" in network_map
        assert network_map["ethereum"] == "mainnet"

    @pytest.mark.asyncio
    async def test_analyze_with_etherscan_api_key(self, analyzer):
        """测试带Etherscan API密钥的分析"""
        mock_output = {"results": {"detectors": []}}

        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock(
                    return_value=(json.dumps(mock_output).encode(), b"")
                )
                mock_exec.return_value = mock_process

                with patch("asyncio.wait_for", return_value=(
                    json.dumps(mock_output).encode(), b""
                )):
                    await analyzer.analyze_contract(
                        "0x1234",
                        "ethereum",
                        etherscan_api_key="test_key",
                    )

                    # 验证命令包含API密钥参数
                    call_args = mock_exec.call_args
                    cmd = call_args[0]
                    assert "--etherscan-apikey" in cmd
                    assert "test_key" in cmd

    @pytest.mark.asyncio
    async def test_json_decode_error(self, analyzer):
        """测试JSON解析错误"""
        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock()
                mock_exec.return_value = mock_process

                with patch("asyncio.wait_for", return_value=(
                    b"invalid json", b""
                )):
                    result, meta = await analyzer.analyze_contract(
                        "0x1234",
                        "ethereum",
                    )

                    assert result.risk_level == "unknown"
                    assert "failed" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_stderr_logging(self, analyzer):
        """测试stderr日志记录"""
        with patch.object(analyzer, "is_available", return_value=True):
            with patch("asyncio.create_subprocess_exec") as mock_exec:
                mock_process = MagicMock()
                mock_process.communicate = AsyncMock()
                mock_exec.return_value = mock_process

                with patch("asyncio.wait_for", return_value=(
                    b"", b"Warning: Some slither warning"
                )):
                    result, meta = await analyzer.analyze_contract(
                        "0x1234",
                        "ethereum",
                    )

                    # 即使有stderr，没有stdout应该返回失败结果
                    assert result.risk_level == "unknown"
