"""
配置管理
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils.exceptions import ConfigurationError


class Settings(BaseSettings):
    """全局配置"""

    # 服务器配置
    mcp_server_host: str = Field(default="0.0.0.0", alias="MCP_SERVER_HOST")
    mcp_server_port: int = Field(default=8000, alias="MCP_SERVER_PORT")
    http_host: str = Field(default="0.0.0.0", alias="HTTP_HOST")
    http_port: int = Field(default=8000, alias="HTTP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")

    # API密钥
    coingecko_api_key: Optional[str] = Field(default=None, alias="COINGECKO_API_KEY")
    coingecko_api_type: str = Field(default="demo", alias="COINGECKO_API_TYPE")  # "demo" or "pro"
    coinmarketcap_api_key: Optional[str] = Field(
        default=None, alias="COINMARKETCAP_API_KEY"
    )
    etherscan_api_key: Optional[str] = Field(default=None, alias="ETHERSCAN_API_KEY")
    bscscan_api_key: Optional[str] = Field(default=None, alias="BSCSCAN_API_KEY")
    basescan_api_key: Optional[str] = Field(default=None, alias="BASESCAN_API_KEY")
    polygonscan_api_key: Optional[str] = Field(default=None, alias="POLYGONSCAN_API_KEY")
    arbiscan_api_key: Optional[str] = Field(default=None, alias="ARBISCAN_API_KEY")
    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    messari_api_key: Optional[str] = Field(default=None, alias="MESSARI_API_KEY")

    # 新增数据源API密钥
    fred_api_key: Optional[str] = Field(default=None, alias="FRED_API_KEY")
    cryptopanic_api_key: Optional[str] = Field(default=None, alias="CRYPTOPANIC_API_KEY")
    brave_search_api_key: Optional[str] = Field(default=None, alias="BRAVE_SEARCH_API_KEY")

    # 搜索引擎API密钥
    google_search_api_key: Optional[str] = Field(default=None, alias="GOOGLE_SEARCH_API_KEY")
    google_cse_id: Optional[str] = Field(default=None, alias="GOOGLE_CSE_ID")
    bing_search_api_key: Optional[str] = Field(default=None, alias="BING_SEARCH_API_KEY")
    serpapi_key: Optional[str] = Field(default=None, alias="SERPAPI_KEY")
    kaito_api_key: Optional[str] = Field(default=None, alias="KAITO_API_KEY")

    # Telegram Scraper配置
    telegram_scraper_url: str = Field(default="http://localhost:8000", alias="TELEGRAM_SCRAPER_URL")
    telegram_scraper_index: str = Field(default="telegram_messages", alias="TELEGRAM_SCRAPER_INDEX")

    # 衍生品和链上数据API密钥
    coinglass_api_key: Optional[str] = Field(default=None, alias="COINGLASS_API_KEY")
    whale_alert_api_key: Optional[str] = Field(default=None, alias="WHALE_ALERT_API_KEY")
    token_unlocks_api_key: Optional[str] = Field(default=None, alias="TOKEN_UNLOCKS_API_KEY")
    goplus_api_key: Optional[str] = Field(default=None, alias="GOPLUS_API_KEY")
    goplus_api_secret: Optional[str] = Field(default=None, alias="GOPLUS_API_SECRET")
    tally_api_key: Optional[str] = Field(default=None, alias="TALLY_API_KEY")
    thegraph_api_key: Optional[str] = Field(default=None, alias="THEGRAPH_API_KEY")

    # 合约风险分析提供商配置
    contract_risk_provider: str = Field(default="goplus", alias="CONTRACT_RISK_PROVIDER")

    # XAI (Grok) API密钥
    xai_api_key: Optional[str] = Field(default=None, alias="XAI_API_KEY")

    # 限流配置
    max_concurrent_requests: int = Field(default=20, alias="MAX_CONCURRENT_REQUESTS")
    rate_limit_coingecko: int = Field(default=50, alias="RATE_LIMIT_COINGECKO")
    rate_limit_coinmarketcap: int = Field(default=30, alias="RATE_LIMIT_COINMARKETCAP")
    rate_limit_etherscan: int = Field(default=5, alias="RATE_LIMIT_ETHERSCAN")
    rate_limit_github: int = Field(default=60, alias="RATE_LIMIT_GITHUB")

    # 超时配置
    default_request_timeout: float = Field(
        default=10.0, alias="DEFAULT_REQUEST_TIMEOUT"
    )
    slow_request_timeout: float = Field(default=30.0, alias="SLOW_REQUEST_TIMEOUT")

    # 功能开关
    enable_cache: bool = Field(default=True, alias="ENABLE_CACHE")
    enable_fallback: bool = Field(default=True, alias="ENABLE_FALLBACK")
    enable_metrics: bool = Field(default=False, alias="ENABLE_METRICS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_dir: Optional[Path] = None):
        """
        初始化配置管理器

        Args:
            config_dir: 配置文件目录，默认为项目根目录下的config/
        """
        if config_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = config_dir
        self._ttl_policies: Optional[Dict] = None
        self._data_sources: Optional[Dict] = None
        self._tools: Optional[Dict] = None
        self._settings: Optional[Settings] = None

    @property
    def settings(self) -> Settings:
        """获取全局设置"""
        if self._settings is None:
            self._settings = Settings()
        return self._settings

    @property
    def ttl_policies(self) -> Dict[str, Any]:
        """获取TTL策略配置"""
        if self._ttl_policies is None:
            self._ttl_policies = self._load_yaml("ttl_policies.yaml")
        return self._ttl_policies

    @property
    def data_sources(self) -> Dict[str, Any]:
        """获取数据源配置"""
        if self._data_sources is None:
            self._data_sources = self._load_yaml("data_sources.yaml")
        return self._data_sources

    @property
    def tools(self) -> Dict[str, Any]:
        """
        获取 MCP 工具开关配置。

        配置文件位于 config/tools.yaml，格式示例：

        crypto_overview:
          enabled: true
        """
        if self._tools is None:
            try:
                self._tools = self._load_yaml("tools.yaml")
            except ConfigurationError:
                # 如果未提供 tools.yaml，则默认所有工具启用
                self._tools = {}
        return self._tools

    def is_tool_enabled(self, tool_name: str) -> bool:
        """
        判断指定 MCP 工具是否启用。

        工具配置格式：
        <tool_name>:
          enabled: true/false

        如果 tools.yaml 不存在，或未配置指定工具，则默认启用。
        """
        tool_cfg = self.tools.get(tool_name, {})
        # 未配置时默认启用
        return bool(tool_cfg.get("enabled", True))

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """加载YAML配置文件"""
        filepath = self.config_dir / filename
        if not filepath.exists():
            raise ConfigurationError(f"Configuration file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse {filename}: {e}")

    def get_ttl(self, tool_name: str, field_type: str) -> int:
        """
        获取TTL配置

        Args:
            tool_name: 工具名称，如 crypto_overview
            field_type: 字段类型，如 basic, market

        Returns:
            TTL秒数
        """
        tool_config = self.ttl_policies.get(tool_name, {})
        return tool_config.get(field_type, self.ttl_policies.get("default", 300))

    def get_data_source_config(self, tool_name: str, capability: str) -> list:
        """
        获取数据源fallback链配置

        Args:
            tool_name: 工具名称
            capability: 能力类型，如 basic, market

        Returns:
            数据源配置列表（按优先级排序）
        """
        tool_config = self.data_sources.get(tool_name, {})
        sources = tool_config.get(capability, [])

        # 按优先级排序
        priority_order = {"PRIMARY": 1, "SECONDARY": 2, "TERTIARY": 3, "FALLBACK": 4}
        return sorted(sources, key=lambda x: priority_order.get(x.get("priority"), 999))

    def get_conflict_threshold(self, field_name: str) -> float:
        """
        获取冲突检测阈值

        Args:
            field_name: 字段名，如 price_diff_percent

        Returns:
            阈值（百分比）
        """
        thresholds = self.data_sources.get("conflict_thresholds", {})
        return thresholds.get(field_name, 1.0)

    def get_api_key(self, provider: str) -> Optional[str]:
        """
        获取API密钥

        Args:
            provider: 提供者名称，如 coingecko, etherscan

        Returns:
            API密钥
        """
        key_mapping = {
            "coingecko": self.settings.coingecko_api_key,
            "coinmarketcap": self.settings.coinmarketcap_api_key,
            "etherscan": self.settings.etherscan_api_key,
            "etherscan_ethereum": self.settings.etherscan_api_key,
            "etherscan_bsc": self.settings.bscscan_api_key,
            "etherscan_base": self.settings.basescan_api_key,
            "etherscan_polygon": self.settings.polygonscan_api_key,
            "etherscan_arbitrum": self.settings.arbiscan_api_key,
            "bscscan": self.settings.bscscan_api_key,
            "basescan": self.settings.basescan_api_key,
            "polygonscan": self.settings.polygonscan_api_key,
            "arbiscan": self.settings.arbiscan_api_key,
            "github": self.settings.github_token,
            "messari": self.settings.messari_api_key,
            # 新增数据源
            "fred": self.settings.fred_api_key,
            "cryptopanic": self.settings.cryptopanic_api_key,
            "brave_search": self.settings.brave_search_api_key,
            # 搜索引擎
            "google_search": self.settings.google_search_api_key,
            "google_cse_id": self.settings.google_cse_id,
            "bing_search": self.settings.bing_search_api_key,
            "serpapi": self.settings.serpapi_key,
            "kaito": self.settings.kaito_api_key,
            # 衍生品和链上数据
            "coinglass": self.settings.coinglass_api_key,
            "whale_alert": self.settings.whale_alert_api_key,
            "token_unlocks": self.settings.token_unlocks_api_key,
            "goplus": self.settings.goplus_api_key,
            "goplus_secret": self.settings.goplus_api_secret,
            "tally": self.settings.tally_api_key,
            # XAI (Grok)
            "xai": self.settings.xai_api_key,
            # The Graph
            "thegraph": self.settings.thegraph_api_key,
        }
        return key_mapping.get(provider.lower())


# 全局配置实例
config = ConfigManager()
