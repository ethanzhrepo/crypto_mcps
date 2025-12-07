"""
安全分析工具 - Slither静态分析封装

注意: 使用此模块需要安装slither-analyzer:
pip install slither-analyzer

以及solc编译器
"""
import asyncio
import json
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import ContractRisk, SourceMeta
from src.core.source_meta import SourceMetaBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SlitherAnalyzer:
    """Slither静态分析器封装"""

    def __init__(self):
        """初始化Slither分析器"""
        self.name = "slither"
        self._slither_available: Optional[bool] = None

    async def is_available(self) -> bool:
        """检查Slither是否可用"""
        if self._slither_available is not None:
            return self._slither_available

        try:
            result = await asyncio.create_subprocess_exec(
                "slither", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            self._slither_available = result.returncode == 0
        except Exception:
            self._slither_available = False

        return self._slither_available

    async def analyze_contract(
        self,
        contract_address: str,
        chain: str = "ethereum",
        etherscan_api_key: Optional[str] = None,
    ) -> tuple[ContractRisk, SourceMeta]:
        """
        分析合约安全性

        Args:
            contract_address: 合约地址
            chain: 链名称
            etherscan_api_key: Etherscan API密钥（用于获取合约源码）

        Returns:
            (合约风险数据, SourceMeta)
        """
        start_time = datetime.utcnow()

        if not await self.is_available():
            logger.error("Slither is not available")
            return self._empty_result(contract_address, chain, "Slither not installed"), self._build_meta(start_time, contract_address)

        # 构建Slither命令
        cmd = [
            "slither",
            contract_address,
            "--json", "-",  # 输出JSON到stdout
        ]

        # 添加Etherscan API密钥
        if etherscan_api_key:
            cmd.extend(["--etherscan-apikey", etherscan_api_key])

        # 设置网络
        network_map = {
            "ethereum": "mainnet",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arbitrum",
            "optimism": "optimism",
        }
        network = network_map.get(chain.lower(), "mainnet")

        try:
            # 运行Slither
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"ETHERSCAN_NETWORK": network},
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120,  # 2分钟超时
            )

            # 解析结果
            if stdout:
                try:
                    result = json.loads(stdout.decode())
                    contract_risk = self._parse_slither_result(result, contract_address, chain)
                    return contract_risk, self._build_meta(start_time, contract_address)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Slither output: {e}")

            # 如果没有stdout或解析失败，检查stderr
            if stderr:
                error_msg = stderr.decode()[:500]
                logger.warning(f"Slither stderr: {error_msg}")

            return self._empty_result(contract_address, chain, "Analysis failed"), self._build_meta(start_time, contract_address)

        except asyncio.TimeoutError:
            logger.error(f"Slither analysis timed out for {contract_address}")
            return self._empty_result(contract_address, chain, "Analysis timed out"), self._build_meta(start_time, contract_address)
        except Exception as e:
            logger.error(f"Slither analysis error: {e}")
            return self._empty_result(contract_address, chain, str(e)), self._build_meta(start_time, contract_address)

    def _parse_slither_result(
        self,
        result: Dict,
        contract_address: str,
        chain: str,
    ) -> ContractRisk:
        """解析Slither分析结果"""
        detectors = result.get("results", {}).get("detectors", [])

        # 统计漏洞
        vulnerabilities = []
        high_count = 0
        medium_count = 0
        low_count = 0

        for detector in detectors:
            impact = detector.get("impact", "").lower()
            check = detector.get("check", "")
            description = detector.get("description", "")

            vulnerabilities.append(f"{check}: {description[:100]}")

            if impact in ["high", "critical"]:
                high_count += 1
            elif impact == "medium":
                medium_count += 1
            else:
                low_count += 1

        # 计算风险分数
        risk_score = min(100, high_count * 30 + medium_count * 10 + low_count * 2)
        risk_level = self._get_risk_level(risk_score)

        # 生成警告
        warnings = []
        if high_count > 0:
            warnings.append(f"{high_count} high severity issues found")
        if medium_count > 0:
            warnings.append(f"{medium_count} medium severity issues found")

        return ContractRisk(
            contract_address=contract_address,
            chain=chain,
            risk_score=risk_score,
            risk_level=risk_level,
            provider="slither",
            vulnerabilities=vulnerabilities[:20],  # 限制数量
            vulnerability_count=len(detectors),
            high_severity_count=high_count,
            medium_severity_count=medium_count,
            low_severity_count=low_count,
            warnings=warnings,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def _empty_result(
        self,
        contract_address: str,
        chain: str,
        error_message: str,
    ) -> ContractRisk:
        """返回空结果"""
        return ContractRisk(
            contract_address=contract_address,
            chain=chain,
            risk_score=None,
            risk_level="unknown",
            provider="slither",
            warnings=[f"Analysis failed: {error_message}"],
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def _get_risk_level(self, score: float) -> str:
        """根据分数获取风险等级"""
        if score >= 50:
            return "critical"
        elif score >= 30:
            return "high"
        elif score >= 15:
            return "medium"
        else:
            return "low"

    def _build_meta(self, start_time: datetime, contract_address: str) -> SourceMeta:
        """构建SourceMeta"""
        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        return SourceMetaBuilder.build(
            provider=self.name,
            endpoint=f"/analyze/{contract_address}",
            ttl_seconds=86400,  # 24小时缓存
            response_time_ms=response_time_ms,
        )


# 全局实例
slither_analyzer = SlitherAnalyzer()
