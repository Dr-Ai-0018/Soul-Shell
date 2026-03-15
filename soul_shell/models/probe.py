import httpx
from .channel import Channel
from ..config.defaults import DEFAULT_CONNECT_TIMEOUT


async def probe_models(channel: Channel) -> list[str]:
    """
    对 OpenAI 兼容渠道调用 GET /v1/models，返回 model id 列表。
    非 openai provider 或请求失败时返回空列表（静默处理）。
    """
    if channel.provider != "openai":
        return []

    headers = {}
    if channel.api_key:
        headers["Authorization"] = f"Bearer {channel.api_key}"

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_CONNECT_TIMEOUT) as client:
            resp = await client.get(
                f"{channel.base_url}/v1/models",
                headers=headers,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [m["id"] for m in data.get("data", []) if "id" in m]
    except Exception:
        return []
