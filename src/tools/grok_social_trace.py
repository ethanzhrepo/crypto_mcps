"""
grok_social_trace 工具

使用 x.com 的 Grok 能力，对给定的关键提示词在 X/Twitter 上进行溯源分析：
- 找到消息最初的来源账号
- 判断该消息是否可能为推广信息
- 基于社交媒体 deepsearch 给出结构化解读
"""
import json
from datetime import datetime
from typing import Any, Dict, Optional

import httpx
import structlog

from src.core.models import (
    GrokOriginAccount,
    GrokSocialTraceInput,
    GrokSocialTraceOutput,
)

logger = structlog.get_logger()


class GrokSocialTraceTool:
    """
    基于 Grok (xAI) 的 X/Twitter 溯源工具。

    说明：
    - 实现假定使用 OpenAI 风格的 Chat Completions 接口：
      POST https://api.x.ai/v1/chat/completions
      headers: Authorization: Bearer <XAI_API_KEY>
    - 实际部署时，如果接口或模型名不同，可通过环境变量或配置调整。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.x.ai/v1",
        model: str = "grok-beta",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

        if not self.api_key:
            logger.warning(
                "grok_social_trace_api_key_missing",
                message="Grok Social Trace tool initialized without XAI API key; calls will fail until configured.",
            )
        else:
            logger.info("grok_social_trace_tool_initialized", model=self.model)

    async def execute(self, params: GrokSocialTraceInput | Dict[str, Any]) -> GrokSocialTraceOutput:
        """
        执行 Grok 溯源分析。

        输入可以是 Pydantic 模型或字典。
        """
        if isinstance(params, dict):
            params = GrokSocialTraceInput(**params)

        if not self.api_key:
            raise RuntimeError(
                "Grok Social Trace 未配置 API key，请设置环境变量 XAI_API_KEY 或在实例化时传入 api_key。"
            )

        logger.info(
            "grok_social_trace_execute_start",
            keyword_prompt=params.keyword_prompt,
            language=params.language,
        )

        system_prompt = (
            "You are Grok with full access to real-time X (Twitter) data. "
            "Given a short keyword-style prompt that describes a circulating message, "
            "you must:\n"
            "1) Trace the origin of this message on X and identify the earliest relevant post/author you can find.\n"
            "2) Decide whether this message is likely promotional/marketing/astroturfed content, and explain why.\n"
            "3) Perform a deep search across X to understand how this message spread, typical reactions, "
            "   and any notable related discussions or controversies.\n\n"
            "Return ONLY a compact JSON object in the following format (no extra text):\n"
            "{\n"
            '  "origin_account": {\n'
            '    "handle": "@..." | null,\n'
            '    "display_name": "..." | null,\n'
            '    "user_id": "..." | null,\n'
            '    "profile_url": "https://x.com/..." | null,\n'
            '    "first_post_url": "https://x.com/..." | null,\n'
            '    "first_post_timestamp": "ISO8601 string" | null,\n'
            '    "followers_count": number | null,\n'
            '    "is_verified": true | false | null\n'
            "  },\n"
            '  "is_likely_promotion": true | false,\n'
            '  "promotion_confidence": number (0-1) | null,\n'
            '  "promotion_rationale": "...",\n'
            '  "deepsearch_insights": "...",\n'
            '  "evidence_posts": [\n'
            "    {\n"
            '      "tweet_url": "https://x.com/...",\n'
            '      "author_handle": "@...",\n'
            '      "summary": "short description of why this post is relevant",\n'
            '      "type": "origin" | "amplification" | "reaction" | "fact_check" | "other"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        user_prompt = (
            f"Language preference: {params.language or 'auto'}.\n"
            f"Keyword prompt describing the message to trace:\n"
            f"{params.keyword_prompt}\n"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        # OpenAI 风格：choices[0].message.content
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            logger.error("grok_social_trace_invalid_response", error=str(e), data=data)
            raise RuntimeError("Grok API 响应格式异常，无法解析。") from e

        raw_text = content.strip()

        # 尝试解析为 JSON
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning(
                "grok_social_trace_non_json_response",
                message="Grok 返回的不是严格 JSON，将原文塞入 deepsearch_insights。",
            )
            now = datetime.utcnow()
            return GrokSocialTraceOutput(
                origin_account=None,
                is_likely_promotion=False,
                promotion_confidence=None,
                promotion_rationale=None,
                deepsearch_insights=raw_text,
                evidence_posts=[],
                raw_model_response=raw_text,
                as_of_utc=now,
            )

        origin_account_data = parsed.get("origin_account") or {}
        origin_account = None
        if isinstance(origin_account_data, dict) and origin_account_data:
            origin_account = GrokOriginAccount(**origin_account_data)

        now = datetime.utcnow()

        output = GrokSocialTraceOutput(
            origin_account=origin_account,
            is_likely_promotion=bool(parsed.get("is_likely_promotion", False)),
            promotion_confidence=parsed.get("promotion_confidence"),
            promotion_rationale=parsed.get("promotion_rationale"),
            deepsearch_insights=parsed.get(
                "deepsearch_insights",
                "Grok deepsearch insights not available in structured form; please inspect raw_model_response.",
            ),
            evidence_posts=parsed.get("evidence_posts") or [],
            raw_model_response=raw_text,
            as_of_utc=now,
        )

        logger.info(
            "grok_social_trace_execute_complete",
            keyword_prompt=params.keyword_prompt,
        )

        return output


__all__ = ["GrokSocialTraceTool"]
