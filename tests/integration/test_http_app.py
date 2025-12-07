"""
MCP HTTP REST API 实际环境测试

这些测试在独立容器中通过HTTP访问已启动的FastAPI服务，触发真实第三方API调用。
每个测试都会把接口响应写入 /tmp，方便在 Docker 测试容器中查看。
"""
import json
import os
from pathlib import Path

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.integration, pytest.mark.live, pytest.mark.live_free]


@pytest.fixture(scope="module")
def base_url():
    """从环境变量读取目标HTTP地址，默认指向本地转发端口"""
    return os.getenv("MCP_HTTP_BASE_URL", "http://localhost:8001")


@pytest.fixture(scope="module")
async def rest_client(base_url):
    """面向真实HTTP服务器的AsyncClient"""
    async with AsyncClient(base_url=base_url, timeout=60.0) as client:
        yield client


@pytest.fixture
def record_response():
    """将接口响应持久化到 /tmp 目录"""

    def _record(name: str, response):
        payload = {
            "status_code": response.status_code,
            "body": response.json(),
        }
        path = Path("/tmp") / f"mcp_server_{name}_response.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        return path

    return _record


@pytest.mark.asyncio
async def test_health_endpoint(rest_client, record_response):
    """健康检查应返回服务状态并保存响应"""
    response = await rest_client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "mcp-server"
    assert "tools_count" in body

    record_response("health", response)


@pytest.mark.asyncio
async def test_list_tools_endpoint(rest_client, record_response):
    """工具列表应返回可用REST端点信息，并与健康检查中的工具数量一致"""
    response = await rest_client.get("/tools")
    assert response.status_code == 200

    body = response.json()
    assert "tools" in body
    tools = body["tools"]
    assert isinstance(tools, list)
    assert len(tools) > 0

    # /tools 返回的数量应与 /health 中的 tools_count 一致，避免硬编码工具个数
    health_response = await rest_client.get("/health")
    assert health_response.status_code == 200
    health_body = health_response.json()
    assert len(tools) == health_body.get("tools_count")

    # 至少包含核心工具端点
    endpoints = {tool["endpoint"] for tool in tools}
    core_endpoints = {
        "/tools/crypto_overview",
        "/tools/market_microstructure",
        "/tools/derivatives_hub",
        "/tools/web_research_search",
        "/tools/macro_hub",
        "/tools/draw_chart",
    }
    assert core_endpoints.issubset(endpoints)

    record_response("tools_list", response)


@pytest.mark.asyncio
async def test_crypto_overview_endpoint_live(rest_client, record_response):
    """POST /tools/crypto_overview 需要访问真实外部API"""
    payload = {"symbol": "btc", "include_fields": ["basic", "market"]}
    response = await rest_client.post("/tools/crypto_overview", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTC"
    assert body["data"]["market"]["price"] > 0

    record_response("crypto_overview", response)


@pytest.mark.asyncio
async def test_derivatives_endpoint_live(rest_client, record_response):
    """POST /tools/derivatives_hub 应返回真实衍生品数据"""
    payload = {"symbol": "BTCUSDT", "include_fields": ["funding_rate", "open_interest"]}
    response = await rest_client.post("/tools/derivatives_hub", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    funding = body["data"]["funding_rate"]
    assert isinstance(funding["funding_rate"], (int, float))
    assert funding["funding_rate_annual"] is not None

    record_response("derivatives_hub", response)


@pytest.mark.asyncio
async def test_market_microstructure_endpoint_live(rest_client, record_response):
    """POST /tools/market_microstructure 调用真实市场数据"""
    payload = {
        "symbol": "BTC/USDT",
        "venues": ["binance"],
        "include_fields": ["ticker"],
    }
    response = await rest_client.post("/tools/market_microstructure", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["data"]["ticker"]["last_price"] > 0

    record_response("market_microstructure", response)


@pytest.mark.asyncio
async def test_crypto_overview_validation_error(rest_client, record_response):
    """非法参数应返回422并记录响应"""
    payload = {"symbol": "btc", "include_fields": ["invalid_field"]}
    response = await rest_client.post("/tools/crypto_overview", json=payload)
    assert response.status_code == 422

    body = response.json()
    error_msgs = " ".join(err.get("msg", "") for err in body.get("detail", []))
    assert "Invalid field" in error_msgs

    record_response("crypto_overview_validation_error", response)
