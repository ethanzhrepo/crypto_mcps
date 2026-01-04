"""
onchain_contract_risk 工具实现

基于 GoPlus 或 Slither 提供合约风险评估。
"""
import time
from datetime import datetime

import structlog

from src.core.models import (
    ContractRisk,
    OnchainContractRiskInput,
    OnchainContractRiskOutput,
    SourceMeta,
)
from src.data_sources.goplus import GoPlusClient
from src.utils.config import config
from src.utils.security import slither_analyzer

logger = structlog.get_logger()


class OnchainContractRiskTool:
    """onchain_contract_risk 工具"""

    def __init__(self):
        logger.info("onchain_contract_risk_tool_initialized")

    async def execute(
        self, params: OnchainContractRiskInput
    ) -> OnchainContractRiskOutput:
        start_time = time.time()
        logger.info(
            "onchain_contract_risk_execute_start",
            contract_address=params.contract_address,
            chain=params.chain,
        )

        warnings: list[str] = []
        source_metas: list[SourceMeta] = []

        provider = config.settings.contract_risk_provider.lower()

        if provider == "slither":
            # 使用 Slither 静态分析
            try:
                contract_risk, meta = await slither_analyzer.analyze_contract(
                    contract_address=params.contract_address,
                    chain=params.chain,
                    etherscan_api_key=config.get_api_key("etherscan"),
                )
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("Slither contract analysis failed", error=str(exc))
                warnings.append(f"Slither analysis failed: {exc}")
                contract_risk = ContractRisk(
                    contract_address=params.contract_address,
                    chain=params.chain,
                    risk_score=None,
                    risk_level="unknown",
                    provider="slither",
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
        else:
            # 默认 GoPlus
            goplus = GoPlusClient()
            try:
                contract_risk, meta = await goplus.get_token_security(
                    contract_address=params.contract_address,
                    chain=params.chain,
                )
                source_metas.append(meta)
            except Exception as exc:
                logger.warning("GoPlus token security fetch failed", error=str(exc))
                warnings.append(f"GoPlus token security fetch failed: {exc}")
                contract_risk = ContractRisk(
                    contract_address=params.contract_address,
                    chain=params.chain,
                    risk_score=None,
                    risk_level="unknown",
                    provider="goplus",
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )

        elapsed = time.time() - start_time
        logger.info(
            "onchain_contract_risk_execute_complete",
            contract_address=params.contract_address,
            elapsed_ms=round(elapsed * 1000, 2),
            warnings=len(warnings),
        )

        return OnchainContractRiskOutput(
            contract_risk=contract_risk,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )

