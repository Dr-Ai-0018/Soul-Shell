from typing import Protocol, AsyncIterator, runtime_checkable


class AdapterError(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code:
            return f"HTTP {self.status_code}: {base}"
        return base


@runtime_checkable
class ModelAdapter(Protocol):
    async def chat_stream(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """逐 token yield 纯文本内容，异常统一抛 AdapterError"""
        ...
