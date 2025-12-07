"""
自定义异常类
"""


class MCPServerError(Exception):
    """MCP服务器基础异常"""

    pass


class ConfigurationError(MCPServerError):
    """配置错误"""

    pass


class DataSourceError(MCPServerError):
    """数据源错误基类"""

    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message
        super().__init__(f"[{source}] {message}")


class DataSourceTimeoutError(DataSourceError):
    """数据源超时"""

    pass


class DataSourceRateLimitError(DataSourceError):
    """数据源限流"""

    pass


class DataSourceAuthError(DataSourceError):
    """数据源认证错误"""

    pass


class DataSourceNotFoundError(DataSourceError):
    """数据源未找到资源"""

    pass


class AllSourcesFailedError(MCPServerError):
    """所有数据源都失败"""

    def __init__(self, capability: str, errors: dict):
        self.capability = capability
        self.errors = errors
        error_summary = "\n".join([f"  - {k}: {v}" for k, v in errors.items()])
        super().__init__(f"All sources failed for {capability}:\n{error_summary}")


class AmbiguousSymbolError(MCPServerError):
    """符号歧义错误"""

    def __init__(self, symbol: str, matches: list):
        self.symbol = symbol
        self.matches = matches
        super().__init__(
            f"Ambiguous symbol '{symbol}'. Multiple matches found: {matches}. "
            "Please specify 'chain' or 'token_address' parameter."
        )


class CacheError(MCPServerError):
    """缓存错误"""

    pass


class ValidationError(MCPServerError):
    """数据验证错误"""

    pass
