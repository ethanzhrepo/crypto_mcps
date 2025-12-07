"""
合约安全分析工具

使用 GoPlus API 进行智能合约风险评估
"""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.core.models import ContractRisk
from src.data_sources.goplus.client import GoPlusClient


class ContractAnalysisInput(BaseModel):
    """合约分析输入参数"""
    contract_address: str = Field(..., description="智能合约地址")
    chain: str = Field(default="ethereum", description="区块链网络")


class ContractAnalysisOutput(BaseModel):
    """合约分析输出结果"""
    contract_address: str
    chain: str
    risk_score: float
    risk_level: str
    is_open_source: Optional[bool] = None
    is_proxy: Optional[bool] = None
    is_mintable: Optional[bool] = None
    is_honeypot: Optional[bool] = None
    buy_tax: Optional[float] = None
    sell_tax: Optional[float] = None
    holder_count: Optional[int] = None
    warnings: list[str] = []
    provider: str = "goplus"
    timestamp: str = ""


class ContractAnalysisTool:
    """合约安全分析工具"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        初始化合约分析工具

        Args:
            api_key: GoPlus API密钥（可选）
            api_secret: GoPlus API密钥对应的Secret
        """
        self.goplus_client = GoPlusClient(api_key=api_key, api_secret=api_secret)

    async def execute(self, params: Dict[str, Any]) -> ContractAnalysisOutput:
        """
        执行合约安全分析

        Args:
            params: 包含 contract_address 和 chain 的字典

        Returns:
            ContractAnalysisOutput 合约风险分析结果
        """
        # 解析输入参数
        input_params = ContractAnalysisInput(**params)

        # 调用 GoPlus API 获取合约安全信息
        contract_risk, meta = await self.goplus_client.get_token_security(
            contract_address=input_params.contract_address,
            chain=input_params.chain
        )

        # 转换为输出格式
        return ContractAnalysisOutput(
            contract_address=contract_risk.contract_address,
            chain=contract_risk.chain,
            risk_score=contract_risk.risk_score,
            risk_level=contract_risk.risk_level,
            is_open_source=contract_risk.is_open_source,
            is_proxy=contract_risk.is_proxy,
            is_mintable=contract_risk.is_mintable,
            is_honeypot=contract_risk.is_honeypot,
            buy_tax=contract_risk.buy_tax,
            sell_tax=contract_risk.sell_tax,
            holder_count=contract_risk.holder_count,
            warnings=contract_risk.warnings or [],
            provider=contract_risk.provider,
            timestamp=contract_risk.timestamp
        )
