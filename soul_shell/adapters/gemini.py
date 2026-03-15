import json
from typing import AsyncIterator

import httpx

from .base import AdapterError
from ..config.defaults import DEFAULT_CONNECT_TIMEOUT


class GeminiAdapter:
    """
    Google Gemini streamGenerateContent 流式适配器。
    认证：?key=API_KEY query param（无 Authorization header）。
    role 映射：assistant → model（Gemini 不认 "assistant"）。
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
        # role 映射，并转换 content 格式
        gemini_messages = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else m["role"]
            gemini_messages.append({
                "role": role,
                "parts": [{"text": m["content"]}],
            })

        # Gemini 要求最后一条必须是 user
        if gemini_messages and gemini_messages[-1]["role"] != "user":
            raise AdapterError("Gemini 要求最后一条消息的 role 必须是 user")

        payload: dict = {"contents": gemini_messages}
        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

        url = (
            f"{self._base_url}/v1beta/models/{self._model}"
            f":streamGenerateContent?alt=sse&key={self._api_key}"
        )

        timeout = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT,
            read=None,
            write=30.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise AdapterError(
                        "请求失败",
                        status_code=response.status_code,
                        body=body.decode(errors="replace"),
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        text = (
                            chunk.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                        )
                        if text:
                            yield text
                    except (json.JSONDecodeError, IndexError, KeyError):
                        pass
