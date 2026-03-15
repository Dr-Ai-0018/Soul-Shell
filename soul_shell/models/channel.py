from dataclasses import dataclass, field


@dataclass
class Channel:
    name: str
    provider: str          # "openai" | "anthropic" | "gemini"
    base_url: str
    api_key: str
    models: list[str] = field(default_factory=list)
    default_model: str = ""

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")
        if not self.default_model and self.models:
            self.default_model = self.models[0]

    @classmethod
    def from_dict(cls, d: dict) -> "Channel":
        return cls(
            name=d["name"],
            provider=d["provider"],
            base_url=d["base_url"],
            api_key=d.get("api_key", ""),
            models=d.get("models", []),
            default_model=d.get("default_model", ""),
        )


@dataclass
class ActiveModel:
    channel: Channel
    model_id: str

    @property
    def display_name(self) -> str:
        return f"{self.channel.name}/{self.model_id}"
