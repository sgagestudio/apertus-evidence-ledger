from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class ModelError(RuntimeError):
    pass


class JsonChatModel(Protocol):
    model: str

    def generate_json(self, *, system: str, user: str) -> dict:
        ...


@dataclass
class ApertusClient:
    """Minimal OpenAI-compatible client for local vLLM or hosted Apertus endpoints."""

    base_url: str = "http://localhost:8000/v1"
    model: str = "swiss-ai/Apertus-v1.5-8B"
    api_key: str | None = None
    timeout_seconds: float = 90.0

    def generate_json(self, *, system: str, user: str) -> dict:
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelError(f"Apertus endpoint request failed: {exc}") from exc

        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError("Apertus endpoint returned an unexpected response shape") from exc

        return parse_json_object(str(content))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def parse_json_object(content: str) -> dict:
    text = content.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        lines = text.splitlines()
        if lines and lines[0].startswith(fence):
            lines = lines[1:]
        if lines and lines[-1].strip() == fence:
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json\n"):
            text = text[5:].lstrip()

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ModelError("Model did not return a JSON object")

    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ModelError(f"Model returned invalid JSON: {exc}") from exc

    if not isinstance(value, dict):
        raise ModelError("Model JSON output must be an object")
    return value
