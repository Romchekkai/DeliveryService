from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "Ты — оператор службы поддержки сервиса доставки посылок. "
    "Отвечай на русском языке, кратко и по делу. "
    "Используй ТОЛЬКО факты из предоставленного контекста. "
    "Если в контексте нет ответа — так и скажи и предложи обратиться к оператору. "
    "Не выдумывай правила, цены и сроки."
)


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, question: str, context: str) -> Any: ...


class OpenAICompatibleLLMClient(LLMClient):
    """Работает с любым OpenAI-совместимым API: OpenAI, Ollama, vLLM, LM Studio."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        temperature: float = 0.2,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature

    async def generate(self, question: str, context: str) -> Any:
        user_prompt = (
            f"Контекст из базы знаний:\n{context}\n\nВопрос пользователя: {question}\n\nОтвет:"
        )

        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()
