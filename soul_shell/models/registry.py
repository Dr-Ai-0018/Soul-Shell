from .channel import Channel, ActiveModel
from ..adapters.base import ModelAdapter, AdapterError
from ..adapters.openai_compat import OpenAICompatAdapter
from ..adapters.anthropic import AnthropicAdapter
from ..adapters.gemini import GeminiAdapter

_ADAPTER_FACTORY = {
    "openai": OpenAICompatAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}


class ModelRegistry:
    def __init__(self, channels: list[Channel]):
        self._channels: dict[str, Channel] = {c.name: c for c in channels}
        self._active: ActiveModel | None = None
        if channels:
            ch = channels[0]
            self._active = ActiveModel(channel=ch, model_id=ch.default_model)

    @property
    def active(self) -> ActiveModel | None:
        return self._active

    @property
    def channels(self) -> dict[str, Channel]:
        return self._channels

    def get_adapter(self) -> ModelAdapter:
        if not self._active:
            raise RuntimeError(
                "没有可用的渠道，请先配置 ~/.config/soul-shell/channels.toml"
            )
        ch = self._active.channel
        cls = _ADAPTER_FACTORY.get(ch.provider)
        if not cls:
            raise ValueError(f"未知 provider: {ch.provider}，支持：openai / anthropic / gemini")
        return cls(
            base_url=ch.base_url,
            api_key=ch.api_key,
            model=self._active.model_id,
        )

    def switch(self, spec: str) -> str:
        """
        spec 格式：
          "channel_name"             -> 切换渠道，用 default_model
          "channel_name/model_id"    -> 切换到指定渠道的指定模型
        返回切换后的 display_name，失败抛 ValueError。
        """
        if "/" in spec:
            ch_name, model_id = spec.split("/", 1)
        else:
            ch_name, model_id = spec, None

        ch = self._channels.get(ch_name)
        if not ch:
            available = ", ".join(self._channels.keys()) or "（无）"
            raise ValueError(f"渠道 '{ch_name}' 不存在，可用：{available}")

        if model_id and model_id not in ch.models:
            available = ", ".join(ch.models) or "（无）"
            raise ValueError(
                f"模型 '{model_id}' 不在渠道 '{ch_name}' 的列表里，可用：{available}"
            )

        self._active = ActiveModel(
            channel=ch,
            model_id=model_id or ch.default_model,
        )
        return self._active.display_name

    def list_all(self) -> str:
        if not self._channels:
            return "  （没有配置任何渠道）"
        lines = []
        for ch in self._channels.values():
            for m in ch.models:
                is_active = (
                    self._active is not None
                    and self._active.channel.name == ch.name
                    and self._active.model_id == m
                )
                marker = " ← 当前" if is_active else ""
                lines.append(f"  {ch.name}/{m}  [{ch.provider}]{marker}")
        return "\n".join(lines)
