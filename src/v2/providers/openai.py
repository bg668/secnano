from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, model: str = "gpt-4.1-mini"):
        self._model = model

    def generate(self, prompt: str) -> str:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI provider")

        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as response:  # nosec B310
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"openai request failed: {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"openai request failed: {exc.reason}") from exc

        return data["choices"][0]["message"]["content"].strip()
