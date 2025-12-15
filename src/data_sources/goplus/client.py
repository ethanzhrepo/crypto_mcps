"""
GoPlus Security API客户端 - 合约风险评估

API文档: https://docs.gopluslabs.io/
"""
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.models import ContractRisk, SourceMeta
from src.data_sources.base import BaseDataSource


class GoPlusClient(BaseDataSource):
    """GoPlus Security API客户端"""

    BASE_URL = "https://api.gopluslabs.io/api/v1"

    # 链ID映射
    CHAIN_IDS = {
        "ethereum": "1",
        "bsc": "56",
        "polygon": "137",
        "arbitrum": "42161",
        "optimism": "10",
        "avalanche": "43114",
        "fantom": "250",
        "cronos": "25",
        "base": "8453",
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        初始化GoPlus客户端

        Args:
            api_key: API密钥（可选，免费版不需要）
            api_secret: API密钥对应的Secret（与api_key配合使用）
        """
        super().__init__(
            name="goplus",
            base_url=self.BASE_URL,
            timeout=15.0,
            requires_api_key=False,  # 免费版可用
        )
        self.api_key = api_key
        self.api_secret = api_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _generate_signature(self, timestamp: int) -> str:
        """
        生成API签名

        签名算法: SHA1(app_key + timestamp + secret)

        Args:
            timestamp: Unix时间戳（秒）

        Returns:
            SHA1签名字符串
        """
        sign_str = f"{self.api_key}{timestamp}{self.api_secret}"
        return hashlib.sha1(sign_str.encode('utf-8')).hexdigest()

    async def _get_access_token(self) -> Optional[str]:
        """
        获取访问令牌

        使用api_key和api_secret生成签名，换取access_token

        Returns:
            访问令牌，如果认证失败则返回None
        """
        # 检查是否有有效的缓存token
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # 如果没有配置密钥，返回None（使用免费模式）
        if not self.api_key or not self.api_secret:
            return None

        # 生成签名
        timestamp = int(time.time())
        sign = self._generate_signature(timestamp)

        # 请求access_token
        try:
            response = await self._make_request(
                "POST",
                "/token",
                json_data={
                    "app_key": self.api_key,
                    "sign": sign,
                    "time": timestamp
                }
            )

            if response and response.get("code") == 1:
                result = response.get("result", {})
                self._access_token = result.get("access_token")
                # Token有效期默认24小时，提前5分钟刷新
                expires_in = result.get("expires_in", 86400)
                self._token_expires_at = time.time() + expires_in - 300
                return self._access_token
        except Exception:
            # 认证失败，回退到免费模式
            pass

        return None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Accept": "application/json",
        }
        if self._access_token:
            headers["Authorization"] = self._access_token
        return headers

    async def _ensure_authenticated(self) -> None:
        """确保已认证（如果配置了密钥）"""
        if self.api_key and self.api_secret:
            await self._get_access_token()

    async def fetch_raw(self, endpoint: str, params: Optional[Dict] = None, base_url_override: Optional[str] = None, headers: Optional[Dict[str, str]] = None) -> Any:
        """获取原始数据"""
        return await self._make_request("GET", endpoint, params, base_url_override, headers)

    def transform(self, raw_data: Any, data_type: str) -> Any:
        """转换原始数据"""
        if data_type == "token_security":
            return self._transform_token_security(raw_data)
        return raw_data

    async def get_token_security(
        self,
        contract_address: str,
        chain: str = "ethereum",
    ) -> tuple[ContractRisk, SourceMeta]:
        """
        获取代币安全信息

        Args:
            contract_address: 合约地址
            chain: 链名称

        Returns:
            (合约风险数据, SourceMeta)
        """
        # 确保已认证（如果配置了密钥）
        await self._ensure_authenticated()

        chain_id = self.CHAIN_IDS.get(chain.lower(), "1")
        endpoint = f"/token_security/{chain_id}"
        params = {
            "contract_addresses": contract_address.lower(),
        }

        data, meta = await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="token_security",
            ttl_seconds=3600,  # 1小时缓存
        )

        # 转换为ContractRisk模型
        address_lower = contract_address.lower()
        token_data = data.get(address_lower, {})

        # 计算风险分数
        risk_score = self._calculate_risk_score(token_data)
        risk_level = self._get_risk_level(risk_score)

        contract_risk = ContractRisk(
            contract_address=contract_address,
            chain=chain,
            risk_score=risk_score,
            risk_level=risk_level,
            provider="goplus",
            # GoPlus安全检查
            is_open_source=self._bool_from_str(token_data.get("is_open_source")),
            is_proxy=self._bool_from_str(token_data.get("is_proxy")),
            is_mintable=self._bool_from_str(token_data.get("is_mintable")),
            can_take_back_ownership=self._bool_from_str(token_data.get("can_take_back_ownership")),
            owner_change_balance=self._bool_from_str(token_data.get("owner_change_balance")),
            hidden_owner=self._bool_from_str(token_data.get("hidden_owner")),
            selfdestruct=self._bool_from_str(token_data.get("selfdestruct")),
            external_call=self._bool_from_str(token_data.get("external_call")),
            # 代币风险
            buy_tax=self._safe_float(token_data.get("buy_tax")),
            sell_tax=self._safe_float(token_data.get("sell_tax")),
            is_honeypot=self._bool_from_str(token_data.get("is_honeypot")),
            holder_count=self._safe_int(token_data.get("holder_count")),
            # 通用
            warnings=self._extract_warnings(token_data),
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        return contract_risk, meta

    async def get_address_security(
        self,
        address: str,
        chain: str = "ethereum",
    ) -> tuple[Dict, SourceMeta]:
        """
        获取地址安全信息

        Args:
            address: 钱包地址
            chain: 链名称

        Returns:
            (地址安全数据, SourceMeta)
        """
        # 确保已认证（如果配置了密钥）
        await self._ensure_authenticated()

        chain_id = self.CHAIN_IDS.get(chain.lower(), "1")
        endpoint = f"/address_security/{address}"
        params = {"chain_id": chain_id}

        return await self.fetch(
            endpoint=endpoint,
            params=params,
            data_type="address_security",
            ttl_seconds=3600,
        )

    def _transform_token_security(self, raw_data: Any) -> Dict:
        """转换代币安全数据"""
        if not raw_data or raw_data.get("code") != 1:
            return {}

        result = raw_data.get("result", {})
        return result

    def _bool_from_str(self, value: Any) -> Optional[bool]:
        """将字符串转换为布尔值"""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value == "1" or value.lower() == "true"
        return bool(value)

    def _safe_float(self, value: Any) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        """安全转换为整数"""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _calculate_risk_score(self, token_data: Dict) -> float:
        """计算风险分数（0-100，越高风险越大）"""
        score = 0

        # 高风险因素
        if self._bool_from_str(token_data.get("is_honeypot")):
            score += 50
        if self._bool_from_str(token_data.get("hidden_owner")):
            score += 20
        if self._bool_from_str(token_data.get("selfdestruct")):
            score += 15
        if self._bool_from_str(token_data.get("can_take_back_ownership")):
            score += 15

        # 中风险因素
        if self._bool_from_str(token_data.get("is_mintable")):
            score += 10
        if self._bool_from_str(token_data.get("owner_change_balance")):
            score += 10
        if self._bool_from_str(token_data.get("external_call")):
            score += 5

        # 税费风险
        buy_tax = self._safe_float(token_data.get("buy_tax")) or 0
        sell_tax = self._safe_float(token_data.get("sell_tax")) or 0
        if buy_tax > 0.1 or sell_tax > 0.1:  # >10%
            score += 15
        elif buy_tax > 0.05 or sell_tax > 0.05:  # >5%
            score += 5

        # 正面因素（降低风险）
        if self._bool_from_str(token_data.get("is_open_source")):
            score -= 10

        return max(0, min(100, score))

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

    def _extract_warnings(self, token_data: Dict) -> List[str]:
        """提取警告信息"""
        warnings = []

        if self._bool_from_str(token_data.get("is_honeypot")):
            warnings.append("Honeypot detected")
        if self._bool_from_str(token_data.get("hidden_owner")):
            warnings.append("Hidden owner detected")
        if self._bool_from_str(token_data.get("selfdestruct")):
            warnings.append("Contract can self-destruct")
        if self._bool_from_str(token_data.get("can_take_back_ownership")):
            warnings.append("Ownership can be taken back")
        if self._bool_from_str(token_data.get("is_mintable")):
            warnings.append("Token is mintable")

        buy_tax = self._safe_float(token_data.get("buy_tax")) or 0
        sell_tax = self._safe_float(token_data.get("sell_tax")) or 0
        if buy_tax > 0.1:
            warnings.append(f"High buy tax: {buy_tax*100:.1f}%")
        if sell_tax > 0.1:
            warnings.append(f"High sell tax: {sell_tax*100:.1f}%")

        return warnings

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 检查WETH合约
            data, _ = await self.get_token_security(
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
                "ethereum"
            )
            return data is not None
        except Exception:
            return False
