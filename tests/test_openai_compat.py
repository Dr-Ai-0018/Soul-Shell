import pytest
import respx
import httpx
from soul_shell.adapters.openai_compat import OpenAICompatAdapter
from soul_shell.adapters.base import AdapterError


def _sse(chunks: list[str], done: bool = True) -> str:
    """构造 OpenAI SSE 响应体"""
    lines = []
    for content in chunks:
        import json
        data = {"choices": [{"delta": {"content": content}}]}
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}\n\n")
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines)


@pytest.mark.asyncio
async def test_basic_stream():
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=_sse(["你好", "世界"]))
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "test-key", "gpt-4")
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        assert chunks == ["你好", "世界"]


@pytest.mark.asyncio
async def test_system_injected_as_first_message():
    """system 参数应作为 role=system 的第一条消息"""
    captured_body = {}

    def capture(request, route):
        import json
        captured_body["messages"] = json.loads(request.content)["messages"]
        return httpx.Response(200, text=_sse(["ok"]))

    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            side_effect=capture
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "key", "model")
        async for _ in adapter.chat_stream(
            [{"role": "user", "content": "hello"}],
            system="你是 Soul"
        ):
            pass

    messages = captured_body["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "你是 Soul"
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_http_401_raises_adapter_error():
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=httpx.Response(401, json={"error": "invalid api key"})
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "bad-key", "model")
        with pytest.raises(AdapterError) as exc_info:
            async for _ in adapter.chat_stream([{"role": "user", "content": "hi"}]):
                pass
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_http_500_raises_adapter_error():
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "key", "model")
        with pytest.raises(AdapterError) as exc_info:
            async for _ in adapter.chat_stream([]):
                pass
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_done_marker_ends_stream():
    """[DONE] 之后的内容不应该被 yield"""
    extra_line = 'data: {"choices":[{"delta":{"content":"不该出现"}}]}\n\n'
    body = _sse(["正常内容"]) + extra_line

    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text=body)
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "key", "model")
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        assert "不该出现" not in chunks


@pytest.mark.asyncio
async def test_empty_delta_content_skipped():
    """delta.content 为 None 或空字符串时不 yield"""
    import json
    lines = [
        f'data: {json.dumps({"choices": [{"delta": {"role": "assistant"}}]})}\n\n',
        f'data: {json.dumps({"choices": [{"delta": {"content": ""}}]})}\n\n',
        f'data: {json.dumps({"choices": [{"delta": {"content": "有内容"}}]})}\n\n',
        "data: [DONE]\n\n",
    ]
    with respx.mock:
        respx.post("https://api.example.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, text="".join(lines))
        )
        adapter = OpenAICompatAdapter("https://api.example.com", "key", "model")
        chunks = []
        async for chunk in adapter.chat_stream([{"role": "user", "content": "hi"}]):
            chunks.append(chunk)
        assert chunks == ["有内容"]
