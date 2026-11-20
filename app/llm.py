from __future__ import annotations

from openai import OpenAI

from .config import Settings


class DeepSeekClient:
    mode = "deepseek"

    def __init__(self, settings: Settings):
        if not settings.deepseek_api_key:
            raise ValueError("真实模式需要 DEEPSEEK_API_KEY；离线体验请设置 AINEWS_DEMO_MODE=true")
        self.model = settings.deepseek_model
        self.client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url, timeout=settings.agent_timeout_seconds)

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.model_dump(exclude_none=True)
