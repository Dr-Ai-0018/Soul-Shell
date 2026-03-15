import json
from typing import AsyncIterator

import httpx

from .base import AdapterError
from ..config.defaults import DEFAULT_CONNECT_TIMEOUT


class OpenAICompatAdapter:
    """
    兼容 OpenAI Chat Completions 协议的流式适配器。
    适用于：OpenAI、DeepSeek、Ollama、vLLM 等兼容实现。
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def chat_stream(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AsyncIterator[str]:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        headers = {
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": full_messages,
            "stream": True,
        }

        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=None,   # 慢速模型不超时
            write=30.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise AdapterError(
                        f"请求失败",
                        status_code=response.status_code,
                        body=body.decode(errors="replace"),
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:]
                    if payload_str.strip() == "[DONE]":
                        return
                    try:
                        chunk = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue

                    content = (
                        chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content") or ""
                    )
                    if content:
                        yield content
