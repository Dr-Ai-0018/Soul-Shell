import json
from typing import AsyncIterator

import httpx

from .base import AdapterError
from ..config.defaults import DEFAULT_CONNECT_TIMEOUT

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicAdapter:
    """
    Anthropic Claude Messages API 流式适配器。
    SSE 格式：每组两行，event: xxx / data: {...}
    system 作为顶层字段，不进 messages。
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
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system

        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=None,
            write=30.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/messages",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise AdapterError(
                        "请求失败",
                        status_code=response.status_code,
                        body=body.decode(errors="replace"),
                    )

                current_event = ""
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:].strip()
                    elif line.startswith("data: "):
                        if current_event == "content_block_delta":
                            try:
                                data = json.loads(line[6:])
                                text = (
                                    data.get("delta", {}).get("text") or ""
                                )
                                if text:
                                    yield text
                            except json.JSONDecodeError:
                                pass
                        elif current_event == "message_stop":
                            return
